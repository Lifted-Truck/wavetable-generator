"""Control-surface (lever set) tests.

Exercises the API the way the CLI and the MCP server will: list the palette,
generate through the validated write path, dry-run without writing, and prove
that an invalid table cannot reach disk through the API either.
"""

from __future__ import annotations

import numpy as np
import pytest

from wtfoundry import api, foundry
from wtfoundry.core.write import GateError
from wtfoundry.generators import registry


@pytest.fixture
def out(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "_out_dir", lambda: tmp_path)
    return tmp_path


def test_list_generators_returns_palette():
    palette = foundry.list_generators()
    names = {g["name"] for g in palette}
    assert {"additive", "fm", "wavefold"}.issubset(names)


def test_generate_writes_and_reports(out):
    result = foundry.generate("additive", {"tilt": 1.2}, {"n_frames": 16}, seed=1)
    assert result["passed"]
    assert result["path"].endswith(".wav")
    assert len(list(out.glob("*.wav"))) == 1
    assert "spectral_centroid" in result["features"]
    # validate the freshly written scope
    report = foundry.validate(str(out))
    assert report["n_tables"] == 1
    assert report["tables"][0]["passed"]


def test_dry_run_writes_nothing(out):
    before = list(out.iterdir())
    result = foundry.generate("fm", {"ratio": 3}, {"n_frames": 8}, seed=2, dry_run=True)
    assert result["dry_run"] is True
    assert "intended_path" in result
    assert list(out.iterdir()) == before  # no file created


def test_unknown_generator_raises():
    with pytest.raises(KeyError):
        foundry.generate("does-not-exist")


def test_invalid_table_cannot_be_written_through_api(out, monkeypatch):
    # Force a registered family to emit a DC-offset frame; the API must refuse
    # to write it and leave nothing on disk.
    gen = registry.get("additive")
    monkeypatch.setattr(gen, "finalize", lambda frame: np.asarray(frame) + 0.5)
    with pytest.raises(GateError):
        foundry.generate("additive", {}, {"n_frames": 8}, seed=0)
    assert list(out.iterdir()) == []
