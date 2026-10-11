// Web Audio step sequencer: drum buses (each with sample layers) + a bass bus with pitched notes.
// Mirrors clustersound/patterns/render.py so what you hear is what gets exported.

const TICK_MS = 25;
const LOOKAHEAD = 0.12;
export const velGain = (v) => Math.pow(v / 127, 1.5);

// 32-bit hash for the random layer alternation: bit-identical to model.alt_hash() in Python
export function altHash(seed, i) {
  let x = (Math.imul(seed >>> 0, 2654435761) + Math.imul(i, 40503)) >>> 0;
  x = (x ^ (x >>> 16)) >>> 0;
  x = Math.imul(x, 0x45d9f3b) >>> 0;
  return (x ^ (x >>> 16)) >>> 0;
}

export function refKey(ref) {
  if (!ref) return '';
  return ref.kind === 'online' ? `online:${ref.url}` : `${ref.kind}:${ref.path}`;
}

export class Sequencer {
  constructor({ player, fetchAudio, onStep }) {
    this.player = player;
    this.fetchAudio = fetchAudio; // ref -> data URL
    this.onStep = onStep;
    this.buffers = new Map();
    this.loading = new Map();
    this.p = null;
    this.playing = false;
    this.nodes = {};
    this.voices = new Set();
    this.openHats = [];
  }

  _choke(when) {
    // only open hats that started before this closed hat (others are scheduled later in the look-ahead)
    const keep = [];
    for (const h of this.openHats) {
      if (h.start < when) { try { h.src.stop(Math.max(when, this.ctx.currentTime)); } catch (e) { /* done */ } }
      else keep.push(h);
    }
    this.openHats = keep;
  }

  get ctx() { return this.player._ensure(); }

  // ---------------------------------------------------------------- graph
  _graph() {
    if (this.master) return;
    const ctx = this.ctx;
    this.master = ctx.createGain();
    this.master.gain.value = 0.9;
    this.limiter = ctx.createDynamicsCompressor();
    this.limiter.threshold.value = -3;
    this.limiter.ratio.value = 12;
    this.limiter.attack.value = 0.002;
    this.limiter.release.value = 0.1;
    this.master.connect(this.limiter).connect(ctx.destination);
  }

  _bus(id) {
    this._graph();
    if (this.nodes[id]) return this.nodes[id];
    const ctx = this.ctx;
    const n = {
      input: ctx.createGain(), hp: ctx.createBiquadFilter(), lp: ctx.createBiquadFilter(),
      gain: ctx.createGain(), pan: ctx.createStereoPanner(), meter: ctx.createAnalyser(),
    };
    n.hp.type = 'highpass'; n.hp.frequency.value = 10; n.hp.Q.value = Math.SQRT1_2;
    n.lp.type = 'lowpass'; n.lp.frequency.value = 22000; n.lp.Q.value = Math.SQRT1_2;
    n.meter.fftSize = 256;
    n.input.connect(n.hp).connect(n.lp).connect(n.gain).connect(n.pan).connect(this.master);
    n.pan.connect(n.meter);
    this.nodes[id] = n;
    return n;
  }

  updateMix() {
    if (!this.p) return;
    const t = this.ctx.currentTime;
    for (const [id, b] of Object.entries(this.p.buses)) {
      const n = this._bus(id);
      n.gain.gain.setTargetAtTime(b.volume, t, 0.01);
      n.pan.pan.setTargetAtTime(b.pan || 0, t, 0.01);
      n.hp.frequency.setTargetAtTime(b.hp || 10, t, 0.01);
      n.lp.frequency.setTargetAtTime(b.lp || 22000, t, 0.01);
    }
  }

  level(id) {
    const n = this.nodes[id];
    if (!n) return 0;
    const buf = new Float32Array(n.meter.fftSize);
    n.meter.getFloatTimeDomainData(buf);
    let peak = 0;
    for (const v of buf) peak = Math.max(peak, Math.abs(v));
    return peak;
  }

  // ---------------------------------------------------------------- samples
  async load(ref) {
    const key = refKey(ref);
    if (!key) return null;
    if (this.buffers.has(key)) return this.buffers.get(key);
    if (this.loading.has(key)) return this.loading.get(key);
    const job = (async () => {
      const url = await this.fetchAudio(ref);
      if (!url) return null;
      const b64 = url.slice(url.indexOf(',') + 1);
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      try { return await this.ctx.decodeAudioData(bytes.buffer); } catch (e) { return null; }
    })();
    this.loading.set(key, job);
    const buf = await job;
    this.loading.delete(key);
    if (buf) this.buffers.set(key, buf);
    return buf;
  }

  async preload(p) {
    const refs = [];
    for (const b of Object.values(p.buses)) for (const l of b.layers) if (l.ref) refs.push(l.ref);
    await Promise.all(refs.map((r) => this.load(r)));
  }

  audition(ref, semitones = 0, bus = null) {
    const buf = this.buffers.get(refKey(ref));
    if (!buf) return this.load(ref).then((b) => b && this.audition(ref, semitones, bus));
    this._graph();
    const t = this.ctx.currentTime + 0.01;
    this._voice(buf, bus ? this._bus(bus).input : this.master, t, 1, Math.pow(2, semitones / 12));
  }

  _voice(buf, dest, when, gain, rate, stopAt = null) {
    const ctx = this.ctx;
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.playbackRate.value = rate;
    const g = ctx.createGain();
    g.gain.value = gain;
    src.connect(g).connect(dest);
    src.start(Math.max(when, ctx.currentTime));
    if (stopAt !== null) {
      g.gain.setValueAtTime(gain, Math.max(stopAt - 0.01, when));
      g.gain.linearRampToValueAtTime(0, stopAt);
      src.stop(stopAt + 0.01);
    }
    this.voices.add(src);
    src.onended = () => this.voices.delete(src);
    return src;
  }

  // ---------------------------------------------------------------- transport
  setPattern(p) { this.p = p; this.updateMix(); }

  // at: AudioContext time of the first step (to start in sync with another transport)
  start(fromStep = 0, at = null) {
    if (this.playing || !this.p) return;
    this.ctx.resume();
    this._graph();
    this.updateMix();
    this.playing = true;
    this.step = fromStep % (this.p.bars * 16);
    this.loop = 0; // loops played since start ('random_pass' alternation re-draws on every loop)
    this.nextTime = at ?? this.ctx.currentTime + 0.06;
    this.timer = setInterval(() => this._tick(), TICK_MS);
    this._tick();
  }

  stop() {
    this.playing = false;
    clearInterval(this.timer);
    for (const v of this.voices) { try { v.stop(); } catch (e) { /* ended */ } }
    this.voices.clear();
    if (this.onStep) this.onStep(-1);
  }

  stepDur() { return 60 / this.p.bpm / 4; }

  // swing of a step: per bar in sequences (each block keeps its own swing)
  swingOf(step) {
    const sb = this.p.swing_bars;
    return sb && sb.length ? sb[Math.min(sb.length - 1, Math.floor(step / 16))] : this.p.swing;
  }

  _tick() {
    if (!this.playing) return;
    const n = this.p.bars * 16;
    while (this.nextTime < this.ctx.currentTime + LOOKAHEAD) {
      const i = this.step % n;
      const swing = i % 2 === 1 ? (this.swingOf(i) / 100 * 2 - 1) * this.stepDur() : 0;
      this._schedule(i, this.nextTime + swing);
      const delay = Math.max(0, (this.nextTime + swing - this.ctx.currentTime) * 1000);
      if (this.onStep) setTimeout(() => this.playing && this.onStep(i), delay);
      this.nextTime += this.stepDur();
      this.step = (i + 1) % n;
      if (this.step === 0) this.loop++;
    }
  }

  _audible() {
    const ids = Object.keys(this.p.buses);
    const solo = ids.filter((id) => this.p.buses[id].solo);
    return (solo.length ? solo : ids).filter((id) => !this.p.buses[id].mute);
  }

  _layers(bus) {
    const ls = bus.layers.filter((l) => l.ref);
    const solo = ls.filter((l) => l.solo);
    return (solo.length ? solo : ls).filter((l) => !l.mute);
  }

  // Layers sounding on step i: all of them, or one of the shared-step layers when the bus alternates
  // (same rules as model.bus_hits in Python).
  _playing(bus, i) {
    const layers = this._layers(bus);
    const mode = bus.alt?.mode || 'off';
    const shared = layers.filter((l) => !l.steps);
    if (mode === 'off' || shared.length < 2 || !bus.steps[i]) return layers;
    const n = shared.length;
    let pick;
    if (mode === 'cycle') {
      let hit = 0;
      for (let k = 0; k < i; k++) if (bus.steps[k]) hit++;
      pick = hit % n;
    } else {
      pick = altHash(bus.alt.seed || 0, mode === 'random_pass' ? i + this.loop * this.p.bars * 16 : i) % n;
    }
    return [...layers.filter((l) => l.steps), shared[pick]];
  }

  _schedule(i, t) {
    const sd = this.stepDur();
    for (const id of this._audible()) {
      const bus = this.p.buses[id];
      const dest = this._bus(id).input;
      if (id === 'bass') { this._scheduleBass(bus, i, t, dest); continue; }
      for (const layer of this._playing(bus, i)) {
        const steps = layer.steps || bus.steps;
        const v = steps[i];
        if (!v) continue;
        const buf = this.buffers.get(refKey(layer.ref));
        if (!buf) continue;
        const r = bus.ratchet[i] || 1;
        const rate = Math.pow(2, (layer.pitch || 0) / 12);
        const off = (layer.offset_ms || 0) / 1000;
        if (id === 'chat') this._choke(t + off); // closed hat cuts the open hat (same choke group as the Drum Rack)
        for (let k = 0; k < r; k++) {
          const vel = Math.max(1, Math.floor(v * (1 - 0.12 * k)));
          const at = t + off + (k * sd) / r;
          const src = this._voice(buf, dest, at, velGain(vel) * layer.volume, rate);
          if (id === 'ohat') this.openHats.push({ src, start: at });
        }
      }
    }
  }

  bassSemis(layer, semi) {
    const root = 12 * (this.p.octave + 1) + this.noteIndex(this.p.key);
    const sampleRoot = layer.root ?? root;
    return root + semi - sampleRoot + (layer.pitch || 0);
  }

  noteIndex(key) {
    const flats = { Db: 'C#', Eb: 'D#', Gb: 'F#', Ab: 'G#', Bb: 'A#' };
    return ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'].indexOf(flats[key] || key);
  }

  _scheduleBass(bus, i, t, dest) {
    const notes = [...bus.notes].sort((a, b) => a.step - b.step);
    const sd = this.stepDur();
    // bassShift (optional, e.g. the Compose tab): semitones for an absolute step, so the bass follows chords
    const shift = this.bassShift ? this.bassShift(this.loop * this.p.bars * 16 + i) : 0;
    const swingAt = (s) => (s % 2 === 1 ? (this.swingOf(s) / 100 * 2 - 1) * sd : 0);
    notes.forEach((nt, idx) => {
      if (nt.step !== i) return;
      const prev = notes[idx - 1];
      if (prev && prev.glide && prev.step + prev.len >= nt.step) return; // reached by a glide
      // follow the glide chain
      const chain = [nt];
      while (chain[chain.length - 1].glide && notes[notes.indexOf(chain[chain.length - 1]) + 1]) {
        const nx = notes[notes.indexOf(chain[chain.length - 1]) + 1];
        if (nx.step > chain[chain.length - 1].step + chain[chain.length - 1].len) break;
        chain.push(nx);
      }
      const last = chain[chain.length - 1];
      const end = t + (last.step + last.len - nt.step) * sd + swingAt(last.step + last.len) - swingAt(nt.step);
      for (const layer of this._layers(bus)) {
        const buf = this.buffers.get(refKey(layer.ref));
        if (!buf) continue;
        const src = this._voice(buf, dest, t + (layer.offset_ms || 0) / 1000,
          velGain(nt.vel || 100) * layer.volume, Math.pow(2, this.bassSemis(layer, nt.semi + shift) / 12), end);
        let rate = Math.pow(2, this.bassSemis(layer, nt.semi + shift) / 12);
        for (const nx of chain.slice(1)) {
          const at = t + (nx.step - nt.step) * sd + swingAt(nx.step) - swingAt(nt.step);
          const next = Math.pow(2, this.bassSemis(layer, nx.semi + shift) / 12);
          src.playbackRate.setValueAtTime(rate, Math.max(t, at - 0.06));
          src.playbackRate.exponentialRampToValueAtTime(next, at);
          rate = next;
        }
      }
    });
  }
}
