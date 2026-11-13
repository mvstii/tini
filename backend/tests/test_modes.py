from app.profile.modes import name_clusters


def cluster(cid, *artists):
    return {"id": cid, "artists": [{"artist_id": a, "affinity": w} for a, w in artists]}


GENRES = {
    1: ("rap", "trap"),
    2: ("rap", "trap"),
    3: ("rap", "boom_bap"),
    4: ("indie_alt", None),
    5: ("indie_alt", "shoegaze"),
    6: ("rap", None),
}


def test_name_is_top_subgenre_by_affinity_and_tags_are_runners_up():
    [m] = name_clusters([cluster(0, (1, 1.0), (2, 0.5), (3, 0.4), (4, 0.1))], GENRES)
    assert m == {"id": 0, "name": "Trap", "tags": ["Boom Bap", "Indie / Alternatif"]}


def test_falls_back_to_main_genre_when_no_subgenre():
    [m] = name_clusters([cluster(0, (4, 1.0))], GENRES)
    assert m["name"] == "Indie / Alternatif"
    assert m["tags"] == []


def test_cluster_without_labelled_artists_has_no_name():
    [m] = name_clusters([cluster(0, (99, 1.0))], GENRES)
    assert m == {"id": 0, "name": None, "tags": []}


def test_duplicate_names_are_numbered_in_order():
    ms = name_clusters([cluster(0, (1, 1.0)), cluster(1, (2, 1.0)), cluster(2, (5, 1.0))], GENRES)
    assert [m["name"] for m in ms] == ["Trap", "Trap 2", "Shoegaze"]


def test_deterministic_tie_break_and_input_untouched():
    c = cluster(0, (3, 1.0), (5, 1.0))  # boom_bap ile shoegaze eşit → anahtara göre
    before = repr(c)
    assert name_clusters([c], GENRES) == name_clusters([c], GENRES)
    assert name_clusters([c], GENRES)[0]["name"] == "Boom Bap"
    assert repr(c) == before


def test_negative_affinity_does_not_vote():
    [m] = name_clusters([cluster(0, (1, -2.0), (4, 0.2))], GENRES)
    assert m["name"] == "Indie / Alternatif"


def test_dominant_shared_genre_does_not_name_every_cluster():
    genres = {1: ("rap", "pop_rap"), 2: ("rap", "pop_rap"), 3: ("rap", "pop_rap"),
              4: ("rap", "trap"), 5: ("indie_alt", "shoegaze"), 6: ("rap", "boom_bap")}
    clusters = [
        cluster(0, (1, 1.0), (4, 0.9)),
        cluster(1, (2, 1.0), (5, 0.9)),
        cluster(2, (3, 1.0), (6, 0.9)),
    ]
    names = [m["name"] for m in name_clusters(clusters, genres)]
    assert names == ["Trap", "Shoegaze", "Boom Bap"]


def test_same_top_genre_is_disambiguated_with_second_genre_then_number():
    genres = {1: ("rap", "trap"), 2: ("rap", "trap"), 3: ("rap", "boom_bap"), 4: ("rap", "drill")}
    clusters = [cluster(0, (1, 1.0), (3, 0.3)), cluster(1, (2, 1.0), (4, 0.3)),
                cluster(2, (1, 1.0), (3, 0.3))]
    names = [m["name"] for m in name_clusters(clusters, genres)]
    assert len(set(names)) == 3
