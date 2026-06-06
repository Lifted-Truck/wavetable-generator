"""The single validated write path.

Bytes reach out/ ONLY through ``write_table``. It runs the Layer-1 gates and
refuses to write a failing table, so every generated table is valid no matter
which client pulled the lever, and the check cannot be skipped. The companion
``GateError`` is what the API and CLI surface when a table is rejected — the
test suite proves an invalid table cannot reach disk through either skin.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from wtfoundry.core import export
from wtfoundry.core.validate import GateResult, check_gates


class GateError(RuntimeError):
    """Raised when a table fails a Layer-1 quality gate. Carries the result so
    callers can report exactly which gate(s) failed."""

    def __init__(self, result: GateResult):
        self.result = result
        super().__init__("; ".join(result.reasons) or "table failed quality gates")


@dataclass
class WriteResult:
    path: Path
    gate: GateResult


def write_table(
    table: np.ndarray,
    path: str | Path,
    *,
    intended_max_harmonic: int | None = None,
    presets_path: str | None = None,
    overwrite: bool = True,
) -> WriteResult:
    """Validate ``table`` against the Layer-1 gates and, only if it passes,
    write it to ``path`` as a Serum-compatible wavetable.

    Raises ``GateError`` (and writes nothing) if any gate fails. This is the one
    function permitted to create files under out/.
    """
    table = np.atleast_2d(np.asarray(table, dtype=float))
    result = check_gates(
        table,
        intended_max_harmonic=intended_max_harmonic,
        presets_path=presets_path,
    )
    if not result.passed:
        raise GateError(result)

    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    export.write_wavetable(table, path)
    return WriteResult(path, result)
