"""Unit tests for perceptual feature extraction.

These assert that the features behave the way the ear expects — a sine is dark
and peaky, a saw is bright and flat-ish with a 1/k tilt, noise is maximally
flat — and that the table descriptor is stable and discriminating, which is the
property the Layer-2 diversity objective relies on.
"""

from __future__ import annotations

import numpy as np
import pytest

from wtfoundry.core import features, synth


def _table(cycle: np.ndarray, n_frames: int = 8) -> np.ndarray:
    return np.tile(cycle, (n_frames, 1))


def test_sine_is_dark_and_peaky():
    f = features.frame_features(synth.sine())
    assert f["spectral_centroid"] == pytest.approx(1.0, abs=0.5)  # only harmonic 1
    assert f["spectral_flatness"] < 0.05
    assert f["spectral_rolloff"] <= 2


def test_saw_is_brighter_than_sine():
    sine = features.frame_features(synth.sine())
    saw = features.frame_features(synth.saw())
    assert saw["spectral_centroid"] > sine["spectral_centroid"]
    assert saw["spectral_flatness"] > sine["spectral_flatness"]


def test_saw_decay_slope_near_minus_one():
    f = features.frame_features(synth.saw(256))
    assert f["harmonic_decay_slope"] == pytest.approx(-1.0, abs=0.15)


def test_triangle_decay_slope_near_minus_two():
    f = features.frame_features(synth.triangle(256))
    assert f["harmonic_decay_slope"] == pytest.approx(-2.0, abs=0.3)


def test_square_has_high_odd_even_ratio():
    f = features.frame_features(synth.square(256))
    assert f["odd_even_ratio"] > 100.0


def test_noise_is_flat():
    rng = np.random.default_rng(0)
    n_bins = synth.SAMPLES_PER_FRAME // 2 + 1
    amps = np.zeros(n_bins)
    amps[1:] = rng.uniform(0.5, 1.0, n_bins - 1)  # full-band, fairly even
    noisy = synth.from_harmonics(amps, rng.uniform(0, 2 * np.pi, n_bins))
    f = features.frame_features(noisy)
    assert f["spectral_flatness"] > 0.1
    assert f["spectral_flatness"] > features.frame_features(synth.saw())["spectral_flatness"]


def test_table_descriptor_shape_and_names():
    vec = features.table_features(_table(synth.saw()))
    assert vec.shape == (len(features.FEATURE_NAMES),)
    assert np.all(np.isfinite(vec))
    d = features.features_dict(_table(synth.saw()))
    assert list(d.keys()) == features.FEATURE_NAMES


def test_identical_tables_have_zero_distance():
    a = features.table_features(_table(synth.saw()))
    b = features.table_features(_table(synth.saw()))
    assert np.allclose(a, b)


def test_different_tables_are_separated():
    saw = features.table_features(_table(synth.saw()))
    sine = features.table_features(_table(synth.sine()))
    assert np.linalg.norm(saw - sine) > 1.0


def test_morph_motion_detects_evolution():
    # A static table (all frames identical) vs an evolving one (sine -> saw).
    static = _table(synth.sine(), 16)
    frames = []
    for i in range(16):
        mix = i / 15.0
        frames.append((1 - mix) * synth.sine() + mix * synth.saw(128))
    evolving = np.array(frames)
    static_vec = features.features_dict(static)
    evolving_vec = features.features_dict(evolving)
    assert evolving_vec["centroid_motion"] > static_vec["centroid_motion"]
    assert static_vec["centroid_motion"] < 1e-6
