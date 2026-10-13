// "Drum Rack" screen: 8×8 pads (Launchpad Pro layout) or a Roland SPD-SX (9 pads + pedal / Trig 2), grouped
// by a geometry / configuration and filled with a seed sample plus similar ones; exported as an Ableton Drum Rack.
import { refKey } from './sequencer.js';
import { toast, suggestBus, showPopover } from './sendmenu.js';
import { sendToLive } from './live.js';
import { NO_ALT, dynControls, wireDynControls, readDynControls } from './pattern.js';
import { btn, openDialog } from './kit.js';
import { svg } from './icons.js';

const $ = (s, root = document) => root.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LS_KEY = 'clustersound.rack';
const LS_SPD = 'clustersound.rack.spdsx';
const LS_DEVICE = 'clustersound.rackDevice';
const DEVICES = [['grid64', 'Controller 8×8 (Launchpad)'], ['spdsx', 'Roland SPD-SX']];
const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const noteName = (n) => `${NOTE_NAMES[n % 12]}${Math.floor(n / 12) - 2}`; // Live: C1 = 36
const HAT_FAMILIES = new Set(['chat', 'ohat', 'hats']);
const MODES = [['nearest', 'Più simili'], ['random', 'Casuale'], ['manual', 'Manuale'], ['trail', 'Percorso']];
const KIND_BADGE = { library: '', online: 'WEB', file: 'FILE' };
const DRAG_TYPE = 'application/x-clustersound-rack';
const LS_RANDOM = 'clustersound.randomRack';
const MAX_PER_BUS = 8;
const PEDAL_ICON = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 20h16M7 20l3-12h4l3 12M10 8l-1-4h6l-1 4"/></svg>';
const ALT_LABELS = [['off', 'insieme (solo il 1° attivo)'], ['cycle', 'a giro'], ['random', 'casuale'], ['random_pass', 'casuale ogni giro']];

const newRack = () => ({ name: 'Kit', geometry: 'cols8', mapping: 'launchpad', pads: new Array(64).fill(null), groups: {} });
const newSpdRack = () => ({ device: 'spdsx', name: 'Kit SPD-SX', geometry: 'spd_kit', triggers: { trig1: true, trig2: false },
  pads: new Array(11).fill(null), groups: {} });

export class DrumRackEditor {
  constructor({ api, player, classes, getTrail, getSequencer, onOpenSequencer }) {
    this.api = api;
    this.getSequencer = getSequencer;      // -> PatternEditor
    this.onOpenSequencer = onOpenSequencer;
    this.player = player;
    this.getTrail = getTrail;              // -> [{id, name}] last similar-samples trail of the 3D view
    this.classColor = Object.fromEntries(classes.map((c) => [c.id, c.color]));
    this.classLabel = Object.fromEntries(classes.map((c) => [c.id, c.label]));
    this.ready = null;
    this.device = 'grid64';                // 'grid64' | 'spdsx': one kit per device, this.rack is the active one
    this.racks = { grid64: newRack(), spdsx: newSpdRack() };
    this.pads = { grid64: 0, spdsx: 4 };   // selected pad per device (its group is the target of every fill)
    this.check = null;                     // SPD-SX: {warnings, allowed} from rack_check
    this.seed = null;                      // last clicked sample: ref
    this.opts = { mode: 'nearest', variation: 0.3, filter: 'class', oneshot: true, avoid: true };
    this.browse = { q: '', family: null, follow: true, items: [] };
    this.manual = { seedKey: '', cands: [], picked: [] };
  }

  get rack() { return this.racks[this.device]; }
  set rack(r) { this.racks[this.device] = r; }
  get pad() { return this.pads[this.device]; }
  set pad(p) { this.pads[this.device] = p; }
  get isSpd() { return this.device === 'spdsx'; }
  get padCount() { return this.isSpd ? this.meta.spdsx.pads : 64; }

  // ---------------------------------------------------------------- lifecycle
  ensure() {
    if (!this.ready) this.ready = this._init();
    return this.ready;
  }

  async _init() {
    this.meta = await this.api.racks_init();
    this.geoById = Object.fromEntries(this.meta.geometries.map((g) => [g.id, g]));
    this.famById = Object.fromEntries(this.meta.families.map((f) => [f.id, f]));
    try {
      const saved = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
      if (saved?.rack?.pads?.length === 64) {
        this.rack = saved.rack;
        this.pad = saved.pad ?? 0;
        this.opts = { ...this.opts, ...saved.opts };
      }
    } catch { /* private mode / bad JSON */ }
    if (!this.geoById[this.rack.geometry]) this.rack.geometry = 'cols8';
    try {
      const spd = JSON.parse(localStorage.getItem(LS_SPD) || 'null');
      if (spd?.rack?.pads?.length === this.meta.spdsx.pads) {
        this.racks.spdsx = { ...newSpdRack(), ...spd.rack };
        this.pads.spdsx = spd.pad ?? 4;
      }
      if (localStorage.getItem(LS_DEVICE) === 'spdsx') this.device = 'spdsx';
    } catch { /* private mode / bad JSON */ }
    if (!this.meta.spdsx.configs.some((c) => c.id === this.racks.spdsx.geometry)) this.racks.spdsx.geometry = 'spd_kit';
    this._fixPad();
    this._buildShell();
    this._persist();
  }

  async show() {
    await this.ensure();
    this.renderAll();
    this.loadBrowser();
  }

  hide() { this.player.stop(); }

  _persist() {
    try {
      if (this.isSpd) localStorage.setItem(LS_SPD, JSON.stringify({ rack: this.rack, pad: this.pad }));
      else localStorage.setItem(LS_KEY, JSON.stringify({ rack: this.rack, pad: this.pad, opts: this.opts }));
    } catch { /* private mode */ }
    const online = [...this.racks.grid64.pads, ...this.racks.spdsx.pads].filter((r) => r?.kind === 'online');
    this.api.protect_samples(online, 'rack');
  }

  setDevice(device) {
    if (device === this.device) return;
    this.player.stop();
    this.device = device;
    this.manual.seedKey = '';
    try { localStorage.setItem(LS_DEVICE, device); } catch { /* private mode */ }
    this._fixPad();
    this._buildBar();
    this.renderAll();
    this._followGroup();
  }

  // the selected pad must belong to a group (a trigger may have been disconnected)
  _fixPad() {
    if (this.groupOf(this.pad) < 0) this.pad = this.groups[0][0];
  }

  // ---------------------------------------------------------------- geometry helpers
  // {id, groups, families, keys?}: the 8×8 geometry, or the SPD-SX configuration for the current triggers
  get geo() {
    if (!this.isSpd) return this.geoById[this.rack.geometry];
    const t = this.rack.triggers || {};
    return this.meta.spdsx.layouts[`${this.rack.geometry}|${t.trig1 ? 1 : 0}${t.trig2 ? 1 : 0}`];
  }

  get groups() { return this.geo.groups; }

  groupOf(p) { return this.groups.findIndex((g) => g.includes(p)); }

  _groupKey(g) {
    const geo = this.geo;
    return `${geo.id}:${geo.keys ? geo.keys[g] : g}`;
  }

  settings(g) {
    const geo = this.geo;
    const s = this.rack.groups[this._groupKey(g)] || {};
    const family = this.famById[s.family] ? s.family : geo.families[g];
    return { family, choke: s.choke ?? (HAT_FAMILIES.has(family) ? 1 : 0), lock: !!s.lock };
  }

  setSetting(g, key, value) {
    const k = this._groupKey(g);
    this.rack.groups[k] = { ...this.settings(g), ...this.rack.groups[k], [key]: value };
    this._persist();
  }

  note(p) { return this.isSpd ? this.meta.spdsx.notes[p] : this.meta.notes[this.rack.mapping][p]; }

  // how a pad is named in menus and messages: its note on the 8×8, its number / input on the SPD-SX
  padName(p) { return this.isSpd ? this.meta.spdsx.labels[p] : noteName(this.note(p)); }

  // ---------------------------------------------------------------- shell
  _buildShell() {
    const root = $('#rack');
    root.innerHTML = `
      <aside class="sidebar rk-browser">
        <div class="filter-title">Sample <span class="links"><wa-checkbox size="xs" id="rk-follow" title="Il browser segue la famiglia del gruppo selezionato">segui gruppo</wa-checkbox></span></div>
        <wa-select id="rk-bfam" size="s" class="rk-select"></wa-select>
        <wa-input id="rk-q" class="search" type="search" size="s" with-clear placeholder="Cerca per nome o cartella…" autocomplete="off"><wa-icon slot="start" name="search"></wa-icon></wa-input>
        <div class="hint">Clic: ascolta e usa come seed · doppio clic: riempi il gruppo · trascina su un pad</div>
        <div id="rk-blist" class="rk-blist"></div>
        <div class="rk-trail-box">
          <div class="filter-title">Percorso dei simili <span class="links"><a href="#" id="rk-trail-use">usa sul gruppo</a></span></div>
          <div id="rk-trail" class="rk-trail"></div>
        </div>
      </aside>
      <main class="rk-main">
        <div class="rk-bar">
          <wa-select id="rk-device" size="s" class="rk-select rk-device" title="Per quale strumento è il kit">${DEVICES.map(([id, l]) => `<wa-option value="${id}">${l}</wa-option>`).join('')}</wa-select>
          <wa-input id="rk-name" size="s" class="rk-name" maxlength="80" title="Nome del kit (anche del file .adg)"></wa-input>
          <wa-radio-group id="rk-geo" class="seg" orientation="horizontal" size="s" label="Geometria"></wa-radio-group>
          <wa-select id="rk-map" size="s" class="rk-select" title="Note MIDI dei pad">
            <wa-option value="launchpad">Note: Launchpad / Live (quadranti 4×4)</wa-option>
            <wa-option value="rows">Note: righe sequenziali (36 + riga×8)</wa-option>
          </wa-select>
          <div class="spacer"></div>
          ${btn('Auto-riempi', { id: 'rk-auto', icon: 'sparkles', title: 'Riempie i gruppi vuoti in base alla famiglia (Alt+clic: rigenera tutti i gruppi non bloccati)' })}
          ${btn('Casuale', { id: 'rk-random', icon: 'dices', title: 'Per ogni gruppo non bloccato: un gruppo di sample simili a caso della sua famiglia, con sample a caso' })}
          ${btn('Genera kit', { id: 'rk-gen', icon: 'dices', hidden: true, title: 'Kit SPD-SX casuale e suonabile: configurazione a caso, ogni gruppo da un gruppo di sample simili diverso' })}
          <wa-select id="rk-saved" size="s" class="rk-select" title="Kit salvati"></wa-select>
          ${btn('Salva', { id: 'rk-save', icon: 'save', title: 'Salva il kit' })}
          ${btn('Elimina', { id: 'rk-del', icon: 'trash-2', hidden: true, title: 'Elimina il kit salvato' })}
          ${btn('Svuota', { id: 'rk-clear', title: 'Svuota tutti i pad' })}
          ${btn('Sequencer', { id: 'rk-toseq', icon: 'arrow-right', title: 'Carica i sample del kit nei bus del Sequencer' })}
          ${btn('Esporta per Ableton', { id: 'rk-export', variant: 'brand', icon: 'file-down' })}
          ${btn('Invia a Live', { id: 'rk-live', title: 'Crea in Live una traccia con questo Drum Rack (serve il device ClusterSound nel set)' })}
        </div>
        <div class="rk-stage">
          <div id="rk-grid" class="rk-grid"></div>
        </div>
      </main>
      <aside id="rk-insp" class="sidebar rk-insp"></aside>`;

    this._buildBar();
    $('#rk-bfam').innerHTML = this.meta.families.map((f) => `<wa-option value="${f.id}"><span slot="start" class="dot" style="background:${f.color}"></span>${esc(f.label)}</wa-option>`).join('');
    $('#rk-follow').checked = this.browse.follow;

    $('#rk-geo').addEventListener('change', (e) => {
      if (e.target.id !== 'rk-geo' || e.target.value === this.rack.geometry) return;
      this.rack.geometry = e.target.value;
      this._fixPad();
      this._persist();
      this.renderAll();
      this._followGroup();
    });
    $('#rk-device').onchange = (e) => this.setDevice(e.target.value);
    $('#rk-gen').onclick = (e) => this.openGenerate(e.currentTarget);
    $('#rk-map').onchange = (e) => { this.rack.mapping = e.target.value; this._persist(); this.renderGrid(); };
    $('#rk-name').oninput = (e) => {
      this.rack.name = e.target.value;
      this._persist();
      const lcd = $('#rk-grid .spd-lcd');
      if (lcd) lcd.textContent = this.rack.name || 'Kit';
    };
    $('#rk-auto').onclick = (e) => this.autofill(!e.altKey);
    $('#rk-random').onclick = (e) => this.openRandomize(e.currentTarget);
    $('#rk-toseq').onclick = () => this.openLoadDialog();
    $('#rk-clear').onclick = () => {
      if (!this.rack.pads.some(Boolean) || !confirm(`Svuotare tutti i ${this.padCount} pad?`)) return;
      this.rack.pads = new Array(this.padCount).fill(null);
      this._persist();
      this.renderAll();
    };
    $('#rk-save').onclick = () => this.save();
    $('#rk-del').onclick = () => this.deleteSaved();
    $('#rk-saved').onchange = (e) => this.loadSaved(e.target.value);
    $('#rk-export').onclick = () => this.exportRack();
    $('#rk-live').onclick = () => this.sendRackToLive();

    // browser
    let qTimer = 0;
    $('#rk-q').oninput = (e) => { this.browse.q = e.target.value || ''; clearTimeout(qTimer); qTimer = setTimeout(() => this.loadBrowser(), 150); };
    $('#rk-bfam').onchange = (e) => { this.browse.family = e.target.value; this.loadBrowser(); };
    $('#rk-follow').onchange = (e) => { this.browse.follow = e.target.checked; this._followGroup(); };
    const list = $('#rk-blist');
    list.onclick = (e) => {
      const row = e.target.closest('[data-k]');
      if (row) this.setSeed(this.browse.items[+row.dataset.k], true);
    };
    list.ondblclick = (e) => {
      const row = e.target.closest('[data-k]');
      if (row) { this.setSeed(this.browse.items[+row.dataset.k], false); this.fillGroup(); }
    };
    list.addEventListener('dragstart', (e) => {
      const row = e.target.closest('[data-k]');
      if (row) e.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ ref: this.browse.items[+row.dataset.k] }));
    });
    $('#rk-trail-use').onclick = (e) => { e.preventDefault(); this.fillFromTrail(); };
    $('#rk-trail').onclick = (e) => {
      const b = e.target.closest('[data-id]');
      if (b) this.api.library_ref(+b.dataset.id).then((ref) => this.setSeed(ref, true));
    };

    // grid
    const grid = $('#rk-grid');
    grid.onchange = (e) => {
      const t = e.target.dataset.trig;
      if (t) this.setTrigger(t, e.target.checked);
    };
    grid.onclick = (e) => {
      if (e.target.closest('[data-trig]')) return;
      const el = e.target.closest('.rk-pad');
      if (!el) return;
      const p = +el.dataset.p;
      this.selectPad(p);
      const ref = this.rack.pads[p];
      if (ref) this.setSeed(ref, true);
    };
    grid.oncontextmenu = (e) => {
      const el = e.target.closest('.rk-pad');
      if (!el) return;
      e.preventDefault();
      this._padMenu(+el.dataset.p, e.clientX, e.clientY);
    };
    grid.addEventListener('dragstart', (e) => {
      const el = e.target.closest('.rk-pad');
      if (el && this.rack.pads[+el.dataset.p]) e.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ from: +el.dataset.p }));
    });
    grid.addEventListener('dragover', (e) => {
      if (!e.target.closest('.rk-pad')) return;
      e.preventDefault();
      grid.querySelectorAll('.rk-pad.drop').forEach((x) => x.classList.remove('drop'));
      e.target.closest('.rk-pad').classList.add('drop');
    });
    grid.addEventListener('dragleave', (e) => { e.target.closest?.('.rk-pad')?.classList.remove('drop'); });
    grid.addEventListener('drop', (e) => {
      const el = e.target.closest('.rk-pad');
      grid.querySelectorAll('.rk-pad.drop').forEach((x) => x.classList.remove('drop'));
      if (!el) return;
      e.preventDefault();
      let data;
      try { data = JSON.parse(e.dataTransfer.getData(DRAG_TYPE)); } catch { return; }
      const p = +el.dataset.p;
      if (data.from != null) {
        const pads = this.rack.pads;
        [pads[p], pads[data.from]] = [pads[data.from], pads[p]];
      } else if (data.ref) this.rack.pads[p] = data.ref;
      this.pad = p;
      this._persist();
      this.renderAll();
    });

    // inspector (re-rendered, so delegated)
    const insp = $('#rk-insp');
    insp.onclick = (e) => {
      const t = e.target.closest('[data-act]');
      if (!t) return;
      const act = t.dataset.act;
      if (act === 'fill') this.fillGroup();
      else if (act === 'clear-group') this.clearGroup();
      else if (act === 'play-seed' && this.seed) this.audition(this.seed);
      else if (act === 'play') this.audition(this.manual.cands[+t.dataset.k]);
      else if (act === 'use-trail') this.fillFromTrail();
    };
    insp.onchange = (e) => {
      const t = e.target;
      const g = this.groupOf(this.pad);
      if (t.dataset.set === 'mode') { this.opts.mode = t.value; this._persist(); this.renderInspector(); }
      else if (t.dataset.set === 'family') { this.setSetting(g, 'family', t.value); this.renderAll(); this._followGroup(); }
      else if (t.dataset.set === 'choke') { this.setSetting(g, 'choke', +t.value); }
      else if (t.dataset.set === 'lock') { this.setSetting(g, 'lock', t.checked); this.renderGrid(); }
      else if (t.dataset.opt) {
        this.opts[t.dataset.opt] = t.localName === 'wa-checkbox' ? t.checked : t.localName === 'wa-slider' ? +t.value : t.value;
        this._persist();
        if (t.dataset.opt !== 'variation' && t.dataset.opt !== 'avoid') { this.manual.seedKey = ''; this.renderInspector(); }
      } else if (t.dataset.pick != null) {
        const k = +t.dataset.pick;
        const size = this.groups[g].length - 1;
        if (t.checked) {
          if (this.manual.picked.length >= size) { t.checked = false; toast(`Il gruppo ha posto per ${size} sample oltre al seed`); return; }
          this.manual.picked.push(k);
        } else this.manual.picked = this.manual.picked.filter((x) => x !== k);
        $('#rk-pick-count').textContent = `${this.manual.picked.length}/${size}`;
      }
    };
    insp.oninput = (e) => {
      if (e.target.dataset.opt === 'variation') $('#rk-var-v').textContent = `${Math.round(e.target.value * 100)}%`;
    };
  }

  // device-dependent part of the toolbar
  _buildBar() {
    const list = this.isSpd ? this.meta.spdsx.configs : this.meta.geometries;
    $('#rk-device').value = this.device;
    $('#rk-geo').innerHTML = list.map((g) => `<wa-radio appearance="button" value="${g.id}">${esc(g.label)}</wa-radio>`).join('');
    $('#rk-geo').title = this.isSpd ? 'Configurazione dei pad: quali gruppi e quali famiglie' : '';
    $('#rk-map').hidden = this.isSpd;
    $('#rk-gen').hidden = !this.isSpd;
    $('#rk-export').innerHTML = `<wa-icon slot="start" name="file-down"></wa-icon>${this._exportLabel()}`;
    $('#rk-export').title = this.isSpd ? 'Drum Rack per Live sulle note della SPD-SX + WAV 16 bit per SPD-SX Wave Manager' : '';
  }

  _exportLabel() { return this.isSpd ? 'Esporta (Live + SPD-SX)' : 'Esporta per Ableton'; }

  setTrigger(key, on) {
    this.rack.triggers = { ...this.rack.triggers, [key]: on };
    this._fixPad();
    this._persist();
    this.renderAll();
    this._followGroup();
  }

  // ---------------------------------------------------------------- render
  renderAll() {
    $('#rk-name').value = this.rack.name;
    $('#rk-map').value = this.rack.mapping;
    $('#rk-geo').value = this.rack.geometry;
    this.renderSaved();
    this.renderGrid();
    this.renderInspector();
    this.renderTrail();
    this.refreshCheck();
  }

  renderGrid() {
    if (this.isSpd) this.renderSpd();
    else this.renderGrid64();
  }

  renderGrid64() {
    // css grid: 4 columns, a gutter, 4 columns (same for rows), top row first
    const at = (r, c) => `grid-row:${8 - r + (r < 4 ? 1 : 0)};grid-column:${c + 1 + (c >= 4 ? 1 : 0)}`;
    const sel = this.groupOf(this.pad);
    const html = [];
    for (let p = 0; p < 64; p++) {
      const r = Math.floor(p / 8), c = p % 8;
      const ref = this.rack.pads[p];
      const color = ref ? this.classColor[ref.cls] || '#8a8f98' : '';
      const badge = ref ? KIND_BADGE[ref.kind] : '';
      html.push(`<div class="rk-pad ${ref ? 'full' : ''} ${p === this.pad ? 'sel' : ''}" data-p="${p}" draggable="${ref ? 'true' : 'false'}"
        style="${at(r, c)};${ref ? `--pc:${color}` : ''}" title="${ref ? esc(ref.name) + (ref.sim != null && ref.sim < 1 ? ` · somiglianza ${Math.round(ref.sim * 100)}%` : '') : 'vuoto'}">
        <span class="rk-note">${noteName(this.note(p))}</span>${badge ? `<span class="rk-badge">${badge}</span>` : ''}
        <span class="rk-pname">${ref ? esc(ref.name.replace(/\.[^.]+$/, '')) : ''}</span></div>`);
    }
    this.groups.forEach((pads, g) => {
      const rows = pads.map((p) => Math.floor(p / 8)), cols = pads.map((p) => p % 8);
      const r0 = Math.min(...rows), r1 = Math.max(...rows), c0 = Math.min(...cols), c1 = Math.max(...cols);
      const rowStart = 8 - r1 + (r1 < 4 ? 1 : 0), rowEnd = 8 - r0 + (r0 < 4 ? 1 : 0) + 1;
      const colStart = c0 + 1 + (c0 >= 4 ? 1 : 0), colEnd = c1 + 1 + (c1 >= 4 ? 1 : 0) + 1;
      const fam = this.famById[this.settings(g).family];
      const lock = this.settings(g).lock;
      if (this.rack.geometry === 'free' && g !== sel && !lock) return;
      html.push(`<div class="rk-frame ${g === sel ? 'sel' : ''} ${lock ? 'lock' : ''}" style="grid-row:${rowStart}/${rowEnd};grid-column:${colStart}/${colEnd};--gc:${fam.color}">
        ${this.rack.geometry !== 'free' || lock ? `<span>${lock ? svg('lock', 9) : ''}${this.rack.geometry !== 'free' ? esc(fam.label) : ''}</span>` : ''}</div>`);
    });
    const grid = $('#rk-grid');
    grid.className = 'rk-grid';
    grid.innerHTML = html.join('');
  }

  // SPD-SX control panel, drawn after the top panel in the manual (decorative: only the LCD and the
  // TRIG IN lights follow the kit). viewBox units ≈ the manual's drawing, left to right.
  _spdConsole() {
    const spd = this.meta.spdsx;
    const t = this.rack.triggers || {};
    const ref = this.rack.pads[this.pad];
    const txt = (x, y, s, cls = 't', anchor = 'middle') => `<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}">${s}</text>`;
    const knob = (x, y, r, label, ly) => `<circle cx="${x}" cy="${y}" r="${r}" class="k"/><circle cx="${x}" cy="${y}" r="${r * 0.62}" class="kc"/>
      <line x1="${x}" y1="${y - r * 0.62}" x2="${x}" y2="${y - r * 0.2}" class="kt"/>${txt(x, ly, label)}`;
    const button = (x, y, w, h, label, cls = '') => `<rect x="${x - w / 2}" y="${y - h / 2}" width="${w}" height="${h}" rx="4" class="b ${cls}"/>${label ? txt(x, y + 3.5, label, 'bt') : ''}`;
    const led = (x, y, on) => `<circle cx="${x}" cy="${y}" r="5" class="led ${on ? 'on' : ''}"/>`;
    const tri = (x, y, d) => {
      const pts = { u: [[0, -7], [-7, 5], [7, 5]], d: [[0, 7], [-7, -5], [7, -5]], l: [[-7, 0], [5, -7], [5, 7]], r: [[7, 0], [-5, -7], [-5, 7]] }[d];
      return `<rect x="${x - 17}" y="${y - 13}" width="34" height="26" rx="6" class="b"/><polygon points="${pts.map(([a, b]) => `${x + a},${y + b}`).join(' ')}" class="ar"/>`;
    };
    const pad = this.pad < 9 ? `PAD ${this.pad + 1}` : spd.labels[this.pad] ?? '';
    const line2 = `${pad}  ${ref ? ref.name.replace(/\.[^.]+$/, '') : '—'}`;
    return `<svg class="spd-console" viewBox="0 0 975 235" aria-hidden="true">
      <rect x="1" y="1" width="973" height="233" rx="10" class="plate"/>
      ${button(37, 42, 52, 24, 'POWER')}
      ${knob(115, 68, 19, 'MASTER', 30)}${knob(188, 68, 19, 'PHONES', 30)}${knob(262, 68, 19, 'CLICK', 30)}
      <rect x="315" y="24" width="38" height="13" rx="6.5" class="b"/>${txt(334, 34, 'TEMPO', 'bt')}
      ${txt(334, 56, 'START/STOP')}${button(334, 73, 36, 18, '')}
      <rect x="4" y="99" width="386" height="128" rx="8" class="frame"/>${txt(197, 104, 'MASTER EFFECTS', 't sec')}
      ${knob(62, 160, 36, 'CONTROL 1', 214)}${knob(188, 160, 36, 'CONTROL 2', 214)}
      ${button(292, 133, 54, 24, 'FILTER')}${button(355, 133, 54, 24, 'DELAY')}${button(292, 178, 54, 24, 'S.LOOP')}${button(355, 178, 54, 24, 'FX')}
      ${txt(426, 28, 'Roland', 'logo', 'start')}${txt(498, 30, 'SPD-SX', 'model', 'start')}${txt(500, 39, 'SAMPLING PAD', 't small', 'start')}
      <rect x="427" y="46" width="174" height="88" rx="4" class="lcd"/>
      <text x="438" y="72" class="lcd-t">KIT</text><text x="470" y="72" class="lcd-t spd-lcd">${esc(this.rack.name || 'Kit')}</text>
      <text x="438" y="98" class="lcd-t dim">${esc(line2.length > 26 ? line2.slice(0, 25) + '…' : line2)}</text>
      <line x1="433" y1="112" x2="595" y2="112" class="lcd-l"/>
      ${[451, 514, 577].map((x) => `<circle cx="${x}" cy="146" r="1.6" class="dot"/>${button(x, 178, 50, 24, '')}`).join('')}
      ${txt(623, 25, 'TRIG IN', 't', 'start')}${led(672, 21, t.trig1)}${txt(684, 25, '-')}${led(696, 21, t.trig2)}${led(722, 21, false)}${txt(734, 25, '-')}${led(746, 21, false)}
      ${txt(764, 25, 'FOOT SW', 't', 'start')}${led(824, 21, false)}${txt(836, 25, '-')}${led(848, 21, false)}
      ${txt(935, 20, 'VISUAL CONTROL', 't small')}${txt(935, 29, 'V-LINK', 't small')}
      <rect x="638" y="50" width="135" height="155" rx="8" class="frame"/>
      ${button(672, 73, 50, 22, 'KIT')}${button(737, 73, 50, 22, 'MENU')}${button(672, 122, 50, 22, 'SAMPLING')}${button(737, 122, 50, 22, 'QUICK')}
      ${button(672, 177, 40, 34, '')}${txt(672, 171, 'ALL', 'bt')}${txt(672, 180, 'SOUND', 'bt')}${txt(672, 189, 'OFF', 'bt')}
      ${txt(737, 160, 'SHIFT')}${button(737, 178, 50, 22, 'PAD CHECK')}
      ${tri(877, 55, 'u')}${tri(820, 74, 'l')}${tri(934, 74, 'r')}${tri(877, 93, 'd')}
      ${button(827, 124, 60, 18, 'EXIT')}${button(927, 124, 60, 18, 'ENTER')}
      <rect x="796" y="154" width="164" height="38" rx="7" class="frame"/>
      ${button(836, 173, 74, 30, '−', 'pm')}${button(919, 173, 74, 30, '+', 'pm')}
    </svg>`;
  }

  // SPD-SX as seen from the player: the narrow pads 1-3 at the top, 4-9 below, then the trigger inputs
  renderSpd() {
    const spd = this.meta.spdsx;
    const sel = this.groupOf(this.pad);
    const t = this.rack.triggers || {};
    const famOf = {};
    const firstOf = {};
    this.groups.forEach((pads, g) => pads.forEach((p, k) => { famOf[p] = g; if (k === 0) firstOf[p] = g; }));
    const cell = (p, extra = '') => {
      const ref = this.rack.pads[p];
      const g = famOf[p];
      const s = this.settings(g);
      const fam = this.famById[s.family];
      const color = ref ? this.classColor[ref.cls] || '#8a8f98' : '';
      const badge = ref ? KIND_BADGE[ref.kind] : '';
      const tag = firstOf[p] != null && this.rack.geometry !== 'spd_free'
        ? `<span class="spd-fam">${s.lock ? svg('lock', 9) : ''}${esc(fam.label)}</span>` : (s.lock ? `<span class="spd-fam">${svg('lock', 9)}</span>` : '');
      return `<div class="rk-pad spd-pad ${extra} ${ref ? 'full' : ''} ${p === this.pad ? 'sel' : ''} ${g === sel ? 'gsel' : ''}" data-p="${p}"
        draggable="${ref ? 'true' : 'false'}" style="--gc:${fam.color};${ref ? `--pc:${color}` : ''}"
        title="${esc(spd.labels[p])} · ${noteName(spd.notes[p])}${ref ? ` · ${esc(ref.name)}` : ' · vuoto'}">
        <span class="rk-note"><i>${noteName(spd.notes[p])}</i></span>${badge ? `<span class="rk-badge">${badge}</span>` : ''}
        ${tag}<span class="rk-pname">${ref ? esc(ref.name.replace(/\.[^.]+$/, '')) : ''}</span>
        ${p < 9 ? `<span class="spd-num">${p + 1}</span><i class="spd-led"></i>` : ''}</div>`;
    };
    const trig = (p, key, label, icon) => `<div class="spd-trig ${t[key] ? '' : 'off'}">
        ${t[key] ? cell(p, 'spd-tpad') : `<div class="spd-tpad spd-empty">${icon}<span>non collegato</span></div>`}
        <wa-checkbox size="s" class="rk-check" data-trig="${key}" ${t[key] ? 'checked' : ''}>${label}</wa-checkbox>
      </div>`;
    const grid = $('#rk-grid');
    grid.className = 'rk-spd';
    grid.innerHTML = `
      <div class="spd-unit">
        <div class="spd-padarea">${Array.from({ length: 9 }, (_, p) => cell(p, p < 3 ? 'spd-top' : '')).join('')}</div>
        ${this._spdConsole()}
      </div>
      <div class="spd-trigs">
        ${trig(spd.trig1, 'trig1', 'Pedale (Trig 1)', PEDAL_ICON)}
        ${trig(spd.trig2, 'trig2', 'Trig 2', svg('circle', 20))}
      </div>
      <div id="rk-warn" class="rk-warn" hidden></div>`;
    this._renderWarnings();
  }

  renderInspector() {
    const g = this.groupOf(this.pad);
    const pads = this.groups[g];
    const s = this.settings(g);
    const fam = this.famById[s.family];
    const o = this.opts;
    const seed = this.seed;
    const similarOk = seed?.kind === 'library';
    const filled = pads.filter((p) => this.rack.pads[p]).length;
    const where = this.isSpd ? pads.map((p) => this.padName(p)).join(' · ') : `${noteName(this.note(pads[0]))}${pads.length > 1 ? '…' : ''}`;
    // SPD-SX: families that would make the kit unplayable (too many kicks / snares / hats) are disabled
    const allowed = this.isSpd && this.rack.geometry !== 'spd_free' ? this.check?.allowed?.[g] : null;
    const famOpt = (f) => {
      const off = allowed && !allowed.includes(f.id);
      return `<wa-option value="${f.id}" ${off ? 'disabled' : ''}><span slot="start" class="dot" style="background:${f.color}"></span>${esc(f.label)}${off ? ' — troppi pad di questo tipo' : ''}</wa-option>`;
    };
    const html = [`
      <div class="rk-ihead"><span class="dot" style="background:${fam.color}"></span>
        <b>Gruppo ${g + 1}</b><span class="hint">${pads.length} pad · ${filled} pieni · ${esc(where)}</span></div>
      <wa-select size="s" class="rk-field" label="Famiglia" data-set="family" value="${s.family}">${this.meta.families.map(famOpt).join('')}</wa-select>
      <wa-select size="s" class="rk-field" label="Choke group" data-set="choke" value="${s.choke || 0}" title="I pad con lo stesso choke group si zittiscono a vicenda (es. hat aperto/chiuso)"><wa-option value="0">nessuno</wa-option>${Array.from({ length: 16 }, (_, i) => `<wa-option value="${i + 1}">${i + 1}</wa-option>`).join('')}</wa-select>
      <wa-checkbox size="s" class="rk-check" data-set="lock" ${s.lock ? 'checked' : ''} title="Casuale e Auto-riempi (Alt) non cambiano i gruppi bloccati">blocca gruppo</wa-checkbox>
      <div class="rk-sep"></div>
      <div class="rk-seed">${seed
        ? `<button class="pt-ib" data-act="play-seed" title="Ascolta">${svg('play', 11)}</button><span class="dot" style="background:${this.classColor[seed.cls] || '#8a8f98'}"></span>
           <span class="rk-seed-name" title="${esc(seed.path || seed.name)}">${esc(seed.name)}</span>`
        : '<span class="hint">Seed: clicca un sample nel browser, su un pad o “Drum Rack” dal menu Invia della Libreria.</span>'}</div>
      <wa-radio-group class="seg rk-modes" orientation="horizontal" size="s" data-set="mode" value="${o.mode}" label="Modo di riempimento">${MODES.map(([m, l]) => `<wa-radio appearance="button" value="${m}">${l}</wa-radio>`).join('')}</wa-radio-group>`];
    if (o.mode === 'random') {
      html.push(`<div class="rk-field" title="Quanto lontano dal seed può pescare: 0% = i più simili"><span class="pop-row"><span>Variazione</span><span id="rk-var-v">${Math.round(o.variation * 100)}%</span></span>
        <wa-slider size="s" min="0" max="1" step="0.05" value="${o.variation}" data-opt="variation" label="Variazione"></wa-slider></div>`);
    }
    html.push(`<wa-select size="s" class="rk-field" label="Simili tra" data-opt="filter" value="${o.filter}">
        <wa-option value="class">stessa classe del seed</wa-option>
        <wa-option value="family">famiglia del gruppo (${esc(fam.label)})</wa-option>
        <wa-option value="none">tutta la libreria</wa-option>
      </wa-select>
      <wa-checkbox size="s" class="rk-check" data-opt="oneshot" ${o.oneshot ? 'checked' : ''}>solo one-shot</wa-checkbox>
      <wa-checkbox size="s" class="rk-check" data-opt="avoid" ${o.avoid ? 'checked' : ''}>evita sample già nel kit</wa-checkbox>`);
    if (o.mode === 'manual') {
      html.push(`<div class="filter-title">Scegli i simili <span id="rk-pick-count">${this.manual.picked.length}/${pads.length - 1}</span></div>
        <div id="rk-cands" class="rk-cands">${similarOk ? '<div class="hint">Carico…</div>' : '<div class="hint">Serve un seed della Libreria.</div>'}</div>`);
    }
    if (o.mode === 'trail') {
      const t = this.getTrail();
      html.push(`<div class="hint">${t.length
        ? `Usa le ${t.length} tappe del percorso (in ordine${t.length < pads.length ? ', completate con i simili dell’ultima' : `, le prime ${pads.length}`}).`
        : 'Nessun percorso: nella Libreria apri “Trova simili” e ricentra con doppio clic sui sample per tracciarlo.'}</div>`);
    }
    const canFill = o.mode === 'trail' ? this.getTrail().length > 0 : !!seed && (similarOk || pads.length === 1);
    html.push(`<div class="rk-actions">
      ${btn(o.mode === 'random' && filled ? 'Rigenera gruppo' : 'Riempi gruppo', { variant: 'brand', icon: o.mode === 'random' && filled ? 'refresh-cw' : 'layout-grid', 'data-act': 'fill', disabled: !canFill })}
      ${btn('Svuota gruppo', { 'data-act': 'clear-group', disabled: !filled })}</div>
      ${seed && !similarOk && pads.length > 1 ? '<div class="hint">Sample online/file: niente simili, trascinalo su un pad.</div>' : ''}`);
    $('#rk-insp').innerHTML = html.join('');
    if (o.mode === 'manual' && similarOk) this._loadCandidates();
  }

  // SPD-SX playability: warnings under the pads and the families each group may take
  async refreshCheck() {
    if (!this.isSpd) { this.check = null; return; }
    const token = (this._checkToken = (this._checkToken || 0) + 1);
    const chk = await this.api.rack_check(this.rack);
    if (token !== this._checkToken || !this.isSpd) return;
    const changed = JSON.stringify(chk.allowed) !== JSON.stringify(this.check?.allowed);
    this.check = chk;
    this._renderWarnings();
    if (changed) this.renderInspector();
  }

  _renderWarnings() {
    const box = $('#rk-warn');
    const w = this.check?.warnings || [];
    if (!box) return;
    box.hidden = !w.length;
    box.innerHTML = w.map((x) => `<div>${svg('triangle-alert', 12)} ${esc(x)}</div>`).join('');
  }

  async _loadCandidates() {
    const seed = this.seed;
    const key = `${seed.id}:${this.opts.filter}:${this.opts.oneshot}:${this.groupOf(this.pad)}`;
    if (key !== this.manual.seedKey) {
      this.manual = { seedKey: key, cands: [], picked: [] };
      const cands = await this.api.rack_candidates(seed.id, 60, this._apiOpts(false));
      if (this.manual.seedKey !== key) return;
      this.manual.cands = cands;
    }
    const box = $('#rk-cands');
    if (!box) return;
    const size = this.groups[this.groupOf(this.pad)].length - 1;
    $('#rk-pick-count').textContent = `${this.manual.picked.length}/${size}`;
    box.innerHTML = this.manual.cands.length ? this.manual.cands.map((c, k) => `<div class="rk-cand">
      <button class="pt-ib" data-act="play" data-k="${k}" title="Ascolta">${svg('play', 11)}</button>
      <wa-checkbox size="xs" class="rk-cname" data-pick="${k}" ${this.manual.picked.includes(k) ? 'checked' : ''} title="${esc(c.path)}"><span class="dot" style="background:${this.classColor[c.cls] || '#8a8f98'}"></span> ${esc(c.name)}</wa-checkbox><b>${Math.round(c.sim * 100)}%</b></div>`).join('')
      : '<div class="hint">Nessun sample simile con questi filtri.</div>';
  }

  renderTrail() {
    const t = this.getTrail();
    $('#rk-trail').innerHTML = t.length
      ? t.map((x, k) => `<button data-id="${x.id}" title="Usa come seed">${k + 1} · ${esc(x.name)}</button>`).join('')
      : '<span class="hint">Vuoto: nella Libreria usa “Trova simili” e ricentra (doppio clic) per creare un percorso.</span>';
    $('#rk-trail-use').hidden = !t.length;
  }

  renderSaved() {
    const saved = (this.meta.saved || []).filter((r) => (r.device || 'grid64') === this.device);
    const sel = $('#rk-saved');
    sel.placeholder = saved.length ? 'Carica kit…' : 'Nessun kit salvato';
    sel.disabled = !saved.length;
    sel.innerHTML = saved.map((r) => `<wa-option value="${esc(r.id)}">${esc(r.name)}</wa-option>`).join('');
    sel.value = saved.some((r) => r.id === this.rack.id) ? this.rack.id : '';
    $('#rk-del').hidden = !this.rack.id;
  }

  async loadBrowser() {
    if (this.browse.family == null) this._followGroup(false);
    $('#rk-bfam').value = this.browse.family;
    const items = await this.api.rack_browse(this.browse.q, this.browse.family, 300);
    this.browse.items = items;
    $('#rk-blist').innerHTML = items.length ? items.map((it, k) => `<div class="rk-brow ${this.seed && refKey(this.seed) === refKey(it) ? 'seed' : ''}" data-k="${k}" draggable="true" title="${esc(it.path)}">
      <span class="dot" style="background:${this.classColor[it.cls] || '#8a8f98'}"></span>
      <span class="rk-bname">${esc(it.name)}</span>
      <span class="rk-bmeta">${it.type === 'One-shot' ? '' : esc(it.type || '')} ${Math.round((it.conf || 0) * 100)}%</span></div>`).join('')
      : '<div class="hint">Nessun sample: scegli una cartella nella Libreria o cambia filtro.</div>';
  }

  _followGroup(reload = true) {
    if (!this.browse.follow && this.browse.family != null) return;
    const fam = this.settings(this.groupOf(this.pad)).family;
    if (fam === this.browse.family) return;
    this.browse.family = fam;
    if (reload && this.meta) this.loadBrowser();
  }

  // ---------------------------------------------------------------- actions
  selectPad(p) {
    const before = this.groupOf(this.pad);
    this.pad = p;
    this._persist();
    this.renderGrid();
    if (this.groupOf(p) !== before) { this.manual.seedKey = ''; this._followGroup(); }
    this.renderInspector();
  }

  setSeed(ref, play) {
    if (!ref) return;
    this.seed = ref;
    if (play) this.audition(ref);
    document.querySelectorAll('.rk-brow').forEach((el) => el.classList.toggle('seed', refKey(this.browse.items[+el.dataset.k]) === refKey(ref)));
    this.renderInspector();
  }

  async audition(ref) {
    if (!ref) return;
    const key = refKey(ref);
    this.player.stop();
    const buf = await this.player.load(key, () => this.api.sample_audio(ref));
    if (buf) this.player.play(key, buf);
  }

  _apiOpts(withExclude = true, group = this.groupOf(this.pad)) {
    const pads = new Set(this.groups[group]);
    const exclude = withExclude && this.opts.avoid
      ? this.rack.pads.filter((r, p) => r?.kind === 'library' && !pads.has(p)).map((r) => r.id) : [];
    return { filter: this.opts.filter, family: this.settings(group).family, oneshot: this.opts.oneshot,
      variation: this.opts.variation, exclude };
  }

  // seed (refs[0]) on the selected pad if it is in the group, the others on the remaining pads in order
  _place(group, refs) {
    const pads = this.groups[group];
    const first = pads.includes(this.pad) ? this.pad : pads[0];
    const order = [first, ...pads.filter((p) => p !== first)];
    order.forEach((p, k) => { this.rack.pads[p] = refs[k] || null; });
    this._persist();
    this.renderAll();
  }

  async fillGroup(mode = this.opts.mode) {
    const g = this.groupOf(this.pad);
    const size = this.groups[g].length;
    if (mode === 'trail') return this.fillFromTrail();
    const seed = this.seed;
    if (!seed) { toast('Scegli prima un sample (seed)'); return; }
    if (seed.kind !== 'library' || size === 1) { this._place(g, [seed]); return; }
    let refs;
    if (mode === 'manual') {
      await this._loadCandidates();
      const picked = [...this.manual.picked].sort((a, b) => a - b).map((k) => this.manual.cands[k]);
      refs = [{ ...seed, sim: 1 }, ...picked];
    } else {
      refs = await this.api.rack_fill(seed.id, size, mode === 'random' ? 'random' : 'nearest', this._apiOpts(true, g));
    }
    if (!refs.length) { toast('Nessun sample simile con questi filtri'); return; }
    this._place(g, refs);
    if (refs.length < size) toast(`Trovati solo ${refs.length - 1} simili: allarga il filtro`);
  }

  async fillFromTrail(trail = this.getTrail()) {
    if (!trail.length) { toast('Nessun percorso: usa “Trova simili” nella Libreria'); return; }
    const g = this.groupOf(this.pad);
    const refs = await this.api.rack_trail_fill(trail.map((x) => x.id), this.groups[g].length, this._apiOpts(true, g));
    if (!refs.length) return;
    this._place(g, refs);
    return refs.length;
  }

  clearGroup() {
    for (const p of this.groups[this.groupOf(this.pad)]) this.rack.pads[p] = null;
    this._persist();
    this.renderAll();
  }

  async autofill(onlyEmpty = true) {
    const btn = $('#rk-auto');
    btn.disabled = true;
    try {
      const out = await this.api.rack_autofill(this.rack, onlyEmpty, this.opts.variation);
      this.rack.pads = out.pads;
      this._persist();
      this.renderAll();
      if (!this.rack.pads.some(Boolean)) toast('Nessun sample nella Libreria da usare');
    } finally { btn.disabled = false; }
  }

  // from the library's "Invia" menu and the similar-samples focus bar (Library tab)
  async sendSeed(ref) {
    await this.ensure();
    this.seed = ref;
    const mode = this.opts.mode === 'random' ? 'random' : 'nearest';
    await this.fillGroup(mode);
    const g = this.groupOf(this.pad);
    toast(`Drum Rack · gruppo ${g + 1}: ${ref.name}${ref.kind === 'library' && this.groups[g].length > 1 ? ` + ${this.groups[g].length - 1} simili` : ''}`);
  }

  async sendTrail(trail) {
    await this.ensure();
    const n = await this.fillFromTrail(trail);
    if (n) toast(`Drum Rack · gruppo ${this.groupOf(this.pad) + 1}: ${n} sample dal percorso`);
  }

  _padMenu(p, x, y) {
    document.querySelector('.rk-menu')?.remove();
    const ref = this.rack.pads[p];
    const el = document.createElement('div');
    el.className = 'send-menu rk-menu';
    el.innerHTML = `<div class="send-title">Pad ${esc(this.padName(p))}${ref ? ` · <b>${esc(ref.name)}</b>` : ''}</div>
      ${ref ? '<div class="send-row" data-m="seed">Usa come seed e riempi il gruppo</div><div class="send-row" data-m="clear">Svuota pad</div>' : ''}
      <div class="send-row" data-m="group">Svuota gruppo</div>`;
    document.body.appendChild(el);
    const r = el.getBoundingClientRect();
    el.style.left = `${Math.min(x, window.innerWidth - r.width - 8)}px`;
    el.style.top = `${Math.min(y, window.innerHeight - r.height - 8)}px`;
    const close = () => { el.remove(); document.removeEventListener('pointerdown', outside, true); };
    const outside = (e) => { if (!el.contains(e.target)) close(); };
    setTimeout(() => document.addEventListener('pointerdown', outside, true), 0);
    el.onclick = (e) => {
      const m = e.target.closest('[data-m]')?.dataset.m;
      if (!m) return;
      close();
      this.pad = p;
      if (m === 'clear') { this.rack.pads[p] = null; this._persist(); this.renderAll(); }
      else if (m === 'group') this.clearGroup();
      else if (m === 'seed') { this.seed = ref; this.fillGroup(); }
    };
  }

  // label of the target of "Invia → Drum Rack"
  async sendTarget() {
    await this.ensure();
    const g = this.groupOf(this.pad);
    return `gruppo ${g + 1} · ${this.famById[this.settings(g).family].label}`;
  }

  // From the Library / Online "Invia" menu: the sample alone on a pad, or with its similars on the group.
  async addSample(ref, { similar = false } = {}) {
    await this.ensure();
    if (similar && ref.kind === 'library') { await this.sendSeed(ref); return; }
    const g = this.groupOf(this.pad);
    const pads = this.rack.pads;
    // selected pad if free, else the first free pad of its group, else of the kit; kit full: the selected pad
    const firstFree = this.isSpd ? this.groups.flat().find((q) => !pads[q]) ?? -1 : pads.findIndex((r) => !r);
    let p = !pads[this.pad] ? this.pad : this.groups[g].find((q) => !pads[q]) ?? firstFree;
    if (p < 0) p = this.pad;
    const replaced = !!pads[p];
    pads[p] = ref;
    this.pad = p;
    this.seed = ref;
    this._persist();
    if (!$('#rack').hidden) this.renderAll();
    toast(`Drum Rack · pad ${this.padName(p)} (gruppo ${this.groupOf(p) + 1})${replaced ? ', kit pieno: sostituito' : ''}: ${ref.name}`);
  }

  // From the Recorder: several samples at once on the free pads, from the selected pad on: in note order on
  // the 8×8 grid (C1, C#1, D1… to play them from a keyboard), in pad order on the SPD-SX.
  async addSamples(refs) {
    await this.ensure();
    const pads = this.rack.pads;
    const order = this.isSpd ? this.groups.flat() : [...pads.keys()].sort((a, b) => this.note(a) - this.note(b));
    const k = Math.max(0, order.indexOf(this.pad));
    const free = [...order.slice(k), ...order.slice(0, k)].filter((p) => !pads[p]);
    const placed = free.slice(0, refs.length);
    placed.forEach((p, i) => { pads[p] = refs[i]; });
    if (placed.length) { this.pad = placed[0]; this.seed = refs[0]; }
    this._persist();
    if (!$('#rack').hidden) this.renderAll();
    const left = refs.length - placed.length;
    toast(placed.length ? `Drum Rack: ${placed.length} sample da ${this.padName(placed[0])}${left ? `, ${left} non caricat${left === 1 ? 'o' : 'i'} (kit pieno)` : ''}`
      : 'Drum Rack pieno: svuota qualche pad');
    return placed.length;
  }

  openRandomize(anchor) {
    let o = { scope: 'all', folder: '', oneshot: true, dyn: false, margin: 0.3 };
    try { o = { ...o, ...JSON.parse(localStorage.getItem(LS_RANDOM) || '{}') }; } catch { /* private mode */ }
    const pop = showPopover(anchor, `
      <div class="pop-title">${svg('dices')} Kit casuale</div>
      <div class="hint">Ogni gruppo prende un gruppo di sample simili scelto a caso tra quelli della sua famiglia, e sample a caso da lì.
        I gruppi bloccati restano com'erano.</div>
      <wa-select size="s" class="pop-field" label="Gruppi" data-o="scope" value="${o.scope}"><wa-option value="all">tutti (non bloccati)</wa-option>
          <wa-option value="empty">solo quelli vuoti</wa-option></wa-select>
      <wa-input size="s" class="pop-field" label="Solo dalla cartella / pack (facoltativo)" data-o="folder" value="${esc(o.folder)}" placeholder="es. Cymatics"></wa-input>
      <wa-checkbox size="s" class="pop-check" data-o="oneshot" ${o.oneshot ? 'checked' : ''}>solo one-shot (niente loop)</wa-checkbox>
      ${dynControls(o, 'gruppi')}
      <div class="pop-actions">${btn('Genera', { variant: 'brand', icon: 'dices', 'data-go': true })}</div>`);
    wireDynControls(pop);
    pop.querySelector('[data-go]').onclick = async () => {
      o = { scope: pop.querySelector('[data-o=scope]').value, folder: (pop.querySelector('[data-o=folder]').value || '').trim(),
        oneshot: pop.querySelector('[data-o=oneshot]').checked, ...readDynControls(pop) };
      try { localStorage.setItem(LS_RANDOM, JSON.stringify(o)); } catch { /* private mode */ }
      pop.close();
      const out = await this.api.rack_randomize(this.rack, o.scope === 'empty',
        { folder: o.folder, oneshot: o.oneshot, ...(o.dyn ? { dyn_margin: o.margin } : {}) });
      this.rack.pads = out.pads;
      this._persist();
      this.renderAll();
      const n = this.rack.pads.filter(Boolean).length;
      toast(n ? `Kit casuale: ${n} pad pieni${o.dyn ? ` · dinamica ±${Math.round(o.margin * 100)}%` : ''}` : 'Nessun sample adatto (controlla il filtro cartella)');
    };
  }

  // SPD-SX: a whole random, playable kit (configuration + samples), see Api.rack_generate
  openGenerate(anchor) {
    let o = { keep: false, folder: '', oneshot: true, dyn: false, margin: 0.3 };
    try { o = { ...o, ...JSON.parse(localStorage.getItem(LS_RANDOM + '.spdsx') || '{}') }; } catch { /* private mode */ }
    const pop = showPopover(anchor, `
      <div class="pop-title">${svg('dices')} Genera kit SPD-SX</div>
      <div class="hint">Sceglie una configurazione suonabile a caso (al massimo pedale + 1 pad di kick, 3 di snare/clap)
        e riempie ogni gruppo con sample simili tra loro, ognuno da un gruppo di suoni diverso. Il pedale prende un kick.
        Con un gruppo bloccato la configurazione resta quella attuale.</div>
      <wa-checkbox size="s" class="pop-check" data-o="keep" ${o.keep ? 'checked' : ''}>mantieni la configurazione attuale</wa-checkbox>
      <wa-input size="s" class="pop-field" label="Solo dalla cartella / pack (facoltativo)" data-o="folder" value="${esc(o.folder)}" placeholder="es. Cymatics"></wa-input>
      <wa-checkbox size="s" class="pop-check" data-o="oneshot" ${o.oneshot ? 'checked' : ''}>solo one-shot (niente loop)</wa-checkbox>
      ${dynControls(o, 'gruppi')}
      <div class="pop-actions">${btn('Genera', { variant: 'brand', icon: 'dices', 'data-go': true })}</div>`);
    wireDynControls(pop);
    pop.querySelector('[data-go]').onclick = async () => {
      o = { keep: pop.querySelector('[data-o=keep]').checked, folder: (pop.querySelector('[data-o=folder]').value || '').trim(),
        oneshot: pop.querySelector('[data-o=oneshot]').checked, ...readDynControls(pop) };
      try { localStorage.setItem(LS_RANDOM + '.spdsx', JSON.stringify(o)); } catch { /* private mode */ }
      pop.close();
      const out = await this.api.rack_generate(this.rack, { keep_config: o.keep, folder: o.folder, oneshot: o.oneshot,
        ...(o.dyn ? { dyn_margin: o.margin } : {}) });
      this.rack = { ...this.rack, geometry: out.geometry, groups: out.groups, pads: out.pads };
      this._fixPad();
      this._persist();
      this._buildBar();
      this.renderAll();
      this._followGroup();
      const n = this.rack.pads.filter(Boolean).length;
      const cfg = this.meta.spdsx.configs.find((c) => c.id === out.geometry)?.label;
      toast(n ? `Kit SPD-SX: ${cfg} · ${n} pad pieni` : 'Nessun sample adatto (controlla il filtro cartella)');
    };
  }

  // pads -> sequencer buses (by sample class), in group fill order, at most MAX_PER_BUS per bus
  _kitByBus(buses) {
    const out = {};
    const seen = new Set();
    for (const pads of this.groups) {
      for (const p of pads) {
        const ref = this.rack.pads[p];
        if (!ref || seen.has(refKey(ref))) continue;
        seen.add(refKey(ref));
        const bus = suggestBus(buses, ref.cls) || 'fx';
        (out[bus] ||= []);
        if (out[bus].length < MAX_PER_BUS) out[bus].push(ref);
      }
    }
    return out;
  }

  async openLoadDialog() {
    await this.ensure();
    const seq = this.getSequencer();
    if (!seq.ready) toast('Preparo il Sequencer…'); // first time: loads its pattern and samples
    await seq.ensure();
    const buses = seq.buses;
    const kit = this._kitByBus(buses);
    const ids = buses.map((b) => b.id).filter((id) => kit[id]);
    if (!ids.length) { toast('Il Drum Rack è vuoto'); return; }
    const counts = seq.layerCounts();
    const modal = openDialog('rk-load', {
      label: 'Carica il Drum Rack nel Sequencer',
      width: '640px',
      body: `<div class="rk-load">
      <div class="hint">Ogni sample va nel bus della sua classe (max ${MAX_PER_BUS} per bus). Scegli quali bus caricare
        e, quando un bus riceve più sample, se suonano insieme o si alternano a ogni colpo.</div>
      <div class="rk-load-rows">${ids.map((id) => {
        const b = buses.find((x) => x.id === id);
        const n = kit[id].length;
        const def = NO_ALT.has(id) || n < 2 ? 'off' : 'random';
        return `<div class="rk-load-row" data-bus="${id}">
          <wa-checkbox size="s" data-use checked><span class="dot" style="background:${b.color}"></span> <b>${esc(b.label)}</b></wa-checkbox>
          <span class="hint">${n} dal kit · ora ${counts[id] || 0} layer</span>
          ${b.melodic || n < 2 ? '<span class="hint">—</span>'
            : `<wa-select size="xs" data-alt value="${def}" title="Come suonano i sample del bus">${ALT_LABELS.map(([m, l]) => `<wa-option value="${m}">${l}</wa-option>`).join('')}</wa-select>`}
        </div>`;
      }).join('')}</div>
      <div class="rk-load-opts">
        <wa-radio-group size="s" data-mode value="replace" label="Come caricare">
          <wa-radio value="replace">Sovrascrivi i bus selezionati</wa-radio>
          <wa-radio value="add">Aggiungi ai layer esistenti</wa-radio>
        </wa-radio-group>
        <wa-checkbox size="s" data-clear>Svuota anche gli altri bus (sovrascrivi tutto)</wa-checkbox>
      </div></div>`,
      footer: btn('Annulla', { 'data-cancel': true }) + btn('Carica e apri il Sequencer', { variant: 'brand', icon: 'arrow-right', 'data-ok': true }),
    });
    const close = () => modal.close();
    modal.querySelector('[data-cancel]').onclick = close;
    modal.querySelector('[data-clear]').addEventListener('change', (e) => {
      if (e.target.checked) modal.querySelector('[data-mode]').value = 'replace';
    });
    modal.querySelector('[data-ok]').onclick = async () => {
      const assign = {};
      for (const row of modal.querySelectorAll('.rk-load-row')) {
        if (!row.querySelector('[data-use]').checked) continue;
        assign[row.dataset.bus] = { refs: kit[row.dataset.bus], alt: row.querySelector('[data-alt]')?.value || 'off' };
      }
      const clearOthers = modal.querySelector('[data-clear]').checked;
      const replace = clearOthers || modal.querySelector('[data-mode]').value === 'replace';
      close();
      await seq.loadKit(assign, { replace, clearOthers });
      toast(`Sequencer: ${Object.keys(assign).length} bus caricati dal Drum Rack`);
      this.onOpenSequencer?.();
    };
  }

  // ---------------------------------------------------------------- save / export
  async save() {
    const name = prompt('Nome del kit', this.rack.name || 'Kit');
    if (!name) return;
    this.rack.name = name;
    const saved = await this.api.save_rack(this.rack);
    this.rack.id = saved.id;
    this.meta.saved = await this.api.list_racks();
    this._persist();
    this.renderAll();
    toast(`Kit “${name}” salvato`);
  }

  loadSaved(id) {
    const r = (this.meta.saved || []).find((x) => x.id === id);
    if (!r) return;
    this.rack = JSON.parse(JSON.stringify(r));
    this._fixPad();
    this._persist();
    this.renderAll();
    this._followGroup();
  }

  async deleteSaved() {
    if (!this.rack.id || !confirm(`Eliminare il kit salvato “${this.rack.name}”?`)) return;
    await this.api.delete_rack(this.rack.id);
    delete this.rack.id;
    this.meta.saved = await this.api.list_racks();
    this._persist();
    this.renderSaved();
  }

  async sendRackToLive() {
    if (!this.rack.pads.some(Boolean)) { toast('Il kit è vuoto'); return; }
    await sendToLive(this.api, 'rack', this.rack);
  }

  async exportRack() {
    if (!this.rack.pads.some(Boolean)) { toast('Il kit è vuoto'); return; }
    const btn = $('#rk-export');
    btn.loading = true;
    try {
      const res = await this.api.export_rack(this.rack);
      if (res.error) toast(`Errore: ${res.error}`);
      else if (res.folder) toast(`Esportato in ${res.folder}`);
    } finally {
      btn.loading = false;
    }
  }
}
