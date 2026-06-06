"""The single validated write path.

Bytes reach out/ ONLY through this module. It runs the Layer-1 quality gates and
refuses to write a failing table, so every generated table is valid no matter
which client pulled the lever, and the check cannot be skipped. Each write also
records the catalog entry (generator, resolved params, seed, features,
morph_dims) for byte-for-byte reproducibility.

SCAFFOLD STATE: not yet implemented (Run 1, milestone 3)."""

from __future__ import annotations
