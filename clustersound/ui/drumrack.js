// "Drum Rack" screen: 8×8 pads (Launchpad Pro layout), grouped by a geometry and filled with a seed
// sample plus similar ones; exported as an Ableton Drum Rack.
import { refKey } from './sequencer.js';
import { toast, suggestBus, showPopover } from './sendmenu.js';
import { NO_ALT, dynControls, wireDynControls, readDynControls } from './pattern.js';

const $ = (s, root = document) => root.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LS_KEY = 'clustersound.rack';
const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const noteName = (n) => `${NOTE_NAMES[n % 12]}${Math.floor(n / 12) - 2}`; // Live: C1 = 36
const HAT_FAMILIES = new Set(['chat', 'ohat', 'hats']);
const MODES = [['nearest', 'Più simili'], ['random', 'Casuale'], ['manual', 'Manuale'], ['trail', 'Percorso']];
const KIND_BADGE = { library: '', online: 'WEB', file: 'FILE' };
const DRAG_TYPE = 'application/x-clustersound-rack';
const LS_RANDOM = 'clustersound.randomRack';
const MAX_PER_BUS = 8;
const ALT_LABELS = [['off', 'insieme (solo il 1° attivo)'], ['cycle', 'a giro'], ['random', 'casuale'], ['random_pass', 'casuale ogni giro']];

const newRack = () => ({ name: 'Kit', geometry: 'cols8', mapping: 'launchpad', pads: new Array(64).fill(null), groups: {} });

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
    this.rack = newRack();
    this.pad = 0;                          // selected pad (its group is the target of every fill)
    this.seed = null;                      // last clicked sample: ref
    this.opts = { mode: 'nearest', variation: 0.3, filter: 'class', oneshot: true, avoid: true };
    this.browse = { q: '', family: null, follow: true, items: [] };
    this.manual = { seedKey: '', cands: [], picked: [] };
  }

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
    try { localStorage.setItem(LS_KEY, JSON.stringify({ rack: this.rack, pad: this.pad, opts: this.opts })); } catch { /* private mode */ }
    this.api.protect_samples(this.rack.pads.filter((r) => r?.kind === 'online'), 'rack');
  }

  // ---------------------------------------------------------------- geometry helpers
  get groups() { return this.geoById[this.rack.geometry].groups; }

  groupOf(p) { return this.groups.findIndex((g) => g.includes(p)); }

  settings(g) {
    const geo = this.geoById[this.rack.geometry];
    const s = this.rack.groups[`${geo.id}:${g}`] || {};
    const family = this.famById[s.family] ? s.family : geo.families[g];
    return { family, choke: s.choke ?? (HAT_FAMILIES.has(family) ? 1 : 0), lock: !!s.lock };
  }

  setSetting(g, key, value) {
    const k = `${this.rack.geometry}:${g}`;
    this.rack.groups[k] = { ...this.settings(g), ...this.rack.groups[k], [key]: value };
    this._persist();
  }

  note(p) { return this.meta.notes[this.rack.mapping][p]; }

  // ---------------------------------------------------------------- shell
  _buildShell() {
    const root = $('#rack');
    root.innerHTML = `
      <aside class="sidebar rk-browser">
        <div class="filter-title">Sample <span class="links"><label title="Il browser segue la famiglia del gruppo selezionato"><input type="checkbox" id="rk-follow"> segui gruppo</label></span></div>
        <select id="rk-bfam" class="rk-select"></select>
        <input id="rk-q" class="search" type="search" placeholder="Cerca per nome o cartella…" autocomplete="off">
        <div class="hint">Clic: ascolta e usa come seed · doppio clic: riempi il gruppo · trascina su un pad</div>
        <div id="rk-blist" class="rk-blist"></div>
        <div class="rk-trail-box">
          <div class="filter-title">Percorso dei simili <span class="links"><a href="#" id="rk-trail-use">usa sul gruppo</a></span></div>
          <div id="rk-trail" class="rk-trail"></div>
        </div>
      </aside>
      <main class="rk-main">
        <div class="rk-bar">
          <input id="rk-name" class="rk-name" type="text" maxlength="80" title="Nome del kit (anche del file .adg)">
          <div class="seg" id="rk-geo"></div>
          <select id="rk-map" class="rk-select" title="Note MIDI dei pad">
            <option value="launchpad">Note: Launchpad / Live (quadranti 4×4)</option>
            <option value="rows">Note: righe sequenziali (36 + riga×8)</option>
          </select>
          <div class="spacer"></div>
          <button class="btn" id="rk-auto" title="Riempie i gruppi vuoti in base alla famiglia (Alt+clic: rigenera tutti i gruppi non bloccati)">Auto-riempi</button>
          <button class="btn" id="rk-random" title="Per ogni gruppo non bloccato (🔒): un gruppo di sample simili a caso della sua famiglia, con sample a caso">🎲 Casuale</button>
          <select id="rk-saved" class="rk-select" title="Kit salvati"></select>
          <button class="btn" id="rk-save" title="Salva il kit">Salva</button>
          <button class="btn" id="rk-del" title="Elimina il kit salvato" hidden>Elimina</button>
          <button class="btn" id="rk-clear" title="Svuota tutti i pad">Svuota</button>
          <button class="btn" id="rk-toseq" title="Carica i sample del kit nei bus del Sequencer">→ Sequencer</button>
          <button class="btn primary" id="rk-export">Esporta per Ableton</button>
        </div>
        <div class="rk-stage">
          <div id="rk-grid" class="rk-grid"></div>
          <aside id="rk-insp" class="rk-insp"></aside>
        </div>
      </main>`;

    $('#rk-geo').innerHTML = this.meta.geometries.map((g) => `<button class="seg-btn" data-geo="${g.id}">${esc(g.label)}</button>`).join('');
    $('#rk-bfam').innerHTML = this.meta.families.map((f) => `<option value="${f.id}">${esc(f.label)}</option>`).join('');
    $('#rk-follow').checked = this.browse.follow;

    $('#rk-geo').onclick = (e) => {
      const b = e.target.closest('[data-geo]');
      if (!b) return;
      this.rack.geometry = b.dataset.geo;
      this._persist();
      this.renderAll();
      this._followGroup();
    };
    $('#rk-map').onchange = (e) => { this.rack.mapping = e.target.value; this._persist(); this.renderGrid(); };
    $('#rk-name').oninput = (e) => { this.rack.name = e.target.value; this._persist(); };
    $('#rk-auto').onclick = (e) => this.autofill(!e.altKey);
    $('#rk-random').onclick = (e) => this.openRandomize(e.currentTarget);
    $('#rk-toseq').onclick = () => this.openLoadDialog();
    $('#rk-clear').onclick = () => {
      if (!this.rack.pads.some(Boolean) || !confirm('Svuotare tutti i 64 pad?')) return;
      this.rack.pads = new Array(64).fill(null);
      this._persist();
      this.renderAll();
    };
    $('#rk-save').onclick = () => this.save();
    $('#rk-del').onclick = () => this.deleteSaved();
    $('#rk-saved').onchange = (e) => this.loadSaved(e.target.value);
    $('#rk-export').onclick = () => this.exportRack();

    // browser
    let qTimer = 0;
    $('#rk-q').oninput = (e) => { this.browse.q = e.target.value; clearTimeout(qTimer); qTimer = setTimeout(() => this.loadBrowser(), 150); };
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
    grid.onclick = (e) => {
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
      if (act === 'mode') { this.opts.mode = t.dataset.mode; this._persist(); this.renderInspector(); }
      else if (act === 'fill') this.fillGroup();
      else if (act === 'clear-group') this.clearGroup();
      else if (act === 'play-seed' && this.seed) this.audition(this.seed);
      else if (act === 'play') this.audition(this.manual.cands[+t.dataset.k]);
      else if (act === 'use-trail') this.fillFromTrail();
    };
    insp.onchange = (e) => {
      const t = e.target;
      const g = this.groupOf(this.pad);
      if (t.dataset.set === 'family') { this.setSetting(g, 'family', t.value); this.renderAll(); this._followGroup(); }
      else if (t.dataset.set === 'choke') { this.setSetting(g, 'choke', +t.value); }
      else if (t.dataset.set === 'lock') { this.setSetting(g, 'lock', t.checked); this.renderGrid(); }
      else if (t.dataset.opt) {
        this.opts[t.dataset.opt] = t.type === 'checkbox' ? t.checked : t.type === 'range' ? +t.value : t.value;
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

  // ---------------------------------------------------------------- render
  renderAll() {
    $('#rk-name').value = this.rack.name;
    $('#rk-map').value = this.rack.mapping;
    document.querySelectorAll('#rk-geo .seg-btn').forEach((b) => b.classList.toggle('active', b.dataset.geo === this.rack.geometry));
    this.renderSaved();
    this.renderGrid();
    this.renderInspector();
    this.renderTrail();
  }

  renderGrid() {
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
        ${this.rack.geometry !== 'free' || lock ? `<span>${lock ? '🔒 ' : ''}${this.rack.geometry !== 'free' ? esc(fam.label) : ''}</span>` : ''}</div>`);
    });
    $('#rk-grid').innerHTML = html.join('');
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
    const html = [`
      <div class="rk-ihead"><span class="dot" style="background:${fam.color}"></span>
        <b>Gruppo ${g + 1}</b><span class="hint">${pads.length} pad · ${filled} pieni · ${noteName(this.note(pads[0]))}${pads.length > 1 ? '…' : ''}</span></div>
      <label class="rk-field">Famiglia
        <select data-set="family" class="rk-select">${this.meta.families.map((f) => `<option value="${f.id}" ${f.id === s.family ? 'selected' : ''}>${esc(f.label)}</option>`).join('')}</select></label>
      <label class="rk-field" title="I pad con lo stesso choke group si zittiscono a vicenda (es. hat aperto/chiuso)">Choke group
        <select data-set="choke" class="rk-select"><option value="0">nessuno</option>${Array.from({ length: 16 }, (_, i) => `<option value="${i + 1}" ${s.choke === i + 1 ? 'selected' : ''}>${i + 1}</option>`).join('')}</select></label>
      <label class="rk-check" title="Casuale e Auto-riempi (Alt) non cambiano i gruppi bloccati"><input type="checkbox" data-set="lock" ${s.lock ? 'checked' : ''}> 🔒 blocca gruppo</label>
      <div class="rk-sep"></div>
      <div class="rk-seed">${seed
        ? `<button class="pt-ib" data-act="play-seed" title="Ascolta">▶</button><span class="dot" style="background:${this.classColor[seed.cls] || '#8a8f98'}"></span>
           <span class="rk-seed-name" title="${esc(seed.path || seed.name)}">${esc(seed.name)}</span>`
        : '<span class="hint">Seed: clicca un sample nel browser, su un pad o “Drum Rack” dal menu Invia della Libreria.</span>'}</div>
      <div class="seg rk-modes">${MODES.map(([m, l]) => `<button class="seg-btn ${o.mode === m ? 'active' : ''}" data-act="mode" data-mode="${m}">${l}</button>`).join('')}</div>`];
    if (o.mode === 'random') {
      html.push(`<label class="rk-field" title="Quanto lontano dal seed può pescare: 0% = i più simili">Variazione <span id="rk-var-v">${Math.round(o.variation * 100)}%</span>
        <input type="range" min="0" max="1" step="0.05" value="${o.variation}" data-opt="variation"></label>`);
    }
    html.push(`<label class="rk-field">Simili tra
      <select data-opt="filter" class="rk-select">
        <option value="class" ${o.filter === 'class' ? 'selected' : ''}>stessa classe del seed</option>
        <option value="family" ${o.filter === 'family' ? 'selected' : ''}>famiglia del gruppo (${esc(fam.label)})</option>
        <option value="none" ${o.filter === 'none' ? 'selected' : ''}>tutta la libreria</option>
      </select></label>
      <label class="rk-check"><input type="checkbox" data-opt="oneshot" ${o.oneshot ? 'checked' : ''}> solo one-shot</label>
      <label class="rk-check"><input type="checkbox" data-opt="avoid" ${o.avoid ? 'checked' : ''}> evita sample già nel kit</label>`);
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
      <button class="btn primary" data-act="fill" ${canFill ? '' : 'disabled'}>${o.mode === 'random' && filled ? '↻ Rigenera gruppo' : 'Riempi gruppo'}</button>
      <button class="btn" data-act="clear-group" ${filled ? '' : 'disabled'}>Svuota gruppo</button></div>
      ${seed && !similarOk && pads.length > 1 ? '<div class="hint">Sample online/file: niente simili, trascinalo su un pad.</div>' : ''}`);
    $('#rk-insp').innerHTML = html.join('');
    if (o.mode === 'manual' && similarOk) this._loadCandidates();
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
    box.innerHTML = this.manual.cands.length ? this.manual.cands.map((c, k) => `<label class="rk-cand">
      <input type="checkbox" data-pick="${k}" ${this.manual.picked.includes(k) ? 'checked' : ''}>
      <button class="pt-ib" data-act="play" data-k="${k}" title="Ascolta">▶</button>
      <span class="dot" style="background:${this.classColor[c.cls] || '#8a8f98'}"></span>
      <span class="rk-cname" title="${esc(c.path)}">${esc(c.name)}</span><b>${Math.round(c.sim * 100)}%</b></label>`).join('')
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
    const saved = this.meta.saved || [];
    $('#rk-saved').innerHTML = `<option value="">${saved.length ? 'Carica kit…' : 'Nessun kit salvato'}</option>`
      + saved.map((r) => `<option value="${esc(r.id)}" ${r.id === this.rack.id ? 'selected' : ''}>${esc(r.name)}</option>`).join('');
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
    el.innerHTML = `<div class="send-title">Pad ${noteName(this.note(p))}${ref ? ` · <b>${esc(ref.name)}</b>` : ''}</div>
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
    let p = !pads[this.pad] ? this.pad : this.groups[g].find((q) => !pads[q]) ?? pads.findIndex((r) => !r);
    if (p < 0) p = this.pad;
    const replaced = !!pads[p];
    pads[p] = ref;
    this.pad = p;
    this.seed = ref;
    this._persist();
    if (!$('#rack').hidden) this.renderAll();
    toast(`Drum Rack · pad ${noteName(this.note(p))} (gruppo ${this.groupOf(p) + 1})${replaced ? ', kit pieno: sostituito' : ''}: ${ref.name}`);
  }

  openRandomize(anchor) {
    let o = { scope: 'all', folder: '', oneshot: true, dyn: false, margin: 0.3 };
    try { o = { ...o, ...JSON.parse(localStorage.getItem(LS_RANDOM) || '{}') }; } catch { /* private mode */ }
    const pop = showPopover(anchor, `
      <div class="pop-title">🎲 Kit casuale</div>
      <div class="hint">Ogni gruppo prende un gruppo di sample simili scelto a caso tra quelli della sua famiglia, e sample a caso da lì.
        I gruppi bloccati (🔒) restano com'erano.</div>
      <label class="pop-field">Gruppi
        <select data-o="scope"><option value="all" ${o.scope === 'all' ? 'selected' : ''}>tutti (non bloccati)</option>
          <option value="empty" ${o.scope === 'empty' ? 'selected' : ''}>solo quelli vuoti</option></select></label>
      <label class="pop-field">Solo dalla cartella / pack (facoltativo)<input type="text" data-o="folder" value="${esc(o.folder)}" placeholder="es. Cymatics"></label>
      <label class="pop-check"><input type="checkbox" data-o="oneshot" ${o.oneshot ? 'checked' : ''}> solo one-shot (niente loop)</label>
      ${dynControls(o, 'gruppi')}
      <div class="pop-actions"><button class="btn primary" data-go>Genera</button></div>`);
    wireDynControls(pop);
    pop.querySelector('[data-go]').onclick = async () => {
      o = { scope: pop.querySelector('[data-o=scope]').value, folder: pop.querySelector('[data-o=folder]').value.trim(),
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
    let modal = $('#rk-load');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'rk-load';
      modal.className = 'modal';
      document.body.appendChild(modal);
    }
    modal.hidden = false;
    modal.innerHTML = `<div class="modal-box rk-load">
      <h3>Carica il Drum Rack nel Sequencer</h3>
      <div class="hint">Ogni sample va nel bus della sua classe (max ${MAX_PER_BUS} per bus). Scegli quali bus caricare
        e, quando un bus riceve più sample, se suonano insieme o si alternano a ogni colpo.</div>
      <div class="rk-load-rows">${ids.map((id) => {
        const b = buses.find((x) => x.id === id);
        const n = kit[id].length;
        const def = NO_ALT.has(id) || n < 2 ? 'off' : 'random';
        return `<div class="rk-load-row" data-bus="${id}">
          <label class="rk-check"><input type="checkbox" data-use checked><span class="dot" style="background:${b.color}"></span><b>${esc(b.label)}</b></label>
          <span class="hint">${n} dal kit · ora ${counts[id] || 0} layer</span>
          ${b.melodic || n < 2 ? '<span class="hint">—</span>'
            : `<select class="rk-select" data-alt title="Come suonano i sample del bus">${ALT_LABELS.map(([m, l]) => `<option value="${m}" ${m === def ? 'selected' : ''}>${l}</option>`).join('')}</select>`}
        </div>`;
      }).join('')}</div>
      <div class="rk-load-opts">
        <label class="rk-check"><input type="radio" name="rk-mode" value="replace" checked> Sovrascrivi i bus selezionati</label>
        <label class="rk-check"><input type="radio" name="rk-mode" value="add"> Aggiungi ai layer esistenti</label>
        <label class="rk-check"><input type="checkbox" data-clear> Svuota anche gli altri bus (sovrascrivi tutto)</label>
      </div>
      <div class="modal-actions"><button class="btn" data-cancel>Annulla</button><button class="btn primary" data-ok>Carica e apri il Sequencer</button></div>
    </div>`;
    const close = () => { modal.hidden = true; };
    modal.querySelector('[data-cancel]').onclick = close;
    modal.onclick = (e) => { if (e.target === modal) close(); };
    modal.querySelector('[data-clear]').onchange = (e) => {
      if (e.target.checked) modal.querySelector('input[value=replace]').checked = true;
    };
    modal.querySelector('[data-ok]').onclick = async () => {
      const assign = {};
      for (const row of modal.querySelectorAll('.rk-load-row')) {
        if (!row.querySelector('[data-use]').checked) continue;
        assign[row.dataset.bus] = { refs: kit[row.dataset.bus], alt: row.querySelector('[data-alt]')?.value || 'off' };
      }
      const clearOthers = modal.querySelector('[data-clear]').checked;
      const replace = clearOthers || modal.querySelector('input[name=rk-mode]:checked').value === 'replace';
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

  async exportRack() {
    if (!this.rack.pads.some(Boolean)) { toast('Il kit è vuoto'); return; }
    const btn = $('#rk-export');
    btn.disabled = true;
    btn.textContent = 'Esporto…';
    try {
      const res = await this.api.export_rack(this.rack);
      if (res.error) toast(`Errore: ${res.error}`);
      else if (res.folder) toast(`Esportato in ${res.folder}`);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Esporta per Ableton';
    }
  }
}
