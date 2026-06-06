"""Scaffold sanity checks.

These prove the package is importable and the lever set / registry are wired,
without asserting any synthesis behavior yet. As Run 1 implements each piece,
this file is replaced by real unit tests (oracle vs known-bad fixtures, the
"invalid table cannot be written" test, etc.) per the milestone checklist.
"""

from __future__ import annotations


def test_package_imports():
    import wtfoundry

    assert wtfoundry.__version__


def test_foundry_exposes_levers():
    from wtfoundry import foundry

    for lever in (
        "list_generators",
        "generate",
        "validate",
        "query_catalog",
        "coverage",
        "render_spectrogram",
    ):
        assert callable(getattr(foundry, lever))


def test_registry_is_populated():
    # Milestone 4+ registers the generator families.
    from wtfoundry.generators import registry

    assert len(registry) >= 3
