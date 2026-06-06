"""Generator interface + registry.

The coordinate-first signature is also the multidimensional seam: a generator
is handed a morph position ``coord`` in [0,1]^N and returns one single-cycle
Frame. Today N = 1 and ``coord`` is a scalar sampled at 256 points, producing
one Serum frame each — but the generator never assumes dimensionality, so the
same code samples an N-D grid later without change.

SCAFFOLD STATE: the interface and an empty registry are declared; no families
are registered yet (Run 1, milestone 4 adds the first three)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np

# A morph coordinate in [0,1]^N (today N == 1). A Frame is one single-cycle
# waveform as a float array. Params is a resolved, validated parameter dict.
Vector = np.ndarray
Frame = np.ndarray
Params = dict[str, Any]


@runtime_checkable
class Generator(Protocol):
    """A synthesis family. Registers under ``name`` with a ``schema`` (typed
    parameter spec) and a one-line timbral ``description``."""

    name: str
    description: str
    schema: dict[str, Any]

    def render(self, coord: Vector, params: Params) -> Frame:
        """Render one single-cycle frame at morph position ``coord``.

        ``coord`` is in [0,1]^N; today N == 1 and ``coord`` is a scalar.
        """
        ...


class _Registry:
    """The generator registry. ``list_generators()`` reads from here."""

    def __init__(self) -> None:
        self._families: dict[str, Generator] = {}

    def register(self, generator: Generator) -> Generator:
        if generator.name in self._families:
            raise ValueError(f"generator already registered: {generator.name!r}")
        self._families[generator.name] = generator
        return generator

    def get(self, name: str) -> Generator:
        return self._families[name]

    def names(self) -> list[str]:
        return sorted(self._families)

    def __len__(self) -> int:
        return len(self._families)


registry = _Registry()
