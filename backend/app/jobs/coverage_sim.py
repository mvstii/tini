"""Kapsama simülasyonu (salt okuma): KESIF_PLANI "Kapsama" kabul ölçütünü ölçer.

Ölçüt: ilk 50 oyda >= 10 ana tür; ilk 200 oyda >= 30 alt tür (sert kaçınılanlar hariç).

Yöntem: kaynak kullanıcının kütüphanesinin kopyasıyla geçici, oy vermemiş bir kullanıcı kurulur;
kuyruk (`GET /votes/queue`) partiler halinde istenir ve her partideki kartlar tohumlu,
deterministik bir kurala göre oylanır (oy parçadan türetilir, türden bağımsızdır). Her şey tek
bir dış işlemde yapılır ve sonunda ROLLBACK edilir: veritabanına hiçbir şey yazılmaz, servis
çağrısı ve arka plan işi yoktur.
SINIR: Yeni kullanıcının sunum önbelleği/öneri tablosu boştur ve sonda/joker kartları dış
servis çözümlemesi ister; bu yüzden ölçüm kütüphane + örnekleyici yolunu (`queue-8`) kapsar,
sonda/joker katkısını kapsamaz. Gerçek kapsama bu sayının altında kalmaz ama bu araçla kanıtlanmaz.
CLI: python -m app.jobs.coverage_sim --email KAYNAK_EPOSTA [--votes 200] [--batch 20] [--seed 1]
     [--sampler/--no-sampler]
"""
import argparse
import hashlib
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import insert, literal, select
from sqlalchemy.orm import Session

from app.catalog.tags import load_genre_pairs
from app.config import ProfileSettings, get_profile_settings
from app.db import make_engine
from app.deps import current_user, get_db
from app.jobs.queue_sim import _genre_of_item, queue_url
from app.main import app
from app.models import User, UserTrackArtist, UserTrackLink, UserTrackMeta, VoteEvent
from app.profile.track_artists import track_artists

# Kabul ölçütleri (docs/KESIF_PLANI.md "Kabul ölçütleri" tablosu); algoritma parametresi değildir.
MAIN_CHECKPOINT = 50
MIN_MAIN_GENRES = 10
SUB_CHECKPOINT = 200
MIN_SUB_GENRES = 30
AWFUL = 1
# Simüle oy dağılımı: (üst sınır yüzdelik, oy). Parçadan türetilir; tür bilgisi içermez.
_VOTE_BANDS = ((10, 1), (20, 2), (35, 3), (65, 4), (90, 5), (100, 6))


def vote_for(seed: int, track: int) -> int:
    """Aynı (tohum, parça) için hep aynı oy; dağılım `_VOTE_BANDS`."""
    h = int.from_bytes(hashlib.sha256(f"{seed}:{track}".encode()).digest()[:4], "big") % 100
    return next(v for cap, v in _VOTE_BANDS if h < cap)


def coverage_at(votes: Sequence[dict], n: int) -> dict:
    """İlk `n` oyda ayrı ana/alt tür sayısı. `votes`: sıralı {main, sub, vote}.
    `*_excl_avoided`: oyu Awful olan alt türler (sert kaçınılan) sayıdan çıkarılır."""
    head = list(votes[:n])
    avoided = {v["sub"] for v in head if v["vote"] == AWFUL and v.get("sub")}
    mains = {v["main"] for v in head if v.get("main")}
    subs = {v["sub"] for v in head if v.get("sub")}
    avoided_mains = {
        m for m in mains
        if all(v["vote"] == AWFUL for v in head if v.get("main") == m)
    }
    return {
        "votes": len(head), "main_genres": len(mains), "sub_genres": len(subs),
        "main_excl_avoided": len(mains - avoided_mains),
        "sub_excl_avoided": len(subs - avoided),
        "unknown_genre": sum(1 for v in head if not v.get("main")),
    }


def gate(votes: Sequence[dict]) -> dict[str, tuple[bool, str]]:
    """Ölçüt adı -> (geçti mi, 'ölçülen / eşik'). Yeterli oy yoksa ölçülemez (geçti=False)."""
    m, s = coverage_at(votes, MAIN_CHECKPOINT), coverage_at(votes, SUB_CHECKPOINT)
    return {
        f"main_genres_first_{MAIN_CHECKPOINT}": (
            m["votes"] >= MAIN_CHECKPOINT and m["main_excl_avoided"] >= MIN_MAIN_GENRES,
            f"{m['main_excl_avoided']} (oy {m['votes']}) / >= {MIN_MAIN_GENRES}",
        ),
        f"sub_genres_first_{SUB_CHECKPOINT}": (
            s["votes"] >= SUB_CHECKPOINT and s["sub_excl_avoided"] >= MIN_SUB_GENRES,
            f"{s['sub_excl_avoided']} (oy {s['votes']}) / >= {MIN_SUB_GENRES}",
        ),
    }


def _clone_user(db: Session, source: User) -> User:
    """Kaynağın kütüphanesini (bağlar, önbellek, özel sanatçı bağları) oysuz yeni kullanıcıya
    kopyalar. Çağıran dış işlemi ROLLBACK eder; kalıcı hiçbir şey kalmaz."""
    sim = User(id=uuid.uuid4(), email=f"coverage-sim-{uuid.uuid4().hex[:8]}@sim.invalid",
               password_hash="x")
    db.add(sim)
    db.flush()
    expires = datetime.now(UTC) + timedelta(days=1)
    for model, cols in (
        (UserTrackLink, ("service", "external_id", "track_id")),
        (UserTrackArtist, ("track_id", "artist_id", "confidence", "method")),
    ):
        db.execute(insert(model).from_select(
            ["user_id", *cols],
            select(literal(sim.id), *(getattr(model, c) for c in cols))
            .where(model.user_id == source.id),
        ))
    db.execute(insert(UserTrackMeta).from_select(
        ["user_id", "track_id", "title", "artist_names", "duration_ms", "image_url", "expires_at"],
        select(
            literal(sim.id), UserTrackMeta.track_id, UserTrackMeta.title,
            UserTrackMeta.artist_names, UserTrackMeta.duration_ms, UserTrackMeta.image_url,
            literal(expires),
        ).where(UserTrackMeta.user_id == source.id),
    ))
    db.flush()
    return sim


def run(
    email: str, votes: int = SUB_CHECKPOINT, batch: int = 20, seed: int = 1, sampler: bool = True
) -> dict:
    cfg = ProfileSettings(queue_sampler_enabled=sampler, fast_queue_enabled=True)
    engine = make_engine()
    conn = engine.connect()
    outer = conn.begin()
    try:
        db = Session(bind=conn, join_transaction_mode="create_savepoint")
        source = db.scalar(select(User).where(User.email == email))
        if source is None:
            raise SystemExit(f"Kullanıcı yok: {email}")
        sim = _clone_user(db, source)
        app.dependency_overrides[current_user] = lambda: sim
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_profile_settings] = lambda: cfg
        client = TestClient(app)
        seq: list[dict] = []
        rounds = 0
        while len(seq) < votes:
            body = client.get(queue_url(batch, seed + rounds)).json()
            items = body.get("items") or []
            if not items:
                break
            tracks = [i["track"] for i in items]
            artist_of = track_artists(db, sim.id, tracks)
            genre_of = load_genre_pairs(db, set(artist_of.values()))
            for i in items[: votes - len(seq)]:
                main, sub = _genre_of_item(i, genre_of.get(artist_of.get(i["track"])))
                v = vote_for(seed, i["track"])
                db.add(VoteEvent(user_id=sim.id, track_id=i["track"], vote=v))
                seq.append({"track": i["track"], "main": main, "sub": sub, "vote": v,
                            "source": i.get("source")})
            db.commit()  # savepoint; dış işlem sonunda geri alınır
            rounds += 1
        out = {
            "db": f"{engine.url.host}/{engine.url.database}",
            "algo_version": body.get("algo_version") if seq else None,
            "votes_cast": len(seq), "rounds": rounds, "batch": batch, "seed": seed,
            "checkpoints": {n: coverage_at(seq, n) for n in (50, 100, 200) if n <= votes},
            "gate": gate(seq),
        }
        return out
    finally:
        app.dependency_overrides.clear()
        outer.rollback()
        conn.close()
        engine.dispose()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--email", required=True)
    p.add_argument("--votes", type=int, default=SUB_CHECKPOINT)
    p.add_argument("--batch", type=int, default=20)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--sampler", action=argparse.BooleanOptionalAction, default=True)
    a = p.parse_args()
    out = run(a.email, a.votes, a.batch, a.seed, a.sampler)
    verdicts = out.pop("gate")
    for k, v in out.items():
        print(f"{k}: {v}")
    print("--- kapı (Kapsama; sonda/joker katkısı ölçülmez) ---")
    for name, (ok, detail) in verdicts.items():
        print(f"{'GEÇTİ' if ok else 'KALDI'}  {name}: {detail}")


if __name__ == "__main__":
    main()
