"""PR-6: omurga (sonda/joker) kartları, doldurucu adımı ve queue-8 yolu."""
# ruff: noqa: F811  (sabitler test_queue içe aktarımından gelir; repo kalıbı)
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from test_queue import client, db, lib_track, mk_artist, register  # noqa: F401

from app.adapters.base import TrackCard
from app.config import (
    GraphSettings,
    ProfileSettings,
    RecommendSettings,
    get_profile_settings,
    get_settings,
)
from app.main import app
from app.models import GenreSeed, Track, User, UserTrackMeta
from app.profile.probe import probe_and_joker, resolve_seed_cards
from app.profile.sampled_queue import _rerank_items
from app.profile.sampler import SOURCES

TTL = timedelta(seconds=get_settings().spotify_cache_ttl_seconds)
RCFG, GCFG = RecommendSettings(_env_file=None), GraphSettings(_env_file=None)


class IsrcAdapter:
    """find_card yalnızca ISRC'den çözer; bilinmeyen ISRC için None (isrc_only davranışı)."""

    def __init__(self, unknown=(), fail=False):
        self.unknown, self.fail, self.calls, self.only = set(unknown), fail, [], []

    def find_card(self, isrc, artist_name, isrc_only=False):
        self.calls.append(isrc)
        self.only.append(isrc_only)
        if self.fail:
            raise httpx.ConnectError("down")
        if isrc in self.unknown:
            return None
        return TrackCard(f"Omurga {isrc}", ("Sanatci",), "http://img/s.jpg")


def user_of(db, email):
    return db.scalar(select(User).where(User.email == email))


def mk_seeds(db, n, sub="grunge", main="rock", band="top", prefix="ZZP"):
    out = []
    for k in range(n):
        art = mk_artist(db, f"{prefix}{sub}{band}{k}")
        t = Track(isrc=f"{prefix}{sub[:3].upper()}{band[0].upper()}{k:05d}", artist_id=art.id)
        db.add(t)
        db.flush()
        db.add(GenreSeed(sub_genre=sub, track_id=t.id, main_genre=main, artist_id=art.id,
                         band=band, source="listenbrainz"))
        out.append(t)
    db.flush()
    return out


def test_resolve_seed_cards_uses_isrc_only_and_skips_unresolvable(db):
    register_email = "p1@example.com"
    db.add(User(email=register_email, password_hash="x"))
    db.flush()
    u = user_of(db, register_email)
    seeds = mk_seeds(db, 3)
    ad = IsrcAdapter(unknown={seeds[0].isrc})
    now = datetime.now(UTC)
    cfg = ProfileSettings(_env_file=None, queue_sampler_enabled=True)
    assert resolve_seed_cards(db, u.id, lambda: ad, now, cfg, RCFG, 10, 1) is True
    assert all(ad.only)  # her çağrı isrc_only=True
    metas = db.scalars(select(UserTrackMeta).where(UserTrackMeta.user_id == u.id))
    got = {m.track_id for m in metas}
    assert got == {seeds[1].id, seeds[2].id}  # çözülemeyen parça sunulmaz
    bad = IsrcAdapter(fail=True)
    assert resolve_seed_cards(db, u.id, lambda: bad, now, cfg, RCFG, 10, 1) is False


def test_resolve_seed_cards_stops_when_ready_buffer_is_full(db):
    db.add(User(email="p2@example.com", password_hash="x"))
    db.flush()
    u = user_of(db, "p2@example.com")
    seeds = mk_seeds(db, 3)
    now = datetime.now(UTC)
    for t in seeds[:2]:
        db.add(UserTrackMeta(user_id=u.id, track_id=t.id, title="H", artist_names=["A"],
                             expires_at=now + TTL))
    db.flush()
    ad = IsrcAdapter()
    cfg = ProfileSettings(_env_file=None, buffer_target=2)
    assert resolve_seed_cards(db, u.id, lambda: ad, now, cfg, RCFG, 10, 1) is True
    assert ad.calls == []  # hedef doldu: servis çağrısı yok


def test_probe_and_joker_are_disjoint_coverage_cards_and_skip_voted(db):
    db.add(User(email="p3@example.com", password_hash="x"))
    db.flush()
    u = user_of(db, "p3@example.com")
    seeds = mk_seeds(db, 4) + mk_seeds(db, 3, sub="jazz", main="jazz_blues", band="tail")
    now = datetime.now(UTC)
    for t in seeds:
        db.add(UserTrackMeta(user_id=u.id, track_id=t.id, title=f"T{t.id}", artist_names=["A"],
                             expires_at=now + TTL))
    db.flush()
    cfg = ProfileSettings(_env_file=None)
    exclude = {seeds[0].id}
    probe, joker = probe_and_joker(db, u.id, now, exclude, 3, 3, cfg, {}, 5)
    ids = [i["track"] for i in probe + joker]
    assert len(ids) == len(set(ids)) and seeds[0].id not in ids
    assert all(i["source"] == "probe" and i["reasons"][0]["kind"] == "coverage" for i in probe)
    assert all(i["reasons"][0]["band"] in ("top", "mid") for i in probe)  # sonda tanınır bant
    assert probe_and_joker(db, u.id, now, exclude, 3, 3, cfg, {}, 5) == (probe, joker)


def test_queue8_mixes_sources_keeps_batch_size_and_is_seeded(client, db):
    h = register(client, "p4@example.com")
    u = user_of(db, "p4@example.com")
    arts = [mk_artist(db, f"P4Art{k}") for k in range(8)]
    for k, a in enumerate(arts):
        lib_track(db, "p4@example.com", f"ZZP4L{k:07d}", a, f"Kutuphane {k}")
    now = datetime.now(UTC)
    for t in mk_seeds(db, 6, prefix="ZZQ") + mk_seeds(db, 4, sub="jazz", main="jazz_blues",
                                                       band="mid", prefix="ZZQ"):
        db.add(UserTrackMeta(user_id=u.id, track_id=t.id, title=f"Omurga {t.id}",
                             artist_names=["S"], expires_at=now + TTL))
    db.flush()
    app.dependency_overrides[get_profile_settings] = lambda: ProfileSettings(
        _env_file=None, queue_sampler_enabled=True, fast_queue_enabled=True
    )
    try:
        a = client.get("/votes/queue?limit=10&seed=3", headers=h).json()
        b = client.get("/votes/queue?limit=10&seed=3", headers=h).json()
    finally:
        app.dependency_overrides.pop(get_profile_settings, None)
    assert a["algo_version"] == "queue-8"
    assert a == b  # aynı tohum, aynı sıra
    items = a["items"]
    assert len(items) == 10 and len({i["track"] for i in items}) == 10
    sources = {i.get("source") for i in items}
    assert {"probe", None} <= sources  # omurga ve kütüphane birlikte
    assert sources <= {*SOURCES, None}
    assert all(i["title"] for i in items)


def test_rerank_quota_uses_pool_key_not_display_label(db):
    """Mahalle öğesinin görüntü etiketi "suggested"dır; kota havuz anahtarıyla ("neighborhood")
    sayılır. Etiket kotaya girerse mahalle adayları hep "dolu" görünür ve payını yitirir."""
    db.add(User(email="p6@example.com", password_hash="x"))
    db.flush()
    u = user_of(db, "p6@example.com")

    def item(k, pool, label=None):
        art = mk_artist(db, f"P6{pool}{k}")
        t = Track(isrc=f"ZZP6{pool[:1].upper()}{k:07d}", artist_id=art.id)
        db.add(t)
        db.flush()
        out = {"track": t.id, "title": f"{pool} {k}", "artists": [art.name], "artist": art.id,
               "pool": pool}
        return {**out, "source": label} if label else out

    lib = [item(k, "library") for k in range(4)]
    nb = [item(k, "neighborhood", "suggested") for k in range(4)]
    cfg = ProfileSettings(_env_file=None)
    out = _rerank_items(db, u, lib + nb, [], [], 4, cfg, {"library": 1, "neighborhood": 3})
    assert len(out) == 4
    assert sum(i.get("source") == "suggested" for i in out) == 3  # kota: 1 kütüphane + 3 mahalle
    assert all("pool" not in i and "artist" not in i for i in out)  # iç alanlar sızmaz


def test_rerank_uses_coverage_cell_genre_of_probe_cards(db):
    """Sonda/joker kartı türünü kapsama hücresinden taşır; sanatçının etiketi olmasa da
    rerank bunu görmeli, yoksa art arda aynı alt tür kısıtı işlemez."""
    db.add(User(email="p7@example.com", password_hash="x"))
    db.flush()
    u = user_of(db, "p7@example.com")
    seeds = mk_seeds(db, 2, prefix="ZZR") + mk_seeds(db, 2, sub="jazz", main="jazz_blues",
                                                      band="mid", prefix="ZZR")
    cells = [("rock", "grunge")] * 2 + [("jazz_blues", "jazz")] * 2
    items = [
        {"track": t.id, "title": f"Omurga {t.id}", "artists": ["S"], "artist": t.artist_id,
         "genre": g, "sub": s, "source": "probe", "pool": "probe"}
        for t, (g, s) in zip(seeds, cells, strict=True)
    ]
    sub_of = {i["track"]: i["sub"] for i in items}
    cfg = ProfileSettings(_env_file=None)
    out = _rerank_items(db, u, items, [], [], 4, cfg, {"probe": 4})
    subs = [sub_of[i["track"]] for i in out]
    assert len(out) == 4
    assert all(a != b for a, b in zip(subs, subs[1:], strict=False))  # alt türler dönüşümlü


def test_queue_flag_off_is_unchanged_queue7(client, db):
    h = register(client, "p5@example.com")
    lib_track(db, "p5@example.com", "ZZP5L0000001", mk_artist(db, "P5A"), "Bir")
    body = client.get("/votes/queue", headers=h).json()
    assert body["algo_version"] == "queue-7"
    assert [i["title"] for i in body["items"]] == ["Bir"]
