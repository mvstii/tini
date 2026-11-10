"""Kuyruk simülasyonu (PR-6, salt okuma): bir kullanıcı için 100 kartlık kuyruk üretir ve
çeşitlilik ölçütlerini yazdırır. Hiçbir şey yazmaz (hızlı yol, servis çağrısı yok).

Ölçütler: en uzun aynı-tür serisi, 20'lik pencerede ayrı tür sayısı, sanatçı tekrarı, keşif
(kütüphane dışı) payı, iki oturum (farklı tohum) örtüşmesi.
CLI: python -m app.jobs.queue_sim --email EPOSTA [--size 100] [--seed 1] [--sampler/--no-sampler]
"""
import argparse
from itertools import groupby

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.tags import load_genre_pairs
from app.config import ProfileSettings, get_profile_settings
from app.db import make_engine
from app.deps import current_user, get_db
from app.main import app
from app.models import Track, User


def longest_run(labels: list) -> int:
    return max((len(list(g)) for _, g in groupby(labels)), default=0)


def window_distinct(labels: list, width: int = 20) -> float:
    """Kayan pencerelerde ortalama ayrı etiket sayısı."""
    if len(labels) < width:
        return float(len(set(labels)))
    wins = [len(set(labels[i:i + width])) for i in range(len(labels) - width + 1)]
    return sum(wins) / len(wins)


def overlap(a: list[int], b: list[int]) -> float:
    return len(set(a) & set(b)) / max(min(len(a), len(b)), 1)


def metrics(tracks: list[int], artist_of: dict, genre_of: dict, sources: list) -> dict:
    artists = [artist_of.get(t) for t in tracks]
    genres = [(genre_of.get(a) or (None, None))[0] for a in artists]
    return {
        "cards": len(tracks),
        "longest_same_genre_run": longest_run(genres),
        "avg_distinct_genres_per_20": round(window_distinct(genres), 2),
        "artist_repeats": len(artists) - len(set(artists)),
        "discovery_share": round(sum(1 for s in sources if s) / max(len(sources), 1), 3),
    }


def run(email: str, size: int = 100, seed: int = 1, sampler: bool = True) -> dict:
    cfg = ProfileSettings(queue_sampler_enabled=sampler, fast_queue_enabled=True)
    engine = make_engine()
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit(f"Kullanıcı yok: {email}")
        app.dependency_overrides[current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_profile_settings] = lambda: cfg
        try:
            client = TestClient(app)
            runs = [
                client.get(f"/votes/queue?limit={size}&seed={s}").json()
                for s in (seed, seed + 1)
            ]
        finally:
            app.dependency_overrides.clear()
        first = runs[0]["items"]
        tracks = [i["track"] for i in first]
        artist_of = dict(
            db.execute(select(Track.id, Track.artist_id).where(Track.id.in_(tracks))).all()
        )
        genre_of = load_genre_pairs(db, {a for a in artist_of.values() if a is not None})
        out = metrics(tracks, artist_of, genre_of, [i.get("source") for i in first])
        out["algo_version"] = runs[0]["algo_version"]
        second = [i["track"] for i in runs[1]["items"]]
        out["two_session_overlap"] = round(overlap(tracks, second), 3)
        return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--email", required=True)
    p.add_argument("--size", type=int, default=100)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--sampler", action=argparse.BooleanOptionalAction, default=True)
    a = p.parse_args()
    for k, v in run(a.email, a.size, a.seed, a.sampler).items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
