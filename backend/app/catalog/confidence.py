from difflib import SequenceMatcher

from app.config import GraphSettings


def name_match_confidence(
    query_norm: str, canonical_norm: str, has_mbid: bool, cfg: GraphSettings
) -> float:
    """Kademe B güveni (saf): sorgu adı ile Last.fm'in kanonik adının benzerliği + MBID bonusu."""
    if not query_norm or not canonical_norm:
        return 0.0
    if query_norm == canonical_norm:
        base = cfg.tier_b_exact_confidence
    else:
        base = SequenceMatcher(None, query_norm, canonical_norm).ratio() * cfg.tier_b_fuzzy_weight
    return min(1.0, base + (cfg.tier_b_mbid_bonus if has_mbid else 0.0))
