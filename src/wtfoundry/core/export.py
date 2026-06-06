"""Pluggable packaging of frames into a deliverable wavetable.

Serum is 1-D today (256 frames x 2048 samples, 32-bit float mono, concatenated).
A 2-D+ target is a different container or a documented flatten order — kept
pluggable so multidimensional readiness costs nothing now.

SCAFFOLD STATE: not yet implemented (Run 1, milestone 6)."""

from __future__ import annotations
