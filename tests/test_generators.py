"""Generator interface + family tests.

Every registered family must (a) render coordinate-first single cycles, (b)
produce a full table that passes the Layer-1 gates by construction, (c) be
seeded-reproducible, and (d) actually move across the morph. Mechanical
distinctness is checked structurally: the three families occupy clearly
different feature regions.
"""

from __future__ import annotations

import numpy as np
import pytest

from wtfoundry.core import synth
from wtfoundry.core.features import table_features
from wtfoundry.core.validate import check_gates
from wtfoundry.generators import registry

FAMILIES = registry.names()


def test_first_three_families_registered():
    assert {"additive", "fm", "wavefold"}.issubset(set(FAMILIES))


def test_schemas_are_well_formed():
    for schema in registry.schemas():
        assert schema["name"]
        assert schema["description"]
        for p in schema["params"]:
            assert {"name", "type", "default", "min", "max", "description"} <= set(p)
            assert p["min"] <= p["default"] <= p["max"]


@pytest.mark.parametrize("name", FAMILIES)
def test_render_is_coordinate_first(name):
    gen = registry.get(name)
    params = gen.resolve(None)
    frame = gen.render(0.5, params)
    assert frame.shape == (synth.SAMPLES_PER_FRAME,)
    assert np.all(np.isfinite(frame))


@pytest.mark.parametrize("name", FAMILIES)
def test_table_passes_all_gates(name):
    gen = registry.get(name)
    table = gen.render_table(n_frames=16, seed=0)
    result = check_gates(table, intended_max_harmonic=gen.intended_max_harmonic(gen.resolve(None)))
    assert result.passed, (name, result.reasons)


@pytest.mark.parametrize("name", FAMILIES)
def test_seeded_reproducibility(name):
    gen = registry.get(name)
    a = gen.render_table(n_frames=8, seed=42)
    b = gen.render_table(n_frames=8, seed=42)
    assert np.array_equal(a, b)


@pytest.mark.parametrize("name", FAMILIES)
def test_morph_actually_moves(name):
    gen = registry.get(name)
    params = gen.resolve(None)
    first = gen.finalize(gen.render(0.0, params))
    last = gen.finalize(gen.render(1.0, params))
    # the endpoints of the morph should be audibly different
    assert np.linalg.norm(first - last) > 1e-3


def test_families_are_mechanically_distinct():
    # Their default tables should land in different feature regions.
    vecs = {n: table_features(registry.get(n).render_table(n_frames=16, seed=0)) for n in FAMILIES}
    names = list(vecs)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            assert np.linalg.norm(vecs[names[i]] - vecs[names[j]]) > 1.0


def test_resolve_clips_out_of_range_and_ignores_unknown():
    gen = registry.get("fm")
    resolved = gen.resolve({"ratio": 999, "bogus": 1.0})
    assert resolved["ratio"] == 8  # clipped to max
    assert "bogus" not in resolved
