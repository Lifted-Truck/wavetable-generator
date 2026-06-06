"""The oracle.

Layer 1 — quality gates (hard, per-table, binary), enforced at the write.py
boundary so every client's output is valid:
  - band-limiting / no aliasing (no energy above the intended top harmonic)
  - DC offset ~= 0
  - loop continuity (endpoint + first-derivative discontinuity below threshold)
  - loudness within tolerance of a target (peak or RMS)
  - format conformance (sample count, channels, bit depth, frame count)

Layer 2 — diversity / coverage objective (library-level), the thing that
prevents convergence:
  - mean nearest-neighbor distance in feature space
  - coverage of a quantized feature grid
  - near-duplicate reject (no two tables within epsilon)

Tolerances and the diversity threshold live in presets.yaml.

SCAFFOLD STATE: not yet implemented (Run 1, milestone 3 — the most important
step: an oracle that never fails is worthless)."""

from __future__ import annotations
