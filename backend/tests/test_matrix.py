import numpy as np
import pytest

from app.config import GraphSettings
from app.graph.matrix import build_matrix
from app.graph.neighborhood import neighborhood

RAW = GraphSettings(matrix_normalization="none")


def arr(*edges):
    s, d, w = zip(*edges, strict=True)
    return np.array(s), np.array(d), np.array(w)


def dense(gm):
    return gm.matrix.toarray()


def test_symmetrize_max_and_mean():
    e = arr((1, 2, 0.8), (2, 1, 0.4), (2, 3, 0.6))
    mx = dense(build_matrix(*e, GraphSettings(matrix_normalization="none")))
    assert mx[0, 1] == pytest.approx(0.8) and mx[1, 0] == pytest.approx(0.8)
    assert mx[1, 2] == pytest.approx(0.6) and mx[2, 1] == pytest.approx(0.6)
    mean = dense(
        build_matrix(*e, GraphSettings(matrix_normalization="none", matrix_symmetrize="mean"))
    )
    assert mean[0, 1] == pytest.approx(0.6)  # (0.8 + 0.4) / 2
    assert mean[1, 2] == pytest.approx(0.3)  # yalnızca tek yön var: (0.6 + 0) / 2


def test_sym_normalization_is_symmetric_with_expected_values():
    gm = build_matrix(*arr((1, 2, 0.5), (2, 3, 0.5)), GraphSettings())
    m = dense(gm)
    assert np.allclose(m, m.T)
    # derece: d1=0.5, d2=1.0, d3=0.5 → m12 = 0.5 / sqrt(0.5 * 1.0)
    assert m[0, 1] == pytest.approx(0.5 / np.sqrt(0.5), rel=1e-5)


def test_row_normalization_rows_sum_to_one():
    cfg = GraphSettings(matrix_normalization="row")
    m = dense(build_matrix(*arr((1, 2, 0.3), (1, 3, 0.9), (3, 4, 0.2)), cfg))
    assert np.allclose(m.sum(axis=1), 1.0)


def test_duplicates_keep_max_and_self_loops_and_threshold_dropped():
    cfg = GraphSettings(matrix_normalization="none", edge_min_weight=0.2)
    e = arr((1, 2, 0.3), (1, 2, 0.7), (2, 2, 1.0), (1, 3, 0.1), (4, 5, 0.0))
    gm = build_matrix(*e, cfg)
    assert list(gm.node_ids) == [1, 2]
    assert dense(gm)[0, 1] == pytest.approx(0.7)


def test_empty_input():
    gm = build_matrix(*arr((1, 1, 1.0)), RAW)
    assert gm.matrix.shape == (0, 0) and gm.node_ids.size == 0
    assert gm.position(1) is None


def test_build_is_deterministic_regardless_of_edge_order():
    edges = [(1, 2, 0.9), (1, 3, 0.5), (2, 4, 0.8), (3, 4, 0.4), (3, 5, 1.0), (5, 1, 0.2)]
    a = build_matrix(*arr(*edges), GraphSettings())
    b = build_matrix(*arr(*reversed(edges)), GraphSettings())
    assert np.array_equal(a.node_ids, b.node_ids)
    assert (a.matrix != b.matrix).nnz == 0


def test_invalid_modes_raise():
    with pytest.raises(ValueError):
        build_matrix(*arr((1, 2, 0.5)), GraphSettings(matrix_symmetrize="x"))
    with pytest.raises(ValueError):
        build_matrix(*arr((1, 2, 0.5)), GraphSettings(matrix_normalization="x"))


# --- komşuluk ---

EDGES = [(1, 2, 0.9), (1, 3, 0.5), (2, 4, 0.8), (3, 4, 0.4), (3, 5, 1.0), (2, 6, 0.1)]


def hood(depth=2, **cfg):
    gm = build_matrix(*arr(*EDGES), GraphSettings(matrix_normalization="none", **cfg))
    return neighborhood(gm, 1, depth, GraphSettings(matrix_normalization="none", **cfg))


def test_neighborhood_depth1_sorted_by_weight():
    h = hood(depth=1)
    assert [(n.artist_id, round(n.score, 3)) for n in h.depth1] == [(2, 0.9), (3, 0.5)]
    assert h.depth2 == []


def test_neighborhood_depth2_path_products_and_via():
    h = hood()
    got = [(n.artist_id, round(n.score, 3), n.via) for n in h.depth2]
    # 4: 0.9*0.8 + 0.5*0.4 = 0.92 (via 2); 5: 0.5*1.0 (via 3); 6: 0.9*0.1 (via 2)
    assert got == [(4, 0.92, 2), (5, 0.5, 3), (6, 0.09, 2)]


def test_neighborhood_excludes_anchor_and_depth1_from_depth2():
    ids = {n.artist_id for n in hood().depth2}
    assert not ids & {1, 2, 3}


def test_neighborhood_fanout_limits_expansion():
    h = hood(neighborhood_fanout=1)  # yalnızca en güçlü komşu (2) genişler
    assert {n.artist_id for n in h.depth2} == {4, 6}


def test_neighborhood_top_k_and_depth_clamp():
    h = hood(neighborhood_top_k=1)
    assert len(h.depth1) == 1 and len(h.depth2) == 1
    assert hood(depth=9, neighborhood_max_depth=1).depth2 == []


def test_neighborhood_unknown_anchor_is_none():
    gm = build_matrix(*arr(*EDGES), RAW)
    assert neighborhood(gm, 99, 2, RAW) is None
