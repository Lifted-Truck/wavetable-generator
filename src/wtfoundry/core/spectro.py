"""Spectrogram rendering for wavetables.

A wavetable's "spectrogram" is its morph laid out in time: each frame's harmonic
magnitude spectrum becomes one column, so the image shows how the timbre evolves
from the start of the morph to the end. Rendered headless (Agg backend) so it
runs inside the locked-down build with no display.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless; must precede pyplot import
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from wtfoundry.core import export  # noqa: E402
from wtfoundry.core.synth import magnitude_spectrum  # noqa: E402

DISPLAY_HARMONICS = 256  # show the lower band where most energy lives
FLOOR_DB = -90.0


def render_spectrogram(
    wav_path: str | Path,
    out_path: str | Path | None = None,
    *,
    display_harmonics: int = DISPLAY_HARMONICS,
) -> Path:
    """Render a morph spectrogram PNG for the wavetable at ``wav_path``. Returns
    the image path (defaults to the wav path with a .png suffix)."""
    wav_path = Path(wav_path)
    out_path = Path(out_path) if out_path is not None else wav_path.with_suffix(".png")

    frames = export.read_wavetable(wav_path)
    cols = []
    for frame in frames:
        mag = magnitude_spectrum(frame)[1 : display_harmonics + 1]
        db = 20.0 * np.log10(mag + 1e-9)
        cols.append(np.clip(db, FLOOR_DB, 0.0))
    img = np.array(cols).T  # harmonics (y) x frames (x)

    fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
    ax.imshow(
        img,
        origin="lower",
        aspect="auto",
        cmap="magma",
        extent=[0, frames.shape[0], 1, display_harmonics],
        vmin=FLOOR_DB,
        vmax=0.0,
    )
    ax.set_xlabel("morph frame")
    ax.set_ylabel("harmonic")
    ax.set_title(wav_path.stem)
    fig.colorbar(ax.images[0], ax=ax, label="dB")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path
