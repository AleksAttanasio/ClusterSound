// "Online" screen: search free samples on Freesound, Openverse, Internet Archive and ccMixter.

const $ = (s, root = document) => root.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtDur = (s) => (s === null || s === undefined ? '' : s < 1 ? `${Math.round(s * 1000)} ms` : s < 60 ? `${s.toFixed(1)} s` : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`);
const fmtSize = (b) => (!b ? '' : b > 1e9 ? `${(b / 1e9).toFixed(1)} GB` : b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} kB`);

const SRC_ABBR = { freesound: 'FS', openverse: 'OV', archive: 'IA', ccmixter: 'CC' };
const LICENSE_FILTERS = [['cc0', 'CC0 / PD'], ['by', 'BY'], ['by-sa', 'BY-SA'], ['nc', 'Non commerciale'], ['nd', 'No derivate'], ['unknown', 'Non dichiarata']];
const LIC_CLASS = { cc0: 'free', pd: 'free', by: 'attr', 'by-sa': 'attr', 'by-nd': 'restr', 'by-nc': 'restr', 'by-nc-sa': 'restr', 'by-nc-nd': 'restr', 'sampling+': 'restr', unknown: 'unk' };
const PRESETS = [
  ['Kick', ['kick']], ['Snare', ['snare']], ['Hat', ['closed_hat', 'open_hat']], ['Clap', ['clap']],
  ['808', ['sub808']], ['Cymbal', ['ride', 'crash', 'cymbal_other']], ['Perc', ['perc_other', 'shaker', 'tambourine', 'hand_drum', 'cowbell']],
  ['Bass', ['bass']], ['Synth', ['synth', 'pad']], ['FX', ['riser', 'impact', 'downlifter']], ['Vocal', ['vocal', 'spoken']],
];
const SORTS = [['relevance', 'Rilevanza'], ['downloads', 'Più scaricati'], ['rating', 'Voto'], ['newest', 'Più recenti'], ['duration', 'Durata']];
const NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

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
      lossless: false, packs: 'all', include_suspect: false, sort: 'relevance',
    };
    this.groupBy = 'source';
    this.data = {};        // source -> response
    this.expanded = {};    // pack uid -> expand response
    this.collapsed = new Set();
    this.loading = new Set();
    this.searchSeq = 0;
    this.started = false;
    player.subscribe((playing, id) => this._syncPlayButtons(playing, id));
  }

  async show() {
    if (this.started) return;
    this.started = true;
    this.meta = await this.api.online_init();
    this.p.sources = new Set(this.meta.sources.map((s) => s.id));
    this._buildSidebar();
    this._bind();
    this._renderKeyHint();
    this.search();
    this._pollDownloads();
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
    if (!srcs.length) return '<span class="srv" title="Filtrato localmente sui risultati">locale</span>';
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
    const keyOpts = ['<option value="">Qualsiasi</option>']
      .concat(NOTES.flatMap((n) => [`<option>${n} major</option>`, `<option>${n} minor</option>`])).join('');
    const grp = (id, title) => `<div class="filter-group collapsed" data-group="${id}">
        <div class="fg-head"><span class="caret"></span><span>${title}</span><span class="fg-count" data-fg-count="${id}"></span></div>
        <div class="fg-body">`;
    sb.innerHTML = `
      <div class="filter-block">
        <div class="filter-title">Strumento <span>${'<span data-srv="instrument"></span>'} <a href="#" id="o-ins-clear">tutti</a></span></div>
        <div id="o-ins-summary" class="hint"></div>
        <div id="o-ins-list" class="o-ins-list">${cls.join('')}</div>
      </div>
      ${grp('src', 'Fonti e licenza')}
      <div class="filter-block">
        <div class="filter-title">Fonti</div>
        <div id="o-sources">${this.meta.sources.map((s) => `
          <label class="o-src"><input type="checkbox" data-src="${s.id}" checked>
          <span class="o-src-name">${esc(s.label)}</span><span class="o-src-status" data-src-status="${s.id}"></span></label>`).join('')}
        </div>
      </div>
      <div class="filter-block">
        <div class="filter-title">Licenza <span data-srv="license"></span></div>
        <div class="chips" id="o-lic">${LICENSE_FILTERS.map(([k, l]) => `<button class="chip" data-lic="${k}">${l}</button>`).join('')}</div>
        <label class="o-check"><input type="checkbox" id="o-commercial"> Solo uso commerciale (no NC/ND) <span data-srv="commercial"></span></label>
      </div></div></div>
      ${grp('char', 'Tipo e caratteristiche')}
      <div class="filter-block">
        <div class="filter-title">Tipo <span data-srv="type"></span></div>
        <div class="chips" id="o-types">${this.types.map((t) => `<button class="chip" data-type="${esc(t)}">${esc(t)}</button>`).join('')}</div>
      </div>
      <div class="filter-block">
        <div class="filter-title">Durata (s) <span data-srv="duration"></span></div>
        <div class="o-range"><input type="number" min="0" step="0.1" id="o-dmin" placeholder="min"><span>–</span><input type="number" min="0" step="0.1" id="o-dmax" placeholder="max"></div>
      </div>
      <div class="filter-block">
        <div class="filter-title">BPM <span data-srv="bpm"></span></div>
        <div class="o-range"><input type="number" min="40" max="250" id="o-bmin" placeholder="min"><span>–</span><input type="number" min="40" max="250" id="o-bmax" placeholder="max"></div>
      </div>
      <div class="filter-block">
        <div class="filter-title">Tonalità <span data-srv="key"></span></div>
        <select id="o-key" class="cls-select">${keyOpts}</select>
      </div></div></div>
      ${grp('fmt', 'Formato, pack e ordine')}
      <div class="filter-block">
        <div class="filter-title">Formato e pack <span data-srv="lossless"></span></div>
        <label class="o-check"><input type="checkbox" id="o-lossless"> Solo lossless (wav / aiff / flac)</label>
        <select id="o-packs" class="cls-select" style="margin-top:6px">
          <option value="all">File singoli e pack</option><option value="files">Solo file singoli</option><option value="packs">Solo pack</option>
        </select>
        <label class="o-check" title="Pack di librerie commerciali (es. Big Fish Audio, Sound Ideas, Loopmasters) ricaricati con una licenza libera che probabilmente non hanno"><input type="checkbox" id="o-suspect"> Mostra pack sospetti di materiale commerciale</label>
      </div>
      <div class="filter-block">
        <div class="filter-title">Ordina <span data-srv="sort"></span></div>
        <select id="o-sort" class="cls-select">${SORTS.map(([k, l]) => `<option value="${k}">${l}</option>`).join('')}</select>
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
      fmt: b(p.lossless) + b(p.packs !== 'all') + b(p.include_suspect) + b(p.sort !== 'relevance'),
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
    $('#online-presets').innerHTML = PRESETS.map(([l, ids]) => `<button class="chip" data-ins='${JSON.stringify(ids)}'>${l}</button>`).join('');
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
    bindVal('#o-suspect', 'include_suspect', 'change', (el) => el.checked);
    bindVal('#o-dmin', 'dur_min', 'input');
    bindVal('#o-dmax', 'dur_max', 'input');
    bindVal('#o-bmin', 'bpm_min', 'input');
    bindVal('#o-bmax', 'bpm_max', 'input');
    bindVal('#o-key', 'key');
    bindVal('#o-packs', 'packs');
    bindVal('#o-sort', 'sort');

    $('#online-q').addEventListener('keydown', (e) => { if (e.key === 'Enter') { this.p.q = e.target.value; this.search(); } });
    $('#online-go').onclick = () => { this.p.q = $('#online-q').value; this.search(); };
    $('#online-group').onclick = (e) => {
      const b = e.target.closest('[data-group]'); if (!b) return;
      this.groupBy = b.dataset.group;
      document.querySelectorAll('#online-group .seg-btn').forEach((x) => x.classList.toggle('active', x === b));
      this.render();
    };
    $('#online-results').onclick = (e) => this._onResultsClick(e);
    $('#btn-settings').onclick = () => this.openSettings();
    $('#dl-open').onclick = () => this.api.open_download_dir();
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
  async search() {
    const seq = ++this.searchSeq;
    this.data = {};
    this.expanded = {};
    for (const s of this.p.sources) this.loading.add(s);
    this.render();
    // one call per source so fast sources show up first
    const params = this.params();
    await Promise.all([...this.p.sources].map(async (s) => {
      const res = await this.api.online_more(s, params, 1);
      if (seq !== this.searchSeq) return;
      this.loading.delete(s);
      this.data[s] = res;
      this.render();
    }));
  }

  async more(source) {
    const cur = this.data[source];
    if (!cur) return;
    this.loading.add(source);
    this.render();
    const res = await this.api.online_more(source, this.params(), cur.page + 1);
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
    if (this.loading.has(s) && !d?.results?.length) return '<span class="spin"></span> ricerca…';
    if (!d) return '';
    if (d.error) return `<span class="error">${esc(d.error)}</span>`;
    const tot = d.total ? ` di ${d.total.toLocaleString('it-IT')}` : '';
    return `${d.results.length} risultati${tot}`;
  }

  render() {
    const box = $('#online-results');
    for (const s of this.meta.sources) {
      const el = document.querySelector(`[data-src-status="${s.id}"]`);
      if (el) {
        const d = this.data[s.id];
        el.innerHTML = !this.p.sources.has(s.id) ? '' : this.loading.has(s.id) ? '<span class="spin"></span>'
          : d?.error ? (d.needs_key ? '<span class="error">chiave</span>' : '<span class="error">errore</span>') : d ? d.results.length : '';
      }
    }
    const active = this.meta.sources.filter((s) => this.p.sources.has(s.id));
    if (!active.length) { box.innerHTML = '<div class="o-empty">Seleziona almeno una fonte.</div>'; return; }
    const html = [];
    if (this.groupBy === 'source') {
      for (const s of active) {
        const d = this.data[s.id];
        const open = !this.collapsed.has(s.id);
        const rows = d?.results || [];
        html.push(`<section class="o-section">
          <header class="o-sec-head" data-collapse="${s.id}"><span class="caret">${open ? '▾' : '▸'}</span>
            <span class="o-sec-title">${esc(s.label)}</span><span class="o-sec-status">${this._statusLine(s.id)}</span>
            ${d?.needs_key ? '<button class="btn small" data-settings="1">Inserisci API key</button>' : ''}</header>
          ${open ? `<div class="o-rows">${rows.map((r) => this._row(r)).join('')}</div>
            ${d?.more ? `<button class="btn o-more" data-more="${s.id}" ${this.loading.has(s.id) ? 'disabled' : ''}>${this.loading.has(s.id) ? 'Caricamento…' : 'Carica altri'}</button>` : ''}
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
        html.push(`<section class="o-section"><header class="o-sec-head" data-collapse="${key}"><span class="caret">${open ? '▾' : '▸'}</span>
          ${c ? `<span class="dot" style="background:${c.color}"></span>` : ''}<span class="o-sec-title">${esc(c ? c.label : 'Strumento non determinato / pack misti')}</span>
          <span class="o-sec-status">${rows.length}</span></header>
          ${open ? `<div class="o-rows">${rows.map((r) => this._row(r, true)).join('')}</div>` : ''}</section>`);
      }
      const loadingAny = active.some((s) => this.loading.has(s.id));
      if (loadingAny) html.push('<div class="o-none"><span class="spin"></span> ricerca in corso…</div>');
      const moreSrc = active.filter((s) => this.data[s.id]?.more);
      if (moreSrc.length && !loadingAny) html.push(`<button class="btn o-more" data-more-all="1">Carica altri da tutte le fonti</button>`);
    }
    box.innerHTML = html.join('');
    this._syncPlayButtons(this.player.playing, this.player.id);
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
      ${r.is_pack && !child ? `<button class="o-btn o-expand" data-expand="${esc(r.uid)}" title="Mostra i file del pack">${ex ? '▾' : '▸'}</button>`
        : `<button class="o-btn o-play" data-play="${esc(r.uid)}" ${playable ? '' : 'disabled'} title="Ascolta">▶</button>`}
      <span class="dot" style="background:${c ? c.color : 'transparent'};${c ? '' : 'box-shadow:0 0 0 1px #3a4152 inset'}" title="${esc(c ? c.label : 'strumento non determinato')}"></span>
      <div class="o-main">
        <div class="o-title" title="${esc(r.title)}">${esc(r.title)} ${packInfo} ${r.suspect ? '<span class="warn" title="Probabile libreria commerciale ricaricata: verifica i diritti">⚠ sospetto</span>' : ''}</div>
        <div class="o-sub">${sub}${tags ? ` <span class="tags">${tags}</span>` : ''}</div>
      </div>
      <div class="o-wave">${r.waveform_img ? `<img src="${esc(r.waveform_img)}" alt="" loading="lazy">` : ''}</div>
      ${this._licBadge(r)}
      <div class="num o-dur">${fmtDur(r.duration)}</div>
      <div class="o-meta" title="${esc(meta)}">${esc(meta)}</div>
      <div class="o-actions">
        ${playable && (r.preview_url || r.download_url) ? `<button class="o-btn" data-send="${esc(r.uid)}" title="Invia al Sequencer o al Drum Rack (file temporaneo, nessun download)">→</button>` : ''}
        ${r.download_url ? `<button class="o-btn" data-dl="${esc(r.uid)}" title="Scarica${r.download_note ? ' — ' + esc(r.download_note) : ''}${r.filesize ? ' (' + fmtSize(r.filesize) + ')' : ''}">⬇</button>` : ''}
        ${r.page_url ? `<button class="o-btn" data-open="${esc(r.page_url)}" title="Apri la pagina della fonte">↗</button>` : ''}
      </div>
    </div>${ex ? this._expansion(r, ex) : ''}`;
  }

  _expansion(r, ex) {
    if (ex.loading) return '<div class="o-children"><div class="o-none"><span class="spin"></span> lettura del pack…</div></div>';
    if (ex.error) return `<div class="o-children"><div class="o-none error">${esc(ex.error)}</div></div>`;
    const archives = (ex.archives || []).map((a) => `<button class="btn small" data-dl-archive="${esc(a.url)}" data-pack="${esc(r.uid)}" title="Scarica l'archivio intero">⬇ ${esc(a.name)} ${a.size ? '(' + fmtSize(a.size) + ')' : ''}</button>`).join(' ');
    const filtered = ex.files.length < ex.total;
    return `<div class="o-children">
      <div class="o-pack-bar">${ex.total} file nel pack${filtered ? ` · ${ex.files.length} corrispondono ai filtri <a href="#" data-expand-all="${esc(r.uid)}">mostra tutti</a>` : ''} ${archives}</div>
      ${ex.files.slice(0, 400).map((f) => this._row(f, false, true)).join('')}
      ${ex.files.length > 400 ? `<div class="o-none">… altri ${ex.files.length - 400} file: restringi i filtri</div>` : ''}
      ${!ex.files.length && !ex.archives?.length ? '<div class="o-none">Nessun file audio consultabile (archivio RAR/7z?): apri la pagina della fonte.</div>' : ''}
    </div>`;
  }

  async _onResultsClick(e) {
    const t = e.target.closest('button, a, header');
    if (!t) return;
    if (t.dataset.play) return this.togglePlay(t.dataset.play, t);
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
    if (t.dataset.settings) return this.openSettings();
    if (t.dataset.tag) { $('#online-q').value = t.dataset.tag; this.p.q = t.dataset.tag; return this.search(); }
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

  // ---------------------------------------------------------------- audio
  async togglePlay(uid, btn) {
    if (this.player.playing && this.player.id === uid) { this.player.stop(); return; }
    this.player.stop();
    this.pending = uid;
    btn.classList.add('busy');
    btn.innerHTML = '<span class="spin"></span>';
    let buf = null;
    try { buf = await this.player.load(uid, (id) => this.api.online_preview(id)); } catch (err) { console.warn(err); }
    btn.classList.remove('busy');
    btn.textContent = '▶';
    if (!buf) { btn.textContent = '✕'; btn.title = 'Anteprima non disponibile'; return; }
    if (this.pending === uid) this.player.play(uid, buf);
  }

  _syncPlayButtons(playing, id) {
    document.querySelectorAll('#online-results [data-play]').forEach((b) => {
      if (b.classList.contains('busy')) return;
      const on = playing && b.dataset.play === id;
      if (b.textContent !== '✕') b.textContent = on ? '■' : '▶';
      b.closest('.o-row')?.classList.toggle('playing', on);
    });
  }

  // ---------------------------------------------------------------- downloads
  async download(uid, url = null) {
    const res = await this.api.online_download(uid, url);
    if (res.error) { alert(res.error); return; }
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
    $('#downloads-list').innerHTML = jobs.slice().reverse().map((j) => {
      const pct = j.total ? Math.min(100, (100 * j.bytes) / j.total) : (j.status === 'done' ? 100 : 0);
      return `<div class="dl-row ${j.status}" ${j.path ? `data-path="${esc(j.path)}" title="Mostra nel Finder"` : ''}>
        <span class="dl-name">${esc(j.title)}</span><span class="dl-src">${esc(j.source)}</span>
        <span class="dl-state">${j.status === 'done' ? '✓' : j.status === 'error' ? `<span class="error" title="${esc(j.error)}">errore</span>` : `${Math.round(pct)}%`}</span>
        <span class="dl-bar"><span style="width:${pct}%"></span></span></div>`;
    }).join('');
    if (active || force) this._dlT = setTimeout(() => this._pollDownloads(), 700);
  }

  // ---------------------------------------------------------------- settings
  _renderKeyHint() {
    const s = this.meta.settings;
    $('#btn-settings').classList.toggle('attention', !s.freesound_key_set);
  }

  openSettings() {
    const s = this.meta.settings;
    const m = $('#settings');
    m.hidden = false;
    $('#set-key').value = '';
    $('#set-key').placeholder = s.freesound_key_set ? `impostata (${s.freesound_key_hint}) — lascia vuoto per mantenerla` : 'incolla qui la tua API key';
    $('#set-dir').value = s.download_dir;
    $('#set-cache').value = s.cache_mb;
    $('#set-cache-used').textContent = `In uso: ${s.cache_used_mb} MB. I file oltre il limite vengono eliminati partendo dai meno usati; quelli del pattern aperto restano.`;
    $('#set-cache-clear').onclick = async (e) => {
      e.preventDefault();
      this.meta.settings = await this.api.clear_cache();
      $('#set-cache-used').textContent = `In uso: ${this.meta.settings.cache_used_mb} MB`;
    };
    $('#set-cancel').onclick = () => { m.hidden = true; };
    $('#set-getkey').onclick = (e) => { e.preventDefault(); this.api.open_url('https://freesound.org/apiv2/apply'); };
    $('#set-pick').onclick = async () => { const p = await this.api.pick_folder(); if (p) $('#set-dir').value = p; };
    $('#set-clear').onclick = async (e) => { e.preventDefault(); this.meta.settings = await this.api.set_setting('freesound_key', ''); m.hidden = true; this._renderKeyHint(); this.search(); };
    $('#set-save').onclick = async () => {
      const key = $('#set-key').value.trim();
      if (key) this.meta.settings = await this.api.set_setting('freesound_key', key);
      this.meta.settings = await this.api.set_setting('download_dir', $('#set-dir').value.trim());
      this.meta.settings = await this.api.set_setting('cache_mb', $('#set-cache').value);
      m.hidden = true;
      this._renderKeyHint();
      if (key) this.search();
    };
  }
}
