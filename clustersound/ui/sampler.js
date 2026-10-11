// "Sampler" screen: open a longer piece of audio (own file, openly licensed link, system audio capture),
// mark regions on its waveform (by hand or on transients) and export them as samples.
import { btn, iconBtn, slider, check, num, select, setPlayButton, icon } from './kit.js';
import { toast } from './sendmenu.js';

const $ = (s, root = document) => root.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LS_KEY = 'clustersound.sampler';
const EDGE_PX = 6;         // grab distance of a region edge
const MIN_VIEW_S = 0.02;   // deepest zoom
const ORIGIN_LABEL = { file: 'File', link: 'Link', capture: 'Cattura' };
const CAPTURE_NOTE = 'Registrazione per uso personale (copia privata): nulla viene decifrato o aggirato, e le app '
  + 'che proteggono il flusso registrano silenzio. Per pubblicare un brano che contiene il sample servono i diritti.';
const fmt = (t) => {
  if (!isFinite(t)) return '–';
  const m = Math.floor(t / 60), s = t - m * 60;
  return m ? `${m}:${s.toFixed(2).padStart(5, '0')}` : `${s.toFixed(3)} s`;
};

export class SamplerEditor {
  constructor({ api, player }) {
    this.api = api;
    this.player = player;
    this.ready = null;
    this.session = null;      // describe() of the open audio
    this.token = 0;           // bumps when a new source opens
    this.audioRev = 0;        // bumps when fades / normalisation change (player cache keys)
    this.maxS = 30;
    this.view = { start: 0, end: 1 };
    this.overview = null;     // peaks of the whole source
    this.detail = null;       // peaks of the current view
    this.regions = [];        // {start, end, name, on}
    this.sel = -1;
    this.drag = null;
    this.playing = null;      // {start, end} being played
    this.capture = { running: false, sources: [] };
    this.linkFiles = [];
    this.opts = { fade_in_ms: 1, fade_out_ms: 10, normalize: false, sensitivity: 0.5, grab: 15, source: 'system' };
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
    this.capture = init.capture;
    if (!this.capture.sources.some((s) => s.id === this.opts.source)) this.opts.source = this.capture.sources[0]?.id || 'system';
    this._buildShell();
    if (init.session) await this._opened(init);
  }

  async show() {
    await this.ensure();
    this._resize();
    if (this.capture.running) this._pollCapture();
  }

  hide() {
    this.player.stop();
    clearTimeout(this.capTimer);
  }

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
          <div class="filter-title">Sorgente</div>
          ${btn('Apri file audio…', { icon: 'folder-open', cls: 'sp-wide', id: 'sp-open' })}
          <div class="sp-link">
            <wa-input id="sp-url" size="s" placeholder="Incolla un link (Freesound, Archive…)" autocomplete="off" with-clear></wa-input>
            ${btn('Apri', { id: 'sp-url-go' })}
          </div>
          <div class="hint">Link accettati: ${esc(this.supported)}. YouTube, Spotify, Tidal e gli altri servizi di
            streaming non consentono di scaricare l'audio.</div>
          <div id="sp-files" class="sp-files" hidden></div>
        </div>
        <div class="filter-block sp-capture">
          <div class="filter-title">Cattura audio</div>
          ${this.capture.sources.length ? `
            ${select(this.capture.sources.map((s) => [s.id, s.name]), o.source, { id: 'sp-cap-src', label: 'Sorgente della cattura' })}
            <div class="sp-cap-row">
              ${btn('Registra', { variant: 'brand', icon: 'circle', id: 'sp-cap-rec' })}
              <div class="sp-meter" title="Livello"><div id="sp-meter-fill"></div></div>
            </div>
            <div class="hint" id="sp-cap-info"></div>
            <div class="sp-cap-row">
              ${num(o.grab, { id: 'sp-grab-s', min: 1, max: 300, step: 1, label: 'Secondi da prendere', 'without-steppers': true })}
              ${btn('Prendi ultimi secondi', { icon: 'download', id: 'sp-grab' })}
            </div>
            <div class="hint sp-note">${esc(CAPTURE_NOTE)}</div>`
          : `<div class="hint">Non disponibile: installa l'extra <code>capture</code>
              (<code>pip install "clustersound[capture]"</code>).</div>`}
        </div>
        <div class="filter-block">
          <div class="filter-title">Esportazione</div>
          <div class="sp-opts">
            ${num(o.fade_in_ms, { id: 'sp-fi', min: 0, max: 200, step: 1, label: 'Fade in (ms)' })}
            ${num(o.fade_out_ms, { id: 'sp-fo', min: 0, max: 2000, step: 5, label: 'Fade out (ms)' })}
          </div>
          ${check('Normalizza a −0,3 dBFS', o.normalize, { id: 'sp-norm' })}
          <div class="hint" id="sp-max-hint"></div>
        </div>
      </aside>
      <main class="sp-main">
        <div class="sp-info" id="sp-info"></div>
        <div class="sp-toolbar">
          ${btn('Play', { variant: 'brand', icon: 'play', id: 'sp-play' })}
          ${iconBtn('maximize-2', 'Mostra tutto', { id: 'sp-fit' })}
          <span class="sp-sep"></span>
          ${btn('Taglia sui transienti', { icon: 'sparkles', id: 'sp-slice' })}
          <span class="sp-sens" title="Sensibilità: più alta = più tagli">
            <span class="hint">Sensibilità</span>${slider(0, 1, 0.05, o.sensitivity, { id: 'sp-sens', label: 'Sensibilità' })}
          </span>
          <span class="spacer"></span>
          <span class="hint" id="sp-view-info"></span>
        </div>
        <div class="sp-wave-wrap" id="sp-wave-wrap">
          <canvas id="sp-wave" class="sp-wave"></canvas>
          <canvas id="sp-overview" class="sp-overview"></canvas>
          <div class="empty sp-empty" id="sp-empty">
            <div class="empty-title">Apri un brano da cui estrarre sample</div>
            <div class="empty-sub">Un file tuo, un link da una fonte con licenza aperta, oppure una cattura
              dell'audio del Mac. Trascina sulla forma d'onda per creare una regione (max <span class="sp-max"></span>),
              oppure usa «Taglia sui transienti». Rotella: zoom · Maiusc+rotella: scorri.</div>
          </div>
        </div>
        <div class="sp-regions-head">
          <span class="filter-title">Regioni <span id="sp-count"></span></span>
          <span class="spacer"></span>
          ${btn('Svuota', { icon: 'trash-2', id: 'sp-clear' })}
          ${btn('Esporta selezionate', { variant: 'brand', icon: 'file-down', id: 'sp-export' })}
        </div>
        <div class="sp-regions" id="sp-regions"></div>
      </main>`;
    this.cv = $('#sp-wave');
    this.ov = $('#sp-overview');
    this._bind();
    this._renderMax();
    this.renderInfo();
    this.renderRegions();
    this._renderCapture();
    new ResizeObserver(() => this._resize()).observe($('#sp-wave-wrap'));
  }

  _bind() {
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
    if (this.capture.sources.length) {
      $('#sp-cap-src').addEventListener('change', (e) => { this.opts.source = e.target.value; this._persist(); });
      $('#sp-cap-rec').onclick = () => this.toggleCapture();
      $('#sp-grab').onclick = () => this.grab();
      $('#sp-grab-s').addEventListener('change', (e) => { this.opts.grab = +e.target.value || 15; this._persist(); });
    }
    const optNum = (id, key) => $(id).addEventListener('change', (e) => { this.opts[key] = Math.max(0, +e.target.value || 0); this._persist(); this._dropAudio(); });
    optNum('#sp-fi', 'fade_in_ms');
    optNum('#sp-fo', 'fade_out_ms');
    $('#sp-norm').addEventListener('change', (e) => { this.opts.normalize = e.target.checked; this._persist(); this._dropAudio(); });
    $('#sp-sens').addEventListener('change', (e) => { this.opts.sensitivity = +e.target.value; this._persist(); });
    $('#sp-play').onclick = () => this.togglePlay();
    $('#sp-fit').onclick = () => this.setView(0, this.duration);
    $('#sp-slice').onclick = () => this.autoSlice();
    $('#sp-clear').onclick = () => { this.regions = []; this.sel = -1; this.renderRegions(); this.draw(); };
    $('#sp-export').onclick = () => this.export();
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
    box.innerHTML = `<div class="hint">${esc(first.info?.pack_title || first.source_label)} · ${files.length} file
      · licenza ${esc(first.license_label)}. Scegli quale aprire:</div>`
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
      ? 'Utilizzabile anche in produzioni commerciali (rispettando l\'attribuzione, se richiesta)'
      : 'Uso commerciale non consentito o da verificare'}">${esc(src.license_label)}</span>` : '';
    const who = src ? ` · ${esc(src.author || 'autore sconosciuto')} · ${esc(src.source_label)}` : '';
    const page = src?.page_url ? ` <a href="#" data-url="${esc(src.page_url)}" class="sp-page">${icon('external-link')} pagina</a>` : '';
    box.innerHTML = `<span class="sp-badge">${ORIGIN_LABEL[s.origin] || s.origin}</span>${lic}
      <b class="sp-title" title="${esc(s.path || s.title)}">${esc(s.title)}</b>
      <span class="hint">${fmt(s.duration)} · ${s.sr} Hz · ${s.channels === 1 ? 'mono' : 'stereo'}${who}${
        s.truncated ? ' · aperti solo i primi 20 minuti' : ''}</span>${page}
      ${s.origin === 'capture' ? `<span class="hint sp-note-inline">${icon('triangle-alert')} solo uso personale</span>` : ''}
      ${src?.suspect ? `<span class="sp-badge warn" title="Sembra materiale commerciale ricaricato con una licenza libera">verifica i diritti</span>` : ''}`;
    const a = box.querySelector('.sp-page');
    if (a) a.onclick = (e) => { e.preventDefault(); this.api.open_url(a.dataset.url); };
  }

  _renderMax() {
    document.querySelectorAll('#sampler .sp-max').forEach((el) => { el.textContent = `${this.maxS} s`; });
    const h = $('#sp-max-hint');
    if (h) h.textContent = `Ogni sample dura al massimo ${this.maxS} s. I file vanno in una sottocartella per origine, `
      + 'con accanto la licenza (link) o la provenienza (cattura).';
  }

  // ---------------------------------------------------------------- capture
  _renderCapture() {
    if (!this.capture.sources.length) return;
    const c = this.capture;
    setPlayButton($('#sp-cap-rec'), c.running, 'Registra', 'Ferma');
    $('#sp-cap-rec').querySelector('wa-icon')?.setAttribute('name', c.running ? 'square' : 'circle');
    $('#sp-cap-src').disabled = c.running;
    $('#sp-meter-fill').style.width = `${Math.min(100, Math.sqrt(c.level || 0) * 220)}%`;
    $('#sp-cap-info').innerHTML = c.error ? `<span class="error">${esc(c.error)}</span>`
      : c.running ? `In registrazione: tengo gli ultimi ${Math.round(c.buffer_seconds)} s (${c.seconds.toFixed(0)} s nel buffer).`
        : c.seconds ? `Ferma: ${c.seconds.toFixed(0)} s nel buffer.` : 'Registra ciò che il Mac sta suonando, poi prendi gli ultimi secondi.';
  }

  async toggleCapture() {
    const b = $('#sp-cap-rec');
    b.loading = true;
    this.capture = { ...this.capture, ...(this.capture.running
      ? await this.api.sampler_capture_stop() : await this.api.sampler_capture_start(this.opts.source)) };
    b.loading = false;
    this._renderCapture();
    if (this.capture.error) this._error(this.capture.error);
    if (this.capture.running) this._pollCapture();
  }

  _pollCapture() {
    clearTimeout(this.capTimer);
    this.capTimer = setTimeout(async () => {
      this.capture = { ...this.capture, ...(await this.api.sampler_capture_status()) };
      this._renderCapture();
      if (this.capture.running && !$('#sampler').hidden) this._pollCapture();
    }, 200);
  }

  async grab() {
    const secs = Math.max(1, +$('#sp-grab-s').value || this.opts.grab);
    this._opened(await this.api.sampler_capture_grab(secs));
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
    $('#sp-view-info').textContent = `Vista ${fmt(start)} – ${fmt(start + len)}`;
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
    const t = this._time(e), k = Math.exp(e.deltaY * 0.002);
    this.setView(t - (t - this.view.start) * k, t + (this.view.end - t) * k);
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
      ctx.fillStyle = sel ? 'rgba(47,141,253,.28)' : r.on ? 'rgba(47,141,253,.13)' : 'rgba(143,155,182,.08)';
      ctx.fillRect(x0, 0, x1 - x0, H);
      ctx.fillStyle = sel ? '#6cc2fd' : '#2f8dfd';
      ctx.fillRect(x0, 0, Math.max(1, dpr), H);
      ctx.fillRect(x1 - Math.max(1, dpr), 0, Math.max(1, dpr), H);
      ctx.font = `${11 * dpr}px ${css.getPropertyValue('--wa-font-family-body')}`;
      ctx.fillStyle = sel ? '#e6eaf4' : '#8f9bb6';
      if (x1 - x0 > 30 * dpr) ctx.fillText(String(i + 1), x0 + 4 * dpr, 14 * dpr);
    });
    // grid (seconds)
    const len = end - start;
    const step = [0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60, 300].find((s) => len / s < 12) || 600;
    ctx.fillStyle = 'rgba(143,155,182,.5)';
    ctx.font = `${10 * dpr}px ${css.getPropertyValue('--wa-font-family-code')}`;
    for (let t = Math.ceil(start / step) * step; t < end; t += step) {
      const x = this._x(t);
      ctx.fillRect(x, H - 4 * dpr, 1, 4 * dpr);
      ctx.fillText(fmt(t).replace(' s', 's'), x + 3 * dpr, H - 6 * dpr);
    }
    // waveform
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, '#32d5fe');
    grad.addColorStop(0.5, '#2086fd');
    grad.addColorStop(1, '#32d5fe');
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
      ctx.fillStyle = this.drag.limited ? 'rgba(239,83,80,.25)' : 'rgba(108,194,253,.25)';
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
    ctx.fillStyle = 'rgba(143,155,182,.55)';
    const n = p.wave_min.length;
    for (let k = 0; k < n; k++) {
      const x = k / n * W;
      ctx.fillRect(x, H / 2 - p.wave_max[k] * H / 2, Math.max(1, W / n), Math.max(1, (p.wave_max[k] - p.wave_min[k]) * H / 2));
    }
    ctx.fillStyle = 'rgba(47,141,253,.5)';
    for (const r of this.regions) ctx.fillRect(r.start / this.duration * W, H - 3, Math.max(1, (r.end - r.start) / this.duration * W), 3);
    const x0 = this.view.start / this.duration * W, x1 = this.view.end / this.duration * W;
    ctx.strokeStyle = '#2f8dfd';
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
    const t = this._time(e), edge = this._edgeAt(e);
    if (edge) this.drag = { kind: 'edge', ...edge };
    else this.drag = { kind: 'new', a: t, b: t, x: e.clientX, hit: this._regionAt(t) };
  }

  _move(e) {
    if (!this.session) return;
    const t = Math.max(0, Math.min(this.duration, this._time(e)));
    if (!this.drag) { this.cv.style.cursor = this._edgeAt(e) ? 'ew-resize' : 'crosshair'; return; }
    if (this.drag.kind === 'edge') {
      const r = this.regions[this.drag.i];
      if (this.drag.side === 'start') r.start = Math.max(r.end - this.maxS, Math.min(t, r.end - 0.005));
      else r.end = Math.min(r.start + this.maxS, Math.max(t, r.start + 0.005));
      this.sel = this.drag.i;
    } else {
      const lim = this.maxS;
      this.drag.limited = Math.abs(t - this.drag.a) > lim;
      this.drag.b = this.drag.a + Math.sign(t - this.drag.a) * Math.min(lim, Math.abs(t - this.drag.a));
      $('#sp-view-info').innerHTML = `Nuova regione: <span class="${this.drag.limited ? 'error' : ''}">${fmt(Math.abs(this.drag.b - this.drag.a))}</span> / max ${this.maxS} s`;
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
    toast(found.length ? `${found.length} regioni ${whole ? '' : 'nella parte visibile '}sui transienti` : 'Nessun transiente trovato: prova ad alzare la sensibilità');
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
    $('#sp-count').textContent = this.regions.length ? `(${on} di ${this.regions.length} selezionate)` : '';
    $('#sp-export').disabled = !on;
    $('#sp-clear').disabled = !this.regions.length;
  }

  renderRegions() {
    const box = $('#sp-regions');
    this._renderCount();
    if (!this.regions.length) {
      box.innerHTML = `<div class="hint sp-regions-empty">${this.session ? 'Nessuna regione: trascina sulla forma d\'onda o usa «Taglia sui transienti».' : ''}</div>`;
      return;
    }
    box.innerHTML = this.regions.map((r, i) => `
      <div class="sp-row${i === this.sel ? ' sel' : ''}" data-i="${i}">
        ${check('', r.on, { label: 'Esporta' })}
        <span class="sp-num">${i + 1}</span>
        <wa-input size="s" value="${esc(r.name)}" placeholder="${esc(this._defaultName(i))}" label="Nome"></wa-input>
        <span class="sp-time">${fmt(r.start)}</span>
        <span class="sp-time ${r.end - r.start >= this.maxS - 1e-3 ? 'error' : ''}">${fmt(r.end - r.start)}</span>
        ${iconBtn('play', 'Ascolta', { 'data-act': 'play' })}
        ${iconBtn('search', 'Mostra sulla forma d\'onda', { 'data-act': 'zoom' })}
        ${iconBtn('x', 'Elimina', { 'data-act': 'del' })}
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
  async export() {
    // empty names get the placeholder shown in the list, so numbers match the region numbers
    const regions = this.regions.map((r, i) => ({ start: r.start, end: r.end, on: r.on, name: r.name || this._defaultName(i) }))
      .filter((r) => r.on).map(({ start, end, name }) => ({ start, end, name }));
    if (!regions.length) return;
    const b = $('#sp-export');
    b.loading = true;
    const r = await this.api.sampler_export(regions, this.opts);
    b.loading = false;
    if (r.error) return this._error(r.error);
    const n = r.paths.length;
    toast(`${n} sample esportat${n === 1 ? 'o' : 'i'}${r.in_library ? ': li analizzo nella libreria' : ''}`);
    const head = $('#sp-regions-head-msg') || Object.assign(document.createElement('div'), { id: 'sp-regions-head-msg', className: 'hint sp-exported' });
    head.innerHTML = `Esportati in <a href="#">${esc(r.folder)}</a>`;
    head.querySelector('a').onclick = (e) => { e.preventDefault(); this.api.reveal_path(r.paths[0]); };
    $('#sp-regions').before(head);
  }
}
