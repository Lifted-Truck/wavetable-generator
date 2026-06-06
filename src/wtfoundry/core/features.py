"""Perceptual feature extraction — the basis the diversity objective measures.

A single-cycle wavetable has no absolute pitch, so analysis uses a *nominal*
sample rate of ``SAMPLES_PER_FRAME`` Hz: harmonic ``k`` sits at exactly ``k`` Hz
and Nyquist is ``MAX_HARMONIC``. That mapping is arbitrary in absolute terms but
consistent across every table, and the mel scaling applied on top of it is what
makes "diverse" mean *audibly* diverse (low harmonics resolved finely, high
harmonics grouped coarsely) rather than numerically spread.

Per frame we extract: spectral centroid, spread, flatness, 85% rolloff,
odd/even harmonic ratio, harmonic-decay slope, and MFCCs. A table is 256 frames,
so the table descriptor is the per-frame mean of those, plus two "morph motion"
terms (how far the centroid and flatness travel across the morph) — a real
diversity axis that separates static tables from evolving ones.

Raw feature vectors are returned here; the library-level diversity metric in
validate.py standardizes them before computing distances.
"""

from __future__ import annotations

import numpy as np

from wtfoundry.core.synth import SAMPLES_PER_FRAME, magnitude_spectrum

NOMINAL_SR = float(SAMPLES_PER_FRAME)  # harmonic k == k Hz
N_MEL = 26
N_MFCC = 13
_EPS = 1e-12

# The ordered names of the table-level feature vector.
FEATURE_NAMES: list[str] = [
    "spectral_centroid",
    "spectral_spread",
    "spectral_flatness",
    "spectral_rolloff",
    "odd_even_ratio",
    "harmonic_decay_slope",
    *[f"mfcc_{i}" for i in range(N_MFCC)],
    "centroid_motion",
    "flatness_motion",
]


def _hz_to_mel(f: np.ndarray | float) -> np.ndarray | float:
    return 2595.0 * np.log10(1.0 + np.asarray(f, dtype=float) / 700.0)


def _mel_to_hz(m: np.ndarray | float) -> np.ndarray | float:
    return 700.0 * (10.0 ** (np.asarray(m, dtype=float) / 2595.0) - 1.0)


def _mel_filterbank(n_bins: int, n_filters: int = N_MEL, sr: float = NOMINAL_SR) -> np.ndarray:
    """Triangular mel filterbank over ``n_bins`` rFFT bins (bin index == Hz)."""
    fmax = sr / 2.0
    mel_pts = np.linspace(_hz_to_mel(1.0), _hz_to_mel(fmax), n_filters + 2)
    hz_pts = _mel_to_hz(mel_pts)
    bin_pts = np.clip(hz_pts, 0, n_bins - 1)
    fb = np.zeros((n_filters, n_bins))
    for i in range(1, n_filters + 1):
        left, center, right = bin_pts[i - 1], bin_pts[i], bin_pts[i + 1]
        if right - left < _EPS:
            continue
        idx = np.arange(n_bins, dtype=float)
        rising = (idx - left) / max(center - left, _EPS)
        falling = (right - idx) / max(right - center, _EPS)
        fb[i - 1] = np.clip(np.minimum(rising, falling), 0.0, None)
    return fb


def _dct_ii(x: np.ndarray, n_out: int) -> np.ndarray:
    """Orthonormal DCT-II of ``x``, returning the first ``n_out`` coefficients."""
    n = x.shape[0]
    k = np.arange(n_out)[:, None]
    m = np.arange(n)[None, :]
    basis = np.cos(np.pi * (m + 0.5) * k / n)
    coeffs = basis @ x
    scale = np.full(n_out, np.sqrt(2.0 / n))
    scale[0] = np.sqrt(1.0 / n)
    return coeffs * scale


_FILTERBANK = _mel_filterbank(SAMPLES_PER_FRAME // 2 + 1)


def frame_features(cycle: np.ndarray) -> dict[str, float | np.ndarray]:
    """Extract the per-frame feature set from one single cycle."""
    mag = magnitude_spectrum(cycle)
    power = mag**2
    freqs = np.arange(mag.shape[0], dtype=float)  # bin index == Hz (nominal)

    total = power.sum() + _EPS
    centroid = float((freqs * power).sum() / total)
    spread = float(np.sqrt(((freqs - centroid) ** 2 * power).sum() / total))

    pos = power[1:] + _EPS  # exclude DC for flatness
    flatness = float(np.exp(np.log(pos).mean()) / pos.mean())

    cumulative = np.cumsum(power)
    rolloff = float(np.searchsorted(cumulative, 0.85 * cumulative[-1]))

    harm = mag[1:]
    k = np.arange(1, harm.shape[0] + 1)
    odd = harm[k % 2 == 1]
    even = harm[k % 2 == 0]
    odd_even = float((odd**2).sum() / ((even**2).sum() + _EPS))

    # Harmonic-decay slope: log-magnitude vs log-harmonic linear fit.
    sig = mag[1:] > (mag[1:].max() * 1e-4) if mag[1:].size else np.array([])
    if sig.sum() >= 2:
        lk = np.log(k[sig])
        lm = np.log(mag[1:][sig] + _EPS)
        slope = float(np.polyfit(lk, lm, 1)[0])
    else:
        slope = 0.0

    mel_energy = np.log(_FILTERBANK @ power + _EPS)
    mfcc = _dct_ii(mel_energy, N_MFCC)

    return {
        "spectral_centroid": centroid,
        "spectral_spread": spread,
        "spectral_flatness": flatness,
        "spectral_rolloff": rolloff,
        "odd_even_ratio": odd_even,
        "harmonic_decay_slope": slope,
        "mfcc": mfcc,
    }


def table_features(frames: np.ndarray) -> np.ndarray:
    """Aggregate per-frame features over a table into one descriptor vector,
    ordered as ``FEATURE_NAMES``. ``frames`` is shaped (n_frames, n_samples)."""
    frames = np.atleast_2d(np.asarray(frames, dtype=float))
    centroids, flatnesses = [], []
    scalars: list[list[float]] = []
    mfccs = []
    for cycle in frames:
        f = frame_features(cycle)
        scalars.append(
            [
                f["spectral_centroid"],
                f["spectral_spread"],
                f["spectral_flatness"],
                f["spectral_rolloff"],
                f["odd_even_ratio"],
                f["harmonic_decay_slope"],
            ]
        )
        mfccs.append(f["mfcc"])
        centroids.append(f["spectral_centroid"])
        flatnesses.append(f["spectral_flatness"])

    scalar_mean = np.mean(scalars, axis=0)
    mfcc_mean = np.mean(mfccs, axis=0)
    centroid_motion = float(np.std(centroids))
    flatness_motion = float(np.std(flatnesses))

    return np.concatenate([scalar_mean, mfcc_mean, [centroid_motion, flatness_motion]]).astype(
        float
    )


def features_dict(frames: np.ndarray) -> dict[str, float]:
    """The table descriptor as a name->value mapping (for the catalog)."""
    vec = table_features(frames)
    return {name: float(v) for name, v in zip(FEATURE_NAMES, vec)}
