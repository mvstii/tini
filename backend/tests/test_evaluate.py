from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from test_lists_api import client, db, library_track, setup_user  # noqa: F401

from app.jobs.evaluate import collect
from app.models import (
    GeneratedList,
    ListFeedback,
    ListItem,
    UnheardEvent,
    User,
    VoteEvent,
)
from app.recommend.metrics import (
    EvalItem,
    PoolEvent,
    TrackVote,
    evaluate_items,
    evaluate_unheard,
    format_report,
    spearman,
)
from app.recommend.outcomes import ArtistVote

T0 = datetime(2026, 11, 1, tzinfo=UTC)
LATER = T0 + timedelta(days=1)
EARLIER = T0 - timedelta(days=1)


def item(pos, artist, slot="explore", score=0.5, list_id=1):
    return EvalItem(list_id, pos, artist, slot, score, T0)


def test_spearman_perfect_inverse_and_degenerate():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    assert spearman([1, 2], [1, 2]) is None  # <3 çift
    assert spearman([1, 2, 3], [5, 5, 5]) is None  # sabit dizi
    assert spearman([1, 2, 2, 3], [1, 2, 2, 3]) == 1.0  # bağlar


def test_items_good_rate_per_slot_uses_last_vote_after_list():
    items = [item(1, 1, "familiar"), item(2, 2, "unheard"), item(3, 3, "explore"),
             item(4, 4, "explore"), item(5, 5, "explore")]
    votes = [
        ArtistVote(1, 1, 5, LATER),
        ArtistVote(2, 2, 2, LATER),
        ArtistVote(3, 3, 6, LATER), ArtistVote(4, 3, 1, LATER),  # son oy geçerli
        ArtistVote(5, 4, 6, EARLIER),  # liste öncesi sayılmaz
    ]
    rep = evaluate_items(items, votes, set())
    assert rep.overall.presented == 5 and rep.overall.voted == 3 and rep.overall.good == 1
    assert rep.slots["familiar"].good_rate == 1.0
    assert rep.slots["unheard"].good_rate == 0.0
    assert rep.slots["explore"].voted == 1 and rep.slots["explore"].good == 0


def test_objection_rate_and_no_votes_gives_none():
    rep = evaluate_items([item(1, 1), item(2, 2)], [], {(1, 1)})
    assert rep.objection_rate == 0.5
    assert rep.overall.good_rate is None and rep.rank_corr is None


def test_rank_corr_excludes_fresh_slot():
    items = [item(i, i, score=s) for i, s in ((1, 0.9), (2, 0.5), (3, 0.1))]
    items.append(item(4, 4, "fresh", score=0.01))
    votes = [ArtistVote(i, i, v, LATER) for i, v in ((1, 6), (2, 4), (3, 2), (4, 6))]
    rep = evaluate_items(items, votes, set())
    assert rep.rank_corr == 1.0 and rep.rank_corr_n == 3
    assert rep.slots["fresh"].good == 1  # sanatçıya sonradan Good+ yine sayılır


def test_unheard_counts_only_votes_after_first_pooled():
    pool = [PoolEvent(1, "pooled", T0), PoolEvent(1, "presented", LATER),
            PoolEvent(2, "pooled", T0), PoolEvent(3, "pooled", T0), PoolEvent(4, "presented", T0)]
    votes = [
        TrackVote(1, 1, 2, LATER), TrackVote(2, 1, 5, LATER),  # son oy 5
        TrackVote(3, 2, 3, LATER),
        TrackVote(4, 3, 6, EARLIER),  # havuzdan önce
        TrackVote(5, 4, 6, LATER),  # hiç pooled olmamış
    ]
    rep = evaluate_items([], [], set())
    evaluate_unheard(rep, pool, votes)
    assert (rep.unheard_pooled, rep.unheard_voted, rep.unheard_good) == (3, 2, 1)
    assert rep.unheard_good_rate == 0.5


def test_format_report_flags_small_samples():
    rep = evaluate_items([item(1, 1)], [ArtistVote(1, 1, 5, LATER)], set())
    text = "\n".join(format_report(rep, min_sample=10))
    assert "yetersiz veri" in text and "%100" in text
    assert "yetersiz veri" not in "\n".join(format_report(rep, min_sample=1)).split("korelasyon")[0]


def test_collect_is_read_only_and_counts_events(client, db):  # noqa: F811
    h, seed, c1, c2 = setup_user(client, db, "ev1@example.com", "EV")
    uid = db.scalar(select(User.id).where(User.email == "ev1@example.com"))
    lst = client.post("/lists/generate", headers=h).json()
    first = lst["items"][0]
    t = library_track(db, "ev1@example.com", "ZZEV00000002", c1)
    pooled = library_track(db, "ev1@example.com", "ZZEV00000003", c2)
    db.add(UnheardEvent(user_id=uid, track_id=pooled.id, state="pooled",
                        created_at=datetime.now(UTC) - timedelta(hours=1)))
    later = datetime.now(UTC) + timedelta(hours=1)
    db.add_all([
        VoteEvent(user_id=uid, track_id=t.id, vote=6, created_at=later),
        VoteEvent(user_id=uid, track_id=pooled.id, vote=5, created_at=later),
    ])
    db.add(ListFeedback(user_id=uid, list_id=lst["id"], position=first["position"],
                        kind="wrong_reason"))
    db.flush()

    def counts():
        return [db.scalar(select(func.count()).select_from(m))
                for m in (VoteEvent, UnheardEvent, GeneratedList, ListItem, ListFeedback)]

    before = counts()
    rep = collect(db, uid)
    assert counts() == before
    assert rep.overall.presented == len(lst["items"]) and rep.overall.objected == 1
    assert rep.unheard_pooled == 1 and rep.unheard_good == 1
