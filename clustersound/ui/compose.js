// "Compose" screen: chord progressions from a MIDI chord pack. Browse the chords of a key, place them on a
// timeline and get the next chord suggested (the harmony, in versions A, B, C…); define how the progression
// is played in a separate "Modalità" (a rhythm grid + strum / arpeggio / humanize settings, in modes 1, 2, 3…);
// generate variations of either, play it together with the Sequencer pattern and export a .mid for Ableton.
// Every harmony version also has a melody ("Melodia" view, a piano roll over the chords): it can be drawn,
// imported, generated from the chords, and a melody can be harmonised into a new version.
// Every note heard here comes from compose_render (Python), so preview and export are the same events.
import { toast, showPopover } from './sendmenu.js';
import { sendToLive } from './live.js';
import { velGain } from './sequencer.js';

const $ = (s, root = document) => root.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const clone = (o) => JSON.parse(JSON.stringify(o));
const uid = () => 'k' + Math.random().toString(36).slice(2, 9);
const LS_KEY = 'clustersound.compose';
const DRAG_TYPE = 'text/plain';
const PPQ = 480;
const STEP_TICKS = PPQ / 4;
const SHARPS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const FLATS = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];
const PC = Object.fromEntries([...SHARPS.map((n, i) => [n, i]), ...FLATS.map((n, i) => [n, i])]);
const FLAT_KEYS = { major: [1, 3, 5, 6, 8, 10], minor: [0, 2, 3, 5, 7, 10] };
const FUNC_COLOR = { T: '#4caf50', S: '#6ea8fe', D: '#ff9f43', C: '#c77dff' };
const FUNC_LABEL = { T: 'tonica', S: 'sottodominante', D: 'dominante', C: 'colore / prestito modale' };
const SNAPS = [[16, '1 battuta'], [8, '1/2'], [4, '1/4'], [2, '1/8'], [1, '1/16']];
const VERSION_NAMES = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const STYLE_BADGE = { block: '▤', strum: '⟋', arp: '⋰' };
const VEL_CYCLE = [0, 100, 120, 65]; // click on a step: off → strike → accent → soft → off
const LEN_CYCLE = [0, 1, 2, 4, 8];   // alt+click: until the next strike, 1/16, 1/8, 1/4, 1/2
const SYNTHS = [['pad', 'Pad'], ['ep', 'Piano elettrico'], ['pluck', 'Pluck'], ['organ', 'Organo']];
const SCALES = { major: [0, 2, 4, 5, 7, 9, 11], minor: [0, 2, 3, 5, 7, 8, 10] };
const ROW_H = 10;     // px per semitone in the piano roll
const MEL = -1;       // clip index of melody events in the transport
// melody layers: synth preset and colour of each role
const ROLE_PRESET = { lead: 'lead', riff: 'lead', arp: 'pluck', bass: 'bass', pad: 'pad', keys: 'ep' };
const ROLE_COLOR = { lead: '#ffb84d', bass: '#5aa9e6', arp: '#7bc96f', riff: '#ef7b6b', pad: '#b096e0', keys: '#e3cf5d' };
const GEN_HINT = {
  lead: "note dell'accordo sui tempi forti, la scala in mezzo",
  bass: 'fondamentale sul primo tempo, ottave/quinte/passaggi, nota di avvicinamento al prossimo accordo',
  arp: "le note dell'accordo in sequenza",
  riff: 'una cellula di una battuta che segue gli accordi',
  pad: 'accordi tenuti, voicing legati',
  keys: 'accordi ritmati (comping)',
};
const PARTS = [['both', 'Accordi + melodia'], ['chords', 'Solo accordi'], ['melody', 'Solo melodia']];

const keyFlats = (k) => FLAT_KEYS[k.mode]?.includes(k.tonic % 12);
const keyName = (k) => `${(keyFlats(k) ? FLATS : SHARPS)[k.tonic % 12]} ${k.mode === 'minor' ? 'minore' : 'maggiore'}`;
const newLayer = (role = 'lead', name = 'Melodia', notes = []) => ({ id: 'L' + uid().slice(1), name, role, notes, vol: 1, mute: false });
// melody of a version: {layers, active}; an old {notes} is one "Melodia" layer
const melodyOf = (m) => {
  if (m?.layers?.length) return m;
  const l = newLayer('lead', 'Melodia', m?.notes || []);
  return { layers: [l], active: l.id };
};
const newSeq = () => ({ bars: 4, keyMode: 'locked', key: { tonic: 0, mode: 'major' }, clips: [], melody: melodyOf() });
const pitchName = (p, flats) => `${(flats ? FLATS : SHARPS)[p % 12]}${Math.floor(p / 12) - 1}`;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const newProject = (mode) => ({
  name: 'Progressione', bpm: 100, active: 'A', order: ['A'], versions: { A: newSeq() },
  modeActive: '1', modeOrder: ['1'], modes: { 1: mode },
});

// grid arrays exactly bars*16 long (a longer grid repeats the shorter one)
function fixGrid(g) {
  const bars = Math.max(1, Math.min(8, g.bars || 1));
  const n = bars * 16;
  const fit = (a, fill) => Array.from({ length: n }, (_, i) => (a?.length ? a[i % a.length] ?? fill : fill));
  return { on: !!g.on, bars, preset: g.preset ?? null, vel: fit(g.vel, 0), len: fit(g.len, 0), dir: fit(g.dir, '') };
}

// Compose v1 style {type: block|strum|arp|rhythm, rhythm: {pattern, hit}, …} -> {play, rhythm}
function legacyStyle(st, grids) {
  const play = {};
  for (const k of ['gate', 'strum', 'arp', 'velCurve', 'humanize', 'alternate']) if (st[k] !== undefined) play[k] = clone(st[k]);
  play.type = st.type || 'block';
  let rhythm = 'sustain';
  if (play.type === 'rhythm') {
    rhythm = clone(grids[st.rhythm?.pattern] || grids.quarters);
    play.type = st.rhythm?.hit === 'strum' ? 'strum' : 'block';
  }
  if (play.type === 'strum' || st.rhythm?.hit === 'strum') play.strum = { dir: 'up', ...(play.strum || {}) };
  if (play.alternate?.tokens) play.alternate.tokens = play.alternate.tokens.map((t) => (t === 'rhythm' ? 'block' : t));
  return { play, rhythm };
}

export function transposeName(name, semis, flats) {
  if (!semis || !name) return name;
  const sub = (n) => (flats ? FLATS : SHARPS)[(((PC[n] ?? 0) + semis) % 12 + 12) % 12];
  return name.replace(/^[A-G][b#]?/, sub).replace(/(?<=[/;])[A-G][b#]?/g, sub);
}

function mergeStyle(base, over) {
  const out = clone(base);
  for (const [k, v] of Object.entries(over || {})) {
    if (v && typeof v === 'object' && !Array.isArray(v) && out[k] && typeof out[k] === 'object') out[k] = mergeStyle(out[k], v);
    else if (v !== null && v !== undefined) out[k] = clone(v);
  }
  return out;
}

// ------------------------------------------------------------------ audio
class ChordSynth {
  constructor(player) {
    this.player = player;
    this.preset = 'pad';
    this.voices = new Set();
  }

  get ctx() { return this.player._ensure(); }

  // one gain per part (chords, melody, 'mel:<layer id>') into a shared compressor
  _bus(part = 'chords') {
    const ctx = this.ctx;
    if (!this.comp) {
      this.comp = ctx.createDynamicsCompressor();
      this.comp.threshold.value = -14;
      this.comp.ratio.value = 4;
      this.comp.connect(ctx.destination);
      this.buses = {};
    }
    if (!this.buses[part]) {
      this.buses[part] = ctx.createGain();
      this.buses[part].gain.value = 0.55;
      this.buses[part].connect(this.comp);
    }
    return this.buses[part];
  }

  note(pitch, vel, t0, t1, preset = this.preset, part = 'chords') {
    const ctx = this.ctx;
    if (ctx.state !== 'running') ctx.resume();
    const f = 440 * Math.pow(2, (pitch - 69) / 12);
    const p = {
      pad: { w: ['sawtooth', 'sawtooth'], det: [-8, 8], mix: [1, 1], a: 0.06, d: 0.4, s: 0.7, r: 0.35, cut: 1500, env: 600, q: 0.6 },
      ep: { w: ['sine', 'triangle'], det: [0, 1200], mix: [1, 0.22], a: 0.004, d: 1.1, s: 0.32, r: 0.25, cut: 3800, env: 0, q: 0.3 },
      pluck: { w: ['sawtooth', 'square'], det: [-4, 4], mix: [1, 0.5], a: 0.003, d: 0.35, s: 0.12, r: 0.14, cut: 700, env: 3200, q: 1.2 },
      organ: { w: ['sine', 'sine'], det: [0, 1200], mix: [1, 0.5], a: 0.01, d: 0.05, s: 1, r: 0.07, cut: 6000, env: 0, q: 0.2 },
      lead: { w: ['sawtooth', 'square'], det: [0, 7], mix: [1, 0.35], a: 0.008, d: 0.3, s: 0.6, r: 0.12, cut: 2200, env: 1800, q: 1 },
      bass: { w: ['sawtooth', 'sine'], det: [0, -1200], mix: [0.55, 1], a: 0.004, d: 0.25, s: 0.7, r: 0.08, cut: 420, env: 900, q: 1.4 },
    }[preset] || {};
    const g = ctx.createGain();
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.Q.value = p.q;
    lp.frequency.setValueAtTime(p.cut + p.env, t0);
    lp.frequency.setTargetAtTime(p.cut, t0 + p.a, p.d / 3);
    const peak = 0.16 * velGain(vel);
    const end = Math.max(t1, t0 + p.a + 0.02);
    g.gain.setValueAtTime(0, t0);
    g.gain.linearRampToValueAtTime(peak, t0 + p.a);
    g.gain.setTargetAtTime(peak * p.s, t0 + p.a, p.d / 3);
    g.gain.cancelScheduledValues(end);
    g.gain.setTargetAtTime(0, end, p.r / 3);
    lp.connect(g).connect(this._bus(part));
    const oscs = p.w.map((w, i) => {
      const o = ctx.createOscillator();
      o.type = w;
      o.frequency.value = f;
      o.detune.value = p.det[i];
      const m = ctx.createGain();
      m.gain.value = p.mix[i];
      o.connect(m).connect(lp);
      o.start(t0);
      o.stop(end + p.r * 2 + 0.05);
      return o;
    });
    const voice = { g, oscs };
    this.voices.add(voice);
    oscs[0].onended = () => { this.voices.delete(voice); g.disconnect(); };
  }

  setVolume(v, part = 'chords') { this._bus(part).gain.value = 0.55 * v; }

  chord(notes, dur = 1.3) {
    this.stopAll();
    const t = this.ctx.currentTime + 0.02;
    for (const [p, v] of notes) this.note(p, v, t, t + dur);
  }

  stopAll() {
    if (!this.player.ctx) return;
    const now = this.ctx.currentTime;
    for (const v of this.voices) {
      v.g.gain.cancelScheduledValues(now);
      v.g.gain.setTargetAtTime(0, now, 0.02);
      for (const o of v.oscs) { try { o.stop(now + 0.1); } catch { /* not started yet */ } }
    }
    this.voices.clear();
  }
}

class Transport {
  constructor(synth) {
    this.synth = synth;
    this.playing = false;
    this.timer = null;
  }

  get ctx() { return this.synth.ctx; }

  // events: [start, end, pitch, vel, clip] ticks (clip MEL: a melody note, + its preset and bus); plays [from, to) once or looped
  // at: AudioContext time of `from` (to start in sync with the Sequencer)
  play({ events, bpm, from = 0, to, loop = false, onEnd, at = null }) {
    this.stop();
    this.bpm = bpm;
    this.spt = 60 / bpm / PPQ;
    this.from = from;
    this.to = to;
    this.loop = loop;
    this.onEnd = onEnd;
    this.lenSec = (to - from) * this.spt;
    this._setEvents(events);
    this.base = at ?? this.ctx.currentTime + 0.06;
    this.n = 0;
    this.idx = 0;
    this.playing = true;
    this.timer = setInterval(() => this._tick(), 25);
    this._tick();
  }

  _setEvents(events) {
    this.events = events.filter((e) => e[0] >= this.from && e[0] < this.to).sort((a, b) => a[0] - b[0]);
  }

  // swap the events while playing (an edit): continue from the current position
  update(events) {
    if (!this.playing) return;
    this._setEvents(events);
    const pos = this.position + 0.1 / this.spt;
    this.idx = this.events.findIndex((e) => e[0] >= pos);
    if (this.idx < 0) this.idx = this.events.length;
  }

  _tick() {
    const now = this.ctx.currentTime;
    const horizon = now + 0.15;
    for (let guard = 0; guard < 2000; guard++) {
      if (this.idx >= this.events.length) {
        if (this.loop && now + 0.15 > this.base + (this.n + 1) * this.lenSec) { this.n++; this.idx = 0; continue; }
        if (!this.loop && now > this.base + this.lenSec + 0.3) { this.stop(); this.onEnd?.(); }
        return;
      }
      const e = this.events[this.idx];
      const off = this.base + this.n * this.lenSec - this.from * this.spt;
      const t = off + e[0] * this.spt;
      if (t > horizon) return;
      if (t >= now - 0.05) {
        const end = off + Math.min(e[1], this.to) * this.spt;
        if (e[4] === MEL) this.synth.note(e[2], e[3], Math.max(t, now), end, e[5] || 'lead', e[6] || 'melody');
        else this.synth.note(e[2], e[3], Math.max(t, now), end);
      }
      this.idx++;
    }
  }

  get position() {
    if (!this.playing) return -1;
    let s = this.ctx.currentTime - this.base;
    if (this.loop) s = ((s % this.lenSec) + this.lenSec) % this.lenSec;
    return this.from + Math.max(0, s) / this.spt;
  }

  stop() {
    clearInterval(this.timer);
    this.timer = null;
    if (this.playing) this.synth.stopAll();
    this.playing = false;
  }
}

// ------------------------------------------------------------------ editor
export class ComposeEditor {
  constructor({ api, player, getPattern, onOpenSequencer }) {
    this.api = api;
    this.player = player;
    this.getPattern = getPattern;          // -> PatternEditor (play together with its pattern)
    this.onOpenSequencer = onOpenSequencer;
    this._pat = null;                      // PatternEditor while its pattern plays under the progression
    this.synth = new ChordSynth(player);
    this.transport = new Transport(this.synth);
    this.ready = null;
    this.project = null;
    this.sel = new Set();
    this.primary = null;
    this.melSel = new Set();                // selected melody notes
    this.browse = { tonic: 0, mode: 'major', cats: ['triad', 'extended', 'borrowed', 'progression'], q: '' };
    this.ui = { snap: 4, loop: true, synth: 'pad', pure: false, withPattern: false, bassFollow: true, chordVol: 0.8, patVol: 0.8,
      view: 'harmony', melVol: 0.8, melMute: false, parts: 'both',
      gen: { role: 'lead', density: 'mid', contour: 'arch', lo: 60, hi: 81, sel: false }, harm: { rate: 'bar', key: 'seq', related: false } };
    this.keyData = new Map();
    this.rendered = { events: [], byId: {}, labels: {}, layers: [] };
    this.undoStack = [];
    this.redoStack = [];
    this.clipKinds = null;
    this.progKinds = null;
    this.modeKinds = null;
  }

  get seq() { return this.project.versions[this.project.active]; }

  get mode() { return this.project.modes[this.project.modeActive]; }

  // what python renders: the harmony + the project tempo + a Modalità
  _playSeq(seq, mode = this.mode) { return { ...seq, bpm: this.project.bpm, mode, name: this.project.name }; }

  get playSeq() { return this._playSeq(this.seq); }

  _migrate(p) {
    const def = this.meta.styles.defaultMode;
    const grids = this.meta.styles.presetGrids;
    if (!p.modes) {
      const v = p.versions[p.active] || Object.values(p.versions)[0];
      const mode = clone(def);
      if (v?.defaultStyle) {
        const { play, rhythm } = legacyStyle(v.defaultStyle, grids);
        mode.play = mergeStyle(def.play, play);
        if (typeof rhythm === 'object') mode.rhythm = rhythm;
      }
      Object.assign(p, { modes: { 1: mode }, modeOrder: ['1'], modeActive: '1' });
    }
    if (!p.bpm) p.bpm = p.versions[p.active]?.bpm || 100;
    for (const v of Object.values(p.versions)) {
      v.melody = melodyOf(v.melody);
      delete v.defaultStyle;
      delete v.bpm;
      for (const c of v.clips) if (c.style?.type && !c.style.play) c.style = legacyStyle(c.style, grids);
    }
    for (const [k, m] of Object.entries(p.modes)) {
      p.modes[k] = { ...mergeStyle(def, m), rhythm: fixGrid(m.rhythm || def.rhythm) };
    }
    if (!p.modes[p.modeActive]) p.modeActive = p.modeOrder[0];
    return p;
  }

  // ---------------------------------------------------------------- lifecycle
  ensure() {
    if (!this.ready) this.ready = this._init();
    return this.ready;
  }

  async _init() {
    this.meta = await this.api.compose_init();
    this.project = newProject(clone(this.meta.styles.defaultMode));
    try {
      const saved = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
      if (saved?.project?.versions) {
        this.project = this._migrate(saved.project);
        this.browse = { ...this.browse, ...saved.browse };
        this.ui = { ...this.ui, ...saved.ui, gen: { ...this.ui.gen, ...saved.ui?.gen } };
      }
    } catch { /* private mode / bad JSON */ }
    if (!this.seq) this.project.active = this.project.order[0];
    this.synth.preset = this.ui.synth;
    this.clipKinds = this.meta.clipKinds.map(([k]) => k);
    this.progKinds = ['reharm', 'rhythm', 'ending', 'voicing'];
    this.modeKinds = ['density', 'syncopation', 'preset', 'strum', 'feel'];
    this._buildShell();
  }

  async show() {
    await this.ensure();
    this.renderAll();
    await this.loadBrowser();
    this.refresh();
  }

  hide() { this.stop(); }

  _persist() {
    try { localStorage.setItem(LS_KEY, JSON.stringify({ project: this.project, browse: this.browse, ui: this.ui })); } catch { /* private mode */ }
  }

  // every change goes through edit(): undo snapshot, persist, redraw, re-render the audio
  edit(fn, { redraw = true } = {}) {
    this.undoStack.push(JSON.stringify(this.project));
    if (this.undoStack.length > 120) this.undoStack.shift();
    this.redoStack = [];
    fn();
    this._afterChange(redraw);
  }

  _afterChange(redraw = true) {
    this._persist();
    if (redraw) this.renderAll();
    this.refresh();
  }

  undo() {
    if (!this.undoStack.length) return;
    this.redoStack.push(JSON.stringify(this.project));
    this.project = JSON.parse(this.undoStack.pop());
    this._keepSelection();
    this._afterChange();
  }

  redo() {
    if (!this.redoStack.length) return;
    this.undoStack.push(JSON.stringify(this.project));
    this.project = JSON.parse(this.redoStack.pop());
    this._keepSelection();
    this._afterChange();
  }

  _keepSelection() {
    const nids = new Set(this.melNotes.map((n) => n.id));
    this.melSel = new Set([...this.melSel].filter((i) => nids.has(i)));
    const ids = new Set(this.seq.clips.map((c) => c.id));
    this.sel = new Set([...this.sel].filter((i) => ids.has(i)));
    if (!ids.has(this.primary)) this.primary = [...this.sel][0] || null;
  }

  // ---------------------------------------------------------------- shell
  _buildShell() {
    const root = $('#compose');
    const tonics = (flats) => SHARPS.map((n, i) => `<option value="${i}">${flats && FLATS[i] !== n ? `${FLATS[i]}` : n}</option>`).join('');
    root.innerHTML = `
      <aside class="sidebar cp-browser">
        <div class="cp-pack"><span class="cp-pack-path" id="cp-dir"></span><button class="link-btn" id="cp-dir-pick">Cambia…</button></div>
        <div class="cp-keyrow">
          <select id="cp-b-tonic" class="cp-select">${tonics(true)}</select>
          <div class="seg" id="cp-b-mode"><button class="seg-btn" data-mode="major">Maggiore</button><button class="seg-btn" data-mode="minor">Minore</button></div>
        </div>
        <div class="hint" id="cp-b-hint"></div>
        <input id="cp-q" class="search" type="search" placeholder="Cerca (es. maj9, sus, Am, bVII)…" autocomplete="off">
        <div class="chips" id="cp-cats"></div>
        <div class="cp-legend">${Object.entries(FUNC_LABEL).map(([f, l]) => `<span><i style="background:${FUNC_COLOR[f]}"></i>${l}</span>`).join('')}</div>
        <div id="cp-list" class="cp-list"></div>
      </aside>
      <main class="cp-main">
        <div class="cp-toolbar">
          <div class="seg" id="cp-view" title="Armonia: gli accordi · Melodia: la melodia sopra gli accordi">
            <button class="seg-btn" data-view="harmony">Armonia</button><button class="seg-btn" data-view="melody">Melodia</button></div>
          <input id="cp-name" class="cp-name" type="text" spellcheck="false" title="Nome della progressione">
          <label class="cp-field">BPM <input id="cp-bpm" type="number" min="40" max="240" step="1"></label>
          <label class="cp-field">Battute <input id="cp-bars" type="number" min="1" max="128" step="1"></label>
          <label class="cp-field">Griglia <select id="cp-snap" class="cp-select">${SNAPS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></label>
          <div class="seg" id="cp-keymode" title="Bloccata: solo accordi della tonalità, cambiare tonalità traspone tutto. Libera: accordi da qualunque tonalità, trasponibili uno per uno.">
            <button class="seg-btn" data-km="locked">🔒 Tonalità</button><button class="seg-btn" data-km="free">Libera</button></div>
          <select id="cp-tonic" class="cp-select" title="Tonalità della progressione">${tonics(true)}</select>
          <select id="cp-mode" class="cp-select"><option value="major">maggiore</option><option value="minor">minore</option></select>
          <div class="spacer"></div>
          <select id="cp-synth" class="cp-select" title="Suono dell'anteprima (non viene esportato)">${SYNTHS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select>
          <button class="icon-btn" id="cp-melmute" title="Melodia: on / muta">♫</button>
          <button class="btn primary cp-play" id="cp-play" title="Play / stop (Spazio)">▶</button>
          <button class="icon-btn" id="cp-loop" title="Loop">⟲</button>
          <span class="cp-pat"><button class="btn" id="cp-withpat" title="Suona insieme al pattern del Sequencer">🥁 Pattern</button><button class="btn" id="cp-patset" title="Pattern: basso, volumi, BPM">▾</button></span>
          <button class="icon-btn" id="cp-undo" title="Annulla (⌘Z)">↶</button>
          <button class="icon-btn" id="cp-redo" title="Ripeti (⇧⌘Z)">↷</button>
          <button class="btn" id="cp-open">Apri…</button>
          <button class="btn" id="cp-save">Salva</button>
          <button class="btn primary" id="cp-export">Esporta MIDI ▾</button>
        </div>
        <div class="cp-versions" id="cp-versions"></div>
        <div class="cp-tlwrap" id="cp-tlwrap">
          <div class="cp-tl" id="cp-tl">
            <div class="cp-ruler" id="cp-ruler"></div>
            <div class="cp-lane" id="cp-lane"></div>
            <div class="cp-rlane" id="cp-rlane" title="Ritmica della modalità · clic: colpo → accento → soft → spento · Alt+clic: durata · ⇧+clic: pennata giù/su"></div>
            <div class="cp-proll" id="cp-proll" hidden></div>
            <div class="cp-playhead" id="cp-playhead" hidden></div>
          </div>
        </div>
        <div class="cp-modes" id="cp-modes"></div>
        <div class="cp-modes cp-melbar" id="cp-melbar" hidden></div>
        <div class="cp-tlbar">
          <span class="hint" id="cp-tlhint"></span>
          <div class="spacer"></div>
          <button class="btn small" id="cp-even" title="Stessa durata per tutti gli accordi, su tutta la lunghezza">⇔ Distribuisci</button>
          <button class="btn small" id="cp-clear">Svuota</button>
        </div>
        <div class="cp-bottom">
          <section class="cp-suggest">
            <div class="cp-sec-title"><span id="cp-sug-title">Prossimo accordo</span><span class="hint">clic: ascolta · + o doppio clic: aggiungi</span></div>
            <div id="cp-sug" class="cp-sug"></div>
          </section>
          <section class="cp-inspector" id="cp-insp"></section>
          <section class="cp-suggest cp-mpanel" id="cp-mgen" hidden></section>
          <section class="cp-suggest cp-mpanel" id="cp-mharm" hidden></section>
        </div>
      </main>`;
    this._bindShell();
  }

  _bindShell() {
    $('#cp-dir-pick').onclick = async () => {
      this.meta = { ...this.meta, ...(await this.api.compose_pick_folder()) };
      this.keyData.clear();
      await this.loadBrowser();
    };
    $('#cp-b-tonic').onchange = (e) => { this.browse.tonic = +e.target.value; this._persist(); this.loadBrowser(); };
    $('#cp-b-mode').onclick = (e) => {
      const b = e.target.closest('[data-mode]'); if (!b) return;
      this.browse.mode = b.dataset.mode; this._persist(); this.loadBrowser();
    };
    $('#cp-q').oninput = (e) => { this.browse.q = e.target.value; this.renderList(); };
    $('#cp-cats').onclick = (e) => {
      const b = e.target.closest('[data-cat]'); if (!b) return;
      const c = b.dataset.cat;
      this.browse.cats = this.browse.cats.includes(c) ? this.browse.cats.filter((x) => x !== c) : [...this.browse.cats, c];
      this._persist();
      this.renderCats();
      this.renderList();
    };
    const list = $('#cp-list');
    list.onclick = (e) => {
      const r = e.target.closest('[data-cid],[data-pid]'); if (!r) return;
      if (e.target.closest('[data-add]')) { this.addFromBrowser(r); return; }
      if (r.dataset.cid) this.audition(this.chord(r.dataset.cid));
      else this.auditionProgression(this.progression(r.dataset.pid));
    };
    list.ondblclick = (e) => { const r = e.target.closest('[data-cid],[data-pid]'); if (r && !e.target.closest('[data-add]')) this.addFromBrowser(r); };
    list.addEventListener('dragstart', (e) => {
      const r = e.target.closest('[data-cid],[data-pid]'); if (!r) return;
      e.dataTransfer.setData(DRAG_TYPE, r.dataset.cid ? `chord:${r.dataset.cid}` : `prog:${r.dataset.pid}`);
      e.dataTransfer.effectAllowed = 'copy';
    });

    $('#cp-name').onchange = (e) => this.edit(() => { this.project.name = e.target.value.trim() || 'Progressione'; }, { redraw: false });
    $('#cp-bpm').onchange = (e) => this.edit(() => { this.project.bpm = Math.max(40, Math.min(240, +e.target.value || 100)); });
    $('#cp-bars').onchange = (e) => this.edit(() => { this.seq.bars = Math.max(1, Math.min(128, Math.round(+e.target.value) || 4)); });
    $('#cp-snap').onchange = (e) => { this.ui.snap = +e.target.value; this._persist(); };
    $('#cp-keymode').onclick = (e) => {
      const b = e.target.closest('[data-km]'); if (!b || b.dataset.km === this.seq.keyMode) return;
      this.edit(() => {
        this.seq.keyMode = b.dataset.km;
        if (b.dataset.km === 'locked') {
          // locking folds the per-clip transpositions into the notes
          for (const c of this.seq.clips) this._bakeTranspose(c);
          this.browse.tonic = this.seq.key.tonic; this.browse.mode = this.seq.key.mode;
        }
      });
      this.loadBrowser();
    };
    $('#cp-tonic').onchange = (e) => this.setKey(+e.target.value, this.seq.key.mode);
    $('#cp-mode').onchange = (e) => this.setKey(this.seq.key.tonic, e.target.value);
    $('#cp-synth').onchange = (e) => { this.ui.synth = this.synth.preset = e.target.value; this._persist(); };
    $('#cp-view').onclick = (e) => { const b = e.target.closest('[data-view]'); if (b) this.setView(b.dataset.view); };
    $('#cp-melmute').onclick = () => {
      this.ui.melMute = !this.ui.melMute;
      this._persist();
      this.renderToolbar();
      this.transport.update(this.playEvents);
    };
    $('#cp-play').onclick = () => this.togglePlay();
    $('#cp-withpat').onclick = () => {
      this.ui.withPattern = !this.ui.withPattern;
      this._persist();
      this.renderToolbar();
      if (this.transport.playing) this.play(Math.floor(this.transport.position / (16 * STEP_TICKS)) * 16 * STEP_TICKS);
    };
    $('#cp-patset').onclick = (e) => this.patternMenu(e.currentTarget);
    $('#cp-loop').onclick = () => { this.ui.loop = !this.ui.loop; this._persist(); this.renderToolbar(); };
    $('#cp-undo').onclick = () => this.undo();
    $('#cp-redo').onclick = () => this.redo();
    $('#cp-save').onclick = () => this.save();
    $('#cp-open').onclick = (e) => this.openDialog(e.currentTarget);
    $('#cp-export').onclick = (e) => this.exportMenu(e.currentTarget);
    $('#cp-even').onclick = () => this.distribute();
    $('#cp-clear').onclick = () => {
      if (this.ui.view === 'melody') { if (this.melNotes.length) this.edit(() => { this.melNotes = []; this.melSel.clear(); }); return; }
      if (this.seq.clips.length) this.edit(() => { this.seq.clips = []; this.sel.clear(); this.primary = null; });
    };
    this._bindMelody();

    $('#cp-versions').onclick = (e) => {
      const v = e.target.closest('[data-v]');
      if (v) { this.project.active = v.dataset.v; this.sel.clear(); this.melSel.clear(); this.primary = null; this._afterChange(); this.loadBrowser(); return; }
      const a = e.target.closest('[data-act]'); if (!a) return;
      if (a.dataset.act === 'harm') { this.setView('melody'); this.harmonize(); return; }
      if (a.dataset.act === 'dup') this.addVersion(clone(this.seq));
      else if (a.dataset.act === 'del') this.deleteVersion();
      else if (a.dataset.act === 'vary') this.progressionVariations();
    };

    const modes = $('#cp-modes');
    modes.onclick = (e) => {
      const t = e.target.closest('[data-m]');
      if (t) { this.project.modeActive = t.dataset.m; this._afterChange(); return; }
      const a = e.target.closest('[data-mact]'); if (!a) return;
      const act = a.dataset.mact;
      if (act === 'dup') this.addMode({ ...clone(this.mode), name: `${this.mode.name} (copia)` });
      else if (act === 'del') this.deleteMode();
      else if (act === 'vary') this.modeVariations();
      else if (act === 'toggle') this.edit(() => { const g = this.mode.rhythm; g.on = !g.on; if (g.on && !g.vel.some(Boolean)) Object.assign(g, fixGrid(this.meta.styles.presetGrids.quarters)); });
      else if (act === 'rclear') this.edit(() => { const g = this.mode.rhythm; g.vel = g.vel.map(() => 0); g.len = g.len.map(() => 0); g.dir = g.dir.map(() => ''); g.preset = null; });
    };
    modes.ondblclick = (e) => {
      const t = e.target.closest('[data-m]'); if (!t) return;
      const name = prompt('Nome della modalità', this.project.modes[t.dataset.m].name);
      if (name) this.edit(() => { this.project.modes[t.dataset.m].name = name.trim(); });
    };
    modes.onchange = (e) => {
      if (e.target.id === 'cp-preset' && e.target.value) {
        this.edit(() => { this.mode.rhythm = fixGrid(this.meta.styles.presetGrids[e.target.value]); });
      } else if (e.target.id === 'cp-rbars') {
        this.edit(() => { this.mode.rhythm = fixGrid({ ...this.mode.rhythm, bars: +e.target.value }); });
      }
    };
    $('#cp-rlane').addEventListener('pointerdown', (e) => this._onRhythmDown(e));

    const lane = $('#cp-lane');
    lane.addEventListener('dragover', (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; this._dropMarker(e); });
    lane.addEventListener('dragleave', () => this._dropMarker(null));
    lane.addEventListener('drop', (e) => {
      e.preventDefault();
      this._dropMarker(null);
      const data = e.dataTransfer.getData(DRAG_TYPE);
      const at = this._stepAt(e.clientX);
      if (data.startsWith('chord:')) this.insertChord(this.chord(data.slice(6)), at);
      else if (data.startsWith('prog:')) this.insertProgression(this.progression(data.slice(5)), at);
    });
    lane.addEventListener('pointerdown', (e) => this._onLaneDown(e));
    lane.addEventListener('dblclick', (e) => {
      const el = e.target.closest('.cp-clip'); if (!el) return;
      const c = this.clip(el.dataset.id);
      this.playRange(c.start * STEP_TICKS, (c.start + c.len) * STEP_TICKS);
    });
    $('#cp-ruler').onclick = (e) => {
      if (!this.transport.playing) return;
      this.play(Math.floor(this._stepAt(e.clientX) / 16) * 16 * STEP_TICKS);
    };

    $('#cp-sug').onclick = (e) => {
      const card = e.target.closest('[data-sug]'); if (!card) return;
      const alt = e.target.closest('[data-alt]');
      const item = this.sugItems[+card.dataset.sug];
      const chord = alt ? item.alts[+alt.dataset.alt] : item.chord;
      if (e.target.closest('[data-add]')) this.insertAfter(chord);
      else this.audition(chord);
    };
    $('#cp-sug').ondblclick = (e) => {
      const card = e.target.closest('[data-sug]'); if (!card || e.target.closest('[data-add]')) return;
      const alt = e.target.closest('[data-alt]');
      const item = this.sugItems[+card.dataset.sug];
      this.insertAfter(alt ? item.alts[+alt.dataset.alt] : item.chord);
    };
    new ResizeObserver(() => { if (!$('#compose').hidden) this.renderTimeline(); }).observe($('#cp-tlwrap'));
  }

  // ---------------------------------------------------------------- browser
  get browseKey() {
    return this.seq.keyMode === 'locked' ? this.seq.key : { tonic: this.browse.tonic, mode: this.browse.mode };
  }

  async keyChords(k) {
    const id = `${k.tonic}:${k.mode}`;
    if (!this.keyData.has(id)) {
      const data = await this.api.compose_chords(k.tonic, k.mode);
      data.byId = Object.fromEntries(data.chords.map((c) => [c.id, c]));
      data.progById = Object.fromEntries(data.progressions.map((p) => [p.id, p]));
      this.keyData.set(id, data);
    }
    return this.keyData.get(id);
  }

  chord(id) {
    for (const d of this.keyData.values()) {
      if (d.byId[id]) return d.byId[id];
      for (const p of d.progressions) { const c = p.chords.find((x) => x.id === id); if (c) return c; }
    }
    return null;
  }

  progression(id) {
    for (const d of this.keyData.values()) if (d.progById[id]) return d.progById[id];
    return null;
  }

  async loadBrowser() {
    this.renderBrowserHead();
    if (!this.meta.exists) {
      $('#cp-list').innerHTML = `<div class="cp-empty">Cartella del chord pack non trovata:<br><code>${esc(this.meta.dir)}</code><br>
        <button class="btn small" id="cp-dir-pick2">Scegli la cartella…</button></div>`;
      $('#cp-dir-pick2').onclick = () => $('#cp-dir-pick').click();
      return;
    }
    this.current = await this.keyChords(this.browseKey);
    this.renderList();
  }

  renderBrowserHead() {
    const k = this.browseKey;
    const locked = this.seq.keyMode === 'locked';
    $('#cp-dir').textContent = this.meta.dir.replace(/^\/Users\/[^/]+/, '~');
    $('#cp-dir').title = this.meta.dir;
    $('#cp-b-tonic').value = k.tonic;
    $('#cp-b-tonic').disabled = locked;
    $('#cp-b-mode').querySelectorAll('[data-mode]').forEach((b) => { b.classList.toggle('active', b.dataset.mode === k.mode); b.disabled = locked; });
    const tr = this.current?.transposed;
    $('#cp-b-hint').textContent = (locked ? `Tonalità bloccata su ${keyName(k)}: cambiala dalla barra in alto.` : `Sfogli ${keyName(k)} · ogni accordo resta trasponibile.`)
      + (tr ? ` Tonalità assente nel pack: trasposta di ${tr > 0 ? '+' : ''}${tr}.` : '')
      + (this.current?.partial ? ' Il pack è incompleto per questa tonalità: alcune categorie sono trasposte da tonalità vicine.' : '');
    this.renderCats();
  }

  renderCats() {
    $('#cp-cats').innerHTML = this.meta.categories.map(([id, label]) =>
      `<button class="chip ${this.browse.cats.includes(id) ? 'on' : ''}" data-cat="${id}">${esc(label)}</button>`).join('');
  }

  renderList() {
    if (!this.current) return;
    this.renderBrowserHead();
    const q = this.browse.q.trim().toLowerCase();
    const match = (c) => !q || c.name.toLowerCase().includes(q) || c.degree.toLowerCase() === q || c.degree.toLowerCase().startsWith(q);
    const chords = this.current.chords.filter((c) => this.browse.cats.includes(c.category) && match(c));
    const k = this.current.key;
    const groups = new Map();
    for (const c of chords) {
      const iv = ((c.root - k.tonic) % 12 + 12) % 12;
      const g = `${String(iv).padStart(2, '0')}${c.degree.replace(/[^IViv#b]/g, '')}`;
      if (!groups.has(g)) groups.set(g, []);
      groups.get(g).push(c);
    }
    const html = [];
    for (const [, items] of [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
      const d = items[0];
      html.push(`<div class="cp-group"><div class="cp-group-title"><span class="cp-deg" style="--fc:${FUNC_COLOR[d.func]}">${esc(d.degree.replace(/(sus|7|\+)$/, ''))}</span><span class="hint">${FUNC_LABEL[d.func]}</span></div>`);
      for (const c of items.sort((a, b) => a.notes.length - b.notes.length || a.name.localeCompare(b.name))) {
        html.push(`<div class="cp-chord" draggable="true" data-cid="${esc(c.id)}" title="${esc(c.file)}">
          <span class="cp-dot" style="background:${FUNC_COLOR[c.func]}"></span><span class="cp-cname">${esc(c.name)}</span>
          <span class="cp-cdeg">${esc(c.degree)}</span><button class="cp-add" data-add title="Aggiungi in coda">+</button></div>`);
      }
      html.push('</div>');
    }
    if (this.browse.cats.includes('progression')) {
      const progs = this.current.progressions.filter((p) => !q || p.name.toLowerCase().includes(q));
      if (progs.length) {
        html.push('<div class="cp-group"><div class="cp-group-title"><span>Progressioni del pack</span></div>');
        for (const p of progs) {
          html.push(`<div class="cp-prog" draggable="true" data-pid="${esc(p.id)}">
            <div class="cp-cname">${esc(p.name.replace(/\s*\(.*\)$/, ''))}</div>
            <div class="cp-prog-chords">${p.chords.map((c) => `<span style="--fc:${FUNC_COLOR[c.func]}">${esc(c.degree)}</span>`).join('')}</div>
            <button class="cp-add" data-add title="Aggiungi in coda">+</button></div>`);
        }
        html.push('</div>');
      }
    }
    $('#cp-list').innerHTML = html.join('') || '<div class="cp-empty">Nessun accordo con questi filtri.</div>';
  }

  addFromBrowser(row) {
    if (row.dataset.cid) this.insertChord(this.chord(row.dataset.cid), this._end());
    else this.insertProgression(this.progression(row.dataset.pid), this._end());
  }

  // ---------------------------------------------------------------- clips
  clip(id) { return this.seq.clips.find((c) => c.id === id); }

  sorted() { return [...this.seq.clips].sort((a, b) => a.start - b.start); }

  _end() { return this.seq.clips.reduce((m, c) => Math.max(m, c.start + c.len), 0); }

  _clipFrom(chord, start, len) {
    return {
      id: uid(), chordId: chord.id, name: chord.name, root: chord.root, quality: chord.quality,
      notes: clone(chord.notes), srcKey: chord.srcKey, category: chord.category, degree: chord.degree, func: chord.func,
      start, len, transpose: 0, octave: 0, inversion: 0, vel: 100, style: null,
    };
  }

  _select(id, add = false) {
    if (!add) this.sel.clear();
    if (id) {
      if (add && this.sel.has(id)) this.sel.delete(id); else this.sel.add(id);
    }
    this.primary = id && this.sel.has(id) ? id : [...this.sel][0] || null;
  }

  insertChord(chord, at, len = 16) {
    if (!chord) return;
    this.edit(() => {
      const c = this._clipFrom(chord, Math.max(0, at), len);
      this.seq.clips.push(c);
      this._resolve(c.id);
      this._select(c.id);
    });
    this.audition(chord);
  }

  insertProgression(p, at) {
    if (!p) return;
    this.edit(() => {
      const base = Math.max(0, at);
      let last = null;
      for (const ch of p.chords) {
        const c = this._clipFrom(ch, base + ch.start, ch.len);
        this.seq.clips.push(c);
        this._resolve(c.id);
        last = c;
      }
      this._select(last?.id);
    });
  }

  // a new chord right after the selected clip (or at the end), as long as it; the following clips move on
  insertAfter(chord) {
    if (!chord) return;
    const ref = this.clip(this.primary) || this.sorted().at(-1);
    this.insertChord(chord, ref ? ref.start + ref.len : 0, ref ? ref.len : 16);
  }

  // no overlaps: the clip that just moved wins, the one under its start is shortened, later ones shift right
  _resolve(id) {
    const m = this.clip(id);
    if (!m) return;
    const end = m.start + m.len;
    const others = this.seq.clips.filter((c) => c !== m).sort((a, b) => a.start - b.start);
    for (const c of others) if (c.start < m.start && c.start + c.len > m.start) c.len = m.start - c.start;
    let cursor = end;
    for (const c of others.filter((x) => x.start >= m.start)) {
      if (c.start < cursor) c.start = cursor;
      cursor = Math.max(cursor, c.start + c.len);
    }
    this._fitBars();
  }

  _fitBars() { this.seq.bars = Math.max(this.seq.bars, Math.ceil(this._end() / 16)); }

  _bakeTranspose(c) {
    if (!c.transpose) return;
    c.notes = c.notes.map(([p, v]) => [p + c.transpose, v]);
    c.name = transposeName(c.name, c.transpose, keyFlats(this.seq.key));
    c.root = ((c.root + c.transpose) % 12 + 12) % 12;
    c.transpose = 0;
  }

  setKey(tonic, mode) {
    const old = this.seq.key;
    if (old.tonic === tonic && old.mode === mode) return;
    this.edit(() => {
      this.seq.key = { tonic, mode }; // first: transposed names are spelled for the new key
      if (this.seq.keyMode === 'locked' && tonic !== old.tonic) {
        const shift = ((tonic - old.tonic + 6) % 12 + 12) % 12 - 6;
        for (const c of this.seq.clips) { c.transpose = (c.transpose || 0) + shift; this._bakeTranspose(c); }
        toast(`Progressione trasposta di ${shift > 0 ? '+' : ''}${shift} semitoni`);
      }
    });
    this.loadBrowser();
  }

  deleteSelected() {
    if (!this.sel.size) return;
    this.edit(() => {
      this.seq.clips = this.seq.clips.filter((c) => !this.sel.has(c.id));
      this.sel.clear();
      this.primary = null;
    });
  }

  duplicateSelected() {
    const items = this.sorted().filter((c) => this.sel.has(c.id));
    if (!items.length) return;
    this.edit(() => {
      const from = items[0].start;
      const end = items.at(-1).start + items.at(-1).len;
      this.sel.clear();
      for (const c of items) {
        const d = { ...clone(c), id: uid(), start: end + (c.start - from) };
        this.seq.clips.push(d);
        this._resolve(d.id);
        this.sel.add(d.id);
      }
      this.primary = [...this.sel].at(-1);
    });
  }

  distribute() {
    const cl = this.sorted();
    if (!cl.length) return;
    this.edit(() => {
      const total = this.seq.bars * 16;
      const each = Math.max(1, Math.floor(total / cl.length / this.ui.snap) * this.ui.snap || Math.floor(total / cl.length));
      cl.forEach((c, i) => { c.start = i * each; c.len = i === cl.length - 1 ? Math.max(each, total - i * each) : each; });
    });
  }

  // ---------------------------------------------------------------- versions
  addVersion(seq, label) {
    const name = VERSION_NAMES.split('').find((n) => !this.project.versions[n]);
    if (!name) { toast('Troppe versioni'); return; }
    this.edit(() => {
      this.project.versions[name] = seq;
      const i = this.project.order.indexOf(this.project.active);
      this.project.order.splice(i + 1, 0, name);
      this.project.active = name;
      this.sel.clear();
      this.melSel.clear();
      this.primary = null;
    });
    if (label) toast(`Versione ${name}: ${label}`);
  }

  deleteVersion() {
    if (this.project.order.length < 2) return;
    const v = this.project.active;
    if (!confirm(`Eliminare la versione ${v}?`)) return;
    this.edit(() => {
      const i = this.project.order.indexOf(v);
      this.project.order.splice(i, 1);
      delete this.project.versions[v];
      this.project.active = this.project.order[Math.max(0, i - 1)];
      this.sel.clear();
      this.primary = null;
    });
  }

  // ---------------------------------------------------------------- rendering (python) + suggestions
  refresh() {
    clearTimeout(this._refreshT);
    this._refreshT = setTimeout(() => { this._render(); this._suggest(); }, 90);
  }

  async _render() {
    const seq = this.seq;
    const ids = seq.clips.map((c) => c.id);
    const token = (this._renderToken = (this._renderToken || 0) + 1);
    const res = await this.api.compose_render(this.playSeq);
    if (token !== this._renderToken || !res?.events) return;
    const byId = {};
    for (const e of res.events) (byId[ids[e[4]]] ||= []).push(e);
    this.rendered = { events: res.events, byId, labels: Object.fromEntries(res.labels.map((l) => [l.id, l])), layers: res.layers || [] };
    for (const c of seq.clips) {
      const l = this.rendered.labels[c.id];
      if (l?.degree) { c.degree = l.degree; c.func = l.func; }
    }
    this.transport.update(this.playEvents);
    this.renderTimeline();
  }

  async _suggest() {
    const seq = this.seq;
    const token = (this._sugToken = (this._sugToken || 0) + 1);
    const res = await this.api.compose_suggest(seq, this.primary, 8);
    if (token !== this._sugToken || !res?.items) return;
    this.sugItems = res.items;
    const after = this.clip(res.after);
    $('#cp-sug-title').innerHTML = after
      ? `Dopo <b>${esc(this.displayName(after))}</b> <span class="cp-deg" style="--fc:${FUNC_COLOR[after.func] || '#888'}">${esc(after.degree || '')}</span>`
      : 'Accordo di partenza';
    $('#cp-sug').innerHTML = res.items.map((it, i) => `
      <div class="cp-sug-card" data-sug="${i}" style="--fc:${FUNC_COLOR[it.func]}">
        <div class="cp-sug-head"><span class="cp-deg" style="--fc:${FUNC_COLOR[it.func]}">${esc(it.degree)}</span><b>${esc(it.chord.name)}</b>
          <button class="cp-add" data-add title="Aggiungi dopo">+</button></div>
        <div class="cp-score"><i style="width:${Math.round(it.score * 100)}%"></i></div>
        <div class="cp-reasons">${esc(it.reasons.join(' · ') || FUNC_LABEL[it.func])}</div>
        ${it.alts.length ? `<div class="cp-alts">${it.alts.map((a, j) => `<span class="chip" data-alt="${j}" title="clic: ascolta · doppio clic: aggiungi">${esc(a.name)}</span>`).join('')}</div>` : ''}
      </div>`).join('') || '<div class="cp-empty">Nessun suggerimento: controlla la cartella del chord pack.</div>';
  }

  // ---------------------------------------------------------------- playback
  displayName(c) { return transposeName(c.name, c.transpose || 0, keyFlats(this.seq.key)); }

  audition(chord) {
    if (!chord) return;
    this.stop();
    this.synth.setVolume(this.ui.chordVol);
    this.synth.chord(chord.notes, 60 / this.project.bpm * 2.5);
  }

  async auditionProgression(p) {
    if (!p) return;
    const seq = { ...clone(this.seq), clips: p.chords.map((c) => this._clipFrom(c, c.start, c.len)) };
    seq.bars = Math.ceil(Math.max(...seq.clips.map((c) => c.start + c.len)) / 16);
    const res = await this.api.compose_render(this._playSeq(seq));
    this.stop();
    this.transport.play({ events: res.events, bpm: this.project.bpm, from: 0, to: seq.bars * 16 * STEP_TICKS, loop: false, onEnd: () => this.renderToolbar() });
  }

  togglePlay() { if (this.transport.playing) this.stop(); else this.play(); }

  async play(from = 0) {
    const to = this.seq.bars * 16 * STEP_TICKS;
    from = Math.max(0, Math.min(from, to - 1));
    this.stop();
    const pe = this.ui.withPattern ? await this._preparePattern() : null;
    const at = this.synth.ctx.currentTime + 0.08;
    if (pe) this._startPattern(pe, at, from);
    this.synth.setVolume(this.ui.chordVol);
    this._melVolumes();
    this.transport.play({ events: this.playEvents, bpm: this.project.bpm, from, to, loop: this.ui.loop, at,
      onEnd: () => { this._stopPattern(); this.renderToolbar(); } });
    this.renderToolbar();
    this._animate();
  }

  playRange(from, to, events = this.playEvents, seqBpm = this.project.bpm) {
    this.stop();
    this.synth.setVolume(this.ui.chordVol);
    this._melVolumes();
    this.transport.play({ events, bpm: seqBpm, from, to, loop: false, onEnd: () => this.renderToolbar() });
    this.renderToolbar();
    this._animate();
  }

  stop() {
    if (this._rec) { this.stopRecording(); return; }
    this.transport.stop();
    this.synth.stopAll();
    this._stopPattern();
    if (this.project) this.renderToolbar(); // hide() also runs before the tab was ever opened
  }

  // ---------------------------------------------------------------- with the Sequencer pattern
  async _preparePattern() {
    const pe = this.getPattern?.();
    if (!pe) return null;
    await pe.ensure();
    if (pe.seq.playing) pe.stop();
    await pe.seq.preload(pe.p);
    return pe.p ? pe : null;
  }

  // the pattern loops under the progression at the progression tempo; its bass can follow the chords
  _startPattern(pe, at, fromTick) {
    const sq = pe.seq;
    sq.setPattern({ ...clone(pe.p), bpm: this.project.bpm });
    const n = pe.p.bars * 16;
    const step = Math.round(fromTick / STEP_TICKS);
    const base = step - (step % n);
    sq.bassShift = this.ui.bassFollow ? (g) => this._bassShiftAt(base + g, pe.p.key, sq) : null;
    sq._graph();
    sq.master.gain.value = 0.9 * this.ui.patVol;
    sq.start(step % n, at);
    this._pat = pe;
  }

  _stopPattern() {
    if (!this._pat) return;
    const sq = this._pat.seq;
    sq.stop();
    sq.bassShift = null;
    if (sq.master) sq.master.gain.value = 0.9;
    sq.setPattern(this._pat.p);
    this._pat = null;
  }

  // semitones from the pattern key to the root of the chord sounding at an absolute step
  _bassShiftAt(abs, key, sq) {
    const L = this.seq.bars * 16;
    const pos = ((abs % L) + L) % L;
    const c = this.seq.clips.find((x) => x.start <= pos && pos < x.start + x.len);
    if (!c) return 0;
    const root = (((c.root + (c.transpose || 0)) % 12) + 12) % 12;
    const d = (((root - sq.noteIndex(key)) % 12) + 12) % 12;
    return d > 6 ? d - 12 : d;
  }

  async patternMenu(anchor) {
    const pe = this.getPattern?.();
    if (!pe) return;
    await pe.ensure();
    const p = pe.p;
    const g = pe.meta?.genres?.find((x) => x.id === p.genre);
    const pop = showPopover(anchor, `
      <div class="cp-sec-title"><span>Pattern del Sequencer</span></div>
      <div>${esc(g?.name || 'Pattern')} · ${esc(p.name || '')}<br><span class="hint">${Math.round(p.bpm)} BPM · ${p.bars} ${p.bars === 1 ? 'battuta' : 'battute'} · basso in ${esc(p.key)}</span></div>
      <label class="cp-own"><input type="checkbox" data-bass ${this.ui.bassFollow ? 'checked' : ''}> il basso segue gli accordi</label>
      <label class="cp-field">Accordi <input type="range" min="0" max="1.2" step="0.05" value="${this.ui.chordVol}" data-cv></label>
      <label class="cp-field">Pattern <input type="range" min="0" max="1.2" step="0.05" value="${this.ui.patVol}" data-pv></label>
      <button class="btn small" data-usebpm>Usa il BPM del pattern (${Math.round(p.bpm)})</button>
      <button class="btn small" data-swing>Swing del pattern (${p.swing}) nella modalità</button>
      <button class="btn small" data-open>Apri nel Sequencer</button>`);
    pop.querySelector('[data-bass]').onchange = (e) => {
      this.ui.bassFollow = e.target.checked;
      this._persist();
      if (this._pat) this._pat.seq.bassShift = null;
      if (this.transport.playing) this.play(Math.floor(this.transport.position / (16 * STEP_TICKS)) * 16 * STEP_TICKS);
    };
    pop.querySelector('[data-cv]').oninput = (e) => { this.ui.chordVol = +e.target.value; this.synth.setVolume(this.ui.chordVol); this._persist(); };
    pop.querySelector('[data-pv]').oninput = (e) => {
      this.ui.patVol = +e.target.value;
      if (this._pat?.seq.master) this._pat.seq.master.gain.value = 0.9 * this.ui.patVol;
      this._persist();
    };
    pop.querySelector('[data-usebpm]').onclick = () => { pop.close(); this.edit(() => { this.project.bpm = Math.round(p.bpm); }); };
    pop.querySelector('[data-swing]').onclick = () => { pop.close(); this.edit(() => { this.mode.swing = Math.max(50, Math.min(75, p.swing)); }); };
    pop.querySelector('[data-open]').onclick = () => { pop.close(); this.stop(); this.onOpenSequencer?.(); };
  }

  _animate() {
    cancelAnimationFrame(this._raf);
    const ph = $('#cp-playhead');
    const step = () => {
      const pos = this.transport.position;
      if (pos < 0 || $('#compose').hidden) { ph.hidden = true; this.renderToolbar(); return; }
      ph.hidden = false;
      ph.style.left = `${(pos / STEP_TICKS) * this.pxStep}px`;
      this._raf = requestAnimationFrame(step);
    };
    this._raf = requestAnimationFrame(step);
  }

  // ---------------------------------------------------------------- draw
  renderAll() {
    this.renderView();
    this.renderToolbar();
    this.renderVersions();
    this.renderModes();
    this.renderMelBar();
    this.renderTimeline();
    this.renderInspector();
    this.renderMelPanels();
  }

  renderToolbar() {
    const s = this.seq;
    const set = (id, v) => { const el = $(id); if (el && document.activeElement !== el) el.value = v; };
    set('#cp-name', this.project.name);
    set('#cp-bpm', this.project.bpm);
    set('#cp-bars', s.bars);
    set('#cp-snap', this.ui.snap);
    set('#cp-tonic', s.key.tonic);
    set('#cp-mode', s.key.mode);
    set('#cp-synth', this.ui.synth);
    $('#cp-keymode').querySelectorAll('[data-km]').forEach((b) => b.classList.toggle('active', b.dataset.km === s.keyMode));
    $('#cp-play').textContent = this.transport.playing || this._rec ? '■' : '▶';
    $('#cp-play').classList.toggle('rec', !!this._rec);
    $('#cp-view').querySelectorAll('[data-view]').forEach((b) => b.classList.toggle('active', b.dataset.view === this.ui.view));
    $('#cp-melmute').classList.toggle('active', !this.ui.melMute && this.hasMelody);
    $('#cp-melmute').title = this.ui.melMute ? 'Melodia muta: clic per sentirla' : 'Melodia: clic per silenziarla';
    $('#cp-loop').classList.toggle('active', this.ui.loop);
    $('#cp-withpat').classList.toggle('active', this.ui.withPattern);
    $('#cp-undo').disabled = !this.undoStack.length;
    $('#cp-redo').disabled = !this.redoStack.length;
  }

  renderVersions() {
    const p = this.project;
    $('#cp-versions').innerHTML = `<span class="cp-barlabel">Armonia</span>
      ${p.order.map((v) => `<button class="cp-vtab ${v === p.active ? 'active' : ''}" data-v="${v}" title="${p.versions[v].clips.length} accordi · ${p.versions[v].bars} battute">${v}</button>`).join('')}
      <button class="btn small" data-act="dup" title="Duplica la versione corrente">＋ Duplica</button>
      <button class="btn small" data-act="vary" title="Variazioni degli accordi: riarmonizzazione, ritmo armonico, voicing, finali">✦ Varia armonia…</button>
      ${this.melNotes.length && this.ui.view === 'harmony' ? '<button class="btn small" data-act="harm" title="Nuove versioni con gli accordi ricavati dalla melodia">♫ Armonizza la melodia…</button>' : ''}
      ${p.order.length > 1 ? '<button class="btn small" data-act="del" title="Elimina la versione corrente">✕</button>' : ''}`;
  }

  get pxStep() { return this._pxStep || 10; }

  renderTimeline() {
    const s = this.seq;
    const wrap = $('#cp-tlwrap');
    const steps = s.bars * 16;
    this._pxStep = Math.max(5, (wrap.clientWidth - 24) / steps);
    const W = steps * this._pxStep;
    $('#cp-tl').style.width = `${W}px`;
    const bar = 16 * this._pxStep;
    $('#cp-ruler').innerHTML = Array.from({ length: s.bars }, (_, i) =>
      `<div class="cp-bar" style="left:${i * bar}px;width:${bar}px">${i + 1}</div>`).join('');
    const lane = $('#cp-lane');
    lane.style.backgroundSize = `${bar}px 100%, ${bar / 4}px 100%`;
    const flats = keyFlats(s.key);
    lane.innerHTML = this.sorted().map((c) => {
      const st = c.style;
      const badge = st ? (STYLE_BADGE[st.play?.type] || '') + (st.rhythm === 'sustain' ? '—' : typeof st.rhythm === 'object' ? '♪' : '') || '•' : '';
      const color = FUNC_COLOR[c.func] || '#888';
      const tr = c.transpose ? ` <span class="cp-tr">${c.transpose > 0 ? '+' : ''}${c.transpose}</span>` : '';
      return `<div class="cp-clip ${this.sel.has(c.id) ? 'sel' : ''} ${this.primary === c.id ? 'primary' : ''}" data-id="${c.id}"
          style="left:${c.start * this._pxStep}px;width:${Math.max(4, c.len * this._pxStep - 2)}px;--fc:${color}">
        <div class="cp-clip-head"><span class="cp-deg" style="--fc:${color}">${esc(c.degree || '?')}</span>
          <span class="cp-clip-name">${esc(transposeName(c.name, c.transpose || 0, flats))}${tr}</span>
          ${badge ? `<span class="cp-badge" title="Esecuzione propria">${badge}</span>` : ''}</div>
        ${this._roll(c)}
        <div class="cp-resize" title="Trascina per cambiare la durata"></div>
      </div>`;
    }).join('') + '<div class="cp-drop" id="cp-drop" hidden></div>';
    if (!s.clips.length) lane.insertAdjacentHTML('beforeend', this.ui.view === 'melody'
      ? '<div class="cp-lane-empty">Nessun accordo: scrivi la melodia qui sotto e usa «Armonizza», oppure aggiungi accordi dalla colonna a sinistra.</div>'
      : '<div class="cp-lane-empty">Trascina qui un accordo o una progressione dalla colonna a sinistra, oppure usa i suggerimenti qui sotto.</div>');
    this.renderRhythm();
    this.renderRoll();
  }

  // ---------------------------------------------------------------- Modalità: tabs + rhythm grid
  renderModes() {
    const p = this.project;
    const g = this.mode.rhythm;
    const presets = this.meta.styles.presets;
    $('#cp-modes').innerHTML = `<span class="cp-barlabel">Modalità</span>
      ${p.modeOrder.map((k) => `<button class="cp-vtab cp-mtab ${k === p.modeActive ? 'active' : ''}" data-m="${k}" title="Doppio clic: rinomina">${esc(p.modes[k].name || k)}</button>`).join('')}
      <button class="btn small" data-mact="dup" title="Duplica la modalità corrente">＋ Duplica</button>
      <button class="btn small" data-mact="vary" title="Variazioni della ritmica e del modo di suonare">✦ Varia modalità…</button>
      ${p.modeOrder.length > 1 ? '<button class="btn small" data-mact="del" title="Elimina la modalità corrente">✕</button>' : ''}
      <span class="cp-sep"></span>
      <span class="cp-barlabel">Ritmica</span>
      <select id="cp-preset" class="cp-select" title="Parti da un preset e modificalo sulla griglia">
        <option value="">${g.preset ? 'Preset…' : '— personalizzata —'}</option>
        ${presets.map(([k, l]) => `<option value="${k}" ${k === g.preset ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>
      <select id="cp-rbars" class="cp-select" title="Lunghezza della ritmica (si ripete)">${[1, 2, 4].map((b) => `<option value="${b}" ${b === g.bars ? 'selected' : ''}>${b} ${b === 1 ? 'battuta' : 'battute'}</option>`).join('')}</select>
      <button class="btn small ${g.on ? '' : 'active'}" data-mact="toggle" title="Spenta: ogni accordo suona una volta e resta tenuto">${g.on ? 'Ritmica attiva' : 'Accordi tenuti'}</button>
      <button class="btn small" data-mact="rclear">Svuota</button>`;
  }

  _autoDir(g, j) {
    const sixteenth = g.vel.some((v, k) => v && k % 2);
    return (sixteenth ? j % 2 === 0 : j % 4 === 0) ? 'd' : 'u';
  }

  renderRhythm() {
    const lane = $('#cp-rlane');
    if (!lane || !this.project) return;
    const g = this.mode.rhythm;
    const n = g.vel.length;
    const steps = this.seq.bars * 16;
    const px = this.pxStep;
    const play = this.mode.play;
    const strum = play.type === 'strum' || (play.alternate?.every !== 'off' && play.alternate?.tokens?.some((t) => t.startsWith('strum')));
    const arrows = strum && ['grid', 'guitar'].includes(play.strum?.dir);
    const cells = [];
    for (let s = 0; s < steps; s++) {
      const j = s % n;
      const v = g.vel[j];
      const cls = `cp-rcell${s >= n ? ' ghost' : ''}${s % 4 === 0 ? ' beat' : ''}${s % 16 === 0 ? ' bar' : ''}${v ? ' on' : ''}`;
      let inner = '';
      if (v) {
        const len = g.len[j] ? `<i class="cp-rlen" style="width:${g.len[j] * px - 2}px"></i>` : '';
        const dir = arrows ? (play.strum.dir === 'grid' ? g.dir[j] || this._autoDir(g, j) : this._autoDir(g, j)) : '';
        inner = `<b style="height:${Math.round((v / 127) * 100)}%"></b>${len}${dir ? `<em>${dir === 'd' ? '↓' : '↑'}</em>` : ''}`;
      }
      cells.push(`<div class="${cls}" style="left:${s * px}px;width:${Math.max(1, px - 1)}px">${inner}</div>`);
    }
    lane.classList.toggle('off', !g.on);
    lane.innerHTML = cells.join('') + (g.on ? '' : '<div class="cp-rlane-off">Accordi tenuti · clicca uno step o scegli un preset per dare un ritmo alla progressione</div>');
  }

  _onRhythmDown(e) {
    if (e.button !== 0) return;
    const r = $('#cp-rlane').getBoundingClientRect();
    const s = Math.floor((e.clientX - r.left) / this.pxStep);
    if (s < 0 || s >= this.seq.bars * 16) return;
    this.edit(() => {
      const g = this.mode.rhythm;
      const j = s % g.vel.length;
      if (!g.on) {
        g.on = true;
        if (!e.shiftKey && !e.altKey) { g.vel = g.vel.map(() => 0); }
      }
      if (e.shiftKey) {
        if (!g.vel[j]) g.vel[j] = 100;
        const st = this.mode.play.strum;
        if (st.dir !== 'grid') { g.dir = g.dir.map((d, k) => d || (g.vel[k] ? this._autoDir(g, k) : '')); st.dir = 'grid'; }
        if (this.mode.play.type !== 'strum') this.mode.play.type = 'strum';
        g.dir[j] = (g.dir[j] || this._autoDir(g, j)) === 'd' ? 'u' : 'd';
      } else if (e.altKey) {
        if (!g.vel[j]) g.vel[j] = 100;
        g.len[j] = LEN_CYCLE[(LEN_CYCLE.indexOf(g.len[j]) + 1) % LEN_CYCLE.length];
      } else {
        const i = VEL_CYCLE.indexOf(g.vel[j]);
        g.vel[j] = i < 0 ? 0 : VEL_CYCLE[(i + 1) % VEL_CYCLE.length];
        if (!g.vel[j]) { g.len[j] = 0; g.dir[j] = ''; }
      }
      g.preset = null;
    }, { redraw: false });
    this.renderModes();
    this.renderRhythm();
  }

  addMode(mode, label) {
    const used = new Set(this.project.modeOrder);
    let k = 1;
    while (used.has(String(k))) k++;
    const id = String(k);
    this.edit(() => {
      this.project.modes[id] = { ...clone(mode), name: mode.name && !label ? mode.name : `Modalità ${id}` };
      const i = this.project.modeOrder.indexOf(this.project.modeActive);
      this.project.modeOrder.splice(i + 1, 0, id);
      this.project.modeActive = id;
    });
    if (label) toast(`Modalità ${id}: ${label}`);
  }

  deleteMode() {
    const p = this.project;
    if (p.modeOrder.length < 2) return;
    if (!confirm(`Eliminare la modalità "${this.mode.name}"?`)) return;
    this.edit(() => {
      const i = p.modeOrder.indexOf(p.modeActive);
      delete p.modes[p.modeActive];
      p.modeOrder.splice(i, 1);
      p.modeActive = p.modeOrder[Math.max(0, i - 1)];
    });
  }

  _roll(c) {
    const ev = this.rendered.byId[c.id];
    const t0 = c.start * STEP_TICKS;
    const span = c.len * STEP_TICKS;
    if (!ev?.length) return '<svg class="cp-roll"></svg>';
    const ps = ev.map((e) => e[2]);
    const lo = Math.min(...ps) - 1, hi = Math.max(...ps) + 1;
    const h = 100 / (hi - lo + 1);
    const rects = ev.map((e) => {
      const x = ((e[0] - t0) / span) * 100, w = Math.max(0.4, ((e[1] - e[0]) / span) * 100);
      const y = (hi - e[2]) * h;
      return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${w.toFixed(2)}" height="${Math.max(1.5, h * 0.8).toFixed(2)}" opacity="${(0.35 + 0.65 * e[3] / 127).toFixed(2)}"/>`;
    }).join('');
    return `<svg class="cp-roll" viewBox="0 0 100 100" preserveAspectRatio="none">${rects}</svg>`;
  }

  _stepAt(clientX) {
    const r = $('#cp-lane').getBoundingClientRect();
    const raw = (clientX - r.left) / this.pxStep;
    return Math.max(0, Math.round(raw / this.ui.snap) * this.ui.snap);
  }

  _dropMarker(e) {
    const m = $('#cp-drop');
    if (!m) return;
    if (!e) { m.hidden = true; return; }
    m.hidden = false;
    m.style.left = `${this._stepAt(e.clientX) * this.pxStep}px`;
  }

  _onLaneDown(e) {
    if (e.button !== 0) return;
    const el = e.target.closest('.cp-clip');
    if (!el) {
      if (this.sel.size) { this._select(null); this.renderTimeline(); this.renderInspector(); this.refresh(); }
      return;
    }
    const c = this.clip(el.dataset.id);
    const resize = !!e.target.closest('.cp-resize');
    const x0 = e.clientX;
    const orig = { start: c.start, len: c.len };
    let moved = false;
    let cur = { ...orig };
    const snap = this.ui.snap;
    el.setPointerCapture(e.pointerId);
    const onMove = (ev) => {
      const d = (ev.clientX - x0) / this.pxStep;
      if (!moved && Math.abs(ev.clientX - x0) < 4) return;
      moved = true;
      if (resize) {
        const end = Math.max(orig.start + snap, Math.round((orig.start + orig.len + d) / snap) * snap);
        cur = { start: orig.start, len: Math.max(1, end - orig.start) };
      } else {
        cur = { start: Math.max(0, Math.round((orig.start + d) / snap) * snap), len: orig.len };
      }
      el.style.left = `${cur.start * this.pxStep}px`;
      el.style.width = `${Math.max(4, cur.len * this.pxStep - 2)}px`;
      el.classList.add('dragging');
    };
    const onUp = () => {
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerup', onUp);
      if (moved && (cur.start !== orig.start || cur.len !== orig.len)) {
        this.edit(() => { Object.assign(c, cur); this._resolve(c.id); this._select(c.id); });
      } else {
        this._select(c.id, e.shiftKey || e.metaKey);
        this.renderTimeline();
        this.renderInspector();
        this.refresh();
        if (!moved) this.synth.chord(this._voiced(c), 0.6);
      }
    };
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerup', onUp);
  }

  // block voicing of a clip (for a quick click preview, before python renders the styled version)
  _voiced(c) {
    let n = c.notes.map(([p, v]) => [p, v]).sort((a, b) => a[0] - b[0]);
    const inv = c.inversion || 0;
    for (let i = 0; i < Math.abs(inv); i++) {
      if (inv > 0) { const x = n.shift(); n.push([x[0] + 12, x[1]]); } else { const x = n.pop(); n.unshift([x[0] - 12, x[1]]); }
    }
    const sh = (c.transpose || 0) + 12 * (c.octave || 0);
    return n.map(([p, v]) => [p + sh, Math.round(v * (c.vel || 100) / 100)]);
  }

  // ---------------------------------------------------------------- inspector
  renderInspector() {
    const box = $('#cp-insp');
    const c = this.clip(this.primary);
    const multi = this.sel.size > 1;
    const mode = this.mode;
    if (!c) {
      const st = { play: mergeStyle(this.meta.styles.defaultPlay, mode.play), swing: mode.swing };
      box.innerHTML = `<div class="cp-sec-title"><span>Modalità <b>${esc(mode.name)}</b>: come si suona</span><span class="hint">vale per tutti gli accordi senza esecuzione propria</span></div>
        ${this._playEditor(st, { swing: true })}`;
      this._bindPlayEditor(box, st, (n) => this.edit(() => { mode.play = n.play; mode.swing = n.swing; }));
      return;
    }
    const locked = this.seq.keyMode === 'locked';
    const own = !!c.style;
    const src = c.srcKey ? keyName(c.srcKey) : '';
    const st = own ? { play: mergeStyle(mode.play, c.style.play), rhythm: c.style.rhythm ?? 'inherit' } : null;
    const rsel = !st ? '' : typeof st.rhythm === 'object' ? `preset:${st.rhythm.preset || ''}` : st.rhythm;
    box.innerHTML = `
      <div class="cp-sec-title"><span><span class="cp-deg" style="--fc:${FUNC_COLOR[c.func] || '#888'}">${esc(c.degree || '?')}</span>
        <b>${esc(this.displayName(c))}</b>${multi ? ` <span class="hint">+ altri ${this.sel.size - 1} selezionati</span>` : ''}</span>
        <span class="hint">${esc(FUNC_LABEL[c.func] || '')}${src ? ` · da ${esc(src)}` : ''}</span></div>
      <div class="cp-props">
        <div class="cp-prop" title="${locked ? 'Tonalità bloccata: passa a Libera per trasporre il singolo accordo' : 'Trasposizione in semitoni'}">Trasposizione
          <span class="cp-step"><button data-p="transpose" data-d="-1" ${locked ? 'disabled' : ''}>−</button><span>${c.transpose > 0 ? '+' : ''}${c.transpose || 0}</span><button data-p="transpose" data-d="1" ${locked ? 'disabled' : ''}>+</button></span></div>
        <div class="cp-prop">Ottava<span class="cp-step"><button data-p="octave" data-d="-1">−</button><span>${c.octave > 0 ? '+' : ''}${c.octave || 0}</span><button data-p="octave" data-d="1">+</button></span></div>
        <div class="cp-prop">Rivolto<span class="cp-step"><button data-p="inversion" data-d="-1">−</button><span>${c.inversion || 0}</span><button data-p="inversion" data-d="1">+</button></span></div>
        <div class="cp-prop">Velocity <input type="range" min="30" max="130" step="5" value="${c.vel || 100}" data-vel><span class="hint">${c.vel || 100}%</span></div>
        <div class="cp-prop">Durata <span>${this._fmtLen(c.len)}</span></div>
      </div>
      <div class="cp-actions">
        <button class="btn small primary" data-act="vary" title="Voicing, colore e sostituzioni dell'accordo (V)">✦ Varia armonia…</button>
        <button class="btn small" data-act="dup" title="Duplica (⌘D)">Duplica</button>
        <button class="btn small" data-act="del" title="Elimina (Canc)">Elimina</button>
      </div>
      <div class="cp-sec-title"><span>Esecuzione</span>
        <label class="cp-own"><input type="checkbox" data-own ${own ? 'checked' : ''}> propria${multi ? ' (tutti i selezionati)' : ''}</label></div>
      ${own ? `<div class="cp-srow"><span>Ritmica</span><select class="cp-select" data-rsel>
          <option value="inherit" ${rsel === 'inherit' ? 'selected' : ''}>quella della modalità</option>
          <option value="sustain" ${rsel === 'sustain' ? 'selected' : ''}>tenuto (un colpo)</option>
          ${this.meta.styles.presets.map(([k, l]) => `<option value="preset:${k}" ${rsel === `preset:${k}` ? 'selected' : ''}>${esc(l)}</option>`).join('')}
          ${rsel === 'preset:' ? '<option value="preset:" selected>personalizzata</option>' : ''}</select></div>
        ${this._playEditor(st, { swing: false })}`
        : `<div class="hint">Suona come la modalità <b>${esc(mode.name)}</b>. Attiva "propria" per suonare questo accordo diversamente (altro strum, arpeggio, tenuto…).</div>`}`;
    box.querySelectorAll('[data-p]').forEach((b) => {
      b.onclick = () => this.edit(() => {
        for (const x of this._selClips()) {
          const p = b.dataset.p, d = +b.dataset.d;
          const lim = p === 'transpose' ? 12 : p === 'octave' ? 2 : 4;
          x[p] = Math.max(-lim, Math.min(lim, (x[p] || 0) + d));
        }
      });
    });
    const vel = box.querySelector('[data-vel]');
    vel.oninput = () => { vel.nextElementSibling.textContent = `${vel.value}%`; };
    vel.onchange = () => this.edit(() => { for (const x of this._selClips()) x.vel = +vel.value; });
    box.querySelector('[data-act="vary"]').onclick = () => this.clipVariations(c.id);
    box.querySelector('[data-act="dup"]').onclick = () => this.duplicateSelected();
    box.querySelector('[data-act="del"]').onclick = () => this.deleteSelected();
    box.querySelector('[data-own]').onchange = (e) => this.edit(() => {
      for (const x of this._selClips()) x.style = e.target.checked ? { play: clone(mode.play), rhythm: 'inherit' } : null;
    });
    if (!own) return;
    box.querySelector('[data-rsel]').onchange = (e) => this.edit(() => {
      const v = e.target.value;
      const rhythm = v.startsWith('preset:') ? fixGrid(this.meta.styles.presetGrids[v.slice(7)] || st.rhythm) : v;
      for (const x of this._selClips()) x.style = { ...(x.style || {}), rhythm: clone(rhythm) };
    });
    this._bindPlayEditor(box, st, (n) => this.edit(() => { for (const x of this._selClips()) x.style = { play: clone(n.play), rhythm: clone(n.rhythm) }; }));
  }

  _selClips() { return this.seq.clips.filter((c) => this.sel.has(c.id)); }

  _fmtLen(len) {
    const bars = Math.floor(len / 16), rest = len % 16;
    const parts = [];
    if (bars) parts.push(`${bars} ${bars === 1 ? 'battuta' : 'battute'}`);
    if (rest) parts.push(rest % 4 === 0 ? `${rest / 4}/4` : `${rest}/16`);
    return parts.join(' + ');
  }

  // st: {play, swing?, rhythm?}; every control edits a path of st
  _playEditor(st, { swing }) {
    const m = this.meta.styles;
    const p = st.play;
    const opt = (list, v) => list.map(([k, l]) => `<option value="${k}" ${String(k) === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('');
    const seg = (name, list, v) => `<div class="seg cp-seg">${list.map(([k, l]) => `<button class="seg-btn ${String(k) === String(v) ? 'active' : ''}" data-s="${name}" data-v="${k}">${esc(l)}</button>`).join('')}</div>`;
    const range = (name, min, max, step, v, unit = '', title = '') => `<span class="cp-range" title="${esc(title)}"><input type="range" data-r="${name}" min="${min}" max="${max}" step="${step}" value="${v}"><span>${v}${unit}</span></span>`;
    const row = (label, html, title = '') => `<div class="cp-srow" title="${esc(title)}"><span>${label}</span>${html}</div>`;
    const strumUsed = p.type === 'strum' || (p.alternate.every !== 'off' && p.alternate.tokens.some((t) => t.startsWith('strum')));
    const s = p.strum, h = p.humanize;
    const tokLabel = Object.fromEntries(m.tokens);
    return `<div class="cp-style">
      ${seg('play.type', m.types, p.type)}
      ${row('Durata note', range('play.gate', 25, 100, 5, Math.round(p.gate * 100), '%'), 'Quanto dura ogni colpo rispetto allo spazio fino al successivo')}
      ${swing ? row('Swing', range('swing', 50, 75, 1, st.swing, '', '50 = dritto, 66 = terzinato, 75 = shuffle pesante (sui sedicesimi in levare)')) : ''}
      ${p.type === 'arp' ? row('Arpeggio', `<select data-sel="play.arp.mode" class="cp-select">${opt(m.arpModes, p.arp.mode)}</select>
          <select data-sel="play.arp.rate" class="cp-select">${opt(m.rates.map((r) => [r, r]), p.arp.rate)}</select>
          ${seg('play.arp.octaves', [[1, '1 ott.'], [2, '2 ott.']], p.arp.octaves)}`) : ''}
      ${strumUsed ? `<div class="cp-subtitle">Strum</div>
        ${row('Direzione', `<select data-sel="play.strum.dir" class="cp-select">${opt(m.strumDirs, s.dir)}</select>`, 'Chitarra: pennata giù sui battere e su in levare. Frecce: ⇧+clic sugli step della ritmica')}
        ${row('Velocità', `${s.unit === 'ms' ? range('play.strum.spread', 3, 90, 1, s.spread, ' ms', 'Tempo tra una nota e la successiva') : ''}
            <select data-sel="play.strum.unit" class="cp-select" title="In millisecondi o in valore musicale (segue il BPM)">${opt(m.strumUnits.map((u) => [u, u === 'ms' ? 'ms' : u]), s.unit)}</select>`)}
        ${row('Curva', `<select data-sel="play.strum.curve" class="cp-select">${opt(m.strumCurves, s.curve)}</select>`, 'Accelera: le ultime corde arrivano più ravvicinate, come una pennata vera')}
        ${row('Pennata su', `<select data-sel="play.strum.upNotes" class="cp-select" title="Nelle pennate dall'alto suonano solo le note più acute">${opt([[0, 'tutte le note'], [2, '2 note alte'], [3, '3 note alte'], [4, '4 note alte']], s.upNotes)}</select>
            ${range('play.strum.upSoft', 0, 60, 5, s.upSoft, '% più piano', 'Le pennate dall\'alto sono più deboli')}`)}
        ${row('Inclinazione', range('play.strum.velTilt', -40, 40, 5, s.velTilt, '%', 'Negativo: la prima nota più forte; positivo: l\'ultima più forte'))}` : ''}
      <div class="cp-subtitle">Humanize <button class="icon-btn small" data-dice title="Nuova umanizzazione (stesse quantità, altro caso)">🎲</button></div>
      ${row('Timing', range('play.humanize.timing', 0, 40, 1, h.timing, ' ms', 'Spostamento casuale di ogni colpo (tutte le note insieme)'))}
      ${row('Note accordo', range('play.humanize.spread', 0, 25, 1, h.spread, ' ms', 'Le note dello stesso colpo non partono esattamente insieme'))}
      ${row('Feel', range('play.humanize.feel', -25, 25, 1, h.feel, ' ms', 'Negativo: in anticipo (spinge) · positivo: in ritardo (laid back)'))}
      ${row('Deriva', range('play.humanize.drift', 0, 100, 5, h.drift, '%', '0: ogni colpo varia per conto suo · 100: il timing ondeggia lentamente, come un musicista'))}
      ${row('Velocity', range('play.humanize.vel', 0, 30, 1, h.vel, ''))}
      ${row('Durate', range('play.humanize.len', 0, 40, 5, h.len, '%', 'Variazione casuale della lunghezza delle note'))}
      ${row('Accenti', range('play.humanize.accent', 0, 40, 5, h.accent, '%', 'Più forte sul primo e sui battere, più leggero in levare'))}
      <div class="cp-subtitle">Dinamica e alternanza</div>
      ${row('Dinamica', `<select data-sel="play.velCurve" class="cp-select">${opt(m.velCurves, p.velCurve)}</select>`)}
      ${row('Alterna', `<select data-sel="play.alternate.every" class="cp-select">${opt([['off', 'no'], ['hit', 'a ogni colpo'], ['bar', 'a ogni battuta']], p.alternate.every)}</select>
        ${p.alternate.every !== 'off' ? `<span class="cp-tokens">${p.alternate.tokens.map((t, i) => `<span class="chip on" data-tokdel="${i}" title="Rimuovi">${esc(tokLabel[t] || t)} ×</span>`).join('') || '<span class="hint">aggiungi:</span>'}</span>
          <span class="cp-tokadd">${m.tokens.filter(([t]) => p.alternate.every === 'bar' || t !== 'arp').map(([t, l]) => `<button class="chip" data-tokadd="${t}">+ ${esc(l)}</button>`).join('')}</span>` : ''}`)}
    </div>`;
  }

  _bindPlayEditor(box, st, commit) {
    const setPath = (o, path, v) => { const ks = path.split('.'); let x = o; for (const k of ks.slice(0, -1)) x = x[k]; x[ks.at(-1)] = v; };
    const ed = box.querySelector('.cp-style');
    if (!ed) return;
    const num = (v) => (v !== '' && !Number.isNaN(+v) ? +v : v);
    ed.querySelectorAll('[data-s]').forEach((b) => {
      b.onclick = () => { const n = clone(st); setPath(n, b.dataset.s, num(b.dataset.v)); commit(n); };
    });
    ed.querySelectorAll('[data-sel]').forEach((sel) => {
      sel.onchange = () => {
        const n = clone(st);
        setPath(n, sel.dataset.sel, num(sel.value));
        if (sel.dataset.sel === 'play.alternate.every' && sel.value !== 'off' && !n.play.alternate.tokens.length) {
          n.play.alternate.tokens = sel.value === 'bar' ? ['block', 'strum_up'] : ['strum_up', 'strum_down'];
        }
        commit(n);
      };
    });
    ed.querySelectorAll('[data-r]').forEach((r) => {
      const unit = r.nextElementSibling.textContent.replace(/^-?[\d.]+/, '');
      r.oninput = () => { r.nextElementSibling.textContent = r.value + unit; };
      r.onchange = () => { const n = clone(st); setPath(n, r.dataset.r, r.dataset.r === 'play.gate' ? +r.value / 100 : +r.value); commit(n); };
    });
    ed.querySelector('[data-dice]').onclick = () => {
      const n = clone(st);
      const h = n.play.humanize;
      h.seed = 1 + Math.floor(Math.random() * 1e9);
      if (!h.timing && !h.vel && !h.spread) { h.timing = 8; h.spread = 4; h.vel = 8; }
      commit(n);
    };
    ed.querySelectorAll('[data-tokdel]').forEach((b) => { b.onclick = () => { const n = clone(st); n.play.alternate.tokens.splice(+b.dataset.tokdel, 1); commit(n); }; });
    ed.querySelectorAll('[data-tokadd]').forEach((b) => { b.onclick = () => { const n = clone(st); n.play.alternate.tokens.push(b.dataset.tokadd); commit(n); }; });
  }

  // ---------------------------------------------------------------- variations
  _modal(title, body) {
    document.querySelector('.cp-modal')?.remove();
    const m = document.createElement('div');
    m.className = 'modal cp-modal';
    m.innerHTML = `<div class="modal-box cp-modal-box"><div class="cp-modal-head"><h3>${title}</h3><button class="icon-btn" data-close>✕</button></div>${body}</div>`;
    document.body.appendChild(m);
    const close = () => { m.remove(); document.removeEventListener('keydown', onKey, true); this.stop(); };
    const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
    document.addEventListener('keydown', onKey, true);
    m.addEventListener('pointerdown', (e) => { if (e.target === m) close(); });
    m.querySelector('[data-close]').onclick = close;
    m.close = close;
    return m;
  }

  async clipVariations(id) {
    const c = this.clip(id);
    if (!c) return;
    const kinds = this.meta.clipKinds;
    const m = this._modal(`Varia armonia: ${esc(this.displayName(c))}`, `
      <div class="cp-vtools"><div class="chips" data-kinds>${kinds.map(([k, l]) => `<button class="chip ${this.clipKinds.includes(k) ? 'on' : ''}" data-kind="${k}">${esc(l)}</button>`).join('')}</div>
        <button class="btn small" data-gen>🎲 Altre proposte</button></div>
      <div class="cp-vlist" data-list><div class="hint">Genero…</div></div>
      <div class="hint">▶ ascolta nel contesto (dalla battuta prima) · Usa: sostituisce l'accordo (annullabile con ⌘Z)</div>`);
    let seed = 1 + Math.floor(Math.random() * 1e6);
    const load = async () => {
      m.querySelector('[data-list]').innerHTML = '<div class="hint">Genero…</div>';
      const res = await this.api.compose_vary_clip(this.playSeq, id, this.clipKinds, seed);
      this._clipProposals = res || [];
      const groups = Object.fromEntries(kinds);
      m.querySelector('[data-list]').innerHTML = this._clipProposals.map((p, i) => `
        <div class="cp-vrow"><span class="cp-vkind">${esc(groups[p.kind] || p.kind)}</span><span class="cp-vlabel">${esc(p.label)}</span>
          <button class="icon-btn small" data-play="${i}" title="Ascolta nel contesto">▶</button>
          <button class="btn small primary" data-use="${i}">Usa</button></div>`).join('') || '<div class="hint">Nessuna variazione per questi tipi.</div>';
    };
    m.querySelector('[data-kinds]').onclick = (e) => {
      const b = e.target.closest('[data-kind]'); if (!b) return;
      const k = b.dataset.kind;
      this.clipKinds = this.clipKinds.includes(k) ? this.clipKinds.filter((x) => x !== k) : [...this.clipKinds, k];
      b.classList.toggle('on', this.clipKinds.includes(k));
      load();
    };
    m.querySelector('[data-gen]').onclick = () => { seed++; load(); };
    m.querySelector('[data-list]').onclick = async (e) => {
      const play = e.target.closest('[data-play]');
      const use = e.target.closest('[data-use]');
      if (play) {
        const p = this._clipProposals[+play.dataset.play];
        const seq = clone(this.playSeq);
        seq.clips = seq.clips.map((x) => (x.id === id ? { ...p.clip, id } : x));
        const res = await this.api.compose_render(seq);
        const cur = this.clip(id);
        this.playRange(Math.max(0, cur.start - 16) * STEP_TICKS, (cur.start + cur.len) * STEP_TICKS, this._events(res));
      } else if (use) {
        const p = this._clipProposals[+use.dataset.use];
        this.edit(() => {
          const i = this.seq.clips.findIndex((x) => x.id === id);
          this.seq.clips[i] = { ...p.clip, id, degree: undefined, func: undefined };
        });
        m.close();
      }
    };
    load();
  }

  async progressionVariations() {
    if (!this.seq.clips.length) { toast('Aggiungi prima qualche accordo'); return; }
    const kinds = this.meta.progKinds;
    const m = this._modal(`Varia armonia: versione ${this.project.active}`, `
      <div class="cp-vtools"><div class="chips" data-kinds>${kinds.map(([k, l]) => `<button class="chip ${this.progKinds.includes(k) ? 'on' : ''}" data-kind="${k}">${esc(l)}</button>`).join('')}</div></div>
      <div class="cp-vtools"><label class="cp-field">Quanto variare <input type="range" min="10" max="100" step="5" value="${this.ui.amount || 50}" data-amount></label>
        <button class="btn small primary" data-gen>🎲 Genera</button></div>
      <div class="cp-vlist" data-list></div>
      <div class="hint">Tieni: diventa una nuova versione (A, B, C…) modificabile · Accoda: la aggiunge alla fine della progressione (A A' …)</div>`);
    let seed = 1 + Math.floor(Math.random() * 1e6);
    const load = async () => {
      m.querySelector('[data-list]').innerHTML = '<div class="hint">Genero…</div>';
      const res = await this.api.compose_vary_progression(this.playSeq, this.progKinds, (this.ui.amount || 50) / 100, seed);
      this._progProposals = res || [];
      m.querySelector('[data-list]').innerHTML = this._progProposals.map((p, i) => `
        <div class="cp-vrow cp-vprog"><div class="cp-vmain"><span class="cp-vlabel">${esc(p.label)}</span>${this._miniTimeline(p.seq)}</div>
          <button class="icon-btn small" data-play="${i}" title="Ascolta">▶</button>
          <button class="btn small primary" data-keep="${i}">Tieni</button>
          <button class="btn small" data-append="${i}">Accoda</button></div>`).join('') || '<div class="hint">Nessuna variazione possibile con questi tipi (servono almeno 2–3 accordi).</div>';
    };
    m.querySelector('[data-kinds]').onclick = (e) => {
      const b = e.target.closest('[data-kind]'); if (!b) return;
      const k = b.dataset.kind;
      this.progKinds = this.progKinds.includes(k) ? this.progKinds.filter((x) => x !== k) : [...this.progKinds, k];
      b.classList.toggle('on', this.progKinds.includes(k));
    };
    m.querySelector('[data-amount]').onchange = (e) => { this.ui.amount = +e.target.value; this._persist(); };
    m.querySelector('[data-gen]').onclick = () => { seed++; load(); };
    m.querySelector('[data-list]').onclick = async (e) => {
      const b = e.target.closest('[data-play],[data-keep],[data-append]'); if (!b) return;
      const p = this._progProposals[+(b.dataset.play ?? b.dataset.keep ?? b.dataset.append)];
      if (b.dataset.play !== undefined) {
        if (this.transport.playing) { this.stop(); return; }
        const res = await this.api.compose_render(p.seq);
        this.playRange(0, p.seq.bars * 16 * STEP_TICKS, this._events(res));
      } else if (b.dataset.keep !== undefined) {
        this.stop();
        this.addVersion(this._freshIds(this._harmonyOf(p.seq)), p.label);
        m.close();
      } else {
        this.stop();
        this.edit(() => {
          const off = Math.ceil(this._end() / 16) * 16;
          for (const c of this._freshIds(clone(p.seq)).clips) this.seq.clips.push({ ...c, start: c.start + off });
          this._fitBars();
        });
        toast(`Accodata: ${p.label}`);
        m.close();
      }
    };
    load();
  }

  // a proposal comes back with the playing fields of playSeq: keep only the harmony
  _harmonyOf(seq) {
    const { mode, bpm, name, ...h } = clone(seq);
    void mode; void bpm; void name;
    return h;
  }

  async modeVariations() {
    const kinds = this.meta.modeKinds;
    const m = this._modal(`Varia modalità: ${esc(this.mode.name)}`, `
      <div class="cp-vtools"><div class="chips" data-kinds>${kinds.map(([k, l]) => `<button class="chip ${this.modeKinds.includes(k) ? 'on' : ''}" data-kind="${k}">${esc(l)}</button>`).join('')}</div></div>
      <div class="cp-vtools"><label class="cp-field">Quanto variare <input type="range" min="10" max="100" step="5" value="${this.ui.modeAmount || 50}" data-amount></label>
        <button class="btn small primary" data-gen>🎲 Genera</button></div>
      <div class="cp-vlist" data-list></div>
      <div class="hint">Gli accordi non cambiano. ▶ ascolta · Usa: sostituisce la modalità corrente (⌘Z per tornare indietro) · Tieni: la aggiunge come nuova modalità</div>`);
    let seed = 1 + Math.floor(Math.random() * 1e6);
    const load = async () => {
      m.querySelector('[data-list]').innerHTML = '<div class="hint">Genero…</div>';
      const res = await this.api.compose_vary_mode(this.mode, this.modeKinds, (this.ui.modeAmount || 50) / 100, seed);
      this._modeProposals = res || [];
      const names = Object.fromEntries(kinds);
      m.querySelector('[data-list]').innerHTML = this._modeProposals.map((p, i) => `
        <div class="cp-vrow cp-vprog"><div class="cp-vmain"><span class="cp-vlabel"><span class="cp-vkind">${esc(names[p.kind] || p.kind)}</span> ${esc(p.label)}</span>${this._miniGrid(p.mode)}</div>
          <button class="icon-btn small" data-play="${i}" title="Ascolta">▶</button>
          <button class="btn small primary" data-use="${i}">Usa</button>
          <button class="btn small" data-keep="${i}">Tieni</button></div>`).join('') || '<div class="hint">Nessuna variazione con questi tipi.</div>';
    };
    m.querySelector('[data-kinds]').onclick = (e) => {
      const b = e.target.closest('[data-kind]'); if (!b) return;
      const k = b.dataset.kind;
      this.modeKinds = this.modeKinds.includes(k) ? this.modeKinds.filter((x) => x !== k) : [...this.modeKinds, k];
      b.classList.toggle('on', this.modeKinds.includes(k));
    };
    m.querySelector('[data-amount]').onchange = (e) => { this.ui.modeAmount = +e.target.value; this._persist(); };
    m.querySelector('[data-gen]').onclick = () => { seed++; load(); };
    m.querySelector('[data-list]').onclick = async (e) => {
      const b = e.target.closest('[data-play],[data-use],[data-keep]'); if (!b) return;
      const p = this._modeProposals[+(b.dataset.play ?? b.dataset.use ?? b.dataset.keep)];
      if (b.dataset.play !== undefined) {
        if (this.transport.playing) { this.stop(); return; }
        const res = await this.api.compose_render(this._playSeq(this.seq, p.mode));
        this.playRange(0, this.seq.bars * 16 * STEP_TICKS, res.events);
      } else if (b.dataset.use !== undefined) {
        this.stop();
        const name = this.mode.name;
        this.edit(() => { this.project.modes[this.project.modeActive] = { ...clone(p.mode), name, rhythm: fixGrid(p.mode.rhythm) }; });
        toast(p.label);
        m.close();
      } else {
        this.stop();
        this.addMode({ ...clone(p.mode), rhythm: fixGrid(p.mode.rhythm) }, p.label);
        m.close();
      }
    };
    load();
  }

  _miniGrid(mode) {
    const g = mode.rhythm;
    if (!g.on) return '<div class="cp-minigrid"><span class="hint">accordi tenuti</span></div>';
    return `<div class="cp-minigrid">${g.vel.map((v, j) => `<i class="${j % 4 === 0 ? 'beat' : ''}" style="opacity:${v ? 0.35 + 0.65 * v / 127 : 0.08}"></i>`).join('')}</div>`;
  }

  _freshIds(seq) {
    seq.clips = seq.clips.map((c) => ({ ...c, id: uid() }));
    return seq;
  }

  _miniTimeline(seq) {
    const total = seq.bars * 16;
    return `<div class="cp-mini">${[...seq.clips].sort((a, b) => a.start - b.start).map((c) =>
      `<span style="left:${(c.start / total) * 100}%;width:${(c.len / total) * 100}%">${esc(c.name)}</span>`).join('')}</div>`;
  }

  // ---------------------------------------------------------------- melody view
  get layers() {
    if (!this.seq.melody?.layers?.length) this.seq.melody = melodyOf(this.seq.melody);
    return this.seq.melody.layers;
  }

  // the layer being edited in the piano roll
  get layer() { return this.layers.find((l) => l.id === this.seq.melody.active) || this.layers[0]; }

  get melNotes() { return this.layer.notes; }

  set melNotes(notes) { this.layer.notes = notes; }

  get hasMelody() { return this.layers.some((l) => l.notes.length); }

  _roleMeta(role) { return this.meta.melody.roles.find((r) => r.id === role) || this.meta.melody.roles[0]; }

  _layerName(role, layers = this.layers) {
    const base = this._roleMeta(role).label;
    for (let i = 1; ; i++) {
      const name = i > 1 ? `${base} ${i}` : base;
      if (!layers.some((l) => l.name === name)) return name;
    }
  }

  // master melody volume x the volume of every layer
  _melVolumes() {
    this.synth.setVolume(this.ui.melVol, 'melody');
    for (const l of this.layers) this.synth.setVolume(this.ui.melVol * (l.vol ?? 1), 'mel:' + l.id);
  }

  // chord events + melody events (clip index MEL, preset and bus of the layer) of a compose_render result
  _events(res) {
    if (this.ui.melMute) return [...res.events];
    const mel = (res.layers || []).flatMap((l) => {
      const cur = this.layers.find((x) => x.id === l.id);
      if (cur ? cur.mute : l.mute) return [];
      return l.events.map((e) => [...e, MEL, ROLE_PRESET[l.role] || 'lead', 'mel:' + l.id]);
    });
    return [...res.events, ...mel];
  }

  get playEvents() { return this._events(this.rendered); }

  setView(v) {
    if (v === this.ui.view) return;
    this.ui.view = v;
    this._persist();
    this.renderAll();
  }

  renderView() {
    const mel = this.ui.view === 'melody';
    $('#cp-tl').classList.toggle('mel', mel);
    $('#cp-proll').hidden = !mel;
    $('#cp-modes').hidden = mel;
    $('#cp-melbar').hidden = !mel;
    $('.cp-bottom').classList.toggle('mel', mel);
    for (const id of ['#cp-sug', '#cp-insp']) $(id).closest('section').hidden = mel;
    $('#cp-mgen').hidden = $('#cp-mharm').hidden = !mel;
    $('#cp-even').hidden = mel;
    $('#cp-tlhint').textContent = mel
      ? 'Clic su uno spazio vuoto: nuova nota (trascina per allungarla) · trascina una nota per spostarla, il bordo destro per allungarla · Alt+trascina: velocity · doppio clic: elimina · ↑↓ trasponi (⇧ ottava) · ←→ sposta · ⌘A tutte'
      : 'Trascina gli accordi sulla timeline · trascina un blocco per spostarlo, il bordo destro per allungarlo · doppio clic: ascolta · V: varia armonia · Canc: elimina';
  }

  renderMelBar() {
    const box = $('#cp-melbar');
    if (!box || this.ui.view !== 'melody') return;
    const L = this.layer, n = this.melNotes.length;
    box.innerHTML = `<span class="cp-barlabel">Layer</span>
      ${this.layers.map((l) => `<span class="cp-layer ${l === L ? 'active' : ''} ${l.mute ? 'muted' : ''}" data-layer="${l.id}" style="--lc:${ROLE_COLOR[l.role] || '#ffb84d'}">
        <button class="cp-lname" data-lsel title="${esc(this._roleMeta(l.role).label)} · ${l.notes.length} note · doppio clic: rinomina">${esc(l.name)}</button>
        <button class="cp-lbtn" data-lmute title="${l.mute ? 'Muto: clic per sentirlo' : 'Silenzia il layer'}">M</button>
        ${this.layers.length > 1 ? '<button class="cp-lbtn" data-ldel title="Elimina il layer">✕</button>' : ''}</span>`).join('')}
      <button class="btn small" data-mel="add" title="Un'altra linea sugli stessi accordi: basso, arpeggio, riff, pad, keys…">＋ Layer ▾</button>
      <span class="cp-sep"></span>
      <span class="hint">${n ? `${n} note` : 'vuoto'}${this.melSel.size ? ` · ${this.melSel.size} selezionate` : ''}</span>
      <button class="btn small" data-mel="import" title="Da file MIDI, da una clip di Ableton o dalla tastiera MIDI">⤓ Importa ▾</button>
      <button class="btn small" data-mel="down" title="Un'ottava sotto (selezione o tutto il layer)" ${n ? '' : 'disabled'}>−8va</button>
      <button class="btn small" data-mel="up" title="Un'ottava sopra (selezione o tutto il layer)" ${n ? '' : 'disabled'}>+8va</button>
      <label class="cp-field" title="Volume del layer «${esc(L.name)}»">Layer <input type="range" min="0" max="1.5" step="0.05" value="${L.vol ?? 1}" data-lvol></label>
      <label class="cp-field" title="Volume di tutti i layer">Tutti <input type="range" min="0" max="1.2" step="0.05" value="${this.ui.melVol}" data-mvol></label>`;
  }

  _melRange() {
    const ps = this.melNotes.map((n) => n.pitch);
    const r = this._roleMeta(this.layer.role);
    const lo = Math.min(r.lo - 3, ...ps.map((p) => p - 2));
    const hi = Math.max(r.hi + 3, ...ps.map((p) => p + 2));
    return { lo: clamp(lo, 0, 127), hi: clamp(hi, 0, 127) };
  }

  renderRoll() {
    const box = $('#cp-proll');
    if (!box || this.ui.view !== 'melody') return;
    const { lo, hi } = (this._mr = this._melRange());
    const px = this.pxStep;
    const bar = 16 * px;
    box.style.height = `${(hi - lo + 1) * ROW_H}px`;
    box.style.backgroundSize = `${bar}px 100%, ${bar / 4}px 100%`;
    const k = this.seq.key;
    const flats = keyFlats(k);
    const scale = new Set(SCALES[k.mode].map((s) => (k.tonic + s) % 12));
    const y = (p) => (hi - p) * ROW_H;
    const html = [];
    for (let p = hi; p >= lo; p--) {
      html.push(`<div class="cp-prow ${scale.has(p % 12) ? 'in' : 'out'} ${p % 12 === k.tonic ? 'tonic' : ''}" style="top:${y(p)}px;height:${ROW_H}px">${p % 12 === 0 ? `<span>C${Math.floor(p / 12) - 1}</span>` : ''}</div>`);
    }
    for (const c of this.seq.clips) { // the notes of the chord under each clip
      const pcs = new Set(this._voiced(c).map(([p]) => ((p % 12) + 12) % 12));
      for (let p = hi; p >= lo; p--) {
        if (pcs.has(p % 12)) html.push(`<div class="cp-ptone" style="left:${c.start * px}px;width:${c.len * px}px;top:${y(p)}px;height:${ROW_H}px;--fc:${FUNC_COLOR[c.func] || '#888'}"></div>`);
      }
    }
    for (const l of this.layers) { // the other layers, behind
      if (l === this.layer || l.mute) continue;
      for (const n of l.notes) {
        if (n.pitch >= lo && n.pitch <= hi) html.push(`<div class="cp-mghost" style="left:${n.start * px}px;width:${Math.max(3, n.len * px - 1)}px;top:${y(n.pitch)}px;height:${ROW_H}px;--lc:${ROLE_COLOR[l.role] || '#ffb84d'}"></div>`);
      }
    }
    const lc = ROLE_COLOR[this.layer.role] || '#ffb84d';
    for (const n of this.melNotes) {
      html.push(`<div class="cp-mnote ${this.melSel.has(n.id) ? 'sel' : ''}" data-n="${n.id}" title="${pitchName(n.pitch, flats)} · vel ${n.vel}"
        style="left:${n.start * px}px;width:${Math.max(3, n.len * px - 1)}px;top:${y(n.pitch)}px;height:${ROW_H}px;opacity:${(0.45 + 0.55 * n.vel / 127).toFixed(2)};--lc:${lc}"><i class="cp-mresize"></i></div>`);
    }
    if (!this.melNotes.length) html.push(`<div class="cp-roll-empty">«${esc(this.layer.name)}»: clicca per scrivere note · oppure «Importa» o «Genera» qui sotto</div>`);
    box.innerHTML = html.join('');
  }

  _rollPos(e) {
    const r = $('#cp-proll').getBoundingClientRect();
    return { x: (e.clientX - r.left) / this.pxStep, pitch: this._mr.hi - Math.floor((e.clientY - r.top) / ROW_H) };
  }

  _noteSound(n) {
    const t = this.synth.ctx.currentTime + 0.01;
    this._melVolumes();
    this.synth.note(n.pitch, n.vel, t, t + Math.min(0.6, Math.max(0.2, n.len * 15 / this.project.bpm)), ROLE_PRESET[this.layer.role] || 'lead', 'mel:' + this.layer.id);
  }

  // an edit already applied (a drag): push the snapshot taken before it
  _commit(before) {
    this.undoStack.push(before);
    if (this.undoStack.length > 120) this.undoStack.shift();
    this.redoStack = [];
    this._afterChange();
  }

  _fitMelodyBars() {
    const end = this.melNotes.reduce((m, n) => Math.max(m, n.start + n.len), 0);
    this.seq.bars = Math.max(this.seq.bars, Math.ceil(end / 16));
  }

  _onRollDown(e) {
    if (e.button !== 0) return;
    const box = $('#cp-proll');
    const before = JSON.stringify(this.project);
    const snap = this.ui.snap;
    const p0 = this._rollPos(e);
    const el = e.target.closest('.cp-mnote');
    let mode, n;
    if (el) {
      n = this.melNotes.find((x) => x.id === el.dataset.n);
      if (!n) return;
      if (e.shiftKey && this.melSel.has(n.id)) { this.melSel.delete(n.id); this.renderRoll(); this.renderMelBar(); return; }
      if (!this.melSel.has(n.id)) { if (!e.shiftKey) this.melSel.clear(); this.melSel.add(n.id); }
      mode = e.target.closest('.cp-mresize') ? 'resize' : e.altKey ? 'vel' : 'move';
    } else {
      if (p0.pitch < 0 || p0.pitch > 127 || p0.x < 0 || p0.x >= this.seq.bars * 16) return;
      n = { id: uid(), start: Math.floor(p0.x / snap) * snap, len: snap, pitch: p0.pitch, vel: 100 };
      this.melNotes.push(n);
      this.melSel = new Set([n.id]);
      mode = 'resize';
    }
    this.renderRoll();
    this._noteSound(n);
    const sel = this.melNotes.filter((x) => this.melSel.has(x.id));
    const orig = new Map(sel.map((x) => [x.id, { ...x }]));
    const minStart = Math.min(...sel.map((x) => x.start));
    let changed = !el;
    let lastPitch = n.pitch;
    box.setPointerCapture(e.pointerId);
    const onMove = (ev) => {
      if (!changed && Math.abs(ev.clientX - e.clientX) < 3 && Math.abs(ev.clientY - e.clientY) < 3) return;
      changed = true;
      const p = this._rollPos(ev);
      const dx = p.x - p0.x;
      for (const x of sel) {
        const o = orig.get(x.id);
        if (mode === 'resize') {
          x.len = Math.max(1, Math.round((o.start + o.len + dx) / snap) * snap - o.start);
        } else if (mode === 'move') {
          x.start = o.start + Math.max(-minStart, Math.round(dx / snap) * snap);
          x.pitch = clamp(o.pitch + p.pitch - p0.pitch, 0, 127);
        } else {
          x.vel = clamp(o.vel + Math.round((e.clientY - ev.clientY) / 2), 1, 127);
        }
      }
      if (n.pitch !== lastPitch) { lastPitch = n.pitch; this._noteSound(n); }
      this.renderRoll();
    };
    const onUp = () => {
      box.removeEventListener('pointermove', onMove);
      box.removeEventListener('pointerup', onUp);
      if (changed) { this._fitMelodyBars(); this._commit(before); } else this.renderMelBar();
    };
    box.addEventListener('pointermove', onMove);
    box.addEventListener('pointerup', onUp);
  }

  _editNotes(fn) {
    const sel = this.melNotes.filter((n) => this.melSel.has(n.id));
    const notes = sel.length ? sel : this.melNotes;
    if (!notes.length) return;
    this.edit(() => { fn(notes); this._fitMelodyBars(); });
  }

  _melKey(e, mod) {
    const k = e.key;
    if (mod && k.toLowerCase() === 'a') { this.melSel = new Set(this.melNotes.map((n) => n.id)); this.renderRoll(); this.renderMelBar(); return true; }
    if (k === 'Escape' && this.melSel.size) { this.melSel.clear(); this.renderRoll(); this.renderMelBar(); return true; }
    if (!this.melSel.size) return false;
    if (k === 'Backspace' || k === 'Delete') {
      this.edit(() => { this.melNotes = this.melNotes.filter((n) => !this.melSel.has(n.id)); this.melSel.clear(); });
      return true;
    }
    if (mod && k.toLowerCase() === 'd') {
      const sel = this.melNotes.filter((n) => this.melSel.has(n.id));
      const from = Math.min(...sel.map((n) => n.start));
      const end = Math.max(...sel.map((n) => n.start + n.len));
      this.edit(() => {
        const copies = sel.map((n) => ({ ...n, id: uid(), start: end + n.start - from }));
        this.melNotes.push(...copies);
        this.melSel = new Set(copies.map((n) => n.id));
        this._fitMelodyBars();
      });
      return true;
    }
    if (k === 'ArrowUp' || k === 'ArrowDown') {
      const d = (k === 'ArrowUp' ? 1 : -1) * (e.shiftKey ? 12 : 1);
      this._editNotes((ns) => ns.forEach((n) => { n.pitch = clamp(n.pitch + d, 0, 127); }));
      const first = this.melNotes.find((n) => this.melSel.has(n.id));
      if (first) this._noteSound(first);
      return true;
    }
    if (k === 'ArrowLeft' || k === 'ArrowRight') {
      const sel = this.melNotes.filter((n) => this.melSel.has(n.id));
      const d = (k === 'ArrowRight' ? 1 : -1) * this.ui.snap;
      if (Math.min(...sel.map((n) => n.start)) + d < 0) return true;
      this._editNotes((ns) => ns.forEach((n) => { n.start += d; }));
      return true;
    }
    return false;
  }

  _bindMelody() {
    const roll = $('#cp-proll');
    roll.addEventListener('pointerdown', (e) => this._onRollDown(e));
    roll.addEventListener('dblclick', (e) => {
      const el = e.target.closest('.cp-mnote'); if (!el) return;
      this.edit(() => { this.melNotes = this.melNotes.filter((n) => n.id !== el.dataset.n); this.melSel.delete(el.dataset.n); });
    });
    const bar = $('#cp-melbar');
    bar.onclick = (e) => {
      const chip = e.target.closest('[data-layer]');
      if (chip) {
        const l = this.layers.find((x) => x.id === chip.dataset.layer); if (!l) return;
        if (e.target.closest('[data-lmute]')) {
          l.mute = !l.mute;
          this._persist();
          this.renderMelBar();
          this.renderRoll();
          this.transport.update(this.playEvents);
        } else if (e.target.closest('[data-ldel]')) {
          if (l.notes.length && !confirm(`Eliminare il layer «${l.name}»?`)) return;
          this.edit(() => {
            this.seq.melody.layers = this.layers.filter((x) => x !== l);
            if (this.seq.melody.active === l.id) this.seq.melody.active = this.layers[0].id;
            this.melSel.clear();
          });
        } else this.selectLayer(l.id);
        return;
      }
      const b = e.target.closest('[data-mel]'); if (!b) return;
      if (b.dataset.mel === 'import') this.importMenu(b);
      else if (b.dataset.mel === 'add') this.addLayerMenu(b);
      else this._editNotes((ns) => ns.forEach((n) => { n.pitch = clamp(n.pitch + (b.dataset.mel === 'up' ? 12 : -12), 0, 127); }));
    };
    bar.ondblclick = (e) => {
      const chip = e.target.closest('[data-lsel]') && e.target.closest('[data-layer]'); if (!chip) return;
      const l = this.layers.find((x) => x.id === chip.dataset.layer);
      const name = prompt('Nome del layer', l.name);
      if (name?.trim() && name.trim() !== l.name) this.edit(() => { l.name = name.trim(); });
    };
    bar.oninput = (e) => {
      if (e.target.matches('[data-mvol]')) this.ui.melVol = +e.target.value;
      else if (e.target.matches('[data-lvol]')) this.layer.vol = +e.target.value;
      else return;
      this._melVolumes();
      this._persist();
    };
    const gen = $('#cp-mgen');
    gen.onchange = (e) => {
      const f = e.target.dataset.g; if (!f) return;
      if (f === 'role') { this._genRole(e.target.value); this._persist(); this.renderMelPanels(); return; }
      this.ui.gen[f] = e.target.type === 'checkbox' ? e.target.checked : ['lo', 'hi'].includes(f) ? +e.target.value : e.target.value;
      if (this.ui.gen.hi - this.ui.gen.lo < 7) this.ui.gen.hi = this.ui.gen.lo + 12;
      this._persist();
      if (['lo', 'hi'].includes(f)) this.renderMelPanels();
    };
    gen.onclick = async (e) => {
      if (e.target.closest('[data-gen]')) { this.generateMelody(); return; }
      const b = e.target.closest('[data-play],[data-use],[data-add]'); if (!b) return;
      const item = this._genItems?.[+(b.dataset.play ?? b.dataset.use ?? b.dataset.add)];
      if (!item) return;
      if (b.dataset.play !== undefined) { this._previewSeq({ ...this.playSeq, melody: this._withLine(item, false) }); return; }
      const asNew = b.dataset.add !== undefined || item.role !== this.layer.role;
      const target = this.layer.name;
      this.stop();
      this.edit(() => { this.seq.melody = this._withLine(item, asNew); this.melSel.clear(); });
      toast(asNew ? `Nuovo layer «${this.layer.name}»: ${item.label}` : `«${target}» sostituito: ${item.label}`);
    };
    const harm = $('#cp-mharm');
    harm.onchange = (e) => {
      const f = e.target.dataset.h; if (!f) return;
      this.ui.harm[f] = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
      this._persist();
    };
    harm.onclick = (e) => {
      if (e.target.closest('[data-harm]')) { this.harmonize(); return; }
      const b = e.target.closest('[data-play],[data-keep],[data-replace]'); if (!b) return;
      const item = this._harmItems?.[+(b.dataset.play ?? b.dataset.keep ?? b.dataset.replace)];
      if (!item) return;
      if (b.dataset.play !== undefined) { this._previewSeq(item.seq); return; }
      this.stop();
      const h = this._freshIds(this._harmonyOf(item.seq));
      if (b.dataset.keep !== undefined) this.addVersion(h, item.label);
      else {
        this.edit(() => { Object.assign(this.seq, { clips: h.clips, bars: h.bars, key: h.key }); this.sel.clear(); this.primary = null; });
        toast(`Accordi sostituiti: ${item.label}`);
      }
      this.loadBrowser();
    };
  }

  renderMelPanels() {
    if (this.ui.view !== 'melody' || !this.meta.melody) return;
    const g = this.ui.gen, h = this.ui.harm, M = this.meta.melody;
    const R = this._roleMeta(g.role);
    const opts = (list, v) => list.map(([k, l]) => `<option value="${k}" ${k === v ? 'selected' : ''}>${esc(l)}</option>`).join('');
    const pitches = (v) => Array.from({ length: 73 }, (_, i) => 24 + i).map((p) => `<option value="${p}" ${p === v ? 'selected' : ''}>${pitchName(p, keyFlats(this.seq.key))}</option>`).join('');
    $('#cp-mgen').innerHTML = `
      <div class="cp-sec-title"><span>Genera dagli accordi</span><span class="hint">${GEN_HINT[g.role] || ''}</span></div>
      <div class="cp-mform">
        <label class="cp-field">Tipo <select class="cp-select" data-g="role">${opts(M.roles.map((r) => [r.id, r.label]), g.role)}</select></label>
        <label class="cp-field">Densità <select class="cp-select" data-g="density">${opts(M.densities, g.density)}</select></label>
        ${R.shapes.length ? `<label class="cp-field">${esc(R.shapeLabel)} <select class="cp-select" data-g="contour">${opts(R.shapes, g.contour)}</select></label>` : ''}
        <label class="cp-field">Da <select class="cp-select" data-g="lo">${pitches(g.lo)}</select> a <select class="cp-select" data-g="hi">${pitches(g.hi)}</select></label>
        <label class="cp-own" title="Seleziona uno o più accordi sulla corsia: il resto della melodia resta com'è"><input type="checkbox" data-g="sel" ${g.sel ? 'checked' : ''}> solo sugli accordi selezionati</label>
        <button class="btn small primary" data-gen>🎲 Genera</button>
      </div>
      <div class="cp-vlist" data-glist>${this._genList()}</div>`;
    const keyLabel = `Tonalità della versione (${keyName(this.seq.key)})`;
    $('#cp-mharm').innerHTML = `
      <div class="cp-sec-title"><span>Accordi dalla melodia</span><span class="hint">ogni accordo contiene le note della melodia, concatenati come i suggerimenti</span></div>
      <div class="cp-mform">
        <label class="cp-field">Ritmo armonico <select class="cp-select" data-h="rate">${opts(M.rates, h.rate)}</select></label>
        <label class="cp-field">Tonalità <select class="cp-select" data-h="key">${opts([['seq', keyLabel], ['auto', 'Rileva dalla melodia']], h.key)}</select></label>
        <label class="cp-own"><input type="checkbox" data-h="related" ${h.related ? 'checked' : ''}> anche accordi in prestito (tonalità vicine)</label>
        <button class="btn small primary" data-harm>♫ Armonizza</button>
      </div>
      <div class="cp-vlist" data-hlist>${this._harmList()}</div>`;
  }

  _miniMelody(notes, bars, color) {
    if (!notes.length) return '';
    const total = bars * 16;
    const ps = notes.map((n) => n.pitch);
    const lo = Math.min(...ps) - 1, hi = Math.max(...ps) + 1;
    const h = 100 / (hi - lo + 1);
    return `<svg class="cp-minimel" viewBox="0 0 100 100" preserveAspectRatio="none" ${color ? `style="fill:${color}"` : ''}>${notes.map((n) =>
      `<rect x="${(n.start / total * 100).toFixed(2)}" y="${((hi - n.pitch) * h).toFixed(2)}" width="${Math.max(0.5, n.len / total * 100 - 0.3).toFixed(2)}" height="${Math.max(2, h * 0.8).toFixed(2)}"/>`).join('')}</svg>`;
  }

  _genList() {
    if (this._genBusy) return '<div class="hint">Genero…</div>';
    const L = this.layer;
    if (!this._genItems) return `<div class="hint">${this.seq.clips.length ? `Scegli il tipo e premi «Genera»: ▶ ascolta con gli accordi e gli altri layer · Usa: sostituisce il layer «${esc(L.name)}» se è dello stesso tipo · ＋ Layer: lo aggiunge sopra gli altri (⌘Z per tornare indietro).` : 'Servono prima degli accordi (vista Armonia).'}</div>`;
    return this._genItems.map((m, i) => {
      const same = m.role === L.role;
      return `
      <div class="cp-vrow cp-vprog"><div class="cp-vmain"><span class="cp-vlabel">${esc(m.label)}</span>${this._miniMelody(m.melody.notes, this.seq.bars, ROLE_COLOR[m.role])}</div>
        <button class="icon-btn small" data-play="${i}" title="Ascolta con gli accordi e gli altri layer">▶</button>
        ${same ? `<button class="btn small primary" data-use="${i}" title="Sostituisce le note del layer «${esc(L.name)}»">Usa</button>` : ''}
        <button class="btn small ${same ? '' : 'primary'}" data-add="${i}" title="Aggiunge un nuovo layer con questa linea">＋ Layer</button></div>`;
    }).join('') || '<div class="hint">Niente da generare: servono degli accordi.</div>';
  }

  _harmList() {
    if (this._harmBusy) return '<div class="hint">Cerco gli accordi…</div>';
    if (!this._harmItems) return `<div class="hint">${this.melNotes.length ? 'Premi «Armonizza»: Nuova versione la aggiunge accanto (A, B, C…), Sostituisci cambia gli accordi di questa.' : 'Scrivi, importa o genera prima una melodia.'}</div>`;
    const key = this._harmKey && this.ui.harm.key === 'auto' ? `<div class="hint">Tonalità rilevata: ${keyName(this._harmKey)}</div>` : '';
    return key + (this._harmItems.map((it, i) => `
      <div class="cp-vrow cp-vprog"><div class="cp-vmain"><span class="cp-vlabel">${esc(it.label)}</span>${this._miniTimeline(it.seq)}</div>
        <button class="icon-btn small" data-play="${i}" title="Ascolta con la melodia">▶</button>
        <button class="btn small primary" data-keep="${i}">Nuova versione</button>
        <button class="btn small" data-replace="${i}">Sostituisci</button></div>`).join('') || '<div class="hint">Nessun accordo del pack per questa melodia.</div>');
  }

  async generateMelody() {
    if (!this.seq.clips.length) { toast('Servono prima degli accordi (vista Armonia)'); return; }
    const g = this.ui.gen;
    // keep the notes outside the bar range only when the result can replace the active layer
    const opts = { role: g.role, density: g.density, contour: g.contour, lo: g.lo, hi: g.hi, layer: g.role === this.layer.role ? this.layer.id : null };
    const sel = this.sorted().filter((c) => this.sel.has(c.id));
    if (g.sel && sel.length) {
      opts.fromBar = Math.floor(sel[0].start / 16);
      opts.toBar = Math.ceil((sel.at(-1).start + sel.at(-1).len) / 16);
    }
    this._genSeed = (this._genSeed || Math.floor(Math.random() * 1e6)) + 1;
    this._genBusy = true;
    $('[data-glist]').innerHTML = this._genList();
    try { this._genItems = (await this.api.compose_melody_generate(this.playSeq, opts, this._genSeed)) || []; } finally { this._genBusy = false; }
    $('[data-glist]').innerHTML = this._genList();
  }

  // Tipo of the generator: its range and first shape
  _genRole(role) {
    const r = this._roleMeta(role);
    Object.assign(this.ui.gen, { role: r.id, lo: r.lo, hi: r.hi, contour: r.shapes[0]?.[0] || '' });
    this._genItems = null;
  }

  selectLayer(id) {
    if (id === this.seq.melody.active) return;
    this.seq.melody.active = id;
    this.melSel.clear();
    if (this.layer.role !== this.ui.gen.role) this._genRole(this.layer.role);
    this._persist();
    this.renderMelBar();
    this.renderRoll();
    this.renderMelPanels();
  }

  addLayerMenu(anchor) {
    const pop = showPopover(anchor, `<div class="cp-sec-title"><span>Nuovo layer</span></div>
      ${this.meta.melody.roles.map((r) => `<button class="btn" data-role="${r.id}" style="border-left:3px solid ${ROLE_COLOR[r.id]}">${esc(r.label)}</button>`).join('')}
      <div class="hint">Un layer vuoto sugli stessi accordi: scrivilo, importalo o generalo qui sotto.</div>`);
    pop.onclick = (e) => {
      const b = e.target.closest('[data-role]'); if (!b) return;
      pop.close();
      const role = b.dataset.role;
      this._genRole(role);
      this.edit(() => {
        const l = newLayer(role, this._layerName(role));
        this.layers.push(l);
        this.seq.melody.active = l.id;
        this.melSel.clear();
      });
    };
  }

  // the melody of this version with a generated line: in place of the active layer's notes, or as a new layer
  _withLine(item, asNew) {
    const m = clone(this.seq.melody);
    const notes = clone(item.melody.notes).map((n) => ({ ...n, id: uid() }));
    if (asNew) {
      const l = newLayer(item.role, this._layerName(item.role, m.layers), notes);
      m.layers.push(l);
      m.active = l.id;
    } else m.layers.find((l) => l.id === this.layer.id).notes = notes;
    return m;
  }

  async harmonize() {
    if (!this.melNotes.length) { toast('Scrivi o importa prima una melodia'); return; }
    const h = this.ui.harm;
    this._harmSeed = (this._harmSeed || Math.floor(Math.random() * 1e6)) + 1;
    this._harmBusy = true;
    $('[data-hlist]').innerHTML = this._harmList();
    try {
      const res = await this.api.compose_harmonize(this.playSeq, { rate: h.rate, key: h.key, related: h.related }, this._harmSeed);
      this._harmItems = res?.items || [];
      this._harmKey = res?.key;
    } finally { this._harmBusy = false; }
    $('[data-hlist]').innerHTML = this._harmList();
  }

  async _previewSeq(seq) {
    if (this.transport.playing) { this.stop(); return; }
    const res = await this.api.compose_render(seq);
    this.playRange(0, seq.bars * 16 * STEP_TICKS, this._events(res));
  }

  importMenu(anchor) {
    const pop = showPopover(anchor, `
      <div class="cp-sec-title"><span>Importa melodia</span></div>
      <button class="btn" data-file>File MIDI…</button>
      <button class="btn" data-live title="In Live: seleziona una clip MIDI e premi «Clip → Melodia» nel device ClusterSound">Clip da Ableton</button>
      <div class="cp-sec-title"><span>Tastiera MIDI</span></div>
      <div data-rec><span class="hint">Cerco le tastiere…</span></div>
      <div class="hint">Sostituisce il layer «${esc(this.layer.name)}» della versione ${this.project.active} (⌘Z per tornare indietro). Da una parte con accordi viene presa la nota più alta.</div>`);
    this.api.compose_midi_inputs().then((r) => {
      const box = pop.querySelector('[data-rec]');
      if (!box) return;
      if (!r?.available || !r.ports.length) { box.innerHTML = `<span class="hint">${esc(r?.hint || 'Nessuna tastiera MIDI collegata')}</span>`; return; }
      box.innerHTML = `<div class="cp-mform"><select class="cp-select" data-port>${r.ports.map((p, i) => `<option value="${i}" ${i === this.ui.midiPort ? 'selected' : ''}>${esc(p)}</option>`).join('')}</select>
        <button class="btn small primary" data-record title="4 click di attacco, poi suona sopra gli accordi · Spazio o ■ per fermare">● Registra</button></div>`;
      box.querySelector('[data-record]').onclick = () => {
        this.ui.midiPort = +box.querySelector('[data-port]').value;
        this._persist();
        pop.close();
        this.startRecording(this.ui.midiPort);
      };
    });
    pop.querySelector('[data-file]').onclick = async () => {
      pop.close();
      this._applyImport(await this.api.compose_melody_import(1));
    };
    pop.querySelector('[data-live]').onclick = async () => {
      pop.close();
      this._applyImport(await this.api.compose_melody_from_live(1));
    };
    return pop;
  }

  // ---------------------------------------------------------------- recording from a MIDI keyboard (python-rtmidi)
  async startRecording(port) {
    this.stop();
    const bpm = this.project.bpm;
    const beat = 60 / bpm;
    const tA = performance.now();
    const r = await this.api.compose_record_start(port);
    const tB = performance.now();
    if (r?.error) { toast(r.error); return; }
    const ctx = this.synth.ctx;
    if (ctx.state !== 'running') await ctx.resume();
    this.synth.setVolume(this.ui.chordVol);
    this._melVolumes();
    const t0 = ctx.currentTime + 0.1;
    for (let i = 0; i < 4; i++) this.synth.note(i ? 84 : 96, 110, t0 + i * beat, t0 + i * beat + 0.05, 'pluck', 'melody');
    const at = t0 + 4 * beat;
    // seconds from the recorder start (midway through the call) to the first beat of the progression
    const offset = (performance.now() + (at - ctx.currentTime) * 1000 - (tA + tB) / 2) / 1000;
    this._rec = { offset, loop: this.ui.loop };
    this.transport.play({ events: this.rendered.events, bpm, from: 0, to: this.seq.bars * 16 * STEP_TICKS, loop: this.ui.loop, at,
      onEnd: () => this.stopRecording() });
    this.renderToolbar();
    this._animate();
    toast('● Registrazione: 4 click di attacco, poi suona · Spazio o ■ per fermare');
  }

  async stopRecording() {
    const rec = this._rec;
    if (!rec) return;
    this._rec = null;
    this.transport.stop();
    this.synth.stopAll();
    this.renderToolbar();
    const res = await this.api.compose_record_stop(rec.offset, this.project.bpm, this.seq.bars, 1, rec.loop);
    if (res?.error) { toast(res.error); return; }
    if (!res?.notes?.length) { toast('Nessuna nota registrata'); return; }
    this.edit(() => { this.melNotes = res.notes; this.melSel.clear(); this._fitMelodyBars(); });
    toast(`Registrate ${res.notes.length} note (⌘Z per tornare alla melodia di prima)`);
  }

  _applyImport(res) {
    if (!res) return;
    if (res.error) { toast(res.error); return; }
    if (!res.notes?.length) { toast('Nessuna nota da importare'); return; }
    const setKey = !this.seq.clips.length && res.key;
    this.edit(() => {
      this.melNotes = res.notes;
      this.melSel.clear();
      this._fitMelodyBars();
      if (setKey) this.seq.key = res.key;
    });
    toast(`Melodia importata: ${res.notes.length} note${res.name ? ` da «${res.name}»` : ''}${setKey ? ` · tonalità ${keyName(res.key)}` : ''}`);
    if (setKey) this.loadBrowser();
  }

  // ---------------------------------------------------------------- save / open / export
  async save() {
    const name = prompt('Nome della progressione', this.project.name);
    if (name === null) return;
    this.project.name = name.trim() || this.project.name;
    const saved = await this.api.save_progression(this.project);
    this.project.id = saved.id;
    this._persist();
    this.renderToolbar();
    toast(`Salvata: ${this.project.name}`);
  }

  async openDialog(anchor) {
    const list = await this.api.list_progressions();
    const pop = showPopover(anchor, `<div class="cp-sec-title"><span>Progressioni salvate</span></div>
      <div class="cp-openlist">${list.sort((a, b) => b.updated - a.updated).map((p) => `
        <div class="cp-openrow" data-id="${esc(p.id)}"><span>${esc(p.name)}</span><span class="hint">${p.order?.length || 1} vers.</span>
          <button class="link-btn" data-del="${esc(p.id)}" title="Elimina">✕</button></div>`).join('') || '<div class="hint">Nessuna progressione salvata.</div>'}</div>
      <button class="btn small" data-new>Nuova progressione</button>`);
    pop.onclick = async (e) => {
      const del = e.target.closest('[data-del]');
      if (del) {
        if (confirm('Eliminare la progressione salvata?')) { await this.api.delete_progression(del.dataset.del); del.closest('.cp-openrow').remove(); }
        return;
      }
      if (e.target.closest('[data-new]')) {
        pop.close();
        this.edit(() => {
          const key = this.seq.key;
          this.project = newProject(clone(this.meta.styles.defaultMode));
          this.project.versions.A.key = { ...key };
          this.sel.clear();
          this.primary = null;
        });
        this.loadBrowser();
        return;
      }
      const row = e.target.closest('[data-id]');
      if (!row) return;
      const p = list.find((x) => x.id === row.dataset.id);
      pop.close();
      this.edit(() => { this.project = this._migrate(clone(p)); this.sel.clear(); this.primary = null; });
      this.loadBrowser();
    };
  }

  exportMenu(anchor) {
    const p = this.project;
    const many = p.order.length > 1;
    const manyModes = p.modeOrder.length > 1;
    const label = (v, mk) => `${p.name}${many ? ` ${v}` : ''}${manyModes ? ` - ${p.modes[mk].name}` : ''}`;
    const hasMel = Object.values(p.versions).some((v) => melodyOf(v.melody).layers.some((l) => l.notes.length));
    const parts = hasMel ? this.ui.parts : 'chords';
    const pop = showPopover(anchor, `
      <button class="btn primary" data-one>Versione ${p.active} · ${esc(this.mode.name)} → .mid</button>
      ${many ? `<button class="btn" data-all>Tutte le versioni (${p.order.join(', ')}) con ${esc(this.mode.name)} → cartella</button>` : ''}
      ${manyModes ? `<button class="btn" data-modes>Versione ${p.active} con tutte le modalità → cartella</button>` : ''}
      <label class="cp-own"><input type="checkbox" data-pure ${this.ui.pure ? 'checked' : ''}> solo accordi (senza ritmica, strum, arpeggi e humanize)</label>
      ${hasMel ? `<div class="seg cp-seg" data-parts>${PARTS.map(([k, l]) => `<button class="seg-btn ${k === this.ui.parts ? 'active' : ''}" data-part="${k}">${l}</button>`).join('')}</div>
        <div class="hint">Accordi + melodia: un .mid con una traccia per gli accordi e una per ogni layer (i layer muti restano fuori).</div>` : ''}
      <button class="btn" data-live>Versione ${p.active} → Live</button>
      ${many ? `<button class="btn" data-live-all>Tutte le versioni → Live (una clip ciascuna)</button>` : ''}
      <div class="hint">In Ableton: trascina il file su una traccia MIDI. Il tempo del file è ${p.bpm} BPM. «→ Live» crea la traccia con le clip tramite il device ClusterSound.</div>`);
    pop.querySelector('[data-pure]').onchange = (e) => { this.ui.pure = e.target.checked; this._persist(); };
    pop.querySelector('[data-parts]')?.addEventListener('click', (e) => {
      const b = e.target.closest('[data-part]'); if (!b) return;
      this.ui.parts = b.dataset.part;
      this._persist();
      pop.close();
      this.exportMenu(anchor);
    });
    pop.querySelector('[data-one]').onclick = async () => {
      pop.close();
      const r = await this.api.compose_export_midi({ ...this.playSeq, name: label(p.active, p.modeActive) }, this.ui.pure, parts);
      if (r) toast(`MIDI salvato: ${r.split('/').pop()}`);
    };
    pop.querySelector('[data-live]').onclick = () => {
      pop.close();
      sendToLive(this.api, 'compose', { ...this.playSeq, name: label(p.active, p.modeActive) }, { pure: this.ui.pure });
    };
    pop.querySelector('[data-live-all]')?.addEventListener('click', () => {
      pop.close();
      sendToLive(this.api, 'compose', clone(p), { pure: this.ui.pure });
    });
    const many_ = async (seqs) => {
      pop.close();
      const r = await this.api.compose_export_versions(seqs, this.ui.pure, parts);
      if (r?.files) toast(`${r.files.length} file MIDI salvati`);
      else if (r?.error) toast(r.error);
    };
    pop.querySelector('[data-all]')?.addEventListener('click', () =>
      many_(p.order.map((v) => ({ ...this._playSeq(p.versions[v]), name: label(v, p.modeActive) }))));
    pop.querySelector('[data-modes]')?.addEventListener('click', () =>
      many_(p.modeOrder.map((mk) => ({ ...this._playSeq(this.seq, p.modes[mk]), name: label(p.active, mk) }))));
  }

  // ---------------------------------------------------------------- keyboard (from app.js)
  onKey(e) {
    if (e.target.closest?.('input, select, textarea')) return false;
    const mod = e.metaKey || e.ctrlKey;
    if (e.key === ' ') { this.togglePlay(); return true; }
    if (mod && e.key.toLowerCase() === 'z') { e.shiftKey ? this.redo() : this.undo(); return true; }
    if (this.ui.view === 'melody' && this._melKey(e, mod)) return true;
    if (mod && e.key.toLowerCase() === 'd') { this.duplicateSelected(); return true; }
    if (e.key === 'Backspace' || e.key === 'Delete') { this.deleteSelected(); return true; }
    if (!mod && e.key.toLowerCase() === 'v' && this.primary) { this.clipVariations(this.primary); return true; }
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      const cl = this.sorted();
      if (!cl.length) return true;
      const i = cl.findIndex((c) => c.id === this.primary);
      const j = i < 0 ? 0 : Math.max(0, Math.min(cl.length - 1, i + (e.key === 'ArrowRight' ? 1 : -1)));
      this._select(cl[j].id);
      this.renderTimeline();
      this.renderInspector();
      this.refresh();
      this.synth.chord(this._voiced(cl[j]), 0.6);
      return true;
    }
    if (e.key === 'Escape' && this.sel.size) { this._select(null); this.renderTimeline(); this.renderInspector(); this.refresh(); return true; }
    return false;
  }
}
