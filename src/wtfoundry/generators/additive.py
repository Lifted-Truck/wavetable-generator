"""Additive / harmonic-recipe synthesis.

Builds the spectrum directly: a harmonic series with a power-law tilt, an
optional even-harmonic attenuation (to slide between full and hollow/odd-only
timbres), and a brightness sweep that opens the band as the morph advances. This
is the most literal generator — the spectrum is the parameter set.
"""

from __future__ import annotations

import numpy as np

from wtfoundry.core import synth
from wtfoundry.generators.base import Frame, Generator, ParamSpec, Params, register


@register
class Additive(Generator):
    name = "additive"
    description = "Harmonic recipe with spectral tilt; brightness opens as it morphs."
    params = (
        ParamSpec("tilt", 1.0, 0.2, 3.0, "Power-law harmonic rolloff exponent (a_k ~ k^-tilt)."),
        ParamSpec("even_level", 1.0, 0.0, 1.0, "Level of even harmonics (0 = odd-only/hollow)."),
        ParamSpec(
            "bright", 0.5, 0.03, 1.0, "Fraction of the band reached at the end of the morph."
        ),
        ParamSpec(
            "bright_start", 0.02, 0.01, 0.5, "Fraction of the band at the start of the morph."
        ),
    )

    def _top(self, coord: float, params: Params) -> int:
        frac = params["bright_start"] + coord * (params["bright"] - params["bright_start"])
        frac = max(params["bright_start"], frac)
        return max(2, int(frac * synth.MAX_HARMONIC))

    def render(self, coord: float, params: Params) -> Frame:
        top = self._top(coord, params)
        amps = np.zeros(top + 1)
        k = np.arange(1, top + 1)
        amps[1:] = k.astype(float) ** (-params["tilt"])
        even = k % 2 == 0
        amps[1:][even] *= params["even_level"]
        return synth.from_harmonics(amps, synth._sine_phases(top + 1))

    def intended_max_harmonic(self, params: Params) -> int:
        return self._top(1.0, params)
