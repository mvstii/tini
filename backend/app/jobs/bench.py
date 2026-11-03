"""Yalnızca ölçüm: test veritabanına sentetik veri basıp ağır yolları süreler.

Yalnızca localhost'a bağlanır (prod'a karşı çalışmayı reddeder). Bütün veri "bench-" önekiyle
işaretlenir ve bitişte silinir (--keep ile kalır).
CLI: python -m app.jobs.bench [--artists N] [--votes N] [--keep]
"""
import argparse
import random
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import delete, event, insert, select, text
from sqlalchemy.orm import Session

from app.config import (
    get_graph_settings,
    get_profile_settings,
    get_recommend_settings,
    get_settings,
)
from app.db import make_engine
from app.graph.service import clear_cache, get_matrix
from app.models import (
    Artist,
    ArtistEdge,
    GeneratedList,
    GraphSnapshot,
    Track,
    User,
    VoteEvent,
)
from app.profile.service import rebuild_profile
from app.recommend.service import generate_list

PREFIX = "bench-"
NEIGHBORS = 20  # Last.fm kuralı: düğüm başına en çok ~20 komşu
TRACKS_PER_ARTIST = 5


def _chunks(rows: list[dict], n: int = 5000):
    for i in range(0, len(rows), n):
        yield rows[i : i + n]


def seed(db: Session, rng: random.Random, n_artists: int, n_votes: int, n_users: int) -> dict:
    gcfg = get_graph_settings()
    tag = uuid.uuid4().hex[:6]
    names = [f"{PREFIX}{tag}-{i}" for i in range(n_artists)]
    db.execute(insert(Artist), [{"name": n, "name_norm": n} for n in names])
    artist_ids = list(
        db.scalars(select(Artist.id).where(Artist.name_norm.like(f"{PREFIX}{tag}-%")))
    )
    expires = datetime.now(UTC) + timedelta(days=30)
    edges = {}
    for a in artist_ids:
        for b in rng.sample(artist_ids, NEIGHBORS):
            if a != b:
                edges[(a, b)] = rng.random()
    rows = [
        {"src": a, "dst": b, "source": gcfg.edge_source, "weight": w, "expires_at": expires}
        for (a, b), w in edges.items()
    ]
    for chunk in _chunks(rows):
        db.execute(insert(ArtistEdge), chunk)
    track_rows = [
        {"isrc": f"BN{tag[:2].upper()}{i:08d}"[:12], "artist_id": a}
        for i, a in enumerate(x for x in artist_ids for _ in range(TRACKS_PER_ARTIST))
    ]
    for chunk in _chunks(track_rows):
        db.execute(insert(Track), chunk)
    all_tracks = list(db.scalars(select(Track.id).where(Track.artist_id.in_(artist_ids))))
    db.add(GraphSnapshot(edge_count=len(rows), params={"bench": True}))
    now = datetime.now(UTC)
    users = []
    for i in range(n_users):
        u = User(email=f"{PREFIX}{tag}-{i}@example.test", password_hash="x")
        db.add(u)
        users.append(u)
    db.flush()
    votes = []
    for k, u in enumerate(users):
        count = n_votes if k == 0 else max(50, n_votes // 5)
        for t in rng.sample(all_tracks, min(count, len(all_tracks))):
            votes.append(
                {
                    "user_id": u.id,
                    "track_id": t,
                    "vote": rng.choice([1, 2, 3, 4, 4, 5, 5, 6]),
                    "created_at": now - timedelta(days=rng.randint(0, 365)),
                }
            )
    for chunk in _chunks(votes):
        db.execute(insert(VoteEvent), chunk)
    db.commit()
    return {"tag": tag, "artists": len(artist_ids), "edges": len(rows), "tracks": len(all_tracks),
            "votes": len(votes), "main_user": users[0].id, "artist_ids": artist_ids}


def cleanup(db: Session) -> None:
    """Önek tabanlı: yarım kalmış önceki çalıştırmaların artıklarını da siler."""
    bench = select(Artist.id).where(Artist.name_norm.like(f"{PREFIX}%"))
    db.execute(delete(User).where(User.email.like(f"{PREFIX}%")))
    db.execute(delete(ArtistEdge).where(ArtistEdge.src.in_(bench)))
    db.execute(delete(ArtistEdge).where(ArtistEdge.dst.in_(bench)))
    db.execute(delete(Track).where(Track.artist_id.in_(bench)))
    db.execute(delete(Artist).where(Artist.name_norm.like(f"{PREFIX}%")))
    db.execute(delete(GraphSnapshot).where(GraphSnapshot.params["bench"].as_boolean()))
    db.commit()
    clear_cache()


def run(n_artists: int, n_votes: int, keep: bool, profile: bool = False) -> list[str]:
    host = urlparse(get_settings().database_url.replace("+psycopg", "")).hostname
    if host not in ("localhost", "127.0.0.1", "::1"):
        raise SystemExit(f"Yalnızca localhost veritabanında çalışır, bulunan: {host}")
    cfg, pcfg, gcfg = get_recommend_settings(), get_profile_settings(), get_graph_settings()
    engine = make_engine()
    rng = random.Random(42)
    out: list[str] = []
    stmts: list[tuple[float, str, object]] = []
    t_start: list[float] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cur, statement, params, ctx, many):
        t_start.append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cur, statement, params, ctx, many):
        stmts.append((time.perf_counter() - t_start.pop(), statement, params))

    with Session(engine) as db:
        t = time.perf_counter()
        info = seed(db, rng, n_artists, n_votes, n_users=30)
        out.append(
            f"tohum: {info['artists']} sanatçı, {info['edges']} kenar, {info['tracks']} parça, "
            f"{info['votes']} oy ({time.perf_counter() - t:.1f} s)"
        )
        try:
            db.execute(text("ANALYZE"))
            db.commit()
            uid, now = info["main_user"], datetime.now(UTC)

            def timed(label, fn, capture=True):
                stmts.clear()
                t0 = time.perf_counter()
                r = fn()
                dt = (time.perf_counter() - t0) * 1000
                db_ms = sum(s[0] for s in stmts) * 1000
                out.append(f"{label}: {dt:.0f} ms (sorgu {len(stmts)} adet, DB {db_ms:.0f} ms)")
                return r

            clear_cache()
            timed("matris kurulumu (soğuk)", lambda: get_matrix(db, gcfg))
            timed("matris (sıcak)", lambda: get_matrix(db, gcfg))
            timed("profil kurulumu", lambda: rebuild_profile(db, uid, now, pcfg, gcfg))
            for i in range(3):
                timed(
                    f"liste üretimi #{i + 1}",
                    lambda: generate_list(db, uid, now, cfg, pcfg, gcfg),
                )
            if profile:
                import cProfile
                import io
                import pstats

                pr = cProfile.Profile()
                pr.enable()
                generate_list(db, uid, now, cfg, pcfg, gcfg)
                pr.disable()
                buf = io.StringIO()
                pstats.Stats(pr, stream=buf).sort_stats("cumulative").print_stats(18)
                out.append(buf.getvalue())
            slow = sorted(stmts, key=lambda s: -s[0])[:5]
            out.append("--- son liste üretiminde en yavaş sorgular ---")
            for dur, sql, params in slow:
                out.append(f"{dur * 1000:.1f} ms  {' '.join(sql.split())[:160]}")
                try:
                    plan = db.connection().exec_driver_sql(
                        "EXPLAIN (ANALYZE, BUFFERS) " + sql, params
                    )
                    out.extend("    " + r[0][:200] for r in plan)
                except Exception as e:  # noqa: BLE001 - ölçüm aracı, plan alınamayan sorguyu atla
                    db.rollback()
                    out.append(f"    plan alınamadı: {type(e).__name__}")
            n_lists = db.scalar(select(text("count(*)")).select_from(GeneratedList))
            out.append(f"generated_list satır sayısı: {n_lists}")
        finally:
            if not keep:
                db.rollback()
                cleanup(db)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--artists", type=int, default=20000)
    ap.add_argument("--votes", type=int, default=500)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--profile", action="store_true")
    ap.add_argument("--cleanup", action="store_true", help="yalnızca artıkları sil")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.cleanup:
        with Session(make_engine()) as s:
            cleanup(s)
        raise SystemExit("temizlendi")
    print("\n".join(run(args.artists, args.votes, args.keep, args.profile)))
