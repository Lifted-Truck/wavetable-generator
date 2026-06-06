"""Shared single-cycle synthesis primitives used by every generator family.

The engine is the inverse real FFT: a single cycle is built from a spectrum of
harmonic coefficients up to ``MAX_HARMONIC``. Building waveforms this way buys
three of the Layer-1 gates for free:

  - **No aliasing** — the spectrum simply has no energy above the top harmonic.
  - **Exact loop continuity** — an inverse-FFT cycle is perfectly periodic, so
    its endpoint and first derivative wrap without a click.
  - **Exact DC removal** — bin 0 is set to zero.

Non-linear families (FM, wavefolding, phase distortion) generate a time-domain
shape that *would* alias; ``bandlimit`` resynthesizes them through an
oversampled FFT, discarding everything above the top harmonic rather than
letting it fold back. Everything here returns a float64 single cycle of length
``SAMPLES_PER_FRAME``; packaging to float32 happens at the export boundary.
"""

from __future__ import annotations

import numpy as np

SAMPLES_PER_FRAME = 2048
MAX_HARMONIC = SAMPLES_PER_FRAME // 2  # 1024 — Nyquist for the single cycle
TWO_PI = 2.0 * np.pi


def phase_axis(n: int = SAMPLES_PER_FRAME) -> np.ndarray:
    """One period of phase in [0, 2*pi), sampled at ``n`` points (endpoint
    excluded so the cycle wraps)."""
    return np.linspace(0.0, TWO_PI, n, endpoint=False)


def from_harmonics(
    amplitudes: np.ndarray | list[float],
    phases: np.ndarray | list[float] | None = None,
    n: int = SAMPLES_PER_FRAME,
) -> np.ndarray:
    """Synthesize a single cycle from harmonic ``amplitudes`` (index 0 = DC).

    Returns ``y[m] = a0 + sum_k a_k * cos(2*pi*k*m/n + phase_k)``. Harmonics at
    or beyond Nyquist are ignored, so the result is always band-limited; DC is
    whatever ``amplitudes[0]`` says (generators pass 0).
    """
    amplitudes = np.asarray(amplitudes, dtype=float)
    n_bins = n // 2 + 1
    k = min(amplitudes.shape[0], n_bins)
    if phases is None:
        ph = np.zeros(k)
    else:
        ph = np.asarray(phases, dtype=float)
        ph = np.resize(ph, amplitudes.shape[0])[:k]

    coeff = np.zeros(n_bins, dtype=complex)
    coeff[:k] = amplitudes[:k].astype(complex) * np.exp(1j * ph)

    # Scale cosine-amplitude coefficients into numpy's irfft convention:
    # DC and Nyquist bins map by n; interior bins by n/2 (they have a conjugate
    # partner that irfft supplies). The Nyquist bin must be set from the
    # original coefficient, not the already-scaled interior value.
    spec = coeff * (n / 2.0)
    spec[0] = coeff[0].real * n
    if n % 2 == 0:
        spec[n // 2] = coeff[n // 2].real * n
    return np.fft.irfft(spec, n=n)


def bandlimit(
    cycle: np.ndarray,
    max_harmonic: int = MAX_HARMONIC,
    oversample: int = 1,
) -> np.ndarray:
    """Project an arbitrary single cycle onto the band-limited harmonic basis.

    The cycle is analyzed by rFFT and every harmonic above ``max_harmonic`` is
    discarded, then resynthesized at ``SAMPLES_PER_FRAME`` points. When the
    cycle was produced by a non-linear process, pass it pre-rendered at
    ``oversample * SAMPLES_PER_FRAME`` points so harmonics that would alias at
    the base rate are captured and discarded instead of folding back.
    """
    cycle = np.asarray(cycle, dtype=float)
    spec = np.fft.rfft(cycle)
    n_src = cycle.shape[0]
    keep = min(max_harmonic, SAMPLES_PER_FRAME // 2) + 1
    out = np.zeros(SAMPLES_PER_FRAME // 2 + 1, dtype=complex)
    out[:keep] = spec[:keep]
    # rFFT magnitude scales with length; renormalize from n_src to base length.
    out *= SAMPLES_PER_FRAME / n_src
    return np.fft.irfft(out, n=SAMPLES_PER_FRAME)


def render_oversampled(
    fn,
    oversample: int = 8,
    max_harmonic: int = MAX_HARMONIC,
) -> np.ndarray:
    """Render a phase->amplitude function ``fn`` over one period at high
    resolution, then band-limit it back to a clean single cycle. ``fn`` receives
    the oversampled phase axis (radians) and returns an array of the same shape.
    """
    n_hi = SAMPLES_PER_FRAME * int(oversample)
    hi = np.asarray(fn(phase_axis(n_hi)), dtype=float)
    return bandlimit(hi, max_harmonic=max_harmonic)


# --------------------------------------------------------------------------
# Canonical band-limited waveforms (harmonic recipes).
# --------------------------------------------------------------------------
def _sine_phases(k: int) -> np.ndarray:
    # cos(x - pi/2) == sin(x): turn the cosine basis into a sine series.
    return np.full(k, -np.pi / 2.0)


def sine() -> np.ndarray:
    """Pure fundamental: ``sin(theta)`` over one period."""
    return from_harmonics([0.0, 1.0], _sine_phases(2))


def saw(n_harmonics: int = MAX_HARMONIC) -> np.ndarray:
    """Band-limited sawtooth: a_k = 1/k for k = 1..H (sine series)."""
    h = min(n_harmonics, MAX_HARMONIC)
    amps = np.zeros(h + 1)
    k = np.arange(1, h + 1)
    amps[1:] = 1.0 / k
    return from_harmonics(amps, _sine_phases(h + 1))


def square(n_harmonics: int = MAX_HARMONIC) -> np.ndarray:
    """Band-limited square: odd harmonics, a_k = 1/k (sine series)."""
    h = min(n_harmonics, MAX_HARMONIC)
    amps = np.zeros(h + 1)
    k = np.arange(1, h + 1)
    odd = k % 2 == 1
    amps[1:][odd] = 1.0 / k[odd]
    return from_harmonics(amps, _sine_phases(h + 1))


def triangle(n_harmonics: int = MAX_HARMONIC) -> np.ndarray:
    """Band-limited triangle: odd harmonics, a_k = 1/k^2 with alternating
    sign (sine series)."""
    h = min(n_harmonics, MAX_HARMONIC)
    amps = np.zeros(h + 1)
    phases = _sine_phases(h + 1)
    k = np.arange(1, h + 1)
    odd = k % 2 == 1
    amps[1:][odd] = 1.0 / (k[odd] ** 2)
    # alternating sign on successive odd harmonics -> flip phase by pi
    sign_flip = ((k[odd] - 1) // 2) % 2 == 1
    idx = np.nonzero(odd)[0] + 1
    phases[idx[sign_flip]] += np.pi
    return from_harmonics(amps, phases)


def pulse(duty: float = 0.5, n_harmonics: int = MAX_HARMONIC) -> np.ndarray:
    """Band-limited pulse of the given duty cycle in (0, 1)."""
    h = min(n_harmonics, MAX_HARMONIC)
    duty = float(np.clip(duty, 1e-3, 1.0 - 1e-3))
    k = np.arange(1, h + 1)
    amps = np.zeros(h + 1)
    amps[1:] = (2.0 / (k * np.pi)) * np.sin(np.pi * k * duty)
    return from_harmonics(np.abs(amps), _sine_phases(h + 1) + np.where(amps < 0, np.pi, 0.0))


# --------------------------------------------------------------------------
# Conditioning helpers (used by generators and by write.py before the gates).
# --------------------------------------------------------------------------
def remove_dc(cycle: np.ndarray) -> np.ndarray:
    """Subtract the mean so DC is exactly zero."""
    cycle = np.asarray(cycle, dtype=float)
    return cycle - cycle.mean()


def normalize_peak(cycle: np.ndarray, target: float = 1.0) -> np.ndarray:
    """Scale so the maximum absolute sample equals ``target``."""
    cycle = np.asarray(cycle, dtype=float)
    peak = np.max(np.abs(cycle))
    if peak < 1e-12:
        return cycle
    return cycle * (target / peak)


def normalize_rms(cycle: np.ndarray, target: float = 0.5) -> np.ndarray:
    """Scale so the RMS equals ``target``."""
    cycle = np.asarray(cycle, dtype=float)
    rms = np.sqrt(np.mean(cycle**2))
    if rms < 1e-12:
        return cycle
    return cycle * (target / rms)


def rms(cycle: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(cycle, dtype=float) ** 2)))


def magnitude_spectrum(cycle: np.ndarray) -> np.ndarray:
    """Harmonic magnitude spectrum (index 0 = DC) of a single cycle, scaled to
    cosine amplitudes so harmonic ``k`` reads its true amplitude."""
    cycle = np.asarray(cycle, dtype=float)
    n = cycle.shape[0]
    spec = np.abs(np.fft.rfft(cycle)) * (2.0 / n)
    spec[0] /= 2.0
    if n % 2 == 0:
        spec[-1] /= 2.0
    return spec
