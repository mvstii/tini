"""Sanatci grafigi riskleri: Deezer related kalitesi, 2 adimlik genisleme boyutu, Deezer<->MusicBrainz sanatci eslemesi.

Girdi : spikes/out/sample.json (spotify_probe.py uretir)
Cikti : spikes/out/graph.json ve konsol ozeti.
Ortam : GRAPH_ARTISTS (varsayilan 25, olculecek farkli sanatci sayisi).
Deezer'a ~25*22 istek, MusicBrainz'e ~2 istek/sanatci (1 istek/sn kurali). Sure ~10 dk.
Not: Deezer kosullari ticari kullanimi yasaklar; bu betik yalnizca Faz 0 olcumudur.
"""
import json
import os
import re
import time

from common import OUT, http, load_env

DZ = "https://api.deezer.com"
MB = "https://musicbrainz.org/ws/2"
DZ_LINK = re.compile(r"deezer\.com/(?:\w+/)?artist/(\d+)")


def dz(path, **params):
    time.sleep(0.15)
    st, b = http("GET", f"{DZ}/{path}", params=params or None)
    return b if st == 200 and isinstance(b, dict) and "error" not in b else {}


def dz_artist(s):
    """(deezer_id, yontem). ISRC dogrulugu daha yuksek; yoksa ad aramasi."""
    if s.get("isrc"):
        b = dz(f"track/isrc:{s['isrc']}")
        if b.get("artist"):
            return b["artist"]["id"], "isrc"
    b = dz("search/artist", q=s["artist"], limit=1)
    if b.get("data"):
        return b["data"][0]["id"], "ad"
    return None, ""


def related(aid):
    return [(a["id"], a["name"]) for a in dz(f"artist/{aid}/related", limit=20).get("data", [])]


def mb_map(name, deezer_id):
    """MusicBrainz'te sanatciyi bul; url-rels'te Deezer baglantisi var mi, varsa ayni sanatci mi."""
    time.sleep(1.1)
    st, b = http("GET", f"{MB}/artist", params={"fmt": "json", "query": f'artist:"{name}"', "limit": 3})
    cands = [a for a in (b.get("artists", []) if st == 200 and isinstance(b, dict) else []) if a.get("score", 0) >= 90]
    if not cands:
        return "yok"
    time.sleep(1.1)
    st, a = http("GET", f"{MB}/artist/{cands[0]['id']}", params={"fmt": "json", "inc": "url-rels"})
    ids = set()
    if st == 200 and isinstance(a, dict):
        for r in a.get("relations", []):
            m = DZ_LINK.search((r.get("url") or {}).get("resource", ""))
            if m:
                ids.add(int(m.group(1)))
    if not ids:
        return "ad_eslesti_baglanti_yok"
    return "baglanti_dogru" if deezer_id in ids else "baglanti_celisiyor"


def main():
    load_env()
    limit = int(os.environ.get("GRAPH_ARTISTS", "25"))
    sample = json.loads((OUT / "sample.json").read_text(encoding="utf8"))
    seen, picks = set(), []
    for s in sample:
        if s["artist"] not in seen:
            seen.add(s["artist"])
            picks.append(s)
    picks = picks[:limit]
    lib_names = {s["artist"].lower() for s in sample}

    rows = []
    for i, s in enumerate(picks, 1):
        aid, how = dz_artist(s)
        row = {"artist": s["artist"], "deezer_id": aid, "via": how, "n1": 0, "reciprocal": None,
               "n2": 0, "lib_hits_1": 0, "lib_hits_2": 0, "related_names": [], "mb": ""}
        if aid:
            hop1 = related(aid)
            row["n1"] = len(hop1)
            row["related_names"] = [n for _, n in hop1]
            row["lib_hits_1"] = sum(1 for _, n in hop1 if n.lower() in lib_names)
            ids2, names2, back, checked = set(), set(), 0, 0
            for k, (rid, rname) in enumerate(hop1):
                h2 = related(rid)
                if k < 5:
                    checked += 1
                    back += any(x == aid for x, _ in h2)
                for x, n in h2:
                    if x != aid:
                        ids2.add(x)
                        names2.add(n.lower())
            row["n2"] = len(ids2 | {x for x, _ in hop1})
            row["lib_hits_2"] = len(names2 & lib_names)
            row["reciprocal"] = round(back / checked, 2) if checked else None
            row["mb"] = mb_map(s["artist"], aid)
        rows.append(row)
        print(f"{i:>2}/{len(picks)} {s['artist']}: via={how or '-'} n1={row['n1']} n2={row['n2']} "
              f"karsilikli={row['reciprocal']} kutuphane(1/2)={row['lib_hits_1']}/{row['lib_hits_2']} mb={row['mb']}")

    (OUT / "graph.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf8")
    ok = [r for r in rows if r["deezer_id"]]
    n = len(rows)
    print(f"\n== ozet (n={n}) ==")
    print(f"Deezer sanatci bulundu: {len(ok)}/{n} (ISRC ile: {sum(1 for r in ok if r['via'] == 'isrc')})")
    if ok:
        avg = lambda k: sum(r[k] for r in ok) / len(ok)
        print(f"ortalama 1 adim: {avg('n1'):.1f} | 2 adim (benzersiz): {avg('n2'):.0f}")
        rec = [r["reciprocal"] for r in ok if r["reciprocal"] is not None]
        print(f"karsilikli kenar orani (ilk 5 komsu): %{100 * sum(rec) / len(rec):.0f}" if rec else "karsilikli: veri yok")
        print(f"kutuphane sanatcisina varan: 1 adimda {sum(1 for r in ok if r['lib_hits_1'])}/{len(ok)}, "
              f"2 adimda {sum(1 for r in ok if r['lib_hits_2'])}/{len(ok)}")
        from collections import Counter
        print("MusicBrainz eslemesi:", dict(Counter(r["mb"] for r in ok)))
    print("\nElle bak (ilk 8 sanatci, komsu listesi):")
    for r in rows[:8]:
        print(f"- {r['artist']}: {', '.join(r['related_names'][:10])}")


if __name__ == "__main__":
    main()
