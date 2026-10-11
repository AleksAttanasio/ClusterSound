// "Pattern" screen: genre patterns on drum buses (with sample layers) + bass line, MIDI/Ableton export.
import { Sequencer, refKey } from './sequencer.js';
import { suggestBus, toast, showPopover } from './sendmenu.js';
import { Arranger } from './arranger.js';

const $ = (s, root = document) => root.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const clone = (o) => JSON.parse(JSON.stringify(o));
const LS_KEY = 'clustersound.pattern';
const KIND_BADGE = { library: 'LIB', online: 'WEB', file: 'FILE' };
const ALT_MODES = [['off', 'insieme'], ['cycle', 'a giro'], ['random', 'casuale'], ['random_pass', 'casuale ogni giro']];
// buses where alternating samples makes no sense by default (one kick, one FX, a melodic bass)
export const NO_ALT = new Set(['kick', 'fx', 'bass']);
export const newSeed = () => Math.floor(Math.random() * 2 ** 32) >>> 0;
const LS_RANDOM = 'clustersound.randomKit';

export class PatternEditor {
  constructor({ api, player, classes, onLoadFromRack }) {
    this.api = api;
    this.onLoadFromRack = onLoadFromRack;
    this.player = player;
    this.classColor = Object.fromEntries(classes.map((c) => [c.id, c.color]));
    this.ready = null;
    this.p = null;
    this.selected = {};      // bus -> selected layer index (target of "replace")
    this.expanded = new Set(['kick', 'snare', 'bass']);
    this.onlineRefs = [];    // online samples sent this session (chooser tab)
    this.seq = new Sequencer({ player, fetchAudio: (ref) => api.sample_audio(ref), onStep: (i) => this._playhead(i) });
    this.playMode = 'pattern'; // 'sequence' while the Sequence panel is playing
  }

  // ---------------------------------------------------------------- lifecycle
  ensure() {
    if (!this.ready) this.ready = this._init();
    return this.ready;
  }

  async _init() {
    this.meta = await this.api.patterns_init();
    this.buses = this.meta.buses;
    this.busById = Object.fromEntries(this.buses.map((b) => [b.id, b]));
    this._buildShell();
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(LS_KEY) || 'null'); } catch (e) { saved = null; }
    if (saved && saved.buses) {
      this.p = saved;
      this.source = saved._source || { genre: saved.genre, variant: 0 };
    } else {
      await this.loadVariant('dnb_rollers', 0, false);
    }
    delete this.p._source;
    await this.autofill();
    this.renderAll();
  }

  async show() {
    await this.ensure();
    // the library may have been scanned after the pattern was first opened
    if (!Object.values(this.p.buses).some((b) => b.layers.length)) await this.autofill();
    this.renderAll();
  }

  hide() { this.stop(); }

  // ---------------------------------------------------------------- pattern state
  _persist(fromArranger = false) {
    if (this.playMode !== 'sequence') this.seq.setPattern(this.p);
    try { localStorage.setItem(LS_KEY, JSON.stringify({ ...this.p, _source: this.source })); } catch (e) { /* private mode */ }
    const refs = [];
    for (const b of Object.values(this.p.buses)) for (const l of b.layers) if (l.ref?.kind === 'online') refs.push(l.ref);
    this.api.protect_samples(refs);
    if (this.arr && !fromArranger) this.arr.onPatternChanged();
    if (this.arr) this.arr._info();
  }

  async loadVariant(genre, variant, keepTempo = true) {
    const fresh = await this.api.pattern_build(genre, variant);
    if (this.p) {
      // keep samples and mix: only the groove changes
      for (const [id, b] of Object.entries(fresh.buses)) {
        const old = this.p.buses[id];
        if (!old) continue;
        for (const k of ['layers', 'volume', 'pan', 'mute', 'solo', 'hp', 'lp']) b[k] = old[k];
      }
      if (keepTempo && this.p.genre === genre) {
        fresh.bpm = this.p.bpm;
        fresh.key = this.p.key;
        fresh.octave = this.p.octave;
      }
    }
    this.p = fresh;
    this.source = { genre, variant };
    this._persist();
  }

  async loadUser(pat) {
    const keep = this.p;
    const fresh = clone(pat);
    if (keep && !Object.values(fresh.buses).some((b) => b.layers.length)) {
      for (const [id, b] of Object.entries(fresh.buses)) if (keep.buses[id]) b.layers = keep.buses[id].layers;
    }
    this.p = fresh;
    this.source = { genre: pat.genre, user: pat.id };
    this._persist();
    await this.seq.preload(this.p);
    this.renderAll();
  }

  async autofill() {
    // first layer of every bus that plays something, from the library (best confidence for its classes)
    const jobs = [];
    for (const b of this.buses) {
      const bus = this.p.buses[b.id];
      const used = b.melodic ? bus.notes.length : bus.steps.some((v) => v);
      if (!used || bus.layers.length) continue;
      jobs.push(this.api.pattern_candidates(b.id, '', 1, true).then(async (c) => {
        if (!c.length) return;
        const ref = c[0];
        bus.layers.push(this._layer(ref));
        if (b.melodic && ref.root == null) bus.layers[bus.layers.length - 1].root = await this.api.sample_root(ref);
      }));
    }
    await Promise.all(jobs);
    this._persist();
    await this.seq.preload(this.p);
  }

  _layer(ref) {
    return { ref, name: ref.name, volume: 1, pitch: 0, offset_ms: 0, mute: false, solo: false, steps: null, root: ref.root ?? null };
  }

  async addSample(busId, ref, mode = 'add') {
    await this.ensure();
    const bus = this.p.buses[busId];
    const layer = this._layer(ref);
    if (busId === 'bass' && layer.root == null) layer.root = await this.api.sample_root(ref);
    let idx;
    if (mode === 'replace' && bus.layers.length) {
      idx = Math.min(this.selected[busId] ?? 0, bus.layers.length - 1);
      const old = bus.layers[idx];
      Object.assign(layer, { volume: old.volume, pitch: old.pitch, offset_ms: old.offset_ms, steps: old.steps });
      bus.layers[idx] = layer;
    } else {
      bus.layers.push(layer);
      idx = bus.layers.length - 1;
    }
    this.selected[busId] = idx;
    if (ref.kind === 'online' && !this.onlineRefs.some((r) => r.url === ref.url)) this.onlineRefs.unshift(ref);
    this.expanded.add(busId);
    this._persist();
    await this.seq.load(ref);
    if (this.root && !this.root.hidden) this.renderGrid();
    toast(`${mode === 'replace' ? 'Sostituito in' : 'Aggiunto a'} ${this.busById[busId].label} (layer ${idx + 1})`);
  }

  // Samples from the Drum Rack: assign = {busId: {refs, alt}}. replace: the bus loses its layers;
  // clearOthers: buses not in assign are emptied too. Without alternation only the first new layer plays.
  async loadKit(assign, { replace = true, clearOthers = false } = {}) {
    await this.ensure();
    for (const bdef of this.buses) {
      const bus = this.p.buses[bdef.id];
      const a = assign[bdef.id];
      if (!a) { if (clearOthers) bus.layers = []; continue; }
      await this._setLayers(bdef.id, a.refs, a.alt, replace);
    }
    this._persist();
    await this.seq.preload(this.p);
    this.renderAll();
  }

  async _setLayers(id, refs, alt, replace = true) {
    const bus = this.p.buses[id];
    const fresh = refs.map((r) => this._layer(r));
    if (id === 'bass') {
      await Promise.all(fresh.map(async (l) => { if (l.root == null) l.root = await this.api.sample_root(l.ref); }));
    } else {
      bus.alt = { mode: alt || 'off', seed: newSeed() };
    }
    if (id === 'bass' || (alt || 'off') === 'off') fresh.forEach((l, k) => { l.mute = k > 0 || (!replace && bus.layers.some((x) => !x.mute)); });
    bus.layers = replace ? fresh : bus.layers.concat(fresh);
    this.selected[id] = 0;
    if (fresh.length > 1) this.expanded.add(id);
  }

  _randomOpts() {
    try { return { variants: 1, folder: '', oneshot: true, ...JSON.parse(localStorage.getItem(LS_RANDOM) || '{}') }; } catch { return { variants: 1, folder: '', oneshot: true }; }
  }

  openRandomKit(anchor) {
    const o = this._randomOpts();
    const pop = showPopover(anchor, `
      <div class="pop-title">🎲 Kit casuale</div>
      <div class="hint">Per ogni bus non bloccato (🔒) sceglie a caso un gruppo di sample simili delle sue classi e ne prende sample a caso. Il groove non cambia.</div>
      <label class="pop-field">Sample per bus
        <select data-o="variants">${[1, 2, 4].map((n) => `<option value="${n}" ${o.variants === n ? 'selected' : ''}>${n}${n > 1 ? ' (alternati a caso)' : ''}</option>`).join('')}</select></label>
      <label class="pop-field">Solo dalla cartella / pack (facoltativo)<input type="text" data-o="folder" value="${esc(o.folder)}" placeholder="es. Cymatics"></label>
      <label class="pop-check"><input type="checkbox" data-o="oneshot" ${o.oneshot ? 'checked' : ''}> solo one-shot (niente loop)</label>
      <div class="pop-actions"><button class="btn primary" data-go>Genera</button></div>`);
    pop.querySelector('[data-go]').onclick = async () => {
      const opts = {
        variants: +pop.querySelector('[data-o=variants]').value,
        folder: pop.querySelector('[data-o=folder]').value.trim(),
        oneshot: pop.querySelector('[data-o=oneshot]').checked,
      };
      try { localStorage.setItem(LS_RANDOM, JSON.stringify(opts)); } catch { /* private mode */ }
      pop.close();
      await this.randomKit(opts);
    };
  }

  async randomKit({ variants = 1, folder = '', oneshot = true } = {}) {
    await this.ensure();
    const used = [];
    let done = 0, locked = 0;
    for (const bdef of this.buses) {
      const bus = this.p.buses[bdef.id];
      const plays = bdef.melodic ? bus.notes.length : bus.steps.some((v) => v) || bus.layers.some((l) => l.steps?.some((v) => v));
      if (!plays) continue;
      if (bus.lock) { locked++; continue; }
      const n = bdef.melodic ? 1 : variants;
      const refs = await this.api.random_refs(bdef.classes, n, { oneshot: bdef.melodic ? false : oneshot, folder, exclude: used });
      if (!refs.length) continue;
      used.push(...refs.map((r) => r.id));
      await this._setLayers(bdef.id, refs, NO_ALT.has(bdef.id) || refs.length < 2 ? 'off' : 'random');
      done++;
    }
    this._persist();
    await this.seq.preload(this.p);
    this.renderAll();
    toast(done ? `Kit casuale: ${done} bus${locked ? ` · ${locked} bloccati` : ''}` : 'Nessun sample adatto (controlla il filtro cartella)');
  }

  layerCounts() {
    const out = {};
    if (this.p) for (const [id, b] of Object.entries(this.p.buses)) out[id] = b.layers.length;
    return out;
  }

  // ---------------------------------------------------------------- transport
  async togglePlay() {
    if (this.seq.playing) { this.stop(); return; } // stops the pattern loop or the sequence
    await this.seq.preload(this.p);
    this.seq.setPattern(this.p);
    this.seq.start();
    $('#pt-play').textContent = '■ Stop';
    $('#pt-play').classList.add('on');
    this._meterLoop();
  }

  stop() {
    this.seq.stop();
    const wasSequence = this.playMode === 'sequence';
    this.playMode = 'pattern';
    if (wasSequence) this.seq.setPattern(this.p);
    const b = $('#pt-play');
    if (b) { b.textContent = '▶ Play'; b.classList.remove('on'); }
    if (this.arr) this.arr.onStopped();
  }

  _playhead(i) {
    if (this.playMode === 'sequence' && this.arr) i = this.arr.onStep(i); // global step -> step of the shown block
    document.querySelectorAll('.pt-cell.now').forEach((c) => c.classList.remove('now'));
    const roll = $('#pt-roll-head');
    if (i < 0) { if (roll) roll.style.display = 'none'; return; }
    document.querySelectorAll(`.pt-cell[data-i="${i}"]`).forEach((c) => c.classList.add('now'));
    if (roll) {
      roll.style.display = '';
      roll.style.left = `calc(${(i / (this.p.bars * 16)) * 100}% )`;
    }
  }

  _meterLoop() {
    if (!this.seq.playing) {
      document.querySelectorAll('.pt-meter span').forEach((m) => { m.style.width = '0'; });
      return;
    }
    document.querySelectorAll('.pt-meter').forEach((m) => {
      const v = Math.min(1, this.seq.level(m.dataset.bus) * 1.2);
      m.firstElementChild.style.width = `${Math.round(v * 100)}%`;
    });
    requestAnimationFrame(() => this._meterLoop());
  }

  // ---------------------------------------------------------------- shell
  _buildShell() {
    this.root = $('#pattern');
    const groups = this.meta.groups.map((g) => `<optgroup label="${esc(g)}">${this.meta.genres.filter((x) => x.group === g)
      .map((x) => `<option value="${x.id}">${esc(x.name)} · ${x.bpm}</option>`).join('')}</optgroup>`).join('');
    const keys = this.meta.note_names.map((n) => `<option>${n}</option>`).join('');
    this.root.innerHTML = `
      <div class="pt-bar">
        <select id="pt-genre" class="cls-select pt-genre" title="Genere">${groups}</select>
        <div id="pt-variants" class="chips pt-variants"></div>
        <div class="spacer"></div>
        <button id="pt-random" class="btn" title="Sceglie a caso un gruppo di sample simili per ogni bus non bloccato (🔒) e ne prende sample a caso">🎲 Kit casuale</button>
        <button id="pt-fromrack" class="btn" title="Carica i sample del Drum Rack nei bus del Sequencer">▦ Carica dal Drum Rack</button>
        <button id="pt-vary" class="btn" title="Genera una variazione del pattern corrente">Varia</button>
        <button id="pt-save" class="btn" title="Salva come variante personale del genere">Salva variante</button>
        <button id="pt-del" class="btn" hidden title="Elimina questa variante personale">Elimina</button>
      </div>
      <div class="pt-bar pt-transport">
        <button id="pt-play" class="btn primary pt-play">▶ Play</button>
        <label>BPM <input id="pt-bpm" type="number" min="40" max="250" step="1"></label>
        <label title="Swing sugli 16esimi in levare (50 = dritto)">Swing <input id="pt-swing" type="range" min="50" max="75" step="1"><span id="pt-swing-v"></span></label>
        <label>Battute <select id="pt-bars"><option>1</option><option>2</option><option>4</option></select></label>
        <label>Tonalità <select id="pt-key">${keys}</select><select id="pt-oct" title="Ottava del basso (convenzione Ableton: C1 = nota MIDI 36)"><option value="0">-1</option><option value="1">0</option><option value="2">1</option><option value="3">2</option></select></label>
        <div class="spacer"></div>
        <select id="pt-map" title="Mappatura note della batteria nel MIDI"><option value="drumrack">MIDI: Drum Rack (C1…)</option><option value="gm">MIDI: General MIDI</option></select>
        <button id="pt-midi" class="btn">Esporta MIDI</button>
        <button id="pt-wav" class="btn">Esporta WAV</button>
        <button id="pt-abl" class="btn primary" title="Cartella con Drum Rack .adg, sample, MIDI e loop pronta per Ableton Live">Esporta per Ableton</button>
      </div>
      <div class="pt-help hint">Clic: step on/off · Shift+clic: accento · Alt+clic: ghost · Tasto destro: roll ×2/×3/×4 · Spazio: play/stop.
        Invia sample ai bus dalla Libreria (tasto destro su un punto 3D o una riga), dalla scheda Online o dal Drum Rack.</div>
      <div id="sq-panel" class="sq"></div>
      <div id="pt-empty" class="pt-empty hint" hidden></div>
      <div id="pt-grid" class="pt-grid"></div>`;
    this._bindShell();
    this.arr = new Arranger(this);
    this.arr.mount($('#sq-panel'));
  }

  _bindShell() {
    $('#pt-genre').onchange = async (e) => { await this.loadVariant(e.target.value, 0, false); await this.seq.preload(this.p); this.renderAll(); };
    $('#pt-variants').onclick = async (e) => {
      const b = e.target.closest('[data-variant],[data-user]');
      if (!b) return;
      if (b.dataset.user) await this.loadUser(this.meta.user.find((u) => u.id === b.dataset.user));
      else { await this.loadVariant(this.p.genre, +b.dataset.variant); await this.seq.preload(this.p); this.renderAll(); }
    };
    $('#pt-play').onclick = () => this.togglePlay();
    $('#pt-bpm').onchange = (e) => { this.p.bpm = Math.max(40, Math.min(250, +e.target.value || 120)); this._persist(); };
    $('#pt-swing').oninput = (e) => { this.p.swing = +e.target.value; $('#pt-swing-v').textContent = `${this.p.swing}%`; this._persist(); };
    $('#pt-bars').onchange = (e) => { this.setBars(+e.target.value); };
    $('#pt-key').onchange = (e) => { this.p.key = e.target.value; this._persist(); this.renderGrid(); };
    $('#pt-oct').onchange = (e) => { this.p.octave = +e.target.value; this._persist(); this.renderGrid(); };
    $('#pt-vary').onclick = () => this.vary();
    $('#pt-random').onclick = (e) => this.openRandomKit(e.currentTarget);
    $('#pt-fromrack').onclick = () => this.onLoadFromRack?.();
    $('#pt-save').onclick = () => this.saveVariant();
    $('#pt-del').onclick = () => this.deleteVariant();
    $('#pt-midi').onclick = async () => { const p = await this.api.export_midi(this._exportable(), $('#pt-map').value); if (p) toast(`MIDI salvato: ${p.split('/').pop()}`); };
    $('#pt-wav').onclick = async () => { toast('Rendering…'); const p = await this.api.export_wav(this._exportable()); if (p) toast(`WAV salvato: ${p.split('/').pop()}`); };
    $('#pt-abl').onclick = async () => {
      toast('Preparazione pacchetto Ableton…');
      const r = await this.api.export_ableton(this._exportable());
      if (r.error) alert(r.error); else if (r.folder) toast(`Pacchetto creato: ${r.folder.split('/').pop()}`);
    };
    $('#pt-grid').addEventListener('click', (e) => this._onGridClick(e));
    $('#pt-grid').addEventListener('contextmenu', (e) => this._onGridContext(e));
    $('#pt-grid').addEventListener('input', (e) => this._onGridInput(e));
    $('#pt-grid').addEventListener('change', (e) => this._onGridInput(e, true));
  }

  _exportable() { return clone(this.p); }

  setBars(bars) {
    const n0 = this.p.bars * 16, n = bars * 16;
    const grow = (arr, fill) => Array.from({ length: n }, (_, i) => (i < n0 ? arr[i] : (n > n0 ? arr[i % n0] : fill)));
    for (const [id, b] of Object.entries(this.p.buses)) {
      if (id === 'bass') {
        const extra = [];
        if (n > n0) for (let r = 1; r < n / n0; r++) for (const nt of b.notes) extra.push({ ...nt, step: nt.step + r * n0 });
        b.notes = b.notes.concat(extra).filter((nt) => nt.step < n).map((nt) => ({ ...nt, len: Math.min(nt.len, n - nt.step) }));
      } else {
        b.steps = grow(b.steps, 0);
        b.ratchet = grow(b.ratchet, 1);
        for (const l of b.layers) if (l.steps) l.steps = grow(l.steps, 0);
      }
    }
    this.p.bars = bars;
    this._persist();
    this.renderGrid();
  }

  // ---------------------------------------------------------------- variants
  vary() {
    const n = this.p.bars * 16;
    const rnd = (k) => Math.floor(Math.random() * k);
    const kick = this.p.buses.kick.steps;
    const on = kick.map((v, i) => (v && i % 4 !== 0 ? i : -1)).filter((i) => i >= 0);
    if (on.length) { // move a secondary kick by one 16th
      const i = on[rnd(on.length)], j = Math.max(1, Math.min(n - 1, i + (Math.random() < 0.5 ? -1 : 1)));
      if (!kick[j]) { kick[j] = kick[i]; kick[i] = 0; }
    } else if (!kick[n - 6]) kick[n - 6] = 100;
    const sn = this.p.buses.snare.steps;
    for (let k = 0; k < 2; k++) { const i = rnd(n); if (!sn[i] && i % 4 !== 0) sn[i] = 55; }
    const hat = this.p.buses.chat;
    const hits = hat.steps.map((v, i) => (v ? i : -1)).filter((i) => i >= 0);
    if (hits.length) hat.ratchet[hits[rnd(hits.length)]] = [2, 3][rnd(2)];
    const oh = this.p.buses.ohat.steps;
    if (oh.some((v) => v) && Math.random() < 0.5) { const i = 2 + 4 * rnd(n / 4); oh[i] = oh[i] ? 0 : 90; }
    this.p.name = (this.p.name || 'Main').replace(/ \(variazione\)$/, '') + ' (variazione)';
    this.source = { genre: this.p.genre, variant: null };
    this._persist();
    this.renderAll();
  }

  async saveVariant() {
    const isUser = this.source?.user;
    const name = prompt('Nome della variante', isUser ? this.p.name : `${this.p.name.replace(/ \(variazione\)$/, '')} mia`);
    if (!name) return;
    const p = clone(this.p);
    p.name = name;
    if (!isUser) delete p.id; else p.id = this.source.user;
    const saved = await this.api.save_user_pattern(p);
    this.meta.user = this.meta.user.filter((u) => u.id !== saved.id).concat([saved]);
    this.p.name = saved.name;
    this.p.id = saved.id;
    this.source = { genre: saved.genre, user: saved.id };
    this._persist();
    this.renderBar();
    toast(`Variante "${saved.name}" salvata`);
  }

  async deleteVariant() {
    const id = this.source?.user;
    if (!id || !confirm('Eliminare questa variante personale?')) return;
    await this.api.delete_user_pattern(id);
    this.meta.user = this.meta.user.filter((u) => u.id !== id);
    await this.loadVariant(this.p.genre, 0);
    this.renderAll();
  }

  // ---------------------------------------------------------------- render
  renderAll() {
    if (!this.p) return;
    this.renderBar();
    this.renderGrid();
    if (this.arr) this.arr.render();
  }

  renderBar() {
    const p = this.p;
    $('#pt-genre').value = p.genre;
    const g = this.meta.genres.find((x) => x.id === p.genre);
    const user = this.meta.user.filter((u) => u.genre === p.genre);
    $('#pt-variants').innerHTML = (g?.variants || []).map((v, i) => `<button class="chip ${this.source?.variant === i && !this.source?.user ? 'on' : ''}" data-variant="${i}" draggable="true" title="Clic: carica · trascina nella Sequenza (o doppio clic) per aggiungerla">${esc(v)}</button>`).join('')
      + user.map((u) => `<button class="chip user ${this.source?.user === u.id ? 'on' : ''}" data-user="${esc(u.id)}" draggable="true" title="Variante personale · trascina nella Sequenza per aggiungerla">★ ${esc(u.name)}</button>`).join('')
      + (this.source?.variant === null && !this.source?.user ? `<span class="chip on">${esc(p.name)}</span>` : '');
    $('#pt-del').hidden = !this.source?.user;
    $('#pt-bpm').value = Math.round(p.bpm);
    $('#pt-swing').value = p.swing;
    $('#pt-swing-v').textContent = `${Math.round(p.swing)}%`;
    $('#pt-bars').value = String(p.bars);
    $('#pt-key').value = p.key;
    $('#pt-oct').value = String(p.octave);
    if (g) $('#pt-bpm').title = `Tipico ${g.bpm_range[0]}–${g.bpm_range[1]} BPM`;
  }

  _cells(steps, ratchet, busId, layerIdx = null) {
    const n = this.p.bars * 16;
    let html = '';
    for (let i = 0; i < n; i++) {
      const v = steps[i];
      const cls = !v ? '' : v >= 120 ? 'on acc' : v < 70 ? 'on ghost' : 'on';
      const r = ratchet && ratchet[i] > 1 ? `<i>${ratchet[i]}</i>` : '';
      html += `<div class="pt-cell ${cls} ${i % 4 === 0 ? 'beat' : ''} ${i % 16 === 0 ? 'bar' : ''}" data-i="${i}" data-bus="${busId}"${layerIdx !== null ? ` data-layer="${layerIdx}"` : ''}>${r}</div>`;
    }
    return html;
  }

  _mix(id, b) {
    return `<div class="pt-mix">
      <button class="pt-ms ${b.mute ? 'on' : ''}" data-act="mute" data-bus="${id}" title="Mute">M</button>
      <button class="pt-ms solo ${b.solo ? 'on' : ''}" data-act="solo" data-bus="${id}" title="Solo">S</button>
      <input type="range" min="0" max="1.5" step="0.01" value="${b.volume}" data-field="volume" data-bus="${id}" title="Volume bus">
      <input type="range" min="-1" max="1" step="0.05" value="${b.pan}" data-field="pan" data-bus="${id}" class="pan" title="Pan">
      <select data-field="filter" data-bus="${id}" title="Filtro del bus">
        <option value="">Filtro off</option>
        ${[60, 120, 250, 500].map((f) => `<option value="hp:${f}" ${b.hp === f ? 'selected' : ''}>HP ${f} Hz</option>`).join('')}
        ${[2000, 5000, 9000].map((f) => `<option value="lp:${f}" ${b.lp === f ? 'selected' : ''}>LP ${f / 1000} kHz</option>`).join('')}
      </select>
      <div class="pt-meter" data-bus="${id}"><span></span></div>
    </div>`;
  }

  _lock(id, b) {
    return `<button class="pt-ib pt-lock ${b.lock ? 'on' : ''}" data-act="lock" data-bus="${id}"
      title="${b.lock ? 'Bloccato: Kit casuale non lo cambia (clic per sbloccare)' : 'Blocca: Kit casuale non cambierà questo bus'}">${b.lock ? '🔒' : '🔓'}</button>`;
  }

  // how the layers share the hits (only meaningful with 2+ layers)
  _alt(id, b) {
    if (b.layers.length < 2) return '';
    const mode = b.alt?.mode || 'off';
    return `<select class="pt-alt ${mode !== 'off' ? 'on' : ''}" data-field="alt" data-bus="${id}"
        title="Layer: insieme = suonano tutti a ogni colpo; a giro / casuale = un layer diverso a ogni colpo">
        ${ALT_MODES.map(([m, l]) => `<option value="${m}" ${m === mode ? 'selected' : ''}>${l}</option>`).join('')}</select>
      ${mode.startsWith('random') ? `<button class="pt-ib" data-act="reseed" data-bus="${id}" title="Nuova estrazione casuale dei layer">⚄</button>` : ''}`;
  }

  _layerRow(id, b, l, j) {
    const sel = (this.selected[id] ?? 0) === j;
    const badge = l.ref ? KIND_BADGE[l.ref.kind] : '';
    const lic = l.ref?.kind === 'online' ? ` <span class="lic-mini">${esc(l.ref.license_label || '')}</span>` : '';
    const n = this.p.bars * 16;
    return `<div class="pt-layer ${sel ? 'sel' : ''}" data-bus="${id}" data-layer="${j}">
      <div class="pt-lhead">
        <span class="pt-lbadge ${l.ref?.kind || ''}" title="${esc(l.ref?.kind === 'online' ? (l.ref.source_label || '') : (l.ref?.path || ''))}">${badge}</span>
        <span class="pt-lname" data-act="select-layer" title="${esc(l.name)} — clic per selezionarlo come layer da sostituire">${esc(l.name || 'vuoto')}${lic}</span>
        <button class="pt-ib" data-act="audition" title="Ascolta">▶</button>
        <button class="pt-ib" data-act="next" title="Prossimo candidato della classe">↻</button>
        <button class="pt-ib" data-act="choose" title="Scegli sample…">…</button>
        <button class="pt-ms ${l.mute ? 'on' : ''}" data-act="lmute">M</button>
        <button class="pt-ms solo ${l.solo ? 'on' : ''}" data-act="lsolo">S</button>
        <label title="Volume layer"><input type="range" min="0" max="1.5" step="0.01" value="${l.volume}" data-lfield="volume"></label>
        <label title="Pitch (semitoni)">± <input type="number" min="-24" max="24" step="1" value="${l.pitch}" data-lfield="pitch"></label>
        <label title="Offset (ms) per allineare i transienti">ms <input type="number" min="-50" max="200" step="1" value="${l.offset_ms}" data-lfield="offset_ms"></label>
        ${id === 'bass' ? `<label title="Nota del sample (radice), per l'intonazione">root <input type="number" min="0" max="127" value="${l.root ?? ''}" placeholder="auto" data-lfield="root"></label>`
          : `<button class="pt-ib ${l.steps ? 'on' : ''}" data-act="own-steps" title="Step propri per questo layer">⋯</button>`}
        <button class="pt-ib danger" data-act="del-layer" title="Rimuovi layer">×</button>
      </div>
      ${l.steps && id !== 'bass' ? `<div class="pt-steps own" style="--n:${n}">${this._cells(l.steps, null, id, j)}</div>` : ''}
    </div>`;
  }

  renderGrid() {
    const p = this.p;
    if (!p) return;
    const n = p.bars * 16;
    const rows = [];
    for (const bdef of this.buses) {
      const id = bdef.id;
      const b = p.buses[id];
      const open = this.expanded.has(id);
      const nl = b.layers.length;
      if (bdef.melodic) {
        rows.push(`<div class="pt-bus bass" data-bus="${id}">
          <div class="pt-head"><span class="caret" data-act="expand">${open ? '▾' : '▸'}</span>
            <span class="dot" style="background:${bdef.color}"></span><span class="pt-name">${bdef.label}</span>
            <span class="pt-nl">${nl ? `${nl} layer` : 'nessun sample'}</span>${this._lock(id, b)}${this._mix(id, b)}</div>
          ${this._roll(b, n)}
          ${open ? `<div class="pt-layers">${b.layers.map((l, j) => this._layerRow(id, b, l, j)).join('')}
            <button class="btn small pt-add" data-act="add-layer" data-bus="${id}">+ layer</button></div>` : ''}
        </div>`);
        continue;
      }
      rows.push(`<div class="pt-bus" data-bus="${id}">
        <div class="pt-row">
          <div class="pt-head"><span class="caret" data-act="expand">${open ? '▾' : '▸'}</span>
            <span class="dot" style="background:${bdef.color}"></span><span class="pt-name">${bdef.label}</span>
            <span class="pt-nl">${nl ? `${nl} layer` : '—'}</span>${this._lock(id, b)}${this._alt(id, b)}</div>
          <div class="pt-steps" style="--n:${n}">${this._cells(b.steps, b.ratchet, id)}</div>
          ${this._mix(id, b)}
        </div>
        ${open ? `<div class="pt-layers">${b.layers.map((l, j) => this._layerRow(id, b, l, j)).join('')}
          <button class="btn small pt-add" data-act="add-layer" data-bus="${id}">+ layer</button></div>` : ''}
      </div>`);
    }
    $('#pt-grid').innerHTML = rows.join('');
    const anySample = Object.values(p.buses).some((b) => b.layers.length);
    const empty = $('#pt-empty');
    empty.hidden = anySample;
    empty.textContent = 'Nessun sample assegnato: scegli una cartella nella scheda Libreria (i bus si riempiono da soli), '
      + 'oppure usa "…" su un layer, "Invia" dalla Libreria e dalla scheda Online, o "Carica dal Drum Rack".';
    this._bindRoll();
  }

  // ---------------------------------------------------------------- bass piano roll
  _rollRange(b) {
    let lo = -12, hi = 12;
    for (const nt of b.notes) { lo = Math.min(lo, nt.semi); hi = Math.max(hi, nt.semi); }
    return [lo, hi];
  }

  _roll(b, n) {
    const [lo, hi] = this._rollRange(b);
    const names = this.meta.note_names;
    const root = (this.p.octave + 1) * 12 + names.indexOf(this.p.key);
    const rows = [];
    for (let s = hi; s >= lo; s--) {
      const midi = root + s;
      const nm = names[((midi % 12) + 12) % 12];
      rows.push(`<div class="pt-rrow ${nm.includes('#') ? 'black' : ''} ${s === 0 ? 'root' : ''}" data-semi="${s}">
        <span class="pt-rlabel">${nm}${Math.floor(midi / 12) - 2}</span></div>`);
    }
    const H = 12;
    const notes = b.notes.map((nt, k) => `<div class="pt-note ${nt.glide ? 'glide' : ''}" data-k="${k}"
        style="left:${(nt.step / n) * 100}%;width:${(nt.len / n) * 100}%;top:${(hi - nt.semi) * H}px;height:${H - 1}px"
        title="${nt.glide ? 'glide → ' : ''}Alt+clic: glide · trascina il bordo destro per allungare · clic: elimina"><span class="pt-rz"></span></div>`).join('');
    return `<div class="pt-roll-wrap"><div class="pt-roll" id="pt-roll" data-lo="${lo}" data-hi="${hi}" style="height:${(hi - lo + 1) * H}px">
      <div class="pt-rgrid" style="--n:${n}">${Array.from({ length: n }, (_, i) => `<span class="${i % 4 === 0 ? 'beat' : ''} ${i % 16 === 0 ? 'bar' : ''}"></span>`).join('')}</div>
      ${rows.join('')}<div class="pt-rnotes">${notes}<div id="pt-roll-head" class="pt-rhead" style="display:none"></div></div></div></div>`;
  }

  _bindRoll() {
    const roll = $('#pt-roll');
    if (!roll) return;
    const notesBox = roll.querySelector('.pt-rnotes');
    const H = 12;
    const n = this.p.bars * 16;
    const hi = +roll.dataset.hi;
    const bus = this.p.buses.bass;
    const pos = (e) => {
      const r = notesBox.getBoundingClientRect();
      return { step: Math.max(0, Math.min(n - 1, Math.floor(((e.clientX - r.left) / r.width) * n))),
        semi: hi - Math.floor((e.clientY - r.top) / H) };
    };
    notesBox.onpointerdown = (e) => {
      e.preventDefault();
      const noteEl = e.target.closest('.pt-note');
      const start = pos(e);
      if (noteEl) {
        const nt = bus.notes[+noteEl.dataset.k];
        if (e.altKey) { nt.glide = !nt.glide; this._persist(); this.renderGrid(); return; }
        const resize = e.target.classList.contains('pt-rz');
        const orig = { ...nt };
        let moved = false;
        const move = (ev) => {
          const q = pos(ev);
          if (q.step !== start.step || q.semi !== start.semi) moved = true;
          if (resize) nt.len = Math.max(1, Math.min(n - nt.step, orig.len + q.step - start.step));
          else { nt.step = Math.max(0, Math.min(n - nt.len, orig.step + q.step - start.step)); nt.semi = orig.semi + q.semi - start.semi; }
          noteEl.style.left = `${(nt.step / n) * 100}%`;
          noteEl.style.width = `${(nt.len / n) * 100}%`;
          noteEl.style.top = `${(hi - nt.semi) * H}px`;
        };
        const up = () => {
          window.removeEventListener('pointermove', move);
          window.removeEventListener('pointerup', up);
          if (!moved && !resize) bus.notes.splice(+noteEl.dataset.k, 1);
          this._persist();
          this.renderGrid();
          if (moved) this._auditionBass(nt.semi);
        };
        window.addEventListener('pointermove', move);
        window.addEventListener('pointerup', up);
        return;
      }
      const nt = { step: start.step, len: 2, semi: start.semi, vel: 100, glide: false };
      nt.len = Math.max(1, Math.min(nt.len, n - nt.step));
      bus.notes.push(nt);
      this._persist();
      this.renderGrid();
      this._auditionBass(nt.semi);
    };
  }

  _auditionBass(semi) {
    const l = this.seq._layers(this.p.buses.bass)[0];
    if (l) { this.seq.setPattern(this.p); this.seq.audition(l.ref, this.seq.bassSemis(l, semi), 'bass'); }
  }

  // ---------------------------------------------------------------- grid events
  _toggle(cell, e, right = false) {
    const i = +cell.dataset.i;
    const bus = this.p.buses[cell.dataset.bus];
    const layer = cell.dataset.layer !== undefined ? bus.layers[+cell.dataset.layer] : null;
    const steps = layer ? layer.steps : bus.steps;
    if (right && !layer) {
      const r = bus.ratchet[i] || 1;
      if (!steps[i]) { steps[i] = 100; bus.ratchet[i] = 2; } else bus.ratchet[i] = r >= 4 ? 1 : r + 1;
    } else if (e.shiftKey) steps[i] = steps[i] === 127 ? 100 : 127;
    else if (e.altKey) steps[i] = steps[i] && steps[i] < 70 ? 0 : 55;
    else { steps[i] = steps[i] ? 0 : 100; if (!steps[i] && !layer) bus.ratchet[i] = 1; }
    const v = steps[i];
    cell.className = `pt-cell ${!v ? '' : v >= 120 ? 'on acc' : v < 70 ? 'on ghost' : 'on'} ${i % 4 === 0 ? 'beat' : ''} ${i % 16 === 0 ? 'bar' : ''}`;
    cell.innerHTML = !layer && bus.ratchet[i] > 1 && v ? `<i>${bus.ratchet[i]}</i>` : '';
    this._persist();
    if (v && !this.seq.playing) for (const l of this.seq._layers(bus)) this.seq.audition(l.ref, l.pitch || 0, cell.dataset.bus);
  }

  _onGridContext(e) {
    const cell = e.target.closest('.pt-cell');
    if (!cell) return;
    e.preventDefault();
    this._toggle(cell, e, true);
  }

  async _onGridClick(e) {
    const cell = e.target.closest('.pt-cell');
    if (cell) { this._toggle(cell, e); return; }
    const t = e.target.closest('[data-act]');
    if (!t) return;
    const busEl = t.closest('[data-bus]');
    const id = t.dataset.bus || busEl?.dataset.bus;
    const bus = this.p.buses[id];
    const layerEl = t.closest('.pt-layer');
    const j = layerEl ? +layerEl.dataset.layer : null;
    const layer = j !== null ? bus.layers[j] : null;
    switch (t.dataset.act) {
      case 'expand': this.expanded.has(id) ? this.expanded.delete(id) : this.expanded.add(id); this.renderGrid(); return;
      case 'mute': bus.mute = !bus.mute; break;
      case 'lock': bus.lock = !bus.lock; break;
      case 'reseed': bus.alt = { mode: bus.alt?.mode || 'random', seed: newSeed() }; break;
      case 'solo': bus.solo = !bus.solo; break;
      case 'lmute': layer.mute = !layer.mute; break;
      case 'lsolo': layer.solo = !layer.solo; break;
      case 'select-layer': this.selected[id] = j; break;
      case 'audition':
        if (layer?.ref) this.seq.audition(layer.ref, id === 'bass' ? this.seq.bassSemis(layer, 0) : layer.pitch || 0, id);
        return;
      case 'del-layer': bus.layers.splice(j, 1); this.selected[id] = 0; break;
      case 'own-steps': layer.steps = layer.steps ? null : [...bus.steps]; break;
      case 'add-layer': return this.openChooser(id, 'add');
      case 'choose': this.selected[id] = j; return this.openChooser(id, 'replace');
      case 'next': return this.nextCandidate(id, j);
      default: return;
    }
    this._persist();
    this.renderGrid();
  }

  _onGridInput(e, committed = false) {
    const el = e.target;
    const id = el.dataset.bus || el.closest('[data-bus]')?.dataset.bus;
    if (!id) return;
    const bus = this.p.buses[id];
    if (el.dataset.field === 'volume' || el.dataset.field === 'pan') bus[el.dataset.field] = +el.value;
    else if (el.dataset.field === 'alt') {
      if (!committed) return;
      bus.alt = { mode: el.value, seed: bus.alt?.seed || newSeed() };
      this._persist();
      this.renderGrid();
      return;
    }
    else if (el.dataset.field === 'filter') {
      const [kind, f] = (el.value || ':').split(':');
      bus.hp = kind === 'hp' ? +f : 0;
      bus.lp = kind === 'lp' ? +f : 0;
    } else if (el.dataset.lfield) {
      const layer = bus.layers[+el.closest('.pt-layer').dataset.layer];
      const f = el.dataset.lfield;
      layer[f] = f === 'root' ? (el.value === '' ? null : +el.value) : +el.value;
    } else return;
    this._persist();
    this.seq.updateMix();
    if (committed && el.dataset.lfield === 'pitch') {
      const layer = bus.layers[+el.closest('.pt-layer').dataset.layer];
      if (layer.ref) this.seq.audition(layer.ref, layer.pitch, id);
    }
  }

  async nextCandidate(id, j) {
    const cands = await this.api.pattern_candidates(id, '', 200);
    if (!cands.length) { toast('Nessun sample di questa classe nella libreria'); return; }
    const bus = this.p.buses[id];
    const cur = bus.layers[j]?.ref;
    const k = cands.findIndex((c) => cur && c.path === cur.path);
    const ref = cands[(k + 1) % cands.length];
    this.selected[id] = j;
    await this.addSample(id, ref, 'replace');
    this.seq.audition(ref, id === 'bass' ? this.seq.bassSemis(this.p.buses.bass.layers[j], 0) : bus.layers[j].pitch || 0, id);
  }

  // ---------------------------------------------------------------- chooser
  async openChooser(busId, mode) {
    const bdef = this.busById[busId];
    let modal = $('#pt-chooser');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'pt-chooser';
      modal.className = 'modal';
      document.body.appendChild(modal);
    }
    modal.hidden = false;
    modal.innerHTML = `<div class="modal-box chooser">
      <h3><span class="dot" style="background:${bdef.color}"></span> ${mode === 'add' ? 'Aggiungi layer a' : 'Sostituisci sample in'} ${esc(bdef.label)}</h3>
      <div class="seg ch-tabs"><button class="seg-btn active" data-tab="lib">Libreria</button><button class="seg-btn" data-tab="web">Online (sessione)</button><button class="seg-btn" data-tab="file">File…</button></div>
      <input class="search" id="ch-q" type="search" placeholder="Cerca nella libreria (vuoto = classi del bus)…">
      <div id="ch-list" class="ch-list"></div>
      <div class="modal-actions"><button class="btn" id="ch-close">Chiudi</button></div></div>`;
    const list = $('#ch-list', modal);
    const show = async (tab) => {
      modal.querySelectorAll('.ch-tabs .seg-btn').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
      $('#ch-q', modal).hidden = tab !== 'lib';
      if (tab === 'file') {
        const ref = await this.api.pick_sample_file();
        if (ref) { modal.hidden = true; await this.addSample(busId, ref, mode); }
        else show('lib');
        return;
      }
      const refs = tab === 'lib' ? await this.api.pattern_candidates(busId, $('#ch-q', modal).value, 300) : this.onlineRefs;
      list.innerHTML = refs.length ? refs.map((r, i) => `<div class="ch-row" data-i="${i}">
          <button class="pt-ib" data-ch="play">▶</button>
          <span class="dot" style="background:${this.classColor[r.cls] || 'transparent'}"></span>
          <span class="ch-name" title="${esc(r.path || r.url || '')}">${esc(r.name)}</span>
          <span class="ch-meta">${r.kind === 'online' ? esc(r.source_label || '') + ' · ' + esc(r.license_label || '') : r.conf !== undefined ? Math.round(r.conf * 100) + '%' : ''}</span>
          <button class="btn small primary" data-ch="use">Usa</button></div>`).join('')
        : `<div class="hint">${tab === 'lib' ? 'Nessun sample: analizza una cartella nella scheda Libreria.' : 'Nessun sample online usato in questa sessione: usa "→ bus" nella scheda Online.'}</div>`;
      list.onclick = async (e) => {
        const b = e.target.closest('[data-ch]');
        if (!b) return;
        const ref = refs[+b.closest('.ch-row').dataset.i];
        if (b.dataset.ch === 'play') this.seq.audition(ref, 0, busId);
        else { modal.hidden = true; await this.addSample(busId, ref, mode); }
      };
    };
    modal.querySelector('.ch-tabs').onclick = (e) => { const b = e.target.closest('[data-tab]'); if (b) show(b.dataset.tab); };
    let qt;
    $('#ch-q', modal).oninput = () => { clearTimeout(qt); qt = setTimeout(() => show('lib'), 250); };
    $('#ch-close', modal).onclick = () => { modal.hidden = true; };
    show('lib');
  }
}

export { suggestBus, refKey };
