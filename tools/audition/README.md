# Audition synth (dev tool)

A tiny in-browser wavetable synth for the Run-1 audition checkpoint — hear the
generated library without Serum. **Not part of the product or `verify.py`.** It
is a read-only "third skin": it serves `out/` (catalog, wav tables,
spectrograms) and plays them with the Web Audio API.

## Run

```powershell
python -m wtfoundry.cli build          # populate out/ first
python tools/audition/server.py        # opens http://localhost:8731
```

## Use

- Click a table in the left list (grouped by family; the orange ● marks the
  "dark + static" cluster worth scrutinizing).
- Click **enable audio**, then hold a key — on-screen, or the computer keys
  `A W S E D F T G Y H U J K` (one octave). Use **octave ± / vol**.
- **Scrub the morph slider while a note sustains** — the oscillator's wave is
  swapped live, so you hear the table evolve. Toggle **drone** to hold a note
  hands-free while you scrub.
- The morph spectrogram and measured features for the selected table are shown
  below the keyboard.

## How it works

The browser fetches each table's `.wav`, parses the exact 32-bit-float
2048-sample frames (no `decodeAudioData`, which would resample), and turns each
frame into a `PeriodicWave` via an FFT. Playing a note is a band-limited
`OscillatorNode`; scrubbing morph calls `setPeriodicWave` on the live voices.
