"""Oylama kuyruğuna öneri motoru karışımı: profil -> liste -> oylanmamış öneri parçaları.

Başlık/kapak servisten çözülür ve yalnızca kullanıcıya özel TTL önbelleğine (UserTrackMeta)
yazılır; kütüphane bağlantısı (UserTrackLink) yazılmaz.
"""
from datetime import datetime, timedelta

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import (
    GraphSettings,
    ProfileSettings,
    RecommendSettings,
    get_settings,
)
from app.models import (
    GeneratedList,
    ListenLater,
    ListItem,
    ServiceConnection,
    TasteProfile,
    Track,
    User,
    UserTrackMeta,
    VoteEvent,
)
from app.profile.probe import resolve_seed_cards
from app.profile.service import rebuild_profile
from app.recommend.service import NoGraph, NoProfile, generate_list


def connected_adapter(db: Session, user: User, http: httpx.Client):
    """Kullanıcının bağlı servisinin adaptörü; bağlı servis yoksa ya da jeton alınamazsa None."""
    from app.library import ADAPTERS
    from app.recommend.api import _service_adapter

    for service in db.scalars(
        select(ServiceConnection.service).where(ServiceConnection.user_id == user.id)
    ):
        if service in ADAPTERS:
            try:
                return _service_adapter(db, user, service, http)
            except HTTPException:
                return None
    return None


def _latest_profile(db: Session, user_id) -> TasteProfile | None:
    return db.scalar(
        select(TasteProfile)
        .where(TasteProfile.user_id == user_id)
        .order_by(TasteProfile.version.desc())
        .limit(1)
    )


def _latest_list(db: Session, user_id) -> GeneratedList | None:
    return db.scalar(
        select(GeneratedList)
        .where(GeneratedList.user_id == user_id, GeneratedList.kind == "main")
        .order_by(GeneratedList.id.desc())
        .limit(1)
    )


def _candidates(db: Session, user_id, lst: GeneratedList | None, exclude: set[int]):
    if lst is None:
        return []
    voted = select(VoteEvent.track_id).where(VoteEvent.user_id == user_id)
    items = db.scalars(
        select(ListItem)
        .where(
            ListItem.list_id == lst.id,
            ListItem.track_id.is_not(None),
            ListItem.track_id.not_in(voted),
        )
        .order_by(ListItem.position)
    ).all()
    return [i for i in items if i.track_id not in exclude]


def ensure_fresh_list(
    db: Session, user: User, now: datetime, exclude: set[int], cfg: ProfileSettings,
    rcfg: RecommendSettings, gcfg: GraphSettings,
) -> list[ListItem]:
    """Yeni oylar profile yansır; liste profilden eskiyse ya da tükendiyse yeniden üretilir."""
    profile = _latest_profile(db, user.id)
    if profile is None:
        return []
    new_votes = db.scalar(
        select(func.count()).select_from(VoteEvent).where(
            VoteEvent.user_id == user.id, VoteEvent.created_at > profile.created_at
        )
    )
    if new_votes >= cfg.queue_rebuild_after_votes:
        profile = rebuild_profile(db, user.id, now, cfg, gcfg)
    lst = _latest_list(db, user.id)
    cands = _candidates(db, user.id, lst, exclude)
    if lst is None or lst.profile_version < profile.version or not cands:
        try:
            lst = generate_list(db, user.id, now, rcfg, cfg, gcfg)
        except (NoProfile, NoGraph):
            return []
        cands = _candidates(db, user.id, lst, exclude)
    return cands


def _fresh_metas(db: Session, user_id, ids: list[int], now: datetime) -> dict[int, UserTrackMeta]:
    return {
        m.track_id: m
        for m in db.scalars(
            select(UserTrackMeta).where(
                UserTrackMeta.user_id == user_id,
                UserTrackMeta.track_id.in_(ids),
                UserTrackMeta.expires_at > now,
            )
        )
    }


def _item(it: ListItem, meta: UserTrackMeta, names: dict) -> dict:
    from app.recommend.api import _reason

    return {
        "track": it.track_id, "title": meta.title, "artists": meta.artist_names,
        "image": meta.image_url, "source": "suggested",
        "reasons": [_reason(r, names) for r in it.reasons],
    }


def _names_for(db: Session, cands: list[ListItem]) -> dict:
    from app.recommend.api import _names

    return _names(
        db, {i.artist_id for i in cands} | {r["seed_id"] for i in cands for r in i.reasons}
    )


def later_ids(db: Session, user_id) -> set[int]:
    return set(db.scalars(select(ListenLater.track_id).where(ListenLater.user_id == user_id)))


def _ready(db: Session, user_id, now: datetime, exclude: set[int]):
    """Hazır öneriler: son ana listede, oylanmamış, kullanıcıya özel meta kaydı süresi dolmamış."""
    cands = _candidates(db, user_id, _latest_list(db, user_id), exclude)
    metas = _fresh_metas(db, user_id, [i.track_id for i in cands], now) if cands else {}
    return [i for i in cands if i.track_id in metas], metas


def ready_count(db: Session, user_id, now: datetime, exclude: set[int] | None = None) -> int:
    return len(_ready(db, user_id, now, later_ids(db, user_id) if exclude is None else exclude)[0])


def ready_suggestions(
    db: Session, user: User, now: datetime, need: int, exclude: set[int]
) -> tuple[list[dict], int]:
    """Salt okuma: (en çok `need` hazır öneri öğesi, toplam hazır sayısı). Servis çağrısı,
    liste üretimi ve profil yenilemesi yapmaz (hızlı yol)."""
    ready, metas = _ready(db, user.id, now, exclude)
    take = ready[: max(need, 0)]
    if not take:
        return [], len(ready)
    names = _names_for(db, take)
    return [_item(i, metas[i.track_id], names) for i in take], len(ready)


def suggest_items(
    db: Session, user: User, adapter, now: datetime, need: int, exclude: set[int],
    cfg: ProfileSettings, rcfg: RecommendSettings, gcfg: GraphSettings,
) -> list[dict]:
    """En çok `need` öneri öğesi: {track, title, artists, image, reasons, source}.

    `adapter` çağrılabilirdir (tembel): yalnızca önbellekte olmayan parça için çağrılır."""
    cands = ensure_fresh_list(db, user, now, exclude, cfg, rcfg, gcfg)[: max(need, 0) * 3]
    if not cands or need <= 0:
        return []
    metas = _fresh_metas(db, user.id, [i.track_id for i in cands], now)
    names = _names_for(db, cands)
    isrcs = dict(
        db.execute(select(Track.id, Track.isrc).where(Track.id.in_([i.track_id for i in cands])))
        .all()
    )
    ttl = timedelta(seconds=get_settings().spotify_cache_ttl_seconds)
    svc, calls, out = None, 0, []
    for it in cands:
        meta = metas.get(it.track_id)
        if meta is None and calls < cfg.queue_suggest_batch:
            svc = svc or adapter()
            if svc is None:
                break
            calls += 1
            try:
                card = svc.find_card(isrcs.get(it.track_id), names.get(it.artist_id) or "")
            except (httpx.HTTPError, PermissionError):
                break  # 429/ağ hatası: kalanlar sonraki istekte denenir
            if card is None:
                continue
            meta = db.merge(UserTrackMeta(
                user_id=user.id, track_id=it.track_id, title=card.title,
                artist_names=list(card.artist_names), image_url=card.image_url,
                fetched_at=now, expires_at=now + ttl,
            ))
        if meta is None:
            continue
        out.append(_item(it, meta, names))
        if len(out) >= need:
            break
    db.commit()
    return out


def refill_buffer(
    db: Session, user: User, adapter, now: datetime, cfg: ProfileSettings,
    rcfg: RecommendSettings, gcfg: GraphSettings,
) -> bool:
    """Arka plan doldurucusu (hızlı yol): önce süresi dolmak üzere olan meta kayıtlarını
    tazeler, sonra profil/listeyi güncelleyip hazır öneri sayısını `buffer_target`'a çıkarır.

    `adapter` tembel çağrılabilirdir. Servis hatasında (429/5xx/ağ) sessizce keser; hazır
    kayıtlara dokunulmaz. False dönerse çağıran bir süre geri çekilir."""
    ttl = timedelta(seconds=get_settings().spotify_cache_ttl_seconds)
    box: list = []

    def service():
        if not box:
            box.append(adapter())
        return box[0]

    ok = _refresh_metas(db, user, service, now, ttl, cfg)
    exclude = later_ids(db, user.id)
    cands = ensure_fresh_list(db, user, now, exclude, cfg, rcfg, gcfg)
    if cands:
        metas = _fresh_metas(db, user.id, [i.track_id for i in cands], now)
        ready = sum(1 for i in cands if i.track_id in metas)
        if ready < cfg.buffer_target and ok:
            names = _names_for(db, cands)
            isrcs = dict(db.execute(
                select(Track.id, Track.isrc).where(Track.id.in_([i.track_id for i in cands]))
            ).all())
            calls = 0
            for it in cands:
                if ready >= cfg.buffer_target or calls >= cfg.refill_batch:
                    break
                if it.track_id in metas:
                    continue
                svc = service()
                if svc is None:
                    break
                calls += 1
                try:
                    card = svc.find_card(isrcs.get(it.track_id), names.get(it.artist_id) or "")
                except (httpx.HTTPError, PermissionError):
                    ok = False
                    break
                if card is None:
                    continue
                db.merge(UserTrackMeta(
                    user_id=user.id, track_id=it.track_id, title=card.title,
                    artist_names=list(card.artist_names), image_url=card.image_url,
                    fetched_at=now, expires_at=now + ttl,
                ))
                ready += 1
    if cfg.queue_sampler_enabled and ok:
        # PR-6: sonda/joker kartları (omurga) önceden çözülür; kuyruk istek anında servis çağırmaz.
        ok = resolve_seed_cards(
            db, user.id, service, now, cfg, rcfg, max(cfg.refill_batch // 2, 1), user.id.int % 10007
        )
    db.commit()
    return ok


def _refresh_metas(db: Session, user: User, service, now: datetime, ttl: timedelta,
                   cfg: ProfileSettings) -> bool:
    """Süresi dolmadan, TTL'in `meta_refresh_at` oranını geçen oylanmamış meta kayıtlarını
    yeniler (G6). Hata olursa kayda dokunmadan keser ve False döner."""
    from app.recommend.api import _names

    soon = now + ttl * (1 - cfg.meta_refresh_at)
    voted = select(VoteEvent.track_id).where(VoteEvent.user_id == user.id)
    rows = db.execute(
        select(UserTrackMeta, Track.isrc, Track.artist_id)
        .join(Track, Track.id == UserTrackMeta.track_id)
        .where(
            UserTrackMeta.user_id == user.id,
            UserTrackMeta.expires_at > now,
            UserTrackMeta.expires_at <= soon,
            UserTrackMeta.track_id.not_in(voted),
        )
        .order_by(UserTrackMeta.expires_at)
        .limit(cfg.meta_refresh_batch)
    ).all()
    if not rows:
        return True
    svc = service()
    if svc is None:
        return True
    names = _names(db, {r[2] for r in rows if r[2] is not None})
    for meta, isrc, artist_id in rows:
        try:
            card = svc.find_card(isrc, names.get(artist_id) or "")
        except (httpx.HTTPError, PermissionError):
            return False
        if card is None:
            continue
        meta.title, meta.artist_names = card.title, list(card.artist_names)
        meta.image_url, meta.fetched_at, meta.expires_at = card.image_url, now, now + ttl
    return True
