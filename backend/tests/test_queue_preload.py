"""`queue-8` istek yolunda tek sefer okunan veri (oy görünümü, parça->sanatçı, tür çiftleri,
profil) alt katmanlara aktarılır; ön yüklemeli çağrı, ön yüklemesiz çağrıyla aynı sonucu verir
ve istek başına sorgu sayısı sınırlı kalır."""
# ruff: noqa: E402, F811  (sabitler test_queue içe aktarımından gelir; repo kalıbı)
from datetime import UTC, datetime, timedelta

from sqlalchemy import event, select
from test_queue import client, db, lib_track, mk_artist, register  # noqa: F401
from test_sampled_queue import TTL, mk_seeds, user_of
from test_track_artists import link

from app.catalog.tags import GenrePairs, load_genre_pairs
from app.config import ProfileSettings, RecommendSettings, get_profile_settings
from app.main import app
from app.models import ArtistTag, TasteProfile, User, UserTrackMeta, VoteEvent
from app.profile.probe import exposure_counts, genre_shares, genre_theta, probe_and_joker
from app.profile.refill import refill_needed
from app.profile.service import load_vote_view, unheard_statuses, vote_view
from app.profile.track_artists import merge_track_artists, track_artist_parts, track_artists

T0 = datetime(2026, 11, 1, tzinfo=UTC)


def count_queries(db):
    """Oturumun bağlantısında çalışan SELECT/DML sayacı (SAVEPOINT vb. sayılmaz)."""
    seen: list[str] = []

    def hook(conn, cursor, statement, *_):
        if statement.lstrip().upper().startswith(("SELECT", "INSERT", "UPDATE", "DELETE", "WITH")):
            seen.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", hook)
    return seen, lambda: event.remove(db.get_bind(), "before_cursor_execute", hook)


def tag(db, artist, name):
    db.add(ArtistTag(artist_id=artist.id, tag=name, weight=100, source="musicbrainz"))
    db.flush()


def vote(db, user, track, value, at=None):
    extra = {"created_at": at} if at else {}
    db.add(VoteEvent(user_id=user.id, track_id=track.id, vote=value, **extra))
    db.flush()


def test_vote_view_latest_vote_is_last_event_and_order_is_input_independent():
    rows = [(3, 10, 2, T0 + timedelta(minutes=3)), (1, 10, 6, T0),
            (2, 20, 4, T0 + timedelta(minutes=1))]
    v = vote_view(rows)
    assert v == vote_view(list(reversed(rows)))
    assert v.track_ids == frozenset({10, 20})
    assert v.latest == [(10, 2), (20, 4)]  # güncel oy = son olay
    assert v.last_at == {10: T0 + timedelta(minutes=3), 20: T0 + timedelta(minutes=1)}
    assert v.recent_tracks == [10, 20, 10]  # olay kimliğine göre yeniden eskiye
    assert v.times == [T0, T0 + timedelta(minutes=1), T0 + timedelta(minutes=3)]
    empty = vote_view([])
    assert empty.track_ids == frozenset() and empty.latest == [] and empty.recent_tracks == []


def test_track_artist_parts_is_one_query_and_matches_merge_rule(db):
    email = "pl1@example.com"
    db.add(User(email=email, password_hash="x"))
    db.flush()
    shared_art, priv_art = mk_artist(db, "PL1 Paylasilan"), mk_artist(db, "PL1 Ozel")
    a = lib_track(db, email, "ZZPL1A000001", shared_art, "A")
    b = lib_track(db, email, "ZZPL1B000001", None, "B")
    c = lib_track(db, email, "ZZPL1C000001", None, "C")
    link(db, email, a, priv_art)  # paylaşılan önceliklidir
    u = link(db, email, b, priv_art)
    ids = [a.id, b.id, c.id]
    seen, stop = count_queries(db)
    try:
        shared, private = track_artist_parts(db, u.id, ids)
    finally:
        stop()
    assert len(seen) == 1
    assert shared == {a.id: shared_art.id, b.id: None, c.id: None}
    assert private == {a.id: priv_art.id, b.id: priv_art.id}
    assert merge_track_artists(shared, private) == {a.id: shared_art.id, b.id: priv_art.id}
    assert track_artists(db, u.id, ids) == {a.id: shared_art.id, b.id: priv_art.id}
    assert track_artist_parts(db, u.id, []) == ({}, {})


def test_genre_pairs_memo_matches_loader_and_never_refetches(db):
    rock, jazz = mk_artist(db, "PL2 Rock"), mk_artist(db, "PL2 Caz")
    bare = mk_artist(db, "PL2 Yok")
    tag(db, rock, "grunge")
    tag(db, jazz, "jazz")
    ids = {rock.id, jazz.id, bare.id}
    memo = GenrePairs(db)
    seen, stop = count_queries(db)
    try:
        first = memo.get({rock.id, bare.id})
        assert len(seen) == 1
        # etiketsiz sanatçı da yeniden sorulmaz
        assert memo.get({rock.id, bare.id}) == first and len(seen) == 1
        full = memo.get(ids)
        assert len(seen) == 2  # yalnız görülmemiş sanatçı için
    finally:
        stop()
    assert full == load_genre_pairs(db, ids)
    assert bare.id not in full and full[rock.id][0] == "rock"
    assert memo.get([]) == {}


def _voted_world(db, email):
    """Etiketli sanatçılara oylar (bir parça iki kez oylanmış) + hazır omurga kartları."""
    db.add(User(email=email, password_hash="x"))
    db.flush()
    u = user_of(db, email)
    arts = [mk_artist(db, f"{email[:3]} Art{k}") for k in range(4)]
    for art, name in zip(arts, ("grunge", "jazz", "hip hop", "grunge"), strict=True):
        tag(db, art, name)
    tracks = [lib_track(db, email, f"ZZ{email[:3].upper()}V{k:06d}", arts[k % 4], f"V{k}")
              for k in range(8)]
    tracks.append(lib_track(db, email, f"ZZ{email[:3].upper()}N000001", None, "Sanatcisiz"))
    for k, t in enumerate(tracks):
        vote(db, u, t, (6, 5, 2, 1, 4, 3)[k % 6], T0 + timedelta(minutes=k))
    vote(db, u, tracks[0], 1, T0 + timedelta(hours=1))  # oy değişikliği: güncel oy son olay
    prefix = f"Z{email[:2].upper()[0]}{email[2]}"
    seeds = mk_seeds(db, 5, prefix=prefix) + mk_seeds(
        db, 4, sub="jazz", main="jazz_blues", band="mid", prefix=prefix
    )
    now = datetime.now(UTC)
    for t in seeds:
        db.add(UserTrackMeta(user_id=u.id, track_id=t.id, title=f"O{t.id}", artist_names=["S"],
                             expires_at=now + TTL))
    vote(db, u, seeds[0], 5, T0 + timedelta(hours=2))  # omurga parçası da maruziyete girer
    db.flush()
    return u, tracks, seeds, now


def test_preloaded_probe_inputs_equal_fresh_reads(db):
    u, tracks, seeds, now = _voted_world(db, "pl3@example.com")
    cfg, rcfg = ProfileSettings(_env_file=None), RecommendSettings(_env_file=None)
    votes = load_vote_view(db, u.id)
    shared, _ = track_artist_parts(db, u.id, votes.track_ids)
    genres = GenrePairs(db)

    for seed in range(4):
        fresh = genre_theta(db, u.id, seed, rcfg)
        assert genre_theta(db, u.id, seed, rcfg, votes=votes.latest, artist_of=shared,
                           genres=genres) == fresh
    assert exposure_counts(db, u.id, cfg, vote_tracks=votes.recent_tracks, genres=genres) == \
        exposure_counts(db, u.id, cfg)
    small = ProfileSettings(_env_file=None, queue_history_size=3)  # pencere kesimi de aynı
    assert exposure_counts(db, u.id, small, vote_tracks=votes.recent_tracks, genres=genres) == \
        exposure_counts(db, u.id, small)

    theta = genre_theta(db, u.id, 1, rcfg)
    exclude = set(votes.track_ids)
    plain = probe_and_joker(db, u.id, now, exclude, 3, 3, cfg, theta, 7)
    assert plain[0] and plain[1]
    assert probe_and_joker(db, u.id, now, exclude, 3, 3, cfg, theta, 7,
                           vote_tracks=votes.recent_tracks, genres=genres) == plain

    assert unheard_statuses(db, u.id, cfg, votes.last_at) == unheard_statuses(db, u.id, cfg)


def test_genre_shares_reads_profile_body():
    assert genre_shares(None) == {} and genre_shares({}) == {}
    assert genre_shares({"genres": {}}) == {}
    main = [{"genre": "rock", "share": 0.75}, {"genre": "jazz_blues", "share": 0.25}]
    body = {"genres": {"main": main}}
    assert genre_shares(body) == {"rock": 0.75, "jazz_blues": 0.25}


def test_refill_needed_same_with_preloaded_profile_and_vote_times(db):
    u, tracks, _, now = _voted_world(db, "pl4@example.com")
    cfg = ProfileSettings(_env_file=None, fast_queue_enabled=True, buffer_low_watermark=0,
                          queue_rebuild_after_votes=3)
    times = load_vote_view(db, u.id).times
    assert refill_needed(db, u, now, cfg, profile=None, vote_times=times) == \
        refill_needed(db, u, now, cfg)  # profil yok
    for created, expect in ((T0 + timedelta(minutes=2), True), (T0 + timedelta(hours=3), False)):
        prof = TasteProfile(user_id=u.id, version=1 if expect else 2, algo_version="t",
                            graph_version=None, created_at=created, body={})
        db.add(prof)
        db.flush()
        assert refill_needed(db, u, now, cfg, ready_total=5) is expect
        got = refill_needed(db, u, now, cfg, ready_total=5, profile=prof, vote_times=times)
        assert got is expect


def test_queue8_query_count_is_bounded_and_independent_of_vote_count(client, db):
    """Gerileme koruması: istek başına sorgu sayısı oy/kart sayısıyla büyümez ve tavanı aşmaz."""
    email = "pl5@example.com"
    h = register(client, email)
    u = user_of(db, email)
    arts = [mk_artist(db, f"PL5 Art{k}") for k in range(12)]
    for k, art in enumerate(arts):
        tag(db, art, ("grunge", "jazz", "hip hop")[k % 3])
    lib = [lib_track(db, email, f"ZZPL5L{k:06d}", arts[k % 12], f"K{k}") for k in range(30)]
    now = datetime.now(UTC)
    for t in mk_seeds(db, 6, prefix="ZP5") + mk_seeds(db, 4, sub="jazz", main="jazz_blues",
                                                       band="mid", prefix="ZP5"):
        db.add(UserTrackMeta(user_id=u.id, track_id=t.id, title=f"O{t.id}", artist_names=["S"],
                             expires_at=now + TTL))
    db.flush()
    app.dependency_overrides[get_profile_settings] = lambda: ProfileSettings(
        _env_file=None, queue_sampler_enabled=True, fast_queue_enabled=True
    )

    def measure():
        seen, stop = count_queries(db)
        try:
            body = client.get("/votes/queue?limit=10&seed=3", headers=h).json()
        finally:
            stop()
        assert body["algo_version"] == "queue-8" and len(body["items"]) == 10
        return len(seen)

    try:
        few = measure()
        for k, t in enumerate(lib[:15]):
            vote(db, u, t, (6, 5, 2, 4)[k % 4])
        many = measure()
    finally:
        app.dependency_overrides.pop(get_profile_settings, None)
    assert few <= 20 and many <= 20, (few, many)
    assert db.scalar(select(VoteEvent.id).where(VoteEvent.user_id == u.id).limit(1)) is not None
