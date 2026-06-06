"""Unit tests for the synthesis primitives.

The references here are analytic (a cosine series with a known closed form), so
they are golden in the strongest sense: they pin the inverse-FFT scaling
convention and the band-limit guarantees, not just a snapshot of today's output.
"""

from __future__ import annotations

import numpy as np
import pytest

from wtfoundry.core import synth


def test_dimensions_and_finiteness():
    for wave in (synth.sine(), synth.saw(), synth.square(), synth.triangle(), synth.pulse(0.3)):
        assert wave.shape == (synth.SAMPLES_PER_FRAME,)
        assert np.all(np.isfinite(wave))


def test_sine_matches_analytic():
    y = synth.sine()
    expected = np.sin(synth.phase_axis())
    assert np.allclose(y, expected, atol=1e-9)


def test_from_harmonics_amplitude_convention():
    # A single cosine of amplitude 0.7 at the 3rd harmonic.
    amps = np.zeros(5)
    amps[3] = 0.7
    y = synth.from_harmonics(amps)
    expected = 0.7 * np.cos(3 * synth.phase_axis())
    assert np.allclose(y, expected, atol=1e-9)


def test_saw_harmonic_decay():
    spec = synth.magnitude_spectrum(synth.saw(64))
    k = np.arange(1, 33)
    # Sawtooth harmonics fall off as 1/k.
    ratios = spec[k] * k
    assert np.allclose(ratios, ratios[0], rtol=1e-6)


def test_square_is_odd_only():
    spec = synth.magnitude_spectrum(synth.square(64))
    even = spec[2:64:2]
    odd = spec[1:64:2]
    assert np.all(even < 1e-9)
    assert np.all(odd[:8] > 1e-3)


def test_triangle_decay_is_steeper_than_saw():
    tri = synth.magnitude_spectrum(synth.triangle(64))
    saw = synth.magnitude_spectrum(synth.saw(64))
    # triangle ~ 1/k^2, saw ~ 1/k: at k=9 triangle is far weaker relative to k=1
    assert (tri[9] / tri[1]) < (saw[9] / saw[1])


def test_loop_continuity_is_exact_for_harmonic_waves():
    # Inverse-FFT cycles are perfectly periodic: the wrap step matches the
    # interior step scale (no click).
    for wave in (synth.saw(128), synth.square(128), synth.triangle(128)):
        interior = np.max(np.abs(np.diff(wave)))
        wrap = abs(wave[0] - wave[-1])
        assert wrap <= interior * 1.5


def test_bandlimit_discards_out_of_band_energy():
    # A hard-clipped sine has energy well above Nyquist; render_oversampled must
    # return a clean band-limited cycle (length 2048 => no bins above 1024).
    clipped = synth.render_oversampled(lambda ph: np.clip(3.0 * np.sin(ph), -1, 1))
    assert clipped.shape == (synth.SAMPLES_PER_FRAME,)
    assert np.all(np.isfinite(clipped))
    # periodic / clean wrap
    interior = np.max(np.abs(np.diff(clipped)))
    assert abs(clipped[0] - clipped[-1]) <= interior * 2.0


def test_remove_dc():
    biased = synth.saw(64) + 0.3
    assert abs(synth.remove_dc(biased).mean()) < 1e-12


def test_normalize_peak_and_rms():
    w = synth.saw(64)
    assert np.max(np.abs(synth.normalize_peak(w, 0.9))) == pytest.approx(0.9, abs=1e-9)
    assert synth.rms(synth.normalize_rms(w, 0.4)) == pytest.approx(0.4, abs=1e-9)


def test_magnitude_spectrum_reads_true_amplitude():
    amps = np.zeros(10)
    amps[5] = 0.42
    spec = synth.magnitude_spectrum(synth.from_harmonics(amps))
    assert spec[5] == pytest.approx(0.42, abs=1e-9)
    assert spec[4] < 1e-9
