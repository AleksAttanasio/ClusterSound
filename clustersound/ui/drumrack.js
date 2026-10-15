// "Drum Rack" screen: 8×8 pads (Launchpad Pro layout) or a Roland SPD-SX (9 pads + pedal / Trig 2), grouped
// by a geometry / configuration and filled with a seed sample plus similar ones; exported as an Ableton Drum Rack.
import { refKey } from './sequencer.js';
import { toast, suggestBus, showPopover } from './sendmenu.js';
import { sendToLive } from './live.js';
import { NO_ALT, dynControls, wireDynControls, readDynControls } from './pattern.js';
import { btn, iconBtn, openDialog, FILE_MANAGER } from './kit.js';
import { setRow, savedFlash } from './settings.js';
import { svg } from './icons.js';
import { t } from './i18n.js';

const $ = (s, root = document) => root.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LS_KEY = 'clustersound.rack';
const LS_SPD = 'clustersound.rack.spdsx';
const LS_DEVICE = 'clustersound.rackDevice';
const DEVICES = [['grid64', '8×8 controller (Launchpad)'], ['spdsx', 'Roland SPD-SX']]; // t() where shown
const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const noteName = (n) => `${NOTE_NAMES[n % 12]}${Math.floor(n / 12) - 2}`; // Live: C1 = 36
const HAT_FAMILIES = new Set(['chat', 'ohat', 'hats']);
const MODES = [['nearest', 'Most similar'], ['random', 'Random'], ['manual', 'Manual'], ['trail', 'Trail']]; // t() where shown
const KIND_BADGE = { library: '', online: 'WEB', file: 'FILE' };
const DRAG_TYPE = 'application/x-clustersound-rack';
const LS_RANDOM = 'clustersound.randomRack';
const MAX_PER_BUS = 8;
const PEDAL_ICON = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 20h16M7 20l3-12h4l3 12M10 8l-1-4h6l-1 4"/></svg>';
const ALT_LABELS = [['off', 'Together (only the 1st active)'], ['cycle', 'In turn'], ['random', 'Random'], ['random_pass', 'Random every loop']]; // t() where shown

const newRack = () => ({ name: 'Kit', geometry: 'cols8', mapping: 'launchpad', pads: new Array(64).fill(null), groups: {} });
const newSpdRack = () => ({ device: 'spdsx', name: 'Kit SPD-SX', geometry: 'spd_kit', triggers: { trig1: true, trig2: false },
  pads: new Array(11).fill(null), groups: {} });

export class DrumRackEditor {
  constructor({ api, player, classes, getTrail, getSequencer, onOpenSequencer, onShowInLibrary }) {
    this.api = api;
    this.onShowInLibrary = onShowInLibrary; // (library id) -> the Library tab, 3D view, with the sample selected
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

  /** Keys of the Drum Rack tab: Delete / Backspace clears the selected pad. True when handled. */
  onKey(e) {
    if ((e.key !== 'Delete' && e.key !== 'Backspace') || document.querySelector('.popover, .send-menu')) return false;
    if (!this.ready || !this.rack.pads[this.pad]) return false;
    this.rack.pads[this.pad] = null;
    this._persist();
    this.renderAll();
    return true;
  }

  /** Drum Rack section of the Settings page: MIDI notes of the 8×8 kit's pads. */
  async renderSettings(body) {
    await this.ensure();
    const kit = this.racks.grid64;
    body.innerHTML = setRow(t('MIDI notes of the pads'), t('It applies to the open 8×8 kit ({kit}) and is saved with the kit: it sets the notes of the Drum Rack exported and sent to Live. The SPD-SX always uses the notes of its pads.', { kit: `<b>${esc(kit.name)}</b>` }),
      `<wa-select id="set-rk-map" size="s" value="${kit.mapping}" label="${t('Notes')}" style="width:300px">
         <wa-option value="launchpad">${t('Launchpad / Live (4×4 quadrants)')}</wa-option>
         <wa-option value="rows">${t('Sequential rows (36 + row×8)')}</wa-option></wa-select>`);
    body.querySelector('#set-rk-map').addEventListener('change', (e) => {
      kit.mapping = e.target.value;
      this._persist();
      if (!this.isSpd) this.renderGrid();
      savedFlash(body);
    });
  }

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
        <div class="filter-title">Sample <span class="links"><wa-checkbox size="xs" id="rk-follow" title="${t('The browser follows the family of the selected group')}">${t('Follow group')}</wa-checkbox></span></div>
        <wa-select id="rk-bfam" size="s" class="rk-select"></wa-select>
        <wa-input id="rk-q" class="search" type="search" size="s" with-clear placeholder="${t('Search by name or folder…')}" autocomplete="off"><wa-icon slot="start" name="search"></wa-icon></wa-input>
        <div class="hint">${t('Click: listen and use as seed · double-click: fill the group · drag onto a pad')}</div>
        <div id="rk-blist" class="rk-blist"></div>
        <div class="rk-trail-box">
          <div class="filter-title">${t('Trail of similar samples')} <span class="links"><a href="#" id="rk-trail-use">${t('Use on the group')}</a></span></div>
          <div id="rk-trail" class="rk-trail"></div>
        </div>
      </aside>
      <main class="rk-main">
        <div class="rk-bar">
          <wa-select id="rk-device" size="s" class="rk-select rk-device" title="${t('Which instrument the kit is for')}">${DEVICES.map(([id, l]) => `<wa-option value="${id}">${t(l)}</wa-option>`).join('')}</wa-select>
          <wa-select id="rk-geo" size="s" class="rk-select rk-geo" title="${t('Layout')}"></wa-select>
          <button id="rk-kit" class="rk-kit" title="${t('Saved kits')}"><span class="rk-kit-name"></span>${svg('chevron-down', 12)}</button>
          ${iconBtn('save', t('Save the kit'), { id: 'rk-save', cls: 'rk-ibtn' })}
          ${iconBtn('trash-2', t('Clear all the pads'), { id: 'rk-clear', cls: 'rk-ibtn rk-danger' })}
          ${btn(`${t('Send to')} ${svg('chevron-down', 11)}`, { id: 'rk-send' })}
          ${btn(t('Random'), { id: 'rk-random', variant: 'success', icon: 'dices' })}
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
      if (e.target.id !== 'rk-geo' || !e.target.value || e.target.value === this.rack.geometry) return;
      this.rack.geometry = e.target.value;
      this._fixPad();
      this._persist();
      this.renderAll();
      this._followGroup();
    });
    $('#rk-device').onchange = (e) => this.setDevice(e.target.value);
    $('#rk-random').onclick = (e) => (this.isSpd ? this.openGenerate(e.currentTarget) : this.openRandomize(e.currentTarget));
    $('#rk-clear').onclick = () => {
      if (!this.rack.pads.some(Boolean) || !confirm(t('Clear all the {n} pads?', { n: this.padCount }))) return;
      this.rack.pads = new Array(this.padCount).fill(null);
      this._persist();
      this.renderAll();
    };
    $('#rk-save').onclick = () => this.save();
    $('#rk-kit').onclick = (e) => this.openKitMenu(e.currentTarget);
    $('#rk-send').onclick = (e) => this.openSendMenu(e.currentTarget);

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
      else if (act === 'autofill') this.autofill(!e.altKey);
      else if (act === 'autosample') this.autosample();
      else if (act === 'clear-group') this.clearGroup();
      else if (act === 'lock') { const g = this.groupOf(this.pad); this.setSetting(g, 'lock', !this.settings(g).lock); this.renderGrid(); this.renderInspector(); }
      else if (act === 'reveal' && this.seed) this.revealSeed();
      else if (act === 'show-3d' && this.seed?.kind === 'library') this.onShowInLibrary?.(this.seed.id);
      else if (act === 'play-seed' && this.seed) this.audition(this.seed);
      else if (act === 'play') this.audition(this.manual.cands[+t.dataset.k]);
      else if (act === 'use-trail') this.fillFromTrail();
    };
    insp.onchange = (e) => {
      const el = e.target;
      const g = this.groupOf(this.pad);
      if (el.dataset.set === 'mode') { this.opts.mode = el.value; this._persist(); this.renderInspector(); }
      else if (el.dataset.set === 'family') { this.setSetting(g, 'family', el.value); this.renderAll(); this._followGroup(); }
      else if (el.dataset.set === 'choke') { this.setSetting(g, 'choke', +el.value); }
      else if (el.dataset.opt) {
        this.opts[el.dataset.opt] = el.localName === 'wa-checkbox' ? el.checked : el.localName === 'wa-slider' ? +el.value : el.value;
        this._persist();
        if (el.dataset.opt !== 'variation' && el.dataset.opt !== 'avoid') { this.manual.seedKey = ''; this.renderInspector(); }
      } else if (el.dataset.pick != null) {
        const k = +el.dataset.pick;
        const size = this.groups[g].length - 1;
        if (el.checked) {
          if (this.manual.picked.length >= size) { el.checked = false; toast(t('The group has room for {n} samples besides the seed', { n: size })); return; }
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
    $('#rk-geo').innerHTML = list.map((g) => `<wa-option value="${g.id}">${esc(g.label)}</wa-option>`).join('');
    $('#rk-geo').value = this.rack.geometry;
    $('#rk-geo').title = this.isSpd ? t('Pad configuration: which groups and which families') : t('Layout');
    $('#rk-random').title = this.isSpd
      ? t('Random, playable SPD-SX kit: random configuration, every group from a different group of similar samples')
      : t('For every unlocked group: a random group of similar samples of its family, with random samples');
  }

  _exportLabel() { return this.isSpd ? t('Export (Live + SPD-SX)') : t('Export for Ableton'); }

  setTrigger(key, on) {
    this.rack.triggers = { ...this.rack.triggers, [key]: on };
    this._fixPad();
    this._persist();
    this.renderAll();
    this._followGroup();
  }

  // ---------------------------------------------------------------- render
  renderAll() {
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
        style="${at(r, c)};${ref ? `--pc:${color}` : ''}" title="${ref ? esc(ref.name) + (ref.sim != null && ref.sim < 1 ? ` · ${t('similarity {p}%', { p: Math.round(ref.sim * 100) })}` : '') : t('Empty')}">
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
    const trg = this.rack.triggers || {};
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
      ${txt(623, 25, 'TRIG IN', 't', 'start')}${led(672, 21, trg.trig1)}${txt(684, 25, '-')}${led(696, 21, trg.trig2)}${led(722, 21, false)}${txt(734, 25, '-')}${led(746, 21, false)}
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
    const trg = this.rack.triggers || {};
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
        title="${esc(spd.labels[p])} · ${noteName(spd.notes[p])}${ref ? ` · ${esc(ref.name)}` : ` · ${t('empty')}`}">
        <span class="rk-note"><i>${noteName(spd.notes[p])}</i></span>${badge ? `<span class="rk-badge">${badge}</span>` : ''}
        ${tag}<span class="rk-pname">${ref ? esc(ref.name.replace(/\.[^.]+$/, '')) : ''}</span>
        ${p < 9 ? `<span class="spd-num">${p + 1}</span><i class="spd-led"></i>` : ''}</div>`;
    };
    const trig = (p, key, label, icon) => `<div class="spd-trig ${trg[key] ? '' : 'off'}">
        ${trg[key] ? cell(p, 'spd-tpad') : `<div class="spd-tpad spd-empty">${icon}<span>${t('Not connected')}</span></div>`}
        <wa-checkbox size="s" class="rk-check" data-trig="${key}" ${trg[key] ? 'checked' : ''}>${label}</wa-checkbox>
      </div>`;
    const grid = $('#rk-grid');
    grid.className = 'rk-spd';
    grid.innerHTML = `
      <div class="spd-unit">
        <div class="spd-padarea">${Array.from({ length: 9 }, (_, p) => cell(p, p < 3 ? 'spd-top' : '')).join('')}</div>
        ${this._spdConsole()}
      </div>
      <div class="spd-trigs">
        ${trig(spd.trig1, 'trig1', spd.labels[spd.trig1], PEDAL_ICON)}
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
      return `<wa-option value="${f.id}" ${off ? 'disabled' : ''}><span slot="start" class="dot" style="background:${f.color}"></span>${esc(f.label)}${off ? ` — ${t('too many pads of this kind')}` : ''}</wa-option>`;
    };
    const lib = seed?.kind === 'library';
    const html = [`
      <div class="rk-ihead"><span class="dot" style="background:${fam.color}"></span>
        <b>${esc(fam.label)} · ${t('Group {n}', { n: g + 1 })}</b><span class="hint">${t('{n} pads · {f} full', { n: pads.length, f: filled })} · ${esc(where)}</span>
        <button class="pt-ib ${s.lock ? 'on' : ''}" data-act="lock" title="${s.lock ? t('Unlock group') : t('Lock group')} · ${t('Random and Auto-fill (Alt) do not change the locked groups')}">${svg(s.lock ? 'lock' : 'lock-open', 11)}</button>
        <button class="pt-ib danger" data-act="clear-group" title="${t('Clear group')}" ${filled ? '' : 'disabled'}>${svg('trash-2', 11)}</button></div>
      <div class="rk-sep"></div>
      <div class="filter-title rk-sec">Sample</div>
      <div class="rk-line">
        <wa-select size="s" class="rk-fam" label="${t('Family')}" data-set="family" value="${s.family}">${this.meta.families.map(famOpt).join('')}</wa-select>
        <wa-select size="s" class="rk-choke" label="Choke" data-set="choke" value="${s.choke || 0}" title="${t('Pads with the same choke group silence each other (e.g. open/closed hat)')}"><wa-option value="0">—</wa-option>${Array.from({ length: 16 }, (_, i) => `<wa-option value="${i + 1}">${i + 1}</wa-option>`).join('')}</wa-select>
      </div>
      <div class="rk-seed">${seed
        ? `<button class="pt-ib" data-act="play-seed" title="${t('Listen')}">${svg('play', 11)}</button><span class="dot" style="background:${this.classColor[seed.cls] || '#8a8f98'}"></span>
           <span class="rk-seed-name" title="${esc(seed.path || seed.name)}">${esc(seed.name)}</span>
           <button class="pt-ib" data-act="reveal" title="${t('Show in {app}', { app: FILE_MANAGER })}">${svg('folder-open', 11)}</button>
           <button class="pt-ib" data-act="show-3d" title="${lib ? t('Show in the 3D view of the Library') : t('Only for Library samples')}" ${lib ? '' : 'disabled'}>${svg('scatter-3d', 13)}</button>`
        : `<span class="hint">${t('Seed: click a sample in the browser, a pad or “Drum Rack” in the Send menu of the Library.')}</span>`}</div>
      <div class="rk-sep"></div>
      <div class="filter-title rk-sec">${t('Generate')}</div>
      ${btn(t('Auto-fill'), { cls: 'cs-ai rk-wide', icon: 'sparkles', 'data-act': 'autofill', title: t('Fills the empty groups by family (Alt+click: regenerates every unlocked group)') })}
      <div class="rk-opt"><span>${t('Select by')}</span><wa-select size="s" data-set="mode" value="${o.mode}">${MODES.map(([m, l]) => `<wa-option value="${m}">${t(l)}</wa-option>`).join('')}</wa-select></div>`];
    if (o.mode === 'random') {
      html.push(`<div class="rk-field" title="${t('How far from the seed it can pick: 0% = the most similar')}"><span class="pop-row"><span>${t('Variation')}</span><span id="rk-var-v">${Math.round(o.variation * 100)}%</span></span>
        <wa-slider size="s" min="0" max="1" step="0.05" value="${o.variation}" data-opt="variation" label="${t('Variation')}"></wa-slider></div>`);
    }
    html.push(`<div class="rk-opt"><span>${t('Similar among')}</span><wa-select size="s" data-opt="filter" value="${o.filter}">
        <wa-option value="class">${t('Same class as the seed')}</wa-option>
        <wa-option value="family">${t('Family of the group ({family})', { family: esc(fam.label) })}</wa-option>
        <wa-option value="none">${t('The whole library')}</wa-option>
      </wa-select></div>
      <wa-checkbox size="s" class="rk-check" data-opt="oneshot" ${o.oneshot ? 'checked' : ''}>${t('One-shots only')}</wa-checkbox>
      <wa-checkbox size="s" class="rk-check" data-opt="avoid" ${o.avoid ? 'checked' : ''}>${t('Avoid samples already in the kit')}</wa-checkbox>`);
    if (o.mode === 'manual') {
      html.push(`<div class="filter-title">${t('Choose the similar ones')} <span id="rk-pick-count">${this.manual.picked.length}/${pads.length - 1}</span></div>
        <div id="rk-cands" class="rk-cands">${similarOk ? `<div class="hint">${t('Loading…')}</div>` : `<div class="hint">${t('It needs a seed from the Library.')}</div>`}</div>`);
    }
    if (o.mode === 'trail') {
      const trail = this.getTrail();
      html.push(`<div class="hint">${!trail.length
        ? t('No trail: in the Library open “Find similar” and re-centre with a double-click on the samples to draw it.')
        : trail.length < pads.length ? t('Uses the {n} stops of the trail (in order, completed with the similar ones of the last).', { n: trail.length })
          : t('Uses the {n} stops of the trail (in order, the first {k}).', { n: trail.length, k: pads.length })}</div>`);
    }
    const canFill = o.mode === 'trail' ? this.getTrail().length > 0 : !!seed && (similarOk || pads.length === 1);
    html.push(`<div class="rk-actions">
      ${btn(o.mode === 'random' && filled ? t('Regenerate group') : t('Fill group'), { variant: 'brand', icon: o.mode === 'random' && filled ? 'refresh-cw' : 'layout-grid', 'data-act': 'fill', disabled: !canFill })}</div>
      <div class="rk-actions">
      ${btn(t('Auto-sample'), { icon: 'plus', 'data-act': 'autosample', disabled: filled >= pads.length, title: t('Adds one sample similar to the group on its next empty pad (same criterion as Auto-fill)') })}</div>
      ${seed && !similarOk && pads.length > 1 ? `<div class="hint">${t('Online/file sample: no similar ones, drag it onto a pad.')}</div>` : ''}`);
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
      <button class="pt-ib" data-act="play" data-k="${k}" title="${t('Listen')}">${svg('play', 11)}</button>
      <wa-checkbox size="xs" class="rk-cname" data-pick="${k}" ${this.manual.picked.includes(k) ? 'checked' : ''} title="${esc(c.path)}"><span class="dot" style="background:${this.classColor[c.cls] || '#8a8f98'}"></span> ${esc(c.name)}</wa-checkbox><b>${Math.round(c.sim * 100)}%</b></div>`).join('')
      : `<div class="hint">${t('No similar samples with these filters.')}</div>`;
  }

  renderTrail() {
    const trail = this.getTrail();
    $('#rk-trail').innerHTML = trail.length
      ? trail.map((x, k) => `<button data-id="${x.id}" title="${t('Use as seed')}">${k + 1} · ${esc(x.name)}</button>`).join('')
      : `<span class="hint">${t('Empty: in the Library use “Find similar” and re-centre (double-click) to create a trail.')}</span>`;
    $('#rk-trail-use').hidden = !trail.length;
  }

  // the kit picker of the toolbar shows the open kit's name (an unsaved kit is marked as such)
  renderSaved() {
    const b = $('#rk-kit');
    b.querySelector('.rk-kit-name').textContent = this.rack.name || 'Kit';
    b.classList.toggle('unsaved', !this.rack.id);
    b.title = this.rack.id ? t('Saved kits') : `${t('Saved kits')} · ${t('not saved yet')}`;
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
      : `<div class="hint">${t('No samples: choose a folder in the Library or change the filter.')}</div>`;
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
    if (!seed) { toast(t('Choose a sample (seed) first')); return; }
    if (seed.kind !== 'library' || size === 1) { this._place(g, [seed]); return; }
    let refs;
    if (mode === 'manual') {
      await this._loadCandidates();
      const picked = [...this.manual.picked].sort((a, b) => a - b).map((k) => this.manual.cands[k]);
      refs = [{ ...seed, sim: 1 }, ...picked];
    } else {
      refs = await this.api.rack_fill(seed.id, size, mode === 'random' ? 'random' : 'nearest', this._apiOpts(true, g));
    }
    if (!refs.length) { toast(t('No similar samples with these filters')); return; }
    this._place(g, refs);
    if (refs.length < size) toast(t('Only {n} similar samples found: widen the filter', { n: refs.length - 1 }));
  }

  async fillFromTrail(trail = this.getTrail()) {
    if (!trail.length) { toast(t('No trail: use “Find similar” in the Library')); return; }
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
    const btn = $('#rk-insp [data-act=autofill]');
    if (btn) btn.disabled = true;
    try {
      const out = await this.api.rack_autofill(this.rack, onlyEmpty, this.opts.variation);
      this.rack.pads = out.pads;
      this._persist();
      this.renderAll();
      if (!this.rack.pads.some(Boolean)) toast(t('No samples in the Library to use'));
    } finally { if (btn) btn.disabled = false; }
  }

  // Auto-fill's criterion for one pad: the next empty pad of the selected group gets a sample similar to the group
  async autosample() {
    const g = this.groupOf(this.pad);
    const p = this.groups[g].find((q) => !this.rack.pads[q]);
    if (p == null) { toast(t('The group is full')); return; }
    const b = $('#rk-insp [data-act=autosample]');
    if (b) b.loading = true;
    try {
      const ref = await this.api.rack_autosample(this.rack, g, this.opts.variation);
      if (!ref) { toast(t('No similar samples with these filters')); return; }
      if (this.rack.pads[p] || this.groupOf(p) !== g) return; // the kit changed meanwhile
      this.rack.pads[p] = ref;
      this.pad = p;
      this._persist();
      this.renderAll();
    } finally { if (b?.isConnected) b.loading = false; }
  }

  // the seed's file in the Finder / File Explorer
  async revealSeed() {
    const ref = this.seed;
    const ok = ref.kind === 'library' ? await this.api.reveal(ref.id) : await this.api.reveal_path(ref.path);
    if (!ok) toast(t('Cannot show the file: it was moved or deleted'));
  }

  // from the library's "Send" menu and the similar-samples focus bar (Library tab)
  async sendSeed(ref) {
    await this.ensure();
    this.seed = ref;
    const mode = this.opts.mode === 'random' ? 'random' : 'nearest';
    await this.fillGroup(mode);
    const g = this.groupOf(this.pad);
    toast(`Drum Rack · ${t('group {n}', { n: g + 1 })}: ${ref.name}${ref.kind === 'library' && this.groups[g].length > 1 ? ` + ${t('{n} similar', { n: this.groups[g].length - 1 })}` : ''}`);
  }

  async sendTrail(trail) {
    await this.ensure();
    const n = await this.fillFromTrail(trail);
    if (n) toast(`Drum Rack · ${t('group {n}', { n: this.groupOf(this.pad) + 1 })}: ${t('{n} samples from the trail', { n })}`);
  }

  _padMenu(p, x, y) {
    document.querySelector('.rk-menu')?.remove();
    const ref = this.rack.pads[p];
    const el = document.createElement('div');
    el.className = 'send-menu rk-menu';
    el.innerHTML = `<div class="send-title">Pad ${esc(this.padName(p))}${ref ? ` · <b>${esc(ref.name)}</b>` : ''}</div>
      ${ref ? `<div class="send-row" data-m="seed">${t('Use as seed and fill the group')}</div><div class="send-row" data-m="clear">${t('Clear pad')}</div>` : ''}
      <div class="send-row" data-m="group">${t('Clear group')}</div>`;
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

  // ---------------------------------------------------------------- Library / Online "Send" menu
  // The menu works on one group (default: the one of the selected pad) and can switch to the others.
  groupLabel(g) { return `${t('Group {n}', { n: g + 1 })} · ${this.famById[this.settings(g).family].label}`; }

  async groupList() {
    await this.ensure();
    return this.groups.map((pads, g) => ({ g, label: this.groupLabel(g), count: pads.filter((p) => this.rack.pads[p]).length }));
  }

  get currentGroup() { return this.groupOf(this.pad); }

  groupSamples(g = this.currentGroup) {
    return this.groups[g].filter((p) => this.rack.pads[p]).map((p) => ({ pad: p, padName: this.padName(p), ref: this.rack.pads[p] }));
  }

  // n library samples similar to the group's seed (the last one added there, else its last library sample)
  // that are not in the kit yet nor in `skip`
  async suggestForGroup(g = this.currentGroup, n = 3, skip = []) {
    const lib = this.groupSamples(g).map((x) => x.ref).filter((r) => r.kind === 'library');
    if (!lib.length) return [];
    const seed = lib.find((r) => this.seed && refKey(r) === refKey(this.seed)) || lib[lib.length - 1];
    const used = new Set([...this.rack.pads.filter((r) => r?.kind === 'library').map((r) => r.id), ...skip]);
    const cands = await this.api.rack_candidates(seed.id, Math.min(60, n + used.size + 4), this._apiOpts(false, g));
    return cands.filter((c) => !used.has(c.id)).slice(0, n);
  }

  // The sample on group g: the selected pad if free and in the group, else the first free pad of the group;
  // group full: the selected pad (or the group's first) is replaced. Returns the pad.
  async addSample(ref, { group = this.currentGroup } = {}) {
    await this.ensure();
    const pads = this.rack.pads, gp = this.groups[group];
    const sel = gp.includes(this.pad) ? this.pad : gp[0];
    const p = !pads[sel] ? sel : gp.find((q) => !pads[q]) ?? sel;
    const replaced = !!pads[p];
    pads[p] = ref;
    this.pad = p;
    this.seed = ref;
    this._persist();
    if (!$('#rack').hidden) this.renderAll();
    if (replaced) toast(`Drum Rack · pad ${this.padName(p)}: ${t('group full: replaced')} · ${ref.name}`);
    return p;
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
    toast(placed.length ? `Drum Rack: ${t('{n} samples from {pad}', { n: placed.length, pad: this.padName(placed[0]) })}${left ? `, ${t('{n} not loaded (kit full)', { n: left })}` : ''}`
      : t('Drum Rack full: clear some pads'));
    return placed.length;
  }

  openRandomize(anchor) {
    let o = { scope: 'all', folder: '', oneshot: true, dyn: false, margin: 0.3 };
    try { o = { ...o, ...JSON.parse(localStorage.getItem(LS_RANDOM) || '{}') }; } catch { /* private mode */ }
    const pop = showPopover(anchor, `
      <div class="pop-title">${svg('dices')} ${t('Random kit')}</div>
      <div class="hint">${t('Every group takes a group of similar samples picked at random among those of its family, and random samples from there. The locked groups stay as they were.')}</div>
      <wa-select size="s" class="pop-field" label="${t('Groups')}" data-o="scope" value="${o.scope}"><wa-option value="all">${t('All (unlocked)')}</wa-option>
          <wa-option value="empty">${t('Only the empty ones')}</wa-option></wa-select>
      <wa-input size="s" class="pop-field" label="${t('Only from the folder / pack (optional)')}" data-o="folder" value="${esc(o.folder)}" placeholder="${t('E.g. Cymatics')}"></wa-input>
      <wa-checkbox size="s" class="pop-check" data-o="oneshot" ${o.oneshot ? 'checked' : ''}>${t('One-shots only (no loops)')}</wa-checkbox>
      ${dynControls(o, 'groups')}
      <div class="pop-actions">${btn(t('Generate'), { variant: 'brand', icon: 'dices', 'data-go': true })}</div>`);
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
      toast(n ? `${t('Random kit: {n} pads full', { n })}${o.dyn ? ` · ${t('dynamics ±{p}%', { p: Math.round(o.margin * 100) })}` : ''}` : t('No suitable samples (check the folder filter)'));
    };
  }

  // SPD-SX: a whole random, playable kit (configuration + samples), see Api.rack_generate
  openGenerate(anchor) {
    let o = { keep: false, folder: '', oneshot: true, dyn: false, margin: 0.3 };
    try { o = { ...o, ...JSON.parse(localStorage.getItem(LS_RANDOM + '.spdsx') || '{}') }; } catch { /* private mode */ }
    const pop = showPopover(anchor, `
      <div class="pop-title">${svg('dices')} ${t('Generate SPD-SX kit')}</div>
      <div class="hint">${t('It picks a playable configuration at random (at most pedal + 1 kick pad, 3 snare/clap pads) and fills every group with samples similar to each other, each from a different group of sounds. The pedal gets a kick. With a locked group the configuration stays the current one.')}</div>
      <wa-checkbox size="s" class="pop-check" data-o="keep" ${o.keep ? 'checked' : ''}>${t('Keep the current configuration')}</wa-checkbox>
      <wa-input size="s" class="pop-field" label="${t('Only from the folder / pack (optional)')}" data-o="folder" value="${esc(o.folder)}" placeholder="${t('E.g. Cymatics')}"></wa-input>
      <wa-checkbox size="s" class="pop-check" data-o="oneshot" ${o.oneshot ? 'checked' : ''}>${t('One-shots only (no loops)')}</wa-checkbox>
      ${dynControls(o, 'groups')}
      <div class="pop-actions">${btn(t('Generate'), { variant: 'brand', icon: 'dices', 'data-go': true })}</div>`);
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
      toast(n ? t('SPD-SX kit: {cfg} · {n} pads full', { cfg, n }) : t('No suitable samples (check the folder filter)'));
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
    if (!seq.ready) toast(t('Preparing the Sequencer…')); // first time: loads its pattern and samples
    await seq.ensure();
    const buses = seq.buses;
    const kit = this._kitByBus(buses);
    const ids = buses.map((b) => b.id).filter((id) => kit[id]);
    if (!ids.length) { toast(t('The Drum Rack is empty')); return; }
    const counts = seq.layerCounts();
    const modal = openDialog('rk-load', {
      label: t('Load the Drum Rack into the Sequencer'),
      width: '640px',
      body: `<div class="rk-load">
      <div class="hint">${t('Every sample goes to the bus of its class (max {max} per bus). Choose which buses to load and, when a bus gets several samples, whether they play together or alternate on every hit.', { max: MAX_PER_BUS })}</div>
      <div class="rk-load-rows">${ids.map((id) => {
        const b = buses.find((x) => x.id === id);
        const n = kit[id].length;
        const def = NO_ALT.has(id) || n < 2 ? 'off' : 'random';
        return `<div class="rk-load-row" data-bus="${id}">
          <wa-checkbox size="s" data-use checked><span class="dot" style="background:${b.color}"></span> <b>${esc(b.label)}</b></wa-checkbox>
          <span class="hint">${t('{n} from the kit · now {k} layers', { n, k: counts[id] || 0 })}</span>
          ${b.melodic || n < 2 ? '<span class="hint">—</span>'
            : `<wa-select size="xs" data-alt value="${def}" title="${t('How the samples of the bus play')}">${ALT_LABELS.map(([m, l]) => `<wa-option value="${m}">${t(l)}</wa-option>`).join('')}</wa-select>`}
        </div>`;
      }).join('')}</div>
      <div class="rk-load-opts">
        <wa-radio-group size="s" data-mode value="replace" label="${t('How to load')}">
          <wa-radio value="replace">${t('Overwrite the selected buses')}</wa-radio>
          <wa-radio value="add">${t('Add to the existing layers')}</wa-radio>
        </wa-radio-group>
        <wa-checkbox size="s" data-clear>${t('Clear the other buses too (overwrite everything)')}</wa-checkbox>
      </div></div>`,
      footer: btn(t('Cancel'), { 'data-cancel': true }) + btn(t('Load and open the Sequencer'), { variant: 'brand', icon: 'arrow-right', 'data-ok': true }),
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
      toast(t('Sequencer: {n} buses loaded from the Drum Rack', { n: Object.keys(assign).length }));
      this.onOpenSequencer?.();
    };
  }

  // ---------------------------------------------------------------- save / export
  // A saved kit is overwritten after a confirmation; a new one asks for its name.
  async save() {
    let name = this.rack.name || 'Kit';
    if (this.rack.id) {
      if (!confirm(t('Overwrite the saved kit “{name}”?', { name }))) return;
    } else {
      name = prompt(t('Name of the kit'), name);
      if (!name) return;
    }
    this.rack.name = name;
    const saved = await this.api.save_rack(this.rack);
    this.rack.id = saved.id;
    this.meta.saved = await this.api.list_racks();
    this._persist();
    this.renderAll();
    toast(t('Kit “{name}” saved', { name }));
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

  // empty kit for the current device (saved with a name on the first Save)
  newKit() {
    this.player.stop();
    this.rack = this.isSpd ? newSpdRack() : { ...newRack(), mapping: this.rack.mapping };
    this.manual.seedKey = '';
    this._fixPad();
    this._persist();
    this._buildBar();
    this.renderAll();
    this._followGroup();
  }

  async renameSaved(id) {
    const r = (this.meta.saved || []).find((x) => x.id === id);
    const name = r && prompt(t('Name of the kit'), r.name)?.trim();
    if (!name || name === r.name) return;
    await this.api.save_rack({ ...r, name });
    this.meta.saved = await this.api.list_racks();
    if (this.rack.id === id) { this.rack.name = name; this._persist(); if (this.isSpd) this.renderGrid(); }
    this.renderSaved();
  }

  async deleteSaved(id) {
    const r = (this.meta.saved || []).find((x) => x.id === id);
    if (!r || !confirm(t('Delete the saved kit “{name}”?', { name: r.name }))) return;
    await this.api.delete_rack(id);
    if (this.rack.id === id) delete this.rack.id;
    this.meta.saved = await this.api.list_racks();
    this._persist();
    this.renderSaved();
  }

  // Kit picker: "+ New Kit", then the saved kits of the device, each with rename (pencil) and delete (×).
  openKitMenu(anchor) {
    const saved = (this.meta.saved || []).filter((r) => (r.device || 'grid64') === this.device);
    const pop = showPopover(anchor, `<div class="rk-kit-menu">
      <button class="rk-kit-row rk-kit-new" data-new>${svg('plus', 13)}<span>${t('New Kit')}</span></button>
      ${saved.length ? '<div class="rk-kit-sep"></div>' : ''}
      ${saved.map((r) => `<div class="rk-kit-row ${r.id === this.rack.id ? 'on' : ''}" data-id="${esc(r.id)}">
        <span class="rk-kit-label" title="${esc(r.name)}">${esc(r.name)}</span>
        <button class="rk-kit-ib" data-rename title="${t('Rename')}">${svg('pencil', 12)}</button>
        <button class="rk-kit-ib danger" data-delete title="${t('Delete the saved kit')}">${svg('x', 13)}</button></div>`).join('')}
      ${saved.length ? '' : `<div class="hint rk-kit-empty">${t('No saved kits')}</div>`}</div>`);
    pop.onclick = async (e) => {
      if (e.target.closest('[data-new]')) { pop.close(); this.newKit(); return; }
      const row = e.target.closest('[data-id]');
      if (!row) return;
      const id = row.dataset.id;
      pop.close();
      if (e.target.closest('[data-rename]')) await this.renameSaved(id);
      else if (e.target.closest('[data-delete]')) await this.deleteSaved(id);
      else this.loadSaved(id);
    };
  }

  // "Send to ▾": the whole kit to the Sequencer, to Live or exported as files (same look as the Recorder's menu).
  openSendMenu(anchor) {
    const empty = !this.rack.pads.some(Boolean);
    const item = (go, ic, label, hint) => `<button class="sp-send-item" data-go="${go}"${empty ? ' disabled' : ''}><wa-icon name="${ic}"></wa-icon><span><b>${label}</b><span class="hint">${hint}</span></span></button>`;
    const pop = showPopover(anchor, `<div class="pop-title"><wa-icon name="arrow-right"></wa-icon> ${t('Send to')}</div>
      <div class="sp-send-list">
        ${item('seq', 'audio-lines', 'Sequencer', t('Loads the samples of the kit into the Sequencer buses'))}
        ${item('live', 'music', 'Ableton Live', t('Creates a track with this Drum Rack in Live (needs the ClusterSound device in the set)'))}
        ${item('export', 'file-down', this._exportLabel(), this.isSpd ? t('Drum Rack for Live on the SPD-SX notes + 16-bit WAV for SPD-SX Wave Manager') : t('Ableton Drum Rack (.adg) with its samples, in a folder'))}
      </div>`);
    pop.onclick = (e) => {
      const b = e.target.closest('[data-go]');
      if (!b || b.disabled) return;
      pop.close();
      if (b.dataset.go === 'seq') this.openLoadDialog();
      else if (b.dataset.go === 'live') this.sendRackToLive();
      else this.exportRack();
    };
  }

  async sendRackToLive() {
    if (!this.rack.pads.some(Boolean)) { toast(t('The kit is empty')); return; }
    await sendToLive(this.api, 'rack', this.rack);
  }

  async exportRack() {
    if (!this.rack.pads.some(Boolean)) { toast(t('The kit is empty')); return; }
    const btn = $('#rk-send');
    btn.loading = true;
    try {
      const res = await this.api.export_rack(this.rack);
      if (res.error) toast(t('Error: {error}', { error: res.error }));
      else if (res.folder) toast(t('Exported to {folder}', { folder: res.folder }));
    } finally {
      btn.loading = false;
    }
  }
}
