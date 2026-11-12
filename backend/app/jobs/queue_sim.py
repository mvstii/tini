"""Kuyruk simülasyonu (PR-6, salt okuma): bir kullanıcı için 100 kartlık kuyruk üretir ve
KESIF_PLANI kabul ölçütlerini (Çeşitlilik, Tazelik) ölçüp geçti/kaldı yazdırır.
Hiçbir şey yazmaz (hızlı yol, servis çağrısı yok).

Ölçülenler: 20'lik en kötü pencerede ana tür sayısı, 20'lik pencerede aynı sanatçı üst sınırı,
sanatçı aralığı ihlali (son 4), aynı şarkı sürümü, en uzun aynı alt tür serisi, iki oturumun
ilk 20 kartının örtüşmesi (ilk oturumun ilk 10 kartı görülmüş sayılarak), aynı tohumla
özdeşlik. Bilgi: keşif payı, türü bilinmeyen kart payı.
ÖLÇÜLMEYEN: Kapsama ölçütü (ilk 50/200 oyda tür sayısı) oy simülasyonu ister; burada yok.
Zamanlama (`timing`): istek başına süre, sorgu sayısı, veritabanı süresi, aşama dökümü ve
`select 1` gidiş-dönüşü. Uygulama bu makinede, veritabanı uzakta koşuyorsa süre gidiş-dönüşle
şişer; `non_rtt_ms` (süre - sorgu × gidiş-dönüş) aynı bölgedeki sunucu için kaba bir tahmindir.
CLI: python -m app.jobs.queue_sim --email EPOSTA [--size 100] [--seed 1] [--sampler/--no-sampler]
     [--pairs 5]  (tazelik kapısı bu kadar tohum çiftinin ortalamasıdır)
"""
import argparse
import statistics
import time
from collections import Counter
from itertools import groupby

from fastapi.testclient import TestClient
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app import timing
from app.catalog.tags import load_genre_pairs
from app.config import ProfileSettings, get_profile_settings
from app.db import make_engine
from app.deps import current_user, get_db
from app.main import app
from app.models import ListenLater, User, UserTrackLink, VoteEvent
from app.profile.queue import song_key
from app.profile.service import unheard_statuses
from app.profile.track_artists import track_artists

# Kabul ölçütleri (docs/KESIF_PLANI.md "Kabul ölçütleri" tablosu); algoritma parametresi değildir.
WINDOW = 20
MIN_MAIN_GENRES = 5
MAX_SAME_ARTIST = 2
ARTIST_GAP = 4
MAX_SUB_RUN = 1
MAX_FIRST_OVERLAP = 0.20
# Tazelik: ikinci oturumdan önce ilk oturumun baştaki bu kadar kartı görülmüş sayılır (istemcinin
# `recent` parametresiyle; yazma yok). Geliştirici kararı, 11 Kasım 2026.
SEEN_BETWEEN_SESSIONS = 10
# Tazelik kapısı bu kadar örtüşmeyen tohum çiftinin ortalamasıdır: tek çiftte 1 kart 0,05 oynatır
# ve sonuç tohum seçimine bağlı kalır. Geliştirici kararı, 12 Kasım 2026.
FRESHNESS_PAIRS = 5
RTT_SAMPLES = 5  # `select 1` gidiş-dönüş örneği (ortanca alınır)


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


def pair_seeds(seed: int, pairs: int) -> list[tuple[int, int]]:
    """Örtüşmeyen tohum çiftleri; ilki kapının ölçtüğü (seed, seed + 1) çiftidir."""
    return [(seed + 2 * k, seed + 2 * k + 1) for k in range(max(pairs, 1))]


def freshness_stats(values: list[float]) -> dict:
    """Çiftler arası tazelik: ortalama (kapı ölçütü), dağılım ve eşiği geçen çift sayısı."""
    if not values:
        return {"pairs": 0}
    return {
        "pairs": len(values), "mean": round(sum(values) / len(values), 3),
        "min": min(values), "max": max(values),
        "passing": sum(1 for v in values if v < MAX_FIRST_OVERLAP), "values": values,
    }


def sub_runs(cards: list[dict]) -> list[dict]:
    """Tanı: 2+ uzunluktaki aynı alt tür serileri; konum (0 tabanlı), alt tür ve kart kaynakları."""
    out, pos = [], 0
    for sub, grp in groupby(cards, key=lambda c: c.get("sub")):
        run = list(grp)
        if sub is not None and len(run) > 1:
            out.append({
                "at": pos, "sub": sub, "sources": [c.get("source") or "library" for c in run],
            })
        pos += len(run)
    return out


def discovery_positions(cards: list[dict]) -> list[int]:
    """Tanı: kütüphane dışı kartların sırası (0 tabanlı); sona yığılma buradan görülür."""
    return [n for n, c in enumerate(cards) if c.get("source") not in (None, "library")]


def overlap_cards(cards: list[dict], other: list[int], width: int = WINDOW) -> list[dict]:
    """Tanı: iki oturumun ilk `width` kartında ortak çıkanlar; konumlar (0 tabanlı), kaynak, tür
    ve o ana türün bu partideki kart sayısı (`main_n`; küçükse tür havuzu dar demektir)."""
    where = {t: n for n, t in enumerate(other[:width])}
    per_main = Counter(c.get("main") for c in cards)
    return [
        {
            "track": c["track"], "at": n, "at2": where[c["track"]],
            "source": c.get("source") or "library",
            "main": c.get("main"), "sub": c.get("sub"), "main_n": per_main[c.get("main")],
        }
        for n, c in enumerate(cards[:width]) if c["track"] in where
    ]


def library_head(
    cands: list[tuple[int, int]], voted_artists: set[int], pool: set[int]
) -> tuple[dict, dict[int, dict]]:
    """Tanı: `order_active`'in katı önceliklerinin baş tarafı ne kadar daralttığı.
    cands: (parça, sanatçı). Kademe 0 = oy almamış sanatçı (her zaman önce gelir).
    Döner: özet ve parça -> {tier, artist_tracks, pool}. `artist_tracks` 1 ise parça her
    tohumda sanatçısının ilk tur adayıdır; `pool` havuz bonusu aldığını gösterir."""
    per_artist = Counter(a for _, a in cands)
    pooled = {a for t, a in cands if t in pool}
    tier0 = set(per_artist) - voted_artists
    summary = {
        "tier0_artists": len(tier0),
        "tier1_artists": len(per_artist) - len(tier0),
        "tier0_single_track_artists": sum(1 for a in tier0 if per_artist[a] == 1),
        "tier0_pool_artists": len(tier0 & pooled),
        "tracks": len(cands),
    }
    info = {
        t: {"tier": 1 if a in voted_artists else 0, "artist_tracks": per_artist[a],
            "pool": t in pool}
        for t, a in cands
    }
    return summary, info


def _library_state(db: Session, user: User, cfg: ProfileSettings) -> tuple:
    """Kuyruğun kütüphane adayları (yaklaşık: önbellek süresi ve sürüm elemesi uygulanmaz),
    oy almış sanatçılar ve Unheard havuzu; `api.queue` ile aynı kurallar, salt okuma."""
    voted = select(VoteEvent.track_id).where(VoteEvent.user_id == user.id)
    later = select(ListenLater.track_id).where(ListenLater.user_id == user.id)
    tracks = set(db.scalars(
        select(UserTrackLink.track_id).where(
            UserTrackLink.user_id == user.id,
            UserTrackLink.track_id.not_in(voted),
            UserTrackLink.track_id.not_in(later),
        )
    ))
    voted_artists = set(track_artists(db, user.id, db.scalars(voted)).values())
    pool = {s.track_id for s in unheard_statuses(db, user.id, cfg) if s.state != "expired"}
    return list(track_artists(db, user.id, tracks).items()), voted_artists, pool


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


def stage_breakdown(laps: list[tuple[str, int, float]]) -> dict[str, dict]:
    """Kümülatif (aşama, sorgu sayısı, DB ms) işaretlerinden aşama başına fark."""
    out: dict[str, dict] = {}
    prev_n, prev_ms = 0, 0.0
    for name, n, ms in laps:
        cur = out.setdefault(name, {"queries": 0, "db_ms": 0.0})
        cur["queries"] += n - prev_n
        cur["db_ms"] = round(cur["db_ms"] + ms - prev_ms, 1)
        prev_n, prev_ms = n, ms
    return out


def _median_sample(samples: list[dict]) -> dict:
    stages: dict[str, dict] = {}
    for name in dict.fromkeys(n for s in samples for n in s["stages"]):
        rows = [s["stages"][name] for s in samples if name in s["stages"]]
        stages[name] = {
            k: round(statistics.median(r[k] for r in rows), 1)
            for k in ("ms", "queries", "db_ms")
        }
    return {
        **{k: round(statistics.median(s[k] for s in samples), 1)
           for k in ("total_ms", "queries", "db_ms")},
        "stages": stages,
    }


def timing_summary(samples: list[dict], rtt_ms: list[float]) -> dict:
    """İstek örneklerinden özet. İlk istek soğuktur (graf matrisi kurulur), ayrı verilir; kalanı
    ortanca ve en kötü. `non_rtt_ms` = süre - sorgu × gidiş-dönüş (kaba tahmin, alt sınır 0)."""
    rtt = round(statistics.median(rtt_ms), 1) if rtt_ms else 0.0
    out: dict = {"rtt_ms": rtt, "requests": len(samples)}
    if not samples:
        return out
    warm = samples[1:] or samples
    med = _median_sample(warm)
    out["cold"] = {k: round(samples[0][k], 1) for k in ("total_ms", "queries", "db_ms")}
    out["warm_median"] = med
    out["warm_max_total_ms"] = round(max(s["total_ms"] for s in warm), 1)
    out["non_rtt_ms"] = round(max(med["total_ms"] - med["queries"] * rtt, 0.0), 1)
    return out


class _Timer:
    """Motor ve aşama zamanlayıcı kancaları (salt ölçüm; `close` ile geri alınır)."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self.count, self.db_ms = 0, 0.0
        self.laps: list[tuple[str, int, float]] = []
        self.stage_ms: dict[str, float] = {}
        self.samples: list[dict] = []
        self._t0: list[float] = []
        self._lap = timing.Stages.lap
        timer = self

        def lap(stages, name: str) -> None:
            timer._lap(stages, name)
            timer.laps.append((name, timer.count, timer.db_ms))
            timer.stage_ms = stages.as_dict()

        timing.Stages.lap = lap
        event.listen(engine, "before_cursor_execute", self._before)
        event.listen(engine, "after_cursor_execute", self._after)

    def _before(self, conn, cur, statement, params, ctx, many) -> None:
        self._t0.append(time.perf_counter())

    def _after(self, conn, cur, statement, params, ctx, many) -> None:
        self.count += 1
        self.db_ms += (time.perf_counter() - self._t0.pop()) * 1000

    def get(self, client, url: str) -> dict:
        self.count, self.db_ms, self.laps, self.stage_ms = 0, 0.0, [], {}
        t = time.perf_counter()
        body = client.get(url).json()
        total = (time.perf_counter() - t) * 1000
        stages = stage_breakdown(self.laps)
        for name, s in stages.items():
            s["ms"] = self.stage_ms.get(name, 0.0)
        self.samples.append(
            {"total_ms": total, "queries": self.count, "db_ms": self.db_ms, "stages": stages}
        )
        return body

    def close(self) -> None:
        timing.Stages.lap = self._lap
        event.remove(self.engine, "before_cursor_execute", self._before)
        event.remove(self.engine, "after_cursor_execute", self._after)


def measure_rtt(db: Session, n: int = RTT_SAMPLES) -> list[float]:
    out = []
    for _ in range(n + 1):
        t = time.perf_counter()
        db.execute(text("select 1"))
        out.append((time.perf_counter() - t) * 1000)
    return out[1:]  # ilki bağlantı kurulumunu içerir


def queue_url(size: int, seed: int, recent: list[int] = ()) -> str:
    """Kuyruk isteği; `recent` istemcide zaten görülmüş parçalardır (eskiden yeniye)."""
    return f"/votes/queue?limit={size}&seed={seed}" + "".join(f"&recent={t}" for t in recent)


def _genre_of_item(item: dict, pair: tuple | None) -> tuple:
    """Sonda/joker kartında tür kapsama gerekçesinden, diğerlerinde sanatçı etiketinden gelir."""
    for r in item.get("reasons") or []:
        if r.get("kind") == "coverage":
            return r.get("main_genre"), r.get("sub_genre")
    return pair or (None, None)


def run(
    email: str, size: int = 100, seed: int = 1, sampler: bool = True,
    pairs: int = FRESHNESS_PAIRS,
) -> dict:
    cfg = ProfileSettings(queue_sampler_enabled=sampler, fast_queue_enabled=True)
    engine = make_engine()
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit(f"Kullanıcı yok: {email}")
        app.dependency_overrides[current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_profile_settings] = lambda: cfg
        rtt = measure_rtt(db)
        timer = _Timer(engine)
        try:
            client = TestClient(app)

            def get(url: str) -> dict:
                return timer.get(client, url)

            one = get(queue_url(size, seed))
            seen = [i["track"] for i in one["items"][:SEEN_BETWEEN_SESSIONS]]
            runs = [
                one,
                get(queue_url(size, seed + 1, seen)),
                get(queue_url(size, seed)),
                get(queue_url(size, seed + 1)),
            ]
            # Tek çift gürültülüdür (1 kart = 0,05); kapı çiftlerin ortalamasına bakar.
            fresh_values = [overlap(
                [i["track"] for i in one["items"][:WINDOW]],
                [i["track"] for i in runs[1]["items"][:WINDOW]],
            )]
            for a, b in pair_seeds(seed, pairs)[1:]:
                head = [i["track"] for i in get(queue_url(size, a))["items"]]
                nxt = get(queue_url(size, b, head[:SEEN_BETWEEN_SESSIONS]))["items"]
                fresh_values.append(overlap(head[:WINDOW], [i["track"] for i in nxt[:WINDOW]]))
        finally:
            timer.close()
            app.dependency_overrides.clear()
        first = runs[0]["items"]
        tracks = [i["track"] for i in first]
        # Paylaşılan sanatçı, yoksa kullanıcıya özel bağ (kademe B); yalnız `Track.artist_id`
        # okumak bağlı parçaları sanatçısız ve türsüz gösteriyordu.
        artist_of = track_artists(db, user.id, tracks)
        genre_of = load_genre_pairs(db, set(artist_of.values()))
        out_resolved = sum(1 for t in tracks if t in artist_of)
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
        out["sub_runs"] = sub_runs(cards)
        out["discovery_positions"] = discovery_positions(cards)
        out["artist_known_share"] = round(out_resolved / len(tracks), 2) if tracks else 0.0
        out["requested"] = size
        out["gumbel_tau"] = cfg.queue_gumbel_tau
        out["main_counts"] = dict(Counter(c["main"] for c in cards).most_common())
        out["algo_version"] = runs[0]["algo_version"]
        # Tanı: 0 kartın nedeni (yanlış veritabanı / süresi dolmuş önbellek) buradan okunur.
        out["db"] = f"{engine.url.host}/{engine.url.database}"
        out["remaining"] = runs[0].get("remaining")
        out["stale"] = runs[0].get("stale")
        second = [i["track"] for i in runs[1]["items"]]
        again = [i["track"] for i in runs[2]["items"]]
        out["first_20_overlap"] = round(overlap(tracks[:WINDOW], second[:WINDOW]), 3)
        raw = [i["track"] for i in runs[3]["items"]]
        out["freshness_pairs"] = freshness_stats([round(v, 3) for v in fresh_values])
        out["first_20_overlap_unseen"] = round(overlap(tracks[:WINDOW], raw[:WINDOW]), 3)
        out["two_session_overlap"] = round(overlap(tracks, second), 3)
        out["overlap_cards"] = overlap_cards(cards, second)
        out["overlap_cards_unseen"] = overlap_cards(cards, raw)
        # Tanı: ortak kartlar katı öncelikten mi geliyor (kademe, tek parçalı sanatçı, havuz)?
        out["library_head"], info = library_head(*_library_state(db, user, cfg))
        for c in out["overlap_cards"] + out["overlap_cards_unseen"]:
            c.update(info.get(c["track"], {}))
        out["head_20_library"] = dict(Counter(
            (info[t]["tier"], info[t]["pool"]) for t in tracks[:WINDOW] if t in info
        ))
        out["timing"] = timing_summary(timer.samples, rtt)
        out["gate"] = gate(out, out["freshness_pairs"]["mean"], tracks == again)
        return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--email", required=True)
    p.add_argument("--size", type=int, default=100)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--sampler", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--pairs", type=int, default=FRESHNESS_PAIRS)
    a = p.parse_args()
    out = run(a.email, a.size, a.seed, a.sampler, a.pairs)
    verdicts = out.pop("gate")
    for k, v in out.items():
        print(f"{k}: {v}")
    measurable = out["cards"] >= WINDOW
    if not measurable:
        print(f"UYARI: {out['cards']} kart; {WINDOW}'lik pencere ölçütleri anlamsız.")
    print("--- kapı (Çeşitlilik + Tazelik; Kapsama ölçülmedi) ---")
    for name, (ok, detail) in verdicts.items():
        label = ("GEÇTİ" if ok else "KALDI") if measurable else "ÖLÇÜLEMEDİ"
        print(f"{label}  {name}: {detail}")


if __name__ == "__main__":
    main()
