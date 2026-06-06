"""FM / phase-modulation synthesis.

A two-operator phase-modulation voice: a sine carrier whose phase is modulated
by a sine at an integer ``ratio``, with the modulation ``index`` sweeping from
zero up across the morph so the spectrum blooms from pure tone to a dense FM
timbre. Mechanically distinct from additive — the harmonics arise from Bessel
sidebands, not a directly written spectrum. The non-linear output is band-limited
by oversampled resynthesis.
"""

from __future__ import annotations

import numpy as np

from wtfoundry.core import synth
from wtfoundry.generators.base import Frame, Generator, ParamSpec, Params, register


@register
class FM(Generator):
    name = "fm"
    description = "Two-operator phase modulation; the modulation index opens as it morphs."
    params = (
        ParamSpec("ratio", 2.0, 1.0, 8.0, "Modulator:carrier frequency ratio.", kind="int"),
        ParamSpec("index_max", 6.0, 0.5, 12.0, "Peak modulation index at the end of the morph."),
        ParamSpec("index_start", 0.0, 0.0, 6.0, "Modulation index at the start of the morph."),
        ParamSpec("feedback", 0.0, 0.0, 1.0, "Modulator self-feedback amount (adds grit)."),
    )

    def render(self, coord: float, params: Params) -> Frame:
        ratio = int(params["ratio"])
        index = params["index_start"] + coord * (params["index_max"] - params["index_start"])
        fb = params["feedback"]

        def shape(ph: np.ndarray) -> np.ndarray:
            mod = np.sin(ratio * ph)
            if fb > 0:
                # one-step approximation of modulator self-feedback
                mod = np.sin(ratio * ph + fb * mod)
            return np.sin(ph + index * mod)

        return synth.render_oversampled(shape, oversample=8)
