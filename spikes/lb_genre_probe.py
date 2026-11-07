"""PR-0 dogrulama spike'i: ListenBrainz tur omurgasi (lb-radio/tags) yeterli mi?

Salt okunur: yalnizca dis API'lere GET atar, spikes/out/ altina yazar; uygulama koduna dokunmaz.
Olcer:
  1. ~20 alt tur x 3 populerlik bandi icin GET /1/lb-radio/tags (yanit alanlari, sure, hiz siniri basliklari, token).
  2. GET /1/popularity/top-recordings-for-artist/{mbid} (token ihtiyaci, yanit bicimi).
  3. Kayit MBID -> ISRC (MusicBrainz recording/{mbid}?inc=isrcs, 1 istek/sn) cozulme orani.
  4. Dusuk bantta etiket tutarliligini elle orneklemek icin liste.
Kapi: alt tur basina >= 20 ISRC'li kayit ve >= %60 MBID->ISRC cozumu.

Calistirma (repo kokunden):
  python spikes/lb_genre_probe.py --genres 2 --isrc-per-band 4      # kucuk deneme
  python spikes/lb_genre_probe.py                                   # ornekli kosu (bant basina 8 ISRC sorgusu)
  python spikes/lb_genre_probe.py --full                            # tum kayitlar icin ISRC sorgusu (uzun)
Opsiyonel .env: LISTENBRAINZ_TOKEN (yoksa anonim denenir), MUSICBRAINZ_CONTACT (User-Agent iletisimi).
Sonuc onbellegi spikes/out/lb_mb_cache.json (yeniden calistirmada ayni MBID bir daha sorulmaz).
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from common import OUT, load_env

LB = "https://api.listenbrainz.org/1"
MB = "https://musicbrainz.org/ws/2"
# (ad, etiket takma adlari). Etiketler MusicBrainz etiket adlaridir; Turkce olanlar icin birden cok yazim denenir.
GENRES = [
    ("arabesk", ["arabesk", "arabesque"]),
    ("anadolu rock", ["anatolian rock", "turkish rock", "anadolu rock"]),
    ("turkce pop", ["turkish pop"]),
    ("turkce rap", ["turkish hip hop", "turkish rap"]),
    ("turk halk", ["turkish folk", "turkish folk music"]),
    ("trap", ["trap"]),
    ("drill", ["drill"]),
    ("boom bap", ["boom bap"]),
    ("shoegaze", ["shoegaze"]),
    ("jazz fusion", ["jazz fusion"]),
    ("house", ["house"]),
    ("techno", ["techno"]),
    ("synthpop", ["synth-pop", "synthpop"]),
    ("black metal", ["black metal"]),
    ("bossa nova", ["bossa nova"]),
    ("reggae", ["reggae"]),
    ("punk rock", ["punk rock"]),
    ("soul", ["soul"]),
    ("country", ["country"]),
    ("k-pop", ["k-pop"]),
]
# populerlik penceresi [pop_begin, pop_end]; kucuk denemede 0-33 en cok dinlenen cikti (yon ters), bu yuzden top/mid/tail.
BANDS = {"top": (0, 33), "mid": (33, 66), "tail": (66, 100)}
COUNT = 25
MB_INTERVAL = 1.1


def ua():
    contact = os.environ.get("MUSICBRAINZ_CONTACT", "mustafabkr42@outlook.com")
    return f"tini-spike/0.1 ({contact})"


def get(url, params=None, token=None, tries=4, post=None):
    """(status, json_or_text, headers_dict, saniye) doner; 429'da Retry-After'a uyar. `post` verilirse JSON POST."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    hdrs = {"User-Agent": ua(), "Accept": "application/json"}
    if token:
        hdrs["Authorization"] = f"Token {token}"
    data = None
    if post is not None:
        data = json.dumps(post).encode()
        hdrs["Content-Type"] = "application/json"
    for attempt in range(tries + 1):
        t0 = time.monotonic()
        req = urllib.request.Request(url, data=data, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw, code, h = r.read(), r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            raw, code, h = e.read(), e.code, dict(e.headers)
        except urllib.error.URLError as e:
            if attempt == tries:
                return 0, str(e), {}, time.monotonic() - t0
            time.sleep(2**attempt)
            continue
        dt = time.monotonic() - t0
        if code in (429, 503) and attempt < tries:
            time.sleep(min(int(h.get("Retry-After", 2 ** (attempt + 1))), 60))
            continue
        text = raw.decode("utf8", "replace")
        try:
            body = json.loads(text)
        except ValueError:
            body = text[:300]
        return code, body, h, dt
    return 0, "retries exhausted", {}, 0.0


def rate_headers(h):
    keep = ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "x-ratelimit-reset-in", "retry-after")
    return {k: v for k, v in ((k.lower(), v) for k, v in h.items()) if k in keep}


def as_records(body):
    """lb-radio yaniti liste ya da {'payload':...} olabilir; hangisi oldugunu da kaydederiz."""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in ("payload", "recordings", "data"):
            v = body.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                for kk in ("recordings", "data", "payload"):
                    if isinstance(v.get(kk), list):
                        return v[kk]
    return []


def mb_info(mbid, cache):
    """Kayit MBID -> {isrcs, title, artist, artist_mbid}; onbellege yazilir. None = sorgu hatasi (yazilmaz)."""
    if mbid in cache:
        return cache[mbid]
    time.sleep(MB_INTERVAL)
    code, body, _, _ = get(f"{MB}/recording/{mbid}", {"fmt": "json", "inc": "isrcs+artist-credits"})
    if code == 404:
        cache[mbid] = {"isrcs": [], "title": None, "artist": None, "artist_mbid": None}
    elif code == 200 and isinstance(body, dict):
        credit = (body.get("artist-credit") or [{}])[0].get("artist") or {}
        cache[mbid] = {"isrcs": body.get("isrcs") or [], "title": body.get("title"),
                       "artist": credit.get("name"), "artist_mbid": credit.get("id")}
    else:
        return None
    return cache[mbid]


def listen_counts(mbids, token):
    """POST /1/popularity/recording: kayit basina toplam dinlenme; bant yonunu dogrulamak icin."""
    code, body, _, _ = get(f"{LB}/popularity/recording", token=token, post={"recording_mbids": mbids})
    if code != 200 or not isinstance(body, list):
        return code, []
    return code, sorted(int(x.get("total_listen_count") or 0) for x in body if isinstance(x, dict))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--genres", type=int, default=len(GENRES), help="ilk N alt tur (deneme icin)")
    ap.add_argument("--isrc-per-band", type=int, default=8, help="bant basina ISRC sorgulanacak kayit")
    ap.add_argument("--full", action="store_true", help="tum kayitlar icin ISRC sorgula")
    args = ap.parse_args()
    load_env()
    token = os.environ.get("LISTENBRAINZ_TOKEN") or None
    print(f"token: {'var' if token else 'yok (anonim)'}")

    cache_p = OUT / "lb_mb_cache.json"
    cache = json.loads(cache_p.read_text(encoding="utf8")) if cache_p.exists() else {}
    report = {"token": bool(token), "radio": [], "popularity": [], "shape": {}}
    artist_pool = []

    for name, tags in GENRES[: args.genres]:
        for band, (lo, hi) in BANDS.items():
            params = {"tag": tags, "operator": "OR", "pop_begin": lo, "pop_end": hi, "count": COUNT}
            code, body, h, dt = get(f"{LB}/lb-radio/tags", params, token)
            recs = as_records(body) if code == 200 else []
            if code == 200 and not report["shape"]:
                report["shape"] = {"top_type": type(body).__name__,
                                   "keys": sorted(recs[0].keys()) if recs and isinstance(recs[0], dict) else None,
                                   "example": recs[0] if recs else None}
                print("yanit sekli:", json.dumps(report["shape"], ensure_ascii=False)[:600])
            row = {"genre": name, "band": band, "status": code, "n": len(recs), "sec": round(dt, 2),
                   "rate": rate_headers(h), "err": None if code == 200 else body, "isrc_checked": 0, "isrc_ok": 0,
                   "records": []}
            todo = recs if args.full else recs[: args.isrc_per_band]
            mbids = [r["recording_mbid"] for r in recs if isinstance(r, dict) and r.get("recording_mbid")]
            lc_code, lc = listen_counts(mbids, token) if mbids else (0, [])
            row["listens_status"] = lc_code
            row["listens_median"] = lc[len(lc) // 2] if lc else None
            for r in todo:
                mbid = r.get("recording_mbid") if isinstance(r, dict) else None
                if not mbid:
                    continue
                info = mb_info(mbid, cache)
                if info is None:
                    continue
                row["isrc_checked"] += 1
                row["isrc_ok"] += 1 if info["isrcs"] else 0
                row["records"].append({**r, **info})
                if info["artist_mbid"]:
                    artist_pool.append(info["artist_mbid"])
            rate = f"{row['isrc_ok']}/{row['isrc_checked']}"
            print(f"{name:13} {band:5} http={code} n={row['n']:>2} {dt:4.1f}s isrc={rate} "
                  f"dinlenme-medyan={row['listens_median']} (http {lc_code}) kalan={row['rate'].get('x-ratelimit-remaining')}")
            report["radio"].append(row)
            cache_p.write_text(json.dumps(cache), encoding="utf8")

    # populerlik ucu: token ihtiyaci ve bicim (3 sanatci)
    for mbid in list(dict.fromkeys(artist_pool))[:3]:
        code, body, h, dt = get(f"{LB}/popularity/top-recordings-for-artist/{mbid}", None, token)
        anon = None
        if token:
            anon = get(f"{LB}/popularity/top-recordings-for-artist/{mbid}")[0]
        recs = body if isinstance(body, list) else as_records(body)
        report["popularity"].append({"artist_mbid": mbid, "status": code, "anonymous_status": anon, "n": len(recs),
                                     "sec": round(dt, 2), "example": recs[:2], "err": None if code == 200 else body})
        print(f"popularity {mbid} http={code} n={len(recs)}")

    (OUT / "lb_genre_probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf8")
    summarize(report, args)


def summarize(report, args):
    print("\n== ozet: alt tur basina ==")
    print("tur            kayit(3 bant)  ornek-ISRC  cozulme  tahmini-ISRCli  kapi")
    for name, _ in GENRES[: args.genres]:
        rows = [r for r in report["radio"] if r["genre"] == name]
        n = sum(r["n"] for r in rows)
        chk = sum(r["isrc_checked"] for r in rows)
        ok = sum(r["isrc_ok"] for r in rows)
        rate = ok / chk if chk else 0.0
        est = n * rate
        gate = "GECTI" if est >= 20 and rate >= 0.6 else "KALDI"
        print(f"{name:14} {n:>8}  {ok:>4}/{chk:<4}  %{100 * rate:3.0f}   {est:6.1f}      {gate}")
    print("\nNot: kayit sayisi istek basina COUNT ile sinirli; 'tahmini' = kayit x cozulme orani.")
    print("Dusuk bant etiket tutarliligi icin spikes/out/lb_genre_probe.json -> radio[band=tail].records elle okunmali.")


if __name__ == "__main__":
    main()
