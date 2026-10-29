"""Spotify Development Mode uc nokta dogrulamasi (PKCE) + 100 sarkilik ornek cikarma.

Gereken .env: SPOTIFY_CLIENT_ID
Spotify dashboard'da redirect URI olarak http://127.0.0.1:8888/callback ekle.
Cikti: spikes/out/spotify_probe.json (uc nokta -> HTTP durumu), spikes/out/sample.json (ornek sarkilar).
Not: playlist yazma denemesi hesapta ozel bir "tini-spike" playlist'i olusturur; isi bitince elle silebilirsin.
"""
import base64
import hashlib
import http.server
import json
import secrets
import threading
import urllib.parse
import webbrowser

from common import OUT, http, load_env, need

REDIRECT = "http://127.0.0.1:8888/callback"
SCOPES = "user-library-read user-top-read user-read-recently-played playlist-modify-private playlist-read-private"
API = "https://api.spotify.com/v1"


def authorize(client_id):
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Tamam, bu sekmeyi kapatabilirsin.")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 8888), H)
    t = threading.Thread(target=srv.handle_request)
    t.start()
    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code", "redirect_uri": REDIRECT,
        "scope": SCOPES, "state": state, "code_challenge_method": "S256", "code_challenge": challenge})
    print("Tarayici aciliyor:", url)
    webbrowser.open(url)
    t.join(timeout=180)
    srv.server_close()
    if got.get("state") != state or "code" not in got:
        raise SystemExit(f"Yetkilendirme basarisiz: {got}")
    st, tok = http("POST", "https://accounts.spotify.com/api/token", form={
        "grant_type": "authorization_code", "code": got["code"], "redirect_uri": REDIRECT,
        "client_id": client_id, "code_verifier": verifier})
    if st != 200:
        raise SystemExit(f"Token alinamadi: {st} {tok}")
    return tok["access_token"]


def main():
    load_env()
    token = authorize(need("SPOTIFY_CLIENT_ID"))
    h = {"Authorization": f"Bearer {token}"}
    results = {}

    def probe(name, method, path, **kw):
        st, body = http(method, API + path, headers=h, **kw)
        results[name] = st
        print(f"{st:>4}  {name}")
        return st, body

    st, me = probe("GET /me", "GET", "/me")
    probe("GET /me/tracks", "GET", "/me/tracks", params={"limit": 1})
    st, top = probe("GET /me/top/tracks", "GET", "/me/top/tracks", params={"limit": 50, "time_range": "long_term"})
    probe("GET /me/top/artists", "GET", "/me/top/artists", params={"limit": 5})
    probe("GET /me/player/recently-played", "GET", "/me/player/recently-played", params={"limit": 5})
    probe("GET /search (limit=10)", "GET", "/search", params={"q": "radiohead", "type": "track", "limit": 10})

    # Ornek: kaydedilmis sarkilar (+ yetmezse top tracks)
    sample, offset = [], 0
    while len(sample) < 100 and offset < 300:
        st, page = http("GET", API + "/me/tracks", headers=h, params={"limit": 50, "offset": offset})
        if st != 200 or not page.get("items"):
            break
        for it in page["items"]:
            t = it["track"]
            sample.append({"id": t["id"], "title": t["name"], "artist": t["artists"][0]["name"],
                           "artist_id": t["artists"][0]["id"], "isrc": (t.get("external_ids") or {}).get("isrc"),
                           "duration_ms": t["duration_ms"]})
        offset += 50
    if len(sample) < 100 and isinstance(top, dict):
        seen = {s["id"] for s in sample}
        for t in top.get("items", []):
            if t["id"] not in seen:
                sample.append({"id": t["id"], "title": t["name"], "artist": t["artists"][0]["name"],
                               "artist_id": t["artists"][0]["id"], "isrc": (t.get("external_ids") or {}).get("isrc"),
                               "duration_ms": t["duration_ms"]})
    sample = sample[:100]
    (OUT / "sample.json").write_text(json.dumps(sample, ensure_ascii=False, indent=1), encoding="utf8")
    print(f"Ornek: {len(sample)} sarki, ISRC'li: {sum(1 for s in sample if s['isrc'])}")

    if sample:
        probe("GET /artists/{id}/albums", "GET", f"/artists/{sample[0]['artist_id']}/albums", params={"limit": 5})
        probe("GET /search isrc:", "GET", "/search", params={"q": f"isrc:{sample[0]['isrc']}", "type": "track", "limit": 1})

    # Kapali oldugu belgelenen uc noktalar: hala kapali mi (varsayma, olc)
    probe("GET /recommendations (kapali bekleniyor)", "GET", "/recommendations", params={"seed_artists": sample[0]["artist_id"]} if sample else None)
    if sample:
        probe("GET /audio-features (kapali bekleniyor)", "GET", f"/audio-features/{sample[0]['id']}")
        probe("GET /artists/{id}/top-tracks (kapali bekleniyor)", "GET", f"/artists/{sample[0]['artist_id']}/top-tracks")
        probe("GET /artists/{id}/related-artists (kapali bekleniyor)", "GET", f"/artists/{sample[0]['artist_id']}/related-artists")
    probe("GET /browse/new-releases (kapali bekleniyor)", "GET", "/browse/new-releases")

    # Playlist yazma
    st, pl = probe("POST /me/playlists", "POST", "/me/playlists",
                   body={"name": "tini-spike", "public": False, "description": "Tini Faz 0 testi, silinebilir"})
    if st in (200, 201) and sample:
        probe("POST /playlists/{id}/tracks", "POST", f"/playlists/{pl['id']}/tracks",
              body={"uris": [f"spotify:track:{sample[0]['id']}"]})

    (OUT / "spotify_probe.json").write_text(json.dumps(results, indent=1), encoding="utf8")


if __name__ == "__main__":
    main()
