"use strict";
// wtfoundry audition synth. Loads a wavetable's exact 2048-sample frames,
// turns each frame into a Web-Audio PeriodicWave, and plays it with a small
// polyphonic keyboard. Scrubbing the morph slider swaps the live oscillators'
// wave so you can hear the table evolve while a note sustains.

const N = 2048;            // samples per frame
const A4 = 440;
const KEYMAP = { a:0, w:1, s:2, e:3, d:4, f:5, t:6, g:7, y:8, h:9, u:10, j:11, k:12 };
const WHITE = [0,2,4,5,7,9,11,12], BLACK = {1:0,3:1,6:3,8:4,10:5};

let ctx = null, master = null;
let waves = [];            // PeriodicWave per frame for the selected table
let nFrames = 0, morph = 0, octave = 3, vol = 0.5;
let entries = [];
const voices = new Map();  // midi -> {osc, gain}

// ---- WAV (float32) parsing — avoid decodeAudioData, which resamples ----------
function parseWavFloat(buf) {
  const dv = new DataView(buf);
  let off = 12, dataOff = null, dataLen = 0;
  while (off + 8 <= dv.byteLength) {
    const id = String.fromCharCode(dv.getUint8(off), dv.getUint8(off+1), dv.getUint8(off+2), dv.getUint8(off+3));
    const sz = dv.getUint32(off + 4, true);
    if (id === "data") { dataOff = off + 8; dataLen = sz; break; }
    off += 8 + sz + (sz & 1);
  }
  const n = dataLen / 4;
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) out[i] = dv.getFloat32(dataOff + i * 4, true);
  return out;
}

// ---- iterative radix-2 FFT (in place) ---------------------------------------
function fft(re, im) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = -2 * Math.PI / len, wr = Math.cos(ang), wi = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let cwr = 1, cwi = 0;
      for (let k = 0; k < len / 2; k++) {
        const ar = re[i+k], ai = im[i+k];
        const br = re[i+k+len/2] * cwr - im[i+k+len/2] * cwi;
        const bi = re[i+k+len/2] * cwi + im[i+k+len/2] * cwr;
        re[i+k] = ar + br; im[i+k] = ai + bi;
        re[i+k+len/2] = ar - br; im[i+k+len/2] = ai - bi;
        const ncwr = cwr * wr - cwi * wi; cwi = cwr * wi + cwi * wr; cwr = ncwr;
      }
    }
  }
}

function frameToWave(frame) {
  const re = new Float32Array(N), im = new Float32Array(N);
  re.set(frame);
  fft(re, im);
  const half = N / 2;
  const real = new Float32Array(half + 1), imag = new Float32Array(half + 1);
  for (let k = 0; k <= half; k++) { real[k] = (2 / N) * re[k]; imag[k] = -(2 / N) * im[k]; }
  real[0] = 0; imag[0] = 0; // no DC
  return ctx.createPeriodicWave(real, imag, { disableNormalization: false });
}

// ---- audio plumbing ---------------------------------------------------------
function enableAudio() {
  if (ctx) { ctx.resume(); return; }
  ctx = new (window.AudioContext || window.webkitAudioContext)();
  master = ctx.createGain();
  master.gain.value = vol;
  master.connect(ctx.destination);
  setStatus("ready");
  document.getElementById("enable").classList.add("on");
}

function midiToFreq(m) { return A4 * Math.pow(2, (m - 69) / 12); }

function noteOn(semi) {
  if (!ctx || !waves.length) return;
  const midi = 12 * (octave + 1) + semi; // octave selector: C{octave}
  if (voices.has(midi)) return;
  const osc = ctx.createOscillator();
  osc.setPeriodicWave(waves[morph]);
  osc.frequency.value = midiToFreq(midi);
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.0001, ctx.currentTime);
  g.gain.exponentialRampToValueAtTime(0.9, ctx.currentTime + 0.01); // soft attack
  osc.connect(g).connect(master);
  osc.start();
  voices.set(midi, { osc, gain: g });
  paintKey(semi, true);
}

function noteOff(semi) {
  const midi = 12 * (octave + 1) + semi;
  const v = voices.get(midi);
  if (!v) return;
  const t = ctx.currentTime;
  v.gain.gain.cancelScheduledValues(t);
  v.gain.gain.setValueAtTime(v.gain.gain.value, t);
  v.gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.08); // release
  v.osc.stop(t + 0.1);
  voices.delete(midi);
  paintKey(semi, false);
}

function setMorph(i) {
  morph = i;
  document.getElementById("morphLabel").textContent = `${i} / ${nFrames - 1}`;
  if (waves.length) for (const v of voices.values()) v.osc.setPeriodicWave(waves[morph]);
}

// ---- table loading ----------------------------------------------------------
async function loadTable(entry) {
  setStatus("loading…");
  const resp = await fetch("/audio/" + entry.file);
  const buf = await resp.arrayBuffer();
  const samples = parseWavFloat(buf);
  nFrames = Math.floor(samples.length / N);
  waves = [];
  for (let f = 0; f < nFrames; f++) waves.push(frameToWave(samples.subarray(f * N, f * N + N)));

  const slider = document.getElementById("morph");
  slider.max = nFrames - 1; slider.value = 0;
  setMorph(0);

  document.getElementById("selName").textContent = `${entry.generator}  ·  ${entry.file}`;
  document.getElementById("selParams").textContent =
    Object.entries(entry.params).map(([k, v]) => `${k}=${v}`).join("  ");
  if (entry.spectrogram)
    document.getElementById("spectro").src = "/spectro/" + entry.spectrogram + "?t=" + Date.now();
  renderFeatures(entry.features);
  setStatus(ctx ? "ready" : "enable audio to play");
}

function renderFeatures(feat) {
  const order = ["spectral_centroid","spectral_spread","spectral_flatness","spectral_rolloff",
                 "odd_even_ratio","harmonic_decay_slope","centroid_motion","flatness_motion"];
  const el = document.getElementById("feat");
  el.innerHTML = "";
  for (const k of order) {
    if (!(k in feat)) continue;
    const d = document.createElement("div");
    const v = feat[k];
    d.innerHTML = `<span>${k}</span><b>${Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(3)}</b>`;
    el.appendChild(d);
  }
}

// ---- UI ---------------------------------------------------------------------
function setStatus(s) { document.getElementById("status").textContent = s; }

function suspect(feat) { // the "dark + static" cluster worth scrutinizing
  return feat.spectral_centroid < 5 && feat.centroid_motion < 2;
}

function buildList() {
  const byFam = {};
  for (const e of entries) (byFam[e.generator] ||= []).push(e);
  const list = document.getElementById("list");
  list.innerHTML = "";
  for (const fam of Object.keys(byFam).sort()) {
    const h = document.createElement("div"); h.className = "fam"; h.textContent = fam;
    list.appendChild(h);
    byFam[fam].sort((a, b) => a.features.spectral_centroid - b.features.spectral_centroid);
    for (const e of byFam[fam]) {
      const row = document.createElement("div");
      row.className = "row" + (suspect(e.features) ? " suspect" : "");
      row.innerHTML = `<span class="nm">${e.file.replace(fam + "__", "").replace(".wav", "")}</span>` +
        `<span class="meta">c${e.features.spectral_centroid.toFixed(0)} · m${e.features.centroid_motion.toFixed(0)}</span>`;
      row.onclick = () => {
        document.querySelectorAll(".row").forEach(r => r.classList.remove("sel"));
        row.classList.add("sel");
        loadTable(e);
      };
      list.appendChild(row);
    }
  }
}

function buildKeyboard() {
  const kbd = document.getElementById("kbd");
  kbd.innerHTML = "";
  for (let semi = 0; semi <= 12; semi++) {
    const isBlack = semi in BLACK;
    const key = document.createElement("div");
    key.className = "key" + (isBlack ? " black" : "");
    key.dataset.semi = semi;
    const label = Object.keys(KEYMAP).find(k => KEYMAP[k] === semi);
    key.textContent = label ? label.toUpperCase() : "";
    key.addEventListener("mousedown", () => noteOn(semi));
    key.addEventListener("mouseup", () => noteOff(semi));
    key.addEventListener("mouseleave", () => noteOff(semi));
    kbd.appendChild(key);
  }
}

function paintKey(semi, down) {
  const k = document.querySelector(`.key[data-semi="${semi}"]`);
  if (k) k.classList.toggle("down", down);
}

// ---- events -----------------------------------------------------------------
document.getElementById("enable").onclick = enableAudio;
document.getElementById("vol").oninput = (e) => { vol = +e.target.value; if (master) master.gain.value = vol; };
document.getElementById("morph").oninput = (e) => setMorph(+e.target.value);
document.getElementById("octup").onclick = () => { octave = Math.min(7, octave + 1); document.getElementById("oct").textContent = octave; };
document.getElementById("octdn").onclick = () => { octave = Math.max(0, octave - 1); document.getElementById("oct").textContent = octave; };

let droneOn = false, droneSemi = 0;
document.getElementById("drone").onclick = (e) => {
  droneOn = !droneOn;
  e.target.classList.toggle("on", droneOn);
  e.target.textContent = "drone: " + (droneOn ? "on" : "off");
  if (droneOn) { enableAudio(); noteOn(droneSemi); } else { noteOff(droneSemi); }
};

window.addEventListener("keydown", (ev) => {
  if (ev.repeat) return;
  const semi = KEYMAP[ev.key.toLowerCase()];
  if (semi !== undefined) { enableAudio(); noteOn(semi); }
});
window.addEventListener("keyup", (ev) => {
  const semi = KEYMAP[ev.key.toLowerCase()];
  if (semi !== undefined) noteOff(semi);
});

// ---- boot -------------------------------------------------------------------
fetch("/catalog.json")
  .then(r => r.json())
  .then(cat => { entries = cat.entries || []; buildList(); buildKeyboard();
                 setStatus(`${entries.length} tables · click one`); })
  .catch(() => { document.getElementById("list").textContent = "could not load catalog.json — run a build first"; });
