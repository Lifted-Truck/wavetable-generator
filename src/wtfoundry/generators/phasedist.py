"""Phase-distortion synthesis (Casio CZ style).

A cosine is read through a warped phase index: a moveable "knee" accelerates the
read through part of the cycle and decelerates through the rest, bending a pure
sine toward saw- and pulse-like spectra. As the morph advances the knee slides
away from center, deepening the distortion. Mechanically distinct from FM — there
is no modulator; the timbre comes from re-indexing a fixed waveshape.
"""

from __future__ import annotations

import numpy as np

from wtfoundry.core import synth
from wtfoundry.generators.base import Frame, Generator, ParamSpec, Params, register


@register
class PhaseDistortion(Generator):
    name = "phasedist"
    description = "Casio-CZ phase distortion; the knee deepens as it morphs (saw/reso)."
    params = (
        ParamSpec("amount_start", 0.05, 0.0, 0.95, "Phase-warp amount at the start of the morph."),
        ParamSpec("amount_end", 0.9, 0.05, 0.98, "Phase-warp amount at the end of the morph."),
        ParamSpec("skew", 0.0, -0.8, 0.8, "Bias of the knee toward the start/end of the cycle."),
    )

    def render(self, coord: float, params: Params) -> Frame:
        amount = params["amount_start"] + coord * (params["amount_end"] - params["amount_start"])
        # knee position: amount 0 -> 0.5 (pure cosine), amount 1 -> near the edge
        m = 0.5 - 0.49 * amount + 0.2 * params["skew"]
        m = float(np.clip(m, 0.02, 0.98))

        def shape(ph: np.ndarray) -> np.ndarray:
            p = (ph / synth.TWO_PI) % 1.0
            warped = np.where(p < m, 0.5 * p / m, 0.5 + 0.5 * (p - m) / (1.0 - m))
            return -np.cos(synth.TWO_PI * warped)

        return synth.render_oversampled(shape, oversample=8)
