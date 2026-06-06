"""catalog.json: entries, query, coverage, and duplicate-finding.

Each entry records generator, resolved parameters, seed, measured features, and
morph_dims. The catalog reconciles 1:1 with the files on disk (the
`catalog --reconcile` check in the verification command).

SCAFFOLD STATE: not yet implemented (Run 1, milestone 6)."""

from __future__ import annotations
