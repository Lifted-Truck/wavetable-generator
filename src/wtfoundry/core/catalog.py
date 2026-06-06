"""catalog.json: entries, query, coverage, and 1:1 reconciliation.

Each entry records everything needed to regenerate a table byte-for-byte
(generator, resolved params, seed, frame count) plus its measured perceptual
features, its morph geometry (``morph_dims`` and per-axis resolution, the
multidimensional seam), and the relative paths of its wav and spectrogram. The
catalog must reconcile 1:1 with the wavs on disk — that check is a stage of the
verification command.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from wtfoundry.core import config

CATALOG_NAME = "catalog.json"
CATALOG_VERSION = 1


@dataclass
class CatalogEntry:
    file: str  # wav filename, relative to the catalog directory
    generator: str
    params: dict[str, Any]
    seed: int | None
    n_frames: int
    morph_dims: int
    morph_resolution: list[int]
    intended_max_harmonic: int
    features: dict[str, float]
    spectrogram: str | None = None


@dataclass
class Catalog:
    version: int = CATALOG_VERSION
    format: dict[str, Any] = field(default_factory=dict)
    entries: list[CatalogEntry] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "format": self.format,
            "entries": [asdict(e) for e in self.entries],
        }


def catalog_path(out_dir: str | Path) -> Path:
    return Path(out_dir) / CATALOG_NAME


def write_catalog(entries: list[CatalogEntry], out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    cat = Catalog(format=dict(config.fmt()), entries=entries)
    path = catalog_path(out_dir)
    path.write_text(json.dumps(cat.to_json(), indent=2), encoding="utf-8")
    return path


def upsert_entry(entry: CatalogEntry, out_dir: str | Path) -> Path:
    """Insert or replace the entry for ``entry.file`` and rewrite the catalog,
    so a single ``generate`` keeps the catalog reconciled with disk."""
    out_dir = Path(out_dir)
    existing = load_catalog(out_dir).entries if catalog_path(out_dir).exists() else []
    kept = [e for e in existing if e.file != entry.file]
    return write_catalog([*kept, entry], out_dir)


def load_catalog(out_dir: str | Path) -> Catalog:
    path = catalog_path(out_dir)
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = [CatalogEntry(**e) for e in data.get("entries", [])]
    return Catalog(
        version=data.get("version", CATALOG_VERSION), format=data.get("format", {}), entries=entries
    )


@dataclass
class ReconcileResult:
    ok: bool
    n_entries: int
    n_files: int
    missing_files: list[str]  # in catalog but not on disk
    orphan_files: list[str]  # on disk but not in catalog
    reasons: list[str] = field(default_factory=list)


def reconcile(out_dir: str | Path) -> ReconcileResult:
    """Assert the catalog matches the wavs on disk 1:1."""
    out_dir = Path(out_dir)
    reasons: list[str] = []
    if not catalog_path(out_dir).exists():
        return ReconcileResult(False, 0, 0, [], [], [f"no {CATALOG_NAME} in {out_dir}"])

    cat = load_catalog(out_dir)
    cataloged = {e.file for e in cat.entries}
    on_disk = {p.name for p in out_dir.glob("*.wav")}

    missing = sorted(cataloged - on_disk)
    orphan = sorted(on_disk - cataloged)
    if missing:
        reasons.append(f"{len(missing)} cataloged table(s) missing on disk: {missing[:3]}")
    if orphan:
        reasons.append(f"{len(orphan)} wav(s) on disk not in catalog: {orphan[:3]}")

    ok = not missing and not orphan
    return ReconcileResult(ok, len(cataloged), len(on_disk), missing, orphan, reasons)


# --------------------------------------------------------------------------
# Query + coverage (the levers).
# --------------------------------------------------------------------------
def _feature_matrix(cat: Catalog) -> tuple[np.ndarray, list[str]]:
    from wtfoundry.core.features import FEATURE_NAMES

    mat = np.array([[e.features.get(n, 0.0) for n in FEATURE_NAMES] for e in cat.entries])
    return mat, FEATURE_NAMES


def query(
    cat: Catalog,
    nearest_to: str | None = None,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Filter and/or rank entries. ``filters`` may pin ``generator`` or give
    ``{feature: [lo, hi]}`` ranges; ``nearest_to`` (a table filename) ranks the
    survivors by perceptual distance to that table."""
    filters = filters or {}
    entries = list(cat.entries)

    if "generator" in filters:
        entries = [e for e in entries if e.generator == filters["generator"]]
    for key, val in filters.items():
        if key == "generator":
            continue
        if isinstance(val, (list, tuple)) and len(val) == 2:
            lo, hi = val
            entries = [e for e in entries if lo <= e.features.get(key, float("nan")) <= hi]

    results = [{"file": e.file, "generator": e.generator, "features": e.features} for e in entries]

    if nearest_to:
        from wtfoundry.core.validate import _standardize

        full_mat, _ = _feature_matrix(cat)
        z = _standardize(full_mat)
        index = {e.file: i for i, e in enumerate(cat.entries)}
        if nearest_to not in index:
            raise KeyError(f"unknown table: {nearest_to!r}")
        anchor = z[index[nearest_to]]
        keep_idx = [index[r["file"]] for r in results]
        dists = np.linalg.norm(z[keep_idx] - anchor, axis=1)
        order = np.argsort(dists)
        results = [
            {**results[o], "distance": float(dists[o])}
            for o in order
            if results[o]["file"] != nearest_to
        ]

    return results


def coverage(cat: Catalog) -> dict[str, Any]:
    """Where the library is dense vs sparse across timbre space."""
    from wtfoundry.core.validate import _grid_coverage, _standardize, diversity_report

    if not cat.entries:
        return {"n_tables": 0}

    mat, names = _feature_matrix(cat)
    by_family: dict[str, int] = {}
    for e in cat.entries:
        by_family[e.generator] = by_family.get(e.generator, 0) + 1

    div = diversity_report(mat)
    z = _standardize(mat)
    bins = int(config.diversity()["grid_bins"])

    ranges = {
        name: [float(mat[:, i].min()), float(mat[:, i].max())] for i, name in enumerate(names)
    }
    return {
        "n_tables": len(cat.entries),
        "by_family": by_family,
        "mean_nn_distance": div.mean_nn_distance,
        "grid_coverage": _grid_coverage(z, bins),
        "near_duplicate_pairs": div.near_duplicate_pairs,
        "feature_ranges": ranges,
    }
