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

from wtfoundry.core import catalog as catalog_mod
from wtfoundry.core import config, export, spectro
from wtfoundry.core.build import Candidate, build_library, table_slug
from wtfoundry.core.catalog import CatalogEntry
from wtfoundry.core.features import features_dict, table_features
from wtfoundry.core.validate import check_gates, diversity_report
from wtfoundry.core.write import write_table
from wtfoundry.generators import registry


def _out_dir() -> Path:
    return config._project_root() / "out"


def _make_entry(
    *,
    generator: str,
    params: dict[str, Any],
    seed: int | None,
    n_frames: int,
    intended_max_harmonic: int,
    frames: np.ndarray,
    path: Path,
    spectrogram: bool = True,
) -> CatalogEntry:
    """Build a catalog entry for a written table, rendering its spectrogram."""
    png = spectro.render_spectrogram(path).name if spectrogram else None
    return CatalogEntry(
        file=path.name,
        generator=generator,
        params=params,
        seed=seed,
        n_frames=n_frames,
        morph_dims=int(config.fmt()["morph_dims"]),
        morph_resolution=[n_frames],
        intended_max_harmonic=intended_max_harmonic,
        features=features_dict(frames),
        spectrogram=png,
    )


class Foundry:
    """The lever set. Instantiated once as the module-level ``foundry``."""

    def list_generators(self) -> list[dict[str, Any]]:
        """Return the palette: every registered generator's name, a one-line
        timbral description, and its typed parameter schema."""
        return registry.schemas()

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
        gen = registry.get(generator)
        resolved = gen.resolve(params)
        morph = morph or {}
        n_frames = int(morph.get("n_frames", config.fmt()["frames_per_table"]))
        slug = table_slug(generator, resolved, seed, n_frames)
        path = _out_dir() / f"{slug}.wav"

        if dry_run:
            return {
                "dry_run": True,
                "generator": generator,
                "params": resolved,
                "seed": seed,
                "n_frames": n_frames,
                "intended_path": str(path),
                "intended_max_harmonic": gen.intended_max_harmonic(resolved),
            }

        imh = gen.intended_max_harmonic(resolved)
        frames = gen.render_table(resolved, n_frames=n_frames, seed=seed)
        result = write_table(frames, path, intended_max_harmonic=imh)
        entry = _make_entry(
            generator=generator,
            params=resolved,
            seed=seed,
            n_frames=n_frames,
            intended_max_harmonic=imh,
            frames=frames,
            path=result.path,
        )
        catalog_mod.upsert_entry(entry, result.path.parent)
        return {
            "generator": generator,
            "params": resolved,
            "seed": seed,
            "n_frames": n_frames,
            "path": str(result.path),
            "passed": result.gate.passed,
            "checks": result.gate.checks,
            "features": entry.features,
            "spectrogram": entry.spectrogram,
        }

    def build(
        self,
        only: str | None = None,
        *,
        presets_path: str | None = None,
        out_dir: str | None = None,
        progress: Any = None,
    ) -> dict[str, Any]:
        """Assemble the diverse library: render the candidate pool from every
        family's sweep, select a maximally-spread subset, and write each table
        through the single validated write path. ``only`` restricts to one family
        for fast iteration. Returns what was written and the diversity report."""
        target_dir = Path(out_dir) if out_dir else _out_dir()
        entries: list[CatalogEntry] = []

        def writer(cand: Candidate, path: Path) -> dict[str, Any]:
            result = write_table(
                cand.frames, path, intended_max_harmonic=cand.intended_max_harmonic
            )
            entries.append(
                _make_entry(
                    generator=cand.generator,
                    params=cand.params,
                    seed=cand.seed,
                    n_frames=cand.n_frames,
                    intended_max_harmonic=cand.intended_max_harmonic,
                    frames=cand.frames,
                    path=result.path,
                )
            )
            return {
                "generator": cand.generator,
                "params": cand.params,
                "seed": cand.seed,
                "n_frames": cand.n_frames,
                "path": str(result.path),
                "passed": result.gate.passed,
            }

        result = build_library(
            only=only,
            presets_path=presets_path,
            out_dir=target_dir,
            progress=progress,
            writer=writer,
        )
        catalog_path = catalog_mod.write_catalog(entries, target_dir)
        return {
            "n_written": len(result.written),
            "pool_size": result.pool_size,
            "written": result.written,
            "diversity": result.diversity,
            "catalog": str(catalog_path),
        }

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
        *,
        scope: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find and compare existing tables — "like this but brighter".

        ``filters`` may pin a ``generator`` or give ``{feature: [lo, hi]}``
        ranges; ``nearest_to`` (a table filename) ranks survivors by perceptual
        distance to that table. Reads the catalog in ``scope`` (default out/)."""
        cat = catalog_mod.load_catalog(Path(scope) if scope else _out_dir())
        return catalog_mod.query(cat, nearest_to=nearest_to, filters=filters)

    def coverage(self, *, scope: str | None = None) -> dict[str, Any]:
        """Report where the library is dense versus sparse across timbre space."""
        cat = catalog_mod.load_catalog(Path(scope) if scope else _out_dir())
        return catalog_mod.coverage(cat)

    def render_spectrogram(self, path: str) -> str:
        """Produce (or return) a spectrogram for the table at ``path``."""
        return str(spectro.render_spectrogram(path))

    def reconcile(self, scope: str | None = None) -> dict[str, Any]:
        """Assert the catalog in ``scope`` (default out/) matches the wavs on
        disk 1:1. A stage of the verification command."""
        result = catalog_mod.reconcile(Path(scope) if scope else _out_dir())
        return {
            "ok": result.ok,
            "n_entries": result.n_entries,
            "n_files": result.n_files,
            "missing_files": result.missing_files,
            "orphan_files": result.orphan_files,
            "reasons": result.reasons,
        }


foundry = Foundry()
