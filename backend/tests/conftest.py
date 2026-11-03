import pytest

from app.ratelimit import get_auth_limits


@pytest.fixture(autouse=True)
def _fresh_auth_limits():
    """Testler aynı sahte IP'den çok kayıt yapar; sayaçlar her testte sıfırlanır."""
    get_auth_limits().clear()
    yield
    get_auth_limits().clear()
