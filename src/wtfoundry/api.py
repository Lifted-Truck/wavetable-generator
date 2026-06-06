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

from typing import Any


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
        """Run the oracle (Layer-1 gates and the Layer-2 diversity objective) on
        an existing table path or scope and report the results."""
        raise NotImplementedError("Run 1, milestone 3: oracle")

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
