"""Direct spectral sculpting (inverse FFT).

The spectrum is painted directly: a few Gaussian magnitude bumps placed in the
band, with seeded randomized phases that give an inharmonic, glassy / cluster
character distinct from the smooth additive recipe. As the morph advances the
bumps sweep across the band. The frame is the inverse FFT of the sculpted
spectrum, so it is band-limited and loop-continuous by construction.
"""

from __future__ import annotations

import numpy as np

from wtfoundry.core import synth
from wtfoundry.generators.base import Frame, Generator, ParamSpec, Params, register


@register
class Spectral(Generator):
    name = "spectral"
    description = "Inverse-FFT spectral sculpting; randomized-phase bumps sweep the band."
    stochastic = True
    params = (
        ParamSpec("n_peaks", 3.0, 1.0, 8.0, "Number of Gaussian spectral bumps.", kind="int"),
        ParamSpec("width", 0.04, 0.005, 0.2, "Bump width as a fraction of the band."),
        ParamSpec("center_start", 0.08, 0.02, 0.6, "Lowest bump center (band fraction) at start."),
        ParamSpec("center_end", 0.5, 0.05, 0.95, "Lowest bump center (band fraction) at end."),
        ParamSpec("phase_rand", 0.8, 0.0, 1.0, "How randomized the harmonic phases are."),
    )

    def render(self, coord: float, params: Params) -> Frame:
        n_bins = synth.MAX_HARMONIC + 1
        k = np.arange(n_bins, dtype=float)
        base = params["center_start"] + coord * (params["center_end"] - params["center_start"])
        width = params["width"] * synth.MAX_HARMONIC

        mag = np.zeros(n_bins)
        n_peaks = int(params["n_peaks"])
        for i in range(n_peaks):
            # peaks spread above the base center, harmonically spaced
            center = base * synth.MAX_HARMONIC * (i + 1)
            if center >= synth.MAX_HARMONIC:
                break
            mag += np.exp(-0.5 * ((k - center) / width) ** 2)
        mag[0] = 0.0

        rand_phase = self.rng.uniform(0.0, synth.TWO_PI, n_bins)
        phases = params["phase_rand"] * rand_phase + (1.0 - params["phase_rand"]) * (-np.pi / 2)
        return synth.from_harmonics(mag, phases)
