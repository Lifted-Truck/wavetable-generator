# wtfoundry

A diversity-seeking, oracle-validated wavetable generator. It synthesizes
libraries of **Serum 2–compatible** wavetables across mechanically distinct
synthesis methods, validates every table against an objective spectral standard,
and catalogs the results.

One **control surface** (`src/wtfoundry/api.py`) is driven two ways: directly by
hand (CLI + Python API) and — in run 2 — through Claude via an MCP server. Both
paths pull the same levers on the same core, so their behavior cannot diverge.

> **Status: Run 1 complete.** `python verify.py` is green end-to-end. Six
> generator families, the two-layer oracle, the single validated write path, a
> coverage-driven build, spectrograms, and a reconciling `catalog.json` are all
> in place. The MCP skin (run 2) is not built yet. See `CLAUDE.md` for the
> invariants and `wavetable-foundry-spec.md` for the full design.

## Quick start

```powershell
# 1. Create and populate the virtual environment (one time).
python -m venv .venv
.venv\Scripts\activate                 # Windows / PowerShell
pip install -e ".[dev]"                # runtime + dev tooling

# 2. Run the single verification command — the only definition of "done".
python verify.py                       # `make verify` delegates here where make exists

# 3. Build a library and look at it.
python -m wtfoundry.cli build          # writes out/*.wav, out/*.png, out/catalog.json
python -m wtfoundry.cli coverage       # where the library is dense vs sparse
```

The deps (`numpy scipy soundfile pyyaml matplotlib`, plus `pytest ruff`) are
pinned in `requirements.txt` / `pyproject.toml`. The canonical command is
`python verify.py`; it runs, in order and stopping at the first failure:
`pytest` → `wtfoundry build` → `wtfoundry validate out --strict` →
`wtfoundry catalog out --reconcile`.

## The control surface (the levers)

Defined once in `src/wtfoundry/api.py`; the CLI is a thin adapter.

| Lever | Purpose |
|-------|---------|
| `list_generators()` | the palette — names, timbral descriptions, parameter schemas |
| `generate(generator, params, morph, seed, dry_run)` | synthesize → validate → write → catalog; the core lever |
| `build(only=None)` | render the candidate pool and select a maximally-spread library |
| `validate(target)` | run the oracle on a table or a scope directory |
| `query_catalog(nearest_to, filters)` | find/compare tables ("like this but brighter") |
| `coverage()` | dense vs sparse regions of timbre space |
| `render_spectrogram(path)` | render a morph spectrogram PNG |
| `reconcile(scope)` | assert `catalog.json` matches the wavs on disk 1:1 |

```powershell
wtfoundry generate --generator wavefold --params '{"fold":7}' --morph '{"n_frames":256}'
wtfoundry generate --generator fm --params '{"ratio":3}' --dry-run   # plan only, no write
wtfoundry build --only spectral        # iterate on one family
wtfoundry validate out --strict
wtfoundry catalog out --reconcile
```

## Generators

Diversity begins with **mechanically distinct** synthesis methods, not parameter
variations of one idea. Six families ship; each is coordinate-first
(`render(coord ∈ [0,1]^N, params)`) and opens or evolves across the morph:

| Family | Method | Character |
|--------|--------|-----------|
| `additive` | directly-written harmonic series with spectral tilt | brightness opens as it morphs |
| `fm` | two-operator phase modulation (Bessel sidebands) | index blooms from pure tone to dense FM |
| `wavefold` | sinusoidal wavefolder (memoryless non-linearity) | metallic, fold depth grows |
| `phasedist` | Casio-CZ phase distortion (re-indexed waveshape) | saw/resonant, knee deepens |
| `spectral` | inverse-FFT spectral sculpting, randomized phases | glassy clusters sweeping the band |
| `formant` | source-filter vocal formants | glides between two vowels |

Adding a family is a single file plus a registry entry; it extends the CLI
vocabulary and Claude's at once. Parameter sweeps for the build live in
`presets.yaml`.

## The oracle

**Layer 1 — quality gates** (per-table, binary, enforced at the single
`write.py` boundary; an invalid table cannot reach disk through any client):

- **no aliasing** — energy above the intended top harmonic is below threshold
- **DC ≈ 0**
- **loop continuity** — scale-invariant wrap-point value/slope jumps (no click)
- **loudness** — peak within tolerance of the target
- **format conformance** — sample/frame counts, channels, finiteness

Inverse-FFT synthesis gives no-aliasing, exact loop continuity, and exact DC
removal by construction; non-linear families (FM, wavefold, phasedist) are
band-limited by oversampled resynthesis.

**Layer 2 — diversity / coverage** (library-level — the thing that prevents
convergence):

- a perceptual feature vector per table (spectral centroid, spread, flatness,
  rolloff, odd/even ratio, harmonic-decay slope, MFCCs, plus morph motion),
  measured in a mel-scaled space
- mean nearest-neighbor distance, 2-D PCA grid coverage, and a near-duplicate
  reject (no two tables within ε)

Tolerances and thresholds live in `presets.yaml`. The oracle is proven by its
known-bad fixtures: it must reject an aliased table, a DC-offset table, a
loop-click table, and a pair of near-duplicates (`tests/test_oracle.py`).

## Catalog & reproducibility

`build` selects a diverse subset of the candidate pool by farthest-point
sampling in feature space and writes, for each table, a `.wav`, a spectrogram
`.png`, and an entry in `out/catalog.json` recording the generator, resolved
params, seed, `morph_dims` + per-axis resolution, intended top harmonic, and
measured features. Every table therefore regenerates byte-for-byte, and the
catalog reconciles 1:1 with the files on disk.

## Layout

```
src/wtfoundry/
  api.py            the lever set (single source of behavior)
  cli.py            thin human adapter
  core/
    synth.py        band-limited single-cycle primitives (inverse-rFFT engine)
    features.py     perceptual feature extraction
    validate.py     the two-layer oracle
    write.py        the single validated write path  ->  export.py (Serum packaging)
    build.py        the coverage-driven diversity build loop
    catalog.py      catalog.json: entries, reconcile, query, coverage
    spectro.py      morph spectrograms
    config.py       loads tunables from presets.yaml
  generators/       base interface + registry, one file per family
tests/              unit tests + golden / known-bad fixtures
out/                generated wavetables, spectrograms, catalog.json
verify.py / Makefile   the single verification command
presets.yaml        format target, sweeps, gate tolerances, diversity thresholds, ceilings
CLAUDE.md           always-loaded invariants + milestone checklist
```

## Multidimensional readiness

Generators are coordinate-first and never assume dimensionality; `catalog.json`
stores `morph_dims` and per-axis resolution; and packaging is isolated in
`export.py`. A 2-D+ morph is the same generators sampled on an N-D grid — the
quality gates and the diversity score generalize without change.
