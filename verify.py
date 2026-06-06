#!/usr/bin/env python
"""The single verification command — the one definition of "done".

`make verify` delegates here, and on platforms without `make` (e.g. Windows /
PowerShell) this script IS the canonical command:

    python verify.py

Everything routes through it so the agent, the hooks, and the operator never
disagree about what "working" means. It runs the same four stages the spec's
Makefile lists, in order, and stops at the first failure:

    1. pytest -q
    2. wtfoundry build  --config presets.yaml
    3. wtfoundry validate out/ --strict      (quality gates + diversity)
    4. wtfoundry catalog  out/ --reconcile

Exit code 0 means every stage passed; non-zero means the run is not done.

SCAFFOLD STATE: stages 2-4 invoke levers that are not implemented yet, so this
exits non-zero by design — milestone 1's failing `make verify`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _venv_python() -> str:
    """Resolve the project's virtual-env interpreter.

    The Stop hook is launched by the system `python` on PATH, which does NOT
    have the dependencies; they live in `.venv`. Routing every stage through the
    venv interpreter (rather than sys.executable) keeps verify correct no matter
    which `python` invoked this script.
    """
    for candidate in (
        _HERE / ".venv" / "Scripts" / "python.exe",  # Windows
        _HERE / ".venv" / "bin" / "python",  # POSIX
    ):
        if candidate.exists():
            return str(candidate)
    return sys.executable


PYTHON = _venv_python()

STAGES: list[tuple[str, list[str]]] = [
    ("pytest", [PYTHON, "-m", "pytest", "-q"]),
    ("build", [PYTHON, "-m", "wtfoundry.cli", "build", "--config", "presets.yaml"]),
    ("validate", [PYTHON, "-m", "wtfoundry.cli", "validate", "out", "--strict"]),
    ("catalog", [PYTHON, "-m", "wtfoundry.cli", "catalog", "out", "--reconcile"]),
]


def main() -> int:
    for name, cmd in STAGES:
        print(f"\n=== verify: {name} ===", flush=True)
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(
                f"\nverify FAILED at stage '{name}' (exit {result.returncode}).",
                file=sys.stderr,
            )
            return result.returncode
    print("\nverify OK — all stages passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
