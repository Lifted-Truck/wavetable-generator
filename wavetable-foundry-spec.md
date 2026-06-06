# Wavetable Foundry — Project Specification & Build Brief

A standalone specification for `wtfoundry`: a diversity-seeking wavetable generator, built autonomously by Claude Code and operated either directly by hand or through Claude.

---

## Overview

`wtfoundry` synthesizes libraries of Serum 2–compatible wavetables across a range of distinct synthesis methods, validates each one against an objective spectral standard, and catalogs the results. It is designed around a single **control surface** with two ways to drive it:

- **Directly, by hand** — a command-line interface and an importable Python API.
- **Through Claude** — a Model Context Protocol (MCP) server exposing the same controls, so Claude can translate natural-language requests ("a gnarly, vocal-ish growl that opens up as it morphs") into parameter settings and run the tool.

Both paths pull the same levers on the same core, so their behavior cannot diverge.

The project serves two purposes at once. It produces a genuinely useful generator that replaces ad-hoc, single-method wavetable scripts. It also functions as a controlled test of fully autonomous agentic development — the tool is built by an unsupervised Claude Code session, and how that session behaves is itself an object of study.

---

## Design principles

**Autonomy is only as good as the oracle.** With no human in the loop during the build, correctness must be machine-checkable at every step. Every part of the build routes through a single verification command that passes or fails objectively; the autonomous session cannot end while it fails. This is the property that makes unsupervised building safe, and it is why a wavetable generator is a good first candidate — spectral analysis gives a hard pass/fail with no aesthetic judgment required.

**Score diversity, not conformance.** A validator that checks each table against a fixed target template pushes the whole library toward sameness — the failure mode of single-method generators, where every output is a variation on one transformation. To counter this, the oracle scores the *spread* of the library as a whole, rewarding mechanically and perceptually distinct results rather than convergence on a template.

**Define the control surface once.** The set of operations and parameters the tool exposes — the levers — is defined in exactly one place. The CLI, the Python API, the MCP server, and any future GUI are thin skins over that single definition. The lever schema (operation names, parameter names, types, descriptions) is simultaneously what the CLI maps onto and what lets Claude map language onto actions, so there is one source of truth for behavior.

**Keep the core plain.** The tool enforces quality, not policy. A single validated write path guarantees every generated table is valid regardless of which client produced it, and every generation is seeded and reproducible. There is no oversight, accountability, or curation layer — Claude is a second operator, not a supervisor.

**Contained blast radius.** The build is hermetic (no network), writes are fenced to the project directory, and the worst-case outcome is a folder of `.wav` files plus local git commits.

---

## Architecture

```
wtfoundry/
├── CLAUDE.md                  # always-loaded brief, conventions, milestone checklist
├── Makefile                   # `make verify` = the single verification command
├── presets.yaml               # generator families, sweep ranges, oracle tolerances, ceilings
├── .mcp.json                  # MCP registration (project scope) — added in run 2
├── src/wtfoundry/
│   ├── core/
│   │   ├── synth.py           # shared single-cycle synthesis primitives
│   │   ├── features.py        # perceptual feature extraction (the diversity basis)
│   │   ├── validate.py        # oracle: quality gates + diversity objective
│   │   ├── catalog.py         # catalog.json: entries, query, coverage, duplicate-finding
│   │   ├── write.py           # the single validated write path
│   │   └── export.py          # pluggable packaging (1-D Serum now; N-D later)
│   ├── generators/
│   │   ├── base.py            # Generator interface + registry
│   │   ├── additive.py  fm.py  phasedist.py  wavefold.py
│   │   ├── spectral.py  formant.py  chaotic.py   ...   # one file per family
│   ├── api.py                 # the control surface — the canonical lever set
│   ├── cli.py                 # thin human adapter over api.py
│   └── mcp_server.py          # thin Claude adapter over api.py (run 2)
├── tests/
│   ├── fixtures/              # golden tables + known-bad tables
│   └── test_*.py
└── out/                       # generated wavetables, spectrograms, catalog.json
```

`api.py` is the lever set. The CLI, MCP server, and future GUI are skins over it. The oracle, the generators, and the single write path sit below the lever set, so no client can bypass quality control or define its own behavior.

---

## The control surface (the levers)

Defined once in `api.py` as typed functions with rich docstrings — those docstrings are what let Claude map language onto pulls:

- `list_generators()` — names, one-line timbral descriptions, and parameter schemas for every registered generator. The palette.
- `generate(generator, params, morph)` — synthesize, validate, and write; returns file paths, measured features, and pass/fail. The core lever.
- `validate(path | scope)` — run the oracle on existing tables.
- `query_catalog(nearest_to | filters)` — find and compare existing tables ("like this but brighter").
- `coverage()` — where the library is dense versus sparse across timbre space.
- `render_spectrogram(path)` — produce or return a spectrogram.

Plain engineering beneath the levers:

- **One validated write path.** Bytes reach `out/` only through `write.py`, which runs the quality gates and refuses to write a failing table. Every generated table is valid no matter which client pulled the lever, and the check cannot be skipped.
- **Seeded reproducibility.** Each catalog entry records the generator, resolved parameters, and seed, so any table regenerates byte-for-byte. An optional lightweight `source` tag (`cli` / `python` / `mcp`) may be stored as catalog metadata.
- **Resource ceilings.** Batch size, total output, and runtime are bounded in `presets.yaml`.

---

## Generators

Diversity begins with mechanically distinct synthesis methods, not parameter variations of one idea.

- **Interface and registry.** Each generator family registers under a name with a typed parameter schema and a short timbral description. Target families: additive/harmonic recipes, FM/PM, phase distortion, wavefolding and other nonlinear shapers, direct spectral sculpting (inverse FFT), formant/vocal, chaotic maps, and light physical models. Aim for at least six distinct families.
- **Coordinate-first signature**, which is also the multidimensional seam:

  ```python
  def render(self, coord: Vector, params: Params) -> Frame:
      """coord ∈ [0,1]^N is the morph position; today N = 1, scalar."""
  ```

  Today `coord` is a scalar sampled at 256 points, producing one Serum frame each. The generator never assumes dimensionality.

The registry is what `list_generators()` exposes, so adding a family automatically extends both the CLI vocabulary and Claude's.

---

## The oracle

**Layer 1 — quality gates (hard, per-table, binary).** Enforced at the `write.py` boundary so every client's output is valid:

- Band-limiting / no aliasing (no energy above the intended top harmonic).
- DC offset ≈ 0.
- Loop continuity — endpoint and first-derivative discontinuity below threshold, so the single cycle wraps without a click.
- Loudness within tolerance of a target (peak or RMS).
- Format conformance — correct sample count, channel count, bit depth, and frame count.

**Layer 2 — diversity / coverage objective (library-level).** This is what prevents convergence:

- A feature vector per table: spectral centroid, spread, flatness, rolloff, odd/even harmonic ratio, harmonic-decay slope, and MFCCs.
- A spread score: mean nearest-neighbor distance in feature space, coverage of a quantized feature grid, and a near-duplicate reject (no two tables within ε).
- **Perceptual weighting.** Features are measured in a perceptually scaled space (bark/mel, perceptual loudness) so that "diverse" means *audibly* diverse rather than numerically spread but perceptually trivial. (A flat-spectral basis is a one-line alternative in `features.py`; perceptual is the default.)

Tolerances and the diversity threshold live in `presets.yaml`. The build iterates: generate a batch, extract features, find under-populated regions of timbre space, add or mutate generators and parameters to fill the gaps, and repeat until the spread target is met with every table passing the gates. The `coverage()` lever surfaces the same picture at use time.

---

## Multidimensional readiness

Two-dimensional and higher morph spaces are a later extension, made cheap now by three decisions: coordinate-first generators (above); `morph_dims` and per-axis resolution stored in `catalog.json`; and a pluggable `export.py` (Serum is 1-D, while a 2-D target is a different container or a documented flatten order). A multidimensional table is the same generators sampled on an N-D grid, producing a tensor instead of a list. The quality gates and the diversity score generalize to N dimensions without change.

---

## The two clients

**Human interface (run 1).** The Python API in `api.py` *is* the lever set: `from wtfoundry import foundry; foundry.generate(...)` runs the gate and writes the catalog automatically, ready for notebooks, scripts, and future Max/DAW glue. The CLI is a thin adapter:

```
wtfoundry generate --generator wavefold --params '...' --morph '...'
wtfoundry validate out/
wtfoundry coverage
wtfoundry generate ... --dry-run      # plan: intended actions + projected output, no write
```

**Claude interface (run 2).** `mcp_server.py` exposes the same levers as MCP tools. Claude's role is purely to translate natural language into lever pulls, so the design effort goes into the schema: the tool and parameter descriptions *are* the interface. Configuration:

- Transport: local **stdio**. Scope: **project** (`.mcp.json` at the repository root).
- Claude Code sets `CLAUDE_PROJECT_DIR` in the spawned server's environment; resolve `out/` relative to it, using a `${CLAUDE_PROJECT_DIR:-.}` default in the config.
- Stdio tools are discovered at session start, so after building, register the server and start a fresh session.
- The build produces and tests the server as ordinary code; it does not consume its own half-built server. Confirm the current MCP Python SDK / FastMCP API against the official documentation during the build.

**GUI (later, by hand).** A graphical interface plugs onto the identical lever set as a third skin. It is deferred deliberately: it has no clean headless oracle and so is poorly suited to autonomous building. It is best built by hand once the levers are stable.

---

## Build plan

The build is split into two autonomous runs with a manual listening checkpoint between them.

**Run 1 — core and human interface.** Complete when `make verify` exits 0, which requires:

- At least six generators from mechanically distinct families.
- Every table passes the Layer-1 quality gates at the `write.py` boundary.
- The library meets the Layer-2 diversity threshold with no near-duplicates.
- A spectrogram for every table.
- `catalog.json` reconciles 1:1 with files on disk and stores parameters, seed, features, and `morph_dims`.
- `api.py` and `cli.py` expose the control surface, including `--dry-run`.
- `pytest` passes, including (a) oracle tests against known-bad fixtures and (b) a test proving an invalid table cannot be written through the API or CLI.
- `README.md` documents usage, the generator families, and the oracle.

**Audition checkpoint.** After run 1, listen to the passing, diverse set in Serum. This confirms whether the diversity metric matches the ear before any second interface is built — the one assumption no amount of test-passing can verify.

**Run 2 — Claude/MCP skin.** Complete when, in addition to the above:

- `mcp_server.py` exposes the control surface as MCP tools.
- An MCP integration test drives `generate`, `validate`, and `query_catalog` and asserts the outputs pass the gates.
- `.mcp.json` is present.

---

## Development harness

These controls govern the build sessions and are separate from the finished product.

**Single verification command.** Everything routes through `make verify` so the agent, the hooks, and the operator never disagree about what "working" means:

```makefile
verify:
	pytest -q
	python -m wtfoundry.cli build --config presets.yaml
	python -m wtfoundry.cli validate out/ --strict   # quality gates + diversity
	python -m wtfoundry.cli catalog out/ --reconcile
```

Support `build --only <generator>` and golden fixtures so iteration does not regenerate the whole library each loop.

**Permission boundary** (`.claude/settings.json`). Rules evaluate in the order deny > allow > ask > default, and a deny rule cannot be overridden by anything. Local git is allowed so the agent can checkpoint its work; push and all network access are denied, because pushes are performed manually:

```json
{
  "permissions": {
    "defaultMode": "default",
    "allow": [
      "Read(**)",
      "Write(src/**)", "Write(tests/**)", "Write(out/**)",
      "Write(presets.yaml)", "Write(Makefile)", "Write(README.md)",
      "Write(CLAUDE.md)", "Write(.mcp.json)",
      "Edit(src/**)", "Edit(tests/**)",
      "Bash(python:*)", "Bash(python -m:*)", "Bash(pytest:*)", "Bash(make verify)",
      "Bash(git add:*)", "Bash(git commit:*)",
      "Bash(git status)", "Bash(git log:*)", "Bash(git diff:*)",
      "Bash(ls:*)", "Bash(cat:*)", "Bash(mkdir:*)"
    ],
    "deny": [
      "Bash(git push:*)", "Bash(rm -rf:*)", "Bash(sudo:*)",
      "Bash(curl:*)", "Bash(wget:*)", "Bash(ssh:*)", "Bash(scp:*)", "Bash(nc:*)",
      "Bash(pip install:*)", "WebFetch", "WebSearch",
      "Read(./.env)", "Read(~/.ssh/**)",
      "Write(../**)", "Write(~/**)"
    ]
  }
}
```

Pre-provision the virtual environment (`numpy scipy soundfile pyyaml matplotlib pytest mcp`) before launch so that network access stays denied throughout. Do not add `additionalDirectories`, and do not launch in a permission-bypass mode.

**Hooks** (`.claude/settings.json`). A `PostToolUse` hook matching `Write|Edit` auto-formats every file as it is written. A `Stop` hook runs `make verify` and refuses to let the session end while it fails — exit 0 allows the stop, exit 2 blocks it and feeds the failures back as the next task. This is the mechanism that makes the run safe to leave unattended.

```bash
#!/usr/bin/env bash
# .claude/hooks/gate.sh — refuse to finish until `make verify` passes.
set -uo pipefail
[ "$(jq -r '.stop_hook_active // false')" = "true" ] && exit 0   # loop guard
if make verify > /tmp/verify.log 2>&1; then
  exit 0
else
  echo "make verify failed — fix before finishing:" >&2
  tail -n 40 /tmp/verify.log >&2
  exit 2
fi
```

The `stop_hook_active` guard is essential; without it a forced-continue Stop hook can loop indefinitely.

**`CLAUDE.md`** carries the invariants so they are in context every turn: the Serum format target, the generator families and the meaning of "distinct," the two-layer oracle, the single-write-path rule, the milestone checklist, the convention that milestone commits are tagged `milestone:<n>` (the operator's push checkpoints), and the rule that `make verify` is the only definition of done.

---

## Autonomous execution with `/goal`

`/goal` is the harness-native autonomous loop. It keeps Claude working across turns until a completion condition reads as satisfied; after each turn, a separate fast evaluator model judges the transcript. The evaluator does not run tools itself, which has two consequences:

- **Name the command, not the intent.** The condition must reference a checkable command — "`make verify` exits 0 and `catalog.json` reconciles" — never a subjective description like "sounds diverse." Keep the Stop hook regardless: because the evaluator only reads the transcript, the hook is the ground-truth proof that verification actually ran clean.
- **Include a ceiling.** A turn or time cap bounds the open-ended diversity loop. `/goal` runs only in a workspace where the trust dialog has been accepted.

A starting invocation:

```
/goal Implement wtfoundry run-1 to the spec in CLAUDE.md. Done when `make verify`
exits 0 and catalog.json reconciles. Commit each milestone as `milestone:<n>`.
Halt and report if not done within <N> turns.
```

`/loop` is for recurring tasks, not this one-shot build. It has a later place as a standing job that re-runs quality control when a generator is added.

---

## Interrupting and pushing manually

Pushes to the remote are performed by hand, which means interrupting the autonomous run a few times.

Use **Esc**, not Ctrl+C. Pressing Esc once stops Claude immediately — the running tool call is canceled and Claude waits for the next instruction. (Ctrl+C can drop the session.) Pressing Esc twice rewinds to an earlier local file checkpoint, separate from git.

1. The agent commits each milestone locally as `milestone:<n>` — these are the clean push points.
2. Press **Esc** once to pause.
3. Push without leaving the session, using the `!` shell prefix at the prompt:
   ```
   !git log --oneline -8
   !git push
   ```
   (Alternatively, Ctrl+Z suspends Claude Code to the shell; run git there, then `fg` to return.)
4. Type `continue` to resume the loop. `/goal` with no arguments prints status — elapsed turns, token spend, and the latest evaluator reason.

This is safe because `git push` only sends committed history, and the Stop hook guarantees the final commit is green; a mid-run push at worst lands a work-in-progress milestone commit on the private remote. An Esc loses at most the in-flight edit, which the agent redoes.

To resume after fully exiting: `claude --continue` reopens the most recent session, or `claude --resume` opens a picker. Resuming reopens the same session and re-runs the `SessionStart` hook with source `resume`.

---

## Milestones

Each milestone ends in a `milestone:<n>` commit.

**Run 1**

1. Scaffold the repository, `Makefile`, a failing `make verify`, and the virtual environment.
2. Core synthesis primitives and `features.py` (perceptual extraction), unit-tested against golden fixtures.
3. The single validated write path (`write.py`) and the oracle (quality gates and diversity), tested against known-bad fixtures — a table that aliases, one with DC offset, one with a loop click, and two near-duplicates the diversity check must reject — plus a test proving an invalid table cannot be written through the API or CLI. This is the most important step: an oracle that never fails is worthless.
4. The `Generator` interface and registry, with the first three distinct families.
5. The remaining families up to the target count, the coverage-driven diversity loop, and a full `build`.
6. Spectrograms, `catalog.json` (parameters, seed, features, `morph_dims`), reconciliation, and the `query_catalog` and `coverage` levers.
7. The `api.py` lever set and the `cli.py` adapter with `--dry-run`; the README; a final green `make verify`.

→ Audition checkpoint.

**Run 2**

8. `mcp_server.py` exposing the control surface.
9. An MCP integration test (generate, validate, query_catalog, with outputs passing the gates); `.mcp.json`; a final green `make verify`.

---

## Evaluation

Beyond shipping the tool, the project answers several questions:

- Whether the perceptual diversity metric tracks the ear — settled at the audition checkpoint.
- Whether a diversity oracle prevents convergence or merely games the metric (numerically spread but perceptually similar), which indicates whether the feature space is right.
- Whether natural-language-to-lever-pulls feels natural through Claude once the levers are stable, or whether the schemas need richer descriptions.
- How the autonomous session behaves under interruption and inside the permission boundary — useful calibration for higher-stakes autonomous runs later.

---

## Kickoff checklist

1. Scaffold the repository; pre-provision the virtual environment; add `settings.json`, `gate.sh`, and `CLAUDE.md`.
2. Confirm two values, then record them in `CLAUDE.md`:
   - **Serum 2 format target** — recommended default: 2048 samples per frame, 32-bit float, mono, up to 256 frames per table.
   - **N**, the minimum number of mechanically distinct generator families — recommended floor: 6.
3. Accept the Claude Code workspace trust dialog. Launch run 1 with the `/goal` invocation above and a turn cap.
4. Break in with **Esc** at `milestone:` commits to push manually; resume with `continue`.
5. When run 1 is green, audition the output in Serum.
6. Launch run 2 to build the MCP skin. Register the server (`claude mcp add --scope project …` or by editing `.mcp.json`), start a fresh session, and drive the tool by natural language.
```
