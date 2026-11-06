from app.recommend.genres import GENRE_BASE, GENRES, blend_labels, main_genre


def test_main_genre_sums_weights_and_normalizes_spelling():
    assert main_genre([("hip-hop", 60), ("southern hip hop", 40), ("pop", 50)]) == "rap"
    assert main_genre([("Thrash Metal", 80), ("rock", 30)]) == "metal"
    assert main_genre([("female vocals", 90), ("american", 50)]) is None
    assert main_genre([]) is None


def test_main_genre_word_boundaries_and_ties():
    assert main_genre([("therapy", 100)]) is None  # "rap" kelimenin içinde sayılmaz
    assert main_genre([("turkish hip hop", 100)]) == "rap"  # eşitlikte GENRES sırası


def test_blend_labels_prefers_genre_and_falls_back_to_community():
    out = blend_labels({1: 3, 2: 5, 3: 7}, {1: "rap", 3: "jazz_blues", 9: "pop"})
    assert out[2] == 5 and out[1] >= GENRE_BASE and out[3] >= GENRE_BASE and 9 not in out
    assert out[1] != out[3]


def test_every_genre_phrase_matches_itself():
    for g, phrases in GENRES.items():
        for p in phrases:
            assert main_genre([(p, 10)]) is not None, (g, p)
