"""POST /playlists/{id}/tracks 403 teshisi: yeni playlist olustur, sarki eklemenin degisik yollarini dene.

Gereken: spikes/out/sample.json (spotify_probe.py uretir), .env icinde SPOTIFY_CLIENT_ID.
Her denemenin HTTP durumunu ve Spotify'in hata mesajini yazar. Hesapta "tini-spike-2" adli ozel playlist olusturur; sonra elle sil.
"""
import json

from common import OUT, http, load_env, need
from spotify_probe import API, authorize


def main():
    load_env()
    token = authorize(need("SPOTIFY_CLIENT_ID"))
    h = {"Authorization": f"Bearer {token}"}
    sample = json.loads((OUT / "sample.json").read_text(encoding="utf8"))
    uri = f"spotify:track:{sample[0]['id']}"

    def show(name, st, body):
        msg = body.get("error") if isinstance(body, dict) else body
        print(f"{st:>4}  {name}  {json.dumps(msg, ensure_ascii=False)[:200] if msg else ''}")

    st, me = http("GET", API + "/me", headers=h)
    show("GET /me", st, me)
    st, pl = http("POST", API + "/me/playlists", headers=h,
                  body={"name": "tini-spike-2", "public": False, "description": "Tini Faz 0 testi, silinebilir"})
    show("POST /me/playlists", st, pl)
    if st not in (200, 201):
        return
    pid = pl["id"]
    print("owner == me:", (pl.get("owner") or {}).get("id") == me.get("id"), "| collaborative:", pl.get("collaborative"))

    st, b = http("GET", f"{API}/playlists/{pid}", headers=h)
    show("GET /playlists/{id}", st, b)
    for name, method, path, kw in [
        ("POST /playlists/{id}/tracks (body uris)", "POST", f"/playlists/{pid}/tracks", {"body": {"uris": [uri]}}),
        ("POST /playlists/{id}/tracks (query uris)", "POST", f"/playlists/{pid}/tracks", {"params": {"uris": uri}}),
        ("POST /playlists/{id}/items (body uris)", "POST", f"/playlists/{pid}/items", {"body": {"uris": [uri]}}),
        ("PUT /playlists/{id}/tracks (body uris)", "PUT", f"/playlists/{pid}/tracks", {"body": {"uris": [uri]}}),
    ]:
        st, b = http(method, API + path, headers=h, **kw)
        show(name, st, b)


if __name__ == "__main__":
    main()
