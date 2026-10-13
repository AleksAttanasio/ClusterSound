// Sequence panel of the Pattern screen: chain patterns (any genre) into a full arrangement.
// The kit (samples, layers, mix) is the one of the pattern editor; every block stores only its groove.
import { toast } from './sendmenu.js';
import { sendToLive } from './live.js';
import { btn, setPlayButton } from './kit.js';
import { svg } from './icons.js';

// Drum notes in exported MIDI: 'drumrack' (C1… as an Ableton Drum Rack) or 'gm' (General MIDI).
// Chosen in Settings › Sequencer; pattern and song export read it from here.
const LS_MIDI_MAP = 'cs.seq.midiMap';
export const midiMap = () => { try { return localStorage.getItem(LS_MIDI_MAP) === 'gm' ? 'gm' : 'drumrack'; } catch { return 'drumrack'; } };
export const setMidiMap = (v) => { try { localStorage.setItem(LS_MIDI_MAP, v === 'gm' ? 'gm' : 'drumrack'); } catch { /* private mode */ } };

const $ = (s, root = document) => root.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const clone = (o) => JSON.parse(JSON.stringify(o));
const LS_KEY = 'clustersound.sequence';
const PX_PER_BAR = 56; // card width = 130 px + 56 px per bar: longer blocks look longer
const DRAG_TYPE = 'text/plain';
const uid = () => 'b' + Math.random().toString(36).slice(2, 9);
const fmtTime = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;

export function grooveOf(p) {
  const buses = {};
  for (const [id, b] of Object.entries(p.buses)) if (id !== 'bass') buses[id] = { steps: [...b.steps], ratchet: [...b.ratchet] };
  return { bars: p.bars, swing: p.swing, buses, bass: { notes: clone(p.buses.bass.notes) } };
}

export function applyGroove(p, g) {
  const n = g.bars * 16;
  p.bars = g.bars;
  p.swing = g.swing;
  for (const [id, b] of Object.entries(p.buses)) {
    if (id === 'bass') { b.notes = clone(g.bass.notes); continue; }
    const gb = g.buses[id] || {};
    b.steps = Array.from({ length: n }, (_, i) => gb.steps?.[i] || 0);
    b.ratchet = Array.from({ length: n }, (_, i) => gb.ratchet?.[i] || 1);
    for (const l of b.layers) if (l.steps) l.steps = Array.from({ length: n }, (_, i) => l.steps[i % l.steps.length]);
  }
}

export class Arranger {
  constructor(editor) {
    this.ed = editor;
    this.api = editor.api;
    this.seq = { name: 'Sequenza', blocks: [] };
    this.editing = null;   // index of the block shown in the grid (null = free pattern)
    this.free = null;      // the free pattern kept aside while a block is edited
    this.playing = false;
    this.flat = null;
    this.follow = true;
    this.open = true;
    try {
      const saved = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
      if (saved && Array.isArray(saved.blocks)) this.seq = saved;
    } catch (e) { /* private mode */ }
  }

  // ---------------------------------------------------------------- shell
  mount(root) {
    this.root = root;
    root.innerHTML = `
      <div class="sq-head">
        <button class="sq-toggle" data-a="toggle" title="Mostra/nascondi la sequenza">${svg('chevron-down')}</button>
        <span class="sq-title">Sequenza</span>
        <wa-input id="sq-name" class="sq-name" size="s" value="" title="Nome della sequenza (usato nell'export)"></wa-input>
        <span id="sq-info" class="sq-info"></span>
        ${btn('<wa-icon slot="start" name="play"></wa-icon>Play sequenza', { variant: 'brand', id: 'sq-play', 'data-a': 'play', title: 'Suona tutta la sequenza' })}
        <wa-checkbox size="s" class="sq-follow" id="sq-follow" checked title="Durante la riproduzione la griglia mostra il blocco che sta suonando">Segui</wa-checkbox>
        <div class="spacer"></div>
        ${btn('Pattern corrente', { icon: 'plus', 'data-a': 'add-current', title: 'Aggiunge in fondo il pattern che vedi nella griglia (con le tue modifiche)' })}
        ${btn('Salva…', { icon: 'save', 'data-a': 'save' })}
        <wa-select id="sq-open" class="sq-open" size="s" placeholder="Apri…" title="Apri una sequenza salvata"></wa-select>
        ${btn('Svuota', { icon: 'trash-2', 'data-a': 'clear' })}
        <span class="sq-exp">Esporta sequenza:</span>
        <wa-button-group label="Esporta sequenza">
          ${btn('MIDI', { 'data-a': 'exp-midi' })}${btn('WAV', { 'data-a': 'exp-wav' })}${btn('Live', { 'data-a': 'exp-live', title: 'Crea in Live le tracce della sequenza (serve il device ClusterSound nel set)' })}
        </wa-button-group>
        ${btn('Ableton', { variant: 'brand', icon: 'file-down', 'data-a': 'exp-abl' })}
      </div>
      <div class="sq-body">
        <div id="sq-track" class="sq-track"></div>
        <div id="sq-banner" class="sq-banner" hidden></div>
      </div>`;
    root.addEventListener('click', (e) => this._onClick(e));
    $('#sq-name').oninput = (e) => { this.seq.name = e.target.value || 'Sequenza'; this._save(); };
    $('#sq-follow').onchange = (e) => { this.follow = e.target.checked; };
    $('#sq-open').onchange = (e) => this._openSaved(e.target.value);
    const track = $('#sq-track');
    track.addEventListener('dragover', (e) => this._dragOver(e));
    track.addEventListener('dragleave', (e) => { if (!track.contains(e.relatedTarget)) this._hideMarker(); });
    track.addEventListener('drop', (e) => this._drop(e));
    track.addEventListener('dragstart', (e) => {
      const card = e.target.closest('.sq-card');
      if (!card) return;
      e.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ type: 'block', index: +card.dataset.i }));
      e.dataTransfer.effectAllowed = 'move';
      card.classList.add('dragging');
    });
    track.addEventListener('dragend', () => { document.querySelectorAll('.sq-card.dragging').forEach((c) => c.classList.remove('dragging')); this._hideMarker(); });
    // variant chips of the editor are drag sources (and double click = append)
    const chips = $('#pt-variants');
    chips.addEventListener('dragstart', (e) => {
      const b = e.target.closest('[data-variant],[data-user]');
      if (!b) return;
      const payload = b.dataset.user ? { type: 'user', id: b.dataset.user } : { type: 'variant', genre: this.ed.p.genre, variant: +b.dataset.variant };
      e.dataTransfer.setData(DRAG_TYPE, JSON.stringify(payload));
      e.dataTransfer.effectAllowed = 'copy';
      $('#sq-track').classList.add('drop-ready');
    });
    chips.addEventListener('dragend', () => $('#sq-track').classList.remove('drop-ready'));
    chips.addEventListener('dblclick', (e) => {
      const b = e.target.closest('[data-variant],[data-user]');
      if (!b) return;
      const payload = b.dataset.user ? { type: 'user', id: b.dataset.user } : { type: 'variant', genre: this.ed.p.genre, variant: +b.dataset.variant };
      this._insertFrom(payload, this.seq.blocks.length);
    });
    this.render();
    this._refreshSaved();
  }

  _save() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(this.seq)); } catch (e) { /* private mode */ }
  }

  // ---------------------------------------------------------------- blocks
  labelFor(genreId, name) {
    const g = this.ed.meta.genres.find((x) => x.id === genreId);
    return `${g ? g.name : 'Pattern'} · ${name}`;
  }

  async _blockFrom(payload) {
    if (payload.type === 'variant') {
      const p = await this.api.pattern_build(payload.genre, payload.variant);
      return { id: uid(), label: this.labelFor(payload.genre, p.name), source: { genre: payload.genre, variant: payload.variant }, repeat: 1, groove: grooveOf(p) };
    }
    if (payload.type === 'user') {
      const u = this.ed.meta.user.find((x) => x.id === payload.id);
      if (!u) return null;
      return { id: uid(), label: this.labelFor(u.genre, `★ ${u.name}`), source: { genre: u.genre, user: u.id }, repeat: 1, groove: grooveOf(u) };
    }
    return null;
  }

  async _insertFrom(payload, at) {
    if (payload.type === 'block') {
      const [b] = this.seq.blocks.splice(payload.index, 1);
      const to = at > payload.index ? at - 1 : at;
      this.seq.blocks.splice(to, 0, b);
      if (this.editing !== null) this.editing = this.seq.blocks.indexOf(this._editingBlock);
    } else {
      const b = await this._blockFrom(payload);
      if (!b) return;
      this.seq.blocks.splice(at, 0, b);
      toast(`Aggiunto alla sequenza: ${b.label}`);
    }
    this._changed();
  }

  addCurrent() {
    const p = this.ed.p;
    const label = this.editing !== null ? `${this.seq.blocks[this.editing].label} (copia)` : this.labelFor(p.genre, p.name);
    this.seq.blocks.push({ id: uid(), label, source: { ...(this.ed.source || {}) }, repeat: 1, groove: grooveOf(p) });
    this._changed();
    toast(`Aggiunto alla sequenza: ${label}`);
  }

  _changed() {
    this._save();
    this.render();
    if (this.playing) this._reflattenSoon();
  }

  // ---------------------------------------------------------------- editing a block in the grid
  editBlock(k) {
    if (k === this.editing) return;
    const b = this.seq.blocks[k];
    if (!b) return;
    if (this.editing === null) this.free = { groove: grooveOf(this.ed.p), name: this.ed.p.name, genre: this.ed.p.genre, source: clone(this.ed.source || {}) };
    this.editing = k;
    this._editingBlock = b;
    applyGroove(this.ed.p, b.groove);
    this.ed.p.name = b.label.split(' · ').slice(1).join(' · ') || b.label;
    if (b.source?.genre) this.ed.p.genre = b.source.genre;
    this.ed.source = clone(b.source || {});
    this.ed._persist(true);
    this.ed.renderAll();
    this.render();
  }

  backToFree() {
    if (this.editing === null) return;
    this.editing = null;
    this._editingBlock = null;
    if (this.free) {
      applyGroove(this.ed.p, this.free.groove);
      this.ed.p.name = this.free.name;
      this.ed.p.genre = this.free.genre;
      this.ed.source = this.free.source;
    }
    this.ed._persist(true);
    this.ed.renderAll();
    this.render();
  }

  // called by the editor after every change of its pattern
  onPatternChanged() {
    if (this.editing === null) return;
    const b = this.seq.blocks[this.editing];
    if (!b) { this.editing = null; return; }
    b.groove = grooveOf(this.ed.p);
    const src = this.ed.source || {};
    if (src.genre && (src.genre !== b.source?.genre || src.variant !== b.source?.variant || src.user !== b.source?.user)) {
      b.source = clone(src);   // a different variant was chosen while editing this block
      b.label = this.labelFor(this.ed.p.genre, this.ed.p.name);
    }
    this._save();
    this._drawCard(this.editing);
    this._info();
    if (this.playing) this._reflattenSoon();
  }

  // ---------------------------------------------------------------- playback
  async play(fromBlock = 0) {
    if (!this.seq.blocks.length) { toast('La sequenza è vuota: trascina qui qualche variante'); return; }
    this.ed.stop();
    const flat = await this.api.sequence_flatten(this.ed.p, this.seq);
    if (flat.error) { toast(flat.error); return; }
    this.flat = flat;
    await this.ed.seq.preload(flat);
    this.ed.playMode = 'sequence';
    this.ed.seq.setPattern(flat);
    const sec = flat.sections.find((s) => s.index === fromBlock) || flat.sections[0];
    this.ed.seq.start(sec.start_bar * 16);
    this.playing = true;
    setPlayButton($('#sq-play'), true, 'Play sequenza');
    this.ed._meterLoop();
  }

  stop() { this.ed.stop(); }

  onStopped() {
    this.playing = false;
    const b = $('#sq-play');
    setPlayButton(b, false, 'Play sequenza');
    this._cursor(null);
    document.querySelectorAll('.sq-card.now').forEach((c) => c.classList.remove('now'));
  }

  _reflattenSoon() {
    clearTimeout(this._rt);
    this._rt = setTimeout(async () => {
      if (!this.playing) return;
      const flat = await this.api.sequence_flatten(this.ed.p, this.seq);
      if (flat.error || !this.playing) return;
      this.flat = flat;
      await this.ed.seq.preload(flat);
      this.ed.seq.setPattern(flat);
    }, 150);
  }

  // global step of the flattened sequence -> local step of the block shown in the grid (or -1)
  onStep(i) {
    if (i < 0 || !this.flat) { this._cursor(null); return -1; }
    const bar = Math.floor(i / 16);
    const sec = this.flat.sections.find((s) => bar >= s.start_bar && bar < s.start_bar + s.bars);
    if (!sec) return -1;
    document.querySelectorAll('.sq-card').forEach((c) => c.classList.toggle('now', +c.dataset.i === sec.index));
    const blockSteps = (sec.bars / sec.repeat) * 16;
    const local = (i - sec.start_bar * 16) % blockSteps;
    this._cursor(sec.index, (i - sec.start_bar * 16) / (sec.bars * 16));
    if (this.follow && this.editing !== sec.index) this.editBlock(sec.index);
    return this.editing === sec.index ? local : -1;
  }

  _cursor(index, frac = 0) {
    const cur = $('#sq-cursor');
    if (!cur) return;
    const card = index === null ? null : this.root.querySelector(`.sq-card[data-i="${index}"]`);
    if (!card) { cur.style.display = 'none'; return; }
    cur.style.display = '';  // cursor lives inside the (positioned) track, so it scrolls with the cards
    cur.style.left = `${card.offsetLeft + frac * card.offsetWidth}px`;
  }

  // ---------------------------------------------------------------- export
  async _export(kind) {
    if (!this.seq.blocks.length) { toast('La sequenza è vuota'); return; }
    const flat = await this.api.sequence_flatten(this.ed.p, this.seq);
    if (flat.error) { toast(flat.error); return; }
    if (kind === 'midi') {
      const p = await this.api.export_midi(flat, midiMap());
      if (p) toast(`MIDI della sequenza salvato: ${p.split('/').pop()}`);
    } else if (kind === 'wav') {
      toast('Rendering della sequenza…');
      const p = await this.api.export_wav(flat);
      if (p) toast(`WAV salvato: ${p.split('/').pop()}`);
    } else if (kind === 'live') {
      await sendToLive(this.api, 'sequence', flat);
    } else {
      toast('Preparazione pacchetto Ableton…');
      const r = await this.api.export_ableton(flat);
      if (r.error) alert(r.error); else if (r.folder) toast(`Pacchetto creato: ${r.folder.split('/').pop()}`);
    }
  }

  // ---------------------------------------------------------------- saved sequences
  async _refreshSaved() {
    const list = await this.api.list_sequences();
    this.saved = list;
    $('#sq-open').innerHTML = list.length ? list.map((s) => `<wa-option value="${esc(s.id)}">${esc(s.name)} (${s.blocks.length} blocchi)</wa-option>`).join('')
      : '<wa-option value="none" disabled>Nessuna sequenza salvata</wa-option>';
  }

  async _saveAs() {
    const name = prompt('Nome della sequenza', this.seq.name || 'Sequenza');
    if (!name) return;
    this.seq.name = name;
    // the kit (samples, layers, mix) goes with the saved copy, so the Max for Live device can import it as heard
    const saved = await this.api.save_sequence({ ...this.seq, kit: clone(this.ed.p) });
    this.seq.id = saved.id;
    this._save();
    this.render();
    this._refreshSaved();
    toast(`Sequenza "${name}" salvata`);
  }

  _openSaved(id) {
    $('#sq-open').value = '';
    const s = (this.saved || []).find((x) => x.id === id);
    if (!s) return;
    if (this.seq.blocks.length && !confirm('Sostituire la sequenza attuale?')) return;
    this.backToFree();
    this.seq = clone(s);
    delete this.seq.kit;  // the editor keeps its own kit; the saved one is for Live
    this._changed();
  }

  // ---------------------------------------------------------------- drag & drop
  _insertIndex(e) {
    const cards = [...this.root.querySelectorAll('.sq-card')];
    for (const c of cards) {
      const r = c.getBoundingClientRect();
      if (e.clientX < r.left + r.width / 2) return +c.dataset.i;
    }
    return cards.length;
  }

  _dragOver(e) {
    e.preventDefault();
    const at = this._insertIndex(e);
    const cards = [...this.root.querySelectorAll('.sq-card')];
    const m = $('#sq-marker');
    let x;
    if (!cards.length) x = 8;
    else if (at < cards.length) x = cards[at].offsetLeft - 4;
    else x = cards[cards.length - 1].offsetLeft + cards[cards.length - 1].offsetWidth + 3;
    m.style.display = '';
    m.style.left = `${x}px`;
  }

  _hideMarker() { const m = $('#sq-marker'); if (m) m.style.display = 'none'; $('#sq-track')?.classList.remove('drop-ready'); }

  async _drop(e) {
    e.preventDefault();
    const at = this._insertIndex(e);
    this._hideMarker();
    let payload;
    try { payload = JSON.parse(e.dataTransfer.getData(DRAG_TYPE)); } catch (err) { return; }
    await this._insertFrom(payload, at);
  }

  // ---------------------------------------------------------------- clicks
  _onClick(e) {
    const a = e.target.closest('[data-a]');
    const card = e.target.closest('.sq-card');
    if (!a && card) { this.editBlock(+card.dataset.i); return; }
    if (!a) return;
    const k = card ? +card.dataset.i : null;
    const b = k !== null ? this.seq.blocks[k] : null;
    switch (a.dataset.a) {
      case 'toggle': this.open = !this.open; this.render(); return;
      case 'play': if (this.playing) this.stop(); else this.play(0); return;
      case 'play-from': this.play(k); return;
      case 'add-current': this.addCurrent(); return;
      case 'save': this._saveAs(); return;
      case 'clear':
        if (this.seq.blocks.length && confirm('Svuotare la sequenza?')) { this.backToFree(); this.seq.blocks = []; this._changed(); }
        return;
      case 'back': this.backToFree(); return;
      case 'rep-': b.repeat = Math.max(1, (b.repeat || 1) - 1); break;
      case 'rep+': b.repeat = Math.min(32, (b.repeat || 1) + 1); break;
      case 'dup': this.seq.blocks.splice(k + 1, 0, { ...clone(b), id: uid() }); break;
      case 'ren': {
        const name = prompt('Nome del blocco', b.label);
        if (!name) return;
        b.label = name;
        break;
      }
      case 'del':
        if (this.editing === k) this.backToFree();
        else if (this.editing !== null && this.editing > k) this.editing -= 1;
        this.seq.blocks.splice(k, 1);
        break;
      case 'exp-midi': this._export('midi'); return;
      case 'exp-wav': this._export('wav'); return;
      case 'exp-abl': this._export('abl'); return;
      case 'exp-live': this._export('live'); return;
      default: return;
    }
    e.stopPropagation();
    this._changed();
  }

  // ---------------------------------------------------------------- render
  _info() {
    const bars = this.seq.blocks.reduce((s, b) => s + b.groove.bars * (b.repeat || 1), 0);
    const secs = (bars * 4 * 60) / (this.ed.p?.bpm || 120);
    const el = $('#sq-info');
    if (el) el.textContent = this.seq.blocks.length ? `${this.seq.blocks.length} blocchi · ${bars} battute · ${fmtTime(secs)} a ${Math.round(this.ed.p?.bpm || 120)} BPM` : '';
  }

  render() {
    if (!this.root) return;
    this.root.classList.toggle('closed', !this.open);
    $('.sq-toggle', this.root).innerHTML = svg(this.open ? 'chevron-down' : 'chevron-right');
    $('#sq-name').value = this.seq.name || 'Sequenza';
    this._info();
    const track = $('#sq-track');
    let bar = 1;
    const cards = this.seq.blocks.map((b, i) => {
      const len = b.groove.bars * (b.repeat || 1);
      const html = `<div class="sq-card ${this.editing === i ? 'editing' : ''}" draggable="true" data-i="${i}" style="width:${130 + len * PX_PER_BAR}px" title="Clic: mostra e modifica nella griglia · trascina per spostare">
        <div class="sq-card-top"><span class="sq-num">${i + 1}</span><span class="sq-label">${esc(b.label)}</span>
          <button class="sq-ib" data-a="play-from" title="Suona da qui">${svg('play', 10)}</button></div>
        <canvas class="sq-thumb" data-i="${i}"></canvas>
        <div class="sq-card-bot"><span class="sq-bars">Batt. ${bar}–${bar + len - 1}</span>
          <span class="sq-rep"><button class="sq-ib" data-a="rep-">${svg('minus', 10)}</button><b>×${b.repeat || 1}</b><button class="sq-ib" data-a="rep+">${svg('plus', 10)}</button></span>
          <span class="sq-tools"><button class="sq-ib" data-a="dup" title="Duplica">${svg('copy', 10)}</button><button class="sq-ib" data-a="ren" title="Rinomina">${svg('pencil', 10)}</button><button class="sq-ib danger" data-a="del" title="Elimina">${svg('x', 10)}</button></span></div>
      </div>`;
      bar += len;
      return html;
    });
    track.innerHTML = (cards.length ? cards.join('') : `<div class="sq-empty">Trascina qui le varianti (i chip sopra, anche di generi diversi: cambia genere dal menu) per comporre la sequenza.
      Doppio clic su un chip = aggiungi in fondo · "+ Pattern corrente" = aggiungi quello che vedi nella griglia.</div>`)
      + '<div id="sq-marker" class="sq-marker" style="display:none"></div><div id="sq-cursor" class="sq-cursor" style="display:none"></div>';
    this.seq.blocks.forEach((_, i) => this._drawCard(i));
    const banner = $('#sq-banner');
    if (this.editing !== null && this.seq.blocks[this.editing]) {
      banner.hidden = false;
      banner.innerHTML = `${svg('pencil', 12)} <span>Nella griglia stai modificando il <b>blocco ${this.editing + 1}</b> · ${esc(this.seq.blocks[this.editing].label)} — ogni modifica aggiorna il blocco.</span>
        ${btn('Torna al pattern libero', { size: 'xs', 'data-a': 'back' })}`;
    } else banner.hidden = true;
  }

  _drawCard(i) {
    const b = this.seq.blocks[i];
    const cv = this.root.querySelector(`canvas.sq-thumb[data-i="${i}"]`);
    if (!b || !cv) return;
    const dpr = window.devicePixelRatio || 1;
    const w = cv.clientWidth, h = cv.clientHeight;
    cv.width = w * dpr; cv.height = h * dpr;
    const ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const g = b.groove;
    const reps = b.repeat || 1;
    const n = g.bars * 16;
    const total = n * reps;
    const sx = w / total;
    const buses = this.ed.buses.filter((x) => !x.melodic && g.buses[x.id]?.steps.some((v) => v));
    const bassH = g.bass.notes.length ? 12 : 0;
    const rowH = Math.max(3, Math.min(8, (h - bassH - 2) / Math.max(1, buses.length)));
    for (let r = 0; r < reps; r++) {
      const x0 = r * n * sx;
      // bar lines
      for (let k = 0; k < g.bars; k++) {
        ctx.fillStyle = k === 0 ? 'rgba(255,255,255,.22)' : 'rgba(255,255,255,.08)';
        ctx.fillRect(x0 + k * 16 * sx, 0, 1, h);
      }
      buses.forEach((bus, row) => {
        const steps = g.buses[bus.id].steps;
        ctx.fillStyle = bus.color;
        for (let s = 0; s < n; s++) {
          const v = steps[s];
          if (!v) continue;
          ctx.globalAlpha = v >= 120 ? 1 : v < 70 ? 0.45 : 0.8;
          ctx.fillRect(x0 + s * sx + 0.5, 1 + row * rowH, Math.max(1.5, sx - 1), rowH - 1);
        }
      });
      ctx.globalAlpha = 1;
      if (bassH) {
        const semis = g.bass.notes.map((nt) => nt.semi);
        const lo = Math.min(...semis), hi = Math.max(...semis);
        ctx.fillStyle = this.ed.busById.bass.color;
        for (const nt of g.bass.notes) {
          const y = h - 3 - ((nt.semi - lo) / Math.max(1, hi - lo)) * (bassH - 4);
          ctx.fillRect(x0 + nt.step * sx, y - 1.5, Math.max(2, nt.len * sx - 1), 3);
        }
      }
    }
  }
}
