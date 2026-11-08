"""lb_genre_probe2 birim testleri (agsiz, stdlib unittest)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lb_genre_probe2 as P  # noqa: E402

VA = P.VARIOUS_ARTISTS


def rec(i, artist, isrc=True, title=None):
    return {"recording_mbid": f"r{i}", "artist_mbid": artist, "title": title or f"t{i}",
            "isrcs": [f"TR{i:010d}"] if isrc else []}


class Pure(unittest.TestCase):
    def test_wilson(self):
        self.assertAlmostEqual(P.wilson(3, 16)[1], 0.430, places=3)
        self.assertAlmostEqual(P.wilson(1, 16)[1], 0.283, places=3)
        self.assertEqual(P.wilson(0, 0), (0.0, 1.0))

    def test_norm_title_and_marker(self):
        self.assertEqual(P.norm_title("Dağlar Dağlar 1"), "daglar daglar")
        self.assertEqual(P.version_marker("Dağlar Dağlar 1"), "num:1")
        self.assertEqual(P.norm_title("ISIK (Live)"), P.norm_title("Işık"))
        self.assertEqual(P.version_marker("Işık (Live)"), "live")
        self.assertEqual(P.version_marker("Song - Demo Remix"), "demo+remix")
        self.assertEqual(P.version_marker("Düz Şarkı"), "")
        self.assertEqual(P.norm_title("İstanbul"), P.norm_title("istanbul"))

    def test_sibling(self):
        r = {"mbid": "a", "artist_mbid": "X", "title": "Zalimsin"}
        b = [{"mbid": "a", "artist_mbid": "X", "title": "Zalimsin", "isrcs": ["SELF"]},
             {"mbid": "b", "artist_mbid": "X", "title": "Zalimsin (Live)", "isrcs": ["LIVE"]},
             {"mbid": "c", "artist_mbid": "Y", "title": "Zalimsin", "isrcs": ["OTHER"]},
             {"mbid": "d", "artist_mbid": "X", "title": "ZALİMSİN", "isrcs": ["ZZ2", "AA1"]}]
        self.assertEqual(P.sibling_isrc(r, b), ("AA1", "sibling_multi"))
        self.assertEqual(P.sibling_isrc(r, b[:3]), (None, "none"))
        self.assertEqual(P.sibling_isrc({"artist_mbid": VA, "title": "x"}, b)[1], "no_artist")

    def test_cap_and_va(self):
        rs = [rec(i, "A") for i in range(5)] + [rec(9, VA), rec(10, "B")]
        out = P.cap_per_artist(rs, 2)
        self.assertEqual([r["recording_mbid"] for r in out], ["r0", "r1", "r10"])

    def test_gate_row(self):
        rs = [rec(i, f"A{i % 16}") for i in range(20)]
        g = P.gate_row(rs, "A")
        self.assertEqual((g["C"], g["A"], g["verdict"]), (20, 16, "GEÇTİ"))
        self.assertEqual(P.gate_row(rs[:19], "A")["verdict"], "KALDI")
        rs2 = [rec(i, "A0") for i in range(30)]  # C ok, A=1
        self.assertEqual(P.gate_row(rs2, "A")["verdict"], "KALDI")
        self.assertEqual(P.gate_row(rs + [rec(99, VA)], "A")["n"], 20)  # Various Artists dislanir
        self.assertEqual(P.gate_row([], "A")["verdict"], "ÖLÇÜLMEDİ")
        self.assertEqual(P.gate_row(None, "A")["verdict"], "ÖLÇÜLMEDİ")
        dup = [rec(1, "A"), dict(rec(2, "B"), isrcs=rec(1, "A")["isrcs"])]
        self.assertEqual(P.gate_row(dup, "A")["C"], 1)  # ayni ISRC tek aday
        # ornek: 16 kayit, 6 ISRC'li, nufus 100 -> C ~ 37, aralik 20'yi icerir
        samp = [rec(i, f"A{i}", isrc=i < 6) for i in range(16)]
        self.assertEqual(P.gate_row(samp, "A", population=100)["verdict"], "SINIRDA")

    def test_program_gate(self):
        def rows(tr, non):
            return ([{"genre": f"t{i}", "tr": True, "verdict": v} for i, v in enumerate(tr)] +
                    [{"genre": f"n{i}", "tr": False, "verdict": v} for i, v in enumerate(non)])
        G, K, S = "GEÇTİ", "KALDI", "SINIRDA"
        r = P.program_gate(rows([G] * 5, [G] * 11 + [K] * 4))
        self.assertEqual((r["verdict"], r["robust"]), ("GEÇTİ", True))
        r = P.program_gate(rows([G] * 4 + [K], [G] * 15))  # Turkce 4/5 gecersiz (K1)
        self.assertEqual((r["verdict"], r["robust"]), ("KALDI", True))
        r = P.program_gate(rows([G] * 4 + [S], [G] * 15))
        self.assertEqual((r["verdict"], r["robust"]), ("SINIRDA", False))
        self.assertEqual(P.program_gate(rows([G] * 5, []))["verdict"], "GEÇTİ")  # E2: yalniz Turkce

    def test_diagnose(self):
        base = {"A": 20, "top_share": 0.1, "isrc_rate_record": 0.8, "isrc_rate_artist": 0.9}
        self.assertEqual(P.diagnose(base), "yok")
        self.assertEqual(P.diagnose(dict(base, A=10)), "etiket")
        self.assertEqual(P.diagnose(dict(base, top_share=0.5)), "etiket")
        gap = dict(base, isrc_rate_record=0.3)
        self.assertEqual(P.diagnose(dict(gap, sibling_closes=True)), "sürüm_açığı")
        self.assertEqual(P.diagnose(dict(gap, sibling_closes=False)), "isrc_açığı")
        self.assertEqual(P.diagnose(dict(gap, A=5)), "ikisi")

    def test_depth_chao1(self):
        self.assertEqual(P.depth(1000, 60, 5, 20), 15)
        self.assertEqual(P.depth(1000, 300, 5, 20), 50)
        self.assertEqual(P.chao1([1, 1, 2, 2, 3]), 5 + 4 / 4)
        self.assertEqual(P.chao1([1, 1, 1, 3]), 4 + 3)  # f2=0 -> S + f1(f1-1)/2
        self.assertEqual(P.chao1([]), 0)
        self.assertAlmostEqual(P.saturation([1, 1, 2, 2]), 0.25)

    def test_pop_tier(self):
        t = P.pop_tier({"a": 1, "b": 5, "c": 9, "d": 20, "e": 30, "f": 99})
        self.assertEqual([t[k] for k in "abcdef"], ["nis", "nis", "orta", "orta", "populer", "populer"])
        g = P.gate_row([rec(i, f"A{i}") for i in range(6)], "A", listens={f"A{i}": i for i in range(6)})
        self.assertEqual(g["A_niche"], 2)

    def _variant(self, gate_ok, min_d, other_d, cps=1.0):
        v = "GEÇTİ" if gate_ok else "KALDI"
        rows = [{"genre": f"t{i}", "tr": True, "verdict": v, "D": (min_d if i == 0 else other_d),
                 "niche_full": True, "H": 0.1, "cand_per_sec": cps} for i in range(5)]
        return rows

    def test_feed_score_and_rank(self):
        bad = P.feed_score(self._variant(False, 99, 99))
        a = P.feed_score(self._variant(True, 10, 10))
        b = P.feed_score(self._variant(True, 10, 20))  # min D esit, Turkce toplam D belirler
        c = P.feed_score(self._variant(True, 5, 90))
        self.assertTrue(bad < c < a < b)
        g = [{"strategy": "bad", "rows": self._variant(False, 99, 99), "points": [P.growth_point("bad", 1, 1, 5, 5, 1)]},
             {"strategy": "A", "rows": self._variant(True, 10, 10), "points": [P.growth_point("A", 1, 10, 100, 20, 5)]},
             {"strategy": "B", "rows": self._variant(True, 10, 10), "points": [P.growth_point("B", 1, 2, 100, 20, 5)]},
             {"strategy": "C", "rows": self._variant(True, 10, 20), "points": [P.growth_point("C", 1, 50, 100, 20, 5)]}]
        self.assertEqual([x["strategy"] for x in P.rank_strategies(g)], ["C", "B", "A", "bad"])  # esitlikte aday/sn


class Infra(unittest.TestCase):
    def test_safe_write_protected(self):
        with tempfile.TemporaryDirectory() as d:
            for name in P.PROTECTED:
                with self.assertRaises(SystemExit):
                    P.safe_write(Path(d) / name, "x")
                self.assertFalse((Path(d) / name).exists())
            P.safe_write(Path(d) / "ok.json", "{}")
            self.assertEqual((Path(d) / "ok.json").read_text(), "{}")
            self.assertFalse((Path(d) / "ok.json.tmp").exists())

    def test_lock_excl(self):
        with tempfile.TemporaryDirectory() as d:
            s1 = P.Store(d)
            s1.acquire()
            with self.assertRaises(SystemExit):
                P.Store(d).acquire()
            P.Store(d, force_unlock=True).acquire()  # --force-unlock
            s1.release()

    def test_store_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "lb_mb_cache.json").write_text(json.dumps({"m1": {"isrcs": ["X"]}}))
            with P.Store(d) as s:
                self.assertEqual(s.lookup("m1"), {"isrcs": ["X"]})
                s.put("m2", {"isrcs": []})
                s.mark_done("p0|a")
            self.assertFalse((Path(d) / "lb_probe2.lock").exists())
            s2 = P.Store(d)
            self.assertTrue(s2.done("p0|a"))
            self.assertIn("m2", s2.cache)
            self.assertEqual(json.loads((Path(d) / "lb_mb_cache.json").read_text()), {"m1": {"isrcs": ["X"]}})

    def test_budget(self):
        b = P.Budget(lb=2, mb=1)
        b.spend("lb")
        b.spend("lb")
        with self.assertRaises(P.BudgetExceeded):
            b.spend("lb")
        with self.assertRaises(P.BudgetExceeded):
            b.spend("lf")

    def test_budget_total_and_scrub(self):
        b = P.Budget(lb=5, mb=5, total=3)
        for _ in range(3):
            b.spend("lb")
        with self.assertRaises(P.BudgetExceeded):
            b.spend("mb")
        self.assertEqual(P._scrub("Token abc xyz9", "xyz9"), "Token_abc ***")

    def test_source_hygiene(self):
        src = (Path(P.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("os.kill" + "(", src)
        self.assertNotIn("DATABASE_URL", src)
        self.assertNotIn("psycopg", src)
        self.assertNotIn("deezer.com", src)

    def test_cli(self):
        a = P.build_parser().parse_args(["--phase", "offline"])
        self.assertFalse(a.allow_deezer)
        self.assertEqual((a.session_size, a.seed, a.artist_cap), (20, 7, 5))
        with self.assertRaises(SystemExit):
            P.main(["--phase", "offline", "--allow-deezer"])


class StubRq:
    """Ag yerine hazir yanit donen Requester taklidi."""

    def __init__(self, meta=None, rid=None, lookup=None):
        self.meta, self.rid, self.lookup, self.calls = meta or {}, rid or [], lookup or {}, []

    def call_retry(self, unit, kind, method, url, params=None, post=None, **kw):
        self.calls.append(unit)
        if unit == "meta":
            return 200, {m: self.meta[m] for m in post["recording_mbids"] if m in self.meta}, {}
        if unit == "rid":
            return 200, {"recordings": self.rid}, {}
        m = url.rsplit("/", 1)[1]
        return (200, self.lookup[m], {}) if m in self.lookup else (404, {}, {})


def lb_entry(title, artist, am, isrcs):
    return {"artist": {"name": artist, "artists": [{"artist_mbid": am, "name": artist}]},
            "recording": {"name": title, "isrcs": isrcs}}


class G5(unittest.TestCase):
    def test_aliases_cover_tr_genres(self):
        self.assertEqual(set(P.TR_ALIASES), set(P.TR_GENRES))
        self.assertEqual(sum(len(v) for v in P.TR_ALIASES.values()), 24)

    def test_accept_alias(self):
        self.assertTrue(P.accept_alias(20, 0, 0.0))
        self.assertFalse(P.accept_alias(19, 14, 0.9))
        self.assertTrue(P.accept_alias(5, 15, 0.5))
        self.assertFalse(P.accept_alias(5, 15, 0.49))
        self.assertFalse(P.accept_alias(100, 3, 0.1, noisy=True))   # arabesque gurultusu
        self.assertTrue(P.accept_alias(100, 30, 0.8, noisy=True))

    def test_reps(self):
        a = set(range(100))
        self.assertTrue(P.need_more_reps([]))
        self.assertTrue(P.need_more_reps([a]))
        self.assertFalse(P.need_more_reps([a, set(a)]))                       # deterministik
        self.assertTrue(P.need_more_reps([a, set(range(50, 200))]))           # kazanc 100/100
        self.assertFalse(P.need_more_reps([a, set(range(5, 105))]))           # kazanc %5
        self.assertFalse(P.need_more_reps([a, set(range(50, 200)), a]))       # tavan 3
        self.assertEqual(P.jaccard({1, 2}, {2, 3}), 1 / 3)

    def test_parse(self):
        i = P.parse_meta_entry(lb_entry("Sarı Gelin", "Ezginin Günlüğü", "A1", ["TR1"]))
        self.assertEqual((i["title"], i["artist_mbid"], i["isrcs"]), ("Sarı Gelin", "A1", ["TR1"]))
        self.assertEqual(P.parse_meta_entry(None)["isrcs"], [])
        j = P.parse_mb_recording({"title": "T", "artist-credit": [{"artist": {"id": "A2", "name": "N"}}], "isrcs": ["X"]})
        self.assertEqual((j["artist_mbid"], j["isrcs"]), ("A2", ["X"]))

    def test_resolve_fallback_chain(self):
        with tempfile.TemporaryDirectory() as d:
            store = P.Store(d)
            rq = StubRq(meta={"m1": lb_entry("a", "X", "A1", ["I1"])},
                        rid=[{"id": "m2", "title": "b", "artist-credit": [{"artist": {"id": "A2", "name": "Y"}}], "isrcs": []}],
                        lookup={"m3": {"title": "c", "artist-credit": [{"artist": {"id": "A3", "name": "Z"}}], "isrcs": ["I3"]}})
            st, left = P.resolve_mbids(rq, store, ["m1", "m2", "m3", "m4"], 10)
            self.assertEqual((st["lb_meta"], st["mb_rid"], st["mb_single"], st["mb_404"], st["unresolved"]), (1, 1, 1, 1, 0))
            self.assertEqual(left, 8)
            self.assertEqual(store.cache["m1"]["src"], "lb_meta")
            self.assertEqual(store.cache["m3"]["isrcs"], ["I3"])
            # ikinci cagri: hepsi onbellekte, istek yok
            n = len(rq.calls)
            P.resolve_mbids(rq, store, ["m1", "m2"], 10)
            self.assertEqual(len(rq.calls), n)
            # lookup siniri
            st2, left2 = P.resolve_mbids(StubRq(), P.Store(d + "/x" if False else d), ["m9"], 0)
            self.assertEqual((st2["unresolved"], left2), (1, 0))

    def test_genre_summary(self):
        cache = {f"m{i}": {"title": f"t{i}", "artist": f"a{i % 20}", "artist_mbid": f"A{i % 20}",
                           "isrcs": [f"I{i}"] if i % 3 == 0 else [], "src": "lb_meta"} for i in range(60)}
        pool = {f"m{i}": {"top" if i < 30 else "tail"} for i in range(60)}
        pool["gone"] = {"top"}
        s = P.genre_summary(pool, cache, 20, 5, ["top", "mid", "tail"])
        self.assertEqual((s["pool"], s["resolved"], s["unresolved"]), (61, 60, 1))
        a = s["A_all_bands"]
        self.assertEqual((a["C"], a["A"], a["verdict"]), (20, 20, "GEÇTİ"))
        self.assertEqual(a["depth"], P.depth(20, 20, 5, 20))
        self.assertEqual(s["B_top_mid"]["n"], 30)
        self.assertEqual(s["per_band"]["mid"]["n"], 0)
        self.assertLessEqual(s["A_cap2"]["n"], 40)
        self.assertEqual(s["isrcless_with_meta"], 40)

    def test_ascii_safe(self):
        self.assertEqual(P.ascii_safe("türkçe"), r"t\xfcrk\xe7e")


class G6(unittest.TestCase):
    def test_select_artists_niche_share_no_cutoff(self):
        rel = {f"a{i}": float(100 - i) for i in range(30)}
        tiers = P.pop_tier({a: i for i, a in enumerate(rel)})  # a0 en az dinlenen -> nis
        ch = P.select_artists(rel, tiers, k=10, niche_share=0.3)
        self.assertEqual(len(ch), 10)
        self.assertEqual(len(set(ch)), 10)
        self.assertGreaterEqual(sum(tiers[a] == "nis" for a in ch), 3)
        self.assertEqual(ch, P.select_artists(rel, tiers, k=10, niche_share=0.3))

    def test_select_artists_fills_when_tier_short(self):
        rel = {f"a{i}": 1.0 for i in range(5)}
        ch = P.select_artists(rel, {a: "populer" for a in rel}, k=8)
        self.assertEqual(sorted(ch), sorted(rel))

    def test_sibling_close_marker_breakdown(self):
        r = [
            rec(1, "A", True, "Aşk (Live)"), rec(2, "A", False, "Aşk (Live)"),
            rec(3, "A", True, "Yol"), rec(4, "A", False, "Yol (Remix)"),
            rec(5, "B", False, "Yol"), rec(6, "A", False, "Yol"),
        ]
        e = P.sibling_close(r)
        self.assertEqual(e["isrcless"], 4)
        self.assertEqual(e["closed_n"], 2)  # r2 (live) ve r6 (isaretsiz)
        self.assertEqual(e["by_marker"], {"live": 1, "(isaret yok)": 1})
        self.assertEqual(e["relaxed_marker_diff"], 1)  # r4: remix, kardeste yok
        self.assertEqual(e["new_unique_isrc"], 0)  # kardesin ISRC'si zaten havuzda
        self.assertNotIn("r5", e["closed"])  # baska sanatci

    def test_de_summary_before_after(self):
        cache = {}
        radio = {}
        for i in range(10):
            cache[f"m{i}"] = {"title": f"s{i}", "artist_mbid": f"ar{i % 2}", "isrcs": [f"I{i}"] if i < 2 else [], "src": "lb_meta"}
            radio[f"m{i}"] = {"top"}
        dpool = {}
        for i in range(10, 40):
            cache[f"m{i}"] = {"title": f"s{i}", "artist_mbid": f"ar{i}", "isrcs": [f"I{i}"], "src": "lb_meta"}
            dpool[f"m{i}"] = {"D"}
        listens = {f"ar{i}": i for i in range(10, 40)}
        res = P.de_summary(radio, dpool, cache, listens, 20, 5)
        self.assertEqual((res["T1"]["C"], res["T1"]["A"]), (2, 2))
        self.assertEqual((res["T1+D"]["C"], res["T1+D"]["A"]), (32, 32))
        self.assertEqual(res["T1+D"]["verdict"], "GEÇTİ")
        self.assertGreater(res["T1+D"]["depth"], res["T1"]["depth"])
        self.assertGreaterEqual(res["T1+D"]["A_niche"], 5)
        self.assertTrue(res["T1+D"]["niche_full"])
        self.assertIn("rate_after", res["E"])

    def test_growth_point_sec_none(self):
        self.assertIsNone(P.growth_point("T1", 3, None, 1, 1, 0)["sec"])


class G7(unittest.TestCase):
    def test_wide_candidates(self):
        w, ex = P.wide_candidates([["a", "TR"], ["b", None], ["c", "DE"], ["a", None], ["d", ""]])
        self.assertEqual(w, {"a": 0.5, "b": 0.3, "d": 0.3})
        self.assertEqual(ex, 1)

    def test_selection_nontr(self):
        class A:
            scope, genres = "nontr", None
        sel = P._tr_selection(A)
        self.assertEqual(len(sel), 15)
        self.assertFalse(set(sel) & set(P.TR_GENRES))
        self.assertIn("trap", sel)

    def test_final_verdict(self):
        ok = {"n": 50, "C": 30, "A": 20, "top_share": 0.2, "ci": [0.1, 0.3]}
        self.assertEqual(P.final_verdict(ok), ("GEÇTİ", []))
        v, why = P.final_verdict({**ok, "top_share": 0.5})
        self.assertEqual(v, "KALDI")
        self.assertIn("pay", why[0])
        v, _ = P.final_verdict({**ok, "A": 5})
        self.assertEqual(v, "KALDI")
        # ornekli T1: C alt sinir 10, Wilson ust sinirindan extrapole C>=20 -> SINIRDA
        lo = {"n": 100, "C": 10, "A": 16, "top_share": 0.1, "ci": [0.05, 0.2]}
        self.assertEqual(P.final_verdict(lo, sampled_pop=3000)[0], "SINIRDA")
        self.assertEqual(P.final_verdict(lo, sampled_pop=3000, has_d=True)[0], "KALDI")
        self.assertEqual(P.final_verdict({"n": 0})[0], "ÖLÇÜLMEDİ")

    def test_build_gate_and_totals(self):
        cache, raw = {}, {}
        rows = []
        for i in range(60):
            cache[f"m{i}"] = {"title": f"s{i}", "artist_mbid": f"ar{i}", "isrcs": [f"I{i}"], "src": "lb_meta"}
            rows.append([f"m{i}", 1, 0, "x"])
        raw["radio|arabesk|top|0"] = rows
        state = {"radio_raw": raw, "pool_size": {}, "artist_pop": {}, "toprec": {}}
        out, pg, rank = P.build_gate(state, cache, {}, 20, 5)
        self.assertEqual(len(out), 20)
        ar = out[0]
        self.assertEqual((ar["genre"], ar["verdict"], ar["best"], ar["C"], ar["A"]), ("arabesk", "GEÇTİ", "T1", 60, 60))
        self.assertEqual(out[1]["verdict"], "ÖLÇÜLMEDİ")
        self.assertEqual(pg["verdict"], "SINIRDA")  # 19 olculmedi: iyimser gecer
        self.assertEqual(len(rank), 3)
        md = P.gate_markdown(out, pg, rank, {"tags": {"lb": 3, "mb": 2, "files": 1}}, {"lb": 3, "mb": 2, "files": 1, "requests": 5}, 20, 5)
        self.assertIn("arabesk", md)
        self.assertIn("5 istek", md)

    def test_request_totals(self):
        with tempfile.TemporaryDirectory() as d:
            for name, lb, mb in (("p0_20260101_000001", 2, 3), ("p0_20260101_000002", 1, 0), ("artist_wide_20260101_000003", 5, 4),
                                 ("gate_20260101_000004", 0, 0)):
                Path(d, f"lb_probe2_{name}.json").write_text(json.dumps({"meta": {"used": {"lb": lb, "mb": mb}}}), encoding="utf-8")
            per, total = P.request_totals(d)
            self.assertEqual(per["p0"], {"lb": 3, "mb": 3, "files": 2})
            self.assertEqual(total["requests"], 15)
            self.assertNotIn("gate", per)


class Offline(unittest.TestCase):
    def test_offline_synthetic(self):
        recs = [{"recording_mbid": f"m{i}", "percent": 0 if i == 0 else 50.0, "source": "artist",
                 "tag_count": 5 - i, "isrcs": ["X"] if i < 2 else [], "title": f"s{i} (Live)" if i == 3 else f"s{i}",
                 "artist": "A", "artist_mbid": f"a{i % 2}"} for i in range(4)]
        probe = {"radio": [{"genre": "arabesk", "band": "top", "records": recs}]}
        rep = P.offline_analysis(probe, {})
        g = rep["per_genre"][0]
        self.assertEqual((g["all"]["n"], g["all"]["ok"]), (4, 2))
        self.assertEqual(rep["v3_percent"]["percent_0_or_100"], 1)
        self.assertEqual(rep["v2_order"]["bands_tag_count_non_increasing"], 1)
        self.assertEqual(rep["marker_x_isrc"]["live"]["n"], 1)


class G10Sample(unittest.TestCase):
    """Elle ornekleme: uretim (tohumlu, kaynak etiketi) + isaretli md'den isabet orani / A duzeltmesi. Ag yok."""

    @staticmethod
    def fixture():
        art = {f"a{i}": f"00000000-0000-0000-0000-{i:012d}" for i in range(6)}
        cache, rows_t, rows_a = {}, [], []
        for i in range(12):
            m = f"m{i:02d}"
            cache[m] = {"title": f"\u015eark\u0131 {i}|x", "artist": f"Sanat\u00e7\u0131 {i % 6}",
                        "artist_mbid": art[f"a{i % 6}"], "isrcs": [f"TR{i:010d}"], "src": "lb"}
        for i in range(12, 14):  # ISRC'siz: elenmeli
            cache[f"m{i:02d}"] = {"title": "t", "artist": "s", "artist_mbid": art["a0"], "isrcs": [], "src": "lb"}
        state = {"radio_raw": {"radio|g|top|0": [[f"m{i:02d}", 1, 1, "x"] for i in range(0, 3)],
                               "radio|g|and-a+b|0": [[f"m{i:02d}", 1, 1, "x"] for i in range(2, 6)]},
                 "artist_sel": {"g": [art["a4"], art["a5"]]},
                 "toprec": {art["a4"]: [["m08", 9], ["m09", 5]], art["a5"]: [["m10", 7], ["m11", 3]]},
                 "artist_pop": {a: 100 * (k + 1) for k, a in enumerate(art.values())}}
        return state, cache

    def test_source_labels_and_filter(self):
        state, cache = self.fixture()
        d = P.build_sample(state, cache, "g", n_rec=99, n_art=99)
        src = {r["mbid"]: r["source"] for r in d["records"]}
        self.assertEqual(src["m00"], "etiket")
        self.assertEqual(src["m02"], "etiket")  # hem etiket hem AND -> etiket
        self.assertEqual(src["m04"], "AND")
        self.assertEqual(src["m08"], "D-sanatci")
        self.assertNotIn("m12", src)
        self.assertEqual(d["isrcd_records"], len(src))

    def test_seeded_deterministic_and_artist_top_record(self):
        state, cache = self.fixture()
        a = P.build_sample(state, cache, "g", n_rec=5, n_art=3, seed=7)
        b = P.build_sample(state, cache, "g", n_rec=5, n_art=3, seed=7)
        self.assertEqual([r["mbid"] for r in a["records"]], [r["mbid"] for r in b["records"]])
        self.assertEqual(len(a["records"]), 5)
        full = P.build_sample(state, cache, "g", n_rec=5, n_art=99)
        top = {r["artist_mbid"]: r["mbid"] for r in full["artists"]}
        self.assertEqual(top["00000000-0000-0000-0000-000000000004"], "m08")  # toprec'in basi

    def test_markdown_roundtrip_and_unicode(self):
        state, cache = self.fixture()
        d = P.build_sample(state, cache, "g", n_rec=6, n_art=4)
        md = P.sample_markdown(d)
        self.assertIn("uygun = bu tur ve Turkce sarki", md)
        self.assertIn("\u015eark\u0131", md)
        self.assertNotIn("x|x", md)  # '|' hucre icinde kacirilir
        p = P.parse_sample_md(md)
        self.assertEqual(p["genre"], "g")
        self.assertEqual(sum(r["section"] == "kayit" for r in p["rows"]), 6)
        self.assertEqual(sum(r["section"] == "sanatci" for r in p["rows"]), 4)
        self.assertTrue(all(r["ok"] for r in p["rows"]))  # bos kutu = uygun

    def test_hit_rates_and_a_correction(self):
        state, cache = self.fixture()
        d = P.build_sample(state, cache, "g", n_rec=99, n_art=99)
        md = P.sample_markdown(d)
        lines, marked = md.splitlines(), 0
        for k, ln in enumerate(lines):  # kayit bolumunde AND ve D-sanatci satirlarini uygun degil yap
            if "## Sanatci" in ln:
                break
            if ln.startswith("| ") and (" | AND | " in ln or " | D-sanatci | " in ln):
                lines[k] = ln.replace("[ ]", "[x]", 1)
                marked += 1
        self.assertGreater(marked, 0)
        h = P.hit_rates(P.parse_sample_md("\n".join(lines)))
        ks = h["kayit"]["kaynak"]
        self.assertEqual(ks["AND"]["ok"], 0)
        self.assertEqual(ks["D-sanatci"]["rate"], 0.0)
        self.assertEqual(ks["etiket"]["rate"], 1.0)
        g = h["kayit"]["genel"]
        self.assertEqual(g["n"], len(d["records"]))
        self.assertEqual(g["ok"], ks["etiket"]["n"])
        lo, hi = P.wilson(g["ok"], g["n"])
        self.assertEqual(g["ci"], [round(lo, 4), round(hi, 4)])
        res = P.evaluate_samples({"g": "\n".join(lines)}, {"g": 40})
        self.assertEqual(res["g"]["A_basis"], "sanatci")  # sanatci bolumu hep uygun -> oran 1
        self.assertEqual(res["g"]["A_correction"]["A_corr"], 40.0)

    def test_a_corrected_math(self):
        blk = {"n": 25, "ok": 20, "rate": 0.8, "ci": [0.6, 0.9]}
        c = P.a_corrected(34, blk)
        self.assertEqual(c["A_corr"], 27.2)
        self.assertEqual(c["A_corr_ci"], [20.4, 30.6])
        self.assertTrue(c["passes_A15"])
        self.assertFalse(P.a_corrected(20, {"n": 10, "ok": 5, "rate": 0.5, "ci": [0.24, 0.76]})["passes_A15"])
        self.assertIsNone(P.a_corrected(30, {"n": 0, "ok": 0, "rate": None, "ci": [0, 1]}))

    def test_upper_x_and_empty(self):
        md = "# Elle ornekleme: g\n\n## Kayit duzeyi (2)\n\n| # | isaret | s | b | kaynak | t | m |\n|---|---|---|---|---|---|---|\n" \
             "| 1 | [X] | a | b | AND | nis | m1 |\n| 2 | [ ] | a | b | AND | nis | m2 |\n"
        h = P.hit_rates(P.parse_sample_md(md))
        self.assertEqual((h["kayit"]["genel"]["n"], h["kayit"]["genel"]["ok"]), (2, 1))
        self.assertEqual(h["sanatci"]["genel"]["n"], 0)



class G12Credits(unittest.TestCase):
    """feat./& kredi ayristirma: sanatci sayimi birincil sanatciya gore. Ag yok."""

    ENTRY = {"recording": {"name": "x", "isrcs": ["TR1"]},
             "artist": {"name": "Saian feat. Patron & Z", "artists": [
                 {"artist_mbid": "A1", "name": "Saian", "join_phrase": " feat. "},
                 {"artist_mbid": "A2", "name": "Patron", "join_phrase": " & "},
                 {"artist_mbid": "A3", "name": "Z", "join_phrase": ""},
                 {"name": "mbidsiz"}]}}

    def test_parse_meta_keeps_full_credit(self):
        i = P.parse_meta_entry(self.ENTRY)
        self.assertEqual(i["artist_mbid"], "A1")
        self.assertEqual([a[0] for a in i["artists"]], ["A1", "A2", "A3"])
        self.assertEqual(i["artists"][0][2], " feat. ")

    def test_primary_artist_rules(self):
        i = P.parse_meta_entry(self.ENTRY)
        self.assertEqual(P.primary_artist(i, ["top"]), "A1")  # radyo: kredinin ilki
        self.assertEqual(P.primary_artist(i, ["D", "D@A2"]), "A2")  # tohum sanatci krediler arasinda
        self.assertEqual(P.primary_artist(i, ["D", "D@A9"]), "A1")  # tohum kredide yok -> ilk
        self.assertEqual(P.primary_artist({"artist_mbid": "Q"}, ["D@A2"]), "Q")  # eski onbellek: artists yok

    def test_pool_recs_attributes_to_seed_and_shrinks_A(self):
        cache = {}
        for k in range(4):  # 4 kayit, hepsi "Yabanci feat. Tohum"; kredi-ilk yontemde 4 farkli sanatci
            cache[f"r{k}"] = {"title": "t", "artist": "x", "artist_mbid": f"F{k}", "isrcs": [f"I{k}"],
                              "artists": [[f"F{k}", "f", " feat. "], ["SEED", "s", ""]]}
        old = P._pool_recs({m: {"D"} for m in cache}, cache)
        new = P._pool_recs({m: {"D", "D@SEED"} for m in cache}, cache)
        self.assertEqual(P.gate_row(old, "x")["A"], 4)
        g = P.gate_row(new, "x")
        self.assertEqual((g["A"], g["C"]), (1, 4))
        self.assertEqual(g["top_share"], 1.0)

    def test_credit_targets_only_isrcd_without_artists(self):
        st = {"radio_raw": {"radio|turkce rap|top|0": [["a", 1, 1, "x"], ["b", 1, 1, "x"], ["c", 1, 1, "x"]],
                            "radio|house|top|0": [["h", 1, 1, "x"]]}}
        cache = {"a": {"isrcs": ["I"], "src": "lb_meta"}, "b": {"isrcs": ["I"], "artists": [], "src": "lb_meta"},
                 "c": {"isrcs": [], "src": "lb_meta"}, "h": {"isrcs": ["I"], "src": "lb_meta"}}
        self.assertEqual(P.credit_targets(st, cache), ["a"])



class G13Excl(unittest.TestCase):
    """Ulke / tur-disi dislama (halkx). Ag yok."""

    def test_offgenre_word_match(self):
        self.assertTrue(P.offgenre(["psychedelic rock"]))
        self.assertTrue(P.offgenre(["Turkish", "Alternative"]))
        self.assertFalse(P.offgenre(["turkish folk music", "ozan", "saz"]))
        self.assertFalse(P.offgenre([]))

    def test_compute_excl_country_and_genre(self):
        meta = {"fr": {"country": "FR", "tags": ["hip hop"]}, "tr_rock": {"country": "TR", "tags": ["rock"]},
                "tr_folk": {"country": "TR", "tags": ["turkish folk"]}, "empty": {"country": None, "tags": []},
                "cur": {"country": "TR", "tags": ["psychedelic folk"]}}
        self.assertEqual(P.compute_excl(meta, "turk halk", curated={"cur"}), {"fr", "tr_rock"})
        self.assertEqual(P.compute_excl(meta, "turkce rap"), {"fr"})  # tur-disi etiket yalniz halk icin

    def test_de_summary_excl_drops_artists(self):
        cache = {f"r{k}": {"title": "t", "artist": "x", "artist_mbid": f"A{k % 3}", "isrcs": [f"I{k}"], "src": "lb_meta"}
                 for k in range(6)}
        pool = {m: {"D"} for m in cache}
        full = P.de_summary({}, pool, cache, {}, 20, 5)["T1+D"]
        cut = P.de_summary({}, pool, cache, {}, 20, 5, excl={"A0"})["T1+D"]
        self.assertEqual((full["A"], full["C"]), (3, 6))
        self.assertEqual((cut["A"], cut["C"]), (2, 4))

    def test_build_sample_applies_excl_and_primary(self):
        st = {"radio_raw": {}, "artist_sel": {"g": ["S", "X"]},
              "toprec": {"S": [["m1", 5]], "X": [["m2", 4]]}, "artist_excl": {"g": ["X"]}}
        cache = {"m1": {"title": "t", "artist": "Foo feat. Seed", "artist_mbid": "F", "isrcs": ["I1"], "src": "lb_meta",
                        "artists": [["F", "Foo", " feat. "], ["S", "Seed", ""]]},
                 "m2": {"title": "u", "artist": "Bar", "artist_mbid": "X", "isrcs": ["I2"], "src": "lb_meta"}}
        d = P.build_sample(st, cache, "g", n_rec=9, n_art=9)
        self.assertEqual([r["mbid"] for r in d["records"]], ["m1"])
        self.assertEqual(d["records"][0]["artist_mbid"], "S")
        self.assertEqual(d["isrcd_artists"], 1)


class G14Lang(unittest.TestCase):
    def test_lang_of(self):
        self.assertEqual(P.lang_of(["mul", "tur", "eng"]), "tur")
        self.assertEqual(P.lang_of(["mul", "", "eng", "eng", "deu"]), "eng")
        self.assertEqual(P.lang_of(["mul", "zxx", ""]), "")
        self.assertEqual(P.lang_of(None), "")

    def test_classify(self):
        self.assertEqual(P.classify_lang("tur", False), "tur")
        self.assertEqual(P.classify_lang("kur", True), "yabanci")   # dil kesinse izin listesi onu gecmez
        self.assertEqual(P.classify_lang("", True), "izin")
        self.assertEqual(P.classify_lang("", False), "belirsiz")

    def test_allow_and_gate_no_softening(self):
        recs = [{"mbid": f"r{i}", "artist_mbid": f"A{i % 4}"} for i in range(8)]
        allow = P.allow_artists(recs, {"r0": True, "r4": False, "r1": True})
        self.assertEqual(allow, {"A1"})  # A0 hem uygun hem uygun-degil -> yok
        lm = {f"r{i}": ["tur"] if i < 6 else ["eng"] for i in range(8)}
        lm["r6"], lm["r7"] = ["eng"], [""]
        g = P.lang_gate(recs, lm, allow)
        self.assertEqual(g["classes"], {"tur": 6, "yabanci": 1, "belirsiz": 1})
        self.assertEqual(g["undetermined"], 1)
        self.assertAlmostEqual(g["mismatch_rate"], 1 / 7, places=3)
        self.assertFalse(g["pass"])  # C=6 < 20: esik ayni kalir

    def test_load_marks_any_x_wins(self):
        head = ["# Elle ornekleme: g", "## Kayit duzeyi", "| # | isaret | sanatci | baslik | kaynak | tertil | mbid |",
                "|---|---|---|---|---|---|---|"]
        a = NL.join(head + ["| 1 | [ ] | a | t | AND | nis | m1 |"])
        b = a.replace("[ ]", "[x]")
        self.assertEqual(P.load_marks([a, b]), {"m1": False})
        self.assertEqual(P.load_marks([a]), {"m1": True})


NL = chr(10)


class G15Excl(unittest.TestCase):
    def test_unfit_majority_rule(self):
        recs = [{"mbid": f"r{i}", "artist_mbid": a} for i, a in enumerate(["X", "X", "X", "Y", "Y", "Z"])]
        marked = {"r0": False, "r1": False, "r2": True, "r3": False, "r4": True, "r5": False}
        self.assertEqual(P.unfit_artists(recs, marked), {"X", "Z"})  # Y esit -> kalir

    def test_country_excl_generic_for_rock(self):
        meta = {"A": {"country": "AU", "tags": []}, "B": {"country": "TR", "tags": ["rock"]}, "C": {"country": None, "tags": []}}
        self.assertEqual(P.compute_excl(meta, "anadolu rock"), {"A"})


class G16ADuz(unittest.TestCase):
    def test_summary_point_and_lower(self):
        head = ["# Elle ornekleme: g", "## Sanatci duzeyi", "| # | isaret | sanatci | baslik | kaynak | tertil | mbid |",
                "|---|---|---|---|---|---|---|"]
        def md(n_ok, n):
            return chr(10).join(head + [f"| {i} | {'[ ]' if i <= n_ok else '[x]'} | a | t | AND | nis | m{i} |" for i in range(1, n + 1)])
        rows = [{"genre": "a", "tr": True, "verdict": "GEÇTİ", "A": 20}, {"genre": "b", "tr": True, "verdict": "GEÇTİ", "A": 20},
                {"genre": "n", "tr": False, "verdict": "GEÇTİ", "A": 20}]
        r = P.a_duz_summary(rows, {"a": md(25, 25), "b": md(15, 25)})  # b: 20*0.6=12 < 15
        self.assertEqual(r["point"], {"tr": 1, "total": 2})
        self.assertEqual(r["lower"]["tr"], 1)
        self.assertFalse(r["per_genre"]["b"]["point"])


class G17Rockx(unittest.TestCase):
    def test_build_sample_only_and_skip(self):
        st = {"radio_raw": {}, "artist_sel": {"g": ["A", "B", "C"]},
              "toprec": {"A": [["m1", 5]], "B": [["m2", 4]], "C": [["m3", 3]]}}
        cache = {m: {"title": "t", "artist": a, "artist_mbid": a, "isrcs": ["I" + m], "src": "lb_meta"}
                 for m, a in (("m1", "A"), ("m2", "B"), ("m3", "C"))}
        d = P.build_sample(st, cache, "g", n_rec=9, n_art=9, only={"B", "C"}, skip={"C"})
        self.assertEqual([r["mbid"] for r in d["records"]], ["m2"])
        self.assertEqual(d["isrcd_artists"], 1)

    def test_rockx_vocab_is_generic(self):
        self.assertTrue(all("kurd" not in x.lower() for x in P.ROCKX_TAGS + [w for p in P.ROCKX_AND for w in p]))


class G19Isrcfill(unittest.TestCase):
    def test_targets_only_isrcless_selected(self):
        st = {"artist_sel": {"g": ["A", "B", "X"]}, "artist_excl": {"g": ["X"]},
              "toprec": {"A": [["a1", 3], ["a2", 2]], "B": [["b1", 3]], "X": [["x1", 1]]}}
        cache = {"a1": {"isrcs": []}, "a2": {"isrcs": []}, "b1": {"isrcs": ["I"]}, "x1": {"isrcs": []}}
        self.assertEqual(P.isrcfill_targets(st, cache, "g", per=1), ["a1"])


class G20Repro(unittest.TestCase):
    def test_jaccard_and_labels(self):
        self.assertEqual(P.jaccard_sets({"a", "b"}, {"b", "c"}), round(1 / 3, 4))
        self.assertIsNone(P.jaccard_sets(set(), set()))
        recs = [{"mbid": "m1", "artist_mbid": "A"}, {"mbid": "m2", "artist_mbid": "A"}, {"mbid": "m3", "artist_mbid": "B"},
                {"mbid": "m4", "artist_mbid": "C"}]
        lab = P.artist_labels(recs, {"m1": True, "m2": False, "m3": False})
        self.assertEqual(lab, {"A": True, "B": False})  # A esit -> uygun; C isaretsiz -> yok


if __name__ == "__main__":
    unittest.main()
