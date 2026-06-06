"""Generator interface + registry.

The coordinate-first signature is the multidimensional seam: a generator is
handed a morph position ``coord`` in [0,1]^N and returns one single-cycle frame.
Today N = 1 and ``coord`` is a scalar; ``render_table`` sweeps it across the
morph axis to build a full table. The generator never assumes dimensionality, so
the same ``render`` samples an N-D grid later without change.

Shared mechanics live here so families stay small: parameter resolution from a
typed schema, per-frame conditioning (DC removal + peak normalization so the DC
and loudness gates pass by construction), and seeded table building for
byte-for-byte reproducibility. The registry is what ``list_generators()`` reads,
so registering a family extends the CLI vocabulary and Claude's at once.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np

from wtfoundry.core import synth

Frame = np.ndarray
Params = dict[str, Any]

LOUDNESS_TARGET = 0.9  # matches presets gates.loudness.target


@dataclass(frozen=True)
class ParamSpec:
    """One typed, range-bounded parameter. The docstring-grade ``description``
    is what lets a human and Claude alike understand the lever."""

    name: str
    default: float
    lo: float
    hi: float
    description: str
    kind: str = "float"  # "float" | "int"

    def clip(self, value: Any) -> float | int:
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = float(self.default)
        v = min(max(v, self.lo), self.hi)
        return int(round(v)) if self.kind == "int" else v

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.kind,
            "default": self.default,
            "min": self.lo,
            "max": self.hi,
            "description": self.description,
        }


class Generator(ABC):
    """A synthesis family. Subclasses set ``name``, ``description`` and a
    ``params`` schema, and implement ``render``."""

    name: str = ""
    description: str = ""
    params: tuple[ParamSpec, ...] = ()
    # Stochastic families draw from self.rng, so different seeds yield different
    # tables; the build varies the seed for these and not for deterministic ones.
    stochastic: bool = False

    # ---- introspection -------------------------------------------------
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "params": [p.to_dict() for p in self.params],
        }

    def resolve(self, user: Params | None) -> Params:
        """Fill defaults and clip every parameter to its declared range. Unknown
        keys are ignored so a client cannot inject behavior."""
        user = user or {}
        return {p.name: p.clip(user.get(p.name, p.default)) for p in self.params}

    # ---- synthesis -----------------------------------------------------
    @abstractmethod
    def render(self, coord: float, params: Params) -> Frame:
        """Render one single-cycle frame (band-limited, un-normalized) at morph
        position ``coord`` in [0, 1]. Stochastic families draw from ``self.rng``."""

    def intended_max_harmonic(self, params: Params) -> int:
        """The top harmonic this table claims to occupy, checked by the aliasing
        gate. Defaults to the full band."""
        return synth.MAX_HARMONIC

    def finalize(self, frame: Frame) -> Frame:
        """Condition a raw frame so the DC and loudness gates pass: remove DC,
        normalize to the peak target."""
        return synth.normalize_peak(synth.remove_dc(frame), LOUDNESS_TARGET)

    @property
    def rng(self) -> np.random.Generator:
        return getattr(self, "_rng", None) or np.random.default_rng(0)

    def render_table(
        self,
        params: Params | None = None,
        n_frames: int = 256,
        seed: int | None = None,
    ) -> np.ndarray:
        """Sweep ``coord`` across ``n_frames`` points and stack the conditioned
        frames into a table. Deterministic given (params, n_frames, seed)."""
        resolved = self.resolve(params)
        self._rng = np.random.default_rng(seed)
        coords = np.linspace(0.0, 1.0, n_frames)
        frames = [self.finalize(self.render(float(c), resolved)) for c in coords]
        return np.asarray(frames, dtype=float)


class _Registry:
    """The generator registry. ``list_generators()`` reads from here."""

    def __init__(self) -> None:
        self._families: dict[str, Generator] = {}

    def register(self, generator: Generator) -> Generator:
        if not generator.name:
            raise ValueError("generator must declare a name")
        if generator.name in self._families:
            raise ValueError(f"generator already registered: {generator.name!r}")
        self._families[generator.name] = generator
        return generator

    def get(self, name: str) -> Generator:
        if name not in self._families:
            raise KeyError(f"unknown generator: {name!r}; have {self.names()}")
        return self._families[name]

    def names(self) -> list[str]:
        return sorted(self._families)

    def all(self) -> list[Generator]:
        return [self._families[n] for n in self.names()]

    def schemas(self) -> list[dict[str, Any]]:
        return [g.schema() for g in self.all()]

    def __len__(self) -> int:
        return len(self._families)


registry = _Registry()


def register(cls: type[Generator]) -> type[Generator]:
    """Class decorator: instantiate a generator and add it to the registry."""
    registry.register(cls())
    return cls
