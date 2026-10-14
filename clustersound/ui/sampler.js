// "Recorder" screen: record what the computer sends to one or more output devices (one file each, several formats),
// then open a recording below to mark regions on its waveform (by hand or on transients) and export them as
// samples. Opening own files and openly licensed links is still here, hidden while show_sources is false.
import { btn, iconBtn, slider, check, num, select, seg, text, setPlayButton, icon, openDialog, FILE_MANAGER } from './kit.js';
import { toast, showPopover } from './sendmenu.js';
import { liveToast } from './live.js';
import { settingsLink, setRow, savedFlash } from './settings.js';
import { t } from './i18n.js';

const $ = (s, root = document) => root.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LS_KEY = 'clustersound.sampler';
const EDGE_PX = 6;         // grab distance of a region edge
const MIN_VIEW_S = 0.02;   // deepest zoom
// English source text: t() where shown
const ORIGIN_LABEL = { file: 'File', link: 'Link', capture: 'Recording' };
const CAPTURE_NOTE = 'Recording for personal use (private copy): nothing is decrypted or bypassed, and apps '
  + 'that protect their stream record silence. To publish a track that contains the sample you need the rights.';
const mb = (b) => (b >= 1 << 20 ? `${(b / (1 << 20)).toFixed(1)} MB` : `${Math.round(b / 1024)} KB`);
const clock = (sec) => `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, '0')}`;
const fmt = (sec) => {
  if (!isFinite(sec)) return '–';
  const m = Math.floor(sec / 60), s = sec - m * 60;
  return m ? `${m}:${s.toFixed(2).padStart(5, '0')}` : `${s.toFixed(3)} s`;
};

export class SamplerEditor {
  constructor({ api, player, onSendToRack, classes = [] }) {
    this.api = api;
    this.classes = classes;   // library classes, for the labels in "From the library…"
    this.onSendToRack = onSendToRack; // (refs) -> loads them on the Drum Rack
    this.player = player;
    this.ready = null;
    this.session = null;      // describe() of the open audio
    this.token = 0;           // bumps when a new source opens
    this.audioRev = 0;        // bumps when fades / normalisation change (player cache keys)
    this.maxS = 30;
    this.view = { start: 0, end: 1 };
    this.overview = null;     // peaks of the whole source
    this.detail = null;       // peaks of the current view
    this.regions = [];        // {start, end, name, on, file?: {key, path} of its last export}
    this.sel = -1;
    this.drag = null;
    this.playing = null;      // {start, end} being played
    this.rec = { devices: [], formats: {}, running: false, tracks: [], recordings: [] };
    this.recFmt = null;       // {format, quality, rate, channels}
    this.recDir = '';
    this.showSources = false;
    this.linkFiles = [];
    this.stems = null;        // stems_status(): extra installed, model ready, last job
    this.enh = null;          // enhance_status(): models (installed, downloaded), last "Enhance" job
    this.opts = { fade_in_ms: 1, fade_out_ms: 10, normalize: false, sensitivity: 0.5, devices: null };
    try { Object.assign(this.opts, JSON.parse(localStorage.getItem(LS_KEY) || '{}')); } catch { /* private mode */ }
    this.player.subscribe((on) => { if (!on) { this.playing = null; this._syncPlay(); } });
  }

  ensure() {
    if (!this.ready) this.ready = this._init();
    return this.ready;
  }

  async _init() {
    const init = await this.api.sampler_init();
    this.supported = init.supported;
    this.maxS = init.max_seconds;
    this.showSources = !!init.show_sources;
    this.rec = init.recorder;
    this.recFmt = init.settings.recorder_format;
    this.recDir = init.settings.recorder_dir;
    this._buildShell();
    if (this.rec.running) this._pollRec();
    this.stems = await this.api.stems_status();
    this._renderStems();
    if (this._stemsBusy()) this._pollStems();
    this.enh = await this.api.enhance_status();
    this._renderEnh();
    if (this._enhBusy()) this._pollEnh();
    if (init.session) await this._opened(init);
  }

  async show() {
    await this.ensure();
    this._resize();
  }

  hide() { this.player.stop(); } // a recording keeps going (and polling) on the other tabs

  _persist() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(this.opts)); } catch { /* private mode */ }
  }

  // ---------------------------------------------------------------- shell
  _buildShell() {
    const root = $('#sampler');
    const o = this.opts;
    root.innerHTML = `
      <aside class="sidebar sp-side">
        <div class="filter-block">
          <div class="filter-title">${t('Open audio')}</div>
          <div class="sp-open-row">
            ${btn(t('Open file…'), { icon: 'folder-open', id: 'sp-open-file', title: t('An audio file on the computer (wav, aif, flac, mp3, ogg…)') })}
            ${btn(t('From the library…'), { icon: 'list', id: 'sp-open-lib', title: t('A sample or a loop of the ClusterSound library, by folder or by name') })}
          </div>
          <div class="hint">${t('Or drag an audio file from {app} onto the waveform.', { app: FILE_MANAGER })}</div>
        </div>
        ${this.showSources ? `<div class="filter-block">
          <div class="filter-title">${t('Source')}</div>
          ${btn(t('Open audio file…'), { icon: 'folder-open', cls: 'sp-wide', id: 'sp-open' })}
          <div class="sp-link">
            <wa-input id="sp-url" size="s" placeholder="${t('Paste a link (Freesound, Archive…)')}" autocomplete="off" with-clear></wa-input>
            ${btn(t('Open'), { id: 'sp-url-go' })}
          </div>
          <div class="hint">${t('Accepted links: {sites}. YouTube, Spotify, Tidal and the other streaming services do not allow downloading the audio.', { sites: esc(this.supported) })}</div>
          <div id="sp-files" class="sp-files" hidden></div>
        </div>` : ''}
        <div class="filter-block rc-block">
          <div class="filter-title rc-title">${t('Record the audio output')} ${settingsLink('sampler', t('Outputs, format and folder'))}</div>
          <div id="rc-devices" class="rc-devices"></div>
          <div class="rc-folder"><span class="rc-fmt-sum" id="rc-fmt-sum"></span><span class="rc-path" id="rc-path"></span>
            ${iconBtn('folder-open', t('Show the folder in {app}', { app: FILE_MANAGER }), { size: 'xs', id: 'rc-reveal' })}</div>
          <div class="rc-go">
            ${btn(t('Record'), { variant: 'brand', icon: 'circle', id: 'rc-rec', cls: 'rc-rec' })}
            <span class="rc-clock" id="rc-clock">0:00</span>
          </div>
          <div class="hint" id="rc-info"></div>
          <div class="hint sp-note">${esc(t(CAPTURE_NOTE))}</div>
        </div>
        <div class="filter-block">
          <div class="filter-title">${t('Recordings')}</div>
          <div id="rc-list" class="rc-list"></div>
        </div>
        <div class="filter-block">
          <div class="filter-title">Stem</div>
          <div id="st-box" class="rc-list"></div>
        </div>
        <div class="filter-block">
          <div class="filter-title en-title">${icon('sparkles')} ${t('Enhance')}</div>
          <div id="en-box" class="rc-list"></div>
        </div>
        <div class="filter-block">
          <div class="filter-title rc-title">${t('Extracted samples')} ${settingsLink('sampler', t('Fades and normalisation'))}</div>
          <div class="hint" id="sp-opts-sum"></div>
          <div class="hint" id="sp-max-hint"></div>
        </div>
      </aside>
      <main class="sp-main">
        <div class="sp-info" id="sp-info"></div>
        <div class="sp-toolbar">
          ${btn('Play', { variant: 'brand', icon: 'play', id: 'sp-play' })}
          ${iconBtn('maximize-2', t('Show all'), { id: 'sp-fit' })}
          <span class="sp-sep"></span>
          ${btn(t('Slice on transients'), { icon: 'sparkles', id: 'sp-slice' })}
          <span class="sp-sens" title="${t('Sensitivity: higher = more slices')}">
            <span class="hint">${t('Sensitivity')}</span>${slider(0, 1, 0.05, o.sensitivity, { id: 'sp-sens', label: t('Sensitivity') })}
          </span>
          <span class="sp-sep"></span>
          ${btn(t('Extract stems'), { icon: 'audio-lines', id: 'sp-stems', title: t('Separates drums, bass, guitar, vocals and the rest, on this computer') })}
          ${btn(t('Enhance'), { icon: 'sparkles', id: 'sp-enh', cls: 'cs-ai', title: t('AI restoration of the selected region (or of all the audio): high frequencies and compression artefacts, on this computer') })}
          <span class="spacer"></span>
          <span class="hint" id="sp-view-info"></span>
        </div>
        <div class="sp-wave-wrap" id="sp-wave-wrap">
          <canvas id="sp-wave" class="sp-wave"></canvas>
          <canvas id="sp-overview" class="sp-overview"></canvas>
          <div class="empty sp-empty" id="sp-empty">
            <div class="empty-title">${t('Record the audio output, or open a file')}</div>
            <div class="empty-sub">${t('Choose one or more outputs and the format, then press Record: every output goes into a file. You can also open an audio file or a library sample, or drag it here from {app}. Open a recording to cut samples: drag on the waveform to create a region (max {max}) or use «Slice on transients». Wheel: zoom · Shift+wheel: scroll.', { app: FILE_MANAGER, max: '<span class="sp-max"></span>' })}</div>
          </div>
        </div>
        <div class="sp-regions-head">
          <span class="filter-title">${t('Regions')} <span id="sp-count"></span></span>
          <span class="spacer"></span>
          ${btn(t('Clear'), { icon: 'trash-2', id: 'sp-clear' })}
          ${btn(t('Send to Live'), { icon: 'music', id: 'sp-live', title: t('Puts the selected region, or with no selection all the open audio, on a new audio track in Live (needs the ClusterSound device in the set). The file also stays in the Live browser: User Library › ClusterSound › Audio') })}
          ${btn(t('To the Drum Rack'), { icon: 'layout-grid', id: 'sp-rack', title: t('Exports the selected regions and loads them on the free pads of the Drum Rack, to play them') })}
          ${btn(t('Export selected'), { variant: 'brand', icon: 'file-down', id: 'sp-export' })}
        </div>
        <div class="sp-regions" id="sp-regions"></div>
      </main>`;
    this.cv = $('#sp-wave');
    this.ov = $('#sp-overview');
    this._bind();
    this._renderMax();
    this.renderInfo();
    this.renderRegions();
    this._renderRecorder();
    new ResizeObserver(() => this._resize()).observe($('#sp-wave-wrap'));
  }

  _bind() {
    this._bindOpen();
    this._bindRecorder();
    if (this.showSources) this._bindSources();
    this._bindRest();
  }

  _bindSources() {
    $('#sp-open').onclick = async () => this._opened(await this.api.sampler_open_file(null));
    const go = async () => {
      const url = ($('#sp-url').value || '').trim();
      if (!url) return;
      const b = $('#sp-url-go');
      b.loading = true;
      const r = await this.api.sampler_link(url);
      b.loading = false;
      if (r.error) return this._error(r.error);
      if (r.files) return this._showFiles(r.files);
      this._opened(r);
    };
    $('#sp-url-go').onclick = go;
    $('#sp-url').addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
    $('#sp-files').onclick = async (e) => {
      const row = e.target.closest('[data-uid]');
      if (!row) return;
      row.classList.add('busy');
      const r = await this.api.sampler_open_result(row.dataset.uid);
      row.classList.remove('busy');
      this._opened(r);
    };
  }

  _bindOpen() {
    $('#sp-open-file').onclick = async () => this._opened(await this.api.sampler_open_file(null));
    $('#sp-open-lib').onclick = () => this.openLibrary();
    // the path of a file dropped from the Finder / File Explorer comes from Python (pywebview): here only the highlight
    const wrap = $('#sp-wave-wrap');
    let depth = 0;
    const isFile = (e) => [...(e.dataTransfer?.types || [])].includes('Files');
    wrap.addEventListener('dragenter', (e) => { if (isFile(e)) { depth++; wrap.classList.add('sp-drop'); } });
    wrap.addEventListener('dragleave', () => { if (--depth <= 0) { depth = 0; wrap.classList.remove('sp-drop'); } });
    wrap.addEventListener('drop', () => { depth = 0; wrap.classList.remove('sp-drop'); });
  }

  // called by Python after an audio file was dropped from the Finder / File Explorer
  dropped(r) {
    $('#sp-wave-wrap')?.classList.remove('sp-drop');
    if (!r?.error) toast(t('Opened: {title}', { title: r.session.title }));
    this._opened(r);
  }

  async openLibrary(folder = this.opts.libFolder || '', q = '') {
    const r = await this.api.sampler_library_browse(folder, q);
    if (r.error) {
      if (folder) { this.opts.libFolder = ''; this._persist(); return this.openLibrary('', q); }
      return this._error(r.error);
    }
    this.opts.libFolder = r.folder;
    this._persist();
    const label = (f) => this.classes[f.cls]?.label || '';
    const rows = r.folders.map((f) => `<button class="sp-lib-row" data-folder="${esc(f.path)}">
        ${icon('folder-open')}<span class="sp-lib-name">${esc(f.name)}</span><span class="hint">${t('{n} files', { n: f.count })}</span></button>`)
      .concat(r.files.map((f) => `<button class="sp-lib-row" data-id="${f.id}" title="${esc(f.rel)}">
        ${icon('music')}<span class="sp-lib-name">${esc(r.q ? f.rel : f.name)}</span>
        <span class="hint">${esc(label(f))}</span><span class="hint">${fmt(f.dur)}</span></button>`));
    const crumbs = r.crumbs.map((c, i) => i === r.crumbs.length - 1 && !r.q ? `<b>${esc(c.name)}</b>`
      : `<a href="#" data-folder="${esc(c.path)}">${esc(c.name)}</a>`).join(' › ');
    const body = `<div class="sp-lib">
        ${text(r.q, { id: 'sp-lib-q', placeholder: t('Search by name or folder in the whole library'), 'with-clear': true })}
        <div class="sp-lib-crumbs">${crumbs}${r.q ? ` › <b>${t('Search')}</b>` : ''}</div>
        <div class="sp-lib-rows">${rows.join('') || `<div class="hint">${t('No audio files here.')}</div>`}</div>
        ${r.more ? `<div class="hint">${t('… and {n} more: refine the search.', { n: r.more })}</div>` : ''}
      </div>`;
    const dlg = openDialog('sp-lib-dlg', { label: t('Open from the library'), body, width: '640px' });
    const qEl = dlg.querySelector('#sp-lib-q');
    let timer;
    qEl.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const v = qEl.value || '';
        if (v.trim().length === 1) return;
        await this.openLibrary(r.folder, v);
        const again = document.querySelector('#sp-lib-q');
        again?.focus();
      }, 250);
    });
    if (r.q) setTimeout(() => qEl.focus(), 0);
    dlg.querySelector('.sp-lib').onclick = async (e) => {
      const f = e.target.closest('[data-folder]');
      if (f) { e.preventDefault(); return this.openLibrary(f.dataset.folder, ''); }
      const it = e.target.closest('[data-id]');
      if (!it) return;
      it.classList.add('busy');
      const out = await this.api.sampler_open_library(+it.dataset.id);
      if (out.error) { it.classList.remove('busy'); return this._error(out.error); }
      dlg.close();
      this._opened(out);
    };
  }

  _bindRest() {
    $('#sp-sens').addEventListener('change', (e) => { this.opts.sensitivity = +e.target.value; this._persist(); });
    $('#sp-play').onclick = () => this.togglePlay();
    $('#sp-fit').onclick = () => this.setView(0, this.duration);
    $('#sp-slice').onclick = () => this.autoSlice();
    $('#sp-clear').onclick = () => { this.regions = []; this.sel = -1; this.renderRegions(); this.draw(); };
    $('#sp-export').onclick = () => this.export();
    $('#sp-rack').onclick = () => this.sendToRack();
    $('#sp-live').onclick = () => this.sendToLive();
    $('#sp-stems').onclick = (e) => this._stemsMenu(e.currentTarget);
    $('#st-box').addEventListener('click', (e) => this._stemsClick(e));
    $('#sp-enh').onclick = (e) => this._enhMenu(e.currentTarget);
    $('#en-box').addEventListener('click', (e) => this._enhClick(e));
    $('#sp-regions').addEventListener('click', (e) => this._regionClick(e));
    $('#sp-regions').addEventListener('change', (e) => {
      const row = e.target.closest('[data-i]');
      if (!row) return;
      const r = this.regions[+row.dataset.i];
      if (e.target.matches('wa-checkbox')) r.on = e.target.checked;
      if (e.target.matches('wa-input')) r.name = e.target.value;
      this._renderCount();
    });
    // waveform
    this.cv.addEventListener('wheel', (e) => this._wheel(e), { passive: false });
    this.cv.addEventListener('pointerdown', (e) => this._down(e));
    this.cv.addEventListener('pointermove', (e) => this._move(e));
    this.cv.addEventListener('pointerup', (e) => this._up(e));
    this.cv.addEventListener('dblclick', (e) => {
      const i = this._regionAt(this._time(e));
      if (i >= 0) this.playRegion(i);
    });
    this.ov.addEventListener('pointerdown', (e) => {
      const seek = (ev) => {
        const r = this.ov.getBoundingClientRect();
        const len = this.view.end - this.view.start;
        const c = (ev.clientX - r.left) / r.width * this.duration;
        this.setView(c - len / 2, c + len / 2);
      };
      this.ov.setPointerCapture(e.pointerId);
      seek(e);
      this.ov.onpointermove = seek;
      this.ov.onpointerup = () => { this.ov.onpointermove = null; };
    });
  }

  onKey(e) {
    if (!this.session) return false;
    if (e.key === ' ') { this.togglePlay(); return true; }
    if ((e.key === 'Delete' || e.key === 'Backspace') && this.sel >= 0) { this.removeRegion(this.sel); return true; }
    if (e.key === 'Escape' && this.sel >= 0) { this.sel = -1; this.renderRegions(); this.draw(); return true; }
    if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && this.regions.length) {
      const i = Math.max(0, Math.min(this.regions.length - 1, this.sel + (e.key === 'ArrowDown' ? 1 : -1)));
      this.playRegion(i);
      return true;
    }
    return false;
  }

  _error(msg) {
    toast(msg.length > 140 ? msg.slice(0, 137) + '…' : msg);
    const info = $('#sp-info');
    if (info && msg.length > 140) info.innerHTML = `<div class="sp-error">${icon('triangle-alert')} ${esc(msg)}</div>`;
  }

  // ---------------------------------------------------------------- sources
  _showFiles(files) {
    this.linkFiles = files;
    const box = $('#sp-files');
    box.hidden = false;
    const first = files[0];
    box.innerHTML = `<div class="hint">${esc(first.info?.pack_title || first.source_label)} · ${t('{n} files', { n: files.length })}
      · ${t('licence {license}. Choose which one to open:', { license: esc(first.license_label) })}</div>`
      + files.map((f) => `<button class="sp-file" data-uid="${esc(f.uid)}" title="${esc(f.path || f.title)}">
          <span class="sp-file-name">${esc((f.path || f.title).split('/').pop())}</span>
          <span class="hint">${f.duration ? fmt(f.duration) : ''}</span></button>`).join('');
  }

  async _opened(r) {
    if (!r || r.cancelled) return;
    if (r.error) return this._error(r.error);
    this.player.stop();
    this.session = r.session;
    this.maxS = r.max_seconds || this.maxS;
    this.token += 1;
    this.regions = [];
    this.sel = -1;
    this.overview = await this.api.sampler_view(0, null, 2000);
    this.detail = null;
    this._renderMax();
    this.renderInfo();
    this.renderRegions();
    this.setView(0, this.duration);
  }

  get duration() { return this.session?.duration || 0; }

  renderInfo() {
    const box = $('#sp-info');
    $('#sp-empty').hidden = !!this.session;
    if (!this.session) { box.innerHTML = ''; return; }
    const s = this.session, src = s.source;
    const lic = src ? `<span class="sp-badge ${src.commercial_ok ? 'ok' : 'warn'}" title="${src.commercial_ok
      ? t('Usable in commercial productions too (respecting the attribution, if required)')
      : t('Commercial use not allowed or to be checked')}">${esc(src.license_label)}</span>` : '';
    const who = src ? ` · ${esc(src.author || t('unknown author'))} · ${esc(src.source_label)}` : '';
    const page = src?.page_url ? ` <a href="#" data-url="${esc(src.page_url)}" class="sp-page">${icon('external-link')} ${t('page')}</a>` : '';
    box.innerHTML = `<span class="sp-badge">${ORIGIN_LABEL[s.origin] ? t(ORIGIN_LABEL[s.origin]) : s.origin}</span>${lic}
      <b class="sp-title" title="${esc(s.path || s.title)}">${esc(s.title)}</b>
      <span class="hint">${fmt(s.duration)} · ${s.sr} Hz · ${s.channels === 1 ? 'mono' : 'stereo'}${who}${
        s.truncated ? ` · ${t('only the first 20 minutes opened')}` : ''}</span>${page}
      ${s.origin === 'capture' ? `<span class="hint sp-note-inline">${icon('triangle-alert')} ${t('personal use only')}</span>` : ''}
      ${src?.suspect ? `<span class="sp-badge warn" title="${t('It looks like commercial material re-uploaded with a free licence')}">${t('Check the rights')}</span>` : ''}`;
    const a = box.querySelector('.sp-page');
    if (a) a.onclick = (e) => { e.preventDefault(); this.api.open_url(a.dataset.url); };
  }

  _renderOptsSummary() {
    const o = this.opts, el = $('#sp-opts-sum');
    if (el) el.textContent = `Fade ${o.fade_in_ms} ms in · ${o.fade_out_ms} ms out${o.normalize ? ` · ${t('normalised to −0.3 dBFS')}` : ''}.`;
  }

  _renderMax() {
    document.querySelectorAll('#sampler .sp-max').forEach((el) => { el.textContent = `${this.maxS} s`; });
    const h = $('#sp-max-hint');
    if (h) h.textContent = t('Every sample lasts at most {max} s. They go into ~/Music/ClusterSound Samples, with the provenance of the recording next to them.', { max: this.maxS });
  }

  // ---------------------------------------------------------------- recorder
  _bindRecorder() {
    $('#rc-reveal').onclick = async (e) => {
      e.preventDefault();
      if (!(await this.api.reveal_path(this.recDir))) toast(t('The folder will be created by the first recording'));
    };
    $('#rc-rec').onclick = () => this.toggleRecording();
    $('#rc-list').addEventListener('click', async (e) => {
      const row = e.target.closest('[data-path]');
      const act = e.target.closest('[data-act]')?.dataset.act;
      if (!row || !act) return;
      if (act === 'reveal') return this.api.reveal_path(row.dataset.path);
      this._opened(await this.api.recorder_open(row.dataset.path));
    });
  }

  // The selected region, or all the open audio, onto a new audio track in Live (through the M4L device).
  async sendToLive() {
    if (!this.session) return this._error(t('Open a recording first'));
    const r = this.regions[this.sel];
    const b = $('#sp-live');
    b.loading = true;
    toast(r ? t('Sending the region to Live…') : t('Sending the audio to Live…'));
    const out = await this.api.sampler_send_to_live(r ? r.start : null, r ? r.end : null, this.opts);
    b.loading = false;
    if (out.file && !out.running) return toast(t('Live bridge not active: the file is in the Live browser anyway, User Library › ClusterSound › Audio'));
    liveToast(out);
  }

  // ---------------------------------------------------------------- stems
  _stemsBusy() { return ['running', 'downloading'].includes(this.stems?.job?.state); }

  _stemsMenu(anchor) {
    const st = this.stems;
    if (!this.session) return this._error(t('Open a recording first'));
    const r = this.regions[this.sel];
    let body;
    if (!st?.installed) {
      body = `<div class="hint">${t('The separation runs on this computer with Demucs (PyTorch), an extension to install once:')}</div>
        <code class="st-code">${esc(st?.install_hint || '')}</code>`;
    } else if (!st.model_ready) {
      body = `<div class="hint">${t('It needs the Demucs model (~{mb} MB), downloaded only once. After that the separation works offline: the audio never leaves the computer.', { mb: st.model_mb })}</div>
        <div class="pop-actions">${btn(t('Download the model'), { variant: 'brand', icon: 'download', 'data-go': 'download' })}</div>`;
    } else {
      const choosable = st.stems.filter((x) => x.choosable);
      const keys = new Set(this.opts.stemKeys || choosable.map((x) => x.key));
      const scope = r && this.opts.stemScope === 'region' ? 'region' : 'all';
      body = `<div class="hint">${t('One WAV file per stem, on this computer, with no external services.')}</div>
        <div class="st-keys">${choosable.map((x) => check(esc(x.label), keys.has(x.key), { 'data-key': x.key })).join('')}</div>
        <div class="hint">${t('+ <b>Other</b>: everything you did not choose, so nothing is lost.')}</div>
        ${seg([['all', t('Whole recording')], ['region', t('Selected region'), { disabled: !r, title: r ? `${fmt(r.start)} – ${fmt(r.end)}` : t('Select a region') }]],
          scope, { 'data-o': 'scope', cls: 'st-scope' })}
        <div class="pop-actions">${btn(t('Extract'), { variant: 'brand', icon: 'audio-lines', 'data-go': 'extract', disabled: !keys.size })}</div>`;
    }
    const pop = showPopover(anchor, `<div class="pop-title">${icon('audio-lines')} ${t('Extract stems')}</div>${body}`);
    const picked = () => [...pop.querySelectorAll('[data-key]')].filter((c) => c.checked).map((c) => c.dataset.key);
    pop.querySelector('.st-keys')?.addEventListener('change', () => {
      pop.querySelector('[data-go=extract]').disabled = !picked().length;
    });
    pop.querySelectorAll('[data-go]').forEach((b) => {
      b.onclick = async () => {
        if (b.disabled) return;
        const go = b.dataset.go;
        let out;
        if (go === 'download') {
          pop.close();
          out = await this.api.stems_download_model();
        } else {
          const keys = picked(), scope = pop.querySelector('[data-o=scope]').value === 'region' && r ? 'region' : 'all';
          Object.assign(this.opts, { stemKeys: keys, stemScope: scope });
          this._persist();
          pop.close();
          out = await this.api.stems_start(scope, scope === 'region' ? r.start : null, scope === 'region' ? r.end : null, keys);
        }
        this.stems = out;
        if (out.error) this._error(out.error);
        this._renderStems();
        if (this._stemsBusy()) this._pollStems();
      };
    });
  }

  _pollStems() {
    clearTimeout(this.stemsTimer);
    this.stemsTimer = setTimeout(async () => {
      const prev = this.stems?.job?.state;
      this.stems = await this.api.stems_status();
      this._renderStems();
      const j = this.stems.job;
      if (this._stemsBusy()) return this._pollStems();
      if (prev === 'downloading' && j.state === 'idle') toast(t('Model downloaded: now you can extract the stems'));
      if (j.state === 'done') toast(t('Stems ready: {n} files', { n: j.stems.length }));
      if (j.state === 'error') this._error(j.error);
    }, 500);
  }

  _renderStems() {
    const box = $('#st-box');
    if (!box) return;
    const j = this.stems?.job || {};
    const tab = document.querySelector('.nav-item[data-tab="sampler"]');
    if (j.state === 'downloading' || j.state === 'running') {
      const pct = Math.round((j.progress || 0) * 100);
      box.innerHTML = `<div class="rc-item">
        <div class="rc-item-name">${j.state === 'downloading' ? t('Downloading the model…') : `${esc(j.title)} · ${j.scope === 'region' ? t('region') : t('whole')}`}</div>
        ${j.state === 'running' ? `<div class="sp-meter st-meter"><div style="width:${pct}%"></div></div>
          <div class="rc-item-act"><span class="hint">${pct}%</span><span class="spacer"></span>
          ${btn(t('Cancel'), { size: 'xs', 'data-act': 'cancel' })}</div>` : ''}
      </div>`;
    } else if (j.state === 'done' && j.stems?.length) {
      box.innerHTML = `<div class="hint">${esc(j.title)} · ${j.scope === 'region' ? t('region') : t('whole')}
          <a href="#" data-act="folder">${icon('folder-open')}</a></div>`
        + j.stems.map((r) => `
        <div class="rc-item st-item" data-path="${esc(r.path)}" title="${esc(r.path)}">
          <div class="rc-item-act"><span class="rc-item-name">${esc(r.label)}</span><span class="spacer"></span>
            ${btn(t('Open in the editor'), { size: 'xs', 'data-act': 'open', icon: 'pencil' })}
            ${iconBtn('folder-open', t('Show in {app}', { app: FILE_MANAGER }), { size: 'xs', 'data-act': 'reveal' })}
          </div>
        </div>`).join('');
    } else {
      const msg = j.state === 'cancelled' ? t('Separation cancelled.') : j.state === 'error' ? `<span class="error">${esc(j.error)}</span>`
        : !this.stems?.installed ? t('To separate the stems install the extension: see «Extract stems».')
          : t('Open a recording and use «Extract stems»: the stems show up here.');
      box.innerHTML = `<div class="hint">${msg}</div>`;
    }
    tab?.classList.toggle('busy', j.state === 'running');
  }

  async _stemsClick(e) {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (!act) return;
    e.preventDefault();
    if (act === 'cancel') { this.stems = await this.api.stems_cancel(); return; }
    if (act === 'folder') return this.api.reveal_path(this.stems.job.folder);
    const path = e.target.closest('[data-path]')?.dataset.path;
    if (!path) return;
    if (act === 'reveal') return this.api.reveal_path(path);
    this._opened(await this.api.stems_open(path));
  }

  // ---------------------------------------------------------------- enhance
  _enhBusy() { return ['running', 'downloading'].includes(this.enh?.job?.state); }

  _enhModel() {
    const ms = this.enh?.models || [];
    return ms.find((m) => m.key === this.opts.enhModel) || ms.find((m) => m.key === this.enh.default) || ms[0];
  }

  _enhMenu(anchor, forceScope) {
    const st = this.enh;
    if (!this.session) return this._error(t('Open a recording first'));
    if (!st?.models?.length) return;
    const r = this.regions[this.sel];
    const m = this._enhModel();
    const scope = forceScope || (r ? 'region' : 'all');
    const models = st.models.length > 1
      ? `<div class="en-model"><b>${esc(m.label)}</b>${settingsLink('sampler', t('Change model'))}</div>` : '';
    const facts = `<div class="en-facts">
        <span>${icon('download')} ${m.mb} MB</span><span title="${t('Memory used only while working')}">RAM ${esc(m.ram)}</span>
        <span title="${t('On Apple Silicon (GPU)')}">${esc(m.speed)}</span></div>`;
    let body, go;
    if (!m.installed) {
      body = `<div class="hint">${t('The enhancement runs on this computer with PyTorch, an extension to install once:')}</div>
        <code class="st-code">${esc(st.install_hint)}</code>`;
    } else if (!m.model_ready) {
      body = `<div class="hint">${t('It needs the {model} model (~{mb} MB), downloaded only once. After that it works offline: the audio never leaves the computer.', { model: `<b>${esc(m.label)}</b>`, mb: m.mb })}</div>`;
      go = btn(t('Download the model'), { variant: 'brand', icon: 'download', 'data-go': 'download' });
    } else {
      body = `${seg([['region', t('Selected region'), { disabled: !r, title: r ? `${fmt(r.start)} – ${fmt(r.end)}` : t('Select a region') }],
        ['all', t('Whole audio')]], scope, { 'data-o': 'scope', cls: 'st-scope' })}
        <div class="hint">${t('Creates a new «… ({enhanced}).wav» file next to the samples: the original stays as it is.', { enhanced: t('enhanced') })}</div>`;
      go = btn(t('Enhance'), { icon: 'sparkles', cls: 'cs-ai', 'data-go': 'run' });
    }
    const pop = showPopover(anchor, `<div class="pop-title">${icon('sparkles')} ${t('Enhance with AI')}</div>
      ${models}<div class="hint en-detail">${esc(m.detail)}</div>${facts}${body}
      <div class="hint en-license">${t('{model} model, licence {license}. The model is loaded only while it works, in a separate process: when the job is done the memory is freed.', { model: esc(m.label.split(' · ')[0]), license: esc(m.license) })}</div>
      ${go ? `<div class="pop-actions">${go}</div>` : ''}`);
    pop.querySelector('[data-settings-link]')?.addEventListener('click', () => pop.close());
    pop.querySelectorAll('[data-go]').forEach((b) => {
      b.onclick = async () => {
        let out;
        pop.close();
        if (b.dataset.go === 'download') {
          out = await this.api.enhance_download_model(m.key);
        } else {
          const sc = pop.querySelector('[data-o=scope]')?.value === 'region' && r ? 'region' : 'all';
          out = await this.api.enhance_start(sc, sc === 'region' ? r.start : null, sc === 'region' ? r.end : null, m.key);
        }
        this.enh = out;
        if (out.error) this._error(out.error);
        this._renderEnh();
        if (this._enhBusy()) this._pollEnh();
      };
    });
  }

  _pollEnh() {
    clearTimeout(this.enhTimer);
    this.enhTimer = setTimeout(async () => {
      const prev = this.enh?.job?.state;
      this.enh = await this.api.enhance_status();
      this._renderEnh();
      const j = this.enh.job;
      if (this._enhBusy()) return this._pollEnh();
      if (prev === 'downloading' && j.state === 'idle') toast(t('Model downloaded: now you can use «Enhance»'));
      if (j.state === 'done') toast(t('Sample enhanced: open it in the editor to listen to it'));
      if (j.state === 'error') this._error(j.error);
    }, 500);
  }

  _renderEnh() {
    const box = $('#en-box');
    if (!box) return;
    const j = this.enh?.job || {};
    const what = `${esc(j.title)} · ${j.scope === 'region' ? t('region, {s} s', { s: j.seconds }) : t('whole')}`;
    if (j.state === 'downloading') {
      box.innerHTML = `<div class="rc-item"><div class="rc-item-name">${t('Downloading the model…')}</div></div>`;
    } else if (j.state === 'running') {
      const pct = Math.round((j.progress || 0) * 100);
      box.innerHTML = `<div class="rc-item en-item">
        <div class="rc-item-name">${what}</div>
        <div class="sp-meter st-meter en-meter"><div style="width:${pct}%"></div></div>
        <div class="rc-item-act"><span class="hint">${pct ? `${pct}%` : t('Loading the model…')}</span><span class="spacer"></span>
          ${btn(t('Cancel'), { size: 'xs', 'data-act': 'cancel' })}</div>
      </div>`;
    } else if (j.state === 'done' && j.result) {
      box.innerHTML = `<div class="rc-item en-item" title="${esc(j.result.path)}">
        <div class="rc-item-name">${what}</div>
        <div class="rc-item-act"><span class="hint">${(j.result.sr / 1000).toFixed(1)} kHz</span><span class="spacer"></span>
          ${btn(t('Open in the editor'), { size: 'xs', 'data-act': 'open', icon: 'pencil' })}
          ${iconBtn('folder-open', t('Show in {app}', { app: FILE_MANAGER }), { size: 'xs', 'data-act': 'reveal' })}
        </div>
      </div>`;
    } else {
      const msg = j.state === 'cancelled' ? t('Enhancement cancelled.') : j.state === 'error' ? `<span class="error">${esc(j.error)}</span>`
        : t('Select a region and press «Enhance»: the AI restoration rebuilds the high frequencies and cleans up the compression.');
      box.innerHTML = `<div class="hint">${msg}</div>`;
    }
    $('#sp-enh')?.toggleAttribute('loading', j.state === 'running');
  }

  async _enhClick(e) {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (!act) return;
    e.preventDefault();
    if (act === 'cancel') { this.enh = await this.api.enhance_cancel(); return; }
    if (act === 'reveal') return this.api.reveal_path(this.enh.job.result.path);
    if (act === 'open') this._opened(await this.api.enhance_open());
  }

  _selectedDevices() {
    const ids = new Set(this.rec.devices.map((d) => d.id));
    let sel = (this.opts.devices || []).filter((id) => ids.has(id));
    if (!this.opts.devices) sel = [this.rec.devices.find((d) => d.default)?.id || this.rec.devices[0]?.id].filter(Boolean);
    return sel;
  }

  _renderRecorder() {
    $('#rc-path').textContent = this.recDir;
    $('#rc-path').title = this.recDir;
    const f = this.recFmt, spec = this.rec.formats[f.format];
    const lbl = (list, v) => list.find(([k]) => String(k) === String(v))?.[1] ?? v;
    $('#rc-fmt-sum').textContent = `${spec.label} · ${lbl(spec.qualities, f.quality)} · ${lbl(this.rec.channels, f.channels)}`;
    this._renderOptsSummary();
    this._renderDevices();
    this._renderRecButton();
    this._renderRecordings();
    if (this._setBody?.isConnected) this._renderSetDevices();
  }

  _formatControls() {
    const f = this.recFmt, spec = this.rec.formats[f.format];
    const rates = spec.rates ? this.rec.rates.filter(([r]) => spec.rates.includes(r)) : this.rec.rates;
    const chans = this.rec.channels.filter(([c]) => spec.multichannel || c !== 'all');
    const dis = this.rec.running;
    return `
      ${select(Object.entries(this.rec.formats).map(([k, v]) => [k, v.label]), f.format, { 'data-k': 'format', label: t('Format'), disabled: dis })}
      ${select(spec.qualities, f.quality, { 'data-k': 'quality', label: t('Quality'), disabled: dis })}
      ${select(rates, f.rate, { 'data-k': 'rate', label: t('Sample rate'), disabled: dis || !!spec.rates })}
      ${select(chans, f.channels, { 'data-k': 'channels', label: t('Channels'), disabled: dis })}`;
  }

  // On screen: the outputs that will be recorded (chosen in Settings), with live meters while recording.
  _renderDevices() {
    const box = $('#rc-devices');
    if (!box) return;
    if (!this.rec.devices.length) {
      box.innerHTML = `<div class="hint">${this.rec.hint || t('No output can be recorded.')}</div>`;
      return;
    }
    const sel = new Set(this._selectedDevices());
    const tracks = Object.fromEntries(this.rec.tracks.map((tr) => [tr.device, tr]));
    const shown = this.rec.devices.filter((d) => (this.rec.running ? tracks[d.id] : sel.has(d.id)));
    box.innerHTML = shown.map((d) => {
      const tr = this.rec.running ? tracks[d.id] : null;
      const meta = d.sample_rate ? `${t('{n} ch', { n: d.channels })} · ${(d.sample_rate / 1000).toFixed(1).replace('.0', '')} kHz` : (d.note || '');
      return `<div class="rc-dev${tr ? ' on' : ''}">
        <div class="rc-dev-name">${esc(d.name)}${d.default ? ` <span class="hint">· ${t('default')}</span>` : ''}</div>
        <div class="rc-dev-meta hint">${tr ? (tr.error ? `<span class="error">${esc(tr.error)}</span>`
          : `${clock(tr.seconds)} · ${mb(tr.bytes)}`) : meta}</div>
        ${tr && !tr.error ? `<div class="sp-meter"><div style="width:${Math.min(100, Math.sqrt(tr.level || 0) * 220)}%"></div></div>` : ''}
      </div>`;
    }).join('');
  }

  // Settings: which outputs to record.
  _renderSetDevices() {
    const box = this._setBody.querySelector('#set-rc-devices');
    if (!this.rec.devices.length) {
      box.innerHTML = `<span class="hint">${this.rec.hint || t('No output can be recorded.')}</span>`;
      return;
    }
    const sel = new Set(this._selectedDevices());
    box.innerHTML = this.rec.devices.map((d) => check(`${esc(d.name)}${d.default ? ` <span class="hint">· ${t('default')}</span>` : ''}`,
      sel.has(d.id), { 'data-dev': d.id, disabled: this.rec.running })).join('');
  }

  /** Recorder section of the Settings page. */
  async renderSettings(body) {
    await this.ensure();
    this._setBody = body;
    const o = this.opts;
    const enhModels = this.enh?.models || [];
    body.innerHTML =
      setRow(t('Outputs to record'), `${t('Every chosen output goes into a separate file.')} <a href="#" id="set-rc-refresh">${t('Refresh the list')}</a>`,
        '<div class="set-checks" id="set-rc-devices"></div>')
      + setRow(t('Format'), t('Format, quality, sample rate and channels of the recorded files.'), `<div class="rc-fmt set-rc-fmt" id="set-rc-fmt">${this._formatControls()}</div>`)
      + setRow(t('Recordings folder'), '',
        `<span class="set-path" id="set-rc-path" title="${esc(this.recDir)}">${esc(this.recDir)}</span>
         <wa-button id="set-rc-pick" size="s" appearance="filled-outlined"><wa-icon slot="start" name="folder-open"></wa-icon>${t('Choose…')}</wa-button>`)
      + setRow(t('Fades of the extracted samples'), t('Applied to every exported region, to avoid clicks at the start and at the end.'),
        `${num(o.fade_in_ms, { id: 'set-sp-fi', min: 0, max: 200, step: 1, label: 'Fade in', style: 'width:120px' }).replace('></wa-number-input>', '><span slot="end" class="hint">ms in</span></wa-number-input>')}
         ${num(o.fade_out_ms, { id: 'set-sp-fo', min: 0, max: 2000, step: 5, label: 'Fade out', style: 'width:130px' }).replace('></wa-number-input>', '><span slot="end" class="hint">ms out</span></wa-number-input>')}`)
      + setRow(t('Normalise'), t('Brings the peak of every extracted sample to −0.3 dBFS.'), `<wa-switch id="set-sp-norm" size="s" ${o.normalize ? 'checked' : ''}></wa-switch>`)
      + (enhModels.length > 1 ? setRow(t('«Enhance» model'), esc(this._enhModel().detail),
        select(enhModels.map((m) => [m.key, m.label]), this._enhModel().key, { id: 'set-en-model', label: t('Model'), style: 'width:280px' })) : '');
    this._renderSetDevices();
    const saved = () => { this._persist(); savedFlash(body); };
    body.querySelector('#set-rc-refresh').onclick = async (e) => {
      e.preventDefault();
      this.rec.devices = await this.api.recorder_devices();
      this._renderRecorder();
    };
    body.querySelector('#set-rc-devices').addEventListener('change', (e) => {
      const cb = e.target.closest('wa-checkbox[data-dev]');
      if (!cb) return;
      const sel = new Set(this._selectedDevices());
      if (cb.checked) sel.add(cb.dataset.dev); else sel.delete(cb.dataset.dev);
      this.opts.devices = [...sel];
      saved();
      this._renderDevices();
      this._renderRecButton();
    });
    body.querySelector('#set-rc-fmt').addEventListener('change', async (e) => {
      const k = e.target.dataset.k;
      if (!k) return;
      this.recFmt = { ...this.recFmt, [k]: k === 'rate' ? +e.target.value : e.target.value };
      if (k === 'format') { // other options depend on the format: fall back to its defaults
        const f = this.rec.formats[this.recFmt.format];
        this.recFmt.quality = f.qualities[0][0];
        if (f.rates) this.recFmt.rate = f.rates[0];
        if (!f.multichannel && this.recFmt.channels === 'all') this.recFmt.channels = 'stereo';
        body.querySelector('#set-rc-fmt').innerHTML = this._formatControls();
      }
      await this.api.set_setting('recorder_format', this.recFmt);
      this._renderRecorder();
      savedFlash(body);
    });
    body.querySelector('#set-rc-pick').onclick = async () => {
      const p = await this.api.pick_folder();
      if (!p) return;
      this.recDir = (await this.api.set_setting('recorder_dir', p)).recorder_dir;
      body.querySelector('#set-rc-path').textContent = this.recDir;
      body.querySelector('#set-rc-path').title = this.recDir;
      this._renderRecorder();
      savedFlash(body);
    };
    const optNum = (id, key) => body.querySelector(id).addEventListener('change', (e) => {
      this.opts[key] = Math.max(0, +e.target.value || 0); saved(); this._dropAudio(); this._renderOptsSummary();
    });
    optNum('#set-sp-fi', 'fade_in_ms');
    optNum('#set-sp-fo', 'fade_out_ms');
    body.querySelector('#set-sp-norm').addEventListener('change', (e) => { this.opts.normalize = e.target.checked; saved(); this._dropAudio(); this._renderOptsSummary(); });
    body.querySelector('#set-en-model')?.addEventListener('change', (e) => { this.opts.enhModel = e.target.value; saved(); });
  }

  _renderRecButton() {
    const on = this.rec.running, b = $('#rc-rec');
    setPlayButton(b, on, t('Record'), t('Stop'));
    b.querySelector('wa-icon')?.setAttribute('name', on ? 'square' : 'circle');
    const n = this._selectedDevices().length;
    b.disabled = !on && !n;
    $('#rc-clock').textContent = clock(on ? this.rec.elapsed : 0);
    $('#rc-clock').classList.toggle('on', on);
    const live = this.rec.tracks.filter((tr) => !tr.error).length;
    $('#rc-info').textContent = on ? (live === 1 ? t('Recording 1 output…') : t('Recording {n} outputs…', { n: live }))
      : n ? (n === 1 ? t('1 output selected: one file.') : t('{n} outputs selected: one file each.', { n })) : t('Select at least one output.');
    document.querySelector('.nav-item[data-tab="sampler"]')?.classList.toggle('recording', on);
  }

  _renderRecordings() {
    const list = this.rec.recordings || [];
    $('#rc-list').innerHTML = list.length ? list.map((r) => `
      <div class="rc-item" data-path="${esc(r.path)}" title="${esc(r.path)}">
        <div class="rc-item-name">${esc(r.device)}</div>
        <div class="hint">${clock(r.seconds)} · ${esc(r.format)} · ${mb(r.bytes)}${r.error ? ` · <span class="error">${esc(r.error)}</span>` : ''}</div>
        <div class="rc-item-act">
          ${btn(t('Open in the editor'), { size: 'xs', 'data-act': 'open', icon: 'pencil' })}
          ${iconBtn('folder-open', t('Show in {app}', { app: FILE_MANAGER }), { size: 'xs', 'data-act': 'reveal' })}
        </div>
      </div>`).join('') : `<div class="hint">${t('The recordings of this session show up here.')}</div>`;
  }

  async toggleRecording() {
    const b = $('#rc-rec');
    b.loading = true;
    const st = this.rec.running ? await this.api.recorder_stop()
      : await this.api.recorder_start(this._selectedDevices(), this.recFmt);
    b.loading = false;
    const was = this.rec.running;
    Object.assign(this.rec, st);
    if (st.error) this._error(st.error);
    this._renderRecorder();
    if (this.rec.running) this._pollRec();
    else if (was && st.recordings?.length) {
      const failed = st.tracks.filter((tr) => tr.error).length;
      toast(!failed ? t('Recording saved') : failed === 1 ? t('Recording saved (1 output with errors)') : t('Recording saved ({n} outputs with errors)', { n: failed }));
      this._opened(await this.api.recorder_open(st.recordings[0].path));
    }
  }

  _pollRec() {
    clearTimeout(this.recTimer);
    this.recTimer = setTimeout(async () => {
      Object.assign(this.rec, await this.api.recorder_status());
      this._renderDevices();
      this._renderRecButton();
      if (this.rec.running) this._pollRec();
    }, 200);
  }

  // ---------------------------------------------------------------- view
  _resize() {
    if (!this.cv) return;
    for (const c of [this.cv, this.ov]) {
      const r = c.getBoundingClientRect();
      c.width = Math.max(1, Math.round(r.width * devicePixelRatio));
      c.height = Math.max(1, Math.round(r.height * devicePixelRatio));
    }
    this.detail = null;
    this._fetchDetail();
    this.draw();
  }

  setView(start, end) {
    const d = this.duration;
    if (!d) return;
    let len = Math.min(d, Math.max(MIN_VIEW_S, end - start));
    start = Math.max(0, Math.min(d - len, start));
    this.view = { start, end: start + len };
    $('#sp-view-info').textContent = t('View {a} – {b}', { a: fmt(start), b: fmt(start + len) });
    this.draw();
    clearTimeout(this.viewTimer);
    this.viewTimer = setTimeout(() => this._fetchDetail(), 60);
  }

  async _fetchDetail() {
    if (!this.session) return;
    const { start, end } = this.view, token = this.token;
    const p = await this.api.sampler_view(start, end, Math.min(4000, this.cv.width));
    if (token !== this.token || !p || p.start !== start && Math.abs(p.start - start) > 1e-3) return;
    this.detail = p;
    this.draw();
  }

  _x(t) { return (t - this.view.start) / (this.view.end - this.view.start) * this.cv.width; }
  _time(e) {
    const r = this.cv.getBoundingClientRect();
    return this.view.start + (e.clientX - r.left) / r.width * (this.view.end - this.view.start);
  }

  _wheel(e) {
    if (!this.session) return;
    e.preventDefault();
    const len = this.view.end - this.view.start;
    if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
      const dx = (e.shiftKey ? e.deltaY : e.deltaX) / this.cv.clientWidth * len;
      this.setView(this.view.start + dx, this.view.end + dx);
      return;
    }
    const at = this._time(e), k = Math.exp(e.deltaY * 0.002);
    this.setView(at - (at - this.view.start) * k, at + (this.view.end - at) * k);
  }

  draw() {
    if (!this.cv) return;
    this._drawWave();
    this._drawOverview();
  }

  _drawWave() {
    const c = this.cv, ctx = c.getContext('2d'), W = c.width, H = c.height, dpr = devicePixelRatio;
    ctx.clearRect(0, 0, W, H);
    if (!this.session) return;
    const css = getComputedStyle(document.documentElement);
    const { start, end } = this.view;
    // regions under the waveform
    this.regions.forEach((r, i) => {
      const x0 = this._x(r.start), x1 = this._x(r.end);
      if (x1 < 0 || x0 > W) return;
      const sel = i === this.sel;
      ctx.fillStyle = sel ? 'rgba(0,176,159,.28)' : r.on ? 'rgba(0,176,159,.13)' : 'rgba(154,154,154,.08)';
      ctx.fillRect(x0, 0, x1 - x0, H);
      ctx.fillStyle = sel ? '#2fd1bd' : '#00b09f';
      ctx.fillRect(x0, 0, Math.max(1, dpr), H);
      ctx.fillRect(x1 - Math.max(1, dpr), 0, Math.max(1, dpr), H);
      ctx.font = `${11 * dpr}px ${css.getPropertyValue('--wa-font-family-body')}`;
      ctx.fillStyle = sel ? '#ececec' : '#9a9a9a';
      if (x1 - x0 > 30 * dpr) ctx.fillText(String(i + 1), x0 + 4 * dpr, 14 * dpr);
    });
    // grid (seconds)
    const len = end - start;
    const step = [0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60, 300].find((s) => len / s < 12) || 600;
    ctx.fillStyle = 'rgba(154,154,154,.5)';
    ctx.font = `${10 * dpr}px ${css.getPropertyValue('--wa-font-family-code')}`;
    for (let s = Math.ceil(start / step) * step; s < end; s += step) {
      const x = this._x(s);
      ctx.fillRect(x, H - 4 * dpr, 1, 4 * dpr);
      ctx.fillText(fmt(s).replace(' s', 's'), x + 3 * dpr, H - 6 * dpr);
    }
    // waveform
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, '#2fd1bd');
    grad.addColorStop(0.5, '#00b09f');
    grad.addColorStop(1, '#2fd1bd');
    ctx.fillStyle = grad;
    const mid = H / 2, amp = H / 2 - 16 * dpr;
    const p = this.detail && Math.abs(this.detail.start - start) < 1e-3 && Math.abs(this.detail.end - end) < 1e-3 ? this.detail : this.overview;
    if (p && p.wave_min.length) {
      const n = p.wave_min.length, span = p.end - p.start;
      const colX = (k) => this._x(p.start + k / n * span);
      const k0 = Math.max(0, Math.floor((start - p.start) / span * n)), k1 = Math.min(n, Math.ceil((end - p.start) / span * n));
      const per = Math.max(1, Math.floor((k1 - k0) / W));
      for (let k = k0; k < k1; k += per) {
        let mn = 1, mx = -1;
        for (let j = k; j < Math.min(k1, k + per); j++) { mn = Math.min(mn, p.wave_min[j]); mx = Math.max(mx, p.wave_max[j]); }
        const x = colX(k), w = Math.max(1, colX(k + per) - x);
        ctx.fillRect(x, mid - mx * amp, w, Math.max(1, (mx - mn) * amp));
      }
    }
    // selection being drawn and playhead
    if (this.drag?.kind === 'new') {
      const x0 = this._x(this.drag.a), x1 = this._x(this.drag.b);
      ctx.fillStyle = this.drag.limited ? 'rgba(239,83,80,.25)' : 'rgba(47,209,189,.25)';
      ctx.fillRect(Math.min(x0, x1), 0, Math.abs(x1 - x0), H);
    }
    if (this.playing && this.player.playing) {
      const x = this._x(this.playing.start + this.player.currentTime);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(x, 0, Math.max(1, dpr), H);
    }
  }

  _drawOverview() {
    const c = this.ov, ctx = c.getContext('2d'), W = c.width, H = c.height;
    ctx.clearRect(0, 0, W, H);
    const p = this.overview;
    if (!p || !this.duration) return;
    ctx.fillStyle = 'rgba(154,154,154,.55)';
    const n = p.wave_min.length;
    for (let k = 0; k < n; k++) {
      const x = k / n * W;
      ctx.fillRect(x, H / 2 - p.wave_max[k] * H / 2, Math.max(1, W / n), Math.max(1, (p.wave_max[k] - p.wave_min[k]) * H / 2));
    }
    ctx.fillStyle = 'rgba(0,176,159,.5)';
    for (const r of this.regions) ctx.fillRect(r.start / this.duration * W, H - 3, Math.max(1, (r.end - r.start) / this.duration * W), 3);
    const x0 = this.view.start / this.duration * W, x1 = this.view.end / this.duration * W;
    ctx.strokeStyle = '#00b09f';
    ctx.lineWidth = devicePixelRatio;
    ctx.strokeRect(x0 + 0.5, 0.5, Math.max(2, x1 - x0) - 1, H - 1);
  }

  // ---------------------------------------------------------------- regions (mouse)
  _regionAt(t) {
    for (let i = this.regions.length - 1; i >= 0; i--) if (t >= this.regions[i].start && t <= this.regions[i].end) return i;
    return -1;
  }

  _edgeAt(e) {
    const x = (e.clientX - this.cv.getBoundingClientRect().left) * devicePixelRatio;
    for (let i = this.regions.length - 1; i >= 0; i--) {
      const r = this.regions[i];
      if (Math.abs(this._x(r.start) - x) <= EDGE_PX * devicePixelRatio) return { i, side: 'start' };
      if (Math.abs(this._x(r.end) - x) <= EDGE_PX * devicePixelRatio) return { i, side: 'end' };
    }
    return null;
  }

  _down(e) {
    if (!this.session || e.button !== 0) return;
    this.cv.setPointerCapture(e.pointerId);
    const at = this._time(e), edge = this._edgeAt(e);
    if (edge) this.drag = { kind: 'edge', ...edge };
    else this.drag = { kind: 'new', a: at, b: at, x: e.clientX, hit: this._regionAt(at) };
  }

  _move(e) {
    if (!this.session) return;
    const at = Math.max(0, Math.min(this.duration, this._time(e)));
    if (!this.drag) { this.cv.style.cursor = this._edgeAt(e) ? 'ew-resize' : 'crosshair'; return; }
    if (this.drag.kind === 'edge') {
      const r = this.regions[this.drag.i];
      if (this.drag.side === 'start') r.start = Math.max(r.end - this.maxS, Math.min(at, r.end - 0.005));
      else r.end = Math.min(r.start + this.maxS, Math.max(at, r.start + 0.005));
      this.sel = this.drag.i;
    } else {
      const lim = this.maxS;
      this.drag.limited = Math.abs(at - this.drag.a) > lim;
      this.drag.b = this.drag.a + Math.sign(at - this.drag.a) * Math.min(lim, Math.abs(at - this.drag.a));
      $('#sp-view-info').innerHTML = `${t('New region:')} <span class="${this.drag.limited ? 'error' : ''}">${fmt(Math.abs(this.drag.b - this.drag.a))}</span> / max ${this.maxS} s`;
    }
    this.draw();
  }

  _up(e) {
    const d = this.drag;
    this.drag = null;
    if (!d) return;
    if (d.kind === 'edge') { this.renderRegions(); this._dropAudio(); this.draw(); return; }
    if (Math.abs(e.clientX - d.x) < 4) {  // a click: select (and play) the region under the pointer
      if (d.hit >= 0) this.playRegion(d.hit);
      else { this.sel = -1; this.renderRegions(); this.draw(); }
      this.setView(this.view.start, this.view.end);
      return;
    }
    const start = Math.min(d.a, d.b), end = Math.max(d.a, d.b);
    this.regions.push({ start, end, name: '', on: true });
    this.regions.sort((x, y) => x.start - y.start);
    this.sel = this.regions.findIndex((r) => r.start === start && r.end === end);
    this.renderRegions();
    this.setView(this.view.start, this.view.end);
    this.playRegion(this.sel);
  }

  async autoSlice() {
    if (!this.session) return;
    const b = $('#sp-slice');
    b.loading = true;
    const whole = this.view.start <= 0 && this.view.end >= this.duration - 1e-6;
    const found = await this.api.sampler_auto_slices(this.opts.sensitivity, this.view.start, whole ? null : this.view.end);
    b.loading = false;
    // replace the regions inside the sliced range, keep the others
    const lo = this.view.start, hi = this.view.end;
    this.regions = this.regions.filter((r) => r.end <= lo || r.start >= hi).concat(found.map((r) => ({ ...r, name: '', on: true })));
    this.regions.sort((x, y) => x.start - y.start);
    this.sel = -1;
    this.renderRegions();
    this.draw();
    toast(!found.length ? t('No transients found: try raising the sensitivity')
      : whole ? t('{n} regions on the transients', { n: found.length }) : t('{n} regions on the transients of the visible part', { n: found.length }));
  }

  removeRegion(i) {
    this.regions.splice(i, 1);
    this.sel = Math.min(this.sel, this.regions.length - 1);
    if (this.sel === i) this.sel = -1;
    this.renderRegions();
    this.draw();
  }

  _renderCount() {
    const on = this.regions.filter((r) => r.on).length;
    $('#sp-count').textContent = this.regions.length ? t('({n} of {total} selected)', { n: on, total: this.regions.length }) : '';
    $('#sp-export').disabled = !on;
    $('#sp-rack').disabled = !on;
    $('#sp-clear').disabled = !this.regions.length;
  }

  renderRegions() {
    const box = $('#sp-regions');
    this._renderCount();
    if (!this.regions.length) {
      box.innerHTML = `<div class="hint sp-regions-empty">${this.session ? t('No regions: drag on the waveform or use «Slice on transients».') : ''}</div>`;
      return;
    }
    box.innerHTML = this.regions.map((r, i) => `
      <div class="sp-row${i === this.sel ? ' sel' : ''}" data-i="${i}">
        ${check('', r.on, { label: t('Export') })}
        <span class="sp-num">${i + 1}</span>
        <wa-input size="s" value="${esc(r.name)}" placeholder="${esc(this._defaultName(i))}" label="${t('Name')}"></wa-input>
        <span class="sp-time">${fmt(r.start)}</span>
        <span class="sp-time ${r.end - r.start >= this.maxS - 1e-3 ? 'error' : ''}">${fmt(r.end - r.start)}</span>
        ${iconBtn('play', t('Listen'), { 'data-act': 'play' })}
        ${iconBtn('search', t('Show on the waveform'), { 'data-act': 'zoom' })}
        ${iconBtn('sparkles', t('Enhance with AI'), { 'data-act': 'enhance', cls: 'cs-ai-icon' })}
        ${iconBtn('layout-grid', t('To the Drum Rack'), { 'data-act': 'rack' })}
        ${iconBtn('x', t('Delete'), { 'data-act': 'del' })}
      </div>`).join('');
  }

  _defaultName(i) { return `${this.session?.title || 'sample'} - ${String(i + 1).padStart(2, '0')}`; }

  _regionClick(e) {
    const row = e.target.closest('[data-i]');
    if (!row) return;
    const i = +row.dataset.i, act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'del') return this.removeRegion(i);
    if (act === 'zoom') {
      const r = this.regions[i], pad = Math.max(0.05, (r.end - r.start) * 0.25);
      this.sel = i;
      this.renderRegions();
      return this.setView(r.start - pad, r.end + pad);
    }
    if (act === 'play') return this.playRegion(i);
    if (act === 'rack') return this.sendToRack([i]);
    if (act === 'enhance') {
      this.sel = i;
      this.renderRegions();
      this.draw();
      return this._enhMenu($(`#sp-regions [data-i="${i}"] [data-act=enhance]`), 'region'); // the row was re-rendered
    }
    if (e.target.closest('wa-input, wa-checkbox')) return;
    this.playRegion(i);
  }

  // ---------------------------------------------------------------- playback
  _dropAudio() { this.audioRev += 1; } // the region audio changed: re-render it on next play

  async _playSpan(start, end, key) {
    const buf = await this.player.load(`sp:${this.token}.${this.audioRev}:${key}:${start.toFixed(4)}-${end.toFixed(4)}`,
      () => this.api.sampler_audio(start, end, this.opts));
    if (!buf) return;
    this.player.play(`sampler:${key}`, buf, 0);
    this.playing = { start, end };
    this._syncPlay();
    const tick = () => { if (this.playing) { this.draw(); requestAnimationFrame(tick); } };
    requestAnimationFrame(tick);
  }

  playRegion(i) {
    const r = this.regions[i];
    if (!r) return;
    this.sel = i;
    this.renderRegions();
    this.draw();
    this._playSpan(r.start, r.end, `r${i}`);
  }

  togglePlay() {
    if (this.player.playing && this.playing) { this.player.stop(); return; }
    if (!this.session) return;
    if (this.sel >= 0) return this.playRegion(this.sel);
    this._playSpan(this.view.start, Math.min(this.view.end, this.view.start + 60), 'view');
  }

  _syncPlay() {
    setPlayButton($('#sp-play'), !!this.playing && this.player.playing);
    this.draw();
  }

  // ---------------------------------------------------------------- export
  // Regions as WAV files, aligned with `idx`. A region already exported with the same bounds, name and
  // fades/normalisation reuses its file (sending to the Drum Rack twice doesn't duplicate it).
  async _files(idx, button) {
    const key = (r, i) => JSON.stringify([r.start, r.end, r.name || this._defaultName(i), this.opts.fade_in_ms,
      this.opts.fade_out_ms, this.opts.normalize]);
    const todo = idx.filter((i) => this.regions[i].file?.key !== key(this.regions[i], i));
    if (todo.length) {
      // empty names get the placeholder shown in the list, so numbers match the region numbers
      const regions = todo.map((i) => ({ start: this.regions[i].start, end: this.regions[i].end, name: this.regions[i].name || this._defaultName(i) }));
      if (button) button.loading = true;
      const r = await this.api.sampler_export(regions, this.opts);
      if (button) button.loading = false;
      if (r.error) { this._error(r.error); return null; }
      todo.forEach((i, k) => { if (r.files[k]) this.regions[i].file = { key: key(this.regions[i], i), path: r.files[k] }; });
      this._showExported(r.folder, r.paths[0]);
      if (r.in_library) toast(t('The samples are in the library: analysing them'));
    }
    return idx.map((i) => this.regions[i].file?.path || null);
  }

  _showExported(folder, first) {
    if (!first) return;
    const head = $('#sp-regions-head-msg') || Object.assign(document.createElement('div'), { id: 'sp-regions-head-msg', className: 'hint sp-exported' });
    head.innerHTML = t('Exported to {folder}', { folder: `<a href="#">${esc(folder)}</a>` });
    head.querySelector('a').onclick = (e) => { e.preventDefault(); this.api.reveal_path(first); };
    $('#sp-regions').before(head);
  }

  _checked() { return this.regions.map((r, i) => (r.on ? i : -1)).filter((i) => i >= 0); }

  async export() {
    const idx = this._checked();
    if (!idx.length) return;
    const files = await this._files(idx, $('#sp-export'));
    if (!files) return;
    const n = files.filter(Boolean).length;
    toast(n === 1 ? t('1 sample exported') : t('{n} samples exported', { n }));
  }

  // Selected regions (or one) onto free Drum Rack pads, from the rack's selected pad on, to play them there.
  async sendToRack(idx = this._checked()) {
    if (!idx.length || !this.onSendToRack) return;
    const files = await this._files(idx, $('#sp-rack'));
    if (!files) return;
    const refs = idx.map((i, k) => files[k] && {
      kind: 'file', path: files[k], name: files[k].split('/').pop(), cls: null, root: null,
      dur: +(this.regions[i].end - this.regions[i].start).toFixed(3) }).filter(Boolean);
    if (refs.length) this.onSendToRack(refs);
  }
}
