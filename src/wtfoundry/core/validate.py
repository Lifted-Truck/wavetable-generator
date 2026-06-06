"""The oracle.

Layer 1 — quality gates (hard, per-table, binary). Enforced at the write.py
boundary so every client's output is valid no matter which lever produced it:

  - aliasing      : energy above the intended top harmonic is below threshold
  - dc_offset     : |mean| is ~ 0
  - loop_continuity: the wrap-point value and slope jumps are in scale with the
                     interior (no click), measured as scale-invariant ratios
  - loudness      : table RMS/peak is within tolerance of the target
  - format        : sample count, frame count, channels, finiteness

Layer 2 — diversity / coverage objective (library-level). The thing that
prevents convergence:

  - mean nearest-neighbor distance in standardized feature space
  - coverage of a quantized 2-D projection of feature space
  - near-duplicate rejection (no two tables within epsilon)

An oracle that never fails is worthless, so the design point is that it MUST
reject the known-bad fixtures: an aliased table, a DC-offset table, a
loop-click table, and a pair of near-duplicates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from wtfoundry.core import config


@dataclass
class GateResult:
    """Outcome of the Layer-1 gates for one table."""

    passed: bool
    checks: dict[str, bool]
    measures: dict[str, float]
    reasons: list[str] = field(default_factory=list)


def _as_frames(table: np.ndarray) -> np.ndarray:
    return np.atleast_2d(np.asarray(table, dtype=float))


def _out_of_band_db(frame: np.ndarray, max_harmonic: int) -> float:
    """Energy above ``max_harmonic`` relative to total, in dB (-inf if clean)."""
    spec = np.abs(np.fft.rfft(frame)) ** 2
    total = spec.sum() + 1e-30
    hi = min(max_harmonic, spec.shape[0] - 1)
    above = spec[hi + 1 :].sum()
    if above <= 0:
        return -np.inf
    return 10.0 * np.log10(above / total)


def _continuity_ratios(frame: np.ndarray) -> tuple[float, float]:
    """(value_ratio, slope_ratio) of the wrap point vs the interior."""
    d1 = frame - np.roll(frame, 1)  # cyclic first difference; d1[0] is the wrap
    d2 = d1 - np.roll(d1, 1)  # cyclic second difference
    interior_step = np.max(np.abs(d1[1:])) + 1e-12
    interior_curv = np.max(np.abs(d2[2:])) + 1e-12
    value_ratio = abs(d1[0]) / interior_step
    slope_ratio = max(abs(d2[0]), abs(d2[1])) / interior_curv
    return float(value_ratio), float(slope_ratio)


def check_gates(
    table: np.ndarray,
    *,
    intended_max_harmonic: int | None = None,
    presets_path: str | None = None,
) -> GateResult:
    """Run all Layer-1 gates on a table (n_frames x samples_per_frame)."""
    g = config.gates(presets_path)
    frames = _as_frames(table)
    checks: dict[str, bool] = {}
    measures: dict[str, float] = {}
    reasons: list[str] = []

    # --- format conformance ---
    n_frames, n_samples = frames.shape
    fmt = config.fmt(presets_path)
    fmt_ok = (
        n_samples == fmt["samples_per_frame"]
        and 1 <= n_frames <= fmt["frames_per_table"]
        and np.all(np.isfinite(frames))
    )
    checks["format"] = bool(fmt_ok)
    measures["n_frames"] = float(n_frames)
    measures["n_samples"] = float(n_samples)
    if not fmt_ok:
        reasons.append(
            f"format: {n_frames}x{n_samples}, expected frames<= "
            f"{fmt['frames_per_table']} x {fmt['samples_per_frame']}, all finite"
        )

    # --- aliasing ---
    max_h = intended_max_harmonic or g["aliasing"]["max_harmonic"]
    oob = max(_out_of_band_db(f, max_h) for f in frames)
    checks["aliasing"] = oob <= g["aliasing"]["out_of_band_db"]
    measures["out_of_band_db"] = float(oob if np.isfinite(oob) else -300.0)
    if not checks["aliasing"]:
        reasons.append(
            f"aliasing: {oob:.1f} dB above harmonic {max_h} "
            f"(limit {g['aliasing']['out_of_band_db']} dB)"
        )

    # --- DC offset ---
    dc = float(np.max(np.abs(frames.mean(axis=1))))
    checks["dc_offset"] = dc <= g["dc_offset_max"]
    measures["dc_offset"] = dc
    if not checks["dc_offset"]:
        reasons.append(f"dc_offset: {dc:.2e} (limit {g['dc_offset_max']:.0e})")

    # --- loop continuity ---
    lc = g["loop_continuity"]
    vr = sr = 0.0
    for f in frames:
        v, s = _continuity_ratios(f)
        vr, sr = max(vr, v), max(sr, s)
    checks["loop_continuity"] = vr <= lc["value_ratio_max"] and sr <= lc["slope_ratio_max"]
    measures["value_ratio"] = vr
    measures["slope_ratio"] = sr
    if not checks["loop_continuity"]:
        reasons.append(
            f"loop_continuity: value {vr:.1f}/{lc['value_ratio_max']}, "
            f"slope {sr:.1f}/{lc['slope_ratio_max']}"
        )

    # --- loudness ---
    loud = g["loudness"]
    if loud["metric"] == "peak":
        level = float(np.max(np.abs(frames)))
    else:
        level = float(np.sqrt(np.mean(frames**2)))
    target = loud["target"]
    db_off = 20.0 * np.log10((level + 1e-12) / target)
    checks["loudness"] = abs(db_off) <= loud["tolerance_db"]
    measures["loudness_db_off"] = float(db_off)
    if not checks["loudness"]:
        reasons.append(f"loudness: {db_off:+.1f} dB from target (tol +/-{loud['tolerance_db']} dB)")

    checks = {k: bool(v) for k, v in checks.items()}
    return GateResult(all(checks.values()), checks, measures, reasons)


# --------------------------------------------------------------------------
# Layer 2 — diversity / coverage (library level).
# --------------------------------------------------------------------------
def _standardize(vectors: np.ndarray) -> np.ndarray:
    """Z-score per feature; drop zero-variance dimensions so they don't dominate
    or inject NaNs."""
    vectors = np.atleast_2d(np.asarray(vectors, dtype=float))
    std = vectors.std(axis=0)
    keep = std > 1e-9
    if not np.any(keep):
        return np.zeros((vectors.shape[0], 1))
    return (vectors[:, keep] - vectors[:, keep].mean(axis=0)) / std[keep]


def _pairwise_distances(z: np.ndarray) -> np.ndarray:
    diff = z[:, None, :] - z[None, :, :]
    return np.sqrt((diff**2).sum(axis=-1))


@dataclass
class DiversityResult:
    passed: bool
    mean_nn_distance: float
    grid_coverage: float
    near_duplicate_pairs: list[tuple[int, int]]
    reasons: list[str] = field(default_factory=list)


def diversity_report(
    feature_vectors: np.ndarray,
    *,
    presets_path: str | None = None,
) -> DiversityResult:
    """Score the spread of a library of table feature vectors."""
    d = config.diversity(presets_path)
    vectors = np.atleast_2d(np.asarray(feature_vectors, dtype=float))
    n = vectors.shape[0]
    reasons: list[str] = []

    if n < 2:
        return DiversityResult(True, float("inf"), 1.0, [], [])

    z = _standardize(vectors)
    dist = _pairwise_distances(z)
    np.fill_diagonal(dist, np.inf)

    nn = dist.min(axis=1)
    mean_nn = float(np.mean(nn))

    eps = d["near_duplicate_epsilon"]
    pairs = [(int(i), int(j)) for i in range(n) for j in range(i + 1, n) if dist[i, j] < eps]

    coverage = _grid_coverage(z, int(d["grid_bins"]))

    passed = True
    if mean_nn < d["min_mean_nn_distance"]:
        passed = False
        reasons.append(f"mean_nn_distance {mean_nn:.3f} < {d['min_mean_nn_distance']}")
    if coverage < d["min_grid_coverage"]:
        passed = False
        reasons.append(f"grid_coverage {coverage:.3f} < {d['min_grid_coverage']}")
    if pairs:
        passed = False
        reasons.append(f"{len(pairs)} near-duplicate pair(s) within eps={eps}")

    return DiversityResult(passed, mean_nn, coverage, pairs, reasons)


def _grid_coverage(z: np.ndarray, bins: int) -> float:
    """Fraction of occupied cells in a 2-D projection (first two principal
    directions) of standardized feature space."""
    if z.shape[0] < 2:
        return 1.0
    # Project to the top 2 principal components for a stable low-dim grid.
    centered = z - z.mean(axis=0)
    try:
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
        proj = centered @ vt[: min(2, vt.shape[0])].T
    except np.linalg.LinAlgError:
        proj = centered[:, : min(2, centered.shape[1])]
    if proj.shape[1] < 2:
        proj = np.column_stack([proj, np.zeros(proj.shape[0])])

    lo = proj.min(axis=0)
    hi = proj.max(axis=0)
    span = np.where(hi - lo > 1e-9, hi - lo, 1.0)
    idx = np.floor((proj - lo) / span * bins).astype(int)
    idx = np.clip(idx, 0, bins - 1)
    occupied = {tuple(row) for row in idx}
    return len(occupied) / float(bins * bins)
