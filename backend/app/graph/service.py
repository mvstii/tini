"""Matris önbelleği: son graph_snapshot sürümüne bağlı, süreç içi, tek kurulum.

İstek başına maliyet: bir `max(version)` sorgusu; sürüm değişmedikçe matris yeniden kurulmaz.
"""
import threading

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import GraphSettings
from app.graph.matrix import GraphMatrix, build_matrix
from app.models import ArtistEdge, GraphSnapshot

_lock = threading.Lock()
_cached: tuple[int, GraphMatrix] | None = None


def _refresh(version: int, cfg: GraphSettings) -> None:
    from app.db import get_session_factory

    with get_session_factory()() as db:
        gm = build_matrix(*load_edge_arrays(db, cfg), cfg)
    global _cached
    with _lock:
        if _cached is None or _cached[0] < version:
            _cached = (version, gm)


def clear_cache() -> None:
    global _cached
    with _lock:
        _cached = None


def load_edge_arrays(db: Session, cfg: GraphSettings) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = db.execute(
        select(ArtistEdge.src, ArtistEdge.dst, ArtistEdge.weight).where(
            ArtistEdge.source == cfg.edge_source
        )
    ).all()
    if not rows:
        e = np.empty(0)
        return e, e, e
    src, dst, w = zip(*rows, strict=True)
    return np.array(src), np.array(dst), np.array(w)


def get_matrix(db: Session, cfg: GraphSettings) -> tuple[int, GraphMatrix] | None:
    """(snapshot sürümü, matris) veya henüz snapshot yoksa None."""
    global _cached
    version = db.scalar(select(func.max(GraphSnapshot.version)))
    if version is None:
        return None
    cached = _cached
    if cached is not None and cached[0] == version:
        return cached
    if cached is not None and cfg.swr_enabled:
        from app.jobs.worker import get_worker

        get_worker().submit(("matrix", version), _refresh, version, cfg)
        return cached  # eski sürüm sunulur; yenisi arka planda kurulur, atomik değişir
    with _lock:
        if _cached is not None and _cached[0] == version:
            return _cached
        gm = build_matrix(*load_edge_arrays(db, cfg), cfg)
        _cached = (version, gm)
        return _cached
