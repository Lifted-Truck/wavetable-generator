"""Thin human adapter over the lever set in ``wtfoundry.api``.

The CLI defines NO behavior of its own — every subcommand maps directly onto a
lever. Usage mirrors the spec:

    wtfoundry generate --generator wavefold --params '...' --morph '...'
    wtfoundry validate out/
    wtfoundry coverage
    wtfoundry generate ... --dry-run        # plan only, no write

Plus the harness-facing commands the verification pipeline drives:

    wtfoundry build --config presets.yaml   # generate the full library
    wtfoundry catalog out/ --reconcile      # catalog reconciles 1:1 with disk

SCAFFOLD STATE: the parser is wired and dispatches, but the levers it calls are
not implemented, so every command exits non-zero. This is the intended red
state for milestone 1's failing `python verify.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from wtfoundry import foundry


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wtfoundry", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="synthesize, validate, and write one table")
    g.add_argument("--generator", required=True)
    g.add_argument("--params", default="{}", help="JSON object of parameters")
    g.add_argument("--morph", default="{}", help="JSON object describing the morph")
    g.add_argument("--seed", type=int, default=None)
    g.add_argument("--dry-run", action="store_true", help="plan only; no write")

    v = sub.add_parser("validate", help="run the oracle on existing tables")
    v.add_argument("target", help="a .wav path or a scope directory")
    v.add_argument("--strict", action="store_true", help="fail on any gate or diversity miss")

    sub.add_parser("coverage", help="report dense vs sparse regions of timbre space")

    q = sub.add_parser("query", help="find/compare existing tables")
    q.add_argument("--nearest-to", default=None)
    q.add_argument("--filters", default="{}", help="JSON object of filters")

    b = sub.add_parser("build", help="generate the full library from a config")
    b.add_argument("--config", default="presets.yaml")
    b.add_argument("--only", default=None, help="build a single generator family")

    c = sub.add_parser("catalog", help="inspect / reconcile catalog.json")
    c.add_argument("target", help="scope directory (e.g. out/)")
    c.add_argument("--reconcile", action="store_true", help="assert catalog matches disk 1:1")

    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        if args.command == "generate":
            result = foundry.generate(
                args.generator,
                json.loads(args.params),
                json.loads(args.morph),
                seed=args.seed,
                dry_run=args.dry_run,
            )
        elif args.command == "validate":
            result = foundry.validate(args.target)
            if args.strict and not result.get("passed", False):
                print(json.dumps(result, indent=2, default=str))
                print("wtfoundry: validation failed (--strict)", file=sys.stderr)
                return 1
        elif args.command == "coverage":
            result = foundry.coverage()
        elif args.command == "query":
            result = foundry.query_catalog(args.nearest_to, json.loads(args.filters))
        elif args.command == "build":
            result = foundry.build(only=args.only, progress=lambda m: print(m, file=sys.stderr))
        elif args.command == "catalog":
            raise NotImplementedError("Run 1, milestone 6: catalog reconcile")
        else:  # pragma: no cover - argparse enforces choices
            raise SystemExit(2)
    except NotImplementedError as exc:
        print(f"wtfoundry: not implemented yet: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
