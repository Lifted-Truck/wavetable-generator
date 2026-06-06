"""Load tunables from presets.yaml.

Tolerances, ceilings, the format target, and the diversity thresholds live in
presets.yaml so code enforces quality without hard-coding policy. This module
finds and parses that file and supplies the same defaults the YAML documents, so
the oracle behaves correctly even if a key is missing.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "format": {
        "samples_per_frame": 2048,
        "frames_per_table": 256,
        "sample_format": "float32",
        "channels": 1,
        "morph_dims": 1,
    },
    "ceilings": {
        "max_tables": 256,
        "max_batch": 32,
        "max_runtime_seconds": 1800,
    },
    "gates": {
        "aliasing": {"max_harmonic": 1024, "out_of_band_db": -60.0},
        "dc_offset_max": 1.0e-4,
        "loop_continuity": {"value_ratio_max": 3.0, "slope_ratio_max": 8.0},
        "loudness": {"metric": "peak", "target": 0.9, "tolerance_db": 1.0},
        "format_conformance": "strict",
    },
    "diversity": {
        "feature_space": "perceptual",
        "min_mean_nn_distance": 0.0,
        "grid_bins": 8,
        "min_grid_coverage": 0.0,
        "near_duplicate_epsilon": 0.05,
    },
}


def _project_root() -> Path:
    # src/wtfoundry/core/config.py -> repo root is three parents up.
    return Path(__file__).resolve().parents[3]


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, val in (override or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


@functools.lru_cache(maxsize=8)
def load_presets(path: str | None = None) -> dict[str, Any]:
    """Parse presets.yaml (searched at the repo root unless ``path`` is given),
    merged over the documented defaults."""
    if path is None:
        candidate = _project_root() / "presets.yaml"
    else:
        candidate = Path(path)
    loaded: dict[str, Any] = {}
    if candidate.exists():
        loaded = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
    return _deep_merge(DEFAULTS, loaded)


def gates(path: str | None = None) -> dict[str, Any]:
    return load_presets(path)["gates"]


def diversity(path: str | None = None) -> dict[str, Any]:
    return load_presets(path)["diversity"]


def fmt(path: str | None = None) -> dict[str, Any]:
    return load_presets(path)["format"]
