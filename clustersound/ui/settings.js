// Settings page: the fine-tuning options of every section, one block per section.
// Sections are registered by their owners (app.js, online.js, the editors) with a render function;
// every option is saved as soon as it changes. Anywhere in the UI, a "⋯" button made with
// settingsLink(section) opens this page on that section.
import { icon, iconBtn } from './kit.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export function openSettings(section = '') {
  window.dispatchEvent(new CustomEvent('cs:open-settings', { detail: section }));
}

export const settingsLink = (section, title = 'Impostazioni') =>
  iconBtn('ellipsis', title, { 'data-settings-link': section, cls: 'more-btn' });

// One option: label and hint on the left, the control on the right.
export const setRow = (label, hint, control, { cls = '', id = '' } = {}) =>
  `<div class="set-row ${cls}"${id ? ` id="${id}"` : ''}><div class="set-text"><div class="set-label">${label}</div>${hint ? `<div class="set-hint">${hint}</div>` : ''}</div><div class="set-ctl">${control}</div></div>`;

// "Salvato" next to the title of the section that contains el.
export function savedFlash(el) {
  const s = el?.closest('.set-section')?.querySelector('.set-saved');
  if (!s) return;
  s.classList.add('on');
  clearTimeout(s._t);
  s._t = setTimeout(() => s.classList.remove('on'), 1400);
}

// Any element with data-settings-link opens the page on that section.
document.addEventListener('click', (e) => {
  const b = e.target.closest?.('[data-settings-link]');
  if (b) { e.preventDefault(); openSettings(b.dataset.settingsLink); }
});

export class Settings {
  constructor(root) {
    this.root = root;
    this.sections = [];
    this._run = 0;
    this._lock = 0; // while a requested section scrolls into view, scrolling does not move the index
    root.innerHTML = `<nav class="set-index" id="set-index"></nav><div class="set-main" id="set-main"></div>`;
    this.index = root.querySelector('#set-index');
    this.main = root.querySelector('#set-main');
    this.index.onclick = (e) => {
      const a = e.target.closest('[data-sec]');
      if (a) this.scrollTo(a.dataset.sec);
    };
    this.main.addEventListener('scroll', () => this._syncIndex());
  }

  /** render(body) fills the section's card; it runs every time the page is shown, so values are fresh. */
  add(id, title, iconName, render) {
    this.sections.push({ id, title, icon: iconName, render });
  }

  async show(section = '') {
    const run = ++this._run; // a newer show() (e.g. a second click) wins over one still rendering
    this.index.innerHTML = this.sections.map((s) =>
      `<button type="button" class="set-link" data-sec="${s.id}">${icon(s.icon)}<span>${esc(s.title)}</span></button>`).join('');
    this.main.innerHTML = this.sections.map((s) => `<section class="set-section" id="set-${s.id}" data-sec="${s.id}">
        <h2>${icon(s.icon)}<span>${esc(s.title)}</span><span class="set-saved">${icon('check')} Salvato</span></h2>
        <div class="set-card"></div></section>`).join('');
    await Promise.all(this.sections.map(async (s) => {
      const body = this.main.querySelector(`#set-${s.id} .set-card`);
      try { await s.render(body); } catch (err) {
        console.error(err);
        body.innerHTML = setRow('Impostazioni non disponibili', esc(err?.message || err), '');
      }
    }));
    if (run === this._run) this.scrollTo(section || this.sections[0]?.id, false);
  }

  /** Re-render one section in place (after an action changed what it shows). */
  async refresh(id) {
    const s = this.sections.find((x) => x.id === id);
    const body = this.main.querySelector(`#set-${id} .set-card`);
    if (s && body) await s.render(body);
  }

  scrollTo(id, smooth = true) {
    const el = this.main.querySelector(`#set-${id}`);
    if (!el) return;
    const top = this.main.scrollTop + el.getBoundingClientRect().top - this.main.getBoundingClientRect().top - 12;
    this.main.scrollTo({ top, behavior: smooth ? 'smooth' : 'auto' });
    this._setActive(id);
    this._lock = Date.now() + (smooth ? 700 : 100);
    el.classList.remove('flash');
    void el.offsetWidth;
    el.classList.add('flash');
  }

  _setActive(id) {
    this.index.querySelectorAll('.set-link').forEach((a) => a.classList.toggle('active', a.dataset.sec === id));
  }

  _syncIndex() {
    if (Date.now() < this._lock) return;
    const top = this.main.getBoundingClientRect().top + 40;
    let cur = this.sections[0]?.id;
    for (const el of this.main.querySelectorAll('.set-section')) if (el.getBoundingClientRect().top <= top) cur = el.dataset.sec;
    this._setActive(cur);
  }
}

// ------------------------------------------------------------------ Generale
// App-wide options: the Ableton Live bridge and the temporary cache.
export function generalSection(api, onSettings) {
  return async (body) => {
    const s = await api.get_settings();
    body.innerHTML =
      setRow('Bridge per Ableton Live', 'Porta usata dal device Max for Live ClusterSound per ricevere kit, pattern e clip. <span id="set-live-status"></span>',
        `<wa-number-input id="set-live-port" size="s" min="1024" max="65535" step="1" value="${s.live_port}" without-steppers label="Porta" style="width:110px"></wa-number-input>`)
      + setRow('Cache temporanea', `Anteprime dello Store e sample provati nel Sequencer. In uso: <b id="set-cache-used">${s.cache_used_mb}</b> MB. Oltre il limite si eliminano i file usati meno di recente; quelli del pattern aperto restano.`,
        `<wa-number-input id="set-cache" size="s" min="50" max="10000" step="50" value="${s.cache_mb}" label="Limite" style="width:150px"><span slot="end" class="hint">MB</span></wa-number-input>
         <wa-button id="set-cache-clear" size="s" appearance="filled-outlined"><wa-icon slot="start" name="trash-2"></wa-icon>Svuota</wa-button>`);
    const status = body.querySelector('#set-live-status');
    api.live_status().then((st) => {
      status.textContent = st.running
        ? `Attivo su 127.0.0.1:${st.port}. Preset per Live in ${st.stage}${st.stage_root === 'places' ? ' (aggiungi la cartella ai Places di Live).' : '.'}`
        : `Non attivo: ${st.error || 'riavvia l\'app'}.`;
    });
    body.querySelector('#set-live-port').addEventListener('change', async (e) => {
      onSettings(await api.set_setting('live_port', e.target.value));
      savedFlash(body);
    });
    body.querySelector('#set-cache').addEventListener('change', async (e) => {
      const ns = await api.set_setting('cache_mb', e.target.value);
      body.querySelector('#set-cache-used').textContent = ns.cache_used_mb;
      onSettings(ns);
      savedFlash(body);
    });
    body.querySelector('#set-cache-clear').onclick = async () => {
      const ns = await api.clear_cache();
      body.querySelector('#set-cache-used').textContent = ns.cache_used_mb;
      onSettings(ns);
      savedFlash(body);
    };
  };
}
