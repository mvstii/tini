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
    ListItem,
    ServiceConnection,
    TasteProfile,
    Track,
    User,
    UserTrackMeta,
    VoteEvent,
)
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


def suggest_items(
    db: Session, user: User, adapter, now: datetime, need: int, exclude: set[int],
    cfg: ProfileSettings, rcfg: RecommendSettings, gcfg: GraphSettings,
) -> list[dict]:
    """En çok `need` öneri öğesi: {track, title, artists, image, reasons, source}.

    `adapter` çağrılabilirdir (tembel): yalnızca önbellekte olmayan parça için çağrılır."""
    from app.recommend.api import _names, _reason

    cands = ensure_fresh_list(db, user, now, exclude, cfg, rcfg, gcfg)[: max(need, 0) * 3]
    if not cands or need <= 0:
        return []
    metas = {
        m.track_id: m
        for m in db.scalars(
            select(UserTrackMeta).where(
                UserTrackMeta.user_id == user.id,
                UserTrackMeta.track_id.in_([i.track_id for i in cands]),
                UserTrackMeta.expires_at > now,
            )
        )
    }
    names = _names(
        db, {i.artist_id for i in cands} | {r["seed_id"] for i in cands for r in i.reasons}
    )
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
        out.append({
            "track": it.track_id, "title": meta.title, "artists": meta.artist_names,
            "image": meta.image_url, "source": "suggested",
            "reasons": [_reason(r, names) for r in it.reasons],
        })
        if len(out) >= need:
            break
    db.commit()
    return out
