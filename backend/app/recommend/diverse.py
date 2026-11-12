"""Topluluk tabanlı çeşitlilik (saf): "uzak" yuva ve tek topluluk tavanı.

Topluluklar grafik matrisinin SVD + KMeans ile bölünmesidir (tohumlu, deterministik); tür etiketi
değildir. Uzak yuva, kullanıcının en çok sevdiği topluluklar dışından, topluluk başına en yüksek
skorlu adayı sırayla seçer. Tavan, hiçbir topluluğun listede `max_share`'den fazla yer almasını
engeller; taşan öğelerin yerine sıradaki adaylar gelir.
"""
from collections import Counter
from collections.abc import Iterable

from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

from app.graph.matrix import GraphMatrix
from app.recommend.ppr import Candidate


def community_labels(gm: GraphMatrix, k: int, seed: int) -> dict[int, int]:
    """artist_id -> topluluk etiketi. Aynı matris ve tohum, aynı etiketler."""
    n = gm.node_ids.size
    if n < 4 or k < 2:
        return {int(a): 0 for a in gm.node_ids}
    k = min(k, n // 2)
    comps = max(2, min(32, n - 1))
    emb = normalize(TruncatedSVD(comps, random_state=seed).fit_transform(gm.matrix))
    labels = KMeans(k, n_init=10, random_state=seed).fit_predict(emb)
    return {int(a): int(lab) for a, lab in zip(gm.node_ids, labels, strict=True)}


def home_weights(
    seeds: Iterable[tuple[int, float]], labels: dict[int, int]
) -> dict[int, float]:
    """Topluluk başına pozitif tohum ağırlığı toplamı (kullanıcının "evi")."""
    out: dict[int, float] = {}
    for artist, w in seeds:
        if w > 0 and artist in labels:
            out[labels[artist]] = out.get(labels[artist], 0.0) + float(w)
    return out


def pick_far(
    cands: list[Candidate], labels: dict[int, int], home: dict[int, float], n: int,
    exclude_top: int, true_far: int | None = None,
) -> list[Candidate]:
    """En çok sevilen `exclude_top` topluluk dışından, ev ağırlığı en düşük topluluktan başlayıp
    sırayla topluluk başına en iyi aday. Yeterli topluluk yoksa turlar tekrarlanır.

    `true_far` verilirse iki kademe (list-6): önce ev ağırlığı sıfırdan büyük topluluklar (bitişik
    olası), sonra ev ağırlığı sıfır olan tek topluluktan en çok `true_far` aday. Bitişik topluluk
    yetmezse kalan yer tüm topluluklardan aynı sırayla dolar."""
    if n <= 0:
        return []
    top = set(sorted(home, key=lambda c: (-home[c], c))[:exclude_top])
    by_comm: dict[int, list[Candidate]] = {}
    for c in sorted(cands, key=lambda c: (-c.score, c.artist_id)):
        comm = labels.get(c.artist_id)
        if comm is not None and comm not in top:
            by_comm.setdefault(comm, []).append(c)
    order = sorted(by_comm, key=lambda c: (home.get(c, 0.0), c))

    def take(comms: list[int], k: int) -> list[Candidate]:
        got: list[Candidate] = []
        while len(got) < k and any(by_comm[c] for c in comms):
            for comm in comms:
                if by_comm[comm] and len(got) < k:
                    got.append(by_comm[comm].pop(0))
        return got

    if true_far is None:
        return take(order, n)
    near = [c for c in order if home.get(c, 0.0) > 0]
    distant = [c for c in order if home.get(c, 0.0) <= 0]
    far_comm = sorted(distant, key=lambda c: (-by_comm[c][0].score, c))[:1]
    far_n = min(max(true_far, 0), n) if far_comm else 0
    out = take(near, n - far_n)
    out += take(far_comm, far_n)
    return out + take(order, n - len(out))


def cap_share(
    chosen: list[Candidate], backfill: list[Candidate], labels: dict[int, int], size: int,
    max_share: float,
) -> list[Candidate]:
    """Hiçbir topluluk `max_share * size`'dan fazla olmasın. `chosen` sırası korunur, taşanlar
    düşer; boşluklar `backfill` adaylarıyla (skor sırasıyla, tavanı aşmadan) doldurulur."""
    cap = max(1, int(size * max_share))
    count: Counter[int] = Counter()
    out: list[Candidate] = []
    taken = {c.artist_id for c in chosen}
    for c in chosen:
        comm = labels.get(c.artist_id, -1)
        if count[comm] < cap:
            count[comm] += 1
            out.append(c)
    for c in sorted(backfill, key=lambda c: (-c.score, c.artist_id)):
        if len(out) >= len(chosen):
            break
        comm = labels.get(c.artist_id, -1)
        if c.artist_id not in taken and count[comm] < cap:
            count[comm] += 1
            taken.add(c.artist_id)
            out.append(c)
    return out


_cache: dict[tuple[int, int, int], dict[int, int]] = {}


def cached_labels(gm: GraphMatrix, graph_version: int, k: int, seed: int) -> dict[int, int]:
    key = (graph_version, k, seed)
    if key not in _cache:
        from app.config import get_graph_settings

        if _cache and get_graph_settings().swr_enabled:
            from app.jobs.worker import get_worker

            get_worker().submit(("labels", key), _compute_labels, gm, key)
            return next(iter(_cache.values()))  # etiketler artist_id anahtarlı: eski sürüm güvenli
        _compute_labels(gm, key)
    return _cache[key]


def _compute_labels(gm: GraphMatrix, key: tuple[int, int, int]) -> None:
    labels = community_labels(gm, key[1], key[2])
    _cache.clear()  # yalnız güncel sürüm tutulur
    _cache[key] = labels



