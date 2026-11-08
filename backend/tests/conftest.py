import pytest

from app.ratelimit import get_auth_limits
from app.sources.http import reset_limiters


@pytest.fixture(autouse=True)
def _fresh_auth_limits():
    """Testler aynı sahte IP'den çok kayıt yapar; sayaçlar her testte sıfırlanır."""
    get_auth_limits().clear()
    yield
    get_auth_limits().clear()


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
