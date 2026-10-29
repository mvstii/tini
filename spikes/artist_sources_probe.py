"""Deezer'a alternatif sanatci benzerligi kaynaklari: Last.fm artist.getSimilar ve ListenBrainz similar-artists.

Girdi : spikes/out/graph.json (graph_probe.py uretir; ayni sanatcilar ve Deezer komsulari)
Gereken .env: LASTFM_API_KEY
Cikti : spikes/out/artist_sources.json ve konsol ozeti (kapsam + Deezer ile ortusme).
ListenBrainz icin sanatci MBID'si MusicBrainz ad aramasindan (skor >= 90) alinir; MBID yoksa o sanatci atlanir.
"""
import json
import os
import time

from common import OUT, http, load_env, need

LFM = "https://ws.audioscrobbler.com/2.0/"
LB = "https://labs.api.listenbrainz.org/similar-artists/json"
LB_ALGO = os.environ.get("LISTENBRAINZ_ARTIST_ALGORITHM",
                         "session_based_days_7500_session_300_contribution_5_threshold_10_limit_100_filter_True_skip_30")
MB = "https://musicbrainz.org/ws/2"


def norm(s):
    return "".join(c for c in s.lower() if c.isalnum())


def mb_artist_mbid(name):
    time.sleep(1.1)
    st, b = http("GET", f"{MB}/artist", params={"fmt": "json", "query": f'artist:"{name}"', "limit": 1})
    a = (b.get("artists") or [{}])[0] if st == 200 and isinstance(b, dict) else {}
    return a.get("id", "") if a.get("score", 0) >= 90 else ""


def overlap(names, deezer_names, k=20):
    a, b = {norm(n) for n in names[:k]}, {norm(n) for n in deezer_names[:k]}
    return len(a & b) / len(b) if b else 0.0


def main():
    load_env()
    key = need("LASTFM_API_KEY")
    rows = json.loads((OUT / "graph.json").read_text(encoding="utf8"))
    out, shown = [], False
    for i, r in enumerate(rows, 1):
        res = {"artist": r["artist"], "dz": r["related_names"], "lfm": [], "lb": [], "mbid": ""}
        st, b = http("GET", LFM, params={"method": "artist.getSimilar", "artist": r["artist"], "api_key": key,
                                         "format": "json", "limit": 50, "autocorrect": 1})
        if st == 200 and isinstance(b, dict):
            res["lfm"] = [a["name"] for a in b.get("similarartists", {}).get("artist", [])]
        res["mbid"] = mb_artist_mbid(r["artist"])
        if res["mbid"]:
            st, b = http("GET", LB, params={"artist_mbids": res["mbid"], "algorithm": LB_ALGO})
            items = b if isinstance(b, list) else (b.get("data", []) if isinstance(b, dict) else [])
            if st == 200 and items and not shown:
                print("LB ornek kayit anahtarlari:", list(items[0].keys()) if isinstance(items[0], dict) else items[0])
                shown = True
            res["lb"] = [x.get("name", "") for x in items if isinstance(x, dict) and x.get("name")]
            res["lb_status"] = st
        out.append(res)
        print(f"{i:>2}/{len(rows)} {r['artist']}: lfm={len(res['lfm'])} lb={len(res['lb'])} mbid={'+' if res['mbid'] else '-'} "
              f"ortusme(dz)  lfm={overlap(res['lfm'], r['related_names']):.2f} lb={overlap(res['lb'], r['related_names']):.2f}")

    (OUT / "artist_sources.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf8")
    n = len(out)
    pct = lambda c: f"%{100 * c / n:.0f}"
    print(f"\n== ozet (n={n}) ==")
    print(f"Last.fm >=10 komsu : {pct(sum(1 for o in out if len(o['lfm']) >= 10))}")
    print(f"MBID bulundu       : {pct(sum(1 for o in out if o['mbid']))}")
    print(f"ListenBrainz >=10  : {pct(sum(1 for o in out if len(o['lb']) >= 10))}")
    print(f"Deezer'siz kapsam (Last.fm veya LB >=10): {pct(sum(1 for o in out if len(o['lfm']) >= 10 or len(o['lb']) >= 10))}")
    for name, k in (("Last.fm", "lfm"), ("ListenBrainz", "lb")):
        vals = [overlap(o[k], o["dz"]) for o in out if o[k]]
        if vals:
            print(f"{name} ile Deezer ilk-20 ortusmesi (ortalama, {len(vals)} sanatci): {sum(vals) / len(vals):.2f}")
    print("\nElle bak (ilk 6 sanatci):")
    for o in out[:6]:
        print(f"- {o['artist']}\n    lfm: {', '.join(o['lfm'][:8])}\n    lb : {', '.join(o['lb'][:8])}")


if __name__ == "__main__":
    main()
