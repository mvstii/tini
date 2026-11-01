from sqlalchemy import func, select
from test_lists_api import client, db, register  # noqa: F401

from app.jobs.delete_user import delete_user
from app.models import AppFeedback, User, UserSession


def test_delete_user_removes_personal_data(client, db):  # noqa: F811
    h = register(client, "del1@example.com")
    client.post(
        "/feedback",
        json={"kind": "bug", "screen": "home", "app_version": "0.1.0", "message": "deneme"},
        headers=h,
    )
    uid = db.scalar(select(User.id).where(User.email == "del1@example.com"))
    sessions = select(func.count()).select_from(UserSession).where(UserSession.user_id == uid)
    assert db.scalar(sessions) > 0
    assert delete_user(db, "del1@example.com") is True
    assert db.scalar(select(User).where(User.email == "del1@example.com")) is None
    for model in (AppFeedback, UserSession):
        assert db.scalar(select(func.count()).select_from(model).where(model.user_id == uid)) == 0


def test_delete_user_unknown_email(db):  # noqa: F811
    assert delete_user(db, "yok@example.com") is False
