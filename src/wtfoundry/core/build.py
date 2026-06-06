"""The coverage-driven diversity build loop.

The build assembles a *candidate pool* from every family's parameter sweep (and,
for stochastic families, a few seeds), renders each candidate, and keeps only
gate-passing tables. It then selects a maximally-spread subset by farthest-point
sampling in standardized perceptual feature space, pruning near-duplicates, so
the shipped library covers timbre space rather than clustering. The selected
tables are written through the single validated write path.

This is the mechanism the spec calls for: generate a batch, extract features,
prefer under-populated regions, and stop when the spread target is met with
every table passing the gates and no near-duplicates.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from wtfoundry.core import config
from wtfoundry.core.features import table_features
from wtfoundry.core.validate import _standardize, check_gates, diversity_report
from wtfoundry.generators import registry


@dataclass
class Candidate:
    generator: str
    params: dict[str, Any]
    seed: int
    n_frames: int
    frames: np.ndarray = field(repr=False)
    features: np.ndarray = field(repr=False)
    intended_max_harmonic: int


def table_slug(generator: str, params: dict[str, Any], seed: int | None, n_frames: int) -> str:
    """Deterministic filename stem from the full recipe — stable across runs so
    tables regenerate byte-for-byte and the catalog reconciles."""
    payload = json.dumps({"g": generator, "p": params, "s": seed, "n": n_frames}, sort_keys=True)
    return f"{generator}__{hashlib.sha1(payload.encode()).hexdigest()[:10]}"


def _variations(name: str, presets_path: str | None) -> list[dict[str, Any]]:
    entry = config.generators_cfg(presets_path).get(name) or {}
    variations = entry.get("variations") if isinstance(entry, dict) else None
    return variations or [{}]  # fall back to schema defaults


def candidate_pool(
    only: str | None = None,
    presets_path: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[Candidate]:
    """Render every (family, variation, seed) into a gate-passing candidate."""
    bcfg = config.build_cfg(presets_path)
    n_frames = int(bcfg["frames_per_table"])
    seeds = list(bcfg["seeds"]) or [0]
    names = [only] if only else registry.names()

    pool: list[Candidate] = []
    for name in names:
        gen = registry.get(name)
        gen_seeds = seeds if gen.stochastic else seeds[:1]
        for variation in _variations(name, presets_path):
            resolved = gen.resolve(variation)
            imh = gen.intended_max_harmonic(resolved)
            for seed in gen_seeds:
                frames = gen.render_table(resolved, n_frames=n_frames, seed=seed)
                gate = check_gates(frames, intended_max_harmonic=imh)
                if not gate.passed:
                    if progress:
                        progress(f"  skip {name} {variation} seed={seed}: {gate.reasons}")
                    continue
                pool.append(
                    Candidate(
                        generator=name,
                        params=resolved,
                        seed=seed,
                        n_frames=n_frames,
                        frames=frames,
                        features=table_features(frames),
                        intended_max_harmonic=imh,
                    )
                )
        if progress:
            progress(f"  rendered family {name}")
    return pool


def farthest_point_select(
    features: np.ndarray,
    target: int,
    *,
    min_separation: float,
) -> list[int]:
    """Greedy farthest-point sampling on standardized features. Returns selected
    indices, stopping at ``target`` or when the next pick is closer than
    ``min_separation`` (no diverse material left)."""
    n = features.shape[0]
    if n == 0:
        return []
    z = _standardize(features)
    # seed with the point farthest from the centroid (deterministic).
    centroid = z.mean(axis=0)
    first = int(np.argmax(np.linalg.norm(z - centroid, axis=1)))
    selected = [first]
    min_dist = np.linalg.norm(z - z[first], axis=1)
    while len(selected) < min(target, n):
        cand = int(np.argmax(min_dist))
        if min_dist[cand] < min_separation:
            break  # everything left is a near-duplicate of the selection
        selected.append(cand)
        min_dist = np.minimum(min_dist, np.linalg.norm(z - z[cand], axis=1))
    return selected


@dataclass
class BuildResult:
    written: list[dict[str, Any]]
    pool_size: int
    diversity: dict[str, Any]


def build_library(
    only: str | None = None,
    presets_path: str | None = None,
    out_dir: str | Path | None = None,
    progress: Callable[[str], None] | None = None,
    writer: Callable[[Candidate, Path], dict[str, Any]] | None = None,
) -> BuildResult:
    """Render the pool, select a diverse subset, and write it.

    ``writer`` is injected by the API so the bytes go through the single
    validated write path (and the catalog); it returns a per-table record.
    """
    from wtfoundry.core import export  # local import to avoid cycle at import time

    dcfg = config.diversity(presets_path)
    bcfg = config.build_cfg(presets_path)
    out_dir = Path(out_dir) if out_dir is not None else config._project_root() / "out"

    pool = candidate_pool(only=only, presets_path=presets_path, progress=progress)
    if not pool:
        raise RuntimeError("build produced an empty candidate pool")

    feats = np.array([c.features for c in pool])
    eps = float(dcfg["near_duplicate_epsilon"])
    chosen_idx = farthest_point_select(feats, int(bcfg["target_tables"]), min_separation=eps)
    chosen = [pool[i] for i in chosen_idx]

    # clear previously generated artifacts so the catalog reconciles 1:1
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.wav"):
        old.unlink()
    for old in out_dir.glob("*.png"):
        old.unlink()

    if writer is None:

        def writer(cand: Candidate, path: Path) -> dict[str, Any]:
            export.write_wavetable(cand.frames, path)
            return {"generator": cand.generator, "path": str(path)}

    written = []
    for cand in chosen:
        slug = table_slug(cand.generator, cand.params, cand.seed, cand.n_frames)
        path = out_dir / f"{slug}.wav"
        written.append(writer(cand, path))
        if progress:
            progress(f"  wrote {path.name}")

    div = diversity_report(np.array([c.features for c in chosen]), presets_path=presets_path)
    return BuildResult(
        written=written,
        pool_size=len(pool),
        diversity={
            "passed": div.passed,
            "mean_nn_distance": div.mean_nn_distance,
            "grid_coverage": div.grid_coverage,
            "near_duplicate_pairs": div.near_duplicate_pairs,
            "reasons": div.reasons,
        },
    )
