// Shared Web Awesome helpers: icon library setup + markup builders used by every screen.
// Must be imported before any <wa-*> element is rendered (index.html loads it first).
import { registerIconLibrary, setBasePath } from './vendor/webawesome/webawesome.js';
import './vendor/webawesome/translations/it.js';

// Absolute, because the autoloader resolves a relative base path against its own chunk URL.
setBasePath(new URL('./vendor/webawesome', import.meta.url).href);

// The app runs offline: the default library resolves to the vendored Lucide subset instead of the
// Font Awesome CDN. Web Awesome's own system icons (close, check, chevrons) are inlined in its bundle.
const ICONS = new URL('./vendor/lucide/', import.meta.url);
registerIconLibrary('default', { resolver: (name) => new URL(`${name}.svg`, ICONS).href });

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// {a: 1, b: true, c: false, d: null} -> ' a="1" b' (false/null attributes are dropped)
export const attrs = (o = {}) => Object.entries(o).map(([k, v]) =>
  v === false || v == null ? '' : v === true ? ` ${k}` : ` ${k}="${esc(v)}"`).join('');

export const icon = (name, label = '') => `<wa-icon name="${name}"${label ? ` label="${esc(label)}"` : ''}></wa-icon>`;

// Labels are trusted markup (callers escape user data), so icons and <b> can be passed in.
export const btn = (label, { variant = 'neutral', appearance, size = 's', icon: ic, cls = '', ...rest } = {}) =>
  `<wa-button variant="${variant}"${appearance ? ` appearance="${appearance}"` : variant === 'neutral' ? ' appearance="filled-outlined"' : ''} size="${size}"${cls ? ` class="${cls}"` : ''}${attrs(rest)}>${ic ? `<wa-icon slot="start" name="${ic}"></wa-icon>` : ''}${label}</wa-button>`;

export const iconBtn = (name, title, { size = 's', cls = '', ...rest } = {}) =>
  `<wa-button appearance="plain" size="${size}" class="icon-btn${cls ? ' ' + cls : ''}" title="${esc(title)}"${attrs(rest)}>${icon(name, title)}</wa-button>`;

// Segmented control. items: [[value, label], …]
export const seg = (items, value, { size = 's', cls = '', ...rest } = {}) =>
  `<wa-radio-group orientation="horizontal" size="${size}" class="seg${cls ? ' ' + cls : ''}" value="${esc(value)}"${attrs(rest)}>${
    items.map(([v, l, extra = {}]) => `<wa-radio appearance="button" value="${esc(v)}"${attrs(extra)}>${l}</wa-radio>`).join('')}</wa-radio-group>`;

// opts: [[value, label], …] or [{value, label, disabled}]
export const options = (opts, value) => opts.map((o) => {
  const [v, l, dis] = Array.isArray(o) ? o : [o.value, o.label, o.disabled];
  return `<wa-option value="${esc(v)}"${dis ? ' disabled' : ''}${String(v) === String(value) ? ' selected' : ''}>${esc(l)}</wa-option>`;
}).join('');

export const select = (opts, value, { size = 's', cls = '', ...rest } = {}) =>
  `<wa-select size="${size}"${cls ? ` class="${cls}"` : ''} value="${esc(value)}"${attrs(rest)}>${options(opts, value)}</wa-select>`;

export const slider = (min, max, step, value, { size = 's', cls = '', ...rest } = {}) =>
  `<wa-slider size="${size}"${cls ? ` class="${cls}"` : ''} min="${min}" max="${max}" step="${step}" value="${value}"${attrs(rest)}></wa-slider>`;

export const check = (label, checked, { size = 's', cls = '', ...rest } = {}) =>
  `<wa-checkbox size="${size}"${cls ? ` class="${cls}"` : ''}${checked ? ' checked' : ''}${attrs(rest)}>${label}</wa-checkbox>`;

export const num = (value, { size = 's', cls = '', ...rest } = {}) =>
  `<wa-number-input size="${size}"${cls ? ` class="${cls}"` : ''} value="${esc(value)}"${attrs(rest)}></wa-number-input>`;

export const text = (value, { size = 's', cls = '', ...rest } = {}) =>
  `<wa-input size="${size}"${cls ? ` class="${cls}"` : ''} value="${esc(value)}"${attrs(rest)}></wa-input>`;

// A reusable <wa-dialog id=…> appended to <body>. Content is replaced on every call; returns the dialog.
// `close()` hides it; `onHide` runs once when it is closed for any reason (Esc, ✕, backdrop, close()).
export function openDialog(id, { label = '', body = '', footer = '', cls = '', width, onHide } = {}) {
  let dlg = document.getElementById(id);
  if (!dlg) {
    dlg = document.createElement('wa-dialog');
    dlg.id = id;
    dlg.setAttribute('light-dismiss', '');
    document.body.appendChild(dlg);
  }
  dlg.className = cls;
  dlg.label = label;
  if (width) dlg.style.setProperty('--width', width);
  dlg.innerHTML = body + (footer ? `<div slot="footer" class="modal-actions">${footer}</div>` : '');
  if (onHide) {
    const h = (e) => { if (e.target !== dlg) return; dlg.removeEventListener('wa-after-hide', h); onHide(); };
    dlg.addEventListener('wa-after-hide', h);
  }
  dlg.close = () => { dlg.open = false; };
  dlg.open = true;
  return dlg;
}

// True while the user is typing into a text-like field, including inside Web Awesome controls.
export function isTypingTarget(e) {
  for (const el of e.composedPath()) {
    if (!(el instanceof Element)) continue;
    const t = el.tagName;
    if (t === 'TEXTAREA' || t === 'SELECT' || el.isContentEditable) return true;
    if (t === 'INPUT') return !['range', 'checkbox', 'radio', 'button'].includes(el.type);
    if (t === 'WA-INPUT' || t === 'WA-NUMBER-INPUT' || t === 'WA-TEXTAREA' || t === 'WA-SELECT') return true;
  }
  return false;
}
