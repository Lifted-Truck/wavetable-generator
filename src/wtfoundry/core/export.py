"""Pluggable packaging of frames into a deliverable wavetable.

Serum 2 reads a wavetable as a mono file sliced into fixed-size single cycles.
The 1-D target here concatenates frames row-major into one float32 stream of
``n_frames * samples_per_frame`` samples. The flatten order is documented and
isolated in this module so a 2-D+ target (a different container, or a different
documented order) is a drop-in later without touching the gates or generators.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from wtfoundry.core.synth import SAMPLES_PER_FRAME

# Serum treats the file as raw single cycles; the rate is a container formality.
SAMPLE_RATE = 44100
SUBTYPE = "FLOAT"  # 32-bit IEEE float


def write_wavetable(frames: np.ndarray, path: str | Path) -> Path:
    """Write ``frames`` (n_frames x SAMPLES_PER_FRAME) as a Serum-compatible
    mono 32-bit-float wav. Frames are concatenated in row-major order."""
    frames = np.atleast_2d(np.asarray(frames, dtype=np.float32))
    if frames.shape[1] != SAMPLES_PER_FRAME:
        raise ValueError(f"each frame must be {SAMPLES_PER_FRAME} samples, got {frames.shape[1]}")
    stream = frames.reshape(-1).astype(np.float32)
    path = Path(path)
    sf.write(path, stream, SAMPLE_RATE, subtype=SUBTYPE, format="WAV")
    return path


def read_wavetable(path: str | Path, samples_per_frame: int = SAMPLES_PER_FRAME) -> np.ndarray:
    """Read a wavetable back into frames (n_frames x samples_per_frame). Inverse
    of ``write_wavetable``; used by tests and catalog reconciliation."""
    data, _ = sf.read(path, dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data[:, 0]
    n = data.shape[0]
    if n % samples_per_frame != 0:
        raise ValueError(
            f"{path}: {n} samples is not a whole number of {samples_per_frame}-sample frames"
        )
    return data.reshape(-1, samples_per_frame)
