"""Build-loop tests.

The build must produce a library that (a) covers all six families, (b) passes
every Layer-1 gate, (c) meets the Layer-2 diversity threshold with no
near-duplicates, and (d) is reproducible byte-for-byte from the same config.
"""

from __future__ import annotations

import numpy as np

from wtfoundry import foundry
from wtfoundry.core import export
from wtfoundry.core.build import build_library, candidate_pool, farthest_point_select
from wtfoundry.core.validate import check_gates


def test_candidate_pool_covers_all_families():
    pool = candidate_pool()
    families = {c.generator for c in pool}
    assert len(families) == 6
    for cand in pool:
        assert cand.frames.shape[0] == 64


def test_farthest_point_select_spreads():
    # three tight clusters; FPS should pick one from each before doubling up.
    rng = np.random.default_rng(0)
    clusters = np.array([[0, 0], [10, 0], [0, 10]], dtype=float)
    pts = np.vstack([c + 0.01 * rng.standard_normal((5, 2)) for c in clusters])
    chosen = farthest_point_select(pts, target=3, min_separation=0.5)
    picked = pts[chosen]
    # the three picks should be far apart (one per cluster)
    dists = np.linalg.norm(picked[:, None] - picked[None, :], axis=-1)
    assert dists[np.triu_indices(3, 1)].min() > 5.0


def test_build_produces_diverse_passing_library(tmp_path):
    result = foundry.build(out_dir=str(tmp_path))
    assert result["n_written"] >= 18
    assert result["diversity"]["passed"]
    assert result["diversity"]["near_duplicate_pairs"] == []

    families = {rec["generator"] for rec in result["written"]}
    assert len(families) == 6  # every family represented

    # every written table passes the gates
    for wav in tmp_path.glob("*.wav"):
        frames = export.read_wavetable(wav)
        assert check_gates(frames).passed


def test_build_is_reproducible(tmp_path):
    a = build_library(out_dir=tmp_path / "a")
    b = build_library(out_dir=tmp_path / "b")
    names_a = sorted(p["path"].split("\\")[-1].split("/")[-1] for p in a.written)
    names_b = sorted(p["path"].split("\\")[-1].split("/")[-1] for p in b.written)
    assert names_a == names_b
    # and the bytes match for a sampled table
    first = names_a[0]
    fa = export.read_wavetable(tmp_path / "a" / first)
    fb = export.read_wavetable(tmp_path / "b" / first)
    assert np.array_equal(fa, fb)


def test_build_only_restricts_family(tmp_path):
    result = foundry.build(only="fm", out_dir=str(tmp_path))
    assert {rec["generator"] for rec in result["written"]} == {"fm"}
