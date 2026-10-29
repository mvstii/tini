"""Spotify OAuth (PKCE). Spotify'a giden çağrılar yalnızca bu pakette yapılır."""
import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
ME_URL = "https://api.spotify.com/v1/me"
SERVICE = "spotify"


@dataclass(frozen=True)
class Tokens:
    access: str
    refresh: str | None
    expires_at: datetime
    scopes: str


def make_pkce() -> tuple[str, str]:
    """(verifier, S256 challenge)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def build_authorize_url(
    client_id: str, redirect_uri: str, scopes: str, state: str, challenge: str
) -> str:
    return AUTHORIZE_URL + "?" + urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
    )


def _parse(body: dict, previous_refresh: str | None = None) -> Tokens:
    return Tokens(
        access=body["access_token"],
        refresh=body.get("refresh_token", previous_refresh),
        expires_at=datetime.now(UTC) + timedelta(seconds=int(body["expires_in"])),
        scopes=body.get("scope", ""),
    )


def exchange_code(
    http: httpx.Client, client_id: str, redirect_uri: str, code: str, verifier: str
) -> Tokens:
    r = http.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    r.raise_for_status()
    return _parse(r.json())


def refresh_tokens(http: httpx.Client, client_id: str, refresh: str) -> Tokens:
    r = http.post(
        TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": refresh, "client_id": client_id},
    )
    r.raise_for_status()
    return _parse(r.json(), previous_refresh=refresh)


def fetch_profile_id(http: httpx.Client, access: str) -> str:
    r = http.get(ME_URL, headers={"Authorization": f"Bearer {access}"})
    r.raise_for_status()
    return r.json()["id"]
