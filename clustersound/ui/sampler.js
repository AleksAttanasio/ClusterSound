// "Recorder" screen: a file bar on top (the shown track and a button to open another one), one tab per open track
// over the waveform, a media-player transport under it (play/pause from the cursor, stop, show all, record the
// audio output), then the "Extractions" of all the open tracks in three tabs: Cuts (regions marked by hand or on
// transients), Stems and Enhanced (files already made from them, found again on disk).
import { btn, iconBtn, slider, check, num, select, seg, text, icon, openDialog, FILE_MANAGER } from './kit.js';
import { toast, showPopover } from './sendmenu.js';
import { liveToast } from './live.js';
import { settingsLink, setRow, savedFlash } from './settings.js';
import { t } from './i18n.js';

const $ = (s, root = document) => root.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LS_KEY = 'clustersound.sampler';
const STEM_DRAG = 'application/x-clustersound-stem';
const EDGE_PX = 6;         // grab distance of a region edge
const MIN_VIEW_S = 0.02;   // deepest zoom
const PLAY_BLOCK_S = 30;   // a track plays in blocks this long (rendered by the backend one at a time)
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
    this.tracks = [];         // open tracks (tabs), see _track(); the shown one is this.cur
    this.cur = null;          // session, regions, sel, view, overview, detail and cursor read through it (see TRACK)
    this.token = 0;           // bumps when another track is shown (late peaks are dropped)
    this.audioRev = 0;        // bumps when fades / normalisation change (player cache keys)
    this.maxS = 30;
    this.drag = null;
    this.playing = null;      // {sid, start, end, key} of a track being played, or {path} of an extracted file
    this.rec = { devices: [], formats: {}, running: false, tracks: [], recordings: [] };
    this.recFmt = null;       // {format, quality, rate, channels}
    this.recDir = '';
    this.sampDir = '';
    this.ext = { stems: [], enhanced: [] }; // extracted files of the open tracks: {path, name, dur, sr, sid, source, on}
    this.hidden = new Set();  // extracted files removed from the lists with "Clear all" (they stay on disk)
    this.collapsed = new Set(); // groups of stems shown closed: "sid|name"
    this.libCopies = new Map();  // extracted file -> its copy sent to the library (shown in the Finder until it is saved)
    this.stems = null;        // stems_status(): extra installed, model ready, last job
    this.enh = null;          // enhance_status(): models (installed, downloaded), last "Enhance" job
    this.opts = { fade_in_ms: 1, fade_out_ms: 10, normalize: false, sensitivity: 0.5, devices: null, tab: 'cuts' };
    try { Object.assign(this.opts, JSON.parse(localStorage.getItem(LS_KEY) || '{}')); } catch { /* private mode */ }
    this.player.subscribe((on, id, ended) => {
      if (on) return;
      const p = this.playing;
      this.playing = null;
      if (ended && p?.key === 'cur') { // the track goes on in the next block, or the cursor goes back to the start
        const tr = this.tracks.find((x) => x.sid === p.sid);
        if (tr && p.end < tr.session.duration - 1e-3) { this._playFrom(tr, p.end); return; }
        if (tr) tr.cursor = 0;
      }
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
    else { this._renderTracks(); this.renderRegions(); }
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
    const tab = (id, ic, label, cls = '') => `<button class="sp-tab ${cls}" data-tab="${id}" role="tab">${icon(ic)}<span>${label}</span><span class="sp-tab-n"></span></button>`;
    root.innerHTML = `
      <main class="sp-main">
        <div class="sp-filebar">
          ${icon('audio-lines')}
          <span class="sp-path" id="sp-path" role="button" tabindex="0" title="${t('Choose a sample or an audio track…')}"></span>
          ${iconBtn('folder-open', t('Choose a sample or an audio track…'), { id: 'sp-choose' })}
        </div>
        <div class="sp-tracks" id="sp-tracks" role="tablist"></div>
        <div class="sp-info" id="sp-info"></div>
        <div class="sp-toolbar">
          <span class="sp-slice">${btn(t('Slice on transients'), { icon: 'scissors', id: 'sp-slice' })}${iconBtn('ellipsis', t('Sensitivity of the slicing'), { id: 'sp-slice-more' })}</span>
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
          <span></span>
          <div class="sp-transport-mid">
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
          </div>
          <span class="hint sp-view-info" id="sp-view-info"></span>
        </div>
        <div class="sp-ext-head">
          <span class="filter-title">${t('Extractions')} <span id="sp-count"></span></span>
          <div class="sp-tabs" role="tablist">
            ${tab('cuts', 'scissors', t('Cuts'))}${tab('stems', 'layers', t('Stems'))}${tab('enhanced', 'sparkles', t('Enhanced'), 'cs-ai-tab')}
          </div>
          <span class="spacer"></span>
          ${btn(t('Clear all'), { icon: 'trash-2', id: 'sp-clear' })}
          ${btn(`${t('Send to')} ${icon('chevron-down')}`, { icon: 'arrow-right', id: 'sp-send' })}
          ${btn(t('Export all'), { variant: 'brand', icon: 'file-down', id: 'sp-export', title: t('Saves the ticked rows in the export folder: new cuts, stems and enhanced files are temporary until then, and are deleted when ClusterSound closes') })}
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
    // the whole bar opens the chooser too
    $('#sp-path').onclick = () => this.openChooser();
    $('#sp-path').onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.openChooser(); } };
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
    $('#sp-slice-more').onclick = (e) => this._sliceMenu(e.currentTarget);
    $('#sp-tracks').onclick = (e) => {
      const b = e.target.closest('[data-sid]');
      if (!b) return;
      if (e.target.closest('[data-close]')) return this.closeTrack(b.dataset.sid);
      if (b.dataset.sid !== this.cur?.sid) this.selectTrack(b.dataset.sid);
    };
    $('#sp-tracks').addEventListener('auxclick', (e) => { // middle click closes, like a browser tab
      const b = e.target.closest('[data-sid]');
      if (b && e.button === 1) this.closeTrack(b.dataset.sid);
    });
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
      const set = e.target.closest('[data-set]');
      if (set && e.target.matches('[data-set-check]')) { // tick or untick every stem of the group
        const st = this._stemSets().find((x) => `${this.ext.stems[x.idx[0]].sid}|${x.name}` === set.dataset.set);
        st?.idx.forEach((i) => { this.ext.stems[i].on = e.target.checked; });
        return this.renderRegions();
      }
      const row = e.target.closest('[data-i]');
      if (!row) return;
      const r = this._rows()[+row.dataset.i];
      if (!r) return;
      if (e.target.matches('wa-checkbox')) r.on = e.target.checked;
      if (e.target.matches('wa-input')) r.name = e.target.value;
      if (this.opts.tab === 'stems') return this.renderRegions(); // the tick of its group follows
      this._renderCount();
    });
    // waveform
    this.cv.addEventListener('wheel', (e) => this._wheel(e), { passive: false });
    this.cv.addEventListener('pointerdown', (e) => this._down(e));
    this.cv.addEventListener('pointermove', (e) => this._move(e));
    this.cv.addEventListener('pointerup', (e) => this._up(e));
    this.cv.addEventListener('dblclick', (e) => {
      const i = this._regionAt(this._time(e));
      if (i >= 0) this.playRegion(this.cur, i);
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
      this.playRegion(this.cur, i);
      return true;
    }
    return false;
  }

  // Sensitivity of «Slice on transients», in a menu next to it.
  _sliceMenu(anchor) {
    const pop = showPopover(anchor, `<div class="pop-title">${icon('scissors')} ${t('Slice on transients')}</div>
      <div class="sp-sens"><span class="hint">${t('Sensitivity')}</span>${slider(0, 1, 0.05, this.opts.sensitivity, { id: 'sp-sens', label: t('Sensitivity') })}
        <span class="hint sp-sens-v">${Math.round(this.opts.sensitivity * 100)}%</span></div>
      <div class="hint">${t('Sensitivity: higher = more slices')}</div>`);
    const sl = pop.querySelector('#sp-sens');
    sl.addEventListener('input', () => { pop.querySelector('.sp-sens-v').textContent = `${Math.round(sl.value * 100)}%`; });
    sl.addEventListener('change', () => { this.opts.sensitivity = +sl.value; this._persist(); });
  }

  _error(msg) {
    toast(msg.length > 140 ? msg.slice(0, 137) + '…' : msg);
    const info = $('#sp-info');
    if (info && msg.length > 140) info.innerHTML = `<div class="sp-error">${icon('triangle-alert')} ${esc(msg)}</div>`;
  }

  // ---------------------------------------------------------------- open tracks (tabs)
  // r: a backend answer with the shown session and every tab. A new session gets its track, then it is shown.
  async _opened(r) {
    if (!r || r.cancelled) return;
    if (r.error) return this._error(r.error);
    this.maxS = r.max_seconds || this.maxS;
    // the tabs follow the backend's: new ones get a track, closed ones lose it
    const old = new Map(this.tracks.map((x) => [x.sid, x]));
    this.tracks = (r.tabs || []).map((s) => old.get(s.sid)
      || { sid: s.sid, session: s, regions: [], sel: -1, view: null, overview: null, detail: null, cursor: 0 });
    await this._show(r.session ? this.tracks.find((x) => x.sid === r.session.sid) : null);
    await this._loadExtractions();
  }

  // Show a track (its session is the shown one in the backend already).
  async _show(tr) {
    if (this._main()) this.player.stop();
    this.cur = tr;
    this.token += 1;
    if (tr && !tr.overview) tr.overview = await this.api.sampler_view(0, null, 2000);
    if (tr) tr.detail = null;
    this._renderMax();
    this.renderInfo();
    this._renderTracks();
    this.renderRegions();
    if (tr) this.setView(tr.view?.start ?? 0, tr.view?.end ?? tr.session.duration);
    else { $('#sp-view-info').textContent = ''; this.draw(); }
    this._syncPlay();
  }

  async selectTrack(sid) {
    const tr = this.tracks.find((x) => x.sid === sid);
    if (!tr) return;
    const r = await this.api.sampler_select(sid);
    if (r.error) return this._error(r.error);
    await this._show(tr);
  }

  async closeTrack(sid) {
    const tr = this.tracks.find((x) => x.sid === sid);
    if (!tr) return;
    const unsaved = tr.regions.filter((x) => !x.file).length;
    if (unsaved && !(await this._confirm(t('Close the track'), (unsaved === 1 ? t('Close «{title}»? Its cut not exported yet is lost.', { title: esc(tr.session.title) })
      : t('Close «{title}»? Its {n} cuts not exported yet are lost.', { title: esc(tr.session.title), n: unsaved })), t('Close')))) return;
    if (this.playing?.sid === sid) this.player.stop();
    await this._opened(await this.api.sampler_close(sid));
  }

  // A small yes/no dialog; resolves to true on yes.
  async _confirm(label, msg, yes) {
    return (await this._ask(label, msg, [['yes', yes, 'danger']])) === 'yes';
  }

  // A small dialog with Cancel and some choices [[go, label, variant]]; resolves to the chosen go, null on Cancel.
  _ask(label, msg, choices) {
    return new Promise((done) => {
      let answer = null;
      const dlg = openDialog('sp-confirm-dlg', { label, width: '420px', body: `<p>${msg}</p>`, onHide: () => done(answer),
        footer: `${btn(t('Cancel'), { 'data-go': 'no' })}${choices.map(([go, l, variant]) => btn(l, { variant, 'data-go': go })).join('')}` });
      dlg.querySelector('.modal-actions').onclick = (e) => {
        const go = e.target.closest('[data-go]')?.dataset.go;
        if (!go) return;
        answer = go === 'no' ? null : go;
        dlg.close();
      };
    });
  }

  _renderTracks() {
    const box = $('#sp-tracks');
    const ic = (x) => (x.session.parent ? 'layers' : x.session.origin === 'capture' ? 'mic' : 'audio-lines');
    box.innerHTML = this.tracks.map((x) => `
      <div class="sp-track${x === this.cur ? ' on' : ''}" data-sid="${x.sid}" role="tab" aria-selected="${x === this.cur}" title="${esc(x.session.path || x.session.title)}">
        ${icon(ic(x))}<span class="sp-track-name">${esc(x.session.title)}</span>
        ${x.regions.length ? `<span class="sp-tab-n">${x.regions.length}</span>` : ''}
        <button class="sp-track-x" data-close title="${esc(t('Close'))}">×</button>
      </div>`).join('') + `<button class="sp-track sp-track-add${this.tracks.length ? '' : ' alone'}" id="sp-track-add" title="${esc(t('Open another track…'))}">${icon('plus')}</button>`;
    $('#sp-track-add').onclick = () => this.openChooser();
  }

  // Stems and enhanced files of the open tracks, from disk; the ticks of the files already listed are kept.
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
    path.title = this.session?.path ? `${this.session.path}\n${t('Click to open another track')}` : t('Choose a sample or an audio track…');
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

  // ---------------------------------------------------------------- stems
  _stemsBusy() { return ['running', 'downloading'].includes(this.stems?.job?.state); }

  // target: none (the shown track: all of it or its selected region), {sid, start, end, label} (a cut of any
  // track) or {path, label} (an extracted file, e.g. an enhanced one).
  _stemsMenu(anchor, target = null) {
    const st = this.stems;
    if (!target && !this.session) return this._error(t('Open a recording first'));
    const r = this.regions[this.sel];
    let body;
    if (!st?.installed) {
      body = `<div class="hint">${t('The separation runs on this computer with Demucs (PyTorch), an extension to install once:')}</div>
        <code class="st-code">${esc(st?.install_hint || '')}</code>`;
    } else if (!st.model_ready) {
      body = `<div class="hint">${t('It needs the Demucs model (~{mb} MB), downloaded only once. After that the separation works offline: the audio never leaves the computer.', { mb: st.model_mb })}</div>
        <div class="pop-actions">${btn(t('Download the model'), { variant: 'brand', icon: 'download', 'data-go': 'download' })}</div>`;
    } else {
      const scope = r && this.opts.stemScope === 'region' ? 'region' : 'all';
      body = `<div class="hint">${t('Drag the stems into the tracks: each track is one WAV file, with its stems summed. A stem can go into several tracks.')}</div>
        <div class="st-board"></div>
        <div class="hint st-rest"></div>
        ${target ? `<div class="hint"><b>${esc(target.label)}</b></div>`
          : seg([['all', t('Whole recording')], ['region', t('Selected region'), { disabled: !r, title: r ? `${fmt(r.start)} – ${fmt(r.end)}` : t('Select a region') }]],
            scope, { 'data-o': 'scope', cls: 'st-scope' })}
        <div class="pop-actions">${btn(t('Extract'), { variant: 'brand', icon: 'audio-lines', 'data-go': 'extract' })}</div>`;
    }
    const pop = showPopover(anchor, `<div class="pop-title">${icon('audio-lines')} ${t('Extract stems')}</div>${body}`,
      st?.installed && st.model_ready ? 'st-pop' : '');
    const tracks = st?.installed && st.model_ready ? this._stemTracks() : [];
    if (pop.querySelector('.st-board')) this._stemBoard(pop, tracks);
    pop.querySelectorAll('[data-go]').forEach((b) => {
      b.onclick = async () => {
        if (b.disabled) return;
        if (b.dataset.go === 'download') {
          pop.close();
          return this._stemsStarted(await this.api.stems_download_model());
        }
        const scope = target ? null : pop.querySelector('[data-o=scope]').value === 'region' && r ? 'region' : 'all';
        if (scope) Object.assign(this.opts, { stemScope: scope });
        this._persist();
        pop.close();
        const groups = await this._stemDuplicates(tracks);
        if (!groups) return;
        let out;
        if (target?.path) out = await this.api.stems_start('all', null, null, null, null, target.path, groups);
        else if (target) out = await this.api.stems_start('region', target.start, target.end, null, target.sid, null, groups);
        else out = await this.api.stems_start(scope, scope === 'region' ? r.start : null, scope === 'region' ? r.end : null, null, null, null, groups);
        this._stemsStarted(out);
      };
    });
  }

  _stemsStarted(out) {
    this.stems = out;
    if (out.error) this._error(out.error);
    this._renderStems();
    if (this._stemsBusy()) this._pollStems();
  }

  // The tracks of the last «Extract stems» (each a list of stem keys); the first time one per stem, as when they
  // were chosen one by one (stemKeys), so «Other» gets the rest.
  _stemTracks() {
    const all = this.stems.stems, known = new Set(all.map((x) => x.key));
    const saved = Array.isArray(this.opts.stemTracks) ? this.opts.stemTracks
      : (this.opts.stemKeys || all.filter((x) => x.choosable).map((x) => x.key)).map((k) => [k]);
    return saved.map((g) => all.map((x) => x.key).filter((k) => g.includes(k) && known.has(k))).filter((g) => g.length);
  }

  // The stems on the left, dragged (copied) into the track columns on the right; the last column, «New Track»,
  // becomes a track when a stem is dropped on it. tracks is edited in place and saved at every change.
  _stemBoard(pop, tracks) {
    const all = this.stems.stems, label = Object.fromEntries(all.map((x) => [x.key, x.label]));
    const order = all.map((x) => x.key);
    const name = (g) => g.map((k) => label[k]).join(' + ');
    const board = pop.querySelector('.st-board');
    const render = () => {
      const chip = (k, i) => `<span class="st-chip"${i == null ? ` draggable="true" data-stem="${k}"` : ''}>${esc(label[k])}${
        i == null ? '' : `<button class="st-x" data-del="${i}" data-key="${k}" title="${esc(t('Remove {stem}', { stem: label[k] }))}">${icon('x')}</button>`}</span>`;
      board.innerHTML = `<div class="st-palette">${order.map((k) => chip(k)).join('')}</div>
        <div class="st-cols">${tracks.map((g, i) => `<div class="st-col" data-col="${i}">
            <div class="st-col-head"><span class="st-col-name" title="${esc(name(g))}">${esc(name(g))}</span>
              <button class="st-x" data-del="${i}" title="${esc(t('Remove the track'))}">${icon('x')}</button></div>
            <div class="st-col-body">${g.map((k) => chip(k, i)).join('')}</div></div>`).join('')}
          <div class="st-col ghost" data-col="new"><div class="st-col-head"><span class="st-col-name">${t('New Track')}</span></div>
            <div class="st-col-body"><span class="hint">${t('Drag a stem here')}</span></div></div></div>`;
      const used = new Set(tracks.flat()), rest = order.filter((k) => !used.has(k));
      const restName = `<b>${esc(used.has('other') ? t('Rest') : label.other)}</b>`;
      pop.querySelector('.st-rest').innerHTML = !rest.length ? ''
        : rest.join() === 'other' ? t('+ «{name}», in no track, so nothing is lost.', { name: restName })
          : t('+ «{name}»: {stems}, in no track, so nothing is lost.', { name: restName, stems: esc(rest.map((k) => label[k]).join(', ')) });
      pop.querySelector('[data-go=extract]').disabled = !tracks.length;
    };
    const changed = () => {
      this.opts.stemTracks = tracks.map((g) => [...g]);
      this._persist();
      render();
    };
    board.addEventListener('dragstart', (e) => {
      const k = e.target.closest?.('[data-stem]')?.dataset.stem;
      if (!k) return;
      e.dataTransfer.setData(STEM_DRAG, k);
      e.dataTransfer.effectAllowed = 'copy';
    });
    const colOf = (e) => (e.dataTransfer.types.includes(STEM_DRAG) ? e.target.closest?.('.st-col') : null);
    board.addEventListener('dragover', (e) => {
      const col = colOf(e);
      if (!col) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
      board.querySelectorAll('.st-col.over').forEach((c) => c !== col && c.classList.remove('over'));
      col.classList.add('over');
    });
    board.addEventListener('dragleave', (e) => {
      const col = e.target.closest?.('.st-col');
      if (col && !col.contains(e.relatedTarget)) col.classList.remove('over');
    });
    board.addEventListener('drop', (e) => {
      const col = colOf(e), k = e.dataTransfer.getData(STEM_DRAG);
      if (!col || !label[k]) return;
      e.preventDefault();
      if (col.dataset.col === 'new') tracks.push([k]);
      else {
        const g = tracks[+col.dataset.col];
        if (g.includes(k)) return render();
        g.push(k);
        g.sort((x, y) => order.indexOf(x) - order.indexOf(y));
      }
      changed();
    });
    board.addEventListener('click', (e) => {
      const x = e.target.closest('[data-del]');
      if (!x) return;
      const i = +x.dataset.del;
      if (x.dataset.key) tracks[i] = tracks[i].filter((k) => k !== x.dataset.key);
      if (!x.dataset.key || !tracks[i].length) tracks.splice(i, 1);
      changed();
    });
    render();
  }

  // Tracks with the same stems would make the same file: ask whether to make them all or one of each.
  // Resolves to the groups to send, or null when cancelled.
  async _stemDuplicates(tracks) {
    const label = Object.fromEntries(this.stems.stems.map((x) => [x.key, x.label]));
    const sig = (g) => [...g].sort().join('+'), seen = new Map();
    tracks.forEach((g) => seen.set(sig(g), (seen.get(sig(g)) || 0) + 1));
    const twins = tracks.filter((g, i) => seen.get(sig(g)) > 1 && tracks.findIndex((h) => sig(h) === sig(g)) === i);
    if (!twins.length) return tracks;
    const names = twins.map((g) => `<b>${esc(g.map((k) => label[k]).join(' + '))}</b> ×${seen.get(sig(g))}`).join(', ');
    const go = await this._ask(t('Repeated tracks'),
      t('Some tracks have the same stems: {names}. Make them all anyway, or only one of each?', { names }),
      [['all', t('Make them all')], ['one', t('One of each'), 'brand']]);
    if (go === 'one') return tracks.filter((g, i) => tracks.findIndex((h) => sig(h) === sig(g)) === i);
    return go === 'all' ? tracks : null;
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

  // target: as in _stemsMenu (none: the shown track, all of it or its selected region).
  _enhMenu(anchor, target = null) {
    const st = this.enh;
    if (!target && !this.session) return this._error(t('Open a recording first'));
    if (!st?.models?.length) return;
    const r = this.regions[this.sel];
    const m = this._enhModel();
    const scope = r ? 'region' : 'all';
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
    } else if (target) {
      body = `<div class="hint"><b>${esc(target.label)}</b></div>
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
        } else if (target?.path) {
          out = await this.api.enhance_start('all', null, null, m.key, target.path);
        } else if (target) {
          out = await this.api.enhance_start('region', target.start, target.end, m.key, null, target.sid);
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
    // only when the state changes: the meters poll every 200 ms, and a click whose icon was just replaced is lost
    if (b.dataset.on !== String(on)) { b.innerHTML = icon(on ? 'square' : 'circle', label); b.dataset.on = on; }
    b.title = `${label} · ${info}\n${this._recSummary()}`;
    b.classList.toggle('on', on);
    b.disabled = !on && !n;
    $('#rc-clock').textContent = clock(on ? this.rec.elapsed : 0);
    $('#rc-clock').classList.toggle('on', on);
    document.querySelector('.nav-item[data-tab="sampler"]')?.classList.toggle('recording', on);
  }

  async toggleRecording() {
    const b = $('#rc-rec');
    if (b.loading) return;
    // a meter poll already on its way would bring back the state from before the click: it is dropped
    clearTimeout(this.recTimer);
    this.recGen = (this.recGen || 0) + 1;
    const was = this.rec.running;
    b.loading = true;
    let st;
    try {
      st = was ? await this.api.recorder_stop() : await this.api.recorder_start(this._selectedDevices(), this.recFmt);
    } catch (e) {
      st = { error: String(e?.message || e) };
    } finally {
      b.loading = false;
    }
    if (!st || st.running === undefined) { // the call failed: show what the recorder is really doing
      const err = st?.error;
      st = await this.api.recorder_status().catch(() => ({ running: false, tracks: [], elapsed: 0 }));
      if (err) st.error = err;
    }
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
    const gen = this.recGen;
    this.recTimer = setTimeout(async () => {
      const st = await this.api.recorder_status();
      if (gen !== this.recGen) return; // Record/Stop was pressed meanwhile
      Object.assign(this.rec, st);
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
    // playhead: where the track plays, or the cursor where play starts
    const on = this._main() && this.playing.sid === this.cur.sid;
    const head = on ? this.playing.start + this.player.currentTime : this.cursor;
    ctx.fillStyle = on ? '#ffffff' : 'rgba(255,255,255,.65)';
    ctx.fillRect(this._x(head), 0, Math.max(1, dpr), H);
    if (!on) { // a small handle on top, to see the cursor at rest
      const x = this._x(head);
      ctx.beginPath();
      ctx.moveTo(x - 5 * dpr, 0); ctx.lineTo(x + 5 * dpr, 0); ctx.lineTo(x, 6 * dpr);
      ctx.fill();
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
    const on = this._main() && this.playing.sid === this.cur.sid;
    ctx.fillStyle = 'rgba(255,255,255,.8)';
    ctx.fillRect((on ? this.playing.start + this.player.currentTime : this.cursor) / this.duration * W, 0, devicePixelRatio, H);
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
    if (Math.abs(e.clientX - d.x) < 4) {  // a click: the cursor goes there (playing goes on from there) and selects the region under it
      this.seek(d.a);
      if (d.hit !== this.sel) { this.sel = d.hit; this.renderRegions(); }
      this.draw();
      return;
    }
    const start = Math.min(d.a, d.b), end = Math.max(d.a, d.b);
    this.regions.push({ start, end, name: '', on: true });
    this.regions.sort((x, y) => x.start - y.start);
    this.sel = this.regions.findIndex((r) => r.start === start && r.end === end);
    this._renderTracks();
    this.renderRegions();
    this.setView(this.view.start, this.view.end);
    this.playRegion(this.cur, this.sel);
  }

  // Move the cursor of the shown track; if it is playing, it goes on from there.
  seek(at) {
    if (!this.cur) return;
    this.cursor = Math.max(0, Math.min(this.duration, at));
    if (this._main() && this.playing.sid === this.cur.sid) this._playFrom(this.cur, this.cursor);
    this.draw();
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
    this._renderTracks();
    this.renderRegions();
    this.draw();
    toast(!found.length ? t('No transients found: try raising the sensitivity')
      : whole ? t('{n} regions on the transients', { n: found.length }) : t('{n} regions on the transients of the visible part', { n: found.length }));
  }

  removeRegion(i, tr = this.cur) {
    tr.regions.splice(i, 1);
    if (tr.sel === i) tr.sel = -1;
    else if (tr.sel > i) tr.sel -= 1;
    this._renderTracks();
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

  // The cuts of every open track, in tab order: [{tr, i, r}].
  _cuts() { return this.tracks.flatMap((tr) => tr.regions.map((r, i) => ({ tr, i, r }))); }

  // The rows of a tab: regions (cuts of every track) or extracted files.
  _rows(tab = this.opts.tab) { return tab === 'cuts' ? this._cuts().map((c) => c.r) : this.ext[tab] || []; }

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
          : this.session ? t('No stems of the open tracks yet: use «Extract stems».') : '')
          : this.session ? t('Nothing enhanced from the open tracks yet: use «Enhance» on a track, on a cut or on a stem.') : '';
      box.innerHTML = `${job}<div class="hint sp-regions-empty">${empty}</div>`;
      return;
    }
    const acts = ({ stems, ai }) => `
        ${iconBtn('play', t('Listen'), { 'data-act': 'play' })}
        ${iconBtn('scan-search', tab === 'cuts' ? t('Show on the waveform') : t('Open its waveform in a new tab'), { 'data-act': 'zoom' })}
        ${stems ? iconBtn('layers', t('Extract stems'), { 'data-act': 'stems' }) : '<span></span>'}
        ${ai ? iconBtn('sparkles', t('Enhance with AI'), { 'data-act': 'enhance', cls: 'cs-ai-icon' }) : '<span></span>'}
        ${iconBtn('send', t('Send to the Sequencer or the Drum Rack'), { 'data-act': 'send' })}`;
    const state = (saved) => `<span class="sp-saved${saved ? ' on' : ''}" title="${esc(saved ? t('Saved in the export folder')
      : t('Temporary: «Export all» saves it, otherwise it is deleted when ClusterSound closes'))}">${icon(saved ? 'check' : 'circle')}</span>`;
    // a title over the rows of every track (or source) when there is more than one
    const groups = new Set((tab === 'cuts' ? this._cuts().map((c) => c.tr.sid) : rows.map((f) => f.sid)));
    let last = null;
    const head = (key, title, sid) => {
      if (groups.size < 2 || key === last) return '';
      last = key;
      return `<div class="sp-group${sid === this.cur?.sid ? ' on' : ''}" data-group="${esc(sid)}">${esc(title)}</div>`;
    };
    if (tab === 'cuts') {
      box.innerHTML = this._cuts().map(({ tr, i, r }, k) => `${head(tr.sid, tr.session.title, tr.sid)}
        <div class="sp-row${tr === this.cur && i === tr.sel ? ' sel' : ''}" data-i="${k}">
          ${check('', r.on, { label: t('Select') })}
          <span class="sp-num">${i + 1}</span>
          <wa-input size="s" value="${esc(r.name)}" placeholder="${esc(this._defaultName(tr, i))}" label="${t('Name')}"></wa-input>
          <span class="sp-time sp-start">${fmt(r.start)}</span>
          <span class="sp-time ${r.end - r.start >= this.maxS - 1e-3 ? 'error' : ''}">${fmt(r.end - r.start)}</span>
          ${state(this._cutSaved(tr, i))}
          ${acts({ stems: true, ai: true })}
          <span></span>
          ${iconBtn('x', t('Delete'), { 'data-act': 'del' })}
        </div>`).join('');
      return;
    }
    const fileRow = (f, i) => `
      <div class="sp-row sp-file-row${f.path === this.session?.path ? ' sel' : ''}${tab === 'enhanced' ? ' en-row' : ''}" data-i="${i}" title="${esc(f.path)}">
        ${check('', f.on, { label: t('Select') })}
        <span class="sp-num">${i + 1}</span>
        <span class="sp-file-name">${esc(tab === 'stems' ? f.name.split(' - ').pop() : f.name)}</span>
        <span class="sp-time sp-start">${f.sr ? `${(f.sr / 1000).toFixed(1)} kHz` : ''}</span>
        <span class="sp-time">${fmt(f.dur)}</span>
        ${state(f.saved)}
        ${acts({ stems: tab === 'enhanced', ai: tab === 'stems' })}
        ${this._whereSaved(f) ? iconBtn('folder-open', t('Show in {app}', { app: FILE_MANAGER }), { 'data-act': 'reveal' })
          : iconBtn('folder-open', t('Not saved yet'), { 'data-act': 'reveal', cls: 'is-off', 'aria-disabled': 'true' })}
        ${iconBtn('trash-2', f.saved ? t('Move to the Trash') : t('Delete'), { 'data-act': 'del' })}
      </div>`;
    if (tab === 'enhanced') {
      box.innerHTML = job + rows.map((f, i) => head(f.sid, f.source, f.sid) + fileRow(f, i)).join('');
      return;
    }
    // stems: the ones of the same separated audio (a track, a cut, an enhanced file) together, collapsible
    let html = job;
    for (const set of this._stemSets()) {
      const f0 = rows[set.idx[0]], key = `${f0.sid}|${set.name}`, open = !this.collapsed.has(key);
      const on = set.idx.filter((i) => rows[i].on).length;
      html += head(f0.sid, f0.source, f0.sid) + `
        <div class="sp-set${open ? ' open' : ''}" data-set="${esc(key)}">
          ${icon(open ? 'chevron-down' : 'chevron-right')}
          ${check('', on === set.idx.length, { label: t('Select'), indeterminate: on > 0 && on < set.idx.length, 'data-set-check': '' })}
          <span class="sp-set-name">${esc(set.name)}</span><span class="sp-tab-n">${set.idx.length}</span>
        </div>` + (open ? set.idx.map((i) => fileRow(rows[i], i)).join('') : '');
    }
    box.innerHTML = html;
  }

  // Stems grouped by what was separated (the name before « - Drums»), in list order: [{name, idx: [i…]}].
  _stemSets() {
    const sets = new Map();
    this.ext.stems.forEach((f, i) => {
      const parts = f.name.split(' - '), name = parts.length > 1 ? parts.slice(0, -1).join(' - ') : f.name;
      const k = `${f.sid}|${name}`;
      if (!sets.has(k)) sets.set(k, { name, idx: [] });
      sets.get(k).idx.push(i);
    });
    return [...sets.values()];
  }

  _defaultName(tr, i) { return `${tr.session?.title || 'sample'} - ${String(i + 1).padStart(2, '0')}`; }

  async _rowClick(e) {
    if (e.target.closest('[data-job]')) return this._cancelJob();
    const g = e.target.closest('[data-group]');
    if (g) return this.tracks.some((x) => x.sid === g.dataset.group) && this.selectTrack(g.dataset.group);
    const set = e.target.closest('[data-set]');
    if (set) {
      if (e.target.closest('[data-set-check]')) return; // the tick of the group: see the change handler
      const k = set.dataset.set;
      if (this.collapsed.has(k)) this.collapsed.delete(k); else this.collapsed.add(k);
      return this.renderRegions();
    }
    const row = e.target.closest('[data-i]');
    if (!row) return;
    const k = +row.dataset.i, act = e.target.closest('[data-act]')?.dataset.act;
    const anchor = () => $(`#sp-regions [data-i="${k}"] [data-act="${act}"]`); // the row may have been re-rendered
    if (this.opts.tab !== 'cuts') {
      const f = this._rows()[k];
      if (act === 'reveal') {
        const where = this._whereSaved(f);
        if (!where) return this._unsavedMenu(anchor(), f);
        if (!(await this.api.reveal_path(where))) this._error(t('Cannot show the file: it was moved or deleted'));
        return;
      }
      if (act === 'del') return this.deleteFile(f);
      if (act === 'zoom') return this._opened(await this.api.sampler_open_extraction(f.path));
      if (act === 'enhance') return this._enhMenu(anchor(), { path: f.path, label: f.name });
      if (act === 'stems') return this._stemsMenu(anchor(), { path: f.path, label: f.name });
      if (act === 'send') return this._sendOne(this._fileRef(f), anchor());
      if (e.target.closest('wa-checkbox')) return;
      return this.playFile(f.path);
    }
    const { tr, i, r } = this._cuts()[k];
    const label = r.name || this._defaultName(tr, i);
    if (act === 'del') return this.removeRegion(i, tr);
    if (act === 'zoom') {
      if (tr !== this.cur) await this.selectTrack(tr.sid);
      const pad = Math.max(0.05, (r.end - r.start) * 0.25);
      this.sel = i;
      this.renderRegions();
      return this.setView(r.start - pad, r.end + pad);
    }
    if (act === 'play') return this.playRegion(tr, i);
    if (act === 'send') {
      const refs = await this._regionRefs(tr, [i], e.target.closest('wa-button'));
      return refs?.[0] && this._sendOne(refs[0], anchor());
    }
    if (act === 'stems' || act === 'enhance') {
      if (tr === this.cur) { this.sel = i; this.draw(); }
      this.renderRegions();
      const target = { sid: tr.sid, start: r.start, end: r.end, label };
      return act === 'stems' ? this._stemsMenu(anchor(), target) : this._enhMenu(anchor(), target);
    }
    if (e.target.closest('wa-input, wa-checkbox')) return;
    this.playRegion(tr, i);
  }

  // The "Send" menu of the library (Sequencer bus or Drum Rack group), under the row's button.
  _sendOne(ref, anchor) {
    if (!this.onSend || !anchor) return;
    const r = anchor.getBoundingClientRect();
    this.onSend(ref, r.left, r.bottom + 4);
  }

  _fileRef(f) { return { kind: 'file', path: f.path, name: f.path.split('/').pop(), cls: null, root: null, dur: f.dur }; }

  // ---------------------------------------------------------------- header actions
  async clearAll() {
    const rows = this._rows();
    if (!rows.length) return;
    const tab = this.opts.tab;
    const msg = tab === 'cuts' ? t('Remove all the {n} cuts of the open tracks?', { n: rows.length })
      : t('Remove the {n} files from the list? They stay on disk.', { n: rows.length });
    if (!(await this._confirm(t('Clear all'), msg, t('Clear all')))) return;
    if (tab === 'cuts') {
      for (const tr of this.tracks) { tr.regions = []; tr.sel = -1; }
      this._renderTracks();
      this.draw();
    } else {
      for (const f of rows) this.hidden.add(f.path);
      this.ext[tab] = [];
    }
    this.renderRegions();
  }

  // "Send to ▾": the ticked rows to Live, to the Drum Rack or to a Sequencer bus.
  async _sendMenu(anchor) {
    const n = this._rows().filter((r) => r.on).length;
    const item = (go, ic, label, hint, dis) => `<button class="sp-send-item" data-go="${go}"${dis ? ' disabled' : ''}>${icon(ic)}<span><b>${label}</b><span class="hint">${hint}</span></span></button>`;
    const pop = showPopover(anchor, `<div class="pop-title">${icon('arrow-right')} ${t('Send to')}</div>
      <div class="sp-send-list">
        ${item('live', 'music', 'Ableton Live', n > 1 ? t('{n} new audio tracks', { n }) : n ? t('A new audio track') : t('All the shown track, on a new audio track'), !this.session && !n)}
        ${item('rack', 'layout-grid', 'Drum Rack', t('On the free pads, from the selected one'), !n)}
        ${item('seq', 'audio-lines', 'Sequencer', t('As new layers of a bus'), !n || !this.getBuses)}
        ${item('lib', 'library-big', t('Library'), t('Copied into «{dir}», a folder per track', { dir: 'ClusterSound Recorder' }), !n)}
      </div><div class="sp-send-buses"></div>`);
    pop.onclick = async (e) => {
      const b = e.target.closest('[data-go], [data-bus]');
      if (!b || b.disabled) return;
      if (b.dataset.bus) { pop.close(); return this.sendToBus(b.dataset.bus); }
      const go = b.dataset.go;
      if (go === 'live') { pop.close(); return this.sendToLive(); }
      if (go === 'rack') { pop.close(); return this.sendToRack(); }
      if (go === 'lib') { pop.close(); return this.sendToLibrary(); }
      const box = pop.querySelector('.sp-send-buses');
      box.innerHTML = `<div class="hint">${t('Loading…')}</div>`;
      const buses = await this.getBuses();
      box.innerHTML = `<div class="hint">${t('Bus')}</div>` + buses.map((x) =>
        `<button class="sp-send-bus" data-bus="${esc(x.id)}"><span class="sp-bus-dot" style="background:${esc(x.color || 'var(--text-3)')}"></span>${esc(x.label)}</button>`).join('');
    };
  }

  // ---------------------------------------------------------------- playback
  _dropAudio() { this.audioRev += 1; } // the region audio changed: re-render it on next play

  _main() { return !!this.playing && !this.playing.path && this.player.playing; } // a track (or a cut) is playing

  // Play [start, end) of a track; key 'cur' is the track itself from the cursor (no fades), else a cut.
  async _playSpan(tr, start, end, key) {
    const raw = key === 'cur';
    const load = (a, b) => this.player.load(`sp:${tr.sid}.${raw ? 'raw' : this.audioRev}:${key}:${a.toFixed(4)}-${b.toFixed(4)}`,
      () => this.api.sampler_audio(a, b, raw ? { fade_in_ms: 0, fade_out_ms: 0, normalize: false } : this.opts, tr.sid));
    const buf = await load(start, end);
    if (!buf) return;
    this.player.play(`sampler:${tr.sid}:${key}`, buf, 0);
    this.playing = { sid: tr.sid, start, end, key };
    this._syncPlay();
    const tick = () => { if (this.playing && !this.playing.path) { this.draw(); requestAnimationFrame(tick); } };
    requestAnimationFrame(tick);
    if (raw && end < tr.session.duration - 1e-3) load(end, Math.min(tr.session.duration, end + PLAY_BLOCK_S)); // the next block, ready in time
  }

  // The track from a point on, in blocks of PLAY_BLOCK_S (the backend renders at most 60 s at a time).
  _playFrom(tr, at) {
    // blocks start on a grid, so the next one is the same (cached) whatever the point played from
    const end = Math.min(tr.session.duration, (Math.floor(at / PLAY_BLOCK_S) + 1) * PLAY_BLOCK_S);
    return this._playSpan(tr, at, end, 'cur');
  }

  async playFile(path) {
    if (this.playing?.path === path && this.player.playing) { this.player.stop(); return; }
    const buf = await this.player.load(`spf:${path}`, () => this.api.sample_audio({ kind: 'file', path }));
    if (!buf) return this._error(t('file not found'));
    this.player.play(`sampler:f:${path}`, buf, 0);
    this.playing = { path };
    this._syncPlay();
  }

  playRegion(tr, i) {
    const r = tr?.regions[i];
    if (!r) return;
    tr.sel = i;
    this.renderRegions();
    this.draw();
    this._playSpan(tr, r.start, r.end, `r${i}`);
  }

  // Play / pause the shown track from its cursor; pausing leaves the cursor where it stopped.
  togglePlay() {
    if (!this.cur) return;
    if (this._main() && this.playing.key === 'cur' && this.playing.sid === this.cur.sid) {
      this.cursor = this.playing.start + this.player.currentTime;
      this.player.stop();
      return;
    }
    if (this.cursor >= this.duration - 1e-3) this.cursor = 0;
    this._playFrom(this.cur, this.cursor);
  }

  // Stop: the cursor goes back to the start of the track.
  stop() {
    this.player.stop();
    if (this.cur) this.cursor = 0;
    this._syncPlay();
  }

  _syncPlay() {
    const b = $('#sp-play'), on = this._main() && this.playing.key === 'cur' && this.playing.sid === this.cur?.sid;
    if (b) {
      const label = on ? t('Pause') : t('Play');
      if (b.dataset.on !== String(on)) { b.innerHTML = icon(on ? 'pause' : 'play', label); b.dataset.on = on; }
      b.title = `${label} (${t('Space')})`;
    }
    this.draw();
  }

  // ---------------------------------------------------------------- export
  _cutKey(tr, r, i) {
    return JSON.stringify([r.start, r.end, r.name || this._defaultName(tr, i), this.opts.fade_in_ms, this.opts.fade_out_ms, this.opts.normalize]);
  }

  _cutSaved(tr, i) { const r = tr.regions[i]; return !!r.file?.saved && r.file.key === this._cutKey(tr, r, i); }

  // Cuts of a track as WAV files, aligned with `idx`: saved into the export folder, or (temp) into the temporary
  // folder of this run. A cut already written with the same bounds, name and fades/normalisation reuses its file
  // (a saved one also when a temporary one would do).
  async _files(tr, idx, button, temp = false) {
    const todo = idx.filter((i) => {
      const r = tr.regions[i];
      return r.file?.key !== this._cutKey(tr, r, i) || (!temp && !r.file.saved);
    });
    if (todo.length) {
      // empty names get the placeholder shown in the list, so numbers match the region numbers
      const regions = todo.map((i) => ({ start: tr.regions[i].start, end: tr.regions[i].end, name: tr.regions[i].name || this._defaultName(tr, i) }));
      if (button) button.loading = true;
      const r = await this.api.sampler_export(regions, this.opts, tr.sid, temp);
      if (button) button.loading = false;
      if (r.error) { this._error(r.error); return null; }
      todo.forEach((i, k) => { if (r.files[k]) tr.regions[i].file = { key: this._cutKey(tr, tr.regions[i], i), path: r.files[k], saved: !temp }; });
      if (!temp) this._showExported(r.folder, r.paths[0]);
      if (r.in_library) toast(t('The samples are in the library: analysing them'));
    }
    return idx.map((i) => tr.regions[i].file?.path || null);
  }

  // Cuts as sample refs, for sending them somewhere (temporary files unless already saved).
  async _regionRefs(tr, idx, button) {
    const files = await this._files(tr, idx, button, true);
    if (!files) return null;
    return idx.map((i, k) => files[k] && {
      kind: 'file', path: files[k], name: files[k].split('/').pop(), cls: null, root: null, sid: tr.sid,
      dur: +(tr.regions[i].end - tr.regions[i].start).toFixed(3) }).filter(Boolean);
  }

  // The ticked cuts, per track: [[tr, [i…]]].
  _checkedCuts() {
    return this.tracks.map((tr) => [tr, tr.regions.map((r, i) => (r.on ? i : -1)).filter((i) => i >= 0)]).filter(([, idx]) => idx.length);
  }

  // Ticked rows of the active tab as sample refs (cuts are written first, as temporary files).
  async _checkedRefs(button) {
    if (this.opts.tab !== 'cuts') return this._rows().filter((f) => f.on).map((f) => ({ ...this._fileRef(f), sid: f.sid }));
    const out = [];
    for (const [tr, idx] of this._checkedCuts()) {
      const refs = await this._regionRefs(tr, idx, button);
      if (!refs) return null;
      out.push(...refs);
    }
    return out;
  }

  _showExported(folder, first) {
    if (!first) return;
    const head = $('#sp-regions-head-msg') || Object.assign(document.createElement('div'), { id: 'sp-regions-head-msg', className: 'hint sp-exported' });
    head.innerHTML = t('Exported to {folder}', { folder: `<a href="#">${esc(folder)}</a>` });
    head.querySelector('a').onclick = (e) => { e.preventDefault(); this.api.reveal_path(first); };
    $('#sp-regions').before(head);
  }

  // "Export all": saves the ticked rows of the tab into the export folder chosen in Settings. What is not saved
  // stays temporary and is deleted when ClusterSound closes.
  async export() {
    const b = $('#sp-export');
    let n = 0;
    if (this.opts.tab === 'cuts') {
      for (const [tr, idx] of this._checkedCuts()) {
        const files = await this._files(tr, idx, b);
        if (!files) return;
        n += files.filter(Boolean).length;
      }
      this._renderTracks();
      this.renderRegions();
    } else {
      const paths = this._rows().filter((f) => f.on).map((f) => f.path);
      if (!paths.length) return;
      n = await this.exportFiles(paths);
    }
    if (n) toast(n === 1 ? t('1 sample saved') : t('{n} samples saved', { n }));
  }

  // Where a stem or enhanced file can be shown in the Finder: saved, or its copy in the library (else null).
  _whereSaved(f) { return f.saved ? f.path : this.libCopies.get(f.path) || null; }

  // «Show in Finder» of a temporary file: it is not saved yet; offer to send it to the library or to export it.
  _unsavedMenu(anchor, f) {
    const pop = showPopover(anchor, `<div class="pop-title">${icon('triangle-alert')} ${t('Not saved yet')}</div>
      <div class="hint sp-unsaved">${t('«{name}» is temporary: it is deleted when ClusterSound closes. Save it to find it in {app}.', { name: esc(f.name), app: FILE_MANAGER })}</div>
      <div class="pop-actions">
        ${btn(t('Send to the library'), { icon: 'library-big', 'data-go': 'lib' })}
        ${btn(t('Export'), { variant: 'brand', icon: 'file-down', 'data-go': 'save', title: t('Saves it in the export folder, like «Export all»') })}
      </div>`);
    pop.querySelectorAll('[data-go]').forEach((b) => {
      b.onclick = async () => {
        pop.close();
        if (b.dataset.go === 'lib') return this.sendToLibrary(null, [{ path: f.path, sid: f.sid }]);
        const n = await this.exportFiles([f.path]);
        if (n) toast(t('1 sample saved'));
      };
    });
  }

  // Save extracted files (temporary ones move into the export folder); returns how many.
  async exportFiles(paths) {
    const b = $('#sp-export');
    b.loading = true;
    const r = await this.api.sampler_export_files(paths);
    b.loading = false;
    if (r.error) { this._error(r.error); return 0; }
    this._showExported(r.folder, r.paths[0]);
    if (r.in_library) toast(t('The samples are in the library: analysing them'));
    await this._loadExtractions(); // the saved ones moved
    return r.paths.length;
  }

  // A stem or enhanced file: a temporary one is deleted, a saved one goes to the Trash (after a confirmation).
  async deleteFile(f) {
    if (f.saved && !(await this._confirm(t('Move to the Trash'), t('Move «{name}» to the Trash? It is saved in the export folder.', { name: esc(f.name) }), t('Move to the Trash')))) return;
    if (this.playing?.path === f.path) this.player.stop();
    const r = await this.api.sampler_delete_extraction(f.path);
    if (r.error) return this._error(r.error);
    if (this.session?.path === f.path) { // its own tab, if open, has nothing to show any more
      const tr = this.cur;
      await this._opened(await this.api.sampler_close(tr.sid));
    }
    await this._loadExtractions();
    toast(f.saved ? t('Moved to the Trash') : t('Deleted'));
  }

  // Ticked rows into the library: ClusterSound Recorder/<track>/ of one of its folders (asked if there are more).
  async sendToLibrary(root = null, items = null) {
    if (!items) {
      const refs = await this._checkedRefs($('#sp-send'));
      if (!refs?.length) return;
      items = refs.map((x) => ({ path: x.path, sid: x.sid }));
    }
    let r = await this.api.sampler_send_to_library(items, root);
    if (r.choose) {
      root = await this._chooseRoot(r.choose);
      if (!root) return;
      r = await this.api.sampler_send_to_library(items, root);
    }
    if (r.error) return this._error(r.error);
    for (const [src, dst] of Object.entries(r.copies || {})) this.libCopies.set(src, dst);
    this.renderRegions();
    toast(r.files.length === 1 ? t('1 sample copied to the library') : t('{n} samples copied to the library', { n: r.files.length }));
  }

  // Which library folder, when the library is made of several.
  _chooseRoot(roots) {
    return new Promise((done) => {
      let picked = null;
      const dlg = openDialog('sp-root-dlg', { label: t('Send to the library'), width: '480px', onHide: () => done(picked),
        body: `<p class="hint">${t('The library is made of several folders: in which one should the «{dir}» folder go?', { dir: 'ClusterSound Recorder' })}</p>
          <div class="sp-roots">${roots.map((x) => `<button class="sp-open-choice" data-root="${esc(x)}">${icon('folder-open')}<b>${esc(x.split('/').pop() || x)}</b><span class="hint">${esc(x)}</span></button>`).join('')}</div>` });
      dlg.querySelector('.sp-roots').onclick = (e) => {
        const b = e.target.closest('[data-root]');
        if (!b) return;
        picked = b.dataset.root;
        dlg.close();
      };
    });
  }

  // The ticked rows (cuts of every track, or files) to Live, one new audio track each; with no cut ticked,
  // all the shown track.
  async sendToLive() {
    const b = $('#sp-send');
    const send = (...a) => this.api.sampler_send_to_live(...a);
    const jobs = [];
    if (this.opts.tab === 'cuts') {
      for (const [tr, idx] of this._checkedCuts()) for (const i of idx) jobs.push(() => send(tr.regions[i].start, tr.regions[i].end, this.opts, null, tr.sid));
      if (!jobs.length && this.cur) jobs.push(() => send(null, null, this.opts, null, this.cur.sid));
    } else {
      for (const f of this._rows().filter((x) => x.on)) jobs.push(() => send(null, null, null, f.path));
    }
    if (!jobs.length) return this._error(t('Open a recording first'));
    b.loading = true;
    toast(t('Sending to Live…'));
    let out = null;
    for (const job of jobs) out = await job();
    b.loading = false;
    if (out.error) return this._error(out.error);
    if (out.file && !out.running) return toast(t('Live bridge not active: the file is in the Live browser anyway, User Library › ClusterSound › Audio'));
    liveToast(out);
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

// What the editor shows is the shown track's: these read and write this.cur (defaults with no track open).
const TRACK = { session: null, regions: [], sel: -1, view: { start: 0, end: 1 }, overview: null, detail: null, cursor: 0 };
for (const [k, d] of Object.entries(TRACK)) {
  Object.defineProperty(SamplerEditor.prototype, k, {
    get() { return this.cur ? this.cur[k] : (Array.isArray(d) ? [] : d); },
    set(v) { if (this.cur) this.cur[k] = v; },
  });
}
