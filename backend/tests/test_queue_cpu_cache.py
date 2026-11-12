"""Kuyruk isteğindeki saf hesap önbellekleri: sonuç önbelleksiz hesapla birebir aynı kalır."""
import re
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np
import pytest

from app.catalog.names import normalize_name
from app.config import GraphSettings, ProfileSettings, RecommendSettings
from app.graph.matrix import build_matrix
from app.profile import active_service
from app.profile.queue import song_key
from app.recommend import genres
from app.recommend.genres import main_genre, sub_genre
from app.recommend.ppr import artist_scores

GCFG = GraphSettings(_env_file=None)
RCFG = RecommendSettings(_env_file=None)
MARKERS = ProfileSettings(_env_file=None).queue_version_markers
EDGES = [(1, 10, 0.9), (10, 12, 0.8), (1, 11, 0.3), (2, 11, 0.9), (20, 21, 0.5)]


def _graph():
    src, dst, w = zip(*EDGES, strict=True)
    return build_matrix(np.array(src), np.array(dst), np.array(w), GCFG)


def _row(user, version, pos):
    body = {
        "clusters": [{"id": 0, "weight": 1.0,
                      "artists": [{"artist_id": a, "affinity": f} for a, f in pos]}],
        "unclustered": [], "anchors": [], "avoid": [],
    }
    return SimpleNamespace(
        id=version, user_id=user, version=version, body=body,
        created_at=datetime(2026, 11, 12, tzinfo=UTC),
    )


@pytest.fixture
def counted(monkeypatch):
    """artist_scores çağrılarını sayar; önbelleği test başında ve sonunda boşaltır."""
    active_service.clear_score_cache()
    calls = []

    def spy(gm, body, cfg):
        calls.append(1)
        return artist_scores(gm, body, cfg)

    monkeypatch.setattr(active_service, "artist_scores", spy)
    yield calls
    active_service.clear_score_cache()


def test_scores_computed_once_per_profile_snapshot(counted):
    gm, row = _graph(), _row(uuid.uuid4(), 1, [(1, 0.7)])
    want = artist_scores(gm, row.body, RCFG)
    for _ in range(3):
        ref, scores = active_service._cached_scores(gm, row, RCFG)
        assert scores == want and ref == sorted(want.values())
    assert len(counted) == 1


def test_scores_recomputed_on_new_profile_graph_or_settings(counted):
    user, gm = uuid.uuid4(), _graph()
    active_service._cached_scores(gm, _row(user, 1, [(1, 0.7)]), RCFG)
    new = _row(user, 2, [(2, 0.7)])
    assert active_service._cached_scores(gm, new, RCFG)[1] == artist_scores(gm, new.body, RCFG)
    assert len(counted) == 2  # yeni profil sürümü
    active_service._cached_scores(_graph(), new, RCFG)
    assert len(counted) == 3  # yeni matris nesnesi
    other = RecommendSettings(_env_file=None, ppr_alpha=0.5)
    got = active_service._cached_scores(_graph(), new, other)[1]
    assert len(counted) == 4  # farklı ayar
    assert got == artist_scores(_graph(), new.body, other)
    # Aynı ayar değerleri taşıyan başka bir nesne isabet sayılır.
    gm2 = _graph()
    active_service._cached_scores(gm2, new, RecommendSettings(_env_file=None))
    active_service._cached_scores(gm2, new, RecommendSettings(_env_file=None))
    assert len(counted) == 5


def test_score_cache_is_bounded(counted):
    gm = _graph()
    for _ in range(active_service._SCORE_CACHE_USERS + 5):
        active_service._cached_scores(gm, _row(uuid.uuid4(), 1, [(1, 0.7)]), RCFG)
    assert len(active_service._score_cache) == active_service._SCORE_CACHE_USERS


def _song_key_ref(title, artists, markers):
    """Önbellekten önceki uygulama (başvuru)."""
    alt = "|".join(re.escape(m) for m in markers)
    stripped = title
    if alt:
        stripped = re.sub(rf"\s*[(\[][^)\]]*\b(?:{alt})[^)\]]*[)\]]", "", stripped, flags=re.I)
        stripped = re.sub(rf"\s+[-–—]\s+[^-–—]*\b(?:{alt})[^-–—]*$", "", stripped, flags=re.I)
    name = normalize_name.__wrapped__(stripped) or normalize_name.__wrapped__(title)
    return name, normalize_name.__wrapped__(artists[0]) if artists else ""


@pytest.mark.parametrize("title", [
    "Paranoid Android (Remastered 2009)", "Hey Jude - Remastered 2015", "Song [Mono Version]",
    "Bayındır – Deluxe Edition", "Live at Wembley (Live)", "Plain Title", "(Remastered)", "",
    "Çok Güzel Şarkı - 2011 Remaster", "A - B - Remastered",
])
def test_song_key_matches_reference(title):
    for markers in (MARKERS, list(MARKERS), ()):
        for artists in (["Sezen Aksu", "X"], None, []):
            for _ in range(2):  # ikinci tur önbellekten
                assert song_key(title, artists, markers) == _song_key_ref(title, artists, markers)


def _main_ref(tags):
    score = {}
    for tag, weight in tags:
        t = genres._norm(tag)
        for g, rx in genres._RE.items():
            if rx.search(t):
                score[g] = score.get(g, 0) + max(int(weight), 1)
    if not score:
        return None
    return max(score, key=lambda g: (score[g], -genres._ORDER.index(g)))


def _sub_ref(tags):
    score, spec = {}, {}
    for tag, weight in tags:
        t = genres._norm(tag)
        best = None
        for i, (g, rx) in enumerate(genres._SUB_RE.items()):
            m = rx.search(t)
            if m:
                cand = (len(m.group(0)), -i, g)
                if best is None or cand > best:
                    best = cand
        if best is not None:
            g = best[2]
            score[g] = score.get(g, 0) + max(int(weight), 1)
            spec[g] = max(spec.get(g, 0), best[0])
    if not score:
        return None
    return max(score, key=lambda g: (score[g], spec[g], -genres._SUB_ORDER.index(g)))


def test_genre_matching_matches_reference():
    patterns = [p for ps in genres.GENRES.values() for p in ps]
    patterns += [p for _, ps in genres.SUB_GENRES.values() for p in ps]
    tag_sets = [[(p, 1)] for p in patterns]
    pairs = zip(patterns, patterns[7:], strict=False)
    tag_sets += [[(a, 3), (b, 0), (f"{a}_{b}", 2)] for a, b in pairs]
    tag_sets += [[], [("zzz unknown", 5)], [("Death-Metal", 2), ("metal", 9)], [("Türk/Pop", 1)]]
    for _ in range(2):  # ikinci tur önbellekten
        for tags in tag_sets:
            assert main_genre(tags) == _main_ref(tags)
            assert sub_genre(tags) == _sub_ref(tags)
