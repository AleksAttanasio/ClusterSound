// Detail drawer: class, actions, dynamics (waveform + RMS envelope + ADSR), spectrogram, metrics.

import { btn, FILE_MANAGER } from './kit.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (v, d = 1, unit = '') => (v === null || v === undefined || Number.isNaN(v) ? '—' : `${Number(v).toFixed(d)}${unit}`);
const fmtTime = (s) => (s === null || s === undefined ? '—' : s < 1 ? `${(s * 1000).toFixed(0)} ms` : `${s.toFixed(2)} s`);

const playLabel = (playing) => playing ? '<wa-icon slot="start" name="square"></wa-icon>Stop' : '<wa-icon slot="start" name="play"></wa-icon>Play';

const ADSR_COLORS = { A: '#ffb74d', D: '#ef5350', S: '#66bb6a', R: '#42a5f5' };

// "magma"-like ramp for the spectrogram
const RAMP = [[0, 0, 4], [40, 11, 84], [101, 21, 110], [159, 42, 99], [212, 72, 66], [245, 125, 21], [250, 193, 39], [252, 255, 164]];
function ramp(t) {
  const x = Math.max(0, Math.min(1, t)) * (RAMP.length - 1);
  const i = Math.min(RAMP.length - 2, Math.floor(x));
  const f = x - i;
  return RAMP[i].map((a, k) => Math.round(a + (RAMP[i + 1][k] - a) * f));
}

export class Panel {
  constructor(root, content, { classes, groups, onRelabel, onReveal, onSimilar, onPlayToggle, onSeek, onClose, onSend, onStore }) {
    this.root = root;
    this.content = content;
    this.classes = classes;
    this.groups = groups;
    this.cb = { onRelabel, onReveal, onSimilar, onPlayToggle, onSeek, onClose, onSend, onStore };
    this.d = null;
    this.playhead = null;
  }

  open() { this.root.classList.add('open'); this.root.setAttribute('aria-hidden', 'false'); }
  close() { this.root.classList.remove('open'); this.root.setAttribute('aria-hidden', 'true'); this.d = null; }
  isOpen() { return this.root.classList.contains('open'); }

  loading(item, cls) {
    this.open();
    this.content.innerHTML = `
      ${this._classHeader(cls, item.conf, item.user)}
      <div class="p-name">${esc(item.name)}</div>
      <div class="p-path">${esc(item.rel)}</div>
      <div class="hint">Analisi della dinamica…</div>`;
  }

  _classHeader(cls, conf, user) {
    return `<div class="p-class">
      <span class="p-badge" style="background:${cls.color}26;color:${cls.color}"><span class="dot" style="background:${cls.color}"></span>${esc(cls.label)}</span>
      <span class="p-conf">${user ? '' : `${Math.round(conf * 100)}% confidenza`}</span>
      ${user ? '<span class="p-user"><wa-icon name="check"></wa-icon> etichetta manuale</span>' : ''}
    </div>`;
  }

  render(d, playing) {
    this.d = d;
    const cls = this.classes.find((c) => c.id === d.cls);
    const dyn = d.dyn || {};
    const a = dyn.adsr || {};
    const info = d.info || {};
    const byId = Object.fromEntries(this.classes.map((c) => [c.id, c]));
    const alts = (d.alts || []).filter((x) => x.cls !== d.cls).slice(0, 3);
    const options = this.groups.map((g, k) => `${k ? '<wa-divider></wa-divider>' : ''}<small>${esc(g)}</small>${this.classes.filter((c) => c.group === g)
      .map((c) => `<wa-option value="${c.id}" ${c.id === d.cls ? 'selected' : ''}><span slot="start" class="dot" style="background:${c.color}"></span>${esc(c.label)}</wa-option>`).join('')}`).join('');
    const bit = (info.subtype || '').replace('PCM_', '').replace('FLOAT', '32f').replace('DOUBLE', '64f');

    this.content.innerHTML = `
      ${this._classHeader(cls, d.conf, d.user)}
      <div>
        <div class="p-name">${esc(d.name)}</div>
        <div class="p-path" title="${esc(d.path)}">${esc(d.rel)}</div>
      </div>
      <div class="p-actions">
        ${btn(playLabel(playing), { variant: 'brand', 'data-act': 'play' })}
        ${btn('Mostra nella cartella', { icon: 'folder-open', 'data-act': 'reveal', title: `Apre ${FILE_MANAGER} con il file selezionato` })}
        ${btn('Trova simili', { icon: 'sparkles', 'data-act': 'similar' })}
        ${btn('Invia', { 'data-act': 'send', 'with-caret': true, title: 'Aggiungi il sample a un bus del Sequencer o al Drum Rack' })}
        ${btn('Altri nello Store', { icon: 'store', 'data-act': 'store', title: `Cerca sample gratuiti di tipo «${cls.label}» nello Store` })}
      </div>

      <div>
        <div class="section-title">Dinamica
          <span class="legend-inline"><span style="color:#8a8a8a">Onda</span><span style="color:#ececec">RMS dB</span></span>
        </div>
        ${dyn.error ? `<div class="error">${esc(dyn.error)}</div>` : '<canvas class="wave" id="cv-wave"></canvas><canvas class="mel" id="cv-mel"></canvas>'}
      </div>

      <div class="metrics">
        ${[
          ['Durata', fmtTime(info.duration ?? dyn.duration)],
          ['Peak', fmt(dyn.peak_dbfs, 1, ' dBFS')],
          ['RMS', fmt(dyn.rms_dbfs, 1, ' dBFS')],
          ['Crest', fmt(dyn.crest_db, 1, ' dB')],
          ['Attack', fmt(a.attack_ms, a.attack_ms < 10 ? 1 : 0, ' ms')],
          ['Decay', fmt(a.decay_ms, 0, ' ms')],
          ['Sustain', fmt(a.sustain_db, 1, ' dB')],
          ['Release', fmt(a.release_ms, 0, ' ms')],
          ['T60', fmtTime(dyn.t60)],
          ['Formato', `${info.samplerate ? (info.samplerate / 1000).toFixed(1) + ' kHz' : '—'}`],
          ['Canali / bit', `${info.channels ?? '—'} / ${bit || '—'}`],
          ['Tipo', esc(d.type || '—')],
          ['Centroide', fmt(d.features?.centroid, 0, ' Hz')],
          ['Armonicità', fmt(d.features?.harmonicity, 2)],
          ['Sottocluster', `#${d.sub}`],
        ].map(([k, v]) => `<div class="metric"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('')}
      </div>

      <div>
        <div class="section-title">Classe</div>
        <wa-select size="s" class="cls-select" id="cls-select" value="${esc(d.cls)}">${options}</wa-select>
        ${alts.length ? `<div class="hint" style="margin:8px 0 6px">Alternative</div><div class="alts">${alts.map((x) => {
          const c = byId[x.cls];
          return `<wa-button size="xs" pill appearance="outlined" class="alt" data-cls="${c.id}"><span slot="start" class="dot" style="background:${c.color}"></span>${esc(c.label)} ${Math.round(x.p * 100)}%</wa-button>`;
        }).join('')}</div>` : ''}
        ${d.user ? '<div style="margin-top:8px"><a href="#" id="clear-label">Rimuovi etichetta manuale</a></div>' : ''}
        <div class="hint" style="margin-top:8px">Le correzioni entrano nel training: le altre classificazioni si aggiornano in pochi secondi.</div>
      </div>`;

    this.content.querySelector('[data-act=play]').onclick = () => this.cb.onPlayToggle();
    this.content.querySelector('[data-act=reveal]').onclick = () => this.cb.onReveal(d.id);
    this.content.querySelector('[data-act=similar]').onclick = () => this.cb.onSimilar(d.id);
    this.content.querySelector('[data-act=store]').onclick = () => this.cb.onStore(d.cls);
    this.content.querySelector('[data-act=send]').onclick = (e) => {
      const r = e.currentTarget.getBoundingClientRect();
      this.cb.onSend(d.id, r.left - 120, r.bottom + 4);
    };
    this.content.querySelector('#cls-select').onchange = (e) => this.cb.onRelabel(d.id, e.target.value);
    this.content.querySelectorAll('.alt').forEach((b) => { b.onclick = () => this.cb.onRelabel(d.id, b.dataset.cls); });
    const clr = this.content.querySelector('#clear-label');
    if (clr) clr.onclick = (e) => { e.preventDefault(); this.cb.onRelabel(d.id, null); };

    if (!dyn.error) {
      this.waveCanvas = this.content.querySelector('#cv-wave');
      this.melCanvas = this.content.querySelector('#cv-mel');
      for (const cv of [this.waveCanvas, this.melCanvas]) {
        cv.onclick = (e) => {
          const r = cv.getBoundingClientRect();
          this.cb.onSeek(((e.clientX - r.left) / r.width) * (dyn.duration || 0));
        };
      }
      this.drawWave();
      this.drawMel();
    }
  }

  setPlaying(playing) {
    const b = this.content.querySelector('[data-act=play]');
    if (b) b.innerHTML = playLabel(playing);
  }

  _fit(cv) {
    const dpr = window.devicePixelRatio || 1;
    const w = cv.clientWidth, h = cv.clientHeight;
    if (cv.width !== w * dpr || cv.height !== h * dpr) { cv.width = w * dpr; cv.height = h * dpr; }
    const ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return [ctx, w, h];
  }

  drawWave(playhead = null) {
    const d = this.d;
    if (!d || !this.waveCanvas) return;
    const dyn = d.dyn;
    const [ctx, w, h] = this._fit(this.waveCanvas);
    ctx.clearRect(0, 0, w, h);
    const dur = dyn.duration || 1;
    const X = (t) => (t / dur) * w;
    const a = dyn.adsr || {};

    // ADSR phases as shaded bands
    const phases = [['A', a.attack_start, a.attack_end], ['D', a.attack_end, a.decay_end],
      ['S', a.decay_end, a.release_start], ['R', a.release_start, a.release_end]];
    ctx.font = `600 10px ${getComputedStyle(document.documentElement).getPropertyValue('--wa-font-family-body')}`;
    for (const [k, t0, t1] of phases) {
      if (t0 === undefined || t1 === undefined || t1 <= t0) continue;
      ctx.fillStyle = ADSR_COLORS[k] + '1c';
      ctx.fillRect(X(t0), 0, Math.max(1, X(t1) - X(t0)), h);
      ctx.fillStyle = ADSR_COLORS[k];
      ctx.fillRect(X(t0), 0, 1, h);
      if (X(t1) - X(t0) > 10) ctx.fillText(k, X(t0) + 3, 12);
    }

    // waveform (min/max columns)
    const mid = h / 2, amp = h * 0.46;
    const mn = dyn.wave_min || [], mx = dyn.wave_max || [];
    ctx.fillStyle = '#8a8a8a';
    const n = mx.length;
    for (let i = 0; i < n; i++) {
      const x = (i / n) * w;
      const y0 = mid - mx[i] * amp, y1 = mid - mn[i] * amp;
      ctx.fillRect(x, y0, Math.max(1, w / n), Math.max(1, y1 - y0));
    }

    // RMS envelope in dB (0 dB at top, -60 dB at bottom)
    const env = dyn.env_db || [];
    const dt = dyn.env_dt || 0.005;
    const Y = (db) => (Math.min(0, Math.max(-60, db)) / -60) * (h - 4) + 2;
    ctx.strokeStyle = '#ececec';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    env.forEach((db, i) => { const x = X(i * dt); i ? ctx.lineTo(x, Y(db)) : ctx.moveTo(x, Y(db)); });
    ctx.stroke();
    // sustain level
    if (a.sustain_db !== undefined) {
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = ADSR_COLORS.S;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, Y(a.sustain_db)); ctx.lineTo(w, Y(a.sustain_db));
      ctx.stroke();
      ctx.setLineDash([]);
    }
    // dB scale
    ctx.fillStyle = '#6b6b6b';
    ctx.font = `9px ${getComputedStyle(document.documentElement).getPropertyValue('--wa-font-family-code')}`;
    for (const db of [0, -20, -40, -60]) ctx.fillText(`${db}`, w - 20, Math.min(h - 3, Y(db) + 9));

    if (playhead !== null) {
      ctx.fillStyle = '#fff';
      ctx.fillRect(X(playhead), 0, 1.5, h);
    }
  }

  drawMel(playhead = null) {
    const d = this.d;
    if (!d || !this.melCanvas) return;
    const mel = d.dyn.mel || [];
    const [ctx, w, h] = this._fit(this.melCanvas);
    if (!mel.length) { ctx.clearRect(0, 0, w, h); return; }
    if (!this._melImg || this._melFor !== d.id) {
      const T = mel.length, F = mel[0].length;
      const img = new ImageData(T, F);
      for (let t = 0; t < T; t++) {
        for (let f = 0; f < F; f++) {
          const [r, g, b] = ramp(mel[t][f] / 255);
          const o = ((F - 1 - f) * T + t) * 4;
          img.data[o] = r; img.data[o + 1] = g; img.data[o + 2] = b; img.data[o + 3] = 255;
        }
      }
      const off = document.createElement('canvas');
      off.width = T; off.height = F;
      off.getContext('2d').putImageData(img, 0, 0);
      this._melImg = off;
      this._melFor = d.id;
    }
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(this._melImg, 0, 0, w, h);
    if (playhead !== null) {
      ctx.fillStyle = '#fff';
      ctx.fillRect((playhead / (d.dyn.duration || 1)) * w, 0, 1.5, h);
    }
  }

  drawPlayhead(t) {
    this.drawWave(t);
    this.drawMel(t);
  }
}
