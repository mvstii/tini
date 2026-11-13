import pytest
from sqlalchemy import create_engine

from app.config import get_settings
from app.ratelimit import get_auth_limits, get_photo_limiter
from app.sources.http import reset_limiters


@pytest.fixture(autouse=True)
def _fresh_auth_limits():
    """Testler aynı sahte IP'den çok kayıt yapar; sayaçlar her testte sıfırlanır."""
    get_auth_limits().clear()
    get_photo_limiter().clear()
    yield
    get_auth_limits().clear()
    get_photo_limiter().clear()


@pytest.fixture(autouse=True)
def _no_vote_expansion(monkeypatch):
    """Oy sonrası arka plan genişletmesi testlerde dış ağa çıkmaz."""
    monkeypatch.setattr("app.profile.api.after_vote", lambda track_id: None)


@pytest.fixture(autouse=True)
def _fresh_source_limiters():
    """Paylaşılan kaynak sınırlayıcıları testler arasında sızmasın."""
    reset_limiters()
    yield
    reset_limiters()


@pytest.fixture(scope="session")
def test_engine():
    """Tüm testler için tek engine/havuz (her fixture'ın kendi engine'i bağlantı sızdırıyordu).

    İzolasyon test başına bağlantı + dış işlem + ROLLBACK ile sürer. Sızan açık işlem ya da
    kilit diğer testleri sonsuza dek kilitlemesin diye oturum başına süre sınırları konur.
    Hiçbir test `DATABASE_URL`'i değiştirmez; URL oturum başında bir kez okunur."""
    engine = create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=3,
        connect_args={
            "options": "-c lock_timeout=15000 -c idle_in_transaction_session_timeout=300000"
        },
    )
    yield engine
    engine.dispose()
