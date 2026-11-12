
"""queue_sim saf ölçütleri: KESIF_PLANI kabul ölçütleriyle (Çeşitlilik, Tazelik) birebir."""
from app.jobs.queue_sim import (
    artist_gap_violations,
    discovery_positions,
    duplicate_keys,
    freshness_stats,
    gate,
    library_head,
    longest_run,
    max_per_window,
    metrics,
    min_window_distinct,
    overlap,
    overlap_cards,
    pair_seeds,
    queue_url,
    stage_breakdown,
    sub_runs,
    timing_summary,
)


def test_longest_run_ignores_unknown():
    assert longest_run(["a", "a", "b", "a", "a", "a"]) == 3
    assert longest_run([None, None, None, "a"]) == 1
    assert longest_run(["a", None, "a"]) == 1  # bilinmeyen seriyi böler
    assert longest_run([]) == 0


def test_min_window_distinct_is_worst_window():
    labels = ["a", "b", "c", "a", "a", "a"]
    assert min_window_distinct(labels, 3) == 1
    assert min_window_distinct(["a", None, None], 3) == 1  # bilinmeyen tür sayılmaz
    assert min_window_distinct(["a", "b"], 20) == 2  # kısa liste tek pencere


def test_max_per_window():
    assert max_per_window([1, 2, 1, 3, 1, 4], 3) == 2
    assert max_per_window([1, 2, 3, 1], 3) == 1
    assert max_per_window([None, None, None], 3) == 0


def test_artist_gap_violations():
    assert artist_gap_violations([1, 2, 3, 4, 5, 1], 4) == 0  # arada 4 kart var
    assert artist_gap_violations([1, 2, 3, 4, 1], 4) == 1
    assert artist_gap_violations([1, 1, 1], 4) == 2
    assert artist_gap_violations([None, None], 4) == 0


def test_duplicate_keys():
    assert duplicate_keys(["x", "y", "x", None, None, "x"]) == 2


def test_overlap_first_n():
    assert overlap([1, 2, 3], [3, 4, 5]) == 1 / 3
    assert overlap([], []) == 0.0


def _cards(n, artists, mains, subs):
    return [
        {"track": i, "artist": artists[i % len(artists)], "main": mains[i % len(mains)],
         "sub": subs[i % len(subs)], "key": f"k{i}", "source": None}
        for i in range(n)
    ]


def test_metrics_and_gate_pass():
    cards = _cards(
        40, list(range(10)), ["rock", "pop", "jazz", "folk", "rap"],
        ["r1", "p1", "j1", "f1", "h1"],
    )
    m = metrics(cards)
    assert m["cards"] == 40
    assert m["min_main_genres_per_20"] == 5
    assert m["max_same_artist_per_20"] == 2
    assert m["artist_gap_violations"] == 0
    assert m["longest_same_sub_genre_run"] == 1
    assert m["duplicate_songs"] == 0
    assert m["unknown_genre_share"] == 0.0
    g = gate(m, first_overlap=0.1, same_seed_identical=True)
    assert all(ok for ok, _ in g.values())


def test_gate_fails_each_criterion():
    cards = _cards(40, [1, 2], ["rock"], ["r1"])
    cards[3]["key"] = cards[2]["key"]
    m = metrics(cards)
    g = gate(m, first_overlap=0.5, same_seed_identical=False)
    assert {k for k, (ok, _) in g.items() if not ok} == {
        "main_genres_per_20", "same_artist_per_20", "artist_gap", "duplicate_songs",
        "sub_genre_run", "freshness", "determinism",
    }


def test_discovery_share_counts_non_library():
    cards = _cards(3, [1, 2, 3], ["rock"], ["r1"])
    cards[1]["source"] = "probe"
    cards[2]["source"] = "library"
    assert metrics(cards)["discovery_share"] == 0.333


def test_sub_runs_and_discovery_positions_locate_runs_and_sources():
    cards = [
        {"sub": "a"}, {"sub": None, "source": "suggested"}, {"sub": None},
        {"sub": "b", "source": "probe"}, {"sub": "b", "source": "joker"}, {"sub": "c"},
        {"sub": "c", "source": "library"},
    ]
    assert sub_runs(cards) == [
        {"at": 3, "sub": "b", "sources": ["probe", "joker"]},
        {"at": 5, "sub": "c", "sources": ["library", "library"]},
    ]
    assert discovery_positions(cards) == [1, 3, 4]


def test_queue_url_sends_seen_cards_as_recent():
    assert queue_url(100, 2) == "/votes/queue?limit=100&seed=2"
    assert queue_url(20, 1, [7, 9]) == "/votes/queue?limit=20&seed=1&recent=7&recent=9"


def test_overlap_cards_lists_shared_head_cards_with_genre_pool_size():
    cards = [
        {"track": 1, "main": "rock", "sub": "indie", "source": None},
        {"track": 2, "main": "jazz", "sub": None, "source": "probe"},
        {"track": 3, "main": "rock", "sub": "punk", "source": "library"},
    ]
    out = overlap_cards(cards, [9, 2, 1, 3], width=2)
    assert out == [
        {"track": 2, "at": 1, "at2": 1, "source": "probe", "main": "jazz", "sub": None,
         "main_n": 1},
    ]
    assert [c["at"] for c in overlap_cards(cards, [3, 1, 2], width=3)] == [0, 1, 2]
    assert overlap_cards(cards, [], width=3) == []


def test_library_head_counts_tiers_and_marks_tracks():
    cands = [(1, 10), (2, 10), (3, 20), (4, 30)]
    summary, info = library_head(cands, voted_artists={30}, pool={3})
    assert summary == {
        "tier0_artists": 2, "tier1_artists": 1, "tier0_single_track_artists": 1,
        "tier0_pool_artists": 1, "tracks": 4,
    }
    assert info[3] == {"tier": 0, "artist_tracks": 1, "pool": True}
    assert info[1] == {"tier": 0, "artist_tracks": 2, "pool": False}
    assert info[4]["tier"] == 1


def test_pair_seeds_do_not_overlap_and_start_with_the_gate_pair():
    assert pair_seeds(1, 3) == [(1, 2), (3, 4), (5, 6)]
    assert pair_seeds(7, 0) == [(7, 8)]


def test_freshness_stats_summarises_pairs_against_threshold():
    out = freshness_stats([0.1, 0.2, 0.3])
    assert out["pairs"] == 3 and out["mean"] == 0.2
    assert (out["min"], out["max"], out["passing"]) == (0.1, 0.3, 1)  # 0,2 eşiği geçmez
    assert freshness_stats([]) == {"pairs": 0}


# --- Veritabanı okuması (kuyrukla aynı aday kuralı) ---
# ruff: noqa: E402, F811  (sabitler test_queue içe aktarımından gelir; repo kalıbı)
from sqlalchemy import select
from test_queue import client, db, lib_track, mk_artist, register  # noqa: F401

from app.config import ProfileSettings
from app.jobs.queue_sim import _library_state
from app.models import User


def test_library_state_reads_unvoted_candidates_and_voted_artists(client, db):
    email = "qsim1@example.com"
    h = register(client, email)
    voted_artist, other = mk_artist(db, "QS Oylu"), mk_artist(db, "QS Diger")
    done = lib_track(db, email, "ZZQS1V000001", voted_artist, "Oylandi")
    left = lib_track(db, email, "ZZQS1V000002", voted_artist, "Kalan")
    new = lib_track(db, email, "ZZQS1N000001", other, "Yeni")
    assert client.post("/votes", json={"track": done.id, "vote": 5}, headers=h).status_code == 201
    user = db.scalar(select(User).where(User.email == email))
    cands, voted_artists, pool = _library_state(db, user, ProfileSettings(_env_file=None))
    assert sorted(cands) == sorted([(left.id, voted_artist.id), (new.id, other.id)])
    assert voted_artists == {voted_artist.id}
    assert pool == set()


def test_stage_breakdown_takes_differences_of_cumulative_marks():
    laps = [("candidates", 9, 100.0), ("uncertainty", 11, 105.5), ("rank", 21, 114.0)]
    assert stage_breakdown(laps) == {
        "candidates": {"queries": 9, "db_ms": 100.0},
        "uncertainty": {"queries": 2, "db_ms": 5.5},
        "rank": {"queries": 10, "db_ms": 8.5},
    }
    assert stage_breakdown([]) == {}


def _sample(total, queries, db_ms, rank_ms):
    return {
        "total_ms": total, "queries": queries, "db_ms": db_ms,
        "stages": {"rank": {"ms": rank_ms, "queries": queries - 10, "db_ms": db_ms / 2}},
    }


def test_timing_summary_separates_cold_request_and_estimates_non_rtt():
    samples = [_sample(5000, 31, 4000, 900), _sample(3000, 30, 2800, 1200),
               _sample(3400, 30, 3000, 1400), _sample(4800, 30, 4400, 2400)]
    out = timing_summary(samples, [90.0, 100.0, 110.0])
    assert out["rtt_ms"] == 100.0
    assert out["requests"] == 4
    assert out["cold"] == {"total_ms": 5000, "queries": 31, "db_ms": 4000}
    assert out["warm_median"]["total_ms"] == 3400
    assert out["warm_median"]["stages"]["rank"] == {"ms": 1400, "queries": 20, "db_ms": 1500}
    assert out["warm_max_total_ms"] == 4800
    assert out["non_rtt_ms"] == 400  # 3400 - 30 × 100


def test_timing_summary_handles_empty_and_single_request():
    assert timing_summary([], []) == {"rtt_ms": 0.0, "requests": 0}
    one = timing_summary([_sample(50, 20, 10, 5)], [10.0])
    assert one["warm_median"]["total_ms"] == 50
    assert one["non_rtt_ms"] == 0.0  # alt sınır
