"""Kuyruk simülasyonu (PR-6, salt okuma): bir kullanıcı için 100 kartlık kuyruk üretir ve
KESIF_PLANI kabul ölçütlerini (Çeşitlilik, Tazelik) ölçüp geçti/kaldı yazdırır.
Hiçbir şey yazmaz (hızlı yol, servis çağrısı yok).

Ölçülenler: 20'lik en kötü pencerede ana tür sayısı, 20'lik pencerede aynı sanatçı üst sınırı,
sanatçı aralığı ihlali (son 4), aynı şarkı sürümü, en uzun aynı alt tür serisi, iki oturumun
ilk 20 kartının örtüşmesi, aynı tohumla özdeşlik. Bilgi: keşif payı, türü bilinmeyen kart payı.
ÖLÇÜLMEYEN: Kapsama ölçütü (ilk 50/200 oyda tür sayısı) oy simülasyonu ister; burada yok.
CLI: python -m app.jobs.queue_sim --email EPOSTA [--size 100] [--seed 1] [--sampler/--no-sampler]
"""
import argparse
from collections import Counter
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
from app.profile.queue import song_key

# Kabul ölçütleri (docs/KESIF_PLANI.md "Kabul ölçütleri" tablosu); algoritma parametresi değildir.
WINDOW = 20
MIN_MAIN_GENRES = 5
MAX_SAME_ARTIST = 2
ARTIST_GAP = 4
MAX_SUB_RUN = 1
MAX_FIRST_OVERLAP = 0.20


def longest_run(labels: list) -> int:
    """En uzun ardışık aynı etiket serisi; bilinmeyen (None) seri sayılmaz, seriyi böler."""
    return max((len(list(g)) for k, g in groupby(labels) if k is not None), default=0)


def window_distinct(labels: list, width: int = WINDOW) -> float:
    """Kayan pencerelerde ortalama ayrı etiket sayısı."""
    if len(labels) < width:
        return float(len(set(labels)))
    wins = [len(set(labels[i:i + width])) for i in range(len(labels) - width + 1)]
    return sum(wins) / len(wins)


def _windows(items: list, width: int) -> list[list]:
    if len(items) <= width:
        return [items]
    return [items[i:i + width] for i in range(len(items) - width + 1)]


def min_window_distinct(labels: list, width: int = WINDOW) -> int:
    """En kötü penceredeki ayrı (bilinen) etiket sayısı."""
    return min(len({x for x in w if x is not None}) for w in _windows(labels, width))


def max_per_window(labels: list, width: int = WINDOW) -> int:
    """Herhangi bir pencerede tek bir (bilinen) etiketin en çok görülme sayısı."""
    best = 0
    for w in _windows(labels, width):
        counts = Counter(x for x in w if x is not None)
        best = max(best, max(counts.values(), default=0))
    return best


def artist_gap_violations(artists: list, gap: int = ARTIST_GAP) -> int:
    """Önceki `gap` kart içinde aynı sanatçısı bulunan kart sayısı."""
    return sum(
        1 for i, a in enumerate(artists)
        if a is not None and a in artists[max(0, i - gap):i]
    )


def duplicate_keys(keys: list) -> int:
    """Aynı şarkı anahtarının fazladan görülme sayısı (None sayılmaz)."""
    counts = Counter(k for k in keys if k is not None)
    return sum(n - 1 for n in counts.values())


def overlap(a: list[int], b: list[int]) -> float:
    return len(set(a) & set(b)) / max(min(len(a), len(b)), 1)


def metrics(cards: list[dict]) -> dict:
    """cards: sıralı {track, artist, main, sub, key, source} sözlükleri."""
    artists = [c.get("artist") for c in cards]
    mains = [c.get("main") for c in cards]
    n = max(len(cards), 1)
    return {
        "cards": len(cards),
        "min_main_genres_per_20": min_window_distinct(mains),
        "avg_main_genres_per_20": round(window_distinct([m for m in mains if m is not None]), 2),
        "max_same_artist_per_20": max_per_window(artists),
        "artist_gap_violations": artist_gap_violations(artists),
        "duplicate_songs": duplicate_keys([c.get("key") for c in cards]),
        "longest_same_sub_genre_run": longest_run([c.get("sub") for c in cards]),
        "longest_same_genre_run": longest_run(mains),
        "discovery_share": round(
            sum(1 for c in cards if c.get("source") not in (None, "library")) / n, 3
        ),
        "unknown_genre_share": round(sum(1 for m in mains if m is None) / n, 3),
    }


def gate(m: dict, first_overlap: float, same_seed_identical: bool) -> dict[str, tuple[bool, str]]:
    """Ölçüt adı -> (geçti mi, 'ölçülen / eşik')."""
    return {
        "main_genres_per_20": (
            m["min_main_genres_per_20"] >= MIN_MAIN_GENRES,
            f"{m['min_main_genres_per_20']} / >= {MIN_MAIN_GENRES}",
        ),
        "same_artist_per_20": (
            m["max_same_artist_per_20"] <= MAX_SAME_ARTIST,
            f"{m['max_same_artist_per_20']} / <= {MAX_SAME_ARTIST}",
        ),
        "artist_gap": (m["artist_gap_violations"] == 0, f"{m['artist_gap_violations']} / 0"),
        "duplicate_songs": (m["duplicate_songs"] == 0, f"{m['duplicate_songs']} / 0"),
        "sub_genre_run": (
            m["longest_same_sub_genre_run"] <= MAX_SUB_RUN,
            f"{m['longest_same_sub_genre_run']} / <= {MAX_SUB_RUN}",
        ),
        "freshness": (
            first_overlap < MAX_FIRST_OVERLAP, f"{first_overlap:.3f} / < {MAX_FIRST_OVERLAP}"
        ),
        "determinism": (same_seed_identical, f"{same_seed_identical} / True"),
    }


def _genre_of_item(item: dict, pair: tuple | None) -> tuple:
    """Sonda/joker kartında tür kapsama gerekçesinden, diğerlerinde sanatçı etiketinden gelir."""
    for r in item.get("reasons") or []:
        if r.get("kind") == "coverage":
            return r.get("main_genre"), r.get("sub_genre")
    return pair or (None, None)


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
                for s in (seed, seed + 1, seed)
            ]
        finally:
            app.dependency_overrides.clear()
        first = runs[0]["items"]
        tracks = [i["track"] for i in first]
        artist_of = dict(
            db.execute(select(Track.id, Track.artist_id).where(Track.id.in_(tracks))).all()
        )
        genre_of = load_genre_pairs(db, {a for a in artist_of.values() if a is not None})
        cards = []
        for i in first:
            artist = artist_of.get(i["track"])
            main, sub = _genre_of_item(i, genre_of.get(artist))
            key = (
                repr(song_key(i["title"], i.get("artists"), cfg.queue_version_markers))
                if i.get("title") else None
            )
            cards.append({
                "track": i["track"], "artist": artist, "main": main, "sub": sub,
                "key": key, "source": i.get("source"),
            })
        out = metrics(cards)
        out["requested"] = size
        out["algo_version"] = runs[0]["algo_version"]
        second = [i["track"] for i in runs[1]["items"]]
        again = [i["track"] for i in runs[2]["items"]]
        out["first_20_overlap"] = round(overlap(tracks[:WINDOW], second[:WINDOW]), 3)
        out["two_session_overlap"] = round(overlap(tracks, second), 3)
        out["gate"] = gate(out, out["first_20_overlap"], tracks == again)
        return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--email", required=True)
    p.add_argument("--size", type=int, default=100)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--sampler", action=argparse.BooleanOptionalAction, default=True)
    a = p.parse_args()
    out = run(a.email, a.size, a.seed, a.sampler)
    verdicts = out.pop("gate")
    for k, v in out.items():
        print(f"{k}: {v}")
    if out["cards"] < WINDOW:
        print(f"UYARI: {out['cards']} kart; {WINDOW}'lik pencere ölçütleri anlamsız.")
    print("--- kapı (Çeşitlilik + Tazelik; Kapsama ölçülmedi) ---")
    for name, (ok, detail) in verdicts.items():
        print(f"{'GEÇTİ' if ok else 'KALDI'}  {name}: {detail}")


if __name__ == "__main__":
    main()
