"""/recommend/candidates (ham PPR adayları) ve /lists (kalıcı MMR listesi).

Yanıtlardaki adlar yalnızca paylaşılan katalogdaki sanatçı adlarıdır.
"""
from datetime import UTC, datetime
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.artist_images import cached_images
from app.config import (
    GraphSettings,
    ProfileSettings,
    RecommendSettings,
    get_graph_settings,
    get_profile_settings,
    get_recommend_settings,
)
from app.connect import get_http
from app.connections import valid_access_value
from app.deps import current_user, get_db
from app.library import ADAPTERS
from app.models import (
    Artist,
    GeneratedList,
    ListFeedback,
    ListItem,
    Release,
    ServiceConnection,
    Track,
    User,
    UserTrackMeta,
    VoteEvent,
)
from app.recommend.daily import pick_daily
from app.recommend.service import (
    NoGraph,
    NoProfile,
    NoReleases,
    compute_candidates,
    generate_fresh,
    generate_list,
)

router = APIRouter(prefix="/recommend")
lists_router = APIRouter(prefix="/lists")


def _names(db: Session, ids: set[int]) -> dict[int, str]:
    return dict(db.execute(select(Artist.id, Artist.name).where(Artist.id.in_(ids))).all())


def _reason(r: dict, names: dict) -> dict:
    return {
        "seed_id": r["seed_id"],
        "seed_name": names.get(r["seed_id"]),
        "share": round(r["share"], 4),
        "is_anchor": r["is_anchor"],
    }


@router.get("/candidates")
def candidates(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: RecommendSettings = Depends(get_recommend_settings),
    pcfg: ProfileSettings = Depends(get_profile_settings),
    gcfg: GraphSettings = Depends(get_graph_settings),
) -> dict:
    try:
        sc = compute_candidates(db, user.id, datetime.now(UTC), cfg, pcfg, gcfg)
    except NoProfile:
        raise HTTPException(404, "Henüz profil üretilmedi") from None
    except NoGraph:
        raise HTTPException(409, "Grafik henüz kurulmadı") from None
    cands = sc.cands
    names = _names(db, {c.artist_id for c in cands} | {r.seed_id for c in cands for r in c.reasons})
    return {
        "algo_version": cfg.recommend_algo_version,
        "profile_version": sc.profile.version,
        "profile_graph_version": sc.profile.graph_version,
        "graph_version": sc.graph_version,
        "candidates": [
            {
                "artist_id": c.artist_id,
                "name": names.get(c.artist_id),
                "score": round(c.score, 6),
                "raw": round(c.raw, 6),
                "novelty": round(c.novelty, 4),
                "penalty": round(c.penalty, 6),
                "reasons": [
                    _reason(
                        {"seed_id": r.seed_id, "share": r.share, "is_anchor": r.is_anchor}, names
                    )
                    for r in c.reasons
                ],
            }
            for c in cands
        ],
    }


def _release_out(r: Release | None) -> dict | None:
    if r is None:
        return None
    return {"id": r.id, "title": r.title, "type": r.primary_type,
            "released": r.first_release_date.isoformat()}


def _list_out(db: Session, lst: GeneratedList) -> dict:
    items = db.scalars(
        select(ListItem).where(ListItem.list_id == lst.id).order_by(ListItem.position)
    ).all()
    ids = {i.artist_id for i in items} | {r["seed_id"] for i in items for r in i.reasons}
    names = _names(db, ids)
    metas = {
        m.track_id: m
        for m in db.scalars(
            select(UserTrackMeta).where(
                UserTrackMeta.user_id == lst.user_id,
                UserTrackMeta.track_id.in_([i.track_id for i in items if i.track_id]),
            )
        )
    }
    releases = {
        r.id: r
        for r in db.scalars(
            select(Release).where(Release.id.in_([i.release_id for i in items if i.release_id]))
        )
    }
    photos = cached_images(db, {i.artist_id for i in items}, datetime.now(UTC))
    return {
        "id": lst.id,
        "kind": lst.kind,
        "created_at": lst.created_at.isoformat(),
        "algo_version": lst.algo_version,
        "candidate_algo_version": lst.candidate_algo_version,
        "profile_version": lst.profile_version,
        "graph_version": lst.graph_version,
        "params": lst.params,
        "items": [
            {
                "position": i.position,
                "artist_id": i.artist_id,
                "name": names.get(i.artist_id),
                "artist_image": photos.get(i.artist_id),
                "slot": i.slot,
                "track_id": i.track_id,
                "title": metas[i.track_id].title if i.track_id in metas else None,
                "release": _release_out(releases.get(i.release_id)),
                "score": round(i.score, 6),
                "reasons": [_reason(r, names) for r in i.reasons],
            }
            for i in items
        ],
    }


@router.get("/daily")
def daily(
    service: str = "spotify",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    http: httpx.Client = Depends(get_http),
    cfg: RecommendSettings = Depends(get_recommend_settings),
    pcfg: ProfileSettings = Depends(get_profile_settings),
    gcfg: GraphSettings = Depends(get_graph_settings),
) -> dict:
    """Günün şarkısı: son ana listeden (yoksa üretilir) gün ve kullanıcıya göre seçilen öğe.
    Gerekçe listeden gelir. Başlık/kapak servisten isteğe bağlı çözülür ve saklanmaz; servis
    bağlı değilse ya da yanıt vermezse yalnızca sanatçı adı ve gerekçe döner."""
    lst = db.scalar(
        select(GeneratedList)
        .where(GeneratedList.user_id == user.id, GeneratedList.kind == "main")
        .order_by(GeneratedList.id.desc())
        .limit(1)
    )
    voted = set(db.scalars(select(VoteEvent.track_id).where(VoteEvent.user_id == user.id)))
    day = datetime.now(UTC).date()

    def _pick(source: GeneratedList) -> tuple[list[ListItem], int | None]:
        its = db.scalars(select(ListItem).where(ListItem.list_id == source.id)).all()
        return its, pick_daily(
            [(i.position, i.track_id) for i in its], day, str(user.id), voted,
            cfg.daily_algo_version,
        )

    def _generate() -> GeneratedList:
        try:
            return generate_list(db, user.id, datetime.now(UTC), cfg, pcfg, gcfg)
        except NoProfile:
            raise HTTPException(404, "Henüz profil üretilmedi") from None
        except NoGraph:
            raise HTTPException(409, "Grafik henüz kurulmadı") from None

    if lst is None:
        lst = _generate()
    items, pos = _pick(lst)
    if pos is None:
        # Liste oylandıkça tükenir (oylanan parçalar elenir); yeni liste oylanan sanatçıları dışlar.
        lst = _generate()
        items, pos = _pick(lst)
    if pos is None:
        raise HTTPException(404, "Önerilecek şarkı kalmadı")
    item = next(i for i in items if i.position == pos)
    ids = {item.artist_id} | {r["seed_id"] for r in item.reasons}
    names = _names(db, ids)
    out = {
        "algo_version": cfg.daily_algo_version,
        "date": day.isoformat(),
        "list_id": lst.id,
        "position": item.position,
        "track": item.track_id,
        "artist_id": item.artist_id,
        "artist_image": cached_images(db, [item.artist_id], datetime.now(UTC)).get(item.artist_id),
        "name": names.get(item.artist_id),
        "title": None,
        "artists": None,
        "image": None,
        "reasons": [_reason(r, names) for r in item.reasons],
    }
    try:
        adapter = _service_adapter(db, user, service, http)
        isrc = None
        if item.track_id:
            isrc = db.scalar(select(Track.isrc).where(Track.id == item.track_id))
        card = adapter.find_card(isrc, names.get(item.artist_id) or "")
    except (HTTPException, httpx.HTTPError):
        card = None
    if card is not None:
        out.update(title=card.title, artists=list(card.artist_names), image=card.image_url)
    return out


@lists_router.post("/generate", status_code=201)
def generate(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: RecommendSettings = Depends(get_recommend_settings),
    pcfg: ProfileSettings = Depends(get_profile_settings),
    gcfg: GraphSettings = Depends(get_graph_settings),
) -> dict:
    # "Yeniden üret" sayacı: önceki ana liste sayısı, tazelik tohumuna girer (list-6)
    nonce = db.scalar(
        select(func.count()).select_from(GeneratedList).where(
            GeneratedList.user_id == user.id, GeneratedList.kind == "main"
        )
    ) or 0
    try:
        lst = generate_list(db, user.id, datetime.now(UTC), cfg, pcfg, gcfg, nonce)
    except NoProfile:
        raise HTTPException(404, "Henüz profil üretilmedi") from None
    except NoGraph:
        raise HTTPException(409, "Grafik henüz kurulmadı") from None
    return _list_out(db, lst)


@lists_router.post("/generate-fresh", status_code=201)
def generate_fresh_list(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: RecommendSettings = Depends(get_recommend_settings),
    gcfg: GraphSettings = Depends(get_graph_settings),
) -> dict:
    try:
        lst = generate_fresh(db, user.id, datetime.now(UTC), cfg, gcfg)
    except NoProfile:
        raise HTTPException(404, "Henüz profil üretilmedi") from None
    except NoGraph:
        raise HTTPException(409, "Grafik henüz kurulmadı") from None
    except NoReleases:
        raise HTTPException(409, "Takip ettiklerinde yeni yayın yok") from None
    return _list_out(db, lst)


@lists_router.get("/{list_id}")
def get_list(
    list_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    lst = db.scalar(
        select(GeneratedList).where(GeneratedList.id == list_id, GeneratedList.user_id == user.id)
    )
    if lst is None:
        raise HTTPException(404, "Liste yok")
    return _list_out(db, lst)


class FeedbackIn(BaseModel):
    kind: Literal["wrong_reason"] = "wrong_reason"
    seed_id: int | None = None


@lists_router.post("/{list_id}/items/{position}/feedback", status_code=201)
def item_feedback(
    list_id: int, position: int, body: FeedbackIn,
    user: User = Depends(current_user), db: Session = Depends(get_db),
) -> dict:
    """Gerekçe itirazı: yalnızca olay kaydı (algoritmaya etkisi Faz 5)."""
    item = db.scalar(
        select(ListItem)
        .join(GeneratedList, GeneratedList.id == ListItem.list_id)
        .where(
            ListItem.list_id == list_id, ListItem.position == position,
            GeneratedList.user_id == user.id,
        )
    )
    if item is None:
        raise HTTPException(404, "Liste öğesi yok")
    if body.seed_id is not None and body.seed_id not in {r["seed_id"] for r in item.reasons}:
        raise HTTPException(422, "Bu çapa öğenin gerekçesinde yok")
    ev = ListFeedback(
        user_id=user.id, list_id=list_id, position=position, seed_id=body.seed_id, kind=body.kind
    )
    db.add(ev)
    db.commit()
    return {"id": ev.id, "list": list_id, "position": position, "seed_id": ev.seed_id,
            "kind": ev.kind}


def _service_adapter(db: Session, user: User, service: str, http: httpx.Client):
    adapter_cls = ADAPTERS.get(service)
    if adapter_cls is None:
        raise HTTPException(400, "Bilinmeyen servis")
    conn = db.scalars(
        select(ServiceConnection).where(
            ServiceConnection.user_id == user.id, ServiceConnection.service == service
        )
    ).first()
    if conn is None:
        raise HTTPException(409, "Servis bağlı değil")
    try:
        return adapter_cls(http, valid_access_value(db, conn, http))
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e


def _owned_item(db: Session, user: User, list_id: int, position: int) -> ListItem:
    item = db.scalar(
        select(ListItem)
        .join(GeneratedList, GeneratedList.id == ListItem.list_id)
        .where(
            ListItem.list_id == list_id, ListItem.position == position,
            GeneratedList.user_id == user.id,
        )
    )
    if item is None:
        raise HTTPException(404, "Liste öğesi yok")
    return item


@lists_router.get("/{list_id}/items/{position}/open")
def item_open(
    list_id: int, position: int, service: str = "spotify",
    user: User = Depends(current_user), db: Session = Depends(get_db),
    http: httpx.Client = Depends(get_http),
) -> dict:
    """Öğeyi servis uygulamasında açan bağlantı. Parça ISRC'den çözülür (tıklama anında, saklanmaz);
    çözülemezse sanatçı araması bağlantısı döner."""
    item = _owned_item(db, user, list_id, position)
    adapter = _service_adapter(db, user, service, http)
    name = db.scalar(select(Artist.name).where(Artist.id == item.artist_id)) or ""
    isrc = db.scalar(select(Track.isrc).where(Track.id == item.track_id)) if item.track_id else None
    # Arama ipucu: albüm öğesinde albüm adı, parça öğesinde (kullanıcı önbelleğindeki) parça adı.
    hint = None
    if item.release_id:
        hint = db.scalar(select(Release.title).where(Release.id == item.release_id))
    elif item.track_id:
        hint = db.scalar(
            select(UserTrackMeta.title).where(
                UserTrackMeta.user_id == user.id, UserTrackMeta.track_id == item.track_id
            )
        )
    try:
        kind, url = adapter.open_url(isrc, name, hint)
    except httpx.HTTPError:
        kind, url = adapter.open_url(None, name, hint)
    return {"kind": kind, "url": url}


@lists_router.post("/{list_id}/export/{service}", status_code=201)
def export_list(
    list_id: int, service: str,
    user: User = Depends(current_user), db: Session = Depends(get_db),
    http: httpx.Client = Depends(get_http),
) -> dict:
    """Listeyi kullanıcının servisinde özel çalma listesi olarak yazar.

    Parçası olmayan veya çözülemeyen öğeler atlanır ve konumlarıyla raporlanır."""
    lst = db.scalar(
        select(GeneratedList).where(GeneratedList.id == list_id, GeneratedList.user_id == user.id)
    )
    if lst is None:
        raise HTTPException(404, "Liste yok")
    adapter = _service_adapter(db, user, service, http)
    items = db.scalars(
        select(ListItem).where(ListItem.list_id == list_id).order_by(ListItem.position)
    ).all()
    isrcs = dict(db.execute(
        select(Track.id, Track.isrc).where(Track.id.in_([i.track_id for i in items if i.track_id]))
    ).all())
    names = dict(db.execute(
        select(Artist.id, Artist.name).where(Artist.id.in_([i.artist_id for i in items]))
    ).all())
    ids: list[str] = []
    skipped: list[int] = []
    skipped_names: list[str] = []
    try:
        for i in items:
            tid = adapter.find_track(isrcs[i.track_id]) if i.track_id in isrcs else None
            if not tid:
                tid = adapter.find_artist_track(names.get(i.artist_id, ""))
            if tid and tid not in ids:
                ids.append(tid)
            else:
                skipped.append(i.position)
                skipped_names.append(names.get(i.artist_id, ""))
        if not ids:
            return {"playlist_id": None, "added": 0, "skipped": skipped,
                    "skipped_names": skipped_names}
        playlist_id = adapter.create_playlist(f"Tını keşif {lst.created_at:%Y-%m-%d}", ids)
    except httpx.HTTPStatusError as e:
        code = 409 if e.response.status_code in (401, 403) else 502
        raise HTTPException(code, "Servis çalma listesini yazamadı") from e
    except httpx.HTTPError as e:
        raise HTTPException(502, "Servise ulaşılamadı") from e
    return {"playlist_id": playlist_id, "added": len(ids), "skipped": skipped,
            "skipped_names": skipped_names}
