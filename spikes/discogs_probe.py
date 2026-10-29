"""Discogs stil/tur etiketi kapsami: ornekteki sarkilar icin /database/search sonucunda style/genre var mi.

Girdi : spikes/out/sample.json (spotify_probe.py uretir)
Gereken .env: DISCOGS_TOKEN (discogs.com > Settings > Developers > Generate new token)
Istege bagli: DISCOGS_SAMPLE (varsayilan 100)
Cikti : spikes/out/discogs.csv ve konsol ozeti. Token ile 60 istek/dk; betik 1.1 sn bekler (~2 dk).
Not: Discogs ToS icerigi gerekenden uzun onbellege almayi yasaklar; bu betik yalnizca sayim yapar, ham veri saklamaz.
"""
import csv
import os
import time

import json

from common import OUT, http, load_env, need


def main():
    load_env()
    token = need("DISCOGS_TOKEN")
    n = int(os.environ.get("DISCOGS_SAMPLE", "100"))
    sample = json.loads((OUT / "sample.json").read_text(encoding="utf8"))[:n]
    h = {"Authorization": f"Discogs token={token}", "User-Agent": "TiniSpike/0.1 (faz0 olcum)"}
    rows = []
    for i, s in enumerate(sample, 1):
        time.sleep(1.1)
        st, b = http("GET", "https://api.discogs.com/database/search", headers=h,
                     params={"type": "release", "artist": s["artist"], "track": s["title"], "per_page": 5})
        res = b.get("results", []) if st == 200 and isinstance(b, dict) else []
        row = {"artist": s["artist"], "title": s["title"], "status": st, "results": len(res),
               "has_style": int(any(r.get("style") for r in res)), "has_genre": int(any(r.get("genre") for r in res))}
        rows.append(row)
        print(f"{i:>3}/{len(sample)} {s['artist']} - {s['title']}: http={st} sonuc={row['results']} stil={row['has_style']}")
    with open(OUT / "discogs.csv", "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    t = len(rows)
    p = lambda c: f"%{100 * c / t:.0f}"
    print(f"\n== Discogs (n={t}) ==")
    print(f"HTTP 200       : {p(sum(1 for r in rows if r['status'] == 200))}")
    print(f"sonuc donen    : {p(sum(1 for r in rows if r['results']))}")
    print(f"stil etiketi   : {p(sum(r['has_style'] for r in rows))}")
    print(f"tur (genre)    : {p(sum(r['has_genre'] for r in rows))}")


if __name__ == "__main__":
    main()
