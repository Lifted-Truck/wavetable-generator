"""The control surface — the canonical lever set.

This module is the ONE place the tool's operations and parameters are defined.
The CLI, the MCP server, and any future GUI are thin adapters over the functions
below. The rich docstrings on each lever are simultaneously what a human reads,
what the CLI maps flags onto, and what lets Claude map natural language onto
actions — so there is a single source of truth for behavior.

SCAFFOLD STATE: the levers are declared with their final signatures and
docstrings but are not yet implemented. They raise NotImplementedError, which
keeps `python verify.py` red until Run 1 fills them in.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from wtfoundry.core import export
from wtfoundry.core.features import table_features
from wtfoundry.core.validate import check_gates, diversity_report


class Foundry:
    """The lever set. Instantiated once as the module-level ``foundry``."""

    def list_generators(self) -> list[dict[str, Any]]:
        """Return the palette: every registered generator's name, a one-line
        timbral description, and its typed parameter schema."""
        raise NotImplementedError("Run 1, milestone 4: generator registry")

    def generate(
        self,
        generator: str,
        params: dict[str, Any] | None = None,
        morph: dict[str, Any] | None = None,
        *,
        seed: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """The core lever. Synthesize a table with ``generator``, run it through
        the Layer-1 quality gates, write it via the single validated write path,
        and record it in the catalog. Returns file paths, measured features, and
        pass/fail. With ``dry_run=True`` it plans only: intended actions and
        projected output, no write."""
        raise NotImplementedError("Run 1, milestone 7: generate lever")

    def validate(self, target: str) -> dict[str, Any]:
        """Run the oracle on an existing table path or scope and report results.

        ``target`` may be a single ``.wav`` table (Layer-1 gates only) or a
        directory scope (Layer-1 gates per table plus the Layer-2 diversity
        objective across them). Returns a JSON-friendly report with an overall
        ``passed`` flag.
        """
        path = Path(target)
        if path.is_dir():
            wavs = sorted(path.glob("*.wav"))
            tables = []
            vectors = []
            for wav in wavs:
                frames = export.read_wavetable(wav)
                gate = check_gates(frames)
                tables.append(
                    {
                        "path": str(wav),
                        "passed": gate.passed,
                        "checks": gate.checks,
                        "reasons": gate.reasons,
                    }
                )
                vectors.append(table_features(frames))
            div = diversity_report(np.array(vectors)) if vectors else None
            gates_ok = all(t["passed"] for t in tables)
            return {
                "scope": str(path),
                "n_tables": len(tables),
                "tables": tables,
                "diversity": None
                if div is None
                else {
                    "passed": div.passed,
                    "mean_nn_distance": div.mean_nn_distance,
                    "grid_coverage": div.grid_coverage,
                    "near_duplicate_pairs": div.near_duplicate_pairs,
                    "reasons": div.reasons,
                },
                "passed": gates_ok and (div is None or div.passed),
            }

        frames = export.read_wavetable(path)
        gate = check_gates(frames)
        return {
            "path": str(path),
            "passed": gate.passed,
            "checks": gate.checks,
            "measures": gate.measures,
            "reasons": gate.reasons,
        }

    def query_catalog(
        self,
        nearest_to: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Find and compare existing tables — "like this but brighter"."""
        raise NotImplementedError("Run 1, milestone 6: catalog query")

    def coverage(self) -> dict[str, Any]:
        """Report where the library is dense versus sparse across timbre space."""
        raise NotImplementedError("Run 1, milestone 6: coverage")

    def render_spectrogram(self, path: str) -> str:
        """Produce (or return) a spectrogram for the table at ``path``."""
        raise NotImplementedError("Run 1, milestone 6: spectrograms")


foundry = Foundry()
