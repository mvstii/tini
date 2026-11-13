import hashlib

from sqlalchemy import func, select
from test_lists_api import client, db, register  # noqa: F401

from app.config import PhotoSettings
from app.jobs.delete_user import delete_user
from app.models import User, UserPhoto

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200


def _put(c, h, data=JPEG):
    return c.put("/me/photo", content=data, headers={**h, "Content-Type": "image/jpeg"})


def _count(session, uid):
    stmt = select(func.count()).select_from(UserPhoto).where(UserPhoto.user_id == uid)
    return session.scalar(stmt)


def test_put_then_get_returns_the_same_bytes(client, db):  # noqa: F811
    h = register(client, "ph1@example.com")
    r = _put(client, h)
    assert r.status_code == 200
    etag = hashlib.sha1(JPEG).hexdigest()
    assert r.json() == {"etag": etag}
    g = client.get("/me/photo", headers=h)
    assert g.status_code == 200
    assert g.content == JPEG
    assert g.headers["content-type"] == "image/jpeg"
    assert g.headers["etag"] == f'"{etag}"'
    assert "private" in g.headers["cache-control"]


def test_put_replaces_the_previous_photo(client, db):  # noqa: F811
    h = register(client, "ph2@example.com")
    _put(client, h)
    newer = JPEG + b"\x01"
    assert _put(client, h, newer).status_code == 200
    assert client.get("/me/photo", headers=h).content == newer
    assert db.scalar(select(func.count()).select_from(UserPhoto)) == 1


def test_get_without_photo_is_404_and_if_none_match_gives_304(client, db):  # noqa: F811
    h = register(client, "ph3@example.com")
    assert client.get("/me/photo", headers=h).status_code == 404
    etag = _put(client, h).json()["etag"]
    same = client.get("/me/photo", headers={**h, "If-None-Match": f'"{etag}"'})
    assert same.status_code == 304 and same.content == b""
    other = client.get("/me/photo", headers={**h, "If-None-Match": '"abc"'})
    assert other.status_code == 200


def test_delete_is_idempotent(client, db):  # noqa: F811
    h = register(client, "ph4@example.com")
    assert client.delete("/me/photo", headers=h).status_code == 204
    _put(client, h)
    assert client.delete("/me/photo", headers=h).status_code == 204
    assert client.get("/me/photo", headers=h).status_code == 404


def test_requires_auth(client, db):  # noqa: F811
    assert client.get("/me/photo").status_code == 401
    assert client.put("/me/photo", content=JPEG).status_code == 401
    assert client.delete("/me/photo").status_code == 401


def test_rejects_oversized_non_jpeg_and_empty(client, db):  # noqa: F811
    h = register(client, "ph5@example.com")
    big = JPEG + b"\x00" * PhotoSettings().max_bytes
    assert _put(client, h, big).status_code == 413
    assert _put(client, h, b"\x89PNG\r\n\x1a\n" + b"\x00" * 50).status_code == 415
    assert _put(client, h, b"").status_code == 400
    assert db.scalar(select(func.count()).select_from(UserPhoto)) == 0


def test_users_only_see_their_own_photo(client, db):  # noqa: F811
    a = register(client, "ph6a@example.com")
    b = register(client, "ph6b@example.com")
    _put(client, a)
    assert client.get("/me/photo", headers=b).status_code == 404
    other = JPEG + b"\x02"
    _put(client, b, other)
    assert client.get("/me/photo", headers=a).content == JPEG
    assert client.get("/me/photo", headers=b).content == other


def test_upload_rate_limit(client, db):  # noqa: F811
    h = register(client, "ph7@example.com")
    limit = PhotoSettings().put_limit
    for _ in range(limit):
        assert _put(client, h).status_code == 200
    r = _put(client, h)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1


def test_rejected_uploads_do_not_use_the_quota(client, db):  # noqa: F811
    h = register(client, "ph8@example.com")
    for _ in range(PhotoSettings().put_limit + 2):
        assert _put(client, h, b"\x89PNG").status_code == 415
    assert _put(client, h).status_code == 200


def test_photo_is_deleted_with_the_account(client, db):  # noqa: F811
    h = register(client, "ph9@example.com")
    _put(client, h)
    uid = db.scalar(select(User.id).where(User.email == "ph9@example.com"))
    assert _count(db, uid) == 1
    assert delete_user(db, "ph9@example.com") is True
    assert _count(db, uid) == 0


def test_delete_me_endpoint_removes_the_photo(client, db):  # noqa: F811
    h = register(client, "ph10@example.com")
    _put(client, h)
    uid = db.scalar(select(User.id).where(User.email == "ph10@example.com"))
    r = client.request("DELETE", "/me", json={"password": "uzun-parola-1"}, headers=h)
    assert r.status_code == 204
    db.expire_all()
    assert _count(db, uid) == 0
