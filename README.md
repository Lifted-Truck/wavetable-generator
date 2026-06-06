# wtfoundry

A diversity-seeking, oracle-validated wavetable generator that synthesizes
libraries of **Serum 2–compatible** wavetables across mechanically distinct
synthesis methods, validates each one against an objective spectral standard,
and catalogs the results.

One **control surface** (`src/wtfoundry/api.py`) is driven two ways: directly by
hand (CLI + Python API) and — later — through Claude via an MCP server. Both
paths pull the same levers on the same core, so their behavior cannot diverge.

> **Status: scaffold.** The structure, harness, and a deliberately *failing*
> `verify` are in place (milestone 1). The synthesis, oracle, and catalog are
> stubs that raise `NotImplementedError` until Run 1 implements them. See
> `CLAUDE.md` for invariants and the milestone checklist, and
> `wavetable-foundry-spec.md` for the full design.

## Quick start

```bash
# 1. Create and populate the virtual environment (one time).
python -m venv .venv
.venv\Scripts\activate          # Windows / PowerShell
# source .venv/bin/activate     # macOS / Linux
pip install -e ".[dev,mcp]"     # or: pip install -r requirements.txt && pip install -e .

# 2. Run the single verification command (the only definition of "done").
python verify.py                # `make verify` delegates here where make exists
```

At scaffold stage `verify` exits non-zero by design: `pytest` passes, but the
`build` stage hits unimplemented levers.

## The levers

Defined once in `src/wtfoundry/api.py`:

| Lever | Purpose |
|-------|---------|
| `list_generators()` | the palette — names, timbral descriptions, parameter schemas |
| `generate(generator, params, morph)` | synthesize → validate → write; the core lever |
| `validate(target)` | run the oracle on existing tables |
| `query_catalog(nearest_to, filters)` | find/compare tables ("like this but brighter") |
| `coverage()` | dense vs sparse regions of timbre space |
| `render_spectrogram(path)` | produce/return a spectrogram |

CLI (thin adapter over the levers):

```bash
wtfoundry generate --generator wavefold --params '{...}' --morph '{...}'
wtfoundry validate out
wtfoundry coverage
wtfoundry generate ... --dry-run    # plan only, no write
```

## The oracle

- **Layer 1 — quality gates** (per-table, binary, enforced at the single
  `write.py` boundary): no aliasing, DC ≈ 0, loop continuity, loudness,
  format conformance.
- **Layer 2 — diversity objective** (library-level): perceptual feature vectors,
  mean nearest-neighbor spread, grid coverage, near-duplicate rejection.

Tolerances and ceilings live in `presets.yaml`.

## Layout

```
src/wtfoundry/        api.py (levers), cli.py, core/ (synth, features,
                      validate, write, catalog, export), generators/
tests/                unit tests + fixtures (golden / known-bad)
out/                  generated wavetables, spectrograms, catalog.json
verify.py / Makefile  the single verification command
presets.yaml          families, sweep ranges, tolerances, ceilings
CLAUDE.md             always-loaded invariants + milestone checklist
```
