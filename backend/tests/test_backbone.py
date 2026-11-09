import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from test_votes_api import client, db, setup_user  # noqa: F401

from app.catalog.backbone import (
    band_for_percentile,
    band_windows,
    build_sub_genre,
    pick_artists,
    report,
    run_backbone,
    split_quota,
    sub_genres_for,
)
from app.config import GraphSettings, get_graph_settings
from app.main import app
from app.models import Artist, GenreSeed, Track, TrackPopularity, UserTrackMeta
from app.recommend.service import _pick_tracks, representative_pick
from app.sources.http import SourceError
from app.sources.listenbrainz import LbRecording

CFG = GraphSettings(
    _env_file=None, backbone_artists_per_sub_genre_cap=3, backbone_top_k=2,
    backbone_enabled=True,
)


def mb(n: int) -> str:
    return str(uuid.UUID(int=n))


def test_band_windows_and_percentile_normalization():
    assert band_windows(CFG) == {"top": (0, 33), "mid": (33, 66), "tail": (66, 100)}
    assert band_for_percentile(0, CFG) == "top"  # 0 = en çok dinlenen
    assert band_for_percentile(32.9, CFG) == "top"
    assert band_for_percentile(33, CFG) == "mid"
    assert band_for_percentile(66, CFG) == "tail"
    assert band_for_percentile(100, CFG) == "tail"


def test_split_quota_distributes_remainder_in_order():
    assert split_quota(60) == {"top": 20, "mid": 20, "tail": 20}
    assert split_quota(61) == {"top": 21, "mid": 20, "tail": 20}
    assert split_quota(2) == {"top": 1, "mid": 1, "tail": 0}
    assert sum(split_quota(7).values()) == 7


def test_pick_artists_dedups_skips_and_caps():
    pool = {
        "r1": LbRecording("r1", "t", "A", "a1", ()),
        "r2": LbRecording("r2", "t", "A", "a1", ()),
        "r3": LbRecording("r3", "t", "B", "b1", ()),
        "r4": LbRecording("r4", "t", "C", None, ()),
        "r5": LbRecording("r5", "t", "D", "d1", ()),
    }
    assert pick_artists(pool, {"b1"}, 5) == [("a1", "A"), ("d1", "D")]
    assert pick_artists(pool, set(), 1) == [("a1", "A")]


def test_sub_genres_for_selector():
    assert sub_genres_for("arabesk") == ["arabesk"]
    assert "arabesk" in sub_genres_for("turkish") and "trap" not in sub_genres_for("turkish")
    assert len(sub_genres_for(None)) > 60
    with pytest.raises(ValueError):
        sub_genres_for("yok")


def test_representative_pick_is_deterministic_and_top_k_bound():
    cands = [(1, 5), (2, 500), (3, 400), (4, 1)]
    a = representative_pick(cands, "u:1:7", 2)
    assert a == representative_pick(list(reversed(cands)), "u:1:7", 2)
    assert a in (2, 3)  # yalnızca en çok dinlenen 2
    assert {representative_pick(cands, f"s{i}", 2) for i in range(40)} == {2, 3}
    assert representative_pick([], "x", 3) is None


class FakeLb:
    """3 bant × her bantta bir sanatçı; sanatçı başına 2 kayıt (biri ISRC'siz)."""

    def __init__(self):
        self.radio_calls = 0
        self.top_calls: list[str] = []
        self.fail_artist: str | None = None

    def radio_tags(self, tag, count, pop_begin=0, pop_end=100):
        self.radio_calls += 1
        base = {0: 10, 33: 20, 66: 30}[pop_begin]
        return [mb(base + i) for i in range(3)]  # kayıt mbid'leri; sanatçı = kayıt − 5

    def top_recordings(self, artist_mbid, k):
        self.top_calls.append(str(artist_mbid))
        if str(artist_mbid) == self.fail_artist:
            raise SourceError("HTTP 500")
        n = int(uuid.UUID(str(artist_mbid)))
        return [(mb(1000 + n), 90), (mb(2000 + n), 10)][:k]

    def recordings(self, mbids):
        out = {}
        for m in mbids:
            n = int(uuid.UUID(m))
            if 10 <= n < 40:  # havuz kaydı → sanatçı (n + 100)
                out[m] = LbRecording(m, "t", f"Artist {n}", mb(n + 100), ())
            elif 1000 <= n < 2000:  # en çok dinlenen kayıt: ISRC'li
                out[m] = LbRecording(m, "t", "x", mb(n - 1000), (f"TRBB{n:08d}",))
            else:  # ISRC'siz (MB yedeği devreye girer)
                out[m] = LbRecording(m, "t", "x", mb(n - 2000), ())
        return out


class FakeMb:
    def __init__(self, with_isrc=True):
        self.with_isrc = with_isrc
        self.calls = 0

    def recording_isrcs(self, mbid):
        self.calls += 1
        return [f"TRMB{int(uuid.UUID(str(mbid))):08d}"] if self.with_isrc else []


def test_build_sub_genre_writes_seeds_and_is_resumable(db):  # noqa: F811
    lb, mbc = FakeLb(), FakeMb()
    s = build_sub_genre(db, lb, mbc, CFG, "arabesk")
    assert s.artists == 3 and s.errors == 0
    assert s.recordings == 6 and s.with_isrc == 6  # 3 ISRC'li + 3 MB yedeği
    assert mbc.calls == 3
    rows = db.execute(select(GenreSeed.band, GenreSeed.main_genre)).all()
    assert sorted(b for b, _ in rows) == ["mid", "mid", "tail", "tail", "top", "top"]
    assert {m for _, m in rows} == {"turkish"}
    assert db.scalar(select(func.count()).select_from(TrackPopularity)) == 6
    # ikinci koşu: kaydı olan sanatçı yeniden sorulmaz
    lb.top_calls.clear()
    s2 = build_sub_genre(db, lb, mbc, CFG, "arabesk")
    assert s2.artists == 0 and lb.top_calls == []
    assert db.scalar(select(func.count()).select_from(GenreSeed)) == 6


def test_source_error_skips_artist_and_retries_next_run(db):  # noqa: F811
    lb = FakeLb()
    lb.fail_artist = mb(110)  # top bandındaki sanatçı
    s = build_sub_genre(db, lb, FakeMb(), CFG, "arabesk")
    assert s.errors == 1 and s.artists == 2
    lb.fail_artist = None
    s2 = build_sub_genre(db, lb, FakeMb(), CFG, "arabesk")
    assert s2.artists == 1 and s2.errors == 0
    assert db.scalar(select(func.count(func.distinct(GenreSeed.artist_id)))) == 3


def test_artist_without_any_isrc_is_not_written(db):  # noqa: F811
    lb = FakeLb()
    cfg = CFG.model_copy(update={"backbone_top_k": 1})
    # k=1 → yalnızca ISRC'li kayıt; MB yedeği yok → yine de yazılır; ISRC'siz sanatçıyı simüle et:
    lb.recordings = lambda ms: {m: LbRecording(m, "t", "x", None, ()) for m in ms} | {
        m: v for m, v in FakeLb.recordings(lb, ms).items() if int(uuid.UUID(m)) < 1000
    }
    s = build_sub_genre(db, lb, FakeMb(with_isrc=False), cfg, "arabesk")
    assert s.artists == 0 and s.seeds == 0
    assert db.scalar(select(func.count()).select_from(GenreSeed)) == 0


def test_run_backbone_limit_is_total_and_report(db):  # noqa: F811
    s = run_backbone(db, FakeLb(), FakeMb(), CFG, selector="turkish", limit=4)
    assert s.artists == 4
    rep = report(db)
    assert rep["sub_genres_with_data"] == 2  # arabesk 3 + sonraki alt tür 1
    assert rep["sub_genres_total"] > 60
    assert set(rep["below_15_artists"]) == set(rep["per_sub"])
    assert rep["db_size_bytes"] > 0
    assert s.as_dict()["isrc_ratio"] == 1.0


def _artist_with_tracks(db, listens):  # noqa: F811
    a = Artist(mbid=uuid.uuid4(), name="X", name_norm="x")
    db.add(a)
    db.flush()
    ids = []
    for n in listens:
        t = Track(isrc=f"TR{uuid.uuid4().hex[:10].upper()}", artist_id=a.id)
        db.add(t)
        db.flush()
        if n is not None:
            db.add(TrackPopularity(track_id=t.id, band="top", listens=n))
        ids.append(t.id)
    db.flush()
    return a, ids


def test_pick_tracks_old_behavior_without_flag_or_data(db):  # noqa: F811
    a, ids = _artist_with_tracks(db, [5, 500, 400])
    uid = uuid.uuid4()
    assert _pick_tracks(db, uid, [a.id]) == {a.id: ids[0]}  # bayraksız: en düşük kimlik
    off = CFG.model_copy(update={"backbone_enabled": False})
    assert _pick_tracks(db, uid, [a.id], off, "s") == {a.id: ids[0]}
    b, bids = _artist_with_tracks(db, [None, None])  # dinlenme verisi yok → eski davranış
    assert _pick_tracks(db, uid, [b.id], CFG, "s") == {b.id: bids[0]}


def test_pick_tracks_representative_is_deterministic_and_skips_voted(db):  # noqa: F811
    a, ids = _artist_with_tracks(db, [5, 500, 400])
    uid = uuid.uuid4()
    first = _pick_tracks(db, uid, [a.id], CFG, "s1")[a.id]
    assert first in (ids[1], ids[2])  # top_k=2 → en çok dinlenen iki parça
    assert all(_pick_tracks(db, uid, [a.id], CFG, "s1")[a.id] == first for _ in range(5))
    assert {_pick_tracks(db, uid, [a.id], CFG, f"s{i}")[a.id] for i in range(30)} == {
        ids[1], ids[2],
    }


def _presented_setup(db, client_):  # noqa: F811
    h, u, _ = setup_user(db, client_)
    t = Track(isrc="TRPRES000001")
    db.add(t)
    db.flush()
    return h, u, t


def test_vote_on_presented_track_d3(client, db):  # noqa: F811
    h, u, t = _presented_setup(db, client)
    exp = datetime.now(UTC) + timedelta(hours=1)
    # bayrak kapalı (varsayılan): sunulmuş olsa da eski davranış
    db.add(UserTrackMeta(user_id=u.id, track_id=t.id, title="T", artist_names=["A"],
                         duration_ms=1, image_url=None, expires_at=exp))
    db.flush()
    assert client.post("/votes", json={"track": t.id, "vote": 4}, headers=h).status_code == 404
    app.dependency_overrides[get_graph_settings] = lambda: CFG
    try:
        assert client.post("/votes", json={"track": t.id, "vote": 4}, headers=h).status_code == 201
        # sunulmamış parça bayrak açıkken de 404
        other = Track(isrc="TRPRES000002")
        db.add(other)
        db.flush()
        r = client.post("/votes", json={"track": other.id, "vote": 4}, headers=h)
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_graph_settings, None)
