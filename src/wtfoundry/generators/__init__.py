"""Generator families. Diversity begins with mechanically distinct synthesis
methods, not parameter variations of one idea.

Target families (>= 6 distinct): additive/harmonic, FM/PM, phase distortion,
wavefolding / nonlinear shapers, direct spectral sculpting (inverse FFT),
formant/vocal, chaotic maps, and light physical models. One file per family.

Each family registers under a name with a typed parameter schema and a short
timbral description; the registry is what ``list_generators()`` exposes, so
adding a family automatically extends both the CLI vocabulary and Claude's."""

from wtfoundry.generators.base import Generator, registry

__all__ = ["Generator", "registry"]
