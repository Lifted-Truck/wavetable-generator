"""Formant / vocal synthesis (source-filter).

A harmonic-rich source (a soft saw) is shaped by a bank of resonant formant
peaks placed at vowel-like frequencies, then the morph glides between two vowels
so the table "speaks" as it sweeps. Mechanically distinct from spectral: the
source is fully harmonic with coherent phase, and the magnitude envelope is a
fixed vocal formant model rather than arbitrary painted bumps.
"""

from __future__ import annotations

import numpy as np

from wtfoundry.core import synth
from wtfoundry.generators.base import Frame, Generator, ParamSpec, Params, register

# Vowel formant centers as a fraction of the nominal band (scaled, stylized).
_VOWELS = {
    "a": (0.03, 0.07, 0.12),
    "e": (0.02, 0.10, 0.14),
    "i": (0.015, 0.11, 0.16),
    "o": (0.02, 0.04, 0.10),
    "u": (0.015, 0.03, 0.08),
}
_ORDER = ["a", "e", "i", "o", "u"]


@register
class Formant(Generator):
    name = "formant"
    description = "Source-filter vocal formants; glides between two vowels as it morphs."
    params = (
        ParamSpec("vowel_from", 0.0, 0.0, 4.0, "Start vowel index (a,e,i,o,u).", kind="int"),
        ParamSpec("vowel_to", 2.0, 0.0, 4.0, "End vowel index (a,e,i,o,u).", kind="int"),
        ParamSpec("tilt", 0.7, 0.3, 1.5, "Source spectral tilt (a_k ~ k^-tilt)."),
        ParamSpec("bandwidth", 0.025, 0.008, 0.08, "Formant resonance width (band fraction)."),
    )

    def render(self, coord: float, params: Params) -> Frame:
        n_bins = synth.MAX_HARMONIC + 1
        k = np.arange(n_bins, dtype=float)

        # harmonic source
        source = np.zeros(n_bins)
        source[1:] = k[1:] ** (-params["tilt"])

        # interpolate formant centers between the two vowels
        f_a = np.array(_VOWELS[_ORDER[int(params["vowel_from"])]])
        f_b = np.array(_VOWELS[_ORDER[int(params["vowel_to"])]])
        centers = ((1 - coord) * f_a + coord * f_b) * synth.MAX_HARMONIC
        bw = params["bandwidth"] * synth.MAX_HARMONIC

        envelope = np.full(n_bins, 0.02)
        for c in centers:
            envelope += np.exp(-0.5 * ((k - c) / bw) ** 2)

        mag = source * envelope
        mag[0] = 0.0
        return synth.from_harmonics(mag, synth._sine_phases(n_bins))
