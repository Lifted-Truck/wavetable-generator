"""Golden and known-bad table fixtures for the oracle tests.

Built programmatically (deterministic) rather than stored as bytes, so a fixture
is a readable recipe for exactly *why* it is good or bad. The known-bad set is
the heart of milestone 3: an oracle that cannot reject these is worthless.
"""

from __future__ import annotations

import numpy as np

from wtfoundry.core import synth


def _tile(cycle: np.ndarray, n_frames: int = 8) -> np.ndarray:
    return np.tile(synth.normalize_peak(synth.remove_dc(cycle), 0.9), (n_frames, 1))


# --------------------------------------------------------------------------
# Golden (should PASS every Layer-1 gate).
# --------------------------------------------------------------------------
def golden_sine() -> np.ndarray:
    return _tile(synth.sine())


def golden_saw() -> np.ndarray:
    return _tile(synth.saw(512))


# --------------------------------------------------------------------------
# Known-bad (each should FAIL exactly the named gate).
# --------------------------------------------------------------------------
def bad_aliased() -> np.ndarray:
    """Full-band energy while declaring a low intended top harmonic — the
    aliasing gate must catch energy above the band the table claims. Pair with
    ``intended_max_harmonic=64`` in the gate call."""
    return _tile(synth.saw(512))


def bad_dc_offset() -> np.ndarray:
    """A large constant offset; DC is nowhere near zero."""
    return np.tile(synth.normalize_peak(synth.sine(), 0.9) + 0.5, (8, 1))


def bad_loop_click() -> np.ndarray:
    """A non-periodic ramp per frame: the endpoints don't meet, so the loop
    point clicks."""
    ramp = np.linspace(-0.8, 0.8, synth.SAMPLES_PER_FRAME)
    return np.tile(ramp, (8, 1))


def near_duplicate_library() -> np.ndarray:
    """A small set of feature vectors where two tables are near-identical and
    the rest are distinct — the Layer-2 near-duplicate reject must flag the
    pair. Returns the *tables* (frames stacked); features computed downstream."""
    base = synth.saw(512)
    almost = base + 1e-4 * synth.sine()  # imperceptibly different
    distinct = [synth.square(256), synth.triangle(256), synth.pulse(0.2, 256)]
    return [
        _tile(base),
        _tile(almost),
        *[_tile(w) for w in distinct],
    ]
