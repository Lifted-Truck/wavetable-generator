# wtfoundry — build brief & invariants

A diversity-seeking, oracle-validated wavetable generator (Serum 2 compatible).
This file is always in context. It carries the invariants that must hold every
turn. The full rationale lives in `wavetable-foundry-spec.md`; this is the
operational summary.

## The one rule

**`make verify` is the only definition of done.** On this machine `make` is not
installed, so the canonical command is:

```
python verify.py
```

(The `Makefile` simply delegates to it.) The session may not end while it fails.
Stages, in order, stop at first failure: `pytest -q` → `wtfoundry build` →
`wtfoundry validate out --strict` → `wtfoundry catalog out --reconcile`.

`verify.py` self-routes every stage through the project venv. For ad-hoc
commands during iteration, use the venv interpreter explicitly
(`.venv\Scripts\python.exe -m pytest ...`), not the system `python`, which
lacks the dependencies.

## Confirmed values (kickoff)

- **Serum 2 format target:** 2048 samples per frame, 32-bit float, mono, up to
  256 frames per table. (Mirrored in `presets.yaml: format`.)
- **N = 6** — the minimum number of *mechanically distinct* generator families.

"Mechanically distinct" means a different synthesis method, not a parameter
variation of one idea: additive/harmonic, FM/PM, phase distortion, wavefolding /
nonlinear shaping, direct spectral sculpting (inverse FFT), formant/vocal,
chaotic maps, light physical models. Ship at least six of these.

## Architecture invariants

- **Define the control surface once.** `src/wtfoundry/api.py` is the canonical
  lever set. The CLI, the MCP server (run 2), and any future GUI are thin skins
  over it. Never add behavior to a skin — add it to the lever and let the skins
  expose it. The registry is what `list_generators()` reads, so adding a family
  extends the CLI vocabulary and Claude's at once.
- **One validated write path.** Bytes reach `out/` ONLY through
  `core/write.py`, which runs the Layer-1 gates and refuses to write a failing
  table. No client may bypass it. A test must prove an invalid table cannot be
  written through the API or the CLI.
- **Coordinate-first generators.** `render(coord: Vector, params: Params) ->
  Frame`, `coord ∈ [0,1]^N`. Today N = 1, a scalar sampled at 256 points. Never
  assume dimensionality — that is the multidimensional seam.
- **Seeded reproducibility.** Every catalog entry records generator, resolved
  params, and seed, so any table regenerates byte-for-byte. Resource ceilings
  live in `presets.yaml`.

## The two-layer oracle (`core/validate.py`)

- **Layer 1 — quality gates** (hard, per-table, binary; enforced at the
  `write.py` boundary): no aliasing, DC ≈ 0, loop continuity (endpoint + first
  derivative), loudness within tolerance, format conformance.
- **Layer 2 — diversity / coverage** (library-level): perceptual feature vector
  per table → mean nearest-neighbor distance, quantized-grid coverage, and a
  near-duplicate reject. This is what prevents convergence. Tolerances and the
  diversity threshold live in `presets.yaml`. An oracle that never fails is
  worthless — it must reject the known-bad fixtures.

## Conventions

- Each milestone ends in a commit; **tag it `milestone:<n>`** — these are the
  operator's push checkpoints. Pushes are performed by hand (push is denied to
  the build session).
- Iterate with `build --only <generator>` and golden fixtures so a loop need not
  regenerate the whole library each time.
- Format on write (ruff). Keep the core plain: the tool enforces quality, not
  policy. No oversight/curation layer.

## Milestone checklist

Run 1 (core + human interface):
1. Scaffold, Makefile/`verify.py`, failing verify, venv. ← **done (this commit)**
2. Synthesis primitives + `features.py`, unit-tested vs golden fixtures.
3. `write.py` single write path + the oracle, tested vs known-bad fixtures
   (alias, DC offset, loop click, two near-duplicates) + "invalid cannot be
   written" test. *Most important step.*
4. `Generator` interface + registry with the first three distinct families.
5. Remaining families to N=6, the coverage-driven diversity loop, full `build`.
6. Spectrograms, `catalog.json` (params, seed, features, `morph_dims`),
   reconciliation, `query_catalog` and `coverage` levers.
7. `api.py` + `cli.py` with `--dry-run`; README; final green verify.

→ Audition checkpoint (listen in Serum).

Run 2 (Claude/MCP skin):
8. `mcp_server.py` exposing the control surface.
9. MCP integration test (generate/validate/query_catalog, outputs pass gates);
   `.mcp.json`; final green verify.

## Harness / permission boundary

- `.claude/settings.json` fences writes to the project, allows local git, and
  denies push + all network. A `Stop` hook runs `python .claude/hooks/gate.py`
  and refuses to finish while verify fails (with a `stop_hook_active` loop
  guard). A `PostToolUse` hook formats files on write.
- The venv (`.venv`) is pre-provisioned so the locked-down run needs no network.
