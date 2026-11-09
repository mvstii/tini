"""`queue-8` birleşik havuz (PR-6): dört kaynaktan karışım, rerank ve kaynak etiketi.

Yalnızca `queue_sampler_enabled` açıkken `queue()` tarafından çağrılır; kapalıyken `queue-7`
yolu değişmeden çalışır. Burada servis çağrısı yalnızca mahalle önerisi (`suggest_items`,
hızlı yol kapalıyken) içindedir; sonda/joker kartları doldurucu tarafından önceden çözülür.
"""
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.tags import load_genre_pairs
from app.config import GraphSettings, ProfileSettings, RecommendSettings
from app.models import ListenLater, Track, User, VoteEvent
from app.profile.probe import genre_theta, probe_and_joker, profile_genre_shares
from app.profile.queue import song_key
from app.profile.sampler import SOURCES, Cand, genre_targets, rerank, source_mix
from app.profile.suggest import connected_adapter, ready_suggestions, suggest_items
from app.recommend.genres import GENRES


def sampled_items(
    db: Session, user: User, http, now: datetime, *,
    size: int, seed: int, fresh: Mapping[int, tuple], library: Sequence[int],
    expired: set[int], recent_set: set[int], prior: Sequence[int],
    voted_meta: Sequence[tuple], cfg: ProfileSettings, rcfg: RecommendSettings,
    gcfg: GraphSettings, adapter: Callable | None = None,
) -> tuple[list[dict], int | None]:
    """(sıralı kart öğeleri, hazır öneri toplamı | None). Her öğede `source` ve (varsa) gerekçe.

    `library`: kütüphane parçaları öncelik sırasında; `fresh[t] = (id, artist, title, artists,
    expires, image)`. Kaynak boşsa payı diğerlerine kayar; parti küçülmez (varsa aday)."""
    voted_ids = set(db.scalars(select(VoteEvent.track_id).where(VoteEvent.user_id == user.id)))
    later = set(db.scalars(select(ListenLater.track_id).where(ListenLater.user_id == user.id)))
    exclude = voted_ids | later | recent_set | expired
    nb_exclude = set(fresh) | exclude
    ready_total = None
    if cfg.fast_queue_enabled:
        neighborhood, ready_total = ready_suggestions(db, user, now, size, nb_exclude)
    else:
        neighborhood = suggest_items(
            db, user, adapter or (lambda: connected_adapter(db, user, http)), now, size,
            nb_exclude, cfg, rcfg, gcfg,
        )
    theta = genre_theta(db, user.id, seed, rcfg)
    probe, joker = probe_and_joker(
        db, user.id, now, nb_exclude | {i["track"] for i in neighborhood},
        size, size, cfg, theta, seed,
    )
    lib = [
        {"track": t, "title": fresh[t][2], "artists": fresh[t][3], "image": fresh[t][5],
         "artist": fresh[t][1]}
        for t in library[:size]
    ]
    pools = {"library": lib, "neighborhood": neighborhood, "probe": probe, "joker": joker}
    mix = source_mix(len(voted_ids), size, {s: bool(p) for s, p in pools.items()}, cfg)
    chosen = [i for s in SOURCES for i in pools[s][: mix[s]]]
    if len(chosen) < size:  # kaynak yetmediyse kalan yuvalar sırayla diğer kaynaklardan dolar
        have = {i["track"] for i in chosen}
        spare = (i for s in SOURCES for i in pools[s][mix[s]:] if i["track"] not in have)
        chosen += [i for _, i in zip(range(size - len(chosen)), spare, strict=False)]
    return _rerank_items(db, user, chosen, prior, voted_meta, size, cfg), ready_total


def _rerank_items(
    db: Session, user: User, items: list[dict], prior: Sequence[int], voted_meta: Sequence[tuple],
    size: int, cfg: ProfileSettings,
) -> list[dict]:
    tracks = [i["track"] for i in items]
    artist_of = {i["track"]: i["artist"] for i in items if i.get("artist") is not None}
    missing = [t for t in tracks if t not in artist_of]
    if missing:
        artist_of.update({
            t: a for t, a in db.execute(
                select(Track.id, Track.artist_id).where(Track.id.in_(missing))
            ).all() if a is not None
        })
    genre_of = load_genre_pairs(db, set(artist_of.values()) | set(prior))
    voted_keys = {song_key(t, a, cfg.queue_version_markers) for t, a in voted_meta}
    cands: list[Cand] = []
    seen: dict[int, dict] = {}
    for i in items:
        t = i["track"]
        key = song_key(i.get("title") or "", i.get("artists"), cfg.queue_version_markers)
        if key in voted_keys:
            continue
        g, s = genre_of.get(artist_of.get(t, -1), (None, None))
        seen[t] = i
        cands.append(Cand(t, artist_of.get(t), g, s, i.get("source") or "library", repr(key)))
    target = genre_targets(profile_genre_shares(db, user.id), list(GENRES), cfg.queue_genre_epsilon)
    prior_subs = [genre_of.get(a, (None, None))[1] for a in prior]
    ordered = rerank(cands, target, size, cfg, list(prior), prior_subs)
    return [
        {k: v for k, v in seen[c.track].items() if k not in ("artist", "genre", "sub")}
        for c in ordered
    ]
