#!/usr/bin/env python
"""PostToolUse hook — auto-format every Python file as it is written.

Cross-platform stand-in for the spec's bash formatter. Reads the tool payload on
stdin, extracts the edited file path, and runs `ruff format` (then a safe
autofix pass) on it if it is a .py file. Always exits 0 — formatting is
best-effort and must never block a write. No-ops silently if ruff is absent.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _edited_path(payload: dict) -> str | None:
    ti = payload.get("tool_input") or {}
    return ti.get("file_path") or ti.get("path")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    path = _edited_path(payload)
    if not path or not path.endswith(".py") or not Path(path).exists():
        return 0

    for cmd in (
        [sys.executable, "-m", "ruff", "format", path],
        [sys.executable, "-m", "ruff", "check", "--fix", "--quiet", path],
    ):
        try:
            subprocess.run(cmd, capture_output=True)
        except Exception:
            return 0  # ruff not installed / unavailable — best-effort only
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
