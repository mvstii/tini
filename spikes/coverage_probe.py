"""Ornek icin ISRC/MBID/benzerlik/etiket kapsamini kaynak ve populerlik katmani bazinda olcer (Faz 0 kapisi).

Girdi : spikes/out/sample.json (spotify_probe.py uretir)
        spikes/out/sample_niche.json (istege bagli, elle: [{"title":..., "artist":..., "isrc":...}] ~50 az bilinen sarki)
Gereken .env: LASTFM_API_KEY
Istege bagli .env: LISTENBRAINZ_ALGORITHM (varsayilan dogrulanmamistir), NICHE_LISTENERS (varsayilan 50000)
Kaynaklar: Last.fm (benzer, etiket, dinleyici sayisi), ListenBrainz (benzer kayit), Deezer (related artists),
           MusicBrainz (MBID, tur, iliskiler). Discogs sonra eklenir (token + kosullar okunmadi).
Katman: Last.fm dinleyici sayisi < NICHE_LISTENERS ise "nis" (Spotify popularity alani kapali, yerine vekil olcut).
Cikti: spikes/out/coverage.csv ve ozet. Kapi: ISRC + benzerlik (Last.fm, ListenBrainz veya Deezer) >= %80.
MusicBrainz 1 istek/sn kuralina uyar.
"""
import csv
import json
import os
import time

from common import OUT, http, load_env, need

MB = "https://musicbrainz.org/ws/2"
LFM = "https://ws.audioscrobbler.com/2.0/"
LB = "https://labs.api.listenbrainz.org/similar-recordings/json"
DZ = "https://api.deezer.com"
LB_ALGO_DEFAULT = "session_based_days_9000_session_300_contribution_5_threshold_15_limit_50_skip_30"
_mb_artist_cache = {}


def mb_get(path, **params):
    time.sleep(1.1)
    return http("GET", f"{MB}/{path}", params={"fmt": "json", **params})


def mbid_for(s):
    """(mbid, yontem, artist_mbid). ISRC once; yoksa/bulunamazsa guvenli metin aramasi (skor >= 90)."""
    if s.get("isrc"):
        st, b = mb_get(f"isrc/{s['isrc']}", inc="artist-credits")
        if st == 200 and isinstance(b, dict) and b.get("recordings"):
            r = b["recordings"][0]
            ac = r.get("artist-credit") or [{}]
            return r["id"], "isrc", (ac[0].get("artist") or {}).get("id", "")
    q = f'recording:"{s["title"]}" AND artist:"{s["artist"]}"'
    st, b = mb_get("recording", query=q, limit=1)
    if st == 200 and isinstance(b, dict) and b.get("recordings") and b["recordings"][0].get("score", 0) >= 90:
        r = b["recordings"][0]
        ac = r.get("artist-credit") or [{}]
        return r["id"], "text", (ac[0].get("artist") or {}).get("id", "")
    return "", "", ""


def mb_artist(artist_mbid):
    if not artist_mbid:
        return 0, 0
    if artist_mbid not in _mb_artist_cache:
        st, b = mb_get(f"artist/{artist_mbid}", inc="genres+artist-rels")
        g = r = 0
        if st == 200 and isinstance(b, dict):
            g, r = len(b.get("genres", [])), len(b.get("relations", []))
        _mb_artist_cache[artist_mbid] = (g, r)
    return _mb_artist_cache[artist_mbid]


def lastfm(method, key, **kw):
    return http("GET", LFM, params={"method": method, "api_key": key, "format": "json", **kw})


def deezer_related(isrc, artist):
    """Deezer'da sanatciyi bul (ISRC veya ad aramasi), related artists sayisini dondur."""
    time.sleep(0.2)
    artist_id = None
    if isrc:
        st, b = http("GET", f"{DZ}/track/isrc:{isrc}")
        if st == 200 and isinstance(b, dict) and b.get("artist"):
            artist_id = b["artist"]["id"]
    if not artist_id:
        st, b = http("GET", f"{DZ}/search/artist", params={"q": artist, "limit": 1})
        if st == 200 and isinstance(b, dict) and b.get("data"):
            artist_id = b["data"][0]["id"]
    if not artist_id:
        return 0
    time.sleep(0.2)
    st, b = http("GET", f"{DZ}/artist/{artist_id}/related", params={"limit": 20})
    return len(b.get("data", [])) if st == 200 and isinstance(b, dict) else 0


def load_sample():
    sample = [dict(s, source="library") for s in json.loads((OUT / "sample.json").read_text(encoding="utf8"))]
    p = OUT / "sample_niche.json"
    if p.exists():
        sample += [dict(s, source="niche_list") for s in json.loads(p.read_text(encoding="utf8"))]
    return sample


def main():
    load_env()
    key = need("LASTFM_API_KEY")
    algo = os.environ.get("LISTENBRAINZ_ALGORITHM", LB_ALGO_DEFAULT)
    niche_cut = int(os.environ.get("NICHE_LISTENERS", "50000"))
    sample = load_sample()
    rows = []
    for i, s in enumerate(sample, 1):
        row = {"source": s["source"], "title": s["title"], "artist": s["artist"], "isrc": s.get("isrc") or "",
               "mbid": "", "mbid_via": "", "listeners": 0, "tier": "", "lfm_similar": 0, "lfm_tags": 0,
               "lb_similar": 0, "lb_status": "", "dz_related": 0, "mb_genres": 0, "mb_rels": 0}
        row["mbid"], row["mbid_via"], artist_mbid = mbid_for(s)
        row["mb_genres"], row["mb_rels"] = mb_artist(artist_mbid)
        st, info = lastfm("track.getInfo", key, artist=s["artist"], track=s["title"], autocorrect=1)
        if st == 200 and isinstance(info, dict) and "track" in info:
            row["listeners"] = int(info["track"].get("listeners") or 0)
        row["tier"] = "nis" if row["listeners"] < niche_cut else "yaygin"
        st, sim = lastfm("track.getSimilar", key, artist=s["artist"], track=s["title"], limit=50, autocorrect=1)
        if st == 200 and isinstance(sim, dict):
            row["lfm_similar"] = len(sim.get("similartracks", {}).get("track", []))
        st, tags = lastfm("track.getTopTags", key, artist=s["artist"], track=s["title"], autocorrect=1)
        if st == 200 and isinstance(tags, dict):
            row["lfm_tags"] = len(tags.get("toptags", {}).get("tag", []))
        if row["mbid"]:
            st, lb = http("GET", LB, params={"recording_mbids": row["mbid"], "algorithm": algo})
            row["lb_status"] = st
            if st == 200 and isinstance(lb, list):
                row["lb_similar"] = len(lb)
        row["dz_related"] = deezer_related(row["isrc"], s["artist"])
        rows.append(row)
        print(f"{i:>3}/{len(sample)} [{row['tier']}] {s['artist']} - {s['title']}: mbid={row['mbid_via'] or '-'} "
              f"lfm={row['lfm_similar']} lb={row['lb_similar']} dz={row['dz_related']} mbrel={row['mb_rels']}")

    with open(OUT / "coverage.csv", "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    def report(label, rs):
        n = len(rs)
        if not n:
            return
        p = lambda c: f"%{100 * c / n:.0f}"
        any_sim = lambda r: r["lfm_similar"] or r["lb_similar"] or r["dz_related"]
        no_lfm = lambda r: r["lb_similar"] or r["dz_related"] or r["mb_rels"]
        print(f"\n== {label} (n={n}) ==")
        print(f"ISRC var            {p(sum(1 for r in rs if r['isrc']))}")
        print(f"MBID                {p(sum(1 for r in rs if r['mbid']))}  (metin aramasiyla: {sum(1 for r in rs if r['mbid_via'] == 'text')})")
        print(f"Last.fm benzer      {p(sum(1 for r in rs if r['lfm_similar']))}")
        print(f"ListenBrainz benzer {p(sum(1 for r in rs if r['lb_similar']))}")
        print(f"Deezer related      {p(sum(1 for r in rs if r['dz_related']))}")
        print(f"MB iliski / tur     {p(sum(1 for r in rs if r['mb_rels']))} / {p(sum(1 for r in rs if r['mb_genres']))}")
        print(f"Last.fm etiket      {p(sum(1 for r in rs if r['lfm_tags']))}")
        print(f"Benzerlik (herhangi) {p(sum(1 for r in rs if any_sim(r)))}")
        print(f"Last.fm OLMADAN      {p(sum(1 for r in rs if no_lfm(r)))}  (LB, Deezer veya MB iliskisi)")
        both = sum(1 for r in rs if r["isrc"] and any_sim(r))
        print(f"KAPI (ISRC + benzerlik) {p(both)} -> {'GECTI' if 100 * both / n >= 80 else 'KALDI'} (esik %80)")

    report("TUMU", rows)
    for tier in ("yaygin", "nis"):
        report(f"katman: {tier}", [r for r in rows if r["tier"] == tier])
    tail = sum(1 for r in rows if r["tier"] == "nis")
    if tail < 15:
        print(f"\nUYARI: nis katmanda yalnizca {tail} sarki var; sonuc guvenilmez. sample_niche.json ekle.")


if __name__ == "__main__":
    main()
