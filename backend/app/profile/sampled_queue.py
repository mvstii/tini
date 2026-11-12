"""`queue-8` birleşik havuz (PR-6): dört kaynaktan karışım, rerank ve kaynak etiketi.

Yalnızca `queue_sampler_enabled` açıkken `queue()` tarafından çağrılır; kapalıyken `queue-7`
yolu değişmeden çalışır. Burada servis çağrısı yalnızca mahalle önerisi (`suggest_items`,
hızlı yol kapalıyken) içindedir; sonda/joker kartları doldurucu tarafından önceden çözülür.
"""
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.tags import GenrePairs, load_genre_pairs
from app.config import GraphSettings, ProfileSettings, RecommendSettings
from app.models import ListenLater, TasteProfile, User
from app.profile.probe import genre_shares, genre_theta, probe_and_joker, profile_genre_shares
from app.profile.queue import song_key
from app.profile.sampler import (
    Cand,
    genre_targets,
    interleave,
    noisy_rank,
    rerank,
    source_mix,
    source_quota,
)
from app.profile.service import VoteView
from app.profile.suggest import connected_adapter, ready_suggestions, suggest_items
from app.profile.track_artists import track_artists
from app.recommend.genres import GENRES


def sampled_items(
    db: Session, user: User, http, now: datetime, *,
    size: int, seed: int, fresh: Mapping[int, tuple], library: Sequence[int],
    expired: set[int], recent_set: set[int], prior: Sequence[int],
    voted_meta: Sequence[tuple], cfg: ProfileSettings, rcfg: RecommendSettings,
    gcfg: GraphSettings, votes: VoteView, shared_artists: Mapping[int, int | None],
    profile: TasteProfile | None, adapter: Callable | None = None,
) -> tuple[list[dict], int | None]:
    """(sıralı kart öğeleri, hazır öneri toplamı | None). Her öğede `source` ve (varsa) gerekçe.

    `library`: kütüphane parçaları öncelik sırasında; `fresh[t] = (id, artist, title, artists,
    expires, image)`. Kaynak boşsa payı diğerlerine kayar; parti küçülmez (varsa aday).
    `votes`, `shared_artists` (oylanan parça -> paylaşılan sanatçı) ve `profile` `queue()`
    tarafından bir kez okunur; burada yeniden sorgulanmaz."""
    voted_ids = votes.track_ids
    later = set(db.scalars(select(ListenLater.track_id).where(ListenLater.user_id == user.id)))
    exclude = voted_ids | later | recent_set | expired
    nb_exclude = set(fresh) | exclude
    ready_total = None
    k = max(cfg.queue_oversample, 1)
    if cfg.fast_queue_enabled:
        neighborhood, ready_total = ready_suggestions(db, user, now, size * k, nb_exclude)
    else:
        neighborhood = suggest_items(
            db, user, adapter or (lambda: connected_adapter(db, user, http)), now, size,
            nb_exclude, cfg, rcfg, gcfg,
        )
    # Tazelik: öneri sırası tohumla sarsılır; yoksa her oturumda aynı öneri aynı yuvaya düşer.
    neighborhood = noisy_rank(neighborhood, cfg.queue_gumbel_tau, seed, lambda i: i["track"])
    lib = [
        {"track": t, "title": fresh[t][2], "artists": fresh[t][3], "image": fresh[t][5],
         "artist": fresh[t][1]}
        for t in library[: size * k]
    ]
    # Sanatçısı bilinen/aranmış parçalar (None: arandı, yok); rerank bunları yeniden sorgulamaz.
    nb_artist = track_artists(db, user.id, [i["track"] for i in neighborhood])
    resolved: dict[int, int | None] = {i["track"]: i["artist"] for i in lib}
    resolved.update({i["track"]: nb_artist.get(i["track"]) for i in neighborhood})
    # Türler tek sorguda: oylanan sanatçılar (θ) + aday sanatçıları + önceki kartlar (rerank).
    genres = GenrePairs(db)
    genres.get(
        {shared_artists.get(t) for t in voted_ids} - {None}
        | {a for a in resolved.values() if a is not None} | set(prior)
    )
    theta = genre_theta(
        db, user.id, seed, rcfg, votes=votes.latest, artist_of=shared_artists, genres=genres
    )
    probe, joker = probe_and_joker(
        db, user.id, now, nb_exclude | {i["track"] for i in neighborhood},
        size * k, size * k, cfg, theta, seed, vote_tracks=votes.recent_tracks, genres=genres,
    )
    # `pool`: kota anahtarı. Öğedeki `source` görüntü etiketidir (mahallede "suggested");
    # algoritmaya girmez.
    pools = {
        s: [{**i, "pool": s} for i in p]
        for s, p in (("library", lib), ("neighborhood", neighborhood), ("probe", probe),
                     ("joker", joker))
    }
    mix = source_mix(len(voted_ids), size, {s: bool(p) for s, p in pools.items()}, cfg)
    # Kaynak yetmezse payı diğerlerine kayar; rerank kotanın k katı adaydan `size` kart seçer.
    quota = source_quota(mix, {s: len(p) for s, p in pools.items()}, size)
    cands = interleave(pools, quota, k)
    items = _rerank_items(
        db, user, cands, prior, voted_meta, size, cfg, quota, seed, resolved=resolved,
        genres=genres, shares=genre_shares(profile.body if profile is not None else None),
    )
    return items, ready_total


def _rerank_items(
    db: Session, user: User, items: list[dict], prior: Sequence[int], voted_meta: Sequence[tuple],
    size: int, cfg: ProfileSettings, quota: Mapping[str, int] | None = None, seed: int = 0,
    *, resolved: Mapping[int, int | None] | None = None, genres: GenrePairs | None = None,
    shares: Mapping[str, float] | None = None,
) -> list[dict]:
    """`resolved` (parça -> sanatçı | None: arandı, yok), `genres` ve `shares` verilirse ilgili
    sorgular atlanır; verilmezse eskisi gibi burada okunur."""
    tracks = [i["track"] for i in items]
    artist_of = {i["track"]: i["artist"] for i in items if i.get("artist") is not None}
    known = resolved or {}
    artist_of.update(
        {t: known[t] for t in tracks if t not in artist_of and known.get(t) is not None}
    )
    missing = [t for t in tracks if t not in artist_of and t not in known]
    if missing:
        artist_of.update(track_artists(db, user.id, missing))
    wanted = set(artist_of.values()) | set(prior)
    genre_of = genres.get(wanted) if genres is not None else load_genre_pairs(db, wanted)
    voted_keys = {song_key(t, a, cfg.queue_version_markers) for t, a in voted_meta}
    cands: list[Cand] = []
    seen: dict[int, dict] = {}
    for i in items:
        t = i["track"]
        key = song_key(i.get("title") or "", i.get("artists"), cfg.queue_version_markers)
        if key in voted_keys:
            continue
        # Sonda/joker kartı türünü kapsama hücresinden taşır; diğerleri sanatçı etiketinden.
        g, s = (
            (i["genre"], i.get("sub")) if i.get("genre")
            else genre_of.get(artist_of.get(t, -1), (None, None))
        )
        seen[t] = i
        cands.append(Cand(t, artist_of.get(t), g, s, i.get("pool") or "library", repr(key)))
    if shares is None:
        shares = profile_genre_shares(db, user.id)
    target = genre_targets(shares, list(GENRES), cfg.queue_genre_epsilon)
    prior_subs = [genre_of.get(a, (None, None))[1] for a in prior]
    ordered = rerank(
        cands, target, size, cfg, list(prior), prior_subs, quota=quota,
        seed=seed, jitter=cfg.queue_genre_jitter,
    )
    return [
        {k: v for k, v in seen[c.track].items() if k not in ("artist", "genre", "sub", "pool")}
        for c in ordered
    ]
