"""Catalog, spectrogram, reconciliation, and query/coverage lever tests."""

from __future__ import annotations

import numpy as np
import pytest

from wtfoundry import foundry
from wtfoundry.core import catalog as catalog_mod
from wtfoundry.core import export

from tests import fixtures


@pytest.fixture(scope="module")
def library(tmp_path_factory):
    out = tmp_path_factory.mktemp("library")
    summary = foundry.build(out_dir=str(out))
    return out, summary


def test_build_writes_catalog_and_spectrograms(library):
    out, summary = library
    assert catalog_mod.catalog_path(out).exists()
    cat = catalog_mod.load_catalog(out)
    assert len(cat.entries) == summary["n_written"]
    assert len(cat.entries) == len(list(out.glob("*.wav")))
    for entry in cat.entries:
        assert entry.features  # measured features present
        assert entry.morph_dims == 1
        assert entry.morph_resolution == [entry.n_frames]
        assert entry.spectrogram and (out / entry.spectrogram).exists()


def test_reconcile_ok_after_build(library):
    out, _ = library
    assert catalog_mod.reconcile(out).ok


def test_reconcile_detects_orphan_file(library, tmp_path):
    # copy the catalog scope is awkward; instead add a stray wav to a fresh build
    out = tmp_path / "lib"
    foundry.build(only="fm", out_dir=str(out))
    assert catalog_mod.reconcile(out).ok
    export.write_wavetable(fixtures.golden_sine(), out / "stray__deadbeef00.wav")
    result = catalog_mod.reconcile(out)
    assert not result.ok
    assert "stray__deadbeef00.wav" in result.orphan_files


def test_reconcile_detects_missing_file(library, tmp_path):
    out = tmp_path / "lib2"
    foundry.build(only="fm", out_dir=str(out))
    # delete a wav that the catalog still references
    victim = next(out.glob("*.wav"))
    victim.unlink()
    result = catalog_mod.reconcile(out)
    assert not result.ok
    assert victim.name in result.missing_files


def test_query_generator_filter(library):
    out, _ = library
    results = foundry.query_catalog(filters={"generator": "fm"}, scope=str(out))
    assert results
    assert all(r["generator"] == "fm" for r in results)


def test_query_nearest_to_ranks_by_distance(library):
    out, _ = library
    cat = catalog_mod.load_catalog(out)
    anchor = cat.entries[0].file
    results = foundry.query_catalog(nearest_to=anchor, scope=str(out))
    assert anchor not in [r["file"] for r in results]  # anchor excluded
    dists = [r["distance"] for r in results]
    assert dists == sorted(dists)  # ascending distance


def test_coverage_reports_all_families(library):
    out, _ = library
    cov = foundry.coverage(scope=str(out))
    assert cov["n_tables"] == len(list(out.glob("*.wav")))
    assert len(cov["by_family"]) == 6
    assert cov["mean_nn_distance"] > 0


def test_render_spectrogram_lever(library, tmp_path):
    out, _ = library
    wav = next(out.glob("*.wav"))
    png = foundry.render_spectrogram(str(wav))
    assert png.endswith(".png")
    from pathlib import Path

    assert Path(png).exists()


def test_catalog_records_are_reproducible(library, tmp_path):
    out, _ = library
    cat1 = catalog_mod.load_catalog(out)
    out2 = tmp_path / "again"
    foundry.build(out_dir=str(out2))
    cat2 = catalog_mod.load_catalog(out2)
    files1 = sorted(e.file for e in cat1.entries)
    files2 = sorted(e.file for e in cat2.entries)
    assert files1 == files2
    # features for a shared table match
    f1 = {e.file: e.features for e in cat1.entries}
    f2 = {e.file: e.features for e in cat2.entries}
    shared = files1[0]
    assert np.allclose(list(f1[shared].values()), list(f2[shared].values()), atol=1e-9)
