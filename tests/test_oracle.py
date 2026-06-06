"""Oracle tests — the most important step.

These prove the oracle does the one thing that makes unsupervised building safe:
it rejects the known-bad fixtures, and it refuses to write an invalid table to
disk through the single write path.
"""

from __future__ import annotations

import numpy as np
import pytest

from wtfoundry.core import export
from wtfoundry.core.features import table_features
from wtfoundry.core.validate import check_gates, diversity_report
from wtfoundry.core.write import GateError, write_table

from tests import fixtures


# --------------------------------------------------------------------------
# Golden tables pass every gate.
# --------------------------------------------------------------------------
def test_golden_tables_pass_all_gates():
    for table in (fixtures.golden_sine(), fixtures.golden_saw()):
        result = check_gates(table)
        assert result.passed, result.reasons


# --------------------------------------------------------------------------
# Known-bad tables fail the gate they are designed to fail.
# --------------------------------------------------------------------------
def test_aliased_table_is_rejected():
    result = check_gates(fixtures.bad_aliased(), intended_max_harmonic=64)
    assert not result.passed
    assert result.checks["aliasing"] is False


def test_aliased_table_passes_when_band_is_honest():
    # Same bytes, but declaring the true (full) band: no out-of-band energy.
    result = check_gates(fixtures.bad_aliased(), intended_max_harmonic=512)
    assert result.checks["aliasing"] is True


def test_dc_offset_table_is_rejected():
    result = check_gates(fixtures.bad_dc_offset())
    assert not result.passed
    assert result.checks["dc_offset"] is False


def test_loop_click_table_is_rejected():
    result = check_gates(fixtures.bad_loop_click())
    assert not result.passed
    assert result.checks["loop_continuity"] is False


def test_near_duplicates_are_rejected_by_diversity():
    tables = fixtures.near_duplicate_library()
    vectors = np.array([table_features(t) for t in tables])
    div = diversity_report(vectors)
    assert not div.passed
    assert div.near_duplicate_pairs
    # the duplicate pair is tables 0 and 1
    assert (0, 1) in div.near_duplicate_pairs


def test_distinct_library_has_no_near_duplicates():
    tables = fixtures.near_duplicate_library()[1:]  # drop one of the dup pair
    vectors = np.array([table_features(t) for t in tables])
    div = diversity_report(vectors)
    assert div.near_duplicate_pairs == []


# --------------------------------------------------------------------------
# The single write path refuses to write an invalid table.
# --------------------------------------------------------------------------
def test_invalid_table_cannot_be_written(tmp_path):
    target = tmp_path / "bad.wav"
    with pytest.raises(GateError):
        write_table(fixtures.bad_dc_offset(), target)
    assert not target.exists()  # nothing reached disk


def test_valid_table_is_written_and_round_trips(tmp_path):
    target = tmp_path / "good.wav"
    table = fixtures.golden_saw()
    result = write_table(table, target)
    assert result.path.exists()
    assert result.gate.passed
    back = export.read_wavetable(target)
    assert back.shape == table.shape
    assert np.allclose(back, table.astype(np.float32), atol=1e-6)


def test_write_path_runs_aliasing_gate(tmp_path):
    # Declaring a dishonest band must block the write too.
    target = tmp_path / "alias.wav"
    with pytest.raises(GateError):
        write_table(fixtures.bad_aliased(), target, intended_max_harmonic=64)
    assert not target.exists()
