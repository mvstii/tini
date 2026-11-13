from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import get_db
from app.main import app
from app.models import Artist, Track, User, UserTrackLink, UserTrackMeta
from app.profile.queue import order_queue


def test_order_is_deterministic_and_seeded():
    cands = [(1, 10), (2, 10), (3, 20), (4, 30)]
    a = order_queue(cands, set(), seed=0)
    assert a == order_queue(list(reversed(cands)), set(), seed=0)
    assert sorted(a) == [1, 2, 3, 4]
    assert any(order_queue(cands, set(), seed=s) != a for s in range(1, 20))


def test_unvoted_artists_first_and_one_track_per_artist_per_round():
    cands = [(1, 10), (2, 10), (3, 20), (4, 30)]
    order = order_queue(cands, voted_artists={20}, seed=0)
    assert order[-1] == 3  # oy almış sanatçı sona
    first_round = order[:2]  # 10 ve 30'dan birer parça; 10'un ikinci parçası sonra
    assert {t for t in first_round} & {4} and len({1, 2} & set(first_round)) == 1


@pytest.fixture
def db(test_engine):
    engine = test_engine
    try:
        conn = engine.connect()
    except Exception:
        pytest.skip("PostgreSQL erişilemiyor")
    trans = conn.begin()
    s = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield s
    s.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def client(db, monkeypatch):
    cfg = Settings(_env_file=None, credential_key=Fernet.generate_key().decode())
    monkeypatch.setattr("app.auth.get_settings", lambda: cfg)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(c, email):
    r = c.post("/auth/register", json={"email": email, "password": "uzun-parola-1"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def lib_track(db, email, isrc, artist, title, expired=False):
    u = db.scalar(select(User).where(User.email == email))
    t = Track(isrc=isrc, artist_id=artist.id if artist else None)
    db.add(t)
    db.flush()
    db.add(UserTrackLink(user_id=u.id, service="spotify", external_id=isrc, track_id=t.id))
    now = datetime.now(UTC)
    exp = now - timedelta(hours=1) if expired else now + timedelta(hours=1)
    db.add(UserTrackMeta(user_id=u.id, track_id=t.id, title=title, artist_names=["X"],
                         expires_at=exp))
    db.flush()
    return t


def mk_artist(db, name):
    a = Artist(name=name, name_norm=name.lower())
    db.add(a)
    db.flush()
    return a


def test_queue_skips_voted_and_stale_and_lists_unresolved_last(client, db):
    h = register(client, "q1@example.com")
    a, b = mk_artist(db, "QA"), mk_artist(db, "QB")
    t1 = lib_track(db, "q1@example.com", "ZZQ000000001", a, "Bir")
    t2 = lib_track(db, "q1@example.com", "ZZQ000000002", b, "Iki")
    t3 = lib_track(db, "q1@example.com", "ZZQ000000003", None, "Sanatçısız")
    lib_track(db, "q1@example.com", "ZZQ000000004", b, "Eski", expired=True)
    client.post("/votes", json={"track": t1.id, "vote": 5}, headers=h)

    body = client.get("/votes/queue", headers=h).json()
    # Sanatçısı eşlenmemiş parça da oylanabilir, ama eşlenmişlerden sonra gelir.
    assert [i["track"] for i in body["items"]] == [t2.id, t3.id]
    assert body["items"][0]["title"] == "Iki" and body["remaining"] == 2 and body["stale"] == 1
    assert body["items"][0]["image"] is None
    assert body["algo_version"] == "queue-7"


def test_unresolved_order_is_seeded_pool_first():
    from app.profile.active import order_unresolved

    a = order_unresolved([1, 2, 3, 4], set(), seed=0)
    assert a == order_unresolved([4, 3, 2, 1], set(), seed=0) and sorted(a) == [1, 2, 3, 4]
    assert order_unresolved([1, 2, 3, 4], {3}, seed=0)[0] == 3


def test_queue_includes_cover_image(client, db):
    h = register(client, "q2@example.com")
    t = lib_track(db, "q2@example.com", "ZZQ000000010", mk_artist(db, "QC"), "Kapakli")
    meta = db.scalar(select(UserTrackMeta).where(UserTrackMeta.track_id == t.id))
    meta.image_url = "https://i.scdn.co/image/abc"
    db.flush()
    item = client.get("/votes/queue", headers=h).json()["items"][0]
    assert item["image"] == "https://i.scdn.co/image/abc"
    assert client.get("/votes/queue?seed=3", headers=h).json() == client.get(
        "/votes/queue?seed=3", headers=h
    ).json()


def test_history_returns_latest_vote_per_track(client, db):
    h = register(client, "q2@example.com")
    a = mk_artist(db, "QH")
    t1 = lib_track(db, "q2@example.com", "ZZQ000000011", a, "Bir")
    t2 = lib_track(db, "q2@example.com", "ZZQ000000012", a, "Iki")
    client.post("/votes", json={"track": t1.id, "vote": 2}, headers=h)
    client.post("/votes", json={"track": t2.id, "vote": 6}, headers=h)
    client.post("/votes", json={"track": t1.id, "vote": 5}, headers=h)

    body = client.get("/votes/history", headers=h).json()
    assert body["total"] == 2
    votes = {i["track"]: i["vote"] for i in body["items"]}
    assert votes == {t1.id: 5, t2.id: 6}
    assert {i["title"] for i in body["items"]} == {"Bir", "Iki"}
    assert all("image" in i for i in body["items"])
    assert body["items"][0]["track"] == t1.id  # en son oy en üstte
    assert client.get("/votes/history?limit=1&offset=1", headers=h).json()["items"][0][
        "track"
    ] == t2.id


def test_queue_and_history_are_private(client, db):
    h1 = register(client, "q3@example.com")
    a = mk_artist(db, "QP")
    t = lib_track(db, "q3@example.com", "ZZQ000000021", a, "Gizli")
    client.post("/votes", json={"track": t.id, "vote": 4}, headers=h1)
    h2 = register(client, "q4@example.com")
    assert client.get("/votes/queue", headers=h2).json()["items"] == []
    assert client.get("/votes/history", headers=h2).json()["total"] == 0


def test_queue_pool_bonus_awaiting_and_expired(client, db):
    from app.models import UnheardEvent

    h = register(client, "q5@example.com")
    u = db.scalar(select(User).where(User.email == "q5@example.com"))
    a, b, c = mk_artist(db, "QX"), mk_artist(db, "QY"), mk_artist(db, "QZ")
    pooled = lib_track(db, "q5@example.com", "ZZQ000000031", a, "Havuz")
    other = lib_track(db, "q5@example.com", "ZZQ000000032", b, "Diger")
    gone = lib_track(db, "q5@example.com", "ZZQ000000033", c, "Bitti")
    assert client.post("/votes/unheard", json={"track": pooled.id}, headers=h).status_code == 201
    for _ in range(3):
        client.post("/votes/unheard", json={"track": gone.id}, headers=h)

    body = client.get("/votes/queue", headers=h).json()
    ids = [i["track"] for i in body["items"]]
    assert body["algo_version"] == "queue-7"
    assert gone.id not in ids and ids[0] == pooled.id and set(ids) == {pooled.id, other.id}
    assert body["stale"] == 0  # havuzda süresi dolan parça kütüphane yenilemesiyle düzelmez
    states = [
        e.state for e in db.scalars(
            select(UnheardEvent).where(
                UnheardEvent.user_id == u.id, UnheardEvent.track_id == pooled.id
            ).order_by(UnheardEvent.id)
        )
    ]
    assert states == ["pooled", "awaiting"]
    client.get("/votes/queue", headers=h)  # tekrar sunum yeni awaiting yazmaz
    assert db.scalar(
        select(func.count()).select_from(UnheardEvent).where(
            UnheardEvent.user_id == u.id, UnheardEvent.track_id == pooled.id
        )
    ) == 2


MARKERS = ("remaster", "mono", "deluxe", "explicit", "feat", "ft", "featuring")


def test_song_key_strips_version_suffix_but_keeps_distinct_recordings():
    from app.profile.queue import song_key

    base = song_key("Yesterday", ["The Beatles"], MARKERS)
    assert song_key("Yesterday - Remastered 2009", ["The Beatles"], MARKERS) == base
    assert song_key("Yesterday (2011 Remaster)", ["The Beatles"], MARKERS) == base
    assert song_key("Yesterday [Deluxe Edition]", ["the beatles", "x"], MARKERS) == base
    assert song_key("Yesterday (Live)", ["The Beatles"], MARKERS) != base
    assert song_key("Yesterday (Remix)", ["The Beatles"], MARKERS) != base
    assert song_key("Yesterday", ["Baska"], MARKERS) != base
    assert song_key("Yesterday (feat. Paul)", ["The Beatles"], MARKERS) == base
    assert song_key("Yesterday - feat. Paul", ["The Beatles"], MARKERS) == base
    assert song_key("Yesterday – Remastered 2009", ["The Beatles"], MARKERS) == base  # uzun tire
    assert song_key("Soft Yesterday", ["The Beatles"], MARKERS) != base
    assert song_key("(Remaster)", ["A"], MARKERS)[0] == "remaster"  # boş kalırsa özgün başlık


def test_pick_versions_one_per_song_and_drops_voted_versions():
    from app.profile.queue import pick_versions

    entries = [
        (5, "Song", ["A"]), (3, "Song (Remastered)", ["A"]), (9, "Other", ["A"]),
        (7, "Voted", ["B"]),
    ]
    voted = [("Voted - 2011 Remaster", ["B"])]
    assert pick_versions(entries, voted, set(), MARKERS) == {3, 9}  # en düşük kimlik
    assert pick_versions(entries, voted, {5}, MARKERS) == {5, 9}  # havuz önceliklidir


def test_queue_hides_other_versions_of_same_song(client, db):
    h = register(client, "q6@example.com")
    a = mk_artist(db, "QV")
    lib_track(db, "q6@example.com", "ZZQ000000041", a, "Hit")
    lib_track(db, "q6@example.com", "ZZQ000000042", a, "Hit - Remastered 2011")
    done = lib_track(db, "q6@example.com", "ZZQ000000043", a, "Baska")
    lib_track(db, "q6@example.com", "ZZQ000000044", a, "Baska (Deluxe)")
    client.post("/votes", json={"track": done.id, "vote": 5}, headers=h)

    body = client.get("/votes/queue", headers=h).json()
    assert [i["title"] for i in body["items"]] == ["Hit"]
    assert body["remaining"] == 1 and body["stale"] == 0


class FakeAdapter:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def find_card(self, isrc, artist_name):
        import httpx

        from app.adapters.base import TrackCard

        self.calls += 1
        if self.fail:
            raise httpx.ConnectError("down")
        return TrackCard(f"Parca {isrc}", (artist_name,), "http://img/x.jpg")


def suggested(db, email, n=2):
    from app.models import GeneratedList, ListItem

    u = db.scalar(select(User).where(User.email == email))
    lst = GeneratedList(user_id=u.id, algo_version="l", candidate_algo_version="c",
                        profile_version=1, graph_version=1, params={})
    db.add(lst)
    db.flush()
    items = []
    for k in range(n):
        art = mk_artist(db, f"Sug{email}{k}")
        seed = mk_artist(db, f"Seed{email}{k}")
        t = Track(isrc=f"ZZS{email[1]}{k:08d}", artist_id=art.id)
        db.add(t)
        db.flush()
        li = ListItem(list_id=lst.id, position=k + 1, artist_id=art.id, track_id=t.id,
                      score=1.0, reasons=[{"seed_id": seed.id, "share": 1.0, "is_anchor": True}])
        db.add(li)
        items.append(li)
    db.flush()
    return items


def test_queue_mixes_suggestions_when_library_runs_low(client, db, monkeypatch):
    h = register(client, "s1@example.com")
    items = suggested(db, "s1@example.com")
    fake = FakeAdapter()
    monkeypatch.setattr("app.profile.suggest.ensure_fresh_list", lambda *a, **k: items)
    monkeypatch.setattr("app.profile.api.connected_adapter", lambda *a: fake)

    body = client.get("/votes/queue", headers=h).json()
    assert [i["track"] for i in body["items"]] == [i.track_id for i in items]
    first = body["items"][0]
    assert first["source"] == "suggested" and first["title"].startswith("Parca")
    assert first["image"] == "http://img/x.jpg" and len(first["reasons"]) == 1
    assert body["remaining"] == 0 and body["stale"] == 0
    assert fake.calls == 2

    client.get("/votes/queue", headers=h)  # ikinci istek önbellekten gelir
    assert fake.calls == 2
    assert client.post("/votes", json={"track": first["track"], "vote": 5}, headers=h
                       ).status_code == 201
    assert client.post("/votes/unheard", json={"track": items[1].track_id}, headers=h
                       ).status_code == 201


def test_queue_survives_service_failure(client, db, monkeypatch):
    h = register(client, "s2@example.com")
    items = suggested(db, "s2@example.com")
    monkeypatch.setattr("app.profile.suggest.ensure_fresh_list", lambda *a, **k: items)
    monkeypatch.setattr("app.profile.api.connected_adapter", lambda *a: FakeAdapter(fail=True))
    assert client.get("/votes/queue", headers=h).json()["items"] == []
    monkeypatch.setattr("app.profile.api.connected_adapter", lambda *a: None)
    assert client.get("/votes/queue", headers=h).status_code == 200


def test_ensure_fresh_list_rebuilds_profile_after_new_votes(db, monkeypatch):
    from app.config import GraphSettings, ProfileSettings, RecommendSettings
    from app.models import TasteProfile
    from app.profile import suggest

    u = User(email="s3@example.com", password_hash="x")
    db.add(u)
    db.flush()
    db.add(TasteProfile(user_id=u.id, version=1, algo_version="p", graph_version=1, body={},
                        created_at=datetime.now(UTC) - timedelta(hours=1)))
    db.flush()
    t = Track(isrc="ZZS300000001")
    db.add(t)
    db.flush()
    from app.models import VoteEvent

    cfg = ProfileSettings(queue_rebuild_after_votes=1)
    seen = {}
    monkeypatch.setattr(suggest, "rebuild_profile",
                        lambda *a, **k: seen.setdefault("p", TasteProfile(version=2)))
    monkeypatch.setattr(suggest, "generate_list", lambda *a, **k: seen.setdefault("l", None))
    monkeypatch.setattr(suggest, "_candidates", lambda *a, **k: [])
    suggest.ensure_fresh_list(db, u, datetime.now(UTC), set(), cfg, RecommendSettings(),
                              GraphSettings())
    assert "p" not in seen  # oy yok -> profil yenilenmez
    db.add(VoteEvent(user_id=u.id, track_id=t.id, vote=5))
    db.flush()
    suggest.ensure_fresh_list(db, u, datetime.now(UTC), set(), cfg, RecommendSettings(),
                              GraphSettings())
    assert "p" in seen and "l" in seen


def test_queue_sends_server_timing_and_logs_stages(client, db, caplog):
    import json
    import logging

    h = register(client, "timing@example.com")
    a = mk_artist(db, "Zzz Timing")
    lib_track(db, "timing@example.com", "ZZTIM0000001", a, "Bir")
    with caplog.at_level(logging.INFO, logger="tini.request"):
        r = client.get("/votes/queue", headers=h)
    assert r.status_code == 200
    names = [p.split(";")[0] for p in r.headers["Server-Timing"].split(", ")]
    assert names == ["candidates", "uncertainty", "rank", "suggest"]
    assert set(r.json()) == {"algo_version", "remaining", "stale", "items"}
    entry = json.loads(caplog.records[-1].getMessage())
    assert list(entry["stages"]) == ["candidates", "uncertainty", "rank", "suggest"]
    assert all(isinstance(v, float) for v in entry["stages"].values())
