// "Recorder" screen: a file bar on top (the open audio and a button to choose another one), the waveform at full
// width with a media-player transport under it (play/pause, stop, show all, record the audio output), then the
// "Extractions" of the open audio in three tabs: Cuts (regions marked by hand or on transients), Stems and
// Enhanced (files already made from it, found again on disk).
import { btn, iconBtn, slider, check, num, select, seg, text, icon, openDialog, FILE_MANAGER } from './kit.js';
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
  constructor({ api, player, onSendToRack, onSend, getBuses, onSendToBus, classes = [] }) {
    this.api = api;
    this.classes = classes;   // library classes, for the labels in "From the library…"
    this.onSendToRack = onSendToRack; // (refs) -> loads them on the Drum Rack
    this.onSend = onSend;             // (ref, x, y) -> the "Send" menu of the library (Sequencer bus or Drum Rack group)
    this.getBuses = getBuses;         // async () -> the Sequencer buses
    this.onSendToBus = onSendToBus;   // (refs, busId) -> new layers on that bus
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
    this.playing = null;      // {start, end, key} of the open audio being played, or {path} of an extracted file
    this.paused = null;       // {start, end, key, at}: where play resumes
    this.rec = { devices: [], formats: {}, running: false, tracks: [], recordings: [] };
    this.recFmt = null;       // {format, quality, rate, channels}
    this.recDir = '';
    this.sampDir = '';
    this.ext = { stems: [], enhanced: [] }; // extracted files of the open audio: {path, name, dur, sr, on}
    this.hidden = new Set();  // extracted files removed from the lists with "Clear all" (they stay on disk)
    this.openPath = '';       // extracted file open in the editor
    this.stems = null;        // stems_status(): extra installed, model ready, last job
    this.enh = null;          // enhance_status(): models (installed, downloaded), last "Enhance" job
    this.opts = { fade_in_ms: 1, fade_out_ms: 10, normalize: false, sensitivity: 0.5, devices: null, tab: 'cuts' };
    try { Object.assign(this.opts, JSON.parse(localStorage.getItem(LS_KEY) || '{}')); } catch { /* private mode */ }
    this.player.subscribe((on, id, ended) => {
      if (on) return;
      if (ended) this.paused = null;
      this.playing = null;
      this._syncPlay();
    });
  }

  ensure() {
    if (!this.ready) this.ready = this._init();
    return this.ready;
  }

  async _init() {
    const init = await this.api.sampler_init();
    this.supported = init.supported;
    this.maxS = init.max_seconds;
    this.rec = init.recorder;
    this.recFmt = init.settings.recorder_format;
    this.recDir = init.settings.recorder_dir;
    this.sampDir = init.settings.sampler_dir;
    this._buildShell();
    if (this.rec.running) this._pollRec();
    this.stems = await this.api.stems_status();
    if (this._stemsBusy()) this._pollStems();
    this.enh = await this.api.enhance_status();
    if (this._enhBusy()) this._pollEnh();
    if (init.session) await this._opened(init);
    else this.renderRegions();
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
    const tab = (id, ic, label, cls = '') => `<button class="sp-tab ${cls}" data-tab="${id}" role="tab">${icon(ic)}<span>${label}</span><span class="sp-tab-n"></span></button>`;
    root.innerHTML = `
      <main class="sp-main">
        <div class="sp-filebar">
          ${icon('audio-lines')}
          <span class="sp-path" id="sp-path"></span>
          ${iconBtn('folder-open', t('Choose a sample or an audio track…'), { id: 'sp-choose' })}
        </div>
        <div class="sp-info" id="sp-info"></div>
        <div class="sp-toolbar">
          ${btn(t('Slice on transients'), { icon: 'scissors', id: 'sp-slice' })}
          <span class="sp-sens" title="${t('Sensitivity: higher = more slices')}">
            <span class="hint">${t('Sensitivity')}</span>${slider(0, 1, 0.05, o.sensitivity, { id: 'sp-sens', label: t('Sensitivity') })}
          </span>
          <span class="sp-sep"></span>
          ${btn(t('Extract stems'), { icon: 'layers', id: 'sp-stems', title: t('Separates drums, bass, guitar, vocals and the rest, on this computer') })}
          ${btn(t('Enhance'), { icon: 'sparkles', id: 'sp-enh', cls: 'cs-ai', title: t('AI restoration of the selected region (or of all the audio): high frequencies and compression artefacts, on this computer') })}
        </div>
        <div class="sp-wave-wrap" id="sp-wave-wrap">
          <canvas id="sp-wave" class="sp-wave"></canvas>
          <canvas id="sp-overview" class="sp-overview"></canvas>
          <div class="empty sp-empty" id="sp-empty">
            <div class="empty-title">${t('Record the audio output, or open a file')}</div>
            <div class="empty-sub">${t('Press ● under the waveform to record the outputs chosen in Settings: every output goes into a file. Or choose an audio file or a library sample with the folder button above, or drag it here from {app}. Then drag on the waveform to cut a region (max {max}) or use «Slice on transients». Wheel: zoom · Shift+wheel: scroll.', { app: FILE_MANAGER, max: '<span class="sp-max"></span>' })}</div>
          </div>
        </div>
        <div class="sp-transport">
          ${iconBtn('square', t('Stop'), { id: 'sp-stop' })}
          <wa-button id="sp-play" class="sp-play" variant="brand" size="s" title="${t('Play')}">${icon('play', t('Play'))}</wa-button>
          ${iconBtn('maximize-2', t('Show all the track'), { id: 'sp-fit' })}
          <span class="sp-sep"></span>
          <wa-button id="rc-rec" class="rc-rec" appearance="filled-outlined" size="s">${icon('circle', t('Record'))}</wa-button>
          <span class="rc-clock" id="rc-clock">0:00</span>
          <div class="rc-meters" id="rc-devices"></div>
          <wa-icon name="triangle-alert" class="rc-warn" id="rc-warn" label="${t('Personal use only')}"></wa-icon>
          <wa-tooltip for="rc-warn" placement="top" class="rc-warn-tip">${esc(t(CAPTURE_NOTE))}</wa-tooltip>
          ${settingsLink('sampler', t('Outputs, format and folder'))}
          <span class="spacer"></span>
          <span class="hint" id="sp-view-info"></span>
        </div>
        <div class="sp-ext-head">
          <span class="filter-title">${t('Extractions')} <span id="sp-count"></span></span>
          <div class="sp-tabs" role="tablist">
            ${tab('cuts', 'scissors', t('Cuts'))}${tab('stems', 'layers', t('Stems'))}${tab('enhanced', 'sparkles', t('Enhanced'), 'cs-ai-tab')}
          </div>
          <span class="spacer"></span>
          ${btn(t('Clear all'), { icon: 'trash-2', id: 'sp-clear' })}
          ${btn(`${t('Send to')} ${icon('chevron-down')}`, { icon: 'send', id: 'sp-send' })}
          ${btn(t('Export all'), { variant: 'brand', icon: 'file-down', id: 'sp-export' })}
          <span id="sp-ext-set">${settingsLink('sampler', t('Fades, normalisation and export folder'))}</span>
        </div>
        <div class="sp-regions" id="sp-regions"></div>
      </main>`;
    this.cv = $('#sp-wave');
    this.ov = $('#sp-overview');
    this._bind();
    this._renderMax();
    this.renderInfo();
    this._renderTabs();
    this.renderRegions();
    this._renderRecorder();
    new ResizeObserver(() => this._resize()).observe($('#sp-wave-wrap'));
  }

  _bind() {
    this._bindOpen();
    this._bindRecorder();
    this._bindRest();
  }

  _bindOpen() {
    $('#sp-choose').onclick = () => this.openChooser();
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

  // "Open audio" modal: a file of the computer, a sample of the library, or a recording of this session.
  openChooser() {
    const recs = (this.rec.recordings || []).map((r) => `
      <div class="rc-item sp-rec-row" data-path="${esc(r.path)}" title="${esc(r.path)}">
        <div class="rc-item-name">${esc(r.device)}</div>
        <span class="hint">${clock(r.seconds)} · ${esc(r.format)} · ${mb(r.bytes)}${r.error ? ` · <span class="error">${esc(r.error)}</span>` : ''}</span>
        ${iconBtn('pencil', t('Open in the editor'), { size: 'xs', 'data-act': 'open' })}
        ${iconBtn('folder-open', t('Show in {app}', { app: FILE_MANAGER }), { size: 'xs', 'data-act': 'reveal' })}
      </div>`).join('');
    const choice = (go, ic, label, hint) => `<button class="sp-open-choice" data-go="${go}">${icon(ic)}<b>${label}</b><span class="hint">${hint}</span></button>`;
    const dlg = openDialog('sp-open-dlg', { label: t('Open audio'), width: '560px', body: `
      <div class="sp-open-choices">
        ${choice('file', 'hard-drive', t('Local folder…'), t('An audio file on the computer (wav, aif, flac, mp3, ogg…)'))}
        ${choice('lib', 'library-big', t('Sample library…'), t('A sample or a loop of the ClusterSound library, by folder or by name'))}
      </div>
      <div class="filter-title sp-open-sub">${icon('history')} ${t('Recent recordings')}</div>
      <div class="rc-list">${recs || `<div class="hint">${t('The recordings of this session show up here.')}</div>`}</div>
      <div class="hint">${t('Or drag an audio file from {app} onto the waveform.', { app: FILE_MANAGER })}</div>` });
    dlg.querySelector('.sp-open-choices').onclick = async (e) => {
      const go = e.target.closest('[data-go]')?.dataset.go;
      if (!go) return;
      dlg.close();
      if (go === 'lib') return this.openLibrary();
      this._opened(await this.api.sampler_open_file(null));
    };
    dlg.querySelector('.rc-list').onclick = async (e) => {
      const row = e.target.closest('[data-path]');
      if (!row) return;
      if (e.target.closest('[data-act]')?.dataset.act === 'reveal') return this.api.reveal_path(row.dataset.path);
      dlg.close();
      this._opened(await this.api.recorder_open(row.dataset.path));
    };
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
    $('#sp-stop').onclick = () => this.stop();
    $('#sp-fit').onclick = () => this.setView(0, this.duration);
    $('#sp-slice').onclick = () => this.autoSlice();
    $('#sp-clear').onclick = () => this.clearAll();
    $('#sp-export').onclick = () => this.export();
    $('#sp-send').onclick = (e) => this._sendMenu(e.currentTarget);
    $('#sp-stems').onclick = (e) => this._stemsMenu(e.currentTarget);
    $('#sp-enh').onclick = (e) => this._enhMenu(e.currentTarget);
    $('.sp-tabs').onclick = (e) => {
      const b = e.target.closest('[data-tab]');
      if (b) this.setTab(b.dataset.tab);
    };
    $('#sp-regions').addEventListener('click', (e) => this._rowClick(e));
    $('#sp-regions').addEventListener('change', (e) => {
      const row = e.target.closest('[data-i]');
      if (!row) return;
      const r = this._rows()[+row.dataset.i];
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

  // ---------------------------------------------------------------- open audio
  async _opened(r) {
    if (!r || r.cancelled) return;
    if (r.error) return this._error(r.error);
    this.player.stop();
    this.paused = null;
    this.session = r.session;
    this.maxS = r.max_seconds || this.maxS;
    this.token += 1;
    this.regions = [];
    this.sel = -1;
    this.openPath = r.extraction ? this.openPath : '';
    this.overview = await this.api.sampler_view(0, null, 2000);
    this.detail = null;
    this._renderMax();
    this.renderInfo();
    this.renderRegions();
    this.setView(0, this.duration);
    if (!r.extraction) await this._loadExtractions(); // an extracted file keeps the lists of its source
  }

  // Stems and enhanced files of the open audio, from disk; the ticks of the files already listed are kept.
  async _loadExtractions() {
    const r = await this.api.sampler_extractions();
    if (r.error) return;
    for (const k of ['stems', 'enhanced']) {
      const was = new Map(this.ext[k].map((f) => [f.path, f.on]));
      this.ext[k] = r[k].filter((f) => !this.hidden.has(f.path)).map((f) => ({ ...f, on: was.get(f.path) ?? true }));
    }
    this._renderTabs();
    if (this.opts.tab !== 'cuts') this.renderRegions();
  }

  get duration() { return this.session?.duration || 0; }

  renderInfo() {
    const box = $('#sp-info'), path = $('#sp-path');
    $('#sp-empty').hidden = !!this.session;
    // the marks keep the slashes in place in the right-to-left ellipsis (the start of a long path is cut)
    path.textContent = this.session ? `\u200e${this.session.path || this.session.title}\u200e` : t('No audio open: choose a file or a library sample →');
    path.title = this.session?.path || '';
    path.classList.toggle('none', !this.session);
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

  // The tooltip of the ⋯ next to "Extractions": what the exported samples get, and where they go.
  _renderOptsSummary() {
    const o = this.opts, b = $('#sp-ext-set wa-button');
    if (!b) return;
    b.title = `Fade ${o.fade_in_ms} ms in · ${o.fade_out_ms} ms out${o.normalize ? ` · ${t('normalised to −0.3 dBFS')}` : ''}. `
      + t('Every sample lasts at most {max} s. They go into {folder}, with the provenance of the recording next to them.', { max: this.maxS, folder: this.sampDir });
  }

  _renderMax() {
    document.querySelectorAll('#sampler .sp-max').forEach((el) => { el.textContent = `${this.maxS} s`; });
    this._renderOptsSummary();
  }

  // ---------------------------------------------------------------- recorder
  _bindRecorder() {
    $('#rc-rec').onclick = () => this.toggleRecording();
  }

  // The ticked rows of the tab (with no cuts ticked, all the open audio) onto new audio tracks in Live (M4L device).
  async sendToLive() {
    if (!this.session) return this._error(t('Open a recording first'));
    const rows = this._rows().filter((r) => r.on);
    const b = $('#sp-send');
    b.loading = true;
    toast(rows.length ? t('Sending to Live…') : t('Sending the audio to Live…'));
    let out = null;
    if (this.opts.tab === 'cuts') {
      if (!rows.length) out = await this.api.sampler_send_to_live(null, null, this.opts);
      for (const r of rows) out = await this.api.sampler_send_to_live(r.start, r.end, this.opts);
    } else {
      for (const f of rows) out = await this.api.sampler_send_to_live(null, null, null, f.path);
    }
    b.loading = false;
    if (!out) return;
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
      if (j.state === 'done') { toast(t('Stems ready: {n} files', { n: j.stems.length })); this._jobDone('stems'); }
      if (j.state === 'error') this._error(j.error);
    }, 500);
  }

  // A job finished: its files join the list of the open audio, and the tab blinks once.
  async _jobDone(tab) {
    await this._loadExtractions();
    const b = $(`.sp-tab[data-tab="${tab}"]`);
    b?.classList.remove('pulse');
    void b?.offsetWidth;
    b?.classList.add('pulse');
  }

  _renderStems() {
    const j = this.stems?.job || {};
    document.querySelector('.nav-item[data-tab="sampler"]')?.classList.toggle('busy', j.state === 'running');
    this._renderTabs();
    if (this.opts.tab === 'stems') this.renderRegions();
  }

  // The state of the last job, on top of its tab: progress and Cancel while it works, or why it stopped.
  _jobHtml(tab) {
    if (tab === 'stems') {
      const j = this.stems?.job || {};
      if (j.state === 'downloading') return `<div class="sp-job">${t('Downloading the model…')}</div>`;
      if (j.state === 'running') {
        const pct = Math.round((j.progress || 0) * 100);
        return `<div class="sp-job"><span class="rc-item-name">${esc(j.title)} · ${j.scope === 'region' ? t('region') : t('whole')}</span>
          <div class="sp-meter st-meter"><div style="width:${pct}%"></div></div><span class="hint">${pct}%</span>
          ${btn(t('Cancel'), { size: 'xs', 'data-job': 'cancel' })}</div>`;
      }
      if (j.state === 'cancelled') return `<div class="sp-job hint">${t('Separation cancelled.')}</div>`;
      if (j.state === 'error') return `<div class="sp-job error">${esc(j.error)}</div>`;
      return '';
    }
    const j = this.enh?.job || {};
    if (j.state === 'downloading') return `<div class="sp-job">${t('Downloading the model…')}</div>`;
    if (j.state === 'running') {
      const pct = Math.round((j.progress || 0) * 100);
      const what = `${esc(j.title)} · ${j.scope === 'region' ? t('region, {s} s', { s: j.seconds }) : t('whole')}`;
      return `<div class="sp-job en-item"><span class="rc-item-name">${what}</span>
        <div class="sp-meter st-meter en-meter"><div style="width:${pct}%"></div></div><span class="hint">${pct ? `${pct}%` : t('Loading the model…')}</span>
        ${btn(t('Cancel'), { size: 'xs', 'data-job': 'cancel' })}</div>`;
    }
    if (j.state === 'cancelled') return `<div class="sp-job hint">${t('Enhancement cancelled.')}</div>`;
    if (j.state === 'error') return `<div class="sp-job error">${esc(j.error)}</div>`;
    return '';
  }

  async _cancelJob() {
    if (this.opts.tab === 'stems') this.stems = await this.api.stems_cancel();
    else this.enh = await this.api.enhance_cancel();
  }

  // ---------------------------------------------------------------- enhance
  _enhBusy() { return ['running', 'downloading'].includes(this.enh?.job?.state); }

  _enhModel() {
    const ms = this.enh?.models || [];
    return ms.find((m) => m.key === this.opts.enhModel) || ms.find((m) => m.key === this.enh.default) || ms[0];
  }

  // forceScope 'region' (a cut) or 'file' (an extracted file, at path); none: the selected region or all the audio.
  _enhMenu(anchor, forceScope, path) {
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
    } else if (forceScope === 'file') {
      body = `<div class="hint"><b>${esc(path.split('/').pop())}</b></div>
        <div class="hint">${t('Creates a new «… ({enhanced}).wav» file next to the samples: the original stays as it is.', { enhanced: t('enhanced') })}</div>`;
      go = btn(t('Enhance'), { icon: 'sparkles', cls: 'cs-ai', 'data-go': 'run' });
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
        } else if (forceScope === 'file') {
          out = await this.api.enhance_start('all', null, null, m.key, path);
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
      if (j.state === 'done') { toast(t('Sample enhanced: it is in the «Enhanced» tab')); this._jobDone('enhanced'); }
      if (j.state === 'error') this._error(j.error);
    }, 500);
  }

  _renderEnh() {
    $('#sp-enh')?.toggleAttribute('loading', this.enh?.job?.state === 'running');
    this._renderTabs();
    if (this.opts.tab === 'enhanced') this.renderRegions();
  }

  _selectedDevices() {
    const ids = new Set(this.rec.devices.map((d) => d.id));
    let sel = (this.opts.devices || []).filter((id) => ids.has(id));
    if (!this.opts.devices) sel = [this.rec.devices.find((d) => d.default)?.id || this.rec.devices[0]?.id].filter(Boolean);
    return sel;
  }

  _renderRecorder() {
    this._renderOptsSummary();
    this._renderDevices();
    this._renderRecButton();
    if (this._setBody?.isConnected) this._renderSetDevices();
  }

  // Format and folder of the recordings, for the tooltip of the Record button.
  _recSummary() {
    const f = this.recFmt, spec = this.rec.formats[f.format];
    const lbl = (list, v) => list.find(([k]) => String(k) === String(v))?.[1] ?? v;
    return `${spec.label} · ${lbl(spec.qualities, f.quality)} · ${lbl(this.rec.channels, f.channels)} → ${this.recDir}`;
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

  // In the transport: a small level meter per output that will be recorded (chosen in Settings), live while recording.
  _renderDevices() {
    const box = $('#rc-devices');
    if (!box) return;
    if (!this.rec.devices.length) {
      box.innerHTML = `<span class="hint rc-none" title="${esc(this.rec.hint || '')}">${t('No output can be recorded.')}</span>`;
      return;
    }
    const sel = new Set(this._selectedDevices());
    const tracks = Object.fromEntries(this.rec.tracks.map((tr) => [tr.device, tr]));
    const shown = this.rec.devices.filter((d) => (this.rec.running ? tracks[d.id] : sel.has(d.id)));
    box.innerHTML = shown.map((d) => {
      const tr = this.rec.running ? tracks[d.id] : null;
      const meta = tr ? (tr.error || `${clock(tr.seconds)} · ${mb(tr.bytes)}`)
        : d.sample_rate ? `${t('{n} ch', { n: d.channels })} · ${(d.sample_rate / 1000).toFixed(1).replace('.0', '')} kHz` : (d.note || '');
      const lvl = tr && !tr.error ? Math.min(100, Math.sqrt(tr.level || 0) * 220) : 0;
      return `<div class="rc-meter${tr ? ' on' : ''}${tr?.error ? ' err' : ''}" title="${esc(d.name)}${meta ? ` · ${esc(meta)}` : ''}"><div style="width:${lvl}%"></div></div>`;
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
      + setRow(t('Export folder'), t('Where «Export all» writes the samples, the stems and the enhanced files.'),
        `<span class="set-path" id="set-sp-path" title="${esc(this.sampDir)}">${esc(this.sampDir)}</span>
         <wa-button id="set-sp-pick" size="s" appearance="filled-outlined"><wa-icon slot="start" name="folder-open"></wa-icon>${t('Choose…')}</wa-button>`)
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
    body.querySelector('#set-sp-pick').onclick = async () => {
      const p = await this.api.pick_folder();
      if (!p) return;
      this.sampDir = (await this.api.set_setting('sampler_dir', p)).sampler_dir;
      body.querySelector('#set-sp-path').textContent = this.sampDir;
      body.querySelector('#set-sp-path').title = this.sampDir;
      this._renderOptsSummary();
      this._loadExtractions();
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
    const n = this._selectedDevices().length;
    const live = this.rec.tracks.filter((tr) => !tr.error).length;
    const info = on ? (live === 1 ? t('Recording 1 output…') : t('Recording {n} outputs…', { n: live }))
      : n ? (n === 1 ? t('1 output selected: one file.') : t('{n} outputs selected: one file each.', { n })) : t('Select at least one output.');
    const label = on ? t('Stop') : t('Record the audio output');
    b.innerHTML = icon(on ? 'square' : 'circle', label);
    b.title = `${label} · ${info}\n${this._recSummary()}`;
    b.classList.toggle('on', on);
    b.disabled = !on && !n;
    $('#rc-clock').textContent = clock(on ? this.rec.elapsed : 0);
    $('#rc-clock').classList.toggle('on', on);
    document.querySelector('.nav-item[data-tab="sampler"]')?.classList.toggle('recording', on);
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
    const head = this._main() ? this.playing.start + this.player.currentTime : this.paused ? this.paused.start + this.paused.at : null;
    if (head != null) {
      ctx.fillStyle = this.paused && !this._main() ? 'rgba(255,255,255,.6)' : '#ffffff';
      ctx.fillRect(this._x(head), 0, Math.max(1, dpr), H);
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

  // ---------------------------------------------------------------- extractions (tabs)
  setTab(tab) {
    if (!['cuts', 'stems', 'enhanced'].includes(tab)) tab = 'cuts';
    this.opts.tab = tab;
    this._persist();
    this._renderTabs();
    this.renderRegions();
  }

  // The rows of the active tab: regions (cuts) or extracted files.
  _rows(tab = this.opts.tab) { return tab === 'cuts' ? this.regions : this.ext[tab] || []; }

  _renderTabs() {
    const busy = { stems: this._stemsBusy(), enhanced: this._enhBusy() };
    document.querySelectorAll('#sampler .sp-tab').forEach((b) => {
      const k = b.dataset.tab, n = this._rows(k).length;
      b.classList.toggle('on', k === this.opts.tab);
      b.setAttribute('aria-selected', k === this.opts.tab);
      b.classList.toggle('busy', !!busy[k]);
      b.querySelector('.sp-tab-n').textContent = n || '';
    });
  }

  _renderCount() {
    const rows = this._rows(), on = rows.filter((r) => r.on).length;
    $('#sp-count').textContent = rows.length ? t('({n} of {total} selected)', { n: on, total: rows.length }) : '';
    $('#sp-export').disabled = !on;
    $('#sp-send').disabled = !this.session && !on;
    $('#sp-clear').disabled = !rows.length;
  }

  renderRegions() {
    const box = $('#sp-regions'), tab = this.opts.tab;
    this._renderCount();
    this._renderTabs();
    const job = tab === 'cuts' ? '' : this._jobHtml(tab);
    const rows = this._rows();
    if (!rows.length) {
      const empty = tab === 'cuts' ? (this.session ? t('No cuts: drag on the waveform or use «Slice on transients».') : '')
        : tab === 'stems' ? (!this.stems?.installed ? t('To separate the stems install the extension: see «Extract stems».')
          : this.session ? t('No stems of this audio yet: use «Extract stems».') : '')
          : this.session ? t('Nothing enhanced from this audio yet: use «Enhance» on the audio, on a cut or on a stem.') : '';
      box.innerHTML = `${job}<div class="hint sp-regions-empty">${empty}</div>`;
      return;
    }
    const acts = (ai) => `
        ${iconBtn('play', t('Listen'), { 'data-act': 'play' })}
        ${iconBtn('scan-search', tab === 'cuts' ? t('Show on the waveform') : t('Open its waveform in the editor'), { 'data-act': 'zoom' })}
        ${ai ? iconBtn('sparkles', t('Enhance with AI'), { 'data-act': 'enhance', cls: 'cs-ai-icon' }) : '<span></span>'}
        ${iconBtn('send', t('Send to the Sequencer or the Drum Rack'), { 'data-act': 'send' })}`;
    if (tab === 'cuts') {
      box.innerHTML = this.regions.map((r, i) => `
        <div class="sp-row${i === this.sel ? ' sel' : ''}" data-i="${i}">
          ${check('', r.on, { label: t('Select') })}
          <span class="sp-num">${i + 1}</span>
          <wa-input size="s" value="${esc(r.name)}" placeholder="${esc(this._defaultName(i))}" label="${t('Name')}"></wa-input>
          <span class="sp-time sp-start">${fmt(r.start)}</span>
          <span class="sp-time ${r.end - r.start >= this.maxS - 1e-3 ? 'error' : ''}">${fmt(r.end - r.start)}</span>
          ${acts(true)}
          ${iconBtn('x', t('Delete'), { 'data-act': 'del' })}
        </div>`).join('');
      return;
    }
    box.innerHTML = job + rows.map((f, i) => `
      <div class="sp-row sp-file-row${f.path === this.openPath ? ' sel' : ''}${tab === 'enhanced' ? ' en-row' : ''}" data-i="${i}" title="${esc(f.path)}">
        ${check('', f.on, { label: t('Select') })}
        <span class="sp-num">${i + 1}</span>
        <span class="sp-file-name">${esc(f.name)}</span>
        <span class="sp-time sp-start">${f.sr ? `${(f.sr / 1000).toFixed(1)} kHz` : ''}</span>
        <span class="sp-time">${fmt(f.dur)}</span>
        ${acts(tab === 'stems')}
        ${iconBtn('folder-open', t('Show in {app}', { app: FILE_MANAGER }), { 'data-act': 'reveal' })}
      </div>`).join('');
  }

  _defaultName(i) { return `${this.session?.title || 'sample'} - ${String(i + 1).padStart(2, '0')}`; }

  async _rowClick(e) {
    if (e.target.closest('[data-job]')) return this._cancelJob();
    const row = e.target.closest('[data-i]');
    if (!row) return;
    const i = +row.dataset.i, act = e.target.closest('[data-act]')?.dataset.act;
    const anchor = () => $(`#sp-regions [data-i="${i}"] [data-act="${act}"]`); // the row may have been re-rendered
    if (this.opts.tab !== 'cuts') {
      const f = this._rows()[i];
      if (act === 'reveal') return this.api.reveal_path(f.path);
      if (act === 'zoom') {
        this.openPath = f.path;
        return this._opened(await this.api.sampler_open_extraction(f.path));
      }
      if (act === 'enhance') return this._enhMenu(anchor(), 'file', f.path);
      if (act === 'send') return this._sendOne(this._fileRef(f), anchor());
      if (e.target.closest('wa-checkbox')) return;
      return this.playFile(f.path);
    }
    if (act === 'del') return this.removeRegion(i);
    if (act === 'zoom') {
      const r = this.regions[i], pad = Math.max(0.05, (r.end - r.start) * 0.25);
      this.sel = i;
      this.renderRegions();
      return this.setView(r.start - pad, r.end + pad);
    }
    if (act === 'play') return this.playRegion(i);
    if (act === 'send') {
      const refs = await this._regionRefs([i], e.target.closest('wa-button'));
      return refs?.[0] && this._sendOne(refs[0], anchor());
    }
    if (act === 'enhance') {
      this.sel = i;
      this.renderRegions();
      this.draw();
      return this._enhMenu(anchor(), 'region');
    }
    if (e.target.closest('wa-input, wa-checkbox')) return;
    this.playRegion(i);
  }

  // The "Send" menu of the library (Sequencer bus or Drum Rack group), under the row's button.
  _sendOne(ref, anchor) {
    if (!this.onSend || !anchor) return;
    const r = anchor.getBoundingClientRect();
    this.onSend(ref, r.left, r.bottom + 4);
  }

  _fileRef(f) { return { kind: 'file', path: f.path, name: f.path.split('/').pop(), cls: null, root: null, dur: f.dur }; }

  // ---------------------------------------------------------------- header actions
  clearAll() {
    const rows = this._rows();
    if (!rows.length) return;
    const tab = this.opts.tab;
    const msg = tab === 'cuts' ? t('Remove all the {n} cuts of this audio?', { n: rows.length })
      : t('Remove the {n} files from the list? They stay on disk.', { n: rows.length });
    const dlg = openDialog('sp-clear-dlg', { label: t('Clear all'), width: '420px', body: `<p>${msg}</p>`,
      footer: `${btn(t('Cancel'), { 'data-go': 'no' })}${btn(t('Clear all'), { variant: 'danger', icon: 'trash-2', 'data-go': 'yes' })}` });
    dlg.querySelector('.modal-actions').onclick = (e) => {
      const go = e.target.closest('[data-go]')?.dataset.go;
      if (!go) return;
      dlg.close();
      if (go !== 'yes') return;
      if (tab === 'cuts') { this.regions = []; this.sel = -1; this.draw(); } else {
        for (const f of rows) this.hidden.add(f.path);
        this.ext[tab] = [];
      }
      this.renderRegions();
    };
  }

  // "Send to ▾": the ticked rows to Live, to the Drum Rack or to a Sequencer bus.
  async _sendMenu(anchor) {
    const n = this._rows().filter((r) => r.on).length;
    const item = (go, ic, label, hint, dis) => `<button class="sp-send-item" data-go="${go}"${dis ? ' disabled' : ''}>${icon(ic)}<span><b>${label}</b><span class="hint">${hint}</span></span></button>`;
    const pop = showPopover(anchor, `<div class="pop-title">${icon('send')} ${t('Send to')}</div>
      <div class="sp-send-list">
        ${item('live', 'music', 'Ableton Live', n > 1 ? t('{n} new audio tracks', { n }) : n ? t('A new audio track') : t('All the open audio, on a new audio track'), !this.session && !n)}
        ${item('rack', 'layout-grid', 'Drum Rack', t('On the free pads, from the selected one'), !n)}
        ${item('seq', 'audio-lines', 'Sequencer', t('As new layers of a bus'), !n || !this.getBuses)}
      </div><div class="sp-send-buses"></div>`);
    pop.onclick = async (e) => {
      const b = e.target.closest('[data-go], [data-bus]');
      if (!b || b.disabled) return;
      if (b.dataset.bus) { pop.close(); return this.sendToBus(b.dataset.bus); }
      const go = b.dataset.go;
      if (go === 'live') { pop.close(); return this.sendToLive(); }
      if (go === 'rack') { pop.close(); return this.sendToRack(); }
      const box = pop.querySelector('.sp-send-buses');
      box.innerHTML = `<div class="hint">${t('Loading…')}</div>`;
      const buses = await this.getBuses();
      box.innerHTML = `<div class="hint">${t('Bus')}</div>` + buses.map((x) =>
        `<button class="sp-send-bus" data-bus="${esc(x.id)}"><span class="sp-bus-dot" style="background:${esc(x.color || 'var(--text-3)')}"></span>${esc(x.label)}</button>`).join('');
    };
  }

  // ---------------------------------------------------------------- playback
  _dropAudio() { this.audioRev += 1; } // the region audio changed: re-render it on next play

  _main() { return !!this.playing && !this.playing.path && this.player.playing; } // the open audio is playing

  async _playSpan(start, end, key, at = 0) {
    const buf = await this.player.load(`sp:${this.token}.${this.audioRev}:${key}:${start.toFixed(4)}-${end.toFixed(4)}`,
      () => this.api.sampler_audio(start, end, this.opts));
    if (!buf) return;
    this.paused = null;
    this.player.play(`sampler:${key}`, buf, at);
    this.playing = { start, end, key };
    this._syncPlay();
    const tick = () => { if (this.playing && !this.playing.path) { this.draw(); requestAnimationFrame(tick); } };
    requestAnimationFrame(tick);
  }

  async playFile(path) {
    if (this.playing?.path === path && this.player.playing) { this.player.stop(); return; }
    const buf = await this.player.load(`spf:${path}`, () => this.api.sample_audio({ kind: 'file', path }));
    if (!buf) return this._error(t('file not found'));
    this.paused = null;
    this.player.play(`sampler:f:${path}`, buf, 0);
    this.playing = { path };
    this._syncPlay();
  }

  playRegion(i) {
    const r = this.regions[i];
    if (!r) return;
    this.sel = i;
    this.renderRegions();
    this.draw();
    this._playSpan(r.start, r.end, `r${i}`);
  }

  // Play / pause: pausing keeps the position, play resumes from there.
  togglePlay() {
    if (this._main()) {
      const { start, end, key } = this.playing;
      this.paused = { start, end, key, at: this.player.currentTime };
      this.player.stop();
      return;
    }
    if (!this.session) return;
    const p = this.paused;
    if (p) return this._playSpan(p.start, p.end, p.key, p.at);
    if (this.sel >= 0) return this.playRegion(this.sel);
    this._playSpan(this.view.start, Math.min(this.view.end, this.view.start + 60), 'view');
  }

  stop() {
    this.paused = null;
    this.player.stop();
    this._syncPlay();
  }

  _syncPlay() {
    const b = $('#sp-play'), on = this._main();
    if (b) {
      const label = on ? t('Pause') : t('Play');
      b.innerHTML = icon(on ? 'pause' : 'play', label);
      b.title = `${label} (${t('Space')})`;
    }
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

  async _regionRefs(idx, button) {
    const files = await this._files(idx, button);
    if (!files) return null;
    return idx.map((i, k) => files[k] && {
      kind: 'file', path: files[k], name: files[k].split('/').pop(), cls: null, root: null,
      dur: +(this.regions[i].end - this.regions[i].start).toFixed(3) }).filter(Boolean);
  }

  // Ticked rows of the active tab as sample refs (cuts are exported first).
  async _checkedRefs(button) {
    if (this.opts.tab === 'cuts') return this._regionRefs(this._checked(), button);
    return this._rows().filter((f) => f.on).map((f) => this._fileRef(f));
  }

  _showExported(folder, first) {
    if (!first) return;
    const head = $('#sp-regions-head-msg') || Object.assign(document.createElement('div'), { id: 'sp-regions-head-msg', className: 'hint sp-exported' });
    head.innerHTML = t('Exported to {folder}', { folder: `<a href="#">${esc(folder)}</a>` });
    head.querySelector('a').onclick = (e) => { e.preventDefault(); this.api.reveal_path(first); };
    $('#sp-regions').before(head);
  }

  _checked() { return this.regions.map((r, i) => (r.on ? i : -1)).filter((i) => i >= 0); }

  // "Export all": the ticked rows of the tab into the export folder chosen in Settings.
  async export() {
    const b = $('#sp-export');
    let n;
    if (this.opts.tab === 'cuts') {
      const idx = this._checked();
      if (!idx.length) return;
      const files = await this._files(idx, b);
      if (!files) return;
      n = files.filter(Boolean).length;
    } else {
      const paths = this._rows().filter((f) => f.on).map((f) => f.path);
      if (!paths.length) return;
      b.loading = true;
      const r = await this.api.sampler_export_files(paths);
      b.loading = false;
      if (r.error) return this._error(r.error);
      this._showExported(r.folder, r.paths[0]);
      if (r.in_library) toast(t('The samples are in the library: analysing them'));
      n = r.paths.length;
    }
    toast(n === 1 ? t('1 sample exported') : t('{n} samples exported', { n }));
  }

  // Ticked rows onto free Drum Rack pads, from the rack's selected pad on, to play them there.
  async sendToRack() {
    if (!this.onSendToRack) return;
    const refs = await this._checkedRefs($('#sp-send'));
    if (refs?.length) this.onSendToRack(refs);
  }

  async sendToBus(bus) {
    if (!this.onSendToBus) return;
    const refs = await this._checkedRefs($('#sp-send'));
    if (refs?.length) this.onSendToBus(refs, bus);
  }
}
