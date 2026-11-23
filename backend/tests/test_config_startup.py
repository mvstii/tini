import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.config import Settings


def make(**kw):
    # .env dosyasından değer sızmasın: yalnız verilen alanlar geçerli
    return Settings(_env_file=None, **kw)


def test_dev_defaults_still_boot(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("CREDENTIAL_KEY", raising=False)
    s = make()
    assert s.app_env == "dev"
    assert s.credential_key == ""


@pytest.mark.parametrize("env", ["dev", "test"])
def test_non_prod_needs_no_key(env):
    assert make(app_env=env).app_env == env


@pytest.mark.parametrize("env", ["production", "Prod", "", "staging"])
def test_unknown_env_rejected(env):
    with pytest.raises(ValidationError):
        make(app_env=env)


def test_prod_with_valid_key_boots():
    key = Fernet.generate_key().decode()
    assert make(app_env="prod", credential_key=key).credential_key == key


@pytest.mark.parametrize("key", ["", "not-a-fernet-key", "abc"])
def test_prod_without_valid_key_fails(key):
    with pytest.raises(ValidationError):
        make(app_env="prod", credential_key=key)
