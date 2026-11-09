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


def test_sub_genre_taxonomy_is_consistent():
    from app.recommend.genres import SUB_GENRES, main_of

    assert 60 <= len(SUB_GENRES) <= 90
    assert all(main in GENRES for main, _ in SUB_GENRES.values())
    assert main_of("arabesk") == "turkish"


def test_every_sub_genre_phrase_resolves_to_a_sub_of_same_main():
    from app.recommend.genres import SUB_GENRES, main_of, sub_genre

    for g, (main, phrases) in SUB_GENRES.items():
        for p in phrases:
            got = sub_genre([(p, 10)])
            assert got is not None, (g, p)
            assert main_of(got) == main, (g, p, got)
        # alt tür kendi ilk (sorgu) kalıbıyla bulunur
        assert sub_genre([(phrases[0], 10)]) == g, (g, phrases[0])


def test_sub_genre_turkish_and_specificity():
    from app.recommend.genres import sub_genre

    assert sub_genre([("arabesk", 80), ("turkish", 40)]) == "arabesk"
    assert sub_genre([("Anadolu Rock", 50), ("rock", 30)]) == "anadolu_rock"
    assert sub_genre([("turkish hip hop", 70)]) == "turkce_rap"
    assert sub_genre([("turkish pop", 70)]) == "turkce_pop"
    assert sub_genre([("death metal", 50), ("metal", 50)]) == "death_metal"  # genel etiket ezmez
    assert sub_genre([("turkish", 90)]) is None  # genel Türkçe etiketi alt tür vermez
    assert sub_genre([("female vocals", 90)]) is None and sub_genre([]) is None


def test_sub_genre_is_pure_and_main_genre_unchanged():
    from app.recommend.genres import sub_genre

    tags = [("trap", 70), ("hip hop", 60)]
    assert sub_genre(tags) == sub_genre(list(reversed(tags)))
    assert main_genre([("arabesk", 80)]) == "turkish"


def test_backbone_query_tags_are_verified_listenbrainz_tags():
    # İlk ifade ListenBrainz sorgu etiketidir; bu altı için canlı denemede (9 Kasım 2026) ilk
    # ifadeler boş/zayıf havuz verdi, aşağıdakiler ≥ 100 kayıt döndü.
    from app.recommend.genres import SUB_GENRES

    expected = {
        "turk_halk": "turkish folk", "turk_sanat": "turkish classical",
        "turkce_rap": "turkish rap", "anadolu_rock": "anatolian rock",
        "k_pop": "k-pop", "j_pop": "j-pop",
    }
    for sub, tag in expected.items():
        assert SUB_GENRES[sub][1][0] == tag


def test_reordered_phrases_still_classify():
    from app.recommend.genres import sub_genre

    assert sub_genre([("turkish folk", 5)]) == "turk_halk"
    assert sub_genre([("türk halk müziği", 5)]) == "turk_halk"
    assert sub_genre([("turkish classical", 5)]) == "turk_sanat"
    assert sub_genre([("turkish rap", 5)]) == "turkce_rap"
    assert sub_genre([("turkish hip hop", 5)]) == "turkce_rap"
    assert sub_genre([("anatolian rock", 5)]) == "anadolu_rock"
    assert sub_genre([("k pop", 5)]) == "k_pop"
    assert sub_genre([("j-pop", 5)]) == "j_pop"
