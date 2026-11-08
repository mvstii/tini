"""PR-0 ek prob (SPEC v2.2): Turkce oncelikli, sirali eleme, surekli besleme olcumu. Salt okunur, yalnizca stdlib.

Bu surum G1-G3'u icerir: iskelet (Budget/Store/safe_write/kilit/bayraklar), saf fonksiyonlar ve `--phase offline` (A0).
Ag fazlari (p0/tags/radio/artist/gate) sonraki gorevlerde (G4+) eklenir; bu dosya simdilik hicbir ag istegi atmaz,
.env okumaz ve Deezer'a hic istek atmaz (`--allow-deezer` kapali, spike'ta kullanilmaz).

Calistirma (repo kokunden):
  python spikes/lb_genre_probe2.py --phase offline      # A0: eski json/onbellekten cevrimdisi analiz, 0 istek
  python spikes/lb_genre_probe2.py --phase p0 --dry-run # faz butcelerini basar, istek atmaz
"""
import argparse
import json
import math
import os
import random
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, load_env  # noqa: E402
# get/mb_info G5+ icin ice aktarilir; P0 kendi tek denemelik, butceli `Requester`'ini kullanir (get 4 kez yeniden dener)
from lb_genre_probe import BANDS, GENRES, LB, MB, as_records, get, mb_info, rate_headers, ua  # noqa: E402,F401

TR_GENRES = [g for g, _ in GENRES[:5]]
VARIOUS_ARTISTS = "89ad4ac3-39f7-470e-963a-56509c546377"
PROTECTED = {"lb_genre_probe.json", "lb_mb_cache.json", "lb_tail_sample.md", "lb_run.log"}
GATE_C, GATE_A = 20, 15  # K2
BASE_CACHE = "lb_mb_cache.json"
BASE_JSON = "lb_genre_probe.json"

# Faz butceleri (SPEC "Bilesen Hiyerarsisi" tablosu; ust sinir istek sayisi, LB / MB)
PHASE_BUDGET = {
    "offline": (0, 0, "A0: eski json/onbellek, <5 sn"),
    "p0": (8, 9, "en cok 20 istek (sabit), ~40 sn"),
    "tags": (30, 30, "T3-TR: 24 takma ad (LB radio + MB artist tag:), ~1 dk"),
    "radio": (200, 80, "T1-TR: 5 tur x 3 bant x <=3 cekim (count=1000) + LB metadata 200/istek; nonTR G8"),
    "artist": (200, 600, "D+E-TR: <=200 sanatci, uyarlamali browse, ~12 dk"),
    "gate": (0, 0, "A/B/C/D/E varyantlari, istek yok"),
    "sample": (0, 0, "elle ornekleme listesi uretir, istek yok"),
    "sample_eval": (0, 0, "isaretli ornekleme md okur, isabet orani + A duzeltmesi, istek yok"),
}


class BudgetExceeded(Exception):
    pass


class Budget:
    """lb/mb/lf istek sayaclari; `--max-*` asilinca BudgetExceeded."""

    def __init__(self, lb=0, mb=0, lf=0, total=None):
        self.max = {"lb": lb, "mb": mb, "lf": lf}
        self.used = {"lb": 0, "mb": 0, "lf": 0}
        self.total = total  # tum kaynaklar icin ortak ust sinir (P0: 20)

    def spend(self, kind, n=1):
        if self.total is not None and sum(self.used.values()) + n > self.total:
            raise BudgetExceeded(f"toplam istek butcesi asildi ({sum(self.used.values())}+{n} > {self.total})")
        if self.used[kind] + n > self.max[kind]:
            raise BudgetExceeded(f"{kind} butcesi asildi ({self.used[kind]}+{n} > {self.max[kind]})")
        self.used[kind] += n


def safe_write(path, text):
    """Korunan eski ciktilara yazmayi reddeder; atomik (tmp + os.replace), PermissionError'da 3 kez dener."""
    p = Path(path)
    if p.name in PROTECTED:
        raise SystemExit(f"korunan dosyaya yazma engellendi: {p.name}")
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    for attempt in range(3):
        try:
            os.replace(tmp, p)
            return p
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.5 * (attempt + 1))
    return p


class Store:
    """Temel onbellek (salt okunur) + lb_probe2_cache.json + durum dosyasi; O_EXCL kilidi."""

    def __init__(self, out=OUT, force_unlock=False):
        self.out = Path(out)
        self.base = _load_json(self.out / BASE_CACHE, {})
        self.cache = _load_json(self.out / "lb_probe2_cache.json", {})
        self.state = _load_json(self.out / "lb_probe2_state.json", {"done": []})
        self.lock_path = self.out / "lb_probe2.lock"
        self.force_unlock = force_unlock
        self._locked = False

    def acquire(self):
        if self.force_unlock and self.lock_path.exists():
            self.lock_path.unlink()
        try:
            fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise SystemExit(f"kilit var: {self.lock_path} (baska kosu ya da yarim kalan kosu; --force-unlock)")
        with os.fdopen(fd, "w") as f:
            f.write(f"{os.getpid()} {time.time():.0f}\n")  # yalnizca bilgi; PID yoklamasi yapilmaz
        self._locked = True

    def release(self):
        if self._locked:
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass
            self._locked = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.flush()
        self.release()
        return False

    def lookup(self, mbid):
        return self.cache.get(mbid) or self.base.get(mbid)

    def put(self, mbid, info):
        self.cache[mbid] = info

    def done(self, unit):
        return unit in self.state["done"]

    def mark_done(self, unit):
        if unit not in self.state["done"]:
            self.state["done"].append(unit)

    def flush(self):
        safe_write(self.out / "lb_probe2_cache.json", json.dumps(self.cache, ensure_ascii=False))
        safe_write(self.out / "lb_probe2_state.json", json.dumps(self.state, ensure_ascii=False, indent=1))


def _load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


# ---------------------------------------------------------------- saf fonksiyonlar (G2)

def wilson(k, n, z=1.96):
    """Wilson %95 araligi (alt, ust). n=0 -> (0, 1)."""
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def _fold(s):
    """casefold + Turkce i/I/ı/İ birlestirme + NFKD aksan atma."""
    s = (s or "").replace("İ", "i").replace("ı", "i").replace("I", "i").casefold()
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _strip_parens(s):
    return re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", s)


def norm_title(s):
    """Karsilastirma anahtari: parantez ici atilir, noktalama bosluk olur, sondaki 1-2 haneli sayi atilir
    (o sayi version_marker'da 'num:N' olarak tasinir)."""
    t = re.sub(r"[^0-9a-z]+", " ", _strip_parens(_fold(s))).strip()
    toks = t.split()
    if len(toks) > 1 and re.fullmatch(r"\d{1,2}", toks[-1]):
        toks = toks[:-1]
    return " ".join(toks)


def version_marker(s):
    """Surum isareti: live/demo/instrumental/remix ve sondaki sayi eki; '+' ile birlesik, yoksa ''."""
    f = _fold(s)
    found = []
    for name, pat in (("live", r"\b(live|canli)\b"), ("demo", r"\bdemo\b"),
                      ("instrumental", r"\b(instrumental|enstrumantal)\b"), ("remix", r"\b(remix|rmx)\b")):
        if re.search(pat, f):
            found.append(name)
    toks = re.sub(r"[^0-9a-z]+", " ", _strip_parens(f)).split()
    if len(toks) > 1 and re.fullmatch(r"\d{1,2}", toks[-1]):
        found.append("num:" + toks[-1])
    return "+".join(sorted(found))


def _first_isrc(isrcs):
    return sorted(isrcs)[0] if isrcs else None


def sibling_isrc(rec, browse):
    """Ayni sanatci + norm_title + version_marker'li, baska MBID'li kardes kaydin ISRC'si.
    Doner (isrc|None, eslesme_turu) ; tur: 'sibling' | 'sibling_multi' | 'none' | 'no_artist'."""
    am = rec.get("artist_mbid")
    if not am or am == VARIOUS_ARTISTS:
        return None, "no_artist"
    key = (norm_title(rec.get("title")), version_marker(rec.get("title")))
    found = set()
    multi = False
    for b in browse or []:
        if b.get("artist_mbid") != am or b.get("mbid") == rec.get("mbid"):
            continue
        if (norm_title(b.get("title")), version_marker(b.get("title"))) != key:
            continue
        if len(b.get("isrcs") or []) > 1:
            multi = True
        found.update(b.get("isrcs") or [])
    if not found:
        return None, "none"
    return _first_isrc(found), ("sibling_multi" if multi or len(found) > 1 else "sibling")


def cap_per_artist(recs, k=2):
    """Sanatci basina ilk k kayit; Various Artists ve sanatcisiz kayitlar disarida."""
    seen = Counter()
    out = []
    for r in recs:
        a = r.get("artist_mbid") or r.get("artist")
        if not a or a == VARIOUS_ARTISTS:
            continue
        if seen[a] < k:
            seen[a] += 1
            out.append(r)
    return out


def pop_tier(artist_listens):
    """K4: {sanatci: dinlenme} -> {sanatci: 'nis'|'orta'|'populer'} (siraya gore tertiller; niş = en az dinlenen 1/3)."""
    ordered = sorted(artist_listens, key=lambda a: (artist_listens[a], str(a)))
    n = len(ordered)
    tiers = {}
    for i, a in enumerate(ordered):
        tiers[a] = "nis" if i * 3 < n else ("orta" if i * 3 < 2 * n else "populer")
    # n<3 ise hepsi 'nis' cikmasin: tek eleman populer sayilir
    if n < 3:
        for a in ordered:
            tiers[a] = "orta"
    return tiers


def gate_row(recs, variant, listens=None, population=None):
    """K2 kapisi: C>=20 ISRC'li benzersiz kayit ve A>=15 ISRC'li benzersiz sanatci.
    `population` verilirse recs orneklemdir: C = population*p, aralik %95 (20'yi iceriyorsa SINIRDA).
    `listens` ({sanatci_mbid: dinlenme}) verilirse A_nis (niş tertil) hesaplanir."""
    if recs is None:
        return {"variant": variant, "n": 0, "C": 0, "A": 0, "A_niche": 0, "rate": None, "ci": None,
                "top_share": None, "verdict": "ÖLÇÜLMEDİ"}
    recs = [r for r in recs if r.get("artist_mbid") != VARIOUS_ARTISTS]
    n = len(recs)
    cands = {}
    for r in recs:
        i = _first_isrc(r.get("isrcs"))
        if i and i not in cands:
            cands[i] = r.get("artist_mbid") or r.get("artist")
    C = len(cands)
    arts = Counter(a for a in cands.values() if a)
    A = len(arts)
    top_share = (max(arts.values()) / C) if C else 0.0
    n_rec_isrc = sum(1 for r in recs if r.get("isrcs"))
    rate = (n_rec_isrc / n) if n else None
    lo, hi = wilson(n_rec_isrc, n)
    a_niche = None
    if listens is not None and arts:
        tiers = pop_tier({a: listens.get(a, 0) for a in arts})
        a_niche = sum(1 for t in tiers.values() if t == "nis")
    c_lo = c_hi = float(C)
    if population and n and n < population:
        c_lo, c_hi = population * lo, population * hi
        C = round(population * rate)
    if n == 0:
        verdict = "ÖLÇÜLMEDİ"
    elif c_lo < GATE_C <= c_hi and c_lo != c_hi:
        verdict = "SINIRDA"
    elif C >= GATE_C and A >= GATE_A:
        verdict = "GEÇTİ"
    else:
        verdict = "KALDI"
    return {"variant": variant, "n": n, "C": C, "A": A, "A_niche": a_niche, "rate": rate,
            "ci": [round(lo, 4), round(hi, 4)], "C_ci": [round(c_lo, 1), round(c_hi, 1)],
            "top_share": round(top_share, 4), "verdict": verdict}


def program_gate(rows, total_needed=16, tr_needed=5, nontr_needed=None):
    """K1: Turkce 5/5 zorunlu + toplam >=16/20. rows: [{genre, tr, verdict}].
    SINIRDA/ÖLÇÜLMEDİ hem gecti hem kaldi sayilir; iki sonuc ayniysa robust.
    Turkce disi satir yoksa (E2) yalnizca Turkce 5/5 aranir."""
    def passes(optimistic):
        def ok(v):
            return v == "GEÇTİ" or (optimistic and v in ("SINIRDA", "ÖLÇÜLMEDİ"))
        tr = [r for r in rows if r.get("tr")]
        non = [r for r in rows if not r.get("tr")]
        tr_ok = sum(ok(r["verdict"]) for r in tr)
        non_ok = sum(ok(r["verdict"]) for r in non)
        good = len(tr) >= tr_needed and tr_ok == len(tr)
        if non:
            good = good and (tr_ok + non_ok) >= total_needed
        return good, tr_ok, non_ok
    pess, tr_p, non_p = passes(False)
    opt, tr_o, non_o = passes(True)
    verdict = "GEÇTİ" if pess else ("KALDI" if not opt else "SINIRDA")
    return {"verdict": verdict, "robust": pess == opt, "pess": pess, "opt": opt,
            "tr_pass": [tr_p, tr_o], "nontr_pass": [non_p, non_o]}


def diagnose(row):
    """row: A, top_share, isrc_rate_record, isrc_rate_artist, sibling_closes(bool).
    -> 'etiket' | 'isrc_açığı' | 'sürüm_açığı' | 'ikisi' ('yok': sorun saptanmadi)."""
    etiket = (row.get("A") or 0) < GATE_A or (row.get("top_share") or 0) > 0.30
    rr, ra = row.get("isrc_rate_record") or 0.0, row.get("isrc_rate_artist") or 0.0
    gap = rr < 0.60
    gap_kind = None
    if gap:
        gap_kind = "sürüm_açığı" if (ra >= 0.60 and row.get("sibling_closes")) else "isrc_açığı"
    if etiket and gap_kind:
        return "ikisi"
    if etiket:
        return "etiket"
    return gap_kind or "yok"


def depth(C, A, m, N):
    """Oturum derinligi D = floor(min(C, A*m) / N)."""
    return int(min(C, A * m) // N)


def chao1(counts):
    """counts: kayit basina gorulme sayisi (liste ya da sozluk). N^ = S + f1^2/(2 f2); f2=0 -> S + f1(f1-1)/2."""
    vals = list(counts.values()) if isinstance(counts, dict) else list(counts)
    vals = [v for v in vals if v > 0]
    S = len(vals)
    f1 = sum(1 for v in vals if v == 1)
    f2 = sum(1 for v in vals if v == 2)
    return S + (f1 * f1 / (2 * f2) if f2 else f1 * (f1 - 1) / 2)


def saturation(counts):
    """H = (N^ - S) / S ; S=0 ise None."""
    vals = [v for v in (counts.values() if isinstance(counts, dict) else counts) if v > 0]
    return (chao1(vals) - len(vals)) / len(vals) if vals else None


def growth_point(strategy, req, sec, C, A, A_niche):
    return {"strategy": strategy, "req": req, "sec": None if sec is None else round(sec, 2), "C": C, "A": A, "A_niche": A_niche}


def feed_score(variant_rows, tr_total_D=None):
    """K3 sozluk sirasi (buyuk = iyi): (kapi, min D Turkce, Turkce toplam D, nis dolu tur sayisi, H, aday/sn).
    variant_rows: [{genre, tr, verdict, D, niche_full, H, cand_per_sec}]."""
    tr = [r for r in variant_rows if r.get("tr")]
    gate = 1 if program_gate(variant_rows)["verdict"] == "GEÇTİ" else 0
    min_d = min((r.get("D") or 0 for r in tr), default=0)
    total_d = tr_total_D if tr_total_D is not None else sum(r.get("D") or 0 for r in tr)
    niche = sum(1 for r in variant_rows if r.get("niche_full"))
    hs = [r["H"] for r in variant_rows if r.get("H") is not None]
    h = sum(hs) / len(hs) if hs else 0.0
    cps = sum(r.get("cand_per_sec") or 0.0 for r in variant_rows)
    return (gate, min_d, total_d, niche, h, cps)


def rank_strategies(growth):
    """growth: [{strategy, rows, points[, tr_total_D]}] -> feed_score'a, sonra son noktadaki aday/sn'ye gore azalan."""
    out = []
    for g in growth:
        pts = g.get("points") or []
        last = pts[-1] if pts else {}
        cps = (last.get("C", 0) / last["sec"]) if last.get("sec") else 0.0
        out.append({"strategy": g["strategy"], "score": feed_score(g.get("rows") or [], g.get("tr_total_D")),
                    "cand_per_sec": round(cps, 4)})
    out.sort(key=lambda x: (x["score"], x["cand_per_sec"]), reverse=True)
    for i, o in enumerate(out, 1):
        o["rank"] = i
    return out


# ---------------------------------------------------------------- A0 offline (G3)

def _rate_block(ok, n):
    lo, hi = wilson(ok, n)
    return {"n": n, "ok": ok, "rate": round(ok / n, 4) if n else None, "ci": [round(lo, 4), round(hi, 4)]}


def offline_analysis(probe, cache, genres=None):
    """Eski lb_genre_probe.json + lb_mb_cache.json uzerinde cevrimdisi olcum. Istek yok, dosya yazmaz."""
    cache = cache or {}
    radio = [r for r in probe.get("radio", []) if not genres or r["genre"] in genres]
    recs = []  # (genre, band, rec, isrc_ok, artist_name)
    for e in radio:
        for r in e.get("records") or []:
            ci = cache.get(r.get("recording_mbid")) or {}
            isrcs = r.get("isrcs") if r.get("isrcs") is not None else ci.get("isrcs") or []
            name = ci.get("artist") or r.get("artist")
            recs.append((e["genre"], e["band"], r, bool(isrcs), name, ci.get("title") or r.get("title")))
    per_genre = []
    for g in dict.fromkeys(e["genre"] for e in radio):
        mine = [x for x in recs if x[0] == g]
        bands = {}
        for b in BANDS:
            sub = [x for x in mine if x[1] == b]
            bands[b] = _rate_block(sum(x[3] for x in sub), len(sub))
        tm = [x for x in mine if x[1] in ("top", "mid")]
        c25 = sum(25 * (v["rate"] or 0) for v in bands.values())
        c25_hi = sum(25 * v["ci"][1] for v in bands.values() if v["n"])
        arts = Counter(x[2].get("artist_mbid") or x[4] for x in mine if x[3])
        per_genre.append({
            "genre": g, "tr": g in TR_GENRES, "bands": bands,
            "top_mid": _rate_block(sum(x[3] for x in tm), len(tm)),
            "all": _rate_block(sum(x[3] for x in mine), len(mine)),
            "artists_unique_isrc": len(arts),
            "top_share_isrc": round(max(arts.values()) / sum(arts.values()), 4) if arts else None,
            "c_est_count25": round(c25, 1), "c_est_count25_upper": round(c25_hi, 1),
            "isrcless_with_meta": sum(1 for x in mine if not x[3] and x[5] and x[4]),
        })
    pct = [x[2].get("percent") for x in recs if x[2].get("percent") is not None]
    edge = sum(1 for p in pct if p in (0, 100))
    edge_tr = [(x[0], x[1]) for x in recs if x[0] in TR_GENRES and x[2].get("percent") in (0, 100)]
    desc_bands = 0
    for e in radio:
        tc = [r.get("tag_count") for r in e.get("records") or [] if r.get("tag_count") is not None]
        desc_bands += bool(tc) and all(a >= b for a, b in zip(tc, tc[1:]))
    marker = defaultdict(lambda: [0, 0])
    source = defaultdict(lambda: [0, 0])
    for x in recs:
        m = version_marker(x[5]) or "(yok)"
        marker[m][0] += 1
        marker[m][1] += x[3]
        s = x[2].get("source") or "(yok)"
        source[s][0] += 1
        source[s][1] += x[3]
    seen = defaultdict(set)
    for x in recs:
        seen[x[2].get("recording_mbid")].add((x[0], x[1]))
    dup = {k: sorted(v) for k, v in seen.items() if len(v) > 1}
    v1_expected = {"arabesk": (8, 16), "anadolu rock": (3, 16), "turkce pop": (8, 16),
                   "turkce rap": (1, 16), "turk halk": (1, 16)}
    v1 = {}
    for g, (k, n) in v1_expected.items():
        row = next((p for p in per_genre if p["genre"] == g), None)
        got = (row["top_mid"]["ok"], row["top_mid"]["n"]) if row else None
        v1[g] = {"beklenen": [k, n], "olculen": list(got) if got else None, "uyum": got == (k, n),
                 "wilson_ust": round(wilson(*got)[1], 3) if got else None}
    return {
        "inputs": {"radio_entries": len(radio), "records": len(recs), "cache_entries": len(cache)},
        "per_genre": per_genre,
        "v1_check": v1,
        "v2_order": {"bands_total": len(radio), "bands_tag_count_non_increasing": desc_bands},
        "v3_percent": {"records": len(pct), "percent_0_or_100": edge,
                       "share": round(edge / len(pct), 4) if pct else None, "tr_edge_bands": edge_tr},
        "marker_x_isrc": {k: _rate_block(v[1], v[0]) for k, v in sorted(marker.items())},
        "source_x_isrc": {k: _rate_block(v[1], v[0]) for k, v in sorted(source.items())},
        "mbid_overlap": {"duplicates": len(dup), "examples": dict(list(dup.items())[:5])},
    }


def run_offline(args):
    probe = _load_json(OUT / BASE_JSON, None)
    if probe is None:
        raise SystemExit(f"temel dosya yok ya da okunamadi: {OUT / BASE_JSON}")
    cache = _load_json(OUT / BASE_CACHE, {})
    wanted = _genre_filter(args)
    rep = offline_analysis(probe, cache, wanted)
    rep["meta"] = {"phase": "offline", "used": {"lb": 0, "mb": 0, "lf": 0}, "requests": 0, "token": False,
                   "errors": 0, "session_size": args.session_size, "artist_cap": args.artist_cap,
                   "scope": args.scope, "seed": args.seed, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    path = OUT / f"lb_probe2_offline_{time.strftime('%Y%m%d_%H%M%S')}.json"
    safe_write(path, json.dumps(rep, ensure_ascii=False, indent=1))
    print_offline_summary(rep)
    print(f"yazildi: {path}")
    return 0


def print_offline_summary(rep):
    print(f"A0 offline: {rep['inputs']['records']} kayit, {rep['inputs']['radio_entries']} bant, 0 istek")
    for p in rep["per_genre"]:
        tm = p["top_mid"]
        print(f"  {p['genre']:<13}{'TR' if p['tr'] else '  '} top+mid {tm['ok']}/{tm['n']} "
              f"ust={tm['ci'][1]:.3f}  C~{p['c_est_count25']}(<= {p['c_est_count25_upper']}) "
              f"sanatci(isrc)={p['artists_unique_isrc']} top_pay={p['top_share_isrc']}")
    v3 = rep["v3_percent"]
    print(f"  percent 0/100: {v3['percent_0_or_100']}/{v3['records']} ({v3['share']})")
    v2 = rep["v2_order"]
    print(f"  tag_count azalan bant: {v2['bands_tag_count_non_increasing']}/{v2['bands_total']}")
    print("  v1 uyum:", {g: v["uyum"] for g, v in rep["v1_check"].items()})


# ---------------------------------------------------------------- P0 (G4): en cok 20 istek, canli

P0_TOTAL = 20
BARIS_MANCO = "33736d61-e2a2-4070-88dd-ad2e173d174c"  # lb_mb_cache.json'dan
GURSES = "104ed17c-1e58-4cf6-aa11-722341032571"       # lb_mb_cache.json'dan


def _scrub(text, token=None):
    """Rapora giren metinlerden token degerini ve 'Token ' kalibini ayiklar."""
    t = str(text)
    if token:
        t = t.replace(token, "***")
    return t.replace("Token ", "Token_")


class Requester:
    """Tek denemelik (yeniden deneme yok), butceli istek. Her istek kaydedilir; Authorization kaydedilmez."""

    def __init__(self, budget, token=None):
        self.budget, self.token, self.log = budget, token, []
        self._last = {"mb": 0.0, "lb": 0.0}

    def _wait(self, kind):
        wait = self._last[kind] + (1.1 if kind == "mb" else 0.35) - time.monotonic()
        if kind == "lb" and self.log:
            rate = next((r["rate"] for r in reversed(self.log) if r["kind"] == "lb"), {})
            rem = str(rate.get("x-ratelimit-remaining", "99"))
            if rem.isdigit() and int(rem) <= 2:
                wait = max(wait, float(rate.get("x-ratelimit-reset-in", 1) or 1) + 0.5)
        if wait > 0:
            time.sleep(wait)

    def call(self, unit, kind, method, url, params=None, post=None, use_token=False, text=False):
        self.budget.spend(kind)
        self._wait(kind)
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
        hdrs = {"User-Agent": ua(), "Accept": "text/plain" if text else "application/json"}
        if use_token and self.token:
            hdrs["Authorization"] = "Token " + self.token
        data = None
        if post is not None:
            data = json.dumps(post).encode()
            hdrs["Content-Type"] = "application/json"
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=hdrs), timeout=60) as r:
                raw, code, h = r.read(), r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            raw, code, h = e.read(), e.code, dict(e.headers)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raw, code, h = str(e).encode(), 0, {}
        dt = time.monotonic() - t0
        self._last[kind] = time.monotonic()
        body = raw.decode("utf-8", "replace")
        if not text:
            try:
                body = json.loads(body)
            except ValueError:
                pass
        rec = {"unit": unit, "kind": kind, "method": method, "url": _scrub(url[:300], self.token),
               "url_len": len(url), "post_items": len(next(iter(post.values()))) if post else None,
               "authorized": bool(use_token and self.token), "status": code, "sec": round(dt, 2),
               "rate": rate_headers(h), "err": None if code == 200 else _scrub(str(body)[:200], self.token)}
        self.log.append(rec)
        return code, body, rec


def _call_retry(self, *a, tries=2, **kw):
    """429/503/ag hatasinda (her yeniden deneme butceden dusulur) bekleyip en cok `tries` kez tekrarlar."""
    for attempt in range(tries + 1):
        code, body, rec = self.call(*a, **kw)
        if code not in (0, 429, 503) or attempt == tries:
            return code, body, rec
        try:
            wait = min(float(rec["rate"].get("retry-after") or 0), 30.0)
        except ValueError:  # Retry-After tarih bicimi
            wait = 0.0
        time.sleep(max(wait, 3.0 * (attempt + 1)))


Requester.call_retry = _call_retry


def _find_key(obj, key):
    """Ic ice yapida ilk `key` degerini bulur."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


def _isrc_values(obj, path="", out=None):
    """Ic ice yapida adi 'isrc' ile baslayan anahtarlari (yol, deger) olarak toplar."""
    out = [] if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower().startswith("isrc"):
                out.append((f"{path}/{k}", v))
            else:
                _isrc_values(v, f"{path}/{k}", out)
    elif isinstance(obj, list):
        for v in obj:
            _isrc_values(v, path + "[]", out)
    return out


def _radio_stats(body):
    recs = as_records(body) if not isinstance(body, str) else []
    mb = [r.get("recording_mbid") for r in recs if isinstance(r, dict)]
    pct = [r.get("percent") for r in recs if isinstance(r, dict) and r.get("percent") is not None]
    return {"n": len(recs), "unique": len(set(mb)), "percent_0_100": sum(1 for p in pct if p in (0, 100)),
            "top_type": type(body).__name__, "keys": sorted(recs[0]) if recs and isinstance(recs[0], dict) else None}


def _dict_body(code, body):
    return body if code == 200 and isinstance(body, dict) else {}


def run_p0(args):
    store = Store(OUT, force_unlock=args.force_unlock)
    cache = store.base
    if not cache:
        raise SystemExit(f"temel onbellek yok: {OUT / BASE_CACHE} (ag fazlari bunu ister)")
    res = store.state.setdefault("p0", {})
    if all(store.done("p0|" + u) for u in P0_UNITS):
        print("p0: tum birimler tamamlanmis; yeni istek 0 (yeniden olcmek icin lb_probe2_state.json'daki p0 kayitlarini sil)")
        return 0
    load_env()  # yalnizca burada; deger asla yazdirilmaz
    token = os.environ.get("LISTENBRAINZ_TOKEN") or None
    budget = Budget(lb=min(8, args.max_lb), mb=min(9, args.max_mb), lf=0, total=P0_TOTAL)
    rq = Requester(budget, token)
    # dogruluk kumesi: onbellekteki kayitlar (ISRC durumu + sanatci biliniyor), tohumlu sabit orneklem
    truth = sorted(m for m, v in cache.items() if isinstance(v, dict) and v.get("title") is not None)
    random.Random(args.seed).shuffle(truth)
    ids200, ids100, ids50 = truth[:200], truth[:100], truth[:50]
    errors = 0

    def isrc_set(m):
        return set(cache[m].get("isrcs") or [])

    def radio(unit, tags, count):
        code, body, rec = rq.call(unit, "lb", "GET", f"{LB}/lb-radio/tags",
                                  {"tag": tags, "operator": "OR", "pop_begin": 0, "pop_end": 100, "count": count})
        st = _radio_stats(body) if code == 200 else {}
        return {"status": code, "count_req": count, "tags": tags, **st,
                "summary": f"count={count} n={st.get('n')} uniq={st.get('unique')} {rec['sec']}s", "err": rec["err"]}

    def meta(unit, ids):
        code, body, rec = rq.call(unit, "lb", "POST", f"{LB}/metadata/recording/",
                                  post={"recording_mbids": ids, "inc": "artist tag"}, use_token=True)
        d = _dict_body(code, body)
        got = sum(1 for m in ids if d.get(m))
        agree = sum(1 for m in ids if d.get(m) and _find_key(d[m], "artist_mbid") == cache[m].get("artist_mbid"))
        return {"status": code, "requested": len(ids), "returned": got, "artist_agree": agree,
                "entries_with_isrc_key": sum(1 for m in ids if d.get(m) and '"isrc' in json.dumps(d[m]).lower()),
                "isrc_in_agreeing_truth": sum(1 for m in ids if d.get(m) and isrc_set(m) and
                                              any(i in json.dumps(d[m]) for i in isrc_set(m))),
                "isrc_paths": sorted({pth for m in ids if isinstance(d.get(m), dict) for pth, _ in _isrc_values(d[m])}),
                "isrc_exact_equal": sum(1 for m in ids if d.get(m) and
                                        {i for _, v in _isrc_values(d[m]) for i in (v if isinstance(v, list) else [v]) if i}
                                        == isrc_set(m)),
                "entry_keys": sorted({k for m in ids if isinstance(d.get(m), dict) for k in d[m]}),
                "summary": f"{got}/{len(ids)} dondu, sanatci uyumu {agree}/{len(ids)}", "err": rec["err"]}

    def meta_artist():
        arts = list(dict.fromkeys(cache[m].get("artist_mbid") for m in ids50 if cache[m].get("artist_mbid")))[:5]
        code, body, rec = rq.call("meta_artist", "lb", "GET", f"{LB}/metadata/artist/",
                                  {"artist_mbids": ",".join(arts), "inc": "tag"}, use_token=True)
        n = len(body) if code == 200 and isinstance(body, (list, dict)) else None
        return {"status": code, "requested": len(arts), "n": n, "top_type": type(body).__name__,
                "summary": f"{n}/{len(arts)} sanatci", "err": rec["err"]}

    def rid(unit, ids):
        q = "rid:(" + " OR ".join(ids) + ")"
        code, body, rec = rq.call(unit, "mb", "GET", f"{MB}/recording", {"query": q, "limit": 100, "fmt": "json"})
        by_id = {r.get("id"): r for r in _dict_body(code, body).get("recordings", []) if isinstance(r, dict)}
        returned = sum(1 for m in ids if m in by_id)
        exact = sum(1 for m in ids if m in by_id and set(by_id[m].get("isrcs") or []) == isrc_set(m))
        field = sum(1 for m in ids if m in by_id and "isrcs" in by_id[m])
        return {"status": code, "requested": len(ids), "returned": returned, "isrc_agree": exact,
                "agree_rate": round(exact / len(ids), 4), "with_isrcs_field": field,
                "summary": f"dondu {returned}/{len(ids)}, ISRC uyumu {exact}/{len(ids)}", "err": rec["err"]}

    def browse():
        code, body, rec = rq.call("browse", "mb", "GET", f"{MB}/recording",
                                  {"artist": BARIS_MANCO, "inc": "isrcs+artist-credits", "limit": 100, "fmt": "json"})
        d = _dict_body(code, body)
        recs = d.get("recordings", [])
        w = sum(1 for r in recs if r.get("isrcs"))
        return {"status": code, "n": len(recs), "with_isrc": w, "total_count": d.get("recording-count"),
                "summary": f"{len(recs)} kayit (toplam {d.get('recording-count')}), ISRC'li {w}", "err": rec["err"]}

    def sibling():
        title = next((v["title"] for v in cache.values() if isinstance(v, dict) and v.get("artist_mbid") == GURSES
                      and not v.get("isrcs") and v.get("title") and "�" not in v["title"]), None)
        if not title:
            return {"status": 0, "summary": "Gurses ISRC'siz kayit yok", "err": "no_seed"}
        q = f'arid:{GURSES} AND recording:"{title}"'
        code, body, rec = rq.call("sibling", "mb", "GET", f"{MB}/recording", {"query": q, "limit": 25, "fmt": "json"})
        recs = _dict_body(code, body).get("recordings", [])
        hits = [r for r in recs if r.get("isrcs")]
        return {"status": code, "n": len(recs), "with_isrc": len(hits), "sibling_found": bool(hits),
                "summary": f"{len(recs)} sonuc, ISRC'li kardes {len(hits)}", "err": rec["err"]}

    def genre_all():
        code, body, rec = rq.call("genre_all", "mb", "GET", f"{MB}/genre/all", {"fmt": "txt"}, text=True)
        names = [x.strip() for x in body.splitlines() if x.strip()] if code == 200 else []
        want = ("arabesk", "turkish folk", "anatolian rock", "turkish pop", "trap", "drill", "boom bap", "shoegaze",
                "bossa nova", "k-pop", "synth-pop", "black metal", "turkish hip hop")
        return {"status": code, "n": len(names), "wanted_present": [g for g in want if g in names],
                "summary": f"{len(names)} tur adi", "err": rec["err"]}

    def artist_tag(unit, tag):
        code, body, rec = rq.call(unit, "mb", "GET", f"{MB}/artist", {"query": f'tag:"{tag}"', "limit": 100, "fmt": "json"})
        d = _dict_body(code, body)
        arts = d.get("artists", [])
        tr = sum(1 for a in arts if a.get("country") == "TR")
        return {"status": code, "tag": tag, "count": d.get("count"), "page_n": len(arts), "tr_in_page": tr,
                "summary": f"tag={tag!r} toplam={d.get('count')} sayfa={len(arts)} TR={tr}", "err": rec["err"]}

    steps = [("radio100", lambda: radio("radio100", ["arabesk", "arabesque"], 100)),
             ("radio1000", lambda: radio("radio1000", ["arabesk", "arabesque"], 1000)),
             ("meta50", lambda: meta("meta50", ids50)),
             ("meta200", lambda: meta("meta200", ids200)),
             ("meta_artist", meta_artist),
             ("radio_rap", lambda: radio("radio_rap", ["türkçe rap"], 100)),
             ("rid50", lambda: rid("rid50", ids50)),
             ("rid100", lambda: rid("rid100", ids100)),
             ("browse", browse),
             ("sibling", sibling),
             ("genre_all", genre_all),
             ("artist_tag_a", lambda: artist_tag("artist_tag_a", "turkish hip hop")),
             ("artist_tag_b", lambda: artist_tag("artist_tag_b", "arabesk"))]
    assert [u for u, _ in steps] == P0_UNITS
    print(f"p0: butce toplam {P0_TOTAL} (LB<={budget.max['lb']}, MB<={budget.max['mb']}), token={'var' if token else 'yok'}")
    interrupted = None
    try:
        with store:
            for unit, fn in steps:
                if store.done("p0|" + unit):
                    continue
                out = fn()
                res[unit] = out
                if out.get("status") == 200:
                    store.mark_done("p0|" + unit)  # hata (5xx/ag) tamamlanmis sayilmaz; yeniden kosuda tekrarlanir
                else:
                    errors += 1
                store.flush()
                print(f"  {unit:<13} http={out.get('status')} {out.get('summary', '')}")
    except (KeyboardInterrupt, BudgetExceeded) as e:
        interrupted = repr(e)
    rid50 = res.get("rid50") or {}
    rep = {"meta": {"phase": "p0", "used": dict(budget.used), "requests": sum(budget.used.values()),
                    "budget_total": P0_TOTAL, "token": bool(token), "errors": errors, "interrupted": interrupted,
                    "seed": args.seed, "ts": time.strftime("%Y-%m-%d %H:%M:%S")},
           "requests": rq.log, "units": res,
           "decision": {"rid_bulk_ok_ge_49_of_50": rid50.get("isrc_agree", 0) >= 49,
                        "rid_agree_50": rid50.get("isrc_agree"),
                        "meta50_ok": (res.get("meta50") or {}).get("status") == 200,
                        "meta200_ok": (res.get("meta200") or {}).get("status") == 200,
                        "radio_count1000_ok": (res.get("radio1000") or {}).get("status") == 200}}
    path = OUT / f"lb_probe2_p0_{time.strftime('%Y%m%d_%H%M%S')}.json"
    safe_write(path, _scrub(json.dumps(rep, ensure_ascii=False, indent=1), token))
    print(f"istek: {rep['meta']['requests']} (LB {budget.used['lb']}, MB {budget.used['mb']}); yazildi: {path}")
    if interrupted:
        print("kesildi:", interrupted)
        return 2
    return 0


P0_UNITS = ["radio100", "radio1000", "meta50", "meta200", "meta_artist", "radio_rap", "rid50", "rid100",
            "browse", "sibling", "genre_all", "artist_tag_a", "artist_tag_b"]


# ---------------------------------------------------------------- T3 + T1-TR (G5)
# P0 bulgusu: ISRC birincil kaynagi LB POST /metadata/recording (200 MBID/istek, /recording/isrcs);
# yedek: MB rid: toplu arama (<=100); son care: tekli MB lookup (sinirli). Adlar taze API yanitindan gelir.

TR_ALIASES = {
    "arabesk": ["arabesk", "arabesque", "arabesk pop", "fantezi"],
    "anadolu rock": ["anatolian rock", "anadolu rock", "anatolian psych", "anatolian psychedelic rock",
                     "turkish psychedelic rock", "turkish rock"],
    "turkce pop": ["turkish pop", "türkçe pop", "türk pop"],
    "turkce rap": ["turkish hip hop", "turkish hip-hop", "turkish rap", "türkçe rap", "türk rap", "turkish trap"],
    "turk halk": ["turkish folk", "türk halk müziği", "halk müziği", "türkü", "anatolian folk"],
}
NOISY_ALIASES = {"arabesque"}  # John Debney gurultusu: yalnizca MB'de TR payi >= %50 ise kabul
T3_MIN_LB, T3_MIN_MB_ARTISTS, T3_MIN_TR = 20, 15, 0.5
META_BATCH, RID_BATCH, LOOKUP_CAP = 200, 100, 40
MAX_REPS, MIN_GAIN = 3, 0.10
PHASE_CAPS = {"tags": (30, 30), "radio": (200, 80)}  # (LB, MB) istek ust siniri; --max-* ile daha da kisilir
# G8 (Turkce disi 15 tur): toplam LB<=600, MB<=150; MB neredeyse yalniz rid: yedegi icin
NT_CAPS = {"tags": (50, 5), "radio": (300, 40), "artist": (250, 50)}
ALIAS_MAP = {**{g: list(a) for g, a in GENRES}, **TR_ALIASES}  # Turkce disi turler: GENRES takma adlari
NT_RESOLVE_CAP = 1000  # Turkce disi tur basina cozulecek en cok MBID (seed'li rastgele ornek; 5 LB metadata istegi)


def ascii_safe(s):
    """cp1254 vb. konsolda UnicodeEncodeError olmasin diye."""
    return str(s).encode("ascii", "backslashreplace").decode("ascii")


def accept_alias(lb_n, mb_count, mb_tr_share, noisy=False):
    """T3 kabul kurali: LB n>=20 ya da (MB sanatci>=15 ve TR>=%50). Gurultulu takma ad yalniz MB kanitiyla (>=15 ve TR>=%50)."""
    mb_ok = mb_count >= T3_MIN_MB_ARTISTS and mb_tr_share >= T3_MIN_TR
    return bool(mb_ok if noisy else (lb_n >= T3_MIN_LB or mb_ok))


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 1.0


def need_more_reps(rep_sets):
    """Tekrarli lb-radio cekimi: ikinci cekim her zaman yapilir; 3.'ye yalniz ikinci cekimin yeni benzersiz
    kazanci >= %10 ise ve cikti rastgele ise (Jaccard<0.99) gecilir."""
    if not rep_sets:
        return True
    if len(rep_sets) >= MAX_REPS:
        return False
    if len(rep_sets) == 1:
        return True
    if jaccard(rep_sets[0], rep_sets[1]) >= 0.99:
        return False  # deterministik
    before = set().union(*rep_sets[:-1])
    gain = len(rep_sets[-1] - before) / len(before) if before else 1.0
    return gain >= MIN_GAIN


def parse_meta_entry(e):
    """LB /metadata/recording girdisi -> {title, artist, artist_mbid, isrcs}."""
    e = e if isinstance(e, dict) else {}
    art, rec = e.get("artist") or {}, e.get("recording") or {}
    first = (art.get("artists") or [{}])[0] or {}
    return {"title": rec.get("name"), "artist": art.get("name") or first.get("name"),
            "artist_mbid": first.get("artist_mbid"), "isrcs": list(rec.get("isrcs") or []),
            "artists": credit_list(art)}


def credit_list(art):
    """LB artist blogu -> [[artist_mbid, ad, join_phrase], ...] (kredi sirasi; MBID'siz girdiler atlanir)."""
    out = []
    for a in (art or {}).get("artists") or []:
        if isinstance(a, dict) and a.get("artist_mbid"):
            out.append([a["artist_mbid"], a.get("name"), a.get("join_phrase") or ""])
    return out


def primary_artist(info, bands=()):
    """Birincil sanatci: D yolunda tohum sanatci (bant 'D@<mbid>') krediler arasindaysa o (feat./& ile baska
    sanatcinin adina yazilmasin); degilse kredinin ilk sanatcisi (feat./ft./& sonrakiler birincil sayilmaz)."""
    ids = [a[0] for a in info.get("artists") or [] if a and a[0]]
    for b in sorted(bands):
        if b.startswith("D@") and b[2:] in ids:
            return b[2:]
    return ids[0] if ids else info.get("artist_mbid")


def parse_mb_recording(r):
    """MB recording (arama ya da lookup) -> ayni bicim."""
    credit = ((r.get("artist-credit") or [{}])[0] or {}).get("artist") or {}
    return {"title": r.get("title"), "artist": credit.get("name"), "artist_mbid": credit.get("id"),
            "isrcs": list(r.get("isrcs") or [])}


def resolve_mbids(rq, store, mbids, lookup_left):
    """Onbellekte (lb_probe2_cache.json, yalniz taze yanitlar) olmayan MBID'leri cozer:
    LB metadata -> MB rid: -> tekli lookup (en cok `lookup_left`). Doner (istatistik, kalan_lookup)."""
    todo = [m for m in dict.fromkeys(mbids) if m not in store.cache]
    st = {"requested": len(todo), "lb_meta": 0, "mb_rid": 0, "mb_single": 0, "mb_404": 0, "unresolved": 0}
    for i in range(0, len(todo), META_BATCH):
        chunk = todo[i:i + META_BATCH]
        code, body, _ = rq.call_retry("meta", "lb", "POST", f"{LB}/metadata/recording/",
                                      post={"recording_mbids": chunk, "inc": "artist tag"}, use_token=True)
        if code == 200 and isinstance(body, dict):
            for m in chunk:
                if body.get(m):
                    store.put(m, {**parse_meta_entry(body[m]), "src": "lb_meta"})
                    st["lb_meta"] += 1
    missing = [m for m in todo if m not in store.cache]
    for i in range(0, len(missing), RID_BATCH):
        chunk = missing[i:i + RID_BATCH]
        q = "rid:(" + " OR ".join(chunk) + ")"
        code, body, _ = rq.call_retry("rid", "mb", "GET", f"{MB}/recording", {"query": q, "limit": 100, "fmt": "json"})
        if code == 200 and isinstance(body, dict):
            for r in body.get("recordings", []):
                if isinstance(r, dict) and r.get("id") in chunk and r["id"] not in store.cache:
                    store.put(r["id"], {**parse_mb_recording(r), "src": "mb_rid"})
                    st["mb_rid"] += 1
    for m in [m for m in missing if m not in store.cache]:
        if lookup_left <= 0:
            break
        lookup_left -= 1
        code, body, _ = rq.call_retry("lookup", "mb", "GET", f"{MB}/recording/{m}",
                                      {"fmt": "json", "inc": "isrcs+artist-credits"})
        if code == 200 and isinstance(body, dict):
            store.put(m, {**parse_mb_recording(body), "src": "mb_single"})
            st["mb_single"] += 1
        elif code == 404:
            store.put(m, {"title": None, "artist": None, "artist_mbid": None, "isrcs": [], "src": "mb_404"})
            st["mb_404"] += 1
    st["unresolved"] = sum(1 for m in todo if m not in store.cache)
    return st, lookup_left


def gate_block(rs, name, m, N, sibling_closes=False):
    """gate_row + oranlar + teshis + derinlik (tek tur x varyant)."""
    g = gate_row(rs, name)
    arts = {r.get("artist_mbid") for r in rs if r.get("artist_mbid")}
    arts_isrc = {r.get("artist_mbid") for r in rs if r.get("artist_mbid") and r.get("isrcs")}
    g["isrc_rate_record"] = g["rate"]
    g["isrc_rate_artist"] = round(len(arts_isrc) / len(arts), 4) if arts else None
    g["diagnose"] = diagnose({"A": g["A"], "top_share": g["top_share"], "isrc_rate_record": g["rate"] or 0.0,
                              "isrc_rate_artist": g["isrc_rate_artist"] or 0.0, "sibling_closes": sibling_closes})
    g["depth"] = depth(g["C"], g["A"], m, N)
    return g


def genre_summary(pool, cache, N, m, bands, sibling_closes=False):
    """pool: {mbid: set(bant)}; cache: {mbid: info}. K2 sayilari, sinirli kume, derinlik, teshis."""
    recs, unresolved = [], 0
    for mbid, bs in pool.items():
        info = cache.get(mbid)
        if not info or info.get("src") == "mb_404":
            unresolved += 1
            continue
        recs.append({"recording_mbid": mbid, "bands": sorted(bs), **info})

    def block(rs, name):
        return gate_block(rs, name, m, N, sibling_closes)

    out = {"pool": len(pool), "resolved": len(recs), "unresolved": unresolved,
           "isrcless_with_meta": sum(1 for r in recs if not r["isrcs"] and r.get("title") and r.get("artist")),
           "A_all_bands": block(recs, "A"),
           "B_top_mid": block([r for r in recs if set(r["bands"]) & {"top", "mid"}], "B"),
           "A_cap2": block(cap_per_artist(recs, 2), "A_cap2"),
           "per_band": {}}
    for b in bands:
        rs = [r for r in recs if b in r["bands"]]
        gb = gate_row(rs, b)
        out["per_band"][b] = {k: gb[k] for k in ("n", "C", "A", "rate", "ci", "top_share")}
    return out


def _count_pool(rep_lists):
    """rep_lists: [[mbid,...], ...] -> Counter (gorulme sayisi)."""
    c = Counter()
    for r in rep_lists:
        c.update(r)
    return c


def _report_tail(kind, rq, budget, store, token, errors, interrupted, extra):
    rep = {"meta": {"phase": kind, "used": dict(budget.used), "requests": sum(budget.used.values()),
                    "token": bool(token), "errors": errors, "errors_rate": round(errors / max(1, len(rq.log)), 4),
                    "phase_valid": errors / max(1, len(rq.log)) <= 0.10, "interrupted": interrupted,
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S")},
           "requests": rq.log, **extra}
    path = OUT / f"lb_probe2_{kind}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    safe_write(path, _scrub(json.dumps(rep, ensure_ascii=False, indent=1), token))
    print(f"istek: {rep['meta']['requests']} (LB {budget.used['lb']}, MB {budget.used['mb']}); hata={errors}; yazildi: {path}")
    return rep


def _tr_selection(args):
    wanted = _genre_filter(args)
    if args.scope == "nontr":
        return [g for g, _ in GENRES if g not in TR_GENRES and (wanted is None or g in wanted)]
    sel = [g for g in TR_GENRES if wanted is None or g in wanted]
    if wanted and set(wanted) - set(TR_GENRES):
        raise SystemExit("bu faz yalniz Turkce turleri isler (--genres Turkce adlari)")
    return sel


def _start(args, kind):
    store = Store(OUT, force_unlock=args.force_unlock)
    load_env()  # deger asla yazdirilmaz
    token = os.environ.get("LISTENBRAINZ_TOKEN") or None
    cap_lb, cap_mb = (NT_CAPS if args.scope == "nontr" else PHASE_CAPS)[kind]
    budget = Budget(lb=min(cap_lb, args.max_lb), mb=min(cap_mb, args.max_mb), lf=0)
    return store, token, budget, Requester(budget, token)


def run_tags(args):
    """T3-TR: takma ad basina LB top count=100 (n) + MB artist tag: (sayi, TR payi) -> kabul."""
    sel = _tr_selection(args)
    store, token, budget, rq = _start(args, "tags")
    res = store.state.setdefault("tags", {})
    errors, interrupted = 0, None
    nontr = args.scope == "nontr"
    print(f"tags: {sum(len(ALIAS_MAP[g]) for g in sel)} takma ad, butce LB<={budget.max['lb']} MB<={budget.max['mb']}")
    try:
        with store:
            for g in sel:
                for a in ALIAS_MAP[g]:
                    key = f"{g}|{a}"
                    if store.done("tags|" + key):
                        continue
                    c1, b1, r1 = rq.call_retry("tag_lb", "lb", "GET", f"{LB}/lb-radio/tags",
                                               {"tag": [a], "operator": "OR", "pop_begin": 0, "pop_end": 100, "count": 100})
                    if nontr:  # MB etiket aramasi Turkce disi turde gereksiz (TR payi anlamsiz): LB n>=20 yeter
                        c2, b2 = 200, {"artists": [], "count": 0}
                    else:
                        c2, b2, r2 = rq.call_retry("tag_mb", "mb", "GET", f"{MB}/artist",
                                                   {"query": f'tag:"{a}"', "limit": 100, "fmt": "json"})
                    if c1 != 200 or c2 != 200:
                        errors += 1
                        print(f"  {ascii_safe(key):<34} HATA lb={c1} mb={c2} (yeniden kosuda tekrarlanir)")
                        continue
                    recs = as_records(b1)
                    arts = b2.get("artists", []) if isinstance(b2, dict) else []
                    tr = sum(1 for x in arts if x.get("country") == "TR")
                    share = tr / len(arts) if arts else 0.0
                    mb_count = b2.get("count", len(arts)) if isinstance(b2, dict) else 0
                    ok = accept_alias(len(recs), mb_count, share, a in NOISY_ALIASES)
                    res[key] = {"genre": g, "alias": a, "lb_n": len(recs),
                                "lb_unique": len({r.get("recording_mbid") for r in recs if isinstance(r, dict)}),
                                "mb_artists": mb_count, "mb_page": len(arts), "mb_tr_share": round(share, 3),
                                "noisy": a in NOISY_ALIASES, "accepted": ok}
                    store.mark_done("tags|" + key)
                    store.flush()
                    print(f"  {ascii_safe(key):<34} lb_n={len(recs):>3} mb={mb_count:>4} TR={share:.2f} -> {'KABUL' if ok else 'ret'}")
    except (KeyboardInterrupt, BudgetExceeded) as e:
        interrupted = repr(e)
    accepted = {g: [v["alias"] for v in res.values() if v["genre"] == g and
                    accept_alias(v["lb_n"], v["mb_artists"], v["mb_tr_share"], v["noisy"])] for g in sel}
    print("kabul edilen:", {ascii_safe(g): [ascii_safe(x) for x in v] for g, v in accepted.items()})
    _report_tail("tags", rq, budget, store, token, errors, interrupted, {"aliases": res, "accepted": accepted})
    return 2 if interrupted else 0


def run_radio(args):
    """T1-TR: tur x bant, kabul edilen takma adlar OR, count=1000, en cok 3 cekim; ISRC LB metadata'dan."""
    sel = _tr_selection(args)
    tags_state = _load_json(OUT / "lb_probe2_state.json", {}).get("tags", {})
    accepted = {g: [v["alias"] for v in tags_state.values() if v["genre"] == g and
                    accept_alias(v["lb_n"], v["mb_artists"], v["mb_tr_share"], v["noisy"])] for g in sel}
    empty = [g for g in sel if not accepted[g]]
    if empty and args.scope == "nontr":
        print("kabul edilmis takma ad yok, atlandi (OLCULMEDI):", [ascii_safe(g) for g in empty])
        sel = [g for g in sel if g not in empty]
    elif empty:
        raise SystemExit(f"kabul edilmis takma ad yok: {empty}; once --phase tags")
    store, token, budget, rq = _start(args, "radio")
    raw = store.state.setdefault("radio_raw", {})
    errors, interrupted, lookup_left = 0, None, (0 if args.scope == "nontr" else LOOKUP_CAP)
    genres_out = {}
    print(f"radio: {len(sel)} tur, butce LB<={budget.max['lb']} MB<={budget.max['mb']}, N={args.session_size} m={args.artist_cap}")
    try:
        with store:
            for g in sel:
                tags = accepted[g]
                bands_out, pool, all_counts = {}, {}, Counter()
                for band, (lo, hi) in BANDS.items():
                    reps = []
                    while need_more_reps([set(r) for r in reps]):
                        unit = f"radio|{g}|{band}|{len(reps)}"
                        if store.done(unit):
                            reps.append([x[0] for x in raw[unit]])
                            continue
                        code, body, rec = rq.call_retry("radio", "lb", "GET", f"{LB}/lb-radio/tags",
                                                        {"tag": tags, "operator": "OR", "pop_begin": lo, "pop_end": hi,
                                                         "count": 1000})
                        if code != 200:
                            errors += 1
                            break
                        rs = [r for r in as_records(body) if isinstance(r, dict) and r.get("recording_mbid")]
                        raw[unit] = [[r["recording_mbid"], r.get("tag_count"), r.get("percent"), r.get("source")] for r in rs]
                        store.mark_done(unit)
                        store.flush()
                        reps.append([r["recording_mbid"] for r in rs])
                    cnt = _count_pool(reps)
                    for mb_ in cnt:
                        pool.setdefault(mb_, set()).add(band)
                    all_counts.update(cnt)
                    sets = [set(r) for r in reps]
                    bands_out[band] = {"reps": len(reps), "per_rep": [len(r) for r in reps],
                                       "unique_per_rep": [len(s) for s in sets], "union": len(cnt),
                                       "jaccard_1_2": round(jaccard(sets[0], sets[1]), 4) if len(sets) > 1 else None,
                                       "chao1": round(chao1(cnt), 1), "H": saturation(cnt) if len(reps) > 1 else None}
                    print(f"  {ascii_safe(g):<13}{band:<5} reps={len(reps)} per_rep={[len(r) for r in reps]} union={len(cnt)} "
                          f"jacc={bands_out[band]['jaccard_1_2']} chao1={bands_out[band]['chao1']}")
                if args.scope == "nontr" and len(pool) > args.resolve_cap:
                    rng = random.Random(f"{args.seed}|{g}")
                    keep = set(rng.sample(sorted(pool), args.resolve_cap))
                    store.state.setdefault("pool_size", {})[g] = len(pool)
                    pool = {k_: v_ for k_, v_ in pool.items() if k_ in keep}
                else:
                    store.state.setdefault("pool_size", {})[g] = len(pool)
                stats, lookup_left = resolve_mbids(rq, store, list(pool), lookup_left)
                store.flush()
                summ = genre_summary(pool, store.cache, args.session_size, args.artist_cap, list(BANDS))
                det = all(b["jaccard_1_2"] is not None and b["jaccard_1_2"] >= 0.99 for b in bands_out.values())
                genres_out[g] = {"aliases": tags, "bands": bands_out, "resolve": stats, "summary": summ,
                                 "chao1_genre": round(chao1(all_counts), 1), "S_genre": len(all_counts),
                                 "H_genre": None if det else saturation(all_counts), "deterministic": det}
                a = summ["A_all_bands"]
                print(f"  => {ascii_safe(g)}: pool={summ['pool']} cozulen={summ['resolved']} (lb_meta={stats['lb_meta']} "
                      f"rid={stats['mb_rid']} tekli={stats['mb_single']}) ISRC'li C={a['C']} A={a['A']} "
                      f"oran={a['rate']} D={a['depth']} verdict={a['verdict']} teshis={a['diagnose']}")
    except (KeyboardInterrupt, BudgetExceeded) as e:
        interrupted = repr(e)
    tr_rows = [{"genre": g, "tr": True, "verdict": v["summary"]["A_all_bands"]["verdict"]} for g, v in genres_out.items()]
    _report_tail("radio", rq, budget, store, token, errors, interrupted,
                 {"genres": genres_out, "depth": {g: v["summary"]["A_all_bands"]["depth"] for g, v in genres_out.items()},
                  "session_size": args.session_size, "artist_cap": args.artist_cap, "tr_rows": tr_rows})
    return 2 if interrupted else 0


# ---------------------------------------------------------------- D + E (G6)
# D: sanatci yolu = LB popularity/artist (K4 tertili) + top-recordings-for-artist + LB metadata (ISRC); MB browse yok.
# E: ISRC'siz kayit icin ayni sanatci + norm_title + surum isareti kardesinden ISRC (ek istek yok).

ARTISTS_PER_GENRE, NICHE_SHARE, CAND_LIMIT, POP_BATCH, CHUNK, NICHE_MIN_A = 40, 0.30, 400, 100, 10, 5
PHASE_CAPS["artist"] = (320, 100)
PHASE_BUDGET["artist"] = (320, 100, "D+E-TR: <=40 sanatci/tur (K4 tabakali), top-recordings + LB metadata; MB browse yok")


def select_artists(rel, tiers, k=ARTISTS_PER_GENRE, niche_share=NICHE_SHARE, seed=7):
    """K4 tabakali secim (populerlik kesigi yok): nis tertilden en az %niche_share, kalan orta/populer arasi
    yariya bolunur; eksik tabaka digerlerinden dolar. rel: {sanatci: ilgi}."""
    rng = random.Random(seed)
    tie = {a: rng.random() for a in rel}

    def ranked(t):
        return sorted((a for a in rel if tiers.get(a) == t), key=lambda a: (-rel[a], tie[a]))

    nis, orta, pop = ranked("nis"), ranked("orta"), ranked("populer")
    n_nis = min(len(nis), math.ceil(k * niche_share))
    rest = k - n_nis
    n_orta = min(len(orta), rest - rest // 2)
    n_pop = min(len(pop), rest - n_orta)
    chosen = nis[:n_nis] + orta[:n_orta] + pop[:n_pop]
    if len(chosen) < k:
        have = set(chosen)
        chosen += sorted((a for a in rel if a not in have), key=lambda a: (-rel[a], tie[a]))[:k - len(chosen)]
    return chosen


def sibling_close(recs):
    """recs: {recording_mbid, artist_mbid, title, isrcs} (taze API adlari). E adimi: ISRC'siz kayit icin kardes ISRC.
    Doner: isrcless, closed{mbid:(isrc,tur)}, closed_n, by_marker{isaret:sayi}, relaxed_marker_diff
    (ayni baslik, baska surum isareti: kabul edilmez), new_unique_isrc (havuzda olmayan yeni ISRC)."""
    by_artist = defaultdict(list)
    for r in recs:
        if r.get("artist_mbid") and r["artist_mbid"] != VARIOUS_ARTISTS:
            by_artist[r["artist_mbid"]].append({**r, "mbid": r["recording_mbid"]})
    closed, by_marker, relaxed, isrcless = {}, Counter(), 0, 0
    have_isrcs = {_first_isrc(r.get("isrcs")) for r in recs if r.get("isrcs")}
    for arts in by_artist.values():
        with_isrc = [b for b in arts if b.get("isrcs")]
        for r in arts:
            if r.get("isrcs"):
                continue
            isrcless += 1
            nt = norm_title(r.get("title"))
            if not nt or not with_isrc:
                continue
            isrc, kind = sibling_isrc(r, with_isrc)
            if isrc:
                closed[r["mbid"]] = (isrc, kind)
                by_marker[version_marker(r.get("title")) or "(isaret yok)"] += 1
            elif any(norm_title(b.get("title")) == nt for b in with_isrc):
                relaxed += 1
    return {"isrcless": isrcless, "closed": closed, "closed_n": len(closed), "by_marker": dict(by_marker),
            "relaxed_marker_diff": relaxed,
            "new_unique_isrc": len({i for i, _ in closed.values()} - have_isrcs)}


def _pool_recs(pool, cache):
    out = []
    for mbid, bs in pool.items():
        info = cache.get(mbid)
        if info and info.get("src") != "mb_404":
            out.append({"recording_mbid": mbid, "bands": sorted(bs), **info,
                        "artist_mbid": primary_artist(info, bs)})
    return out


def niche_count(recs, tiers):
    """K4: ISRC'li benzersiz sanatcilardan nis tertilde olanlarin sayisi."""
    arts = {r["artist_mbid"] for r in recs if r.get("isrcs") and r.get("artist_mbid")}
    return sum(1 for a in arts if tiers.get(a) == "nis")


def capped_c(recs, m):
    """Sanatci basina tavan m ile benzersiz ISRC sayisi (cap uygulanmis kullanilabilir ISRC'li kayit)."""
    per = defaultdict(set)
    for r in recs:
        if r.get("isrcs") and r.get("artist_mbid") and r["artist_mbid"] != VARIOUS_ARTISTS:
            per[r["artist_mbid"]].add(_first_isrc(r["isrcs"]))
    return sum(min(len(v), m) for v in per.values())


def de_summary(radio_pool, d_pool, cache, listens, N, m, excl=()):
    """T1 (radio) / D (sanatci yolu) / T1+D varyantlari + E kapanisi. listens: {sanatci: dinlenme};
    nis tertili yalniz dinlenmesi bilinen sanatcilar uzerinden hesaplanir."""
    merged = {k: set(v) for k, v in radio_pool.items()}
    for k, v in d_pool.items():
        merged.setdefault(k, set()).update(v)
    r_t1, r_d, r_u = (_pool_recs(p_, cache) for p_ in (radio_pool, d_pool, merged))
    if excl:  # G13: yabanci ulkeli / tur-disi sanatcilar (artist_excl) dislanir
        r_t1, r_d, r_u = ([r for r in rs if r.get("artist_mbid") not in excl] for rs in (r_t1, r_d, r_u))
    known = {r["artist_mbid"] for r in r_u if r.get("artist_mbid") in listens}
    tiers = pop_tier({a: listens[a] for a in known})
    e = sibling_close(r_u)
    n_u = len(r_u)
    with_isrc = sum(1 for r in r_u if r.get("isrcs"))
    rate_after = (with_isrc + e["closed_n"]) / n_u if n_u else 0.0
    closes = rate_after >= 0.60
    out = {"artists_with_tier": len(known)}
    for name, rs in (("T1", r_t1), ("D", r_d), ("T1+D", r_u)):
        b = gate_block(rs, name, m, N, sibling_closes=closes)
        b["A_niche"] = niche_count(rs, tiers)
        b["niche_full"] = b["A_niche"] >= NICHE_MIN_A
        b["C_capped_m"] = capped_c(rs, m)
        out[name] = b
    out["E"] = {**{k: v for k, v in e.items() if k != "closed"},
                "rate_before": round(with_isrc / n_u, 4) if n_u else None,
                "rate_after": round(rate_after, 4), "sibling_closes": closes,
                "C_unchanged": e["new_unique_isrc"] == 0}
    return out


WIDE_ALIASES = {  # G6b: ek takma adlar (T1 havuzunu degistirmez; yalniz D icin sanatci adayi)
    "turk halk": ["turkish folk", "turkish folk music", "türkü", "halk müziği", "türk halk müziği", "ozan", "aşık",
                  "bağlama", "alevi", "bektaşi", "anatolian folk", "turkish traditional"],
    "turkce rap": ["turkish hip hop", "turkish rap", "turkish hip-hop", "türkçe rap", "turkish trap", "turkish drill"],
}
# G6c (son deneme): halk icin ek takma adlar + arabesk komsulari
WIDE_ALIASES["turk halk"] += ["saz", "halk ozanı", "uzun hava", "bozlak", "zeybek", "alevi deyiş", "deyiş"]
WIDE_ALIASES["arabesk"] = ["arabesk", "fantezi", "arabesk pop", "arabesque", "türk sanat müziği", "turkish classical",
                           "turkish arabesque", "türk özgün müziği"]
# LB lb-radio/tags operator=AND kombinasyonlari (T1 havuzuna "and-..." bandiyla eklenir, radio_raw'a yazilir)
AND_PAIRS = {"turk halk": [["turkish", "folk"], ["anatolian", "folk"], ["turkish", "traditional"], ["turkish", "saz"],
                           ["turkish", "türkü"], ["turkish", "alevi"]]}


def wide_candidates(entries):
    """MB artist aramasi satirlari [[id, country], ...] -> ({id: agirlik}, haric_sayisi).
    TR 0.5, ulkesi bos 0.3; baska ulke haric (Turk etiketli yabanci sanatci gurultusu)."""
    out, excluded = {}, 0
    for aid, country in entries:
        if country == "TR":
            out[aid] = max(out.get(aid, 0), 0.5)
        elif not country:
            out.setdefault(aid, 0.3)
        else:
            excluded += 1
    return out, excluded


def _prev_artist_report():
    """Onceki kapi raporundan {tur: {C, A, top_share, verdict, best}} ('once' degerleri)."""
    fs = sorted(OUT.glob("lb_probe2_gate_2*.json"))
    rows = _load_json(fs[-1], {}).get("genres", []) if fs else []
    return {r["genre"]: {k: r.get(k) for k in ("best", "C", "A", "top_share", "verdict", "isrc_rate_record")}
            for r in rows if r.get("best")}


def run_artist(args):
    wide = bool(getattr(args, "wide", False))
    if wide and not args.genres:
        args.genres = "turk halk,turkce rap"
    sel = _tr_selection(args)
    store, token, budget, rq = _start(args, "artist")
    cache = store.cache
    tags_state, raw = store.state.get("tags", {}), store.state.get("radio_raw", {})
    accepted = {g: [v["alias"] for v in tags_state.values() if v["genre"] == g and
                    accept_alias(v["lb_n"], v["mb_artists"], v["mb_tr_share"], v["noisy"])] for g in sel}
    radio_pool = {g: {} for g in sel}
    for unit, rows in raw.items():
        parts = unit.split("|")
        if len(parts) == 4 and parts[1] in radio_pool:
            for r in rows:
                radio_pool[parts[1]].setdefault(r[0], set()).add(parts[2])
    nontr = args.scope == "nontr"
    empty = [g for g in sel if not radio_pool[g] or not accepted[g]]
    if empty and nontr:
        print("radio/tags verisi yok, atlandi:", [ascii_safe(g) for g in empty])
        sel = [g for g in sel if g not in empty]
    elif empty:
        raise SystemExit(f"radio/tags verisi yok: {empty}; once --phase tags ve --phase radio")
    tagart = store.state.setdefault("tagartists_wide" if wide else "tagartists", {})
    apop = store.state.setdefault("artist_pop", {})
    toprec = store.state.setdefault("toprec", {})
    chosen = store.state.setdefault("artist_sel_wide" if wide else "artist_sel", {})
    k_art = args.artists_per_genre or (80 if wide else (30 if nontr else ARTISTS_PER_GENRE))
    prev = _prev_artist_report() if wide else {}
    wide_info, skipped_d = {}, []
    top_k, errors, interrupted, lookup_left = args.top_k, 0, None, (0 if nontr else LOOKUP_CAP)
    growth, genres_out = [], {}
    t_phase = time.monotonic()
    print(f"artist: {len(sel)} tur, butce LB<={budget.max['lb']} MB<={budget.max['mb']}, top_k={top_k}, "
          f"N={args.session_size} m={args.artist_cap}")

    def spent():
        return sum(budget.used.values())

    try:
        with store:
            # 1) MB etiket aramasi: kabul edilen takma adlarin TR sanatcilari (K4: nis sanatcilar da gelsin)
            for g in sel:
                if wide:  # LB AND kombinasyonlari: T1 havuzunu genisletir
                    for pair in AND_PAIRS.get(g, []):
                        unit = f"radio|{g}|and-{'+'.join(pair)}|0"
                        if unit not in raw:
                            code, body, _ = rq.call_retry("radio_and", "lb", "GET", f"{LB}/lb-radio/tags",
                                                          {"tag": pair, "operator": "AND", "pop_begin": 0, "pop_end": 100,
                                                           "count": 1000})
                            if code != 200:
                                errors += 1
                                continue
                            rs_ = [r for r in as_records(body) if isinstance(r, dict) and r.get("recording_mbid")]
                            raw[unit] = [[r["recording_mbid"], r.get("tag_count"), r.get("percent"), r.get("source")] for r in rs_]
                            store.mark_done(unit)
                        for r in raw[unit]:
                            radio_pool[g].setdefault(r[0], set()).add("and")
                    _, lookup_left = resolve_mbids(rq, store, [m_ for m_ in radio_pool[g] if m_ not in cache], lookup_left)
                    store.flush()
                if nontr:
                    break
                for a in (WIDE_ALIASES[g] if wide else accepted[g]):
                    if a in tagart:
                        continue
                    if not wide:
                        code, body, _ = rq.call_retry("tagsearch", "mb", "GET", f"{MB}/artist",
                                                      {"query": f'tag:"{a}"', "limit": 100, "fmt": "json"})
                        if code == 200 and isinstance(body, dict):
                            tagart[a] = [x["id"] for x in body.get("artists", []) if x.get("country") == "TR" and x.get("id")]
                        else:
                            errors += 1
                        continue
                    rows, ok = [], True
                    for pg in range(args.tag_pages):
                        code, body, _ = rq.call_retry("tagsearch", "mb", "GET", f"{MB}/artist",
                                                      {"query": f'tag:"{a}"', "limit": 100, "offset": 100 * pg, "fmt": "json"})
                        if code != 200 or not isinstance(body, dict):
                            errors += 1
                            ok = False
                            break
                        arts_ = body.get("artists", [])
                        rows += [[x["id"], x.get("country")] for x in arts_ if x.get("id")]
                        if len(arts_) < 100 or 100 * (pg + 1) >= body.get("count", 0):
                            break
                    if ok:
                        tagart[a] = rows
            store.flush()
            for g in sel:
                t_g, req_g = time.monotonic(), spent()
                if nontr:  # E2: T1 acikca geciyorsa (C>=40 ve A>=25) D atlanir
                    t1g = gate_row(_pool_recs(radio_pool[g], cache), "T1")
                    if t1g["C"] >= 40 and t1g["A"] >= 25:
                        skipped_d.append(g)
                        chosen[g] = []
                rel = Counter(cache[m_]["artist_mbid"] for m_ in radio_pool[g]
                              if cache.get(m_) and cache[m_].get("artist_mbid") and cache[m_].get("src") != "mb_404")
                rel = {a: float(n) for a, n in rel.items() if a != VARIOUS_ARTISTS}
                if wide:
                    ex_total = 0
                    for a in WIDE_ALIASES[g]:
                        w_, ex_ = wide_candidates(tagart.get(a, []))
                        ex_total += ex_
                        for x, wt in w_.items():
                            rel[x] = max(rel.get(x, 0), wt)
                    wide_info[g] = {"aliases": len(WIDE_ALIASES[g]),
                                    "alias_rows": {a: len(tagart.get(a, [])) for a in WIDE_ALIASES[g]},
                                    "cands_total": len(rel), "excluded_nonTR": ex_total}
                else:
                    for a in accepted[g]:
                        for x in tagart.get(a, []):
                            rel.setdefault(x, 0.5)
                cands = dict(sorted(rel.items(), key=lambda kv: (-kv[1], kv[0]))[:CAND_LIMIT])
                todo = [] if g in skipped_d else [a for a in cands if a not in apop]
                for i in range(0, len(todo), POP_BATCH):
                    chunk = todo[i:i + POP_BATCH]
                    code, body, _ = rq.call_retry("pop_artist", "lb", "POST", f"{LB}/popularity/artist",
                                                  post={"artist_mbids": chunk}, use_token=True)
                    if code == 200 and isinstance(body, list):
                        got = {x.get("artist_mbid"): int(x.get("total_listen_count") or 0)
                               for x in body if isinstance(x, dict)}
                        for a in chunk:
                            apop[a] = got.get(a, 0)
                    else:
                        errors += 1
                store.flush()
                listens = {a: apop[a] for a in cands if a in apop}
                tiers = pop_tier(listens)
                if g not in chosen or wide:
                    chosen[g] = select_artists({a: cands[a] for a in listens}, tiers, k_art,
                                               NICHE_SHARE, args.seed)
                d_pool = {}
                for i in range(0, len(chosen[g]), CHUNK):
                    new_mbids = []
                    for a in chosen[g][i:i + CHUNK]:
                        if a not in toprec:
                            code, body, _ = rq.call_retry("toprec", "lb", "GET",
                                                          f"{LB}/popularity/top-recordings-for-artist/{a}", use_token=True)
                            if code == 200 and isinstance(body, list):
                                rows = sorted((x for x in body if isinstance(x, dict) and x.get("recording_mbid")),
                                              key=lambda x: -(x.get("total_listen_count") or 0))[:top_k]
                                toprec[a] = [[x["recording_mbid"], x.get("total_listen_count") or 0] for x in rows]
                            elif code == 404:
                                toprec[a] = []
                            else:
                                errors += 1
                                continue
                        new_mbids += [x[0] for x in toprec[a]]
                    for m_ in new_mbids:
                        d_pool.setdefault(m_, set()).add("D")
                    _, lookup_left = resolve_mbids(rq, store, new_mbids, lookup_left)
                    store.flush()
                    union = {**{k: set(v) for k, v in radio_pool[g].items()}}
                    for k, v in d_pool.items():
                        union.setdefault(k, set()).update(v)
                    for strat, rs in (("D", _pool_recs(d_pool, cache)), ("T1+D", _pool_recs(union, cache))):
                        gr = gate_row(rs, strat)
                        growth.append({"genre": g, **growth_point(strat, spent() - req_g, time.monotonic() - t_g,
                                                                  gr["C"], gr["A"], niche_count(rs, tiers))})
                res = de_summary(radio_pool[g], d_pool, cache, listens, args.session_size, args.artist_cap)
                res.update({"d_skipped_e2": g in skipped_d, "wide": wide_info.get(g),
                            "before": prev.get(g) if wide else None,
                            "artists_selected": len(chosen[g]), "artists_cands": len(cands),
                            "tier_of_selected": dict(Counter(tiers.get(a) for a in chosen[g])),
                            "toprec_empty": sum(1 for a in chosen[g] if not toprec.get(a)),
                            "d_pool": len(d_pool)})
                genres_out[g] = res
                t1, d_, u, e = res["T1"], res["D"], res["T1+D"], res["E"]
                print(f"  {ascii_safe(g):<13} T1 C={t1['C']} A={t1['A']} -> T1+D C={u['C']} A={u['A']} A_nis={u['A_niche']} "
                      f"oran={u['rate'] or 0:.3f} D={t1['depth']}->{u['depth']} {ascii_safe(u['verdict'])} | "
                      f"D-only C={d_['C']} A={d_['A']} | E kapanan={e['closed_n']}/{e['isrcless']} "
                      f"yeni_ISRC={e['new_unique_isrc']} kapatir={e['sibling_closes']}")
    except (KeyboardInterrupt, BudgetExceeded) as e_:
        interrupted = repr(e_)
    h_radio = {}
    for f_ in sorted(OUT.glob("lb_probe2_radio_*.json")):
        h_radio.update({g: v.get("H_genre") for g, v in _load_json(f_, {}).get("genres", {}).items()})
    sec_total = time.monotonic() - t_phase
    ranking = []
    for strat in ("T1", "D", "T1+D"):
        rows = [{"genre": g, "tr": True, "verdict": v[strat]["verdict"], "D": v[strat]["depth"],
                 "niche_full": v[strat]["niche_full"], "H": h_radio.get(g)} for g, v in genres_out.items()]
        pts = [{"C": sum(v[strat]["C"] for v in genres_out.values()), "sec": None if strat == "T1" else sec_total}]
        ranking.append({"strategy": strat, "rows": rows, "points": pts})
    strategy_rank = rank_strategies(ranking) if genres_out else []
    _report_tail("artist_wide" if wide else "artist", rq, budget, store, token, errors, interrupted,
                 {"scope": args.scope, "d_skipped_e2": skipped_d, "genres": genres_out, "growth": growth, "strategy_rank": strategy_rank,
                  "session_size": args.session_size, "artist_cap": args.artist_cap, "top_k": top_k})
    return 2 if interrupted else 0


# ---------------------------------------------------------------- Kapi raporu (G7): istek yok
MAX_TOP_SHARE = 0.30  # K2 nesnel olcut: en buyuk sanatci payi <= %30


def final_verdict(b, sampled_pop=None, has_d=False):
    """b: gate_block ciktisi. Doner (verdict, nedenler). top_share > %30 kapiyi dusurur; ornekleme (T1 yalniz) ile
    C<20 ama Wilson ust sinirindan extrapole C>=20 ise SINIRDA."""
    if not b.get("n"):
        return "ÖLÇÜLMEDİ", ["veri yok"]
    why = []
    if b["C"] < GATE_C:
        why.append(f"C={b['C']}<{GATE_C}")
    if b["A"] < GATE_A:
        why.append(f"A={b['A']}<{GATE_A}")
    if b["C"] >= GATE_C and b["A"] >= GATE_A and (b.get("top_share") or 0) > MAX_TOP_SHARE:
        why.append(f"en buyuk sanatci payi {b['top_share']:.2f}>{MAX_TOP_SHARE:.2f}")
    if not why:
        return "GEÇTİ", []
    if (sampled_pop and not has_d and b["C"] < GATE_C and b["A"] >= GATE_A and b.get("ci")
            and sampled_pop * b["ci"][1] >= GATE_C):
        return "SINIRDA", why
    return "KALDI", why


def build_gate(state, cache, h_radio, N, m):
    raw, psize = state.get("radio_raw", {}), state.get("pool_size", {})
    apop, toprec = state.get("artist_pop", {}), state.get("toprec", {})
    pools = {}
    for unit, rows in raw.items():
        parts = unit.split("|")
        if len(parts) == 4:
            for r in rows:
                pools.setdefault(parts[1], {}).setdefault(r[0], set()).add(parts[2])
    sel = {}
    for key in ("artist_sel", "artist_sel_wide"):
        for g, arts in state.get(key, {}).items():
            sel.setdefault(g, [])
            sel[g] += [a for a in arts if a not in sel[g]]
    rows_out, variants = [], {"T1": [], "D": [], "T1+D": []}
    for g, _ in GENRES:
        tr = g in TR_GENRES
        radio_pool = pools.get(g)
        if not radio_pool:
            rows_out.append({"genre": g, "tr": tr, "verdict": "ÖLÇÜLMEDİ", "reasons": ["takma ad kabul edilmedi ya da T1 verisi yok"],
                             "best": None, "D": 0})
            for v in variants:
                variants[v].append({"genre": g, "tr": tr, "verdict": "ÖLÇÜLMEDİ", "D": 0, "niche_full": False, "H": None})
            continue
        d_pool = {}
        for a in sel.get(g, []):
            for mb_, _n in toprec.get(a, []):
                d_pool.setdefault(mb_, set()).update(("D", "D@" + a))
        res = de_summary(radio_pool, d_pool, cache, apop, N, m, excl=set(state.get("artist_excl", {}).get(g, [])))
        has_d = bool(d_pool)
        best = "T1+D" if has_d else "T1"
        b = res[best]
        size = psize.get(g, len(radio_pool))
        sampled = size if res["T1"]["n"] < size else None
        verdict, why = final_verdict(b, sampled, has_d)
        h = h_radio.get(g)
        rows_out.append({
            "genre": g, "tr": tr, "best": best, "verdict": verdict, "reasons": why, "pool": size,
            "resolved_t1": res["T1"]["n"], "sampled": bool(sampled), "d_ran": has_d,
            "n": b["n"], "C": b["C"], "A": b["A"], "C_capped_m": b["C_capped_m"], "top_share": b["top_share"],
            "isrc_rate_record": b["rate"], "ci": b["ci"], "isrc_rate_artist": b["isrc_rate_artist"],
            "A_niche": b["A_niche"] if (b["A_niche"] or has_d) else None, "D": b["depth"], "diagnose": b["diagnose"],
            "T1": {k: res["T1"][k] for k in ("n", "C", "A", "verdict", "depth")},
            "T1+D": {k: res["T1+D"][k] for k in ("n", "C", "A", "verdict", "depth")} if has_d else None,
            "E": {k: res["E"][k] for k in ("isrcless", "closed_n", "by_marker", "rate_before", "rate_after")},
            "H": h})
        for v in variants:
            vb = res[v]
            variants[v].append({"genre": g, "tr": tr,
                                "verdict": vb["verdict"] if (v != "T1+D" or has_d) and (v != "D" or has_d) else "ÖLÇÜLMEDİ",
                                "D": vb["depth"] if (v == "T1" or has_d) else 0,
                                "niche_full": bool(vb["niche_full"]) and (v == "T1" or has_d), "H": h})
    gate_rows = [{"genre": r["genre"], "tr": r["tr"], "verdict": r["verdict"]} for r in rows_out]
    pg = program_gate(gate_rows)
    ranking = rank_strategies([{"strategy": v, "rows": variants[v], "points": []} for v in variants])
    return rows_out, pg, ranking


def request_totals(out_dir):
    """Tum faz raporlarindaki (offline/gate haric) meta.requests toplami; faz basina LB/MB."""
    per, total = {}, {"lb": 0, "mb": 0, "lf": 0, "files": 0}
    for f in sorted(Path(out_dir).glob("lb_probe2_*_2*.json")):
        name = f.name[len("lb_probe2_"):]
        phase = name.rsplit("_", 2)[0]
        if phase in ("offline", "gate"):
            continue
        meta = _load_json(f, {}).get("meta", {})
        used = meta.get("used") or {}
        d = per.setdefault(phase, {"lb": 0, "mb": 0, "files": 0})
        d["lb"] += used.get("lb", 0)
        d["mb"] += used.get("mb", 0)
        d["files"] += 1
        total["lb"] += used.get("lb", 0)
        total["mb"] += used.get("mb", 0)
        total["files"] += 1
    total["requests"] = total["lb"] + total["mb"]
    return per, total


def gate_markdown(rows, pg, ranking, per, total, N, m, halk_dil=None, a_duz=None):
    L = ["# PR-0 kapi raporu (lb_genre_probe2, G7)", "",
         f"Program kapisi: **{pg['verdict']}** (robust={pg['robust']}); Turkce gecen: {pg['tr_pass'][0]}/5 "
         f"(iyimser {pg['tr_pass'][1]}); Turkce disi gecen: {pg['nontr_pass'][0]}/15 (iyimser {pg['nontr_pass'][1]}); "
         f"toplam gecen: {pg['tr_pass'][0] + pg['nontr_pass'][0]}/20, esik >=16.",
         f"Oturum N={N}, sanatci tavani m={m}. Kayit sayilari ISRC'li benzersiz kayit (C) ve sanatci (A); "
         "ornekli turlerde C alt sinirdir.", "",
         "| Tur | TR | Varyant | Karar | C | A | pay | oran [Wilson] | A_nis | D(g) | Teshis | Neden |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["best"] is None:
            L.append(f"| {r['genre']} | {'E' if r['tr'] else 'H'} | - | {r['verdict']} | - | - | - | - | - | 0 | - | {'; '.join(r['reasons'])} |")
            continue
        ci = r["ci"]
        L.append(f"| {r['genre']} | {'E' if r['tr'] else 'H'} | {r['best']}{'*' if r['sampled'] else ''} | {r['verdict']} | {r['C']} | {r['A']} | "
                 f"{r['top_share']:.2f} | {(r['isrc_rate_record'] or 0):.3f} [{ci[0]:.3f}-{ci[1]:.3f}] | "
                 f"{'-' if r['A_niche'] is None else r['A_niche']} | {r['D']} | {r['diagnose']} | {'; '.join(r['reasons'])} |")
    L += ["", "`*` = T1 havuzundan seed'li rastgele ornek cozuldu (C alt sinir); SINIRDA = Wilson ust sinirindan extrapole C>=20.", "",
          "## Strateji sirasi (K3 feed_score)", "",
          "| Sira | Strateji | skor (kapi, min D TR, TR toplam D, nis dolu, H, aday/sn) |", "|---|---|---|"]
    for s in ranking:
        L.append(f"| {s['rank']} | {s['strategy']} | {tuple(round(x, 3) if isinstance(x, float) else x for x in s['score'])} |")
    if halk_dil:
        h = halk_dil
        L += ["", "## Halk kayit duzeyi dil kapisi (surum dili + sanatci izin listesi; esikler ayni)", "",
              f"ISRC'li kayit {h['records']}; siniflar {h['classes']}; **dil uyusmazligi orani {h['mismatch_rate']}** "
              f"(yabanci/(tur+izin+yabanci); yalniz dili bilinen: {h['mismatch_rate_lang_known']}); belirsiz (sayiya katilmaz) {h['undetermined']}.",
              f"Dil-duzeltmeli C={h['C']} A={h['A']} pay={h['top_share']} -> **{'GECTI' if h['pass'] else 'KALDI'}** "
              f"(esik C>={GATE_C}, A>={GATE_A}, pay<={MAX_TOP_SHARE}); izin listesi {h['allow_artists']} sanatci."]
    if a_duz:
        L += ["", "## A_duz (sanatci duzeyi uygun orani) ve program kapisi: nokta | alt uc (Wilson)", "",
              "| Tur | A | oran | A_duz [Wilson] | nokta | alt uc | kayit duzeyi uygun |", "|---|---|---|---|---|---|---|"]
        for g, v in a_duz["per_genre"].items():
            if "ci" not in v:
                L.append(f"| {g} | {v['A']} | - | - | {v['point']} | {v['lower']} | {v['note']} |")
                continue
            k = v["kayit"]
            L.append(f"| {g} | {v['A']} | {v['rate']} | {v['A_corr']} [{v['ci'][0]}-{v['ci'][1]}] | {'evet' if v['point'] else 'hayir'} | "
                     f"{'evet' if v['lower'] else 'hayir'} | {k['ok']}/{k['n']} = {k['rate']} |")
        pt, lo = a_duz["point"], a_duz["lower"]
        L += ["", f"Program kapisi (A_duz **nokta**): Turkce {pt['tr']}/5, toplam {pt['total']}/20 -> "
                  f"{'GECTI' if pt['tr'] == 5 and pt['total'] >= 16 else 'KALDI'}",
              f"Program kapisi (A_duz **alt uc**): Turkce {lo['tr']}/5, toplam {lo['total']}/20 -> "
              f"{'GECTI' if lo['tr'] == 5 and lo['total'] >= 16 else 'KALDI'} (Turkce 5/5 ve toplam >=16 gerekir)"]
    L += ["", "## Istek sayilari (faz raporlari toplami; loglu)", "", "| Faz | rapor | LB | MB |", "|---|---|---|---|"]
    for ph, d in sorted(per.items()):
        L.append(f"| {ph} | {d['files']} | {d['lb']} | {d['mb']} |")
    L.append(f"| **toplam** | {total['files']} | {total['lb']} | {total['mb']} |  (= {total['requests']} istek; Deezer 0, Last.fm 0; "
             "loglanmamis elle kesif sorgulari ayrica ~4)")
    return "\n".join(L) + "\n"


def _with_base(rows, state, cache):
    """anadolu rock: A_duz tabani = isaret dislamasi oncesi havuz (yontem: oran, v2+v3 isaretli sanatcilardan; ayni havuza uygulanir)."""
    out = []
    for r in rows:
        r = dict(r)
        if r["genre"] in ("anadolu rock", "arabesk") and state.get({"arabesk": "arabeskx"}.get(r["genre"], "rockx")):
            r["A_duz_base"] = a_pre_mark(state, cache, r["genre"])
        out.append(r)
    return out


def run_gate(args):
    state = _load_json(OUT / "lb_probe2_state.json", {})
    cache = _load_json(OUT / "lb_probe2_cache.json", {})
    h_radio = {}
    for f in sorted(OUT.glob("lb_probe2_radio_*.json")):
        h_radio.update({g: v.get("H_genre") for g, v in _load_json(f, {}).get("genres", {}).items()})
    rows, pg, ranking = build_gate(state, cache, h_radio, args.session_size, args.artist_cap)
    per, total = request_totals(OUT)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    rep = {"meta": {"phase": "gate", "requests": 0, "used": {"lb": 0, "mb": 0, "lf": 0}, "ts": stamp,
                    "session_size": args.session_size, "artist_cap": args.artist_cap},
           "program_gate": pg, "genres": rows, "strategy_rank": ranking,
           "halk_dil": halk_lang_report(state, cache),
           "a_duz": a_duz_summary(_with_base(rows, state, cache),
                                  {g: chr(10).join((OUT / x).read_text(encoding="utf-8") for x in ((f,) if isinstance(f, str) else f)
                                                   if (OUT / x).exists()) for g, f in A_DUZ_FILES.items()}),
           "requests_total": {"per_phase": per, **total}}
    safe_write(OUT / f"lb_probe2_gate_{stamp}.json", json.dumps(rep, ensure_ascii=False, indent=1))
    md = gate_markdown(rows, pg, ranking, per, total, args.session_size, args.artist_cap, rep["halk_dil"], rep["a_duz"])
    safe_write(OUT / f"lb_probe2_gate_{stamp}.md", md)
    print(ascii_safe(md))
    print(f"yazildi: lb_probe2_gate_{stamp}.json / .md")
    return 0


# ---------------------------------------------------------------- A_duz ozeti (G16): nokta ve alt uc program kapisi
A_DUZ_FILES = {"turk halk": "lb_sample_tr_turk_halk_v2.md", "turkce rap": "lb_sample_tr_turkce_rap_v2.md",
               "arabesk": ("lb_sample_tr_arabesk_v3.md", "lb_sample_tr_arabesk_v4.md"), "anadolu rock": ("lb_sample_tr_anadolu_rock_v2.md", "lb_sample_tr_anadolu_rock_v3.md"),
               "turkce pop": "lb_sample_tr_turkce_pop.md"}


def a_pre_mark(state, cache, g):
    """Isaret dislamasi oncesi (yalniz MB ulke dislamasi uygulanmis) havuzun sanatci sayisi: A_duz'un tahmin tabani.
    Isaretli sanatci orani bu genis havuzdan cekildigi icin oran, ayni havuza uygulanir (isaretle temizlenmis havuza degil)."""
    meta = state.get("artist_meta", {})
    ctry = compute_excl({a: meta[a] for a in pool_artists(state, cache, g) if a in meta}, g)
    st2 = {**state, "artist_excl": {**state.get("artist_excl", {}), g: sorted(ctry)}}
    return len({r["artist_mbid"] for r in isrcd_recs(st2, cache, g)[0]})


def a_duz_summary(rows, texts):
    """rows: gate tur satirlari; texts: {tur: isaretli md}. Nokta = A x oran >= A esigi; alt uc = A x Wilson alt >= esik.
    Ham kapiyi gecen ve ornegi olmayan turler ham sonucla sayilir. Doner: per-tur + 'Turkce k/5, toplam n/20' iki surum."""
    res = evaluate_samples(texts, {r["genre"]: r.get("A_duz_base") or r.get("A") or 0 for r in rows})
    per, tr_pt, tr_lo, other = {}, 0, 0, 0
    for r in rows:
        g = r["genre"]
        passed = r["verdict"] == "GEÇTİ"
        corr = (res.get(g) or {}).get("A_correction")
        if r["tr"]:
            if corr:
                pt, lo = corr["A_corr"] >= GATE_A, corr["passes_A15"]
                per[g] = {"A": corr["A"], "rate": corr["rate"], "A_corr": corr["A_corr"], "ci": corr["A_corr_ci"],
                          "point": pt, "lower": lo, "kayit": res[g]["rates"]["kayit"]["genel"]}
            else:
                pt = lo = passed
                per[g] = {"A": r.get("A"), "point": pt, "lower": lo, "note": "ornek yok; ham"}
            tr_pt += bool(pt and passed)
            tr_lo += bool(lo and passed)
        else:
            other += passed
    return {"per_genre": per, "point": {"tr": tr_pt, "total": tr_pt + other}, "lower": {"tr": tr_lo, "total": tr_lo + other},
            "gate_total_min": 16}


# ---------------------------------------------------------------- Elle ornekleme (istek yok)
# V9: konu disi denetimi icin T1+D ISRC'li havuzdan tohumlu ornek; kullanici isaretler, sonra sample_eval okur.

SAMPLE_GENRES = ["turk halk", "turkce rap", "arabesk"]
SAMPLE_N_REC, SAMPLE_N_ART = 40, 25
_MARK_RE = re.compile(r"^\[( |x|X)\]$")


def sample_pools(state, g):
    """-> (normal_radio, and_pool, d_pool): MBID kumeleri. 'and-' bantlari AND, digerleri etiket (OR) havuzudur."""
    normal, andp = set(), set()
    for unit, rows in state.get("radio_raw", {}).items():
        parts = unit.split("|")
        if len(parts) == 4 and parts[1] == g:
            (andp if parts[2].startswith("and-") else normal).update(r[0] for r in rows)
    d = {}
    for key in ("artist_sel", "artist_sel_wide"):
        for a in state.get(key, {}).get(g, []):
            for mb_, _n in state.get("toprec", {}).get(a, []):
                d.setdefault(mb_, a)
    return normal, andp, d  # d: {kayit: tohum sanatci}; 'in' ile kume gibi kullanilir


def source_of(mbid, normal, andp, dset):
    """Kayit kaynagi: yalniz AND havuzunda -> 'AND'; etiket (OR) havuzunda -> 'etiket'; yalniz sanatci yolunda -> 'D-sanatci'."""
    if mbid in normal:
        return "etiket"
    if mbid in andp:
        return "AND"
    return "D-sanatci" if mbid in dset else "?"


def isrcd_recs(state, cache, g):
    """T1+D ISRC'li, dislanmamis kayitlar (birincil sanatci atfiyla) + (normal, and, d) havuzlari."""
    normal, andp, dset = sample_pools(state, g)
    union = sorted(normal | andp | set(dset))
    excl = set(state.get("artist_excl", {}).get(g, []))
    recs = []
    for m_ in union:
        info = cache.get(m_)
        if info and info.get("src") != "mb_404" and info.get("isrcs") and info.get("artist_mbid") \
                and info["artist_mbid"] != VARIOUS_ARTISTS:
            prim = primary_artist(info, {"D@" + dset[m_]} if m_ in dset else ())
            if prim in excl or prim == VARIOUS_ARTISTS:
                continue
            recs.append({"mbid": m_, **{**info, "artist_mbid": prim}, "source": source_of(m_, normal, andp, dset)})
    return recs, normal, andp, dset


def build_sample(state, cache, g, n_rec=SAMPLE_N_REC, n_art=SAMPLE_N_ART, seed=7, max_per_art=0, only=None, skip=()):
    recs, normal, andp, dset = isrcd_recs(state, cache, g)
    if only is not None:  # yalniz verilen sanatcilar (ve skip disindakiler)
        recs = [r for r in recs if r["artist_mbid"] in only and r["artist_mbid"] not in skip]
    apop = state.get("artist_pop", {})
    arts_all = sorted({r["artist_mbid"] for r in recs})
    tiers = pop_tier({a: apop[a] for a in arts_all if a in apop})
    rng = random.Random(f"{seed}|sample|{g}")
    rec_s = rng.sample(recs, min(n_rec, len(recs)))
    if max_per_art:  # cesitlilik: ayni tohumlu karistirmadan sanatci basina en cok max_per_art kayit
        cnt, rec_s = Counter(), []
        for r in rng.sample(recs, len(recs)):
            if cnt[r["artist_mbid"]] < max_per_art and len(rec_s) < n_rec:
                cnt[r["artist_mbid"]] += 1
                rec_s.append(r)
    for r in rec_s:
        r["tier"] = tiers.get(r["artist_mbid"], "bilinmiyor")
    by_art = defaultdict(list)
    for r in recs:
        by_art[r["artist_mbid"]].append(r)
    toprec = state.get("toprec", {})
    arts_s = []
    for a in rng.sample(arts_all, min(n_art, len(arts_all))):
        best = None
        for mb_, _n in toprec.get(a, []):  # toprec dinlenmeye gore azalan
            info = cache.get(mb_)
            if info and info.get("isrcs") and info.get("src") != "mb_404":
                best = {"mbid": mb_, **info}
                break
        if best is None:
            best = {k: v for k, v in sorted(by_art[a], key=lambda r: r["mbid"])[0].items() if k != "source"}
        srcs = {r["source"] for r in by_art[a]}
        src = "etiket" if "etiket" in srcs else ("AND" if "AND" in srcs else "D-sanatci")
        arts_s.append({**best, "artist_mbid": a, "source": src, "tier": tiers.get(a, "bilinmiyor")})
    return {"genre": g, "records": rec_s, "artists": arts_s, "isrcd_records": len(recs), "isrcd_artists": len(arts_all)}


def _cell(s):
    return str(s if s is not None else "").replace("|", "/").replace("\n", " ").strip()


def sample_markdown(data):
    g = data["genre"]
    L = [f"# Elle ornekleme: {g}", "",
         "Talimat: **uygun = bu tur ve Turkce sarki.** Her satirda isaret kutusunu `[ ]` (uygun) birakin, uygun degilse `[x]` yapin. "
         "Baska sutunlari degistirmeyin. Isaretledikten sonra `python spikes/lb_genre_probe2.py --phase sample_eval` isabet oranini ve "
         "A duzeltmesini hesaplar.",
         "Kaynak: `AND` = yalniz lb-radio AND etiket birlesiminden, `etiket` = lb-radio OR (takma adlar), `D-sanatci` = sanatcinin en cok dinlenen kayitlari.",
         f"Havuz: ISRC'li {data['isrcd_records']} kayit, {data['isrcd_artists']} sanatci (T1+D). Orneklem tohumludur.", "",
         f"## Kayit duzeyi ({len(data['records'])} kayit)", "",
         "| # | isaret | sanatci | baslik | kaynak | tertil | mbid |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(data["records"], 1):
        L.append(f"| {i} | [ ] | {_cell(r.get('artist'))} | {_cell(r.get('title'))} | {r['source']} | {r['tier']} | {r['mbid']} |")
    L += ["", f"## Sanatci duzeyi ({len(data['artists'])} sanatci, her biri icin en cok dinlenen ISRC'li kayit)", "",
          "| # | isaret | sanatci | baslik | kaynak | tertil | mbid |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(data["artists"], 1):
        L.append(f"| {i} | [ ] | {_cell(r.get('artist'))} | {_cell(r.get('title'))} | {r['source']} | {r['tier']} | {r['mbid']} |")
    return "\n".join(L) + "\n"


def sample_slug(g):
    return g.replace(" ", "_")


def new_only(state, cache, g, args):
    """--only-new: yalniz genisletmeyle gelen (rockx.before disindaki) sanatcilar; onceki isaretli dosyalardaki sanatcilar tekrar cikmaz."""
    if not getattr(args, "only_new", False):
        return {}
    before = set(state.get({"arabesk": "arabeskx"}.get(g, "rockx"), {}).get("before", []))
    recs = isrcd_recs(state, cache, g)[0]
    marked = set()
    for f in EXCL_GENRES.get(g, ()) + ("lb_sample_tr_anadolu_rock_v2.md",):
        pth = OUT / f
        if pth.exists():
            marked |= {r["mbid"] for r in parse_sample_md(pth.read_text(encoding="utf-8"))["rows"]}
    seen = {r["artist_mbid"] for r in recs if r["mbid"] in marked}
    return {"only": {r["artist_mbid"] for r in recs} - before, "skip": seen}


def run_sample(args):
    state = _load_json(OUT / "lb_probe2_state.json", {})
    cache = _load_json(OUT / "lb_probe2_cache.json", {})
    wanted = [g.strip() for g in args.genres.split(",")] if args.genres else SAMPLE_GENRES
    for g in wanted:
        d = build_sample(state, cache, g, n_rec=args.n_rec or SAMPLE_N_REC, seed=args.seed,
                         max_per_art=args.max_per_art, **new_only(state, cache, g, args))
        path = OUT / f"lb_sample_tr_{sample_slug(g)}{args.suffix}.md"
        if path.exists():
            print(f"{path.name} zaten var; ustune yazilmadi (isaretler korunur)")
            continue
        safe_write(path, sample_markdown(d))
        by = Counter(r["source"] for r in d["records"])
        print(f"{ascii_safe(g):<12} kayit={len(d['records'])} sanatci={len(d['artists'])} kaynak={dict(by)} -> {path.name}")
    return 0


def parse_sample_md(text):
    """Isaretlenmis md -> {genre, rows:[{section: 'kayit'|'sanatci', ok: bool (kutu bos), source, tier, artist, mbid}]}."""
    genre, section, rows = None, None, []
    for line in text.splitlines():
        if line.startswith("# Elle ornekleme:"):
            genre = line.split(":", 1)[1].strip()
        elif line.startswith("## Kayit"):
            section = "kayit"
        elif line.startswith("## Sanatci"):
            section = "sanatci"
        elif line.startswith("|") and section:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 7 and _MARK_RE.match(cells[1]):
                rows.append({"section": section, "ok": cells[1] == "[ ]", "artist": cells[2], "title": cells[3],
                             "source": cells[4], "tier": cells[5], "mbid": cells[6]})
    return {"genre": genre, "rows": rows}


def rate_block(rows):
    n = len(rows)
    ok = sum(1 for r in rows if r["ok"])
    lo, hi = wilson(ok, n)
    return {"n": n, "ok": ok, "rate": round(ok / n, 4) if n else None, "ci": [round(lo, 4), round(hi, 4)]}


def hit_rates(parsed):
    """Bolum (kayit/sanatci) ve kaynak bazinda uygun orani + Wilson."""
    out = {}
    for sec in ("kayit", "sanatci"):
        rs = [r for r in parsed["rows"] if r["section"] == sec]
        out[sec] = {"genel": rate_block(rs), "kaynak": {s: rate_block([r for r in rs if r["source"] == s])
                                                          for s in sorted({r["source"] for r in rs})}}
    return out


def a_corrected(A, block):
    """A_duzeltilmis = A x uygun orani; aralik Wilson uclarindan. block: rate_block ciktisi (n=0 ise None)."""
    if not block or not block.get("n"):
        return None
    lo, hi = block["ci"]
    return {"A": A, "rate": block["rate"], "A_corr": round(A * block["rate"], 1),
            "A_corr_ci": [round(A * lo, 1), round(A * hi, 1)], "passes_A15": A * lo >= GATE_A}


def evaluate_samples(texts, a_by_genre):
    """texts: {tur: md metni}; a_by_genre: {tur: A}. Sanatci duzeyi oran varsa onu, yoksa kayit duzeyini A duzeltmesinde kullanir."""
    res = {}
    for g, t in texts.items():
        p = parse_sample_md(t)
        h = hit_rates(p)
        block = h["sanatci"]["genel"] if h["sanatci"]["genel"]["n"] else h["kayit"]["genel"]
        res[g] = {"rates": h, "A_basis": "sanatci" if h["sanatci"]["genel"]["n"] else "kayit",
                  "A_correction": a_corrected(a_by_genre.get(g, 0), block)}
    return res


def run_sample_eval(args):
    fs = sorted(OUT.glob("lb_probe2_gate_2*.json"))
    rows = _load_json(fs[-1], {}).get("genres", []) if fs else []
    a_by = {r["genre"]: r.get("A") or 0 for r in rows}
    texts = {}
    wanted = [g.strip() for g in args.genres.split(",")] if args.genres else SAMPLE_GENRES
    for g in wanted:
        p = OUT / f"lb_sample_tr_{sample_slug(g)}{args.suffix}.md"
        if p.exists():
            texts[g] = p.read_text(encoding="utf-8")
    res = evaluate_samples(texts, a_by)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe_write(OUT / f"lb_probe2_sample_eval_{stamp}.json", json.dumps(res, ensure_ascii=False, indent=1))
    for g, v in res.items():
        print(ascii_safe(g), json.dumps(v["A_correction"]), "genel kayit:", v["rates"]["kayit"]["genel"])
    return 0


# ---------------------------------------------------------------- Rap genisletme (G11): adlandirilmis sanatci + MB etiket (country:TR) + LB AND
RAPX_G = "turkce rap"
RAPX_NAMES = ["Uzi", "Ati242", "Motive", "Wegh", "Reckol",  # kullanicinin verdigi
              "Ceza", "Ezhel", "Sagopa Kajmer", "Norm Ender", "Lvbel C5", "Gazapizm", "Killa Hakan", "Mero", "Hayki",
              "Defkhan", "Heijan", "Khontkar", "Murda", "Contra", "Şanışer", "Anıl Piyancı", "Şehinşah", "Patron",
              "Aspova", "Blok3", "Joker", "Lil Zey", "Ben Fero", "Eypio", "Massaka", "Pit10", "Sansar Salvo", "Allame",
              "Server Uraz", "Cakal", "Lvbel C5", "Burry Soprano", "Fuat", "Tankurt Manas", "Rapozof"]
RAPX_TAGS = ["rap", "hip hop", "hip-hop", "trap", "drill", "gangsta rap", "türkçe rap", "turkish hip hop", "turkish rap"]
RAPX_AND = [["turkish", "rap"], ["turkish", "hip hop"], ["turkish", "hip-hop"], ["turkish", "trap"], ["turkish", "drill"],
            ["turkish", "gangsta rap"]]
PHASE_BUDGET["rapx"] = (200, 100, "G11: rap icin adlandirilmis sanatci + MB tag:X AND country:TR + LB AND + D akisi")
PHASE_CAPS["rapx"] = (200, 100)


def pick_named(results, name):
    """MB artist arama sonuclari -> en iyi eslesme (ad katlanmis esit; TR oncelikli, sonra skor) ya da None."""
    want = _fold(name)
    ex = [x for x in results if isinstance(x, dict) and x.get("id") and
          want in (_fold(x.get("name") or ""), _fold(x.get("sort-name") or ""))]
    if not ex:
        return None
    ex.sort(key=lambda x: (x.get("country") != "TR", -(x.get("score") or 0)))
    x = ex[0]
    return {"id": x["id"], "name": x.get("name"), "country": x.get("country"), "score": x.get("score"),
            "tags": [t.get("name") for t in (x.get("tags") or []) if isinstance(t, dict)][:12],
            "alternatives_TR": [y["id"] for y in ex[1:] if y.get("country") == "TR"]}


def run_rapx(args):
    g = RAPX_G
    store, token, budget, rq = _start(args, "rapx")
    cache, st = store.cache, store.state
    raw = st.setdefault("radio_raw", {})
    apop, toprec = st.setdefault("artist_pop", {}), st.setdefault("toprec", {})
    chosen = st.setdefault("artist_sel_wide", {})
    rx = st.setdefault("rapx", {"names": {}, "tagrows": {}})
    prev = _prev_artist_report().get(g)
    errors, interrupted, lookup_left = 0, None, 5
    k_new = args.artists_per_genre or 90
    print(f"rapx: butce LB<={budget.max['lb']} MB<={budget.max['mb']}, yeni sanatci tavani {k_new}")
    named_ids, tag_ids, radio_pool, pick = {}, {}, {}, []
    try:
        with store:
            # 1) ad aramasi (MB, 1 istek / ad)
            for nm in dict.fromkeys(RAPX_NAMES):
                if nm in rx["names"]:
                    continue
                code, body, _ = rq.call_retry("namesearch", "mb", "GET", f"{MB}/artist",
                                              {"query": f'artist:"{nm}"', "limit": 10, "fmt": "json"})
                if code == 200 and isinstance(body, dict):
                    rx["names"][nm] = pick_named(body.get("artists", []), nm) or {"id": None}
                else:
                    errors += 1
            store.flush()
            # 2) MB etiket + country:TR (sayfalama)
            for tg in RAPX_TAGS:
                if tg in rx["tagrows"]:
                    continue
                rows, ok = [], True
                for pg in range(args.tag_pages):
                    code, body, _ = rq.call_retry("tagsearch", "mb", "GET", f"{MB}/artist",
                                                  {"query": f'tag:"{tg}" AND country:TR', "limit": 100,
                                                   "offset": 100 * pg, "fmt": "json"})
                    if code != 200 or not isinstance(body, dict):
                        errors += 1
                        ok = False
                        break
                    arts_ = body.get("artists", [])
                    rows += [[x["id"], x.get("name"), x.get("country")] for x in arts_ if x.get("id")]
                    if len(arts_) < 100 or 100 * (pg + 1) >= body.get("count", 0):
                        break
                if ok:
                    rx["tagrows"][tg] = rows
            store.flush()
            # 3) LB AND kombinasyonlari (T1 havuzuna)
            for pair in RAPX_AND:
                unit = f"radio|{g}|and-{'+'.join(pair)}|0"
                if unit in raw:
                    continue
                code, body, _ = rq.call_retry("radio_and", "lb", "GET", f"{LB}/lb-radio/tags",
                                              {"tag": pair, "operator": "AND", "pop_begin": 0, "pop_end": 100, "count": 1000})
                if code != 200:
                    errors += 1
                    continue
                rs_ = [r for r in as_records(body) if isinstance(r, dict) and r.get("recording_mbid")]
                raw[unit] = [[r["recording_mbid"], r.get("tag_count"), r.get("percent"), r.get("source")] for r in rs_]
                store.mark_done(unit)
            for unit, rows in raw.items():
                parts = unit.split("|")
                if len(parts) == 4 and parts[1] == g:
                    for r in rows:
                        radio_pool.setdefault(r[0], set()).add(parts[2])
            _, lookup_left = resolve_mbids(rq, store, [m_ for m_ in radio_pool if m_ not in cache], lookup_left)
            store.flush()
            # 4) aday sanatcilar: adlandirilmis (TR) + etiketten gelen TR
            for nm, v in rx["names"].items():
                if v.get("id") and v.get("country") in ("TR", None, ""):  # ulkesi bos olan adlandirilmislar da (MB ulke eksik)
                    named_ids[v["id"]] = nm
            for tg, rows in rx["tagrows"].items():
                for aid, nm, c in rows:
                    if c == "TR":
                        tag_ids.setdefault(aid, nm)
            cands = list(dict.fromkeys(list(named_ids) + list(tag_ids)))
            todo = [a for a in cands if a not in apop]
            for i in range(0, len(todo), POP_BATCH):
                chunk = todo[i:i + POP_BATCH]
                code, body, _ = rq.call_retry("pop_artist", "lb", "POST", f"{LB}/popularity/artist",
                                              post={"artist_mbids": chunk}, use_token=True)
                if code == 200 and isinstance(body, list):
                    got = {x.get("artist_mbid"): int(x.get("total_listen_count") or 0) for x in body if isinstance(x, dict)}
                    for a in chunk:
                        apop[a] = got.get(a, 0)
                else:
                    errors += 1
            store.flush()
            prior = set(chosen.get(g, [])) | set(st.get("artist_sel", {}).get(g, []))
            listens = {a: apop[a] for a in cands if a in apop}
            tiers = pop_tier({a: apop[a] for a in set(listens) | prior if a in apop})
            rest = {a: 0.5 for a in listens if a not in named_ids and a not in prior and listens[a] > 0}
            pick = [a for a in named_ids if a not in prior]
            pick += select_artists(rest, tiers, max(0, k_new - len(pick)), NICHE_SHARE, args.seed)
            for i in range(0, len(pick), CHUNK):
                new_mbids = []
                for a in pick[i:i + CHUNK]:
                    if a not in toprec:
                        code, body, _ = rq.call_retry("toprec", "lb", "GET",
                                                      f"{LB}/popularity/top-recordings-for-artist/{a}", use_token=True)
                        if code == 200 and isinstance(body, list):
                            rows = sorted((x for x in body if isinstance(x, dict) and x.get("recording_mbid")),
                                          key=lambda x: -(x.get("total_listen_count") or 0))[:args.top_k]
                            toprec[a] = [[x["recording_mbid"], x.get("total_listen_count") or 0] for x in rows]
                        elif code == 404:
                            toprec[a] = []
                        else:
                            errors += 1
                            continue
                    new_mbids += [x[0] for x in toprec[a]]
                _, lookup_left = resolve_mbids(rq, store, new_mbids, lookup_left)
                store.flush()
            have = chosen.setdefault(g, [])
            for a in pick:
                if a in toprec and a not in have:
                    have.append(a)
            store.flush()
    except (KeyboardInterrupt, BudgetExceeded) as e_:
        interrupted = repr(e_)
    # --- ozet (istek yok): once/sonra ve teshis
    d_pool = {}
    for a in set(chosen.get(g, [])) | set(st.get("artist_sel", {}).get(g, [])):
        for m_, _n in toprec.get(a, []):
            d_pool.setdefault(m_, set()).update(("D", "D@" + a))
    lis = {a: v for a, v in apop.items()}
    res = de_summary(radio_pool, d_pool, cache, lis, args.session_size, args.artist_cap)
    in_radio = {cache[m_]["artist_mbid"] for m_ in (radio_pool)
                if cache.get(m_) and cache[m_].get("artist_mbid")}
    diag = {}
    for nm, v in rx["names"].items():
        a = v.get("id")
        if not a:
            diag[nm] = {"mb": "bulunamadi"}
            continue
        trs = toprec.get(a)
        diag[nm] = {"mb_id": a, "country": v.get("country"), "mb_tags": v.get("tags"),
                    "in_tag_search": a in tag_ids, "in_lb_radio": a in in_radio, "listens": apop.get(a),
                    "toprec_n": None if trs is None else len(trs),
                    "toprec_isrc_n": None if trs is None else sum(1 for m_, _ in trs if cache.get(m_, {}).get("isrcs")),
                    "in_pool": a in set(chosen.get(g, [])) | set(st.get("artist_sel", {}).get(g, []))}
    _report_tail("rapx", rq, budget, store, token, errors, interrupted,
                 {"before": prev, "after": {k: res["T1+D"].get(k) for k in ("n", "C", "A", "top_share", "verdict")},
                  "after_full": res, "named": diag, "tag_counts": {t: len(r) for t, r in rx["tagrows"].items()},
                  "tag_TR_unique": len(tag_ids), "new_artists_picked": len(pick)})
    a_ = res["T1+D"]
    print(f"rap once: {prev}")
    print(f"rap sonra: C={a_['C']} A={a_['A']} pay={a_['top_share']} n={a_['n']}")
    return 2 if interrupted else 0


# ---------------------------------------------------------------- Kredi listesi yenileme (G12)
PHASE_BUDGET["credits"] = (40, 0, "G12: onbellekteki ISRC'li TR kayitlarina tum sanatci kredisini ekler (LB metadata)")
PHASE_CAPS["credits"] = (40, 0)


def credit_targets(state, cache):
    """TR turlerinin (T1 radyo + D top-kayit) ISRC'li ve henuz 'artists' alani olmayan kayit MBID'leri."""
    pool = set()
    for unit, rows in state.get("radio_raw", {}).items():
        p = unit.split("|")
        if len(p) == 4 and p[1] in TR_GENRES:
            pool.update(r[0] for r in rows)
    for key in ("artist_sel", "artist_sel_wide"):
        for g, arts in state.get(key, {}).items():
            if g in TR_GENRES:
                for a in arts:
                    pool.update(m_ for m_, _n in state.get("toprec", {}).get(a, []))
    return sorted(m_ for m_ in pool if cache.get(m_) and cache[m_].get("isrcs") and cache[m_].get("src") != "mb_404"
                  and "artists" not in cache[m_])


def run_credits(args):
    store, token, budget, rq = _start(args, "credits")
    errors, interrupted, got = 0, None, 0
    todo = credit_targets(store.state, store.cache)
    print(f"credits: {len(todo)} kayit, {-(-len(todo) // META_BATCH)} LB istegi (tavan {budget.max['lb']})")
    try:
        with store:
            for i in range(0, len(todo), META_BATCH):
                chunk = todo[i:i + META_BATCH]
                code, body, _ = rq.call_retry("meta", "lb", "POST", f"{LB}/metadata/recording/",
                                              post={"recording_mbids": chunk, "inc": "artist tag"}, use_token=True)
                if code != 200 or not isinstance(body, dict):
                    errors += 1
                    continue
                for m_ in chunk:
                    if body.get(m_):
                        store.cache[m_]["artists"] = credit_list((body[m_] or {}).get("artist"))
                        got += 1
                store.flush()
    except (KeyboardInterrupt, BudgetExceeded) as e_:
        interrupted = repr(e_)
    _report_tail("credits", rq, budget, store, token, errors, interrupted, {"targets": len(todo), "updated": got})
    return 2 if interrupted else 0


# ---------------------------------------------------------------- Halk genisletme (G13): kanitli ad listesi + MB tur-alti etiket + ulke/tur-disi filtresi
HALK_G = "turk halk"
HALKX_NAMES = [
    "Neşet Ertaş", "Aşık Veysel", "Muharrem Ertaş", "Ruhi Su", "Arif Sağ", "Musa Eroğlu", "Hüseyin Turan",
    "Selda Bağcan", "Bedia Akartürk", "Sabahat Akkiraz", "Pervin Çakar", "Yavuz Bingöl", "Edip Akbayram",
    "Mahzuni Şerif", "Ali Ekber Çiçek", "Kıvırcık Ali", "Çiğdem Akın", "Belkıs Akkale", "Hakkı Bulut",
    "Aşık Daimi", "Aşık Feymani", "Aşık Reyhani", "Aşık Ali İzzet", "Aşık Ruhsati", "Aşık Şeref Taşlıova",
    "Aşık Murat Çobanoğlu", "Aşık Nesimi Çimen", "Aşık Hüseyin Çırakman", "Ozan Arif", "Muhlis Akarsu",
    "Erdal Erzincan", "Davut Sulari", "Hasret Gültekin", "Çekiç Ali", "Mazlum Çimen", "Nizamettin Ariç",
    "Erkan Oğur", "Ferhat Tunç", "Fuat Saka", "Özay Gönlüm"]
HALKX_TAGS = ["türkü", "halk müziği", "türk halk müziği", "ozan", "aşık", "bağlama", "saz", "uzun hava", "zeybek", "bozlak",
              "alevi", "deyiş", "semah", "turkish folk", "folk"]
HALKX_AND = [["turkish", "bağlama"], ["turkish", "semah"], ["turkish", "zeybek"], ["turkish", "uzun hava"],
             ["turkish", "ozan"], ["turkish", "deyiş"]]
OFF_WORDS = {"psychedelic", "alternative", "indie", "rock", "electronic", "pop", "hip", "rap", "metal", "jazz", "electronica",
             "ambient", "techno", "house", "punk"}
PHASE_BUDGET["halkx"] = (200, 100, "G13: halk icin ad listesi + MB tur-alti etiket + LB AND + ulke/tur-disi filtre + D akisi")
PHASE_CAPS["halkx"] = (200, 100)
META_GENRES = ("turk halk", "turkce rap", "arabesk")
ARID_BATCH = 40


def offgenre(tags):
    """MB etiket adlari -> tur disi (psychedelic/alternative/indie/rock/electronic/pop/...) sozcugu iceriyor mu."""
    return any(w in OFF_WORDS for t in tags or [] for w in _fold(t).replace("-", " ").split())


def compute_excl(meta, g, curated=()):
    """artist_meta {id: {country, tags}} -> disarida tutulacak sanatci kimlikleri.
    Yabanci ulke (MB'de ulke dolu ve TR degil) her tur icin; halk icin ayrica tur-disi etiketli (kurulu ad listesindekiler haric)."""
    out = set()
    for a, v in meta.items():
        c = v.get("country")
        if c and c != "TR":
            out.add(a)
        elif g == HALK_G and a not in curated and offgenre(v.get("tags")):
            out.add(a)
    return out


def names_of(cache, aid):
    """Onbellekteki kredi listelerinden sanatci adi (yoksa kimligin basi)."""
    for i in cache.values():
        for a in i.get("artists") or []:
            if a[0] == aid:
                return a[1]
    return aid[:8]


def pool_artists(state, cache, g):
    """g turunun T1+D ISRC'li kayitlarinin birincil sanatci kimlikleri (dislama oncesi)."""
    mg = {}
    for unit, rows in state.get("radio_raw", {}).items():
        p = unit.split("|")
        if len(p) == 4 and p[1] == g:
            for r in rows:
                mg.setdefault(r[0], set()).add(p[2])
    for key in ("artist_sel", "artist_sel_wide"):
        for a in state.get(key, {}).get(g, []):
            for m_, _n in state.get("toprec", {}).get(a, []):
                mg.setdefault(m_, set()).update(("D", "D@" + a))
    return {r["artist_mbid"] for r in _pool_recs(mg, cache) if r.get("isrcs") and r.get("artist_mbid")}


def fetch_artist_meta(rq, ids, meta):
    """MB arid: toplu arama (ARID_BATCH / istek) -> meta[id] = {country, tags}. Hata sayisini dondurur."""
    errors = 0
    todo = [a for a in dict.fromkeys(ids) if a not in meta]
    for i in range(0, len(todo), ARID_BATCH):
        chunk = todo[i:i + ARID_BATCH]
        code, body, _ = rq.call_retry("arid", "mb", "GET", f"{MB}/artist",
                                      {"query": "arid:(" + " OR ".join(chunk) + ")", "limit": 100, "fmt": "json"})
        if code != 200 or not isinstance(body, dict):
            errors += 1
            continue
        got = {x["id"]: x for x in body.get("artists", []) if isinstance(x, dict) and x.get("id")}
        for a in chunk:
            x = got.get(a)
            meta[a] = {"country": (x or {}).get("country"), "tags": [t.get("name") for t in (x or {}).get("tags") or []
                                                                       if isinstance(t, dict)][:15], "found": bool(x)}
    return errors


def run_halkx(args):
    g = HALK_G
    store, token, budget, rq = _start(args, "halkx")
    cache, st = store.cache, store.state
    raw = st.setdefault("radio_raw", {})
    apop, toprec = st.setdefault("artist_pop", {}), st.setdefault("toprec", {})
    chosen = st.setdefault("artist_sel_wide", {})
    hx = st.setdefault("halkx", {"names": {}, "tagrows": {}})
    meta = st.setdefault("artist_meta", {})
    prev = _prev_artist_report().get(g)
    errors, interrupted, lookup_left = 0, None, 5
    k_new = args.artists_per_genre or 80
    named_ids, tag_ids, radio_pool, pick, dropped_off = {}, {}, {}, [], []
    print(f"halkx: butce LB<={budget.max['lb']} MB<={budget.max['mb']}, yeni sanatci tavani {k_new}")
    try:
        with store:
            for nm in dict.fromkeys(HALKX_NAMES):
                if nm in hx["names"]:
                    continue
                code, body, _ = rq.call_retry("namesearch", "mb", "GET", f"{MB}/artist",
                                              {"query": f'artist:"{nm}"', "limit": 10, "fmt": "json"})
                if code == 200 and isinstance(body, dict):
                    hx["names"][nm] = pick_named(body.get("artists", []), nm) or {"id": None}
                else:
                    errors += 1
            store.flush()
            for tg in HALKX_TAGS:
                if tg in hx["tagrows"]:
                    continue
                rows, ok = [], True
                for pg in range(args.tag_pages):
                    code, body, _ = rq.call_retry("tagsearch", "mb", "GET", f"{MB}/artist",
                                                  {"query": f'tag:"{tg}" AND country:TR', "limit": 100,
                                                   "offset": 100 * pg, "fmt": "json"})
                    if code != 200 or not isinstance(body, dict):
                        errors += 1
                        ok = False
                        break
                    arts_ = body.get("artists", [])
                    rows += [[x["id"], x.get("name"), x.get("country"),
                              [t.get("name") for t in (x.get("tags") or []) if isinstance(t, dict)][:15]]
                             for x in arts_ if x.get("id")]
                    if len(arts_) < 100 or 100 * (pg + 1) >= body.get("count", 0):
                        break
                if ok:
                    hx["tagrows"][tg] = rows
            store.flush()
            for pair in HALKX_AND:
                unit = f"radio|{g}|and-{'+'.join(pair)}|0"
                if unit in raw:
                    continue
                code, body, _ = rq.call_retry("radio_and", "lb", "GET", f"{LB}/lb-radio/tags",
                                              {"tag": pair, "operator": "AND", "pop_begin": 0, "pop_end": 100, "count": 1000})
                if code != 200:
                    errors += 1
                    continue
                rs_ = [r for r in as_records(body) if isinstance(r, dict) and r.get("recording_mbid")]
                raw[unit] = [[r["recording_mbid"], r.get("tag_count"), r.get("percent"), r.get("source")] for r in rs_]
                store.mark_done(unit)
            for unit, rows in raw.items():
                parts = unit.split("|")
                if len(parts) == 4 and parts[1] == g:
                    for r in rows:
                        radio_pool.setdefault(r[0], set()).add(parts[2])
            _, lookup_left = resolve_mbids(rq, store, [m_ for m_ in radio_pool if m_ not in cache], lookup_left)
            store.flush()
            # adaylar: kurulu ad listesi (TR) + etiketten TR (tur-disi etiketliler haric)
            for nm, v in hx["names"].items():
                if v.get("id") and v.get("country") == "TR":
                    named_ids[v["id"]] = nm
            for tg, rows in hx["tagrows"].items():
                for aid, nm, c, tags in rows:
                    if c != "TR":
                        continue
                    if offgenre(tags) and aid not in named_ids:
                        dropped_off.append(nm)
                        continue
                    tag_ids.setdefault(aid, nm)
            cands = list(dict.fromkeys(list(named_ids) + list(tag_ids)))
            todo = [a for a in cands if a not in apop]
            for i in range(0, len(todo), POP_BATCH):
                chunk = todo[i:i + POP_BATCH]
                code, body, _ = rq.call_retry("pop_artist", "lb", "POST", f"{LB}/popularity/artist",
                                              post={"artist_mbids": chunk}, use_token=True)
                if code == 200 and isinstance(body, list):
                    got = {x.get("artist_mbid"): int(x.get("total_listen_count") or 0) for x in body if isinstance(x, dict)}
                    for a in chunk:
                        apop[a] = got.get(a, 0)
                else:
                    errors += 1
            store.flush()
            prior = set(chosen.get(g, [])) | set(st.get("artist_sel", {}).get(g, []))
            listens = {a: apop[a] for a in cands if a in apop}
            tiers = pop_tier({a: apop[a] for a in set(listens) | prior if a in apop})
            rest = {a: 0.5 for a in listens if a not in named_ids and a not in prior and listens[a] > 0}
            pick = [a for a in named_ids if a not in prior]
            pick += select_artists(rest, tiers, max(0, k_new - len(pick)), NICHE_SHARE, args.seed)
            for i in range(0, len(pick), CHUNK):
                new_mbids = []
                for a in pick[i:i + CHUNK]:
                    if a not in toprec:
                        code, body, _ = rq.call_retry("toprec", "lb", "GET",
                                                      f"{LB}/popularity/top-recordings-for-artist/{a}", use_token=True)
                        if code == 200 and isinstance(body, list):
                            rows = sorted((x for x in body if isinstance(x, dict) and x.get("recording_mbid")),
                                          key=lambda x: -(x.get("total_listen_count") or 0))[:args.top_k]
                            toprec[a] = [[x["recording_mbid"], x.get("total_listen_count") or 0] for x in rows]
                        elif code == 404:
                            toprec[a] = []
                        else:
                            errors += 1
                            continue
                    new_mbids += [x[0] for x in toprec[a]]
                _, lookup_left = resolve_mbids(rq, store, new_mbids, lookup_left)
                store.flush()
            have = chosen.setdefault(g, [])
            for a in pick:
                if a in toprec and a not in have:
                    have.append(a)
            store.flush()
            # ulke + etiket meta: uc TR turunun havuz sanatcilari (yabanci sizintisini kapatmak icin)
            for mg_ in META_GENRES:
                errors += fetch_artist_meta(rq, sorted(pool_artists(st, cache, mg_)), meta)
                store.flush()
            curated = set(named_ids)
            ex = st.setdefault("artist_excl", {})
            for mg_ in META_GENRES:
                ex[mg_] = sorted(compute_excl({a: meta[a] for a in pool_artists(st, cache, mg_) if a in meta}, mg_, curated))
            store.flush()
    except (KeyboardInterrupt, BudgetExceeded) as e_:
        interrupted = repr(e_)
    ex_h = set(st.get("artist_excl", {}).get(g, []))
    d_pool = {}
    for a in set(chosen.get(g, [])) | set(st.get("artist_sel", {}).get(g, [])):
        for m_, _n in toprec.get(a, []):
            d_pool.setdefault(m_, set()).update(("D", "D@" + a))
    res = de_summary(radio_pool, d_pool, cache, apop, args.session_size, args.artist_cap, excl=ex_h)
    names_rep = {}
    for nm in HALKX_NAMES:
        v = hx["names"].get(nm)
        if v is None:
            continue
        a = v.get("id")
        trs = toprec.get(a) if a else None
        names_rep[nm] = ({"mb": "bulunamadi"} if not a else
                         {"mb_id": a, "country": v.get("country"), "mb_tags": v.get("tags"), "listens": apop.get(a),
                          "toprec_n": None if trs is None else len(trs),
                          "toprec_isrc_n": None if trs is None else sum(1 for m_, _ in trs if cache.get(m_, {}).get("isrcs"))})
    _report_tail("halkx", rq, budget, store, token, errors, interrupted,
                 {"before": prev, "after": {k: res["T1+D"].get(k) for k in ("n", "C", "A", "top_share", "verdict")},
                  "after_full": res, "named": names_rep,
                  "tag_counts": {t: len(r) for t, r in hx["tagrows"].items()}, "tag_TR_unique": len(tag_ids),
                  "tag_dropped_offgenre": sorted(set(dropped_off)), "new_artists_picked": len(pick),
                  "excluded": {k: len(v) for k, v in st.get("artist_excl", {}).items()},
                  "excluded_detail": {k: [[names_of(cache, a), (meta.get(a) or {}).get("country"), (meta.get(a) or {}).get("tags", [])[:4]]
                                          for a in v] for k, v in st.get("artist_excl", {}).items()}})
    a_ = res["T1+D"]
    print(f"halk once: {prev}")
    print(f"halk sonra: C={a_['C']} A={a_['A']} pay={a_['top_share']} n={a_['n']}")
    return 2 if interrupted else 0


# ---------------------------------------------------------------- Halk dil izin listesi (G14): kayit duzeyi "Turkce sarki"
# MB kayitlarinda dil alani yok; surum (release) text-representation.language kullanilir. Tek, genel olcut: Turkce sarki.
PHASE_BUDGET["lang"] = (0, 60, "G14: halk ISRC'li kayitlarin surum dili (MB recording rid: + release reid:)")
PHASE_CAPS["lang"] = (0, 60)
LANG_BATCH, LANG_REL_PER_REC = 25, 3
LANG_NEUTRAL = {"", "mul", "zxx", "und"}
LANG_SAMPLE_FILES = ("lb_sample_tr_turk_halk.md", "lb_sample_tr_turk_halk_v2.md")


def lang_of(langs):
    """Surum dillerinden kayit dili: 'tur' varsa 'tur'; yoksa en sik belirgin dil; yoksa '' (bilinmiyor)."""
    ls = [l for l in (langs or []) if isinstance(l, str)]
    if "tur" in ls:
        return "tur"
    known = [l for l in ls if l not in LANG_NEUTRAL]
    return Counter(known).most_common(1)[0][0] if known else ""


def classify_lang(lang, artist_allowed):
    """tur -> 'tur'; baska belirgin dil -> 'yabanci'; dil yok + izin listesinde -> 'izin'; aksi 'belirsiz' (sayiya katilmaz)."""
    if lang == "tur":
        return "tur"
    if lang and lang not in LANG_NEUTRAL:
        return "yabanci"
    return "izin" if artist_allowed else "belirsiz"


def allow_artists(recs, marked):
    """marked: {kayit mbid: uygun(bool)}. Izin: en az bir uygun isareti olan ve hic uygun-degil isareti olmayan sanatci."""
    ok, bad = set(), set()
    for r in recs:
        if r["mbid"] in marked:
            (ok if marked[r["mbid"]] else bad).add(r["artist_mbid"])
    return ok - bad


def lang_gate(recs, lang_map, allow):
    """Halk kayit duzeyi dil kapisi: yalniz tur/izin kayitlar sayilir; yumusatma yok (K2 esikleri ayni)."""
    cls = Counter()
    kept = []
    for r in recs:
        c = classify_lang(lang_of(lang_map.get(r["mbid"])), r["artist_mbid"] in allow)
        cls[c] += 1
        if c in ("tur", "izin"):
            kept.append(r)
    per = Counter(r["artist_mbid"] for r in kept)
    C, A = len(kept), len(per)
    share = (max(per.values()) / C) if C else 0.0
    known = cls["tur"] + cls["izin"] + cls["yabanci"]
    tl = cls["tur"] + cls["yabanci"]
    return {"records": len(recs), "classes": dict(cls), "C": C, "A": A, "top_share": round(share, 3),
            "mismatch_rate": round(cls["yabanci"] / known, 4) if known else None,
            "mismatch_rate_lang_known": round(cls["yabanci"] / tl, 4) if tl else None,
            "undetermined": cls["belirsiz"], "pass": C >= GATE_C and A >= GATE_A and share <= MAX_TOP_SHARE}


def load_marks(texts):
    """Birden cok isaretli md -> {kayit mbid: uygun}; herhangi bir [x] uygun-degil sayilir."""
    marked = {}
    for t in texts:
        for r in parse_sample_md(t)["rows"]:
            marked[r["mbid"]] = r["ok"] and marked.get(r["mbid"], True)
    return marked


def halk_lang_report(state, cache, out_dir=None):
    out_dir = Path(out_dir or OUT)
    lang_map = state.get("lang", {})
    if not lang_map:
        return None
    recs = isrcd_recs(state, cache, HALK_G)[0]
    texts = [(out_dir / f).read_text(encoding="utf-8") for f in LANG_SAMPLE_FILES if (out_dir / f).exists()]
    allow = allow_artists(recs, load_marks(texts))
    rep = lang_gate(recs, lang_map, allow)
    rep["allow_artists"] = len(allow)
    rep["lang_covered"] = sum(1 for r in recs if r["mbid"] in lang_map)
    rep["by_lang"] = dict(Counter(lang_of(lang_map.get(r["mbid"])) or "?" for r in recs))
    return rep


def lang_targets(state, cache):
    done = state.get("lang", {})
    return [r["mbid"] for r in isrcd_recs(state, cache, HALK_G)[0] if r["mbid"] not in done]


def run_lang(args):
    store, token, budget, rq = _start(args, "lang")
    errors, interrupted = 0, None
    todo = lang_targets(store.state, store.cache)
    print(f"lang: {len(todo)} kayit")
    st = store.state
    lg = st.setdefault("lang", {})
    try:
        with store:
            for i in range(0, len(todo), LANG_BATCH):
                chunk = todo[i:i + LANG_BATCH]
                code, body, _ = rq.call_retry("rec", "mb", "GET", f"{MB}/recording",
                                              {"query": "rid:(" + " OR ".join(chunk) + ")", "limit": 100, "fmt": "json"})
                if code != 200 or not isinstance(body, dict):
                    errors += 1
                    continue
                rels = {}
                for r in body.get("recordings", []):
                    rels[r.get("id")] = [x["id"] for x in (r.get("releases") or [])[:LANG_REL_PER_REC] if x.get("id")]
                allrel = sorted({x for v in rels.values() for x in v})
                relang = {}
                for j in range(0, len(allrel), LANG_BATCH):
                    c2 = allrel[j:j + LANG_BATCH]
                    code, b2, _ = rq.call_retry("rel", "mb", "GET", f"{MB}/release",
                                                {"query": "reid:(" + " OR ".join(c2) + ")", "limit": 100, "fmt": "json"})
                    if code != 200 or not isinstance(b2, dict):
                        errors += 1
                        continue
                    for x in b2.get("releases", []):
                        relang[x.get("id")] = ((x.get("text-representation") or {}).get("language") or "")
                for m_ in chunk:
                    if m_ in rels:
                        lg[m_] = [relang.get(x, "") for x in rels[m_]]
                store.flush()
    except (KeyboardInterrupt, BudgetExceeded) as e_:
        interrupted = repr(e_)
    rep = halk_lang_report(st, store.cache)
    _report_tail("lang", rq, budget, store, token, errors, interrupted, {"targets": len(todo), "halk_dil": rep})
    print("halk dil:", json.dumps(rep, ensure_ascii=False))
    return 2 if interrupted else 0


# ---------------------------------------------------------------- Sizinti filtresi (G15): arabesk + anadolu rock
# Genel olcut: yabanci ulke (MB) + kullanicinin 'uygun degil' isaretledigi sanatcilar (tur disi/yabanci). Etnik/dil grubuna ozel liste yok.
PHASE_BUDGET["excl"] = (0, 60, "G15: arabesk/anadolu rock icin MB ulke meta + isaretli uygunsuz sanatci dislamasi")
PHASE_CAPS["excl"] = (0, 60)
EXCL_GENRES = {"arabesk": ("lb_sample_tr_arabesk.md", "lb_sample_tr_arabesk_v2.md", "lb_sample_tr_arabesk_v3.md", "lb_sample_tr_arabesk_v4.md"),
               "anadolu rock": ("lb_sample_tr_anadolu_rock.md", "lb_sample_tr_anadolu_rock_v2.md", "lb_sample_tr_anadolu_rock_v3.md")}


def unfit_artists(recs, marked):
    """Isaretli kayitlardan sanatci: uygun-degil ([x]) sayisi uygun sayisindan fazla -> tur disi/yabanci, dislanir (esitlikte kalir)."""
    bad, ok = Counter(), Counter()
    for r in recs:
        if r["mbid"] in marked:
            (ok if marked[r["mbid"]] else bad)[r["artist_mbid"]] += 1
    return {a for a, n in bad.items() if n > ok[a]}


def run_excl(args):
    store, token, budget, rq = _start(args, "excl")
    st, cache = store.state, store.cache
    meta = st.setdefault("artist_meta", {})
    errors, interrupted, rep = 0, None, {}
    try:
        with store:
            for g, files in EXCL_GENRES.items():
                errors += fetch_artist_meta(rq, sorted(pool_artists(st, cache, g)), meta)
                store.flush()
            ex = st.setdefault("artist_excl", {})
            for g, files in EXCL_GENRES.items():
                # tum havuz (dislama oncesi) uzerinden kayit->sanatci eslemesi
                keep = ex.get(g, [])
                ex[g] = []
                recs = isrcd_recs(st, cache, g)[0]
                texts = [(OUT / f).read_text(encoding="utf-8") for f in files if (OUT / f).exists()]
                unfit = unfit_artists(recs, load_marks(texts))
                ctry = compute_excl({a: meta[a] for a in pool_artists(st, cache, g) if a in meta}, g)
                ex[g] = sorted(set(keep) | unfit | ctry)
                after = isrcd_recs(st, cache, g)[0]
                rep[g] = {"country_excl": len(ctry), "marked_unfit": len(unfit), "excluded_total": len(ex[g]),
                          "A_before": len({r["artist_mbid"] for r in recs}), "A_after": len({r["artist_mbid"] for r in after}),
                          "C_after": len(after), "unfit_names": sorted(names_of(cache, a) for a in unfit)}
            store.flush()
    except (KeyboardInterrupt, BudgetExceeded) as e_:
        interrupted = repr(e_)
    _report_tail("excl", rq, budget, store, token, errors, interrupted, {"genres": rep})
    print(ascii_safe(json.dumps(rep, ensure_ascii=False)))
    return 2 if interrupted else 0


# ---------------------------------------------------------------- Anadolu rock genisletme (G17): yeni takma ad + AND + MB etiket (country:TR) + D
ROCKX_G = "anadolu rock"
ROCKX_TAGS = ["anatolian rock", "anadolu rock", "türk rock", "turkish rock", "türkçe rock", "psychedelic rock",
              "anatolian psychedelic rock", "turkish psychedelic rock", "garage rock", "progressive rock", "folk rock"]
ROCKX_AND = [["anatolian", "psychedelic"], ["turkish", "psychedelic"], ["anatolian", "rock"], ["turkish", "rock"],
             ["turkish", "psychedelic rock"], ["anatolian", "psychedelic rock"], ["turkish", "garage rock"]]
PHASE_BUDGET["rockx"] = (60, 40, "G17: anadolu rock icin yeni takma ad/AND + MB tag:X AND country:TR + D; hata/429'da durur")
PHASE_CAPS["rockx"] = (60, 40)
ROCKX_NEW_MAX = 14


def run_ext(args, phase, g, tags_, ands_, key, max_new):
    """Genel tur genisletme (rockx/arabeskx): yeni etiket + AND + MB tag country:TR + D; hata/429'da durur."""
    store, token, budget, rq = _start(args, phase)
    cache, st = store.cache, store.state
    raw = st.setdefault("radio_raw", {})
    apop, toprec = st.setdefault("artist_pop", {}), st.setdefault("toprec", {})
    chosen = st.setdefault("artist_sel_wide", {})
    meta = st.setdefault("artist_meta", {})
    rx = st.setdefault(key, {"tagrows": {}, "new": []})
    before = pool_artists(st, cache, g)
    rx.setdefault("before", sorted(before))  # genisletme oncesi havuz (yeni sanatci ayrimi icin)
    errors, interrupted, lookup_left = 0, None, 3
    tag_ids, pick = {}, []
    try:
        with store:
            for tg in tags_:
                if tg in rx["tagrows"]:
                    continue
                code, body, _ = rq.call_retry("tagsearch", "mb", "GET", f"{MB}/artist",
                                              {"query": f'tag:"{tg}" AND country:TR', "limit": 100, "fmt": "json"})
                if code != 200 or not isinstance(body, dict):
                    errors += 1
                    break
                rx["tagrows"][tg] = [[x["id"], x.get("name"), x.get("country")] for x in body.get("artists", []) if x.get("id")]
            store.flush()
            for pair in ands_ if not errors else []:
                unit = f"radio|{g}|and-{'+'.join(pair)}|0"
                if unit in raw:
                    continue
                code, body, _ = rq.call_retry("radio_and", "lb", "GET", f"{LB}/lb-radio/tags",
                                              {"tag": pair, "operator": "AND", "pop_begin": 0, "pop_end": 100, "count": 1000})
                if code != 200:
                    errors += 1
                    break
                rs_ = [r for r in as_records(body) if isinstance(r, dict) and r.get("recording_mbid")]
                raw[unit] = [[r["recording_mbid"], r.get("tag_count"), r.get("percent"), r.get("source")] for r in rs_]
                store.mark_done(unit)
            store.flush()
            if not errors:
                radio_pool = {}
                for unit, rows in raw.items():
                    parts = unit.split("|")
                    if len(parts) == 4 and parts[1] == g:
                        for r in rows:
                            radio_pool.setdefault(r[0], set()).add(parts[2])
                _, lookup_left = resolve_mbids(rq, store, [m_ for m_ in radio_pool if m_ not in cache], lookup_left)
                store.flush()
                for tg, rows in rx["tagrows"].items():
                    for aid, nm, c in rows:
                        tag_ids.setdefault(aid, nm)
                prior = before | set(chosen.get(g, [])) | set(st.get("artist_sel", {}).get(g, []))
                cands = [a for a in dict.fromkeys(list(tag_ids) + sorted(pool_artists(st, cache, g))) if a not in prior]
                todo = [a for a in cands if a not in apop]
                for i in range(0, len(todo), POP_BATCH):
                    chunk = todo[i:i + POP_BATCH]
                    code, body, _ = rq.call_retry("pop_artist", "lb", "POST", f"{LB}/popularity/artist",
                                                  post={"artist_mbids": chunk}, use_token=True)
                    if code == 200 and isinstance(body, list):
                        got = {x.get("artist_mbid"): int(x.get("total_listen_count") or 0) for x in body if isinstance(x, dict)}
                        for a in chunk:
                            apop[a] = got.get(a, 0)
                    else:
                        errors += 1
                        break
                store.flush()
            if not errors:
                listens = {a: apop[a] for a in cands if apop.get(a, 0) > 0}
                errors += fetch_artist_meta(rq, sorted(listens), meta)  # yabanci ulke dislamasi (genel)
                store.flush()
                foreign = compute_excl({a: meta[a] for a in listens if a in meta}, g)
                rest = {a: 0.5 for a in listens if a not in foreign}
                tiers = pop_tier({a: apop[a] for a in rest})
                pick = select_artists(rest, tiers, max_new, NICHE_SHARE, args.seed)
                for a in pick:
                    if errors:
                        break
                    code, body, _ = rq.call_retry("toprec", "lb", "GET", f"{LB}/popularity/top-recordings-for-artist/{a}", use_token=True)
                    if code == 200 and isinstance(body, list):
                        rows = sorted((x for x in body if isinstance(x, dict) and x.get("recording_mbid")),
                                      key=lambda x: -(x.get("total_listen_count") or 0))[:args.top_k]
                        toprec[a] = [[x["recording_mbid"], x.get("total_listen_count") or 0] for x in rows]
                    elif code == 404:
                        toprec[a] = []
                    else:
                        errors += 1
                        break
                store.flush()
                _, lookup_left = resolve_mbids(rq, store, [x[0] for a in pick for x in toprec.get(a, [])], lookup_left)
                have = chosen.setdefault(g, [])
                for a in pick:
                    if a in toprec and a not in have:
                        have.append(a)
                rx["new"] = sorted(set(rx["new"]) | {a for a in pick if a in toprec})
                store.flush()
    except (KeyboardInterrupt, BudgetExceeded) as e_:
        interrupted = repr(e_)
    after = pool_artists(st, cache, g)
    _report_tail(phase, rq, budget, store, token, errors, interrupted,
                 {"pool_before": len(before), "pool_after": len(after), "picked": [names_of(cache, a) for a in rx["new"]],
                  "tag_counts": {t: len(r) for t, r in rx["tagrows"].items()}})
    print(f"{phase}: havuz {len(before)} -> {len(after)}; yeni secilen {len(rx['new'])}; hata={errors}")
    return 2 if (interrupted or errors) else 0


def run_rockx(args):
    return run_ext(args, "rockx", ROCKX_G, ROCKX_TAGS, ROCKX_AND, "rockx", ROCKX_NEW_MAX)


ARABX_G = "arabesk"
ARABX_TAGS = ["arabesk", "arabesque", "türk arabeski", "arabesk müzik", "fantezi", "özgün müzik", "turkish arabesque",
              "arabesk pop", "slow",
              "damar", "yeni arabesk", "turkish pop", "türk pop", "türk halk müziği"]
ARABX_AND = [["arabesk", "pop"], ["arabesk", "halk"], ["arabesk", "slow"], ["turkish", "arabesk"], ["turkish", "arabesque"],
             ["fantezi", "turkish"], ["özgün", "turkish"]]
PHASE_BUDGET["arabeskx"] = (45, 30, "G18: arabesk icin yeni takma ad/AND + MB tag:X AND country:TR + D; hata/429'da durur")
PHASE_CAPS["arabeskx"] = (45, 30)


def run_arabeskx(args):
    return run_ext(args, "arabeskx", ARABX_G, ARABX_TAGS, ARABX_AND, "arabeskx", 14)


# ---------------------------------------------------------------- ISRC tamamlama (G19): LB metadata'da ISRC'si olmayan secili sanatcilarin ilk kayitlari
PHASE_BUDGET["repro"] = (0, 0, "G20: iki tohum kosusunu karsilastirir (istek yok)")
PHASE_CAPS["repro"] = (0, 0)
PHASE_BUDGET["isrcfill"] = (0, 25, "G19: ISRC'siz secili sanatcilarin en cok dinlenen kayitlari icin MB rid: ISRC tamamlama")
PHASE_CAPS["isrcfill"] = (0, 25)
ISRCFILL_PER_ARTIST = 8


def isrcfill_targets(state, cache, g, per=ISRCFILL_PER_ARTIST):
    """Secili (artist_sel/_wide) ve dislanmamis sanatcilardan hic ISRC'li kaydi olmayanlarin ilk `per` onbellek kaydi."""
    excl = set(state.get("artist_excl", {}).get(g, []))
    out = []
    for key in ("artist_sel", "artist_sel_wide"):
        for a in state.get(key, {}).get(g, []):
            tr = state.get("toprec", {}).get(a, [])
            if a in excl or not tr or any((cache.get(m_) or {}).get("isrcs") for m_, _n in tr):
                continue
            out += [m_ for m_, _n in tr[:per] if m_ in cache and cache[m_].get("src") != "mb_404"]
    return list(dict.fromkeys(out))


def run_isrcfill(args):
    store, token, budget, rq = _start(args, "isrcfill")
    errors, interrupted, got = 0, None, 0
    gs = [x.strip() for x in args.genres.split(",")] if args.genres else [ARABX_G]
    todo = list(dict.fromkeys(m_ for g in gs for m_ in isrcfill_targets(store.state, store.cache, g)))
    print(f"isrcfill: {len(todo)} kayit, {-(-len(todo) // RID_BATCH)} MB istegi")
    try:
        with store:
            for i in range(0, len(todo), RID_BATCH):
                chunk = todo[i:i + RID_BATCH]
                code, body, _ = rq.call_retry("rid", "mb", "GET", f"{MB}/recording",
                                              {"query": "rid:(" + " OR ".join(chunk) + ")", "limit": 100, "fmt": "json"})
                if code != 200 or not isinstance(body, dict):
                    errors += 1
                    break
                for r in body.get("recordings", []):
                    m_ = r.get("id")
                    isr = parse_mb_recording(r).get("isrcs")
                    if m_ in chunk and isr:
                        store.cache[m_] = {**store.cache[m_], "isrcs": isr, "isrc_src": "mb_rid"}
                        got += 1
                store.flush()
    except (KeyboardInterrupt, BudgetExceeded) as e_:
        interrupted = repr(e_)
    _report_tail("isrcfill", rq, budget, store, token, errors, interrupted, {"targets": len(todo), "filled": got})
    print(f"isrcfill: {got}/{len(todo)} kayda ISRC eklendi; hata={errors}")
    return 2 if (interrupted or errors) else 0


# ---------------------------------------------------------------- Tekrarlanabilirlik (G20): ikinci tohum kosusu karsilastirmasi (istek yok)
REPRO_GENRES = ("turk halk", "turkce rap", "arabesk", "anadolu rock")
REPRO_MARK_FILES = {"turk halk": ("lb_sample_tr_turk_halk.md", "lb_sample_tr_turk_halk_v2.md"),
                    "turkce rap": ("lb_sample_tr_turkce_rap.md", "lb_sample_tr_turkce_rap_v2.md"),
                    "arabesk": EXCL_GENRES["arabesk"], "anadolu rock": EXCL_GENRES["anadolu rock"]}


def jaccard_sets(a, b):
    a, b = set(a), set(b)
    return round(len(a & b) / len(a | b), 4) if (a | b) else None


def artist_labels(recs, marked):
    """kayit isaretlerinden sanatci etiketi: {sanatci: True(uygun) / False(uygun degil: [x] cogunlukta)}; isaretsiz yok."""
    ok, bad = Counter(), Counter()
    for r in recs:
        if r["mbid"] in marked:
            (ok if marked[r["mbid"]] else bad)[r["artist_mbid"]] += 1
    return {a: not (bad[a] > ok[a]) for a in set(ok) | set(bad)}


def pre_mark_pool(state, cache, g):
    """Isaret dislamasi oncesi sanatci kumesi (arabesk/rock: yalniz MB ulke dislamasi; halk/rap: kayitli artist_excl)."""
    if g in ("arabesk", "anadolu rock"):
        meta = state.get("artist_meta", {})
        ex = sorted(compute_excl({a: meta[a] for a in pool_artists(state, cache, g) if a in meta}, g))
        state = {**state, "artist_excl": {**state.get("artist_excl", {}), g: ex}}
    return isrcd_recs(state, cache, g)[0]


def repro_compare(run_a, run_b, g, labels, gate_a, gate_b):
    """run_*: (state, cache). labels: ortak isaretlerden sanatci etiketleri. A_duz yalniz isaretli ortak sanatci oranindan."""
    out = {"genre": g}
    for tag, (st, ca), gr in (("run1", run_a, gate_a), ("run2", run_b, gate_b)):
        recs = isrcd_recs(st, ca, g)[0]
        pre = pre_mark_pool(st, ca, g)
        pre_arts = {r["artist_mbid"] for r in pre}
        lab = {a: labels[a] for a in pre_arts if a in labels}
        n_ok = sum(lab.values())
        blk = {"n": len(lab), "ok": n_ok}
        lo, hi = wilson(n_ok, len(lab)) if lab else (0.0, 0.0)
        A_pre = len(pre_arts)
        out[tag] = {"C": gr.get("C"), "A": gr.get("A"), "top_share": gr.get("top_share"), "verdict": gr.get("verdict"),
                    "pool_A": len({r["artist_mbid"] for r in recs}), "A_pre": A_pre,
                    "marked": len(lab), "unmarked": A_pre - len(lab), "rate": round(n_ok / len(lab), 4) if lab else None,
                    "A_duz": round(A_pre * n_ok / len(lab), 1) if lab else None,
                    "A_duz_ci": [round(A_pre * lo, 1), round(A_pre * hi, 1)] if lab else None}
    sa = {r["artist_mbid"] for r in isrcd_recs(*run_a, g)[0]}
    sb = {r["artist_mbid"] for r in isrcd_recs(*run_b, g)[0]}
    out["jaccard_pool"] = jaccard_sets(sa, sb)
    out["common"], out["only_run1"], out["only_run2"] = len(sa & sb), len(sa - sb), len(sb - sa)
    out["verdict_changed"] = out["run1"]["verdict"] != out["run2"]["verdict"]
    return out


def run_repro(args):
    import common
    d1, d2 = Path(common.OUT), Path(args.repro_dir)
    res = []
    marks_cache = {}
    for g in REPRO_GENRES:
        s1, c1 = _load_json(d1 / "lb_probe2_state.json", {}), _load_json(d1 / "lb_probe2_cache.json", {})
        s2, c2 = _load_json(d2 / "lb_probe2_state.json", {}), _load_json(d2 / "lb_probe2_cache.json", {})
        gate = lambda d: {r["genre"]: r for r in _load_json(sorted(d.glob("lb_probe2_gate_2*.json"))[-1], {}).get("genres", [])}
        texts = [(d1 / f).read_text(encoding="utf-8") for f in REPRO_MARK_FILES[g] if (d1 / f).exists()]
        marked = load_marks(texts)
        recs_all = pre_mark_pool(s1, c1, g) + pre_mark_pool(s2, c2, g) + isrcd_recs(s1, c1, g)[0] + isrcd_recs(s2, c2, g)[0]
        labels = artist_labels(recs_all, marked)
        res.append(repro_compare((s1, c1), (s2, c2), g, labels, gate(d1).get(g, {}), gate(d2).get(g, {})))
    stamp = time.strftime("%Y%m%d_%H%M%S")
    L = ["# Tekrarlanabilirlik: tohum 7 (birincil) ve tohum 2", "",
         "| Tur | Kosu | C | A | pay | karar | A_pre | isaretli / isaretsiz | oran | A_duz [Wilson] |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in res:
        for tag in ("run1", "run2"):
            x = r[tag]
            L.append(f"| {r['genre']} | {tag} | {x['C']} | {x['A']} | {x['top_share']} | {x['verdict']} | {x['A_pre']} | "
                     f"{x['marked']} / {x['unmarked']} | {x['rate']} | {x['A_duz']} {x['A_duz_ci']} |")
    L += ["", "| Tur | Jaccard (havuz sanatcilari) | ortak | yalniz run1 | yalniz run2 | karar degisti mi |", "|---|---|---|---|---|---|"]
    for r in res:
        L.append(f"| {r['genre']} | {r['jaccard_pool']} | {r['common']} | {r['only_run1']} | {r['only_run2']} | {r['verdict_changed']} |")
    md = chr(10).join(L) + chr(10)
    safe_write(d1 / f"lb_probe2_repro_{stamp}.json", json.dumps(res, ensure_ascii=False, indent=1))
    safe_write(d1 / f"lb_probe2_repro_{stamp}.md", md)
    print(ascii_safe(md))
    print(f"yazildi: lb_probe2_repro_{stamp}.json / .md")
    return 0


# ---------------------------------------------------------------- CLI (G1)

def _genre_filter(args):
    names = [g for g, _ in GENRES]
    if args.genres:
        wanted = [g.strip() for g in args.genres.split(",") if g.strip()]
        bad = [g for g in wanted if g not in names]
        if bad:
            raise SystemExit(f"bilinmeyen tur: {bad}; gecerli: {names}")
        return set(wanted)
    if args.scope == "tr":
        return set(TR_GENRES)
    if args.scope == "nontr":
        return set(names) - set(TR_GENRES)
    return None


def build_parser():
    ap = argparse.ArgumentParser(description="PR-0 ek prob (SPEC v2.2); bu surum: offline + iskelet")
    ap.add_argument("--phase", choices=list(PHASE_BUDGET), required=True)
    ap.add_argument("--scope", choices=("tr", "nontr", "all"), default="all")
    ap.add_argument("--genres", help="virgullu tur adlari (GENRES icindeki ad)")
    ap.add_argument("--sample", type=int, default=0, help="tabaka basina ornek; 0 = tam")
    ap.add_argument("--repro-dir", default=str(OUT / "seed2"), help="repro: ikinci tohum kosusunun dizini")
    ap.add_argument("--out-dir", default=None, help="cikti/durum dizini (varsayilan spikes/out); ikinci tohum kosusu icin ayri dizin")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--only-new", action="store_true", help="sample: yalniz genisletmeyle gelen yeni sanatcilar")
    ap.add_argument("--suffix", default="", help="sample: dosya adi eki (ornek _v2)")
    ap.add_argument("--max-per-art", type=int, default=0, help="sample: sanatci basina en cok kayit (0=sinirsiz)")
    ap.add_argument("--n-rec", type=int, default=0, help="sample: kayit sayisi (0=varsayilan)")
    ap.add_argument("--max-lb", type=int, default=600)
    ap.add_argument("--max-mb", type=int, default=1200)
    ap.add_argument("--max-lf", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="istek atmaz, faz butcelerini basar")
    ap.add_argument("--session-size", type=int, default=20)
    ap.add_argument("--artist-cap", type=int, default=5)
    ap.add_argument("--top-k", type=int, default=30, help="D: sanatci basina en cok dinlenen ilk K kayit")
    ap.add_argument("--wide", action="store_true", help="G6b: MB etiket aramasi ulke filtresiz + ek takma ad + sayfalama")
    ap.add_argument("--tag-pages", type=int, default=3, help="G6b: takma ad basina en cok sayfa (100'luk)")
    ap.add_argument("--artists-per-genre", type=int, default=0, help="D: tur basina sanatci (0=varsayilan)")
    ap.add_argument("--resolve-cap", type=int, default=NT_RESOLVE_CAP, help="G8: tur basina cozulecek en cok MBID")
    ap.add_argument("--allow-lastfm", action="store_true")
    ap.add_argument("--allow-deezer", action="store_true", help="KAPALI: spike'ta kullanilmaz (K5)")
    ap.add_argument("--force-unlock", action="store_true")
    return ap


def dry_run(args):
    print(f"DRY-RUN: istek yok; faz={args.phase} scope={args.scope} seed={args.seed} N={args.session_size} "
          f"m={args.artist_cap} max(lb/mb/lf)={args.max_lb}/{args.max_mb}/{args.max_lf}")
    print("faz butceleri (LB / MB istek ust siniri):")
    for ph, (lb, mb, note) in PHASE_BUDGET.items():
        mark = ">>" if ph == args.phase else "  "
        over = "  ASIYOR" if lb > args.max_lb or mb > args.max_mb else ""
        print(f"{mark} {ph:<8}{lb:>4} / {mb:<4} {note}{over}")
    print("Deezer: 0 istek (kapali). Last.fm:", "izinli" if args.allow_lastfm else "kapali")
    return 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    if getattr(args, "out_dir", None):  # tekrarlanabilirlik kosusu: ayri durum/onbellek/rapor dizini
        global OUT
        OUT = Path(args.out_dir).resolve()
        OUT.mkdir(parents=True, exist_ok=True)
    if args.allow_deezer:
        raise SystemExit("--allow-deezer bu spike'ta kullanilmaz (K5); Deezer'a istek atilmaz")
    if args.dry_run:
        return dry_run(args)
    if args.phase == "offline":
        return run_offline(args)
    if args.phase == "p0":
        return run_p0(args)
    if args.phase == "tags":
        return run_tags(args)
    if args.phase == "radio":
        return run_radio(args)
    if args.phase == "artist":
        return run_artist(args)
    if args.phase == "gate":
        return run_gate(args)
    if args.phase == "halkx":
        return run_halkx(args)
    if args.phase == "credits":
        return run_credits(args)
    if args.phase == "repro":
        return run_repro(args)
    if args.phase == "isrcfill":
        return run_isrcfill(args)
    if args.phase == "arabeskx":
        return run_arabeskx(args)
    if args.phase == "rockx":
        return run_rockx(args)
    if args.phase == "excl":
        return run_excl(args)
    if args.phase == "lang":
        return run_lang(args)
    if args.phase == "rapx":
        return run_rapx(args)
    if args.phase == "sample":
        return run_sample(args)
    if args.phase == "sample_eval":
        return run_sample_eval(args)
    raise SystemExit(f"faz '{args.phase}' bu surumde yok (G4+); ag fazlari henuz eklenmedi")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, BudgetExceeded) as e:
        print(f"durduruldu: {e!r}")
        sys.exit(2)
