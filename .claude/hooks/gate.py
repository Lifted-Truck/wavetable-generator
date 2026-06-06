#!/usr/bin/env python
"""Stop hook — refuse to finish until verification passes.

Cross-platform replacement for the spec's bash `gate.sh` (no bash, no jq, no
/tmp). Reads the hook payload on stdin, runs `python verify.py`, and:

  - exits 0 to allow the stop when verify passes;
  - exits 2 to BLOCK the stop when it fails, feeding the tail of the log back as
    the next task (Claude Code treats hook stderr on exit 2 as the reason).

A `stop_hook_active` guard prevents an infinite forced-continue loop.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
LOG = PROJECT_DIR / "verify.log"


def main() -> int:
    # Loop guard: if we are already inside a Stop-hook-triggered continuation,
    # let it stop to avoid looping indefinitely.
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if payload.get("stop_hook_active"):
        return 0

    with LOG.open("w", encoding="utf-8") as fh:
        result = subprocess.run(
            [sys.executable, "verify.py"],
            cwd=PROJECT_DIR,
            stdout=fh,
            stderr=subprocess.STDOUT,
        )

    if result.returncode == 0:
        return 0

    log_text = LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = "\n".join(log_text[-40:])
    print("`python verify.py` failed - fix before finishing:\n" + tail, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
