// "Store" mode of the Library: browse free samples and packs (Freesound, Openverse, Internet Archive,
// ccMixter) plus a curated showcase of royalty-free packs from sites without an API.
// Views: home (provider strip, categories, featured rows) · results (sounds or packs, grid or list)
// · pack page · provider page.
import { svg } from './icons.js';
import { FILE_MANAGER } from './kit.js';
import { setRow, savedFlash, openSettings } from './settings.js';

const $ = (s, root = document) => root.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtDur = (s) => (s === null || s === undefined ? '' : s < 1 ? `${Math.round(s * 1000)} ms` : s < 60 ? `${s.toFixed(1)} s` : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`);
const fmtSize = (b) => (!b ? '' : b > 1e9 ? `${(b / 1e9).toFixed(1)} GB` : b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} kB`);

const SRC_ABBR = { freesound: 'FS', openverse: 'OV', archive: 'IA', ccmixter: 'CC' };
const LICENSE_FILTERS = [['cc0', 'CC0 / PD'], ['by', 'BY'], ['by-sa', 'BY-SA'], ['nc', 'Non commerciale'], ['nd', 'No derivate'], ['unknown', 'Non dichiarata']];
const LIC_CLASS = { cc0: 'free', pd: 'free', by: 'attr', 'by-sa': 'attr', 'by-nd': 'restr', 'by-nc': 'restr', 'by-nc-sa': 'restr', 'by-nc-nd': 'restr', 'sampling+': 'restr', rf: 'free', unknown: 'unk' };
const PRESETS = [
  ['Kick', ['kick']], ['Snare', ['snare']], ['Hat', ['closed_hat', 'open_hat']], ['Clap', ['clap']],
  ['808', ['sub808']], ['Cymbal', ['ride', 'crash', 'cymbal_other']], ['Perc', ['perc_other', 'shaker', 'tambourine', 'hand_drum', 'cowbell']],
  ['Bass', ['bass']], ['Synth', ['synth', 'pad']], ['FX', ['riser', 'impact', 'downlifter']], ['Vocal', ['vocal', 'spoken']],
];
const SUSPECT_KEY = 'cs.store.suspect';
const SORTS = [['relevance', 'Rilevanza'], ['downloads', 'Più scaricati'], ['rating', 'Voto'], ['newest', 'Più recenti'], ['duration', 'Durata']];
const NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const ANY_KEY = 'any'; // wa-option values cannot be empty
const chip = (attrs, label) => `<wa-button size="xs" pill class="chip" ${attrs}>${label}</wa-button>`;
const SPIN = '<wa-spinner class="spin"></wa-spinner>';
const KIND_LABEL = { api: 'Ricerca live', curated: 'Vetrina' };
const hue = (text) => { let h = 0; for (const c of String(text)) h = (h * 31 + c.charCodeAt(0)) % 360; return h; };
const nSounds = (n) => `${n} suon${n === 1 ? 'o' : 'i'}`;
const fmtNum = (n) => (n === null || n === undefined ? '' : n >= 1e6 ? `${(n / 1e6).toFixed(1)} M` : n >= 1e4 ? `${Math.round(n / 1e3)} k` : n.toLocaleString('it-IT'));

export class Online {
  constructor({ api, player, classes, groups, types }) {
    this.api = api;
    this.player = player;
    this.classes = classes.filter((c) => c.id !== 'unsorted');
    this.byId = Object.fromEntries(classes.map((c) => [c.id, c]));
    this.groups = groups;
    this.types = types;
    this.p = {
      q: '', instruments: new Set(), sources: new Set(), licenses: new Set(), commercial: false,
      types: new Set(), dur_min: null, dur_max: null, bpm_min: null, bpm_max: null, key: '',
      lossless: false, packs: 'all', include_suspect: (() => { try { return localStorage.getItem(SUSPECT_KEY) === '1'; } catch { return false; } })(), sort: 'relevance',
    };
    this.groupBy = 'source';
    this.data = {};        // source -> response
    this.expanded = {};    // pack uid -> expand response
    this.collapsed = new Set();
    this.loading = new Set();
    this.searchSeq = 0;
    this.started = false;
    this.view = { name: 'home' }; // home | results | pack | provider
    this.history = [];
    this.kind = 'sounds';         // results: sounds | packs
    this.layout = (() => { try { return localStorage.getItem('cs.storeLayout') === 'list' ? 'list' : 'grid'; } catch { return 'grid'; } })();
    this.packData = {};           // source -> pack search response
    this.packPage = null;         // open pack page response
    this.provData = null;         // open provider page: {sounds, packs}
    this.featured = null;
    this.queue = null;            // "listen to all" on a pack page: {uids, i}
    player.subscribe((playing, id, ended) => { this._syncPlayButtons(playing, id); if (ended) this._queueNext(id); });
  }

  async show() {
    if (this.started) return this._ready;
    this.started = true;
    this._ready = (async () => {
      this.meta = await this.api.online_init();
      this.prov = Object.fromEntries(this.meta.providers.map((p) => [p.id, p]));
      this.p.sources = new Set(this.meta.sources.map((s) => s.id));
      this._buildSidebar();
      this._bind();
      this._renderKeyHint();
      this.render();
      this._loadFeatured();
      this._pollDownloads();
    })();
    return this._ready;
  }

  /** Open the results with some parameters (e.g. from the library: same instrument as a sample). */
  async browse(over = {}) {
    await this.show();
    if (over.instruments) this.p.instruments = new Set(over.instruments);
    if (over.q !== undefined) { this.p.q = over.q; $('#online-q').value = over.q; }
    this._refreshSrvHints();
    this.search();
  }

  // ---------------------------------------------------------------- params
  params() {
    const p = this.p;
    const num = (v) => (v === null || v === '' || Number.isNaN(+v) ? null : +v);
    return {
      q: p.q.trim(), instruments: [...p.instruments], sources: [...p.sources], licenses: [...p.licenses],
      commercial: p.commercial, types: [...p.types], dur_min: num(p.dur_min), dur_max: num(p.dur_max),
      bpm_min: num(p.bpm_min), bpm_max: num(p.bpm_max), key: p.key || null, lossless: p.lossless,
      packs: p.packs, include_suspect: p.include_suspect, sort: p.sort,
    };
  }

  // ---------------------------------------------------------------- sidebar
  _srvHint(filter) {
    const srcs = (this.meta.server_filters[filter] || []).filter((s) => this.p.sources.has(s));
    if (!srcs.length) return '<span class="srv" title="Filtrato localmente sui risultati">Locale</span>';
    const names = srcs.map((s) => this.meta.sources.find((x) => x.id === s).label).join(', ');
    return `<span class="srv" title="Applicato direttamente da: ${esc(names)}. Sulle altre fonti è filtrato localmente.">${srcs.map((s) => SRC_ABBR[s]).join('·')}</span>`;
  }

  _buildSidebar() {
    const sb = $('#online-sidebar');
    const cls = [];
    for (const g of this.groups) {
      const members = this.classes.filter((c) => c.group === g);
      if (!members.length) continue;
      cls.push(`<div class="group-title" data-ogroup="${esc(g)}"><span>${esc(g)}</span></div>`);
      for (const c of members) {
        cls.push(`<div class="cls-row o-cls" data-cls="${c.id}" title="Clic: aggiungi/togli · Alt+clic: solo questo">
          <span class="dot" style="background:${c.color}"></span><span class="cls-name">${esc(c.label)}</span></div>`);
      }
    }
    const keyOpts = [`<wa-option value="${ANY_KEY}">Qualsiasi</wa-option>`]
      .concat(NOTES.flatMap((n) => [`<wa-option value="${n} major">${n} major</wa-option>`, `<wa-option value="${n} minor">${n} minor</wa-option>`])).join('');
    const grp = (id, title) => `<div class="filter-group collapsed" data-group="${id}">
        <div class="fg-head"><span class="caret">${svg('chevron-down', 12)}</span><span>${title}</span><wa-badge pill variant="brand" class="fg-count" data-fg-count="${id}"></wa-badge></div>
        <div class="fg-body">`;
    sb.innerHTML = `
      <div class="filter-block">
        <div class="filter-title">Strumento <span>${'<span data-srv="instrument"></span>'} <a href="#" id="o-ins-clear">Tutti</a></span></div>
        <div id="o-ins-summary" class="hint"></div>
        <div id="o-ins-list" class="o-ins-list">${cls.join('')}</div>
      </div>
      ${grp('src', 'Fonti e licenza')}
      <div class="filter-block">
        <div class="filter-title">Fonti</div>
        <div id="o-sources">${this.meta.sources.map((s) => `
          <div class="o-src"><wa-checkbox size="s" class="o-src-name" data-src="${s.id}" checked>${esc(s.label)}</wa-checkbox>
          <span class="o-src-status" data-src-status="${s.id}"></span></div>`).join('')}
        </div>
      </div>
      <div class="filter-block">
        <div class="filter-title">Licenza <span data-srv="license"></span></div>
        <div class="chips" id="o-lic">${LICENSE_FILTERS.map(([k, l]) => chip(`data-lic="${k}"`, l)).join('')}</div>
        <wa-checkbox size="s" class="o-check" id="o-commercial">Solo uso commerciale (no NC/ND) <span data-srv="commercial"></span></wa-checkbox>
      </div></div></div>
      ${grp('char', 'Tipo e caratteristiche')}
      <div class="filter-block">
        <div class="filter-title">Tipo <span data-srv="type"></span></div>
        <div class="chips" id="o-types">${this.types.map((t) => chip(`data-type="${esc(t)}"`, esc(t))).join('')}</div>
      </div>
      <div class="filter-block">
        <div class="filter-title">Durata (s) <span data-srv="duration"></span></div>
        <div class="o-range"><wa-number-input size="s" without-steppers min="0" step="0.1" id="o-dmin" placeholder="Min"></wa-number-input><span>–</span><wa-number-input size="s" without-steppers min="0" step="0.1" id="o-dmax" placeholder="Max"></wa-number-input></div>
      </div>
      <div class="filter-block">
        <div class="filter-title">BPM <span data-srv="bpm"></span></div>
        <div class="o-range"><wa-number-input size="s" without-steppers min="40" max="250" id="o-bmin" placeholder="Min"></wa-number-input><span>–</span><wa-number-input size="s" without-steppers min="40" max="250" id="o-bmax" placeholder="Max"></wa-number-input></div>
      </div>
      <div class="filter-block">
        <div class="filter-title">Tonalità <span data-srv="key"></span></div>
        <wa-select size="s" id="o-key" value="${ANY_KEY}">${keyOpts}</wa-select>
      </div></div></div>
      ${grp('fmt', 'Formato, pack e ordine')}
      <div class="filter-block">
        <div class="filter-title">Formato e pack <span data-srv="lossless"></span></div>
        <wa-checkbox size="s" class="o-check" id="o-lossless">Solo lossless (wav / aiff / flac)</wa-checkbox>
        <wa-select size="s" id="o-packs" value="all" style="margin-top:8px">
          <wa-option value="all">File singoli e pack</wa-option><wa-option value="files">Solo file singoli</wa-option><wa-option value="packs">Solo pack</wa-option>
        </wa-select>
      </div>
      <div class="filter-block">
        <div class="filter-title">Ordina <span data-srv="sort"></span></div>
        <wa-select size="s" id="o-sort" value="relevance">${SORTS.map(([k, l]) => `<wa-option value="${k}">${l}</wa-option>`).join('')}</wa-select>
      </div></div></div>`;
    sb.onclick = (e) => {
      const h = e.target.closest('.fg-head'); if (!h) return;
      h.parentElement.classList.toggle('collapsed');
    };
    this._refreshSrvHints();
  }

  _refreshGroupCounts() {
    const p = this.p;
    const b = (v) => (v ? 1 : 0);
    const set = (v) => (v !== null && v !== '' ? 1 : 0);
    const counts = {
      src: b(p.sources.size !== this.meta.sources.length) + p.licenses.size + b(p.commercial),
      char: p.types.size + set(p.dur_min) + set(p.dur_max) + set(p.bpm_min) + set(p.bpm_max) + b(p.key),
      fmt: b(p.lossless) + b(p.packs !== 'all') + b(p.sort !== 'relevance'),
    };
    for (const [id, n] of Object.entries(counts)) {
      const el = document.querySelector(`[data-fg-count="${id}"]`);
      if (el) { el.textContent = n || ''; el.style.display = n ? '' : 'none'; }
    }
  }

  _refreshSrvHints() {
    document.querySelectorAll('#online-sidebar [data-srv]').forEach((el) => { el.innerHTML = this._srvHint(el.dataset.srv); });
    this._refreshGroupCounts();
    const n = this.p.instruments.size;
    $('#o-ins-summary').textContent = n ? `${n} selezionat${n === 1 ? 'o' : 'i'}` : 'Tutti gli strumenti';
    document.querySelectorAll('.o-cls').forEach((r) => r.classList.toggle('on', this.p.instruments.has(r.dataset.cls)));
    $('#o-ins-list').classList.toggle('has-sel', n > 0);
    document.querySelectorAll('#online-presets .chip').forEach((b) => {
      const ids = JSON.parse(b.dataset.ins);
      b.classList.toggle('on', ids.length === this.p.instruments.size && ids.every((i) => this.p.instruments.has(i)));
    });
  }

  _bind() {
    const changed = () => { this._refreshSrvHints(); this._debouncedSearch(); };
    $('#online-presets').innerHTML = PRESETS.map(([l, ids]) => chip(`data-ins='${JSON.stringify(ids)}'`, l)).join('');
    $('#online-presets').onclick = (e) => {
      const b = e.target.closest('.chip'); if (!b) return;
      const ids = JSON.parse(b.dataset.ins);
      const same = ids.length === this.p.instruments.size && ids.every((i) => this.p.instruments.has(i));
      this.p.instruments = same ? new Set() : new Set(ids);
      changed();
    };
    $('#o-ins-list').onclick = (e) => {
      const row = e.target.closest('.o-cls');
      const gt = e.target.closest('[data-ogroup]');
      if (row) {
        const id = row.dataset.cls;
        if (e.altKey) this.p.instruments = new Set([id]);
        else this.p.instruments.has(id) ? this.p.instruments.delete(id) : this.p.instruments.add(id);
      } else if (gt) {
        const ids = this.classes.filter((c) => c.group === gt.dataset.ogroup).map((c) => c.id);
        const all = ids.every((i) => this.p.instruments.has(i));
        ids.forEach((i) => (all ? this.p.instruments.delete(i) : this.p.instruments.add(i)));
      } else return;
      changed();
    };
    $('#o-ins-clear').onclick = (e) => { e.preventDefault(); this.p.instruments.clear(); changed(); };
    $('#o-sources').onchange = (e) => {
      const s = e.target.dataset.src; if (!s) return;
      e.target.checked ? this.p.sources.add(s) : this.p.sources.delete(s);
      changed();
    };
    const toggleChips = (sel, key, attr) => {
      $(sel).onclick = (e) => {
        const b = e.target.closest('.chip'); if (!b) return;
        const v = b.dataset[attr];
        this.p[key].has(v) ? this.p[key].delete(v) : this.p[key].add(v);
        b.classList.toggle('on', this.p[key].has(v));
        changed();
      };
    };
    toggleChips('#o-lic', 'licenses', 'lic');
    toggleChips('#o-types', 'types', 'type');
    const bindVal = (sel, key, ev = 'change', map = (el) => el.value) => {
      $(sel).addEventListener(ev, (e) => { this.p[key] = map(e.target); changed(); });
    };
    bindVal('#o-commercial', 'commercial', 'change', (el) => el.checked);
    bindVal('#o-lossless', 'lossless', 'change', (el) => el.checked);
    bindVal('#o-dmin', 'dur_min', 'input');
    bindVal('#o-dmax', 'dur_max', 'input');
    bindVal('#o-bmin', 'bpm_min', 'input');
    bindVal('#o-bmax', 'bpm_max', 'input');
    bindVal('#o-key', 'key', 'change', (el) => (el.value === ANY_KEY ? '' : el.value));
    bindVal('#o-packs', 'packs');
    bindVal('#o-sort', 'sort');

    $('#online-q').addEventListener('keydown', (e) => { if (e.key === 'Enter') { this.p.q = $('#online-q').value || ''; this.search(); } });
    $('#online-go').onclick = () => { this.p.q = $('#online-q').value || ''; this.search(); };
    $('#online-group').addEventListener('change', (e) => {
      if (e.target.id !== 'online-group') return;
      this.groupBy = e.target.value;
      this.render();
    });
    $('#online-results').onclick = (e) => this._onResultsClick(e);
    $('#store-view').onclick = (e) => this._onResultsClick(e);
    $('#store-nav').onclick = (e) => this._onResultsClick(e);
    $('#dl-open').onclick = () => this.api.open_download_dir();
    $('#dl-library').onclick = () => this.onLibrary?.(this.meta.settings.download_dir);
    $('#dl-toggle').onclick = () => $('#downloads').classList.toggle('collapsed');
    $('#downloads-list').onclick = (e) => {
      const r = e.target.closest('[data-path]');
      if (r && r.dataset.path) this.api.reveal_path(r.dataset.path);
    };
  }

  _debouncedSearch() {
    clearTimeout(this._t);
    this._t = setTimeout(() => this.search(), 450);
  }

  // ---------------------------------------------------------------- search
  _activeSources() {
    const all = [...this.p.sources];
    return this.kind === 'packs' ? all.filter((s) => this.meta.pack_sources.includes(s)) : all;
  }

  async search() {
    if (this.view.name !== 'results') this._go({ name: 'results' });
    const seq = ++this.searchSeq;
    const store = this.kind === 'packs' ? (this.packData = {}) : (this.data = {});
    this.expanded = {};
    this.loading.clear();
    const sources = this._activeSources();
    for (const s of sources) this.loading.add(s);
    this.render();
    // one call per source so fast sources show up first
    const params = this.params();
    const call = this.kind === 'packs' ? 'online_packs' : 'online_more';
    await Promise.all(sources.map(async (s) => {
      const res = await this.api[call](s, params, 1);
      if (seq !== this.searchSeq) return;
      this.loading.delete(s);
      store[s] = res;
      this.render();
    }));
  }

  async more(source) {
    const packs = this.kind === 'packs';
    const cur = (packs ? this.packData : this.data)[source];
    if (!cur) return;
    this.loading.add(source);
    this.render();
    const res = await this.api[packs ? 'online_packs' : 'online_more'](source, this.params(), cur.page + 1);
    this.loading.delete(source);
    if (!res.error) {
      cur.results = cur.results.concat(res.results.filter((r) => !cur.results.some((x) => x.uid === r.uid)));
      cur.page = res.page;
      cur.more = res.more;
    }
    this.render();
  }

  // ---------------------------------------------------------------- render
  _statusLine(s) {
    const d = this.data[s];
    if (this.loading.has(s) && !d?.results?.length) return `${SPIN} ricerca…`;
    if (!d) return '';
    if (d.error) return `<span class="error">${esc(d.error)}</span>`;
    const tot = d.total ? ` di ${d.total.toLocaleString('it-IT')}` : '';
    return `${d.results.length} risultati${tot}`;
  }

  render() {
    if (!this.meta) return;
    const results = this.view.name === 'results';
    const list = results && this.layout === 'list' && this.kind === 'sounds';
    for (const s of this.meta.sources) {
      const el = document.querySelector(`[data-src-status="${s.id}"]`);
      if (el) {
        const d = (this.kind === 'packs' ? this.packData : this.data)[s.id];
        el.innerHTML = !results || !this.p.sources.has(s.id) ? '' : this.loading.has(s.id) ? SPIN
          : d?.error ? (d.needs_key ? '<span class="error">Chiave</span>' : '<span class="error">Errore</span>') : d ? d.results.length : '';
      }
    }
    $('#online-results').hidden = !list;
    $('#store-view').hidden = list;
    $('#online-presets-bar').hidden = !(this.view.name === 'home' || results);
    $('#online-group').classList.toggle('tab-hidden', !list);
    this._renderNav();
    if (list) this._renderList();
    else if (this.view.name === 'home') this._renderHome();
    else if (results) this._renderGrid();
    else if (this.view.name === 'pack') this._renderPack();
    else if (this.view.name === 'provider') this._renderProvider();
    this._syncPlayButtons(this.player.playing, this.player.id);
  }

  _renderList() {
    const box = $('#online-results');
    const active = this.meta.sources.filter((s) => this.p.sources.has(s.id));
    if (!active.length) { box.innerHTML = '<div class="o-empty">Seleziona almeno una fonte.</div>'; return; }
    const html = [];
    if (this.groupBy === 'source') {
      for (const s of active) {
        const d = this.data[s.id];
        const open = !this.collapsed.has(s.id);
        const rows = d?.results || [];
        html.push(`<section class="o-section">
          <header class="o-sec-head" data-collapse="${s.id}"><span class="caret">${svg(open ? 'chevron-down' : 'chevron-right', 14)}</span>
            <span class="o-sec-title">${esc(s.label)}</span><span class="o-sec-status">${this._statusLine(s.id)}</span>
            ${d?.needs_key ? '<wa-button size="xs" variant="brand" data-settings="1"><wa-icon slot="start" name="settings"></wa-icon>Inserisci API key</wa-button>' : ''}</header>
          ${open ? `<div class="o-rows">${rows.map((r) => this._row(r)).join('')}</div>
            ${d?.more ? `<wa-button size="s" appearance="filled-outlined" class="o-more" data-more="${s.id}" ${this.loading.has(s.id) ? 'loading disabled' : ''}>Carica altri</wa-button>` : ''}
            ${d && !d.error && !rows.length && !this.loading.has(s.id) ? `<div class="o-none">Nessun risultato con questi filtri${d.fetched ? ` (${d.fetched} scartati dai filtri)` : ''}.</div>` : ''}` : ''}
        </section>`);
      }
    } else {
      const all = active.flatMap((s) => this.data[s.id]?.results || []);
      const groups = new Map();
      for (const c of this.classes) groups.set(c.id, []);
      groups.set(null, []);
      for (const r of all) (groups.get(r.instrument) || groups.get(null)).push(r);
      for (const [cid, rows] of groups) {
        if (!rows.length) continue;
        const c = cid ? this.byId[cid] : null;
        const key = `ins:${cid}`;
        const open = !this.collapsed.has(key);
        html.push(`<section class="o-section"><header class="o-sec-head" data-collapse="${key}"><span class="caret">${svg(open ? 'chevron-down' : 'chevron-right', 14)}</span>
          ${c ? `<span class="dot" style="background:${c.color}"></span>` : ''}<span class="o-sec-title">${esc(c ? c.label : 'Strumento non determinato / pack misti')}</span>
          <span class="o-sec-status">${rows.length}</span></header>
          ${open ? `<div class="o-rows">${rows.map((r) => this._row(r, true)).join('')}</div>` : ''}</section>`);
      }
      const loadingAny = active.some((s) => this.loading.has(s.id));
      if (loadingAny) html.push(`<div class="o-none">${SPIN} ricerca in corso…</div>`);
      const moreSrc = active.filter((s) => this.data[s.id]?.more);
      if (moreSrc.length && !loadingAny) html.push('<wa-button size="s" appearance="filled-outlined" class="o-more" data-more-all="1">Carica altri da tutte le fonti</wa-button>');
    }
    box.innerHTML = html.join('');
  }

  _licBadge(r) {
    return `<span class="lic lic-${LIC_CLASS[r.license] || 'unk'}" title="${esc(r.license_label)} · uso commerciale come sample: ${r.commercial_ok ? 'sì' : 'no / da verificare'}">${esc(r.license_label)}</span>`;
  }

  _row(r, showSource = false, child = false) {
    const c = r.instrument ? this.byId[r.instrument] : null;
    const meta = [r.bpm ? `${Math.round(r.bpm)} BPM` : '', r.key || '', r.format ? r.format.toUpperCase() : '',
      r.samplerate ? `${(r.samplerate / 1000).toFixed(1)}k` : ''].filter(Boolean).join(' · ');
    const tags = child ? '' : (r.tags || []).slice(0, 6).map((t) => `<button class="tag" data-tag="${esc(t)}">${esc(t)}</button>`).join('');
    const sub = child ? esc(r.path) : [r.author ? esc(r.author) : '', showSource ? esc(r.source_label) : '', r.type ? esc(r.type) : ''].filter(Boolean).join(' · ');
    const ex = this.expanded[r.uid];
    const packInfo = r.is_pack ? `<span class="pack-badge">PACK${r.filesize ? ' · ' + fmtSize(r.filesize) : ''}</span>` : '';
    const playable = !r.is_pack || r.preview_url;
    return `<div class="o-row ${child ? 'child' : ''} ${r.suspect ? 'suspect' : ''}" data-uid="${esc(r.uid)}">
      ${r.is_pack && !child ? `<button class="o-btn o-expand" data-expand="${esc(r.uid)}" title="Mostra i file del pack">${svg(ex ? 'chevron-down' : 'chevron-right')}</button>`
        : `<button class="o-btn o-play" data-play="${esc(r.uid)}" ${playable ? '' : 'disabled'} title="Ascolta">${svg('play', 12)}</button>`}
      <span class="dot" style="background:${c ? c.color : 'transparent'};${c ? '' : 'box-shadow:0 0 0 1px var(--line-2) inset'}" title="${esc(c ? c.label : 'Strumento non determinato')}"></span>
      <div class="o-main">
        <div class="o-title" title="${esc(r.title)}">${esc(r.title)} ${packInfo} ${r.suspect ? `<span class="warn" title="Probabile libreria commerciale ricaricata: verifica i diritti">${svg('triangle-alert', 11)} sospetto</span>` : ''}</div>
        <div class="o-sub">${sub}${tags ? ` <span class="tags">${tags}</span>` : ''}</div>
      </div>
      <div class="o-wave">${r.waveform_img ? `<img src="${esc(r.waveform_img)}" alt="" loading="lazy">` : ''}</div>
      ${this._licBadge(r)}
      <div class="num o-dur">${fmtDur(r.duration)}</div>
      <div class="o-meta" title="${esc(meta)}">${esc(meta)}</div>
      <div class="o-actions">
        ${playable && (r.preview_url || r.download_url) ? `<button class="o-btn" data-send="${esc(r.uid)}" title="Invia al Sequencer o al Drum Rack (file temporaneo, nessun download)">${svg('arrow-right')}</button>` : ''}
        ${r.download_url ? `<button class="o-btn" data-dl="${esc(r.uid)}" title="Scarica${r.download_note ? ' — ' + esc(r.download_note) : ''}${r.filesize ? ' (' + fmtSize(r.filesize) + ')' : ''}">${svg('download')}</button>` : ''}
        ${r.page_url ? `<button class="o-btn" data-open="${esc(r.page_url)}" title="Apri la pagina della fonte">${svg('external-link')}</button>` : ''}
      </div>
    </div>${ex ? this._expansion(r, ex) : ''}`;
  }

  _expansion(r, ex) {
    if (ex.loading) return `<div class="o-children"><div class="o-none">${SPIN} lettura del pack…</div></div>`;
    if (ex.error) return `<div class="o-children"><div class="o-none error">${esc(ex.error)}</div></div>`;
    const archives = (ex.archives || []).map((a) => `<wa-button size="xs" appearance="filled-outlined" data-dl-archive="${esc(a.url)}" data-pack="${esc(r.uid)}" title="Scarica l'archivio intero"><wa-icon slot="start" name="download"></wa-icon>${esc(a.name)} ${a.size ? '(' + fmtSize(a.size) + ')' : ''}</wa-button>`).join(' ');
    const filtered = ex.files.length < ex.total;
    return `<div class="o-children">
      <div class="o-pack-bar">${ex.total} file nel pack${filtered ? ` · ${ex.files.length} corrispondono ai filtri <a href="#" data-expand-all="${esc(r.uid)}">Mostra tutti</a>` : ''} ${archives}</div>
      ${ex.files.slice(0, 400).map((f) => this._row(f, false, true)).join('')}
      ${ex.files.length > 400 ? `<div class="o-none">… altri ${ex.files.length - 400} file: restringi i filtri</div>` : ''}
      ${!ex.files.length && !ex.archives?.length ? '<div class="o-none">Nessun file audio consultabile (archivio RAR/7z?): apri la pagina della fonte.</div>' : ''}
    </div>`;
  }

  async _onResultsClick(e) {
    const t = e.target.closest('button, wa-button, a, header, [data-pack], [data-provider], [data-cat]');
    if (!t) return;
    if (t.tagName === 'A' && (t.dataset.nav || t.dataset.provider || t.dataset.home !== undefined)) e.preventDefault();
    if (t.dataset.play) { this.queue = null; return this.togglePlay(t.dataset.play, t); }
    if (t.dataset.dlArchive) return this.download(t.dataset.pack, t.dataset.dlArchive);
    if (t.dataset.home !== undefined) return this._home();
    if (t.dataset.back !== undefined) return this._back();
    if (t.dataset.nav !== undefined) return this._jump(+t.dataset.nav);
    if (t.dataset.pack) return this.openPack(t.dataset.pack);
    if (t.dataset.provider) return this.openProvider(t.dataset.provider);
    if (t.dataset.cat) { this.p.instruments = new Set(JSON.parse(t.dataset.cat)); this._refreshSrvHints(); return this.search(); }
    if (t.dataset.kind) { this.kind = t.dataset.kind; return this.search(); }
    if (t.dataset.layout) {
      this.layout = t.dataset.layout;
      try { localStorage.setItem('cs.storeLayout', this.layout); } catch { /* private mode */ }
      return this.render();
    }
    if (t.dataset.dlPack) return this.downloadPack(t.dataset.dlPack);
    if (t.dataset.playAll !== undefined) return this.playAll();
    if (t.dataset.packMore !== undefined) return this._packMore();
    if (t.dataset.toLibrary !== undefined) return this.onLibrary?.(this.meta.settings.download_dir);
    if (t.dataset.send) {
      const ref = await this.api.online_ref(t.dataset.send);
      const r = t.getBoundingClientRect();
      if (ref && this.onSend) this.onSend(ref, r.left - 300, r.bottom + 4);
      return;
    }
    if (t.dataset.dl) return this.download(t.dataset.dl);
    if (t.dataset.dlArchive) return this.download(t.dataset.pack, t.dataset.dlArchive);
    if (t.dataset.open) return this.api.open_url(t.dataset.open);
    if (t.dataset.more) return this.more(t.dataset.more);
    if (t.dataset.moreAll) return Promise.all([...this.p.sources].filter((s) => this.data[s]?.more).map((s) => this.more(s)));
    if (t.dataset.settings) return openSettings('online');
    if (t.dataset.tag) { $('#online-q').value = t.dataset.tag; this.p.q = t.dataset.tag; this.kind = 'sounds'; return this.search(); }
    if (t.dataset.expand) return this.toggleExpand(t.dataset.expand);
    if (t.dataset.expandAll) { e.preventDefault(); return this.toggleExpand(t.dataset.expandAll, true); }
    if (t.dataset.collapse) {
      const k = t.dataset.collapse;
      this.collapsed.has(k) ? this.collapsed.delete(k) : this.collapsed.add(k);
      this.render();
    }
  }

  async toggleExpand(uid, all = false) {
    if (this.expanded[uid] && !all) { delete this.expanded[uid]; this.render(); return; }
    this.expanded[uid] = { loading: true };
    this.render();
    const params = all ? { include_suspect: true } : this.params();
    this.expanded[uid] = await this.api.online_expand(uid, params);
    this.render();
  }

  // ---------------------------------------------------------------- store navigation
  _go(view, replace = false) {
    if (!replace) this.history.push(this.view);
    this.view = view;
    $('#store-view').scrollTop = 0;
  }

  _home() { this.history = []; this.view = { name: 'home' }; this.searchSeq++; this.render(); }

  _back() {
    if (!this.history.length) return this._home();
    this.view = this.history.pop();
    this.render();
  }

  _jump(i) { // breadcrumb: go back to the i-th view of the trail
    if (i >= this.history.length) return;
    this.view = this.history[i];
    this.history = this.history.slice(0, i);
    this.render();
  }

  _viewLabel(v) {
    if (v.name === 'home') return 'Store';
    if (v.name === 'results') return this.p.q ? `«${esc(this.p.q)}»` : 'Risultati';
    if (v.name === 'pack') return esc(v.title || 'Pack');
    if (v.name === 'provider') return esc(this.prov[v.id]?.name || v.id);
    return '';
  }

  _renderNav() {
    const trail = [...this.history, this.view];
    const crumbs = trail.map((v, i) => (i === trail.length - 1
      ? `<span class="sn-cur">${this._viewLabel(v)}</span>`
      : v.name === 'home' ? '<a href="#" data-home>Store</a>' : `<a href="#" data-nav="${i}">${this._viewLabel(v)}</a>`));
    const results = this.view.name === 'results';
    const seg = (attr, items, cur) => `<span class="sn-seg">${items.map(([v, l, ic]) => `<button class="${v === cur ? 'on' : ''}" data-${attr}="${v}">${ic ? svg(ic, 13) : ''}${l}</button>`).join('')}</span>`;
    $('#store-nav').innerHTML = `
      ${this.view.name !== 'home' ? `<button class="o-btn sn-back" data-back title="Indietro">${svg('arrow-left', 14)}</button>` : `<span class="sn-icon">${svg('store', 16)}</span>`}
      <span class="sn-crumbs">${crumbs.join('<span class="sn-sep">›</span>')}</span>
      <span class="spacer"></span>
      ${results ? seg('kind', [['sounds', 'Suoni', 'music'], ['packs', 'Pack', 'package']], this.kind) : ''}
      ${results && this.kind === 'sounds' ? seg('layout', [['grid', '', 'layout-grid'], ['list', '', 'list']], this.layout) : ''}`;
  }

  // ---------------------------------------------------------------- store: building blocks
  _logo(id, size = 'm') {
    const p = this.prov[id];
    if (!p) return '';
    return p.logo ? `<span class="pv-logo pv-${size}" title="${esc(p.name)}"><img src="${esc(p.logo)}" alt="${esc(p.name)}"></span>`
      : `<span class="pv-logo pv-${size} pv-mono" style="--pc:${p.color}" title="${esc(p.name)}">${esc(p.name.slice(0, 2))}</span>`;
  }

  _cover(r, { icon = null, big = false } = {}) {
    const c = r.instrument ? this.byId[r.instrument] : null;
    const h = hue(r.title + r.author);
    const bg = c ? `linear-gradient(135deg, ${c.color}55, hsl(${h} 45% 16%))` : `linear-gradient(135deg, hsl(${h} 55% 34%), hsl(${(h + 60) % 360} 45% 14%))`;
    return `<div class="sc-cover ${big ? 'big' : ''}" style="background:${bg}">
      ${r.waveform_img ? `<img class="sc-wave" src="${esc(r.waveform_img)}" alt="" loading="lazy">` : ''}
      ${icon ? `<span class="sc-icon">${svg(icon, big ? 40 : 26)}</span>` : ''}
      ${r.preview_url ? `<button class="sc-play" data-play="${esc(r.uid)}" title="Ascolta">${svg('play', 16)}</button>` : ''}
    </div>`;
  }

  _soundCard(r) {
    const meta = [fmtDur(r.duration), r.bpm ? `${Math.round(r.bpm)} BPM` : '', r.key || ''].filter(Boolean).join(' · ');
    const c = r.instrument ? this.byId[r.instrument] : null;
    return `<div class="sc-card" data-uid="${esc(r.uid)}">
      ${this._cover(r)}
      <div class="sc-body">
        <div class="sc-title" title="${esc(r.title)}">${esc(r.title)}</div>
        <div class="sc-sub">${this._logo(r.source, 's')}<span>${esc(r.author || r.source_label)}</span></div>
        <div class="sc-meta">${this._licBadge(r)}${c ? `<span class="sc-cls"><span class="dot" style="background:${c.color}"></span>${esc(c.label)}</span>` : ''}<span class="num">${esc(meta)}</span></div>
        <div class="sc-actions">
          ${r.preview_url || r.download_url ? `<button class="o-btn" data-send="${esc(r.uid)}" title="Invia al Sequencer o al Drum Rack (file temporaneo)">${svg('arrow-right')}</button>` : ''}
          ${r.download_url ? `<button class="o-btn" data-dl="${esc(r.uid)}" title="Scarica${r.download_note ? ' — ' + esc(r.download_note) : ''}">${svg('download')}</button>` : ''}
          ${r.page_url ? `<button class="o-btn" data-open="${esc(r.page_url)}" title="Apri la pagina della fonte">${svg('external-link')}</button>` : ''}
        </div>
      </div>
    </div>`;
  }

  _packCard(r) {
    const i = r.info || {};
    // grouped search cards only know how many sounds match; the pack page has the full count
    const count = i.num_sounds ? nSounds(i.num_sounds) : i.matching ? `${nSounds(i.matching)} corrispondent${i.matching === 1 ? 'e' : 'i'}` : r.filesize ? fmtSize(r.filesize) : '';
    const matching = i.matching && i.num_sounds && i.matching < i.num_sounds ? ` · ${i.matching} corrispondono` : '';
    const dls = i.downloads ? `${svg('download', 11)} ${fmtNum(i.downloads)}` : '';
    return `<div class="sc-card pack ${r.suspect ? 'suspect' : ''}" data-pack="${esc(r.uid)}" data-title="${esc(r.title)}" title="Apri il pack">
      ${this._cover(r, { icon: 'package' })}
      <div class="sc-body">
        <div class="sc-title" title="${esc(r.title)}">${esc(r.title)}</div>
        <div class="sc-sub">${this._logo(r.source, 's')}<span>${esc(r.author || r.source_label)}</span></div>
        <div class="sc-meta">${r.license !== 'unknown' ? this._licBadge(r) : ''}<span>${esc(count)}${matching}</span><span class="sc-dl">${dls}</span></div>
        ${r.suspect ? `<div class="warn">${svg('triangle-alert', 11)} probabile materiale commerciale</div>` : ''}
      </div>
    </div>`;
  }

  _curatedCard(c) {
    const p = this.prov[c.provider];
    const lic = { license: c.license, license_label: this.meta.licenses[c.license], commercial_ok: true };
    return `<div class="sc-card curated">
      <div class="sc-cover" style="background:linear-gradient(135deg, ${p.color}66, hsl(${hue(c.title)} 35% 13%))">${this._logo(c.provider, 'l')}</div>
      <div class="sc-body">
        <div class="sc-title" title="${esc(c.title)}">${esc(c.title)}</div>
        <div class="sc-sub"><span>${esc(p.name)}</span>${c.count ? `<span>· ${c.count} file</span>` : ''}</div>
        <div class="sc-desc">${esc(c.description)}</div>
        <div class="sc-meta">${this._licBadge(lic)}${c.note ? `<span class="sc-note" title="${esc(c.note)}">Condizioni</span>` : ''}</div>
        <div class="sc-actions"><wa-button size="xs" appearance="filled-outlined" data-open="${esc(c.url)}"><wa-icon slot="start" name="external-link"></wa-icon>Scarica dal sito</wa-button></div>
      </div>
    </div>`;
  }

  _shelf(title, body, { link = '', note = '' } = {}) {
    return `<section class="shelf"><header class="shelf-head"><h3>${title}</h3>${note ? `<span class="hint">${note}</span>` : ''}<span class="spacer"></span>${link}</header>${body}</section>`;
  }

  _rowOf(cards, empty = '') { return cards.length ? `<div class="sc-row">${cards.join('')}</div>` : `<div class="o-none">${empty}</div>`; }

  // ---------------------------------------------------------------- store: home
  async _loadFeatured() {
    this.featured = null;
    if (this.view.name === 'home') this.render();
    const f = await this.api.online_featured();
    this.featured = f;
    for (const k of Object.keys(f)) {
      if (f[k].results) f[k].results = f[k].results.filter((r) => r.is_pack || k === 'cc0_new');
    }
    if (this.view.name === 'home') this.render();
  }

  _featuredRow(key, card, empty) {
    const f = this.featured?.[key];
    if (!f) return `<div class="o-none">${SPIN} caricamento…</div>`;
    if (f.needs_key) return `<div class="sc-keycta">${this._logo('freesound', 'm')}<div><b>Sblocca i pack di Freesound</b><br><span class="hint">Serve una API key gratuita: oltre 600.000 suoni, organizzati in pack.</span></div><wa-button size="s" variant="brand" data-settings="1"><wa-icon slot="start" name="settings"></wa-icon>Inserisci API key</wa-button></div>`;
    if (f.error) return `<div class="o-none error">${esc(f.error)}</div>`;
    return this._rowOf(f.results.slice(0, 16).map(card), empty);
  }

  _renderHome() {
    const providers = this.meta.providers.map((p) => `
      <div class="pv-card" data-provider="${p.id}" title="${esc(p.description)}">
        ${this._logo(p.id, 'l')}
        <div class="pv-name">${esc(p.name)}</div>
        <div class="pv-kind ${p.kind}">${KIND_LABEL[p.kind]}</div>
      </div>`).join('');
    const cats = PRESETS.map(([label, ids]) => {
      const c = this.byId[ids[0]];
      return `<div class="cat-tile" data-cat='${JSON.stringify(ids)}' style="--cc:${c?.color || '#888'}"><span>${esc(label)}</span></div>`;
    }).join('');
    const fsLink = '<a href="#" data-provider="freesound">Tutti →</a>';
    $('#store-view').innerHTML = `
      <div class="store-hero">
        <div><h2>Sample gratuiti, pronti per la libreria</h2>
          <div class="hint">Solo fonti libere: pubblico dominio, Creative Commons e pack royalty-free. Ogni download arriva con il suo .license.txt.</div></div>
      </div>
      ${this._shelf('Provider', `<div class="pv-strip">${providers}</div>`)}
      ${this._shelf('Categorie', `<div class="cat-grid">${cats}</div>`)}
      ${this._shelf('Pack in evidenza su Freesound', this._featuredRow('freesound_packs', (r) => this._packCard(r), 'Nessun pack'), { link: fsLink })}
      ${this._shelf('Pack da Internet Archive', this._featuredRow('archive_packs', (r) => this._packCard(r), 'Nessun pack'), { link: '<a href="#" data-provider="archive">Tutti →</a>' })}
      ${this._shelf('Nuovi suoni CC0', this._featuredRow('cc0_new', (r) => this._soundCard(r), 'Nessun suono'), { note: 'Pubblico dominio, nessuna attribuzione' })}
      ${this._shelf('Vetrina gratuita', `<div class="sc-grid">${this.meta.curated.map((c) => this._curatedCard(c)).join('')}</div>`,
    { note: 'pack royalty-free da siti senza API: si scaricano dalla pagina ufficiale' })}`;
  }

  // ---------------------------------------------------------------- store: results grid
  _renderGrid() {
    const packs = this.kind === 'packs';
    const store = packs ? this.packData : this.data;
    const active = this.meta.sources.filter((s) => this._activeSources().includes(s.id));
    const html = [];
    if (!active.length) html.push(`<div class="o-empty">${packs ? 'Nessuna fonte selezionata offre pack (Freesound, Internet Archive, ccMixter).' : 'Seleziona almeno una fonte.'}</div>`);
    for (const s of active) {
      const d = store[s.id];
      const rows = d?.results || [];
      const status = this.loading.has(s.id) && !rows.length ? `${SPIN} ricerca…` : !d ? '' : d.error ? `<span class="error">${esc(d.error)}</span>`
        : `${rows.length}${d.total ? ` di ${d.total.toLocaleString('it-IT')}` : ''}`;
      html.push(`<section class="shelf"><header class="shelf-head">${this._logo(s.id, 's')}<h3>${esc(s.label)}</h3><span class="hint">${status}</span><span class="spacer"></span>
        ${d?.needs_key ? '<wa-button size="xs" variant="brand" data-settings="1"><wa-icon slot="start" name="settings"></wa-icon>Inserisci API key</wa-button>' : ''}</header>
        ${rows.length ? `<div class="sc-grid">${rows.map((r) => (r.is_pack ? this._packCard(r) : this._soundCard(r))).join('')}</div>` : ''}
        ${d && !d.error && !rows.length && !this.loading.has(s.id) ? `<div class="o-none">Nessun risultato con questi filtri${d.fetched ? ` (${d.fetched} scartati dai filtri)` : ''}.</div>` : ''}
        ${d?.more ? `<wa-button size="s" appearance="filled-outlined" class="o-more" data-more="${s.id}" ${this.loading.has(s.id) ? 'loading disabled' : ''}>Carica altri</wa-button>` : ''}
      </section>`);
    }
    $('#store-view').innerHTML = html.join('');
  }

  // ---------------------------------------------------------------- store: pack page
  async openPack(uid) {
    const card = document.querySelector(`[data-pack="${CSS.escape(uid)}"]`);
    this._go({ name: 'pack', uid, title: card?.dataset.title || '' });
    this.packPage = { loading: true };
    this.queue = null;
    this.render();
    const res = await this.api.online_pack(uid, 1);
    if (this.view.uid !== uid) return;
    this.packPage = res;
    if (res.pack) this.view.title = res.pack.title;
    this.render();
  }

  async _packMore() {
    const pg = this.packPage;
    if (!pg?.more || pg.loadingMore) return;
    pg.loadingMore = true;
    this.render();
    const res = await this.api.online_pack(this.view.uid, pg.page + 1);
    pg.loadingMore = false;
    if (!res.error) { pg.files = pg.files.concat(res.files); pg.page = res.page; pg.more = res.more; }
    this.render();
  }

  _renderPack() {
    const pg = this.packPage;
    const box = $('#store-view');
    if (!pg || pg.loading) { box.innerHTML = `<div class="o-none">${SPIN} apertura del pack…</div>`; return; }
    if (pg.error) { box.innerHTML = `<div class="o-none error">${esc(pg.error)}</div>`; return; }
    const r = pg.pack;
    const i = r.info || {};
    const p = this.prov[r.source];
    const facts = [i.num_sounds ? nSounds(i.num_sounds) : `${pg.total} file`, i.downloads ? `${fmtNum(i.downloads)} download` : '',
      r.filesize ? fmtSize(r.filesize) : '', i.created ? new Date(i.created).getFullYear() : ''].filter(Boolean).join(' · ');
    const playable = pg.files.some((f) => f.preview_url);
    const archives = (pg.archives || []).map((a) => `<wa-button size="s" appearance="filled-outlined" data-dl-archive="${esc(a.url)}" data-pack="${esc(r.uid)}" title="Scarica l'archivio intero"><wa-icon slot="start" name="download"></wa-icon>${esc(a.name)} ${a.size ? '(' + fmtSize(a.size) + ')' : ''}</wa-button>`).join(' ');
    const fsNote = r.source === 'freesound' ? '<div class="hint">Da qui si scaricano le anteprime MP3 HQ; gli originali (WAV/AIFF) si scaricano dalla pagina Freesound.</div>' : '';
    box.innerHTML = `
      <div class="pk-head">
        ${this._cover(r, { icon: 'package', big: true })}
        <div class="pk-info">
          <div class="pk-kicker">${this._logo(r.source, 's')} Pack · ${esc(p?.name || r.source_label)}</div>
          <h2>${esc(r.title)}</h2>
          <div class="pk-author">Di <b>${esc(r.author || 'Autore sconosciuto')}</b></div>
          <div class="sc-meta">${r.license !== 'unknown' ? this._licBadge(r) : ''}<span>${esc(facts)}</span></div>
          ${i.description ? `<div class="pk-desc">${esc(i.description)}</div>` : ''}
          <div class="pk-actions">
            ${playable ? `<wa-button size="s" variant="brand" data-play-all><wa-icon slot="start" name="play"></wa-icon>Ascolta tutto</wa-button>` : ''}
            ${pg.files.length ? `<wa-button size="s" appearance="filled-outlined" data-dl-pack="${esc(r.uid)}"><wa-icon slot="start" name="download"></wa-icon>Scarica pack</wa-button>` : ''}
            ${archives}
            ${r.page_url ? `<wa-button size="s" appearance="filled-outlined" data-open="${esc(r.page_url)}"><wa-icon slot="start" name="external-link"></wa-icon>Apri su ${esc(p?.name || 'sito')}</wa-button>` : ''}
          </div>
          ${fsNote}
          ${r.suspect ? `<div class="warn">${svg('triangle-alert', 11)} Probabile libreria commerciale ricaricata: verifica i diritti prima dell'uso.</div>` : ''}
        </div>
      </div>
      ${this._shelf('Tracce', `<div class="o-rows pk-tracks">${pg.files.slice(0, 600).map((f) => this._row(f, false, true)).join('')}</div>
        ${pg.more ? `<wa-button size="s" appearance="filled-outlined" class="o-more" data-pack-more ${pg.loadingMore ? 'loading disabled' : ''}>Carica altre tracce</wa-button>` : ''}
        ${!pg.files.length ? '<div class="o-none">Nessun file audio consultabile: usa gli archivi o apri la pagina della fonte.</div>' : ''}`,
    { note: pg.total ? `${pg.files.length} di ${pg.total}` : '' })}
      ${pg.others?.length ? this._shelf(`Altri pack di ${esc(r.author)}`, this._rowOf(pg.others.map((o) => this._packCard(o)))) : ''}`;
  }

  async downloadPack(uid) {
    const res = await this.api.online_download_pack(uid);
    if (res.error) { alert(res.error); return; }
    this.inLibrary = res.in_library;
    $('#downloads').hidden = false;
    $('#downloads').classList.remove('collapsed');
    this._pollDownloads(true);
  }

  playAll() {
    const uids = (this.packPage?.files || []).filter((f) => f.preview_url).map((f) => f.uid);
    if (!uids.length) return;
    this.queue = { uids, i: 0 };
    this._playQueued();
  }

  _playQueued() {
    const uid = this.queue.uids[this.queue.i];
    const btn = document.querySelector(`#store-view [data-play="${CSS.escape(uid)}"]`);
    if (!btn) { this.queue = null; return; }
    this.togglePlay(uid, btn); // only a click on a play button clears the queue
    btn.scrollIntoView({ block: 'nearest' });
  }

  _queueNext(id) {
    const q = this.queue;
    if (!q || q.uids[q.i] !== id || this.view.name !== 'pack' || $('#online').hidden) return;
    q.i += 1;
    if (q.i >= q.uids.length) { this.queue = null; return; }
    this._playQueued();
  }

  // ---------------------------------------------------------------- store: provider page
  async openProvider(id) {
    const p = this.prov[id];
    if (!p) return;
    this._go({ name: 'provider', id });
    this.provData = { id, loading: p.kind === 'api' };
    this.render();
    if (p.kind !== 'api') return;
    const params = { ...this.params(), q: this.p.q.trim() };
    const [sounds, packs] = await Promise.all([
      this.api.online_more(id, params, 1),
      this.meta.pack_sources.includes(id) ? this.api.online_packs(id, params, 1) : null,
    ]);
    if (this.view.id !== id) return;
    this.provData = { id, sounds, packs };
    this.render();
  }

  _renderProvider() {
    const p = this.prov[this.view.id];
    const d = this.provData || {};
    const curated = this.meta.curated.filter((c) => c.provider === p.id);
    const lic = (p.licenses || []).map((k) => `<span class="lic lic-${LIC_CLASS[k] || (k === 'nc' ? 'restr' : 'free')}">${esc(this.meta.licenses[k] || (k === 'nc' ? 'Non commerciale' : k))}</span>`).join(' ');
    const section = (res, title, card) => {
      if (!res) return '';
      if (res.needs_key) return this._shelf(title, `<div class="sc-keycta">${this._logo('freesound', 'm')}<div><b>Serve una API key gratuita</b></div><wa-button size="s" variant="brand" data-settings="1">Inserisci API key</wa-button></div>`);
      if (res.error) return this._shelf(title, `<div class="o-none error">${esc(res.error)}</div>`);
      return this._shelf(title, res.results.length ? `<div class="sc-grid">${res.results.map(card).join('')}</div>` : '<div class="o-none">Nessun risultato.</div>');
    };
    let body = '';
    if (p.kind === 'curated') body = this._shelf('Pack in vetrina', `<div class="sc-grid">${curated.map((c) => this._curatedCard(c)).join('')}</div>`);
    else if (d.loading) body = `<div class="o-none">${SPIN} caricamento…</div>`;
    else {
      // packs already have their own shelf (Internet Archive only returns packs)
      const sounds = d.sounds && !d.sounds.error && !d.sounds.needs_key ? { ...d.sounds, results: d.sounds.results.filter((r) => !r.is_pack) } : d.sounds;
      body = section(d.packs, 'Pack', (r) => this._packCard(r))
        + (d.packs && sounds && !sounds.error && !sounds.results.length ? '' : section(sounds, 'Suoni', (r) => this._soundCard(r)));
    }
    $('#store-view').innerHTML = `
      <div class="pv-head" style="--pc:${p.color}">
        ${this._logo(p.id, 'xl')}
        <div class="pk-info">
          <div class="pk-kicker">${KIND_LABEL[p.kind]}</div>
          <h2>${esc(p.name)}</h2>
          <div class="pk-desc">${esc(p.description)}</div>
          <div class="sc-meta">${lic}</div>
          <div class="pk-actions"><wa-button size="s" appearance="filled-outlined" data-open="${esc(p.url)}"><wa-icon slot="start" name="external-link"></wa-icon>Visita il sito</wa-button>
          ${p.kind === 'api' && this.p.q.trim() ? `<span class="hint">Filtrato per «${esc(this.p.q.trim())}» e i filtri attivi</span>` : ''}</div>
        </div>
      </div>${body}`;
  }

  // ---------------------------------------------------------------- audio
  async togglePlay(uid, btn) {
    if (this.player.playing && this.player.id === uid) { this.player.stop(); return; }
    this.player.stop();
    this.pending = uid;
    btn.classList.add('busy');
    btn.innerHTML = SPIN;
    let buf = null;
    try { buf = await this.player.load(uid, (id) => this.api.online_preview(id)); } catch (err) { console.warn(err); }
    btn.classList.remove('busy');
    btn.innerHTML = svg('play', btn.classList.contains('sc-play') ? 16 : 12);
    if (!buf) { btn.innerHTML = svg('x', 12); btn.dataset.failed = '1'; btn.title = 'Anteprima non disponibile'; return; }
    if (this.pending === uid) this.player.play(uid, buf);
  }

  _syncPlayButtons(playing, id) {
    document.querySelectorAll('#online [data-play]').forEach((b) => {
      if (b.classList.contains('busy')) return;
      const on = playing && b.dataset.play === id;
      if (!b.dataset.failed) b.innerHTML = svg(on ? 'square' : 'play', b.classList.contains('sc-play') ? 16 : 12);
      b.closest('.o-row, .sc-card')?.classList.toggle('playing', on);
    });
  }

  // ---------------------------------------------------------------- downloads
  async download(uid, url = null) {
    const res = await this.api.online_download(uid, url);
    if (res.error) { alert(res.error); return; }
    this.inLibrary = res.in_library;
    $('#downloads').hidden = false;
    $('#downloads').classList.remove('collapsed');
    this._pollDownloads(true);
  }

  async _pollDownloads(force = false) {
    clearTimeout(this._dlT);
    const jobs = await this.api.downloads();
    const box = $('#downloads');
    if (jobs.length) box.hidden = false;
    const active = jobs.filter((j) => j.status === 'queued' || j.status === 'downloading').length;
    $('#dl-count').textContent = active ? `${active} in corso` : `${jobs.length} completati`;
    $('#dl-library').hidden = !jobs.length || this.inLibrary !== false;
    $('#dl-in-library').hidden = !jobs.length || this.inLibrary !== true;
    $('#downloads-list').innerHTML = jobs.slice().reverse().map((j) => {
      const pct = j.total ? Math.min(100, (100 * j.bytes) / j.total) : (j.status === 'done' ? 100 : 0);
      return `<div class="dl-row ${j.status}" ${j.path ? `data-path="${esc(j.path)}" title="Mostra in ${FILE_MANAGER}"` : ''}>
        <span class="dl-name">${esc(j.title)}</span><span class="dl-src">${esc(j.source)}</span>
        <span class="dl-state">${j.status === 'done' ? svg('check', 12) : j.status === 'error' ? `<span class="error" title="${esc(j.error)}">Errore</span>` : `${Math.round(pct)}%`}</span>
        <span class="dl-bar"><span style="width:${pct}%"></span></span></div>`;
    }).join('');
    if (active || force) this._dlT = setTimeout(() => this._pollDownloads(), 700);
  }

  // ---------------------------------------------------------------- settings
  _refreshAfterKey() {
    this._loadFeatured();
    if (this.view.name === 'results') this.search();
    else if (this.view.name === 'provider') { const id = this.view.id; this._back(); this.openProvider(id); }
  }

  _renderKeyHint() {
    document.querySelector('.nav-item[data-tab="online"]')?.classList.toggle('attention', !this.meta.settings.freesound_key_set);
  }

  /** Settings changed elsewhere (the Settings page): keep the copy used for searches in step. */
  onSettings(s) {
    if (!this.meta) return;
    const keyChanged = s.freesound_key_set !== this.meta.settings.freesound_key_set || s.freesound_key_hint !== this.meta.settings.freesound_key_hint;
    this.meta.settings = s;
    this._renderKeyHint();
    if (keyChanged) this._refreshAfterKey();
  }

  /** Store section of the Settings page: Freesound key, download folder, suspect packs. */
  async renderSettings(body) {
    const s = await this.api.get_settings();
    const keyHint = s.freesound_key_set ? `Impostata (${esc(s.freesound_key_hint)}). <a href="#" id="set-key-clear">Rimuovi chiave</a>` : 'Nessuna chiave: Freesound resta escluso dalle ricerche.';
    body.innerHTML =
      setRow('API key Freesound', `Gratuita: crea un account e <a href="#" id="set-getkey">richiedi una chiave</a>, poi incolla il valore "Client secret/Api key". Resta salvata solo su questo computer. ${keyHint}`,
        `<wa-input id="set-key" type="password" password-toggle size="s" autocomplete="off" label="API key" placeholder="${s.freesound_key_set ? 'Incolla per sostituirla' : 'Incolla qui la tua API key'}" style="width:260px"></wa-input>`)
      + setRow('Cartella dei download', 'Ogni file va in una sottocartella per fonte, con accanto un file .license.txt.',
        `<span class="set-path" title="${esc(s.download_dir)}">${esc(s.download_dir)}</span>
         <wa-button id="set-pick" size="s" appearance="filled-outlined"><wa-icon slot="start" name="folder-open"></wa-icon>Scegli…</wa-button>`)
      + setRow('Pack sospetti', 'Mostra anche i pack di librerie commerciali (es. Big Fish Audio, Sound Ideas, Loopmasters) ricaricati con una licenza libera che probabilmente non hanno.',
        `<wa-switch id="set-suspect" size="s" ${this.p.include_suspect ? 'checked' : ''}>Mostra</wa-switch>`);
    const done = (ns) => { this.meta ? this.onSettings(ns) : null; savedFlash(body); return this.renderSettings(body); };
    body.querySelector('#set-getkey').onclick = (e) => { e.preventDefault(); this.api.open_url('https://freesound.org/apiv2/apply'); };
    const clear = body.querySelector('#set-key-clear');
    if (clear) clear.onclick = async (e) => { e.preventDefault(); done(await this.api.set_setting('freesound_key', '')); };
    body.querySelector('#set-key').addEventListener('change', async (e) => {
      const key = (e.target.value || '').trim();
      if (key) done(await this.api.set_setting('freesound_key', key));
    });
    body.querySelector('#set-pick').onclick = async () => {
      const p = await this.api.pick_folder();
      if (p) done(await this.api.set_setting('download_dir', p));
    };
    body.querySelector('#set-suspect').addEventListener('change', (e) => {
      this.p.include_suspect = e.target.checked;
      try { localStorage.setItem(SUSPECT_KEY, e.target.checked ? '1' : '0'); } catch { /* private mode */ }
      if (this.started && this.view.name === 'results') this.search();
      savedFlash(body);
    });
  }
}
