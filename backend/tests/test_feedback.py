import json
import logging

from sqlalchemy import func, select
from test_lists_api import client, db, register  # noqa: F401

from app.models import AppFeedback, User

BODY = {"kind": "bug", "screen": "rating", "app_version": "1.0.0", "message": "Kart takıldı"}


def test_feedback_is_saved_for_user(client, db):  # noqa: F811
    h = register(client, "fb@example.com")
    r = client.post("/feedback", json=BODY, headers=h)
    assert r.status_code == 201
    row = db.get(AppFeedback, r.json()["id"])
    assert row.kind == "bug" and row.screen == "rating" and row.message == "Kart takıldı"
    assert row.user_id == db.scalar(select(User.id).where(User.email == "fb@example.com"))


def test_feedback_requires_auth_and_valid_body(client, db):  # noqa: F811
    assert client.post("/feedback", json=BODY).status_code == 401
    h = register(client, "fb2@example.com")
    assert client.post("/feedback", json={**BODY, "kind": "x"}, headers=h).status_code == 422
    assert client.post("/feedback", json={**BODY, "message": "a"}, headers=h).status_code == 422
    too_long = {**BODY, "message": "a" * 2001}
    assert client.post("/feedback", json=too_long, headers=h).status_code == 422
    assert db.scalar(select(func.count()).select_from(AppFeedback)) == 0


def test_feedback_deleted_with_account(client, db):  # noqa: F811
    h = register(client, "fb3@example.com")
    client.post("/feedback", json=BODY, headers=h)
    db.delete(db.scalar(select(User).where(User.email == "fb3@example.com")))
    db.flush()
    assert db.scalar(select(func.count()).select_from(AppFeedback)) == 0


def test_request_log_has_id_user_and_no_body(client, caplog):  # noqa: F811
    h = register(client, "fb4@example.com")
    with caplog.at_level(logging.INFO, logger="tini.request"):
        r = client.post("/feedback", json=BODY, headers=h)
    assert r.headers["X-Request-Id"]
    entry = json.loads(caplog.records[-1].getMessage())
    assert entry["request_id"] == r.headers["X-Request-Id"]
    assert entry["path"] == "/feedback" and entry["status"] == 201 and entry["user"]
    assert "Kart takıldı" not in caplog.text and "Bearer" not in caplog.text
