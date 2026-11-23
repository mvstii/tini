from sqlalchemy.exc import IntegrityError
from test_lists_api import client, db, register  # noqa: F401

from app.models import User


def test_me_returns_401_when_user_vanished(client, db, monkeypatch):  # noqa: F811
    h = register(client, "ghost@example.com")
    real_get = db.get

    def get(model, ident, *a, **kw):
        return None if model is User else real_get(model, ident, *a, **kw)

    monkeypatch.setattr(db, "get", get)
    r = client.get("/me", headers=h)
    assert r.status_code == 401


def test_register_race_maps_to_409(client, db, monkeypatch):  # noqa: F811
    real_flush = db.flush

    def flush(*a, **kw):
        if not any(isinstance(o, User) for o in db.new):
            return real_flush(*a, **kw)  # ön kontrolün autoflush'u
        monkeypatch.setattr(db, "flush", real_flush)
        raise IntegrityError("insert", {}, Exception("duplicate"))

    monkeypatch.setattr(db, "flush", flush)
    r = client.post(
        "/auth/register", json={"email": "race@example.com", "password": "uzun-parola-1"}
    )
    assert r.status_code == 409
