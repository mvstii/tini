"""PR-2 hızlı yol: hazır öneriler salt okunur, doldurucu arka planda ve tek uçuşlu."""
# ruff: noqa: F811  (sabitler test_queue içe aktarımından gelir; repo kalıbı)
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from test_queue import FakeAdapter, client, db, lib_track, mk_artist, register, suggested  # noqa: F401

from app.config import GraphSettings, ProfileSettings, RecommendSettings, get_settings
from app.db import get_engine
from app.models import Track, User, UserTrackMeta, VoteEvent
from app.profile import refill, suggest
from app.profile.refill import lock_key, maybe_refill, refill_needed, try_lock, unlock
from app.profile.suggest import ready_suggestions, refill_buffer

TTL = timedelta(seconds=get_settings().spotify_cache_ttl_seconds)


def fast_cfg(**kw) -> ProfileSettings:
    return ProfileSettings(fast_queue_enabled=True, **kw)


def user_of(db, email) -> User:
    return db.scalar(select(User).where(User.email == email))


class FakeWorker:
    def __init__(self):
        self.jobs = []

    def submit(self, key, fn, *args):
        self.jobs.append(key)
        return True


def test_queue_is_served_from_ready_buffer_without_service_calls(client, db, monkeypatch):
    h = register(client, "f1@example.com")
    items = suggested(db, "f1@example.com", n=3)
    u = user_of(db, "f1@example.com")
    now = datetime.now(UTC)
    for it in items[:2]:  # yalnızca ikisinin meta kaydı var (hazır); üçüncüsü eksik
        db.add(UserTrackMeta(user_id=u.id, track_id=it.track_id, title="Hazir",
                             artist_names=["A"], expires_at=now + TTL))
    db.flush()
    from app.config import get_profile_settings
    from app.main import app

    app.dependency_overrides[get_profile_settings] = lambda: fast_cfg()
    boom = FakeAdapter(fail=True)
    monkeypatch.setattr("app.profile.api.connected_adapter", lambda *a: boom)
    monkeypatch.setattr(suggest, "ensure_fresh_list",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("istek yolunda")))
    jobs = FakeWorker()
    monkeypatch.setattr(refill, "get_worker", lambda: jobs)
    try:
        body = client.get("/votes/queue", headers=h)
    finally:
        app.dependency_overrides.pop(get_profile_settings, None)
    assert body.status_code == 200
    got = body.json()["items"]
    assert [i["title"] for i in got] == ["Hazir", "Hazir"]
    assert boom.calls == 0
    assert jobs.jobs == []  # profil yok -> doldurucu gerekmez


def test_refill_needed_triggers(db):
    u = User(email="f3@example.com", password_hash="x")
    db.add(u)
    db.flush()
    cfg = fast_cfg(buffer_low_watermark=2)
    now = datetime.now(UTC)
    assert refill_needed(db, u, now, cfg) is False  # profil yok, süresi dolacak meta yok
    t = Track(isrc="ZZF300000001")
    db.add(t)
    db.flush()
    # TTL'in %80'i geçmiş ama dolmamış meta -> tazeleme gerekir
    db.add(UserTrackMeta(user_id=u.id, track_id=t.id, title="Eski", artist_names=["A"],
                         expires_at=now + TTL * 0.1))
    db.flush()
    assert refill_needed(db, u, now, cfg) is True


def test_maybe_refill_is_off_by_default(db, monkeypatch):
    u = User(email="f4@example.com", password_hash="x")
    db.add(u)
    db.flush()
    jobs = FakeWorker()
    monkeypatch.setattr(refill, "get_worker", lambda: jobs)
    assert maybe_refill(db, u, datetime.now(UTC), ProfileSettings()) is False
    assert jobs.jobs == []


def test_refill_buffer_fills_to_target_and_stops_quietly_on_service_error(db, monkeypatch):
    register_user(db, "f5@example.com")
    items = suggested(db, "f5@example.com", n=3)
    u = user_of(db, "f5@example.com")
    monkeypatch.setattr(suggest, "ensure_fresh_list", lambda *a, **k: items)
    cfg = fast_cfg(buffer_target=2)
    now = datetime.now(UTC)
    fake = FakeAdapter()
    assert refill_buffer(db, u, lambda: fake, now, cfg, RecommendSettings(), GraphSettings())
    assert fake.calls == 2  # hedefe (2) ulaşınca durur
    assert len(ready_suggestions(db, u, now, 10, set())[0]) == 2
    assert suggest.ready_count(db, u.id, now, set()) == 2

    bad = FakeAdapter(fail=True)
    cfg = fast_cfg(buffer_target=3)
    assert refill_buffer(db, u, lambda: bad, now, cfg, RecommendSettings(),
                         GraphSettings()) is False
    assert suggest.ready_count(db, u.id, now, set()) == 2  # tampon bozulmadı


def test_meta_refresh_before_expiry_and_untouched_on_503(db, monkeypatch):
    register_user(db, "f6@example.com")
    art = mk_artist(db, "RefreshArt")
    t = lib_track(db, "f6@example.com", "ZZF600000001", art, "Eski Baslik")
    u = user_of(db, "f6@example.com")
    now = datetime.now(UTC)
    meta = db.get(UserTrackMeta, (u.id, t.id))
    meta.expires_at = now + TTL * 0.1  # TTL'in %90'ı geçti, henüz dolmadı
    meta.fetched_at = now - TTL * 0.9
    db.flush()
    monkeypatch.setattr(suggest, "ensure_fresh_list", lambda *a, **k: [])
    cfg = fast_cfg()

    class Down(FakeAdapter):
        def find_card(self, isrc, artist_name):
            self.calls += 1
            req = httpx.Request("GET", "http://x")
            raise httpx.HTTPStatusError("503", request=req, response=httpx.Response(503))

    before = meta.expires_at
    assert refill_buffer(db, u, lambda: Down(), now, cfg, RecommendSettings(),
                         GraphSettings()) is False
    db.refresh(meta)
    assert meta.title == "Eski Baslik" and meta.expires_at == before  # dokunulmadı

    assert refill_buffer(db, u, lambda: FakeAdapter(), now, cfg, RecommendSettings(),
                         GraphSettings()) is True
    db.refresh(meta)
    assert meta.title.startswith("Parca") and meta.expires_at >= now + TTL - timedelta(seconds=5)


def test_expired_metas_are_refreshed_and_trigger_refill(db, monkeypatch):
    register_user(db, "f7@example.com")
    art = mk_artist(db, "ExpiredArt")
    t = lib_track(db, "f7@example.com", "ZZF700000001", art, "Bayat Baslik")
    u = user_of(db, "f7@example.com")
    now = datetime.now(UTC)
    meta = db.get(UserTrackMeta, (u.id, t.id))
    meta.expires_at = now - timedelta(hours=3)  # süresi dolmuş
    db.flush()
    monkeypatch.setattr(suggest, "ensure_fresh_list", lambda *a, **k: [])
    cfg = fast_cfg()
    assert refill_needed(db, u, now, cfg) is True
    assert refill_buffer(db, u, lambda: FakeAdapter(), now, cfg, RecommendSettings(),
                         GraphSettings()) is True
    db.refresh(meta)
    assert meta.expires_at >= now + TTL - timedelta(seconds=5)


def test_advisory_lock_allows_only_one_holder():
    engine = get_engine()
    key = lock_key(uuid.uuid4())
    with engine.connect() as a, engine.connect() as b:
        a = a.execution_options(isolation_level="AUTOCOMMIT")
        b = b.execution_options(isolation_level="AUTOCOMMIT")
        assert try_lock(a, key) is True
        assert try_lock(b, key) is False  # ikinci tetik: iş yok
        unlock(a, key)
        assert try_lock(b, key) is True
        unlock(b, key)


def test_run_refill_skips_when_lock_is_held(monkeypatch):
    uid = uuid.uuid4()
    calls = []
    monkeypatch.setattr(refill, "refill_buffer", lambda *a, **k: calls.append(1) or True)
    engine = get_engine()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as holder:
        assert try_lock(holder, lock_key(uid))
        refill.run_refill(uid)
        unlock(holder, lock_key(uid))
    assert calls == []  # kilit başkasındayken iş yapılmadı


def test_worker_coalesces_concurrent_refill_triggers():
    from app.jobs.worker import Worker

    w = Worker(10)
    ran = []
    import threading

    gate = threading.Event()
    w.submit("block", gate.wait)  # yürütücüyü meşgul tut
    assert w.submit(("refill", 1), ran.append, 1) is True
    assert w.submit(("refill", 1), ran.append, 1) is False  # birleştirildi
    gate.set()
    assert w.wait_idle()
    assert ran == [1]


def register_user(db, email):
    db.add(User(email=email, password_hash="x"))
    db.flush()


def test_cast_vote_flag_off_does_not_trigger(client, db, monkeypatch):
    h = register(client, "f7@example.com")
    art = mk_artist(db, "VoteArt")
    t = lib_track(db, "f7@example.com", "ZZF700000001", art, "Sarki")
    jobs = FakeWorker()
    monkeypatch.setattr(refill, "get_worker", lambda: jobs)
    assert client.post("/votes", json={"track": t.id, "vote": 5}, headers=h).status_code == 201
    assert jobs.jobs == []
    assert db.scalar(select(VoteEvent.id).where(VoteEvent.track_id == t.id)) is not None


def test_cast_vote_triggers_refill_when_buffer_is_low(client, db, monkeypatch):
    from app.config import get_profile_settings
    from app.main import app
    from app.models import TasteProfile

    h = register(client, "f8@example.com")
    art = mk_artist(db, "VoteArt2")
    t = lib_track(db, "f8@example.com", "ZZF800000001", art, "Sarki")
    u = user_of(db, "f8@example.com")
    db.add(TasteProfile(user_id=u.id, version=1, algo_version="p", graph_version=1, body={}))
    db.flush()
    jobs = FakeWorker()
    monkeypatch.setattr(refill, "get_worker", lambda: jobs)
    app.dependency_overrides[get_profile_settings] = lambda: fast_cfg()
    try:
        assert client.post("/votes", json={"track": t.id, "vote": 5}, headers=h
                           ).status_code == 201
    finally:
        app.dependency_overrides.pop(get_profile_settings, None)
    assert jobs.jobs == [("refill", u.id)]
