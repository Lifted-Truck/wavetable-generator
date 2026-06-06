"""Perceptual feature extraction — the basis the diversity objective measures in.

Per-table feature vector: spectral centroid, spread, flatness, rolloff,
odd/even harmonic ratio, harmonic-decay slope, and MFCCs. Features are computed
in a perceptually scaled space (bark/mel, perceptual loudness) by default, so
that "diverse" means audibly diverse. A flat-spectral basis is the one-line
alternative documented here.

SCAFFOLD STATE: not yet implemented (Run 1, milestone 2)."""

from __future__ import annotations
