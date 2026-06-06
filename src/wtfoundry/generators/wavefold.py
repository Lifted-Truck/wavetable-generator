"""Wavefolding / non-linear shaping.

A sine driven through a sinusoidal wavefolder: as the drive grows across the
morph, the signal folds back on itself more times, generating progressively
richer (and characteristically metallic) harmonics. A symmetry bias breaks the
odd-only symmetry to introduce even harmonics. Mechanically distinct again — the
harmonics come from a memoryless non-linearity, band-limited by oversampled
resynthesis.
"""

from __future__ import annotations

import numpy as np

from wtfoundry.core import synth
from wtfoundry.generators.base import Frame, Generator, ParamSpec, Params, register


@register
class Wavefold(Generator):
    name = "wavefold"
    description = "Sinusoidal wavefolder; fold depth grows as it morphs (metallic)."
    params = (
        ParamSpec("fold", 5.0, 1.0, 9.0, "Peak fold depth (drive) at the end of the morph."),
        ParamSpec("fold_start", 1.0, 0.5, 5.0, "Fold depth at the start of the morph."),
        ParamSpec("symmetry", 0.0, -0.9, 0.9, "DC bias into the folder (adds even harmonics)."),
    )

    def render(self, coord: float, params: Params) -> Frame:
        drive = params["fold_start"] + coord * (params["fold"] - params["fold_start"])
        bias = params["symmetry"]

        def shape(ph: np.ndarray) -> np.ndarray:
            x = np.sin(ph) + bias
            return np.sin(np.pi * drive * x)

        return synth.render_oversampled(shape, oversample=8)
