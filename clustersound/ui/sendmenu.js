// "Send" popup: route a sample (library, online or file) to a sequencer bus (as a new layer or replacing
// the current one) or to a group of the Drum Rack. Used from the 3D view, the list, the detail panel and the
// Online tab. The Drum Rack part stays open to build the group one sample at a time, with suggestions.

import { t } from './i18n.js';
import { svg } from './icons.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LS_ALL_BUSES = 'clustersound.sendAllBuses';

export function suggestBus(buses, cls) {
  if (!cls) return null;
  if (cls === 'sub808' || cls === 'bass') return 'bass';
  const b = buses.find((x) => !x.melodic && x.classes.includes(cls));
  return b ? b.id : 'fx';
}

let current = null;

export function closeSendMenu() {
  if (current) { current.remove(); current = null; }
  document.removeEventListener('pointerdown', onOutside, true);
}

function onOutside(e) {
  if (current && !current.contains(e.target)) closeSendMenu();
}

const ib = (attrs, icon, title, size = 12) => `<button class="send-ib" ${attrs} title="${esc(title)}">${svg(icon, size)}</button>`;

// buses: ui buses (id, label, color, melodic); counts: bus id -> number of layers (for the hint);
// rack: {group, groups(), samples(g), suggest(g, skip), add(ref, g), preview(ref)} for the Drum Rack section;
// onOpen(tab): the arrows next to the section titles open the Drum Rack / Sequencer tab
export function showSendMenu({ x, y, ref, buses, counts = {}, onPick, rack, onOpen }) {
  closeSendMenu();
  const sug = suggestBus(buses, ref.cls);
  const ordered = sug ? [buses.find((b) => b.id === sug), ...buses.filter((b) => b.id !== sug)] : buses;
  let showAll = false;
  try { showAll = localStorage.getItem(LS_ALL_BUSES) === '1'; } catch { /* private mode */ }
  let group = rack?.group ?? 0;
  let pickGroup = false;
  let shown = [];   // refs with a play button in the Drum Rack part: group samples, then suggestions
  let sugg = [];

  const el = document.createElement('div');
  el.className = 'send-menu';
  el.innerHTML = `<div class="send-title" title="${esc(ref.name)}">${t('Send')} · <b>${esc(ref.name)}</b></div>
    ${rack ? '<div class="send-rk"></div>' : ''}
    <div class="send-sec"><wa-icon name="audio-lines"></wa-icon>Sequencer<span class="send-sec-tools">
      ${sug ? '<span data-eye></span>' : ''}${onOpen ? ib('data-open="pattern"', 'arrow-right', t('Open the Sequencer tab')) : ''}</span></div>
    <div class="send-buses"></div>`;
  const rkBox = el.querySelector('.send-rk'), busBox = el.querySelector('.send-buses');

  const place = () => {
    const W = window.innerWidth, H = window.innerHeight;
    const r = el.getBoundingClientRect();
    el.style.left = `${Math.max(8, Math.min(x, W - r.width - 8))}px`;
    el.style.top = `${Math.max(8, Math.min(y, H - r.height - 8))}px`;
  };

  const renderBuses = () => {
    const list = showAll || !sug ? ordered : ordered.filter((b) => b.id === sug);
    const eye = el.querySelector('[data-eye]');
    if (eye) eye.outerHTML = ib('data-eye', showAll ? 'eye-off' : 'eye', showAll ? t('Show only the suggested track') : t('Show all the tracks'));
    busBox.innerHTML = list.map((b) => `<div class="send-row ${b.id === sug ? 'sug' : ''}" data-bus="${b.id}">
      <span class="dot" style="background:${b.color}"></span><span class="send-bus">${esc(b.label)}${b.id === sug ? ` <i>${t('suggested')}</i>` : ''}</span>
      <span class="send-count">${counts[b.id] ? (counts[b.id] === 1 ? t('1 layer') : t('{n} layers', { n: counts[b.id] })) : t('Empty')}</span>
      <wa-button size="xs" appearance="filled-outlined" data-mode="add" title="${t('Add as a new layer of the bus')}"><wa-icon name="plus" label="${t('Add as a new layer of the bus')}"></wa-icon></wa-button>
      <wa-button size="xs" appearance="filled-outlined" data-mode="replace" title="${t('Replace the selected layer (or the first one)')}" ${counts[b.id] ? '' : 'disabled'}>${svg('replace', 14)}</wa-button>
    </div>`).join('');
  };

  let token = 0;
  const renderRack = async () => {
    if (!rack) return;
    const tok = ++token;
    const [groups, samples] = await Promise.all([rack.groups(), rack.samples(group)]);
    if (tok !== token || !el.isConnected) return;
    const cur = groups.find((g) => g.g === group) || groups[0];
    shown = samples.map((s) => s.ref);
    sugg = [];
    seen = new Set();
    rkBox.innerHTML = `<div class="send-sec"><wa-icon name="drum"></wa-icon>Drum Rack
        <button class="send-grp" data-grp title="${t('Show another group of the Drum Rack')}">${esc(cur.label)} ${svg('chevron-down', 11)}</button>
        <span class="send-sec-tools">${onOpen ? ib('data-open="rack"', 'arrow-right', t('Open the Drum Rack tab')) : ''}</span></div>
      ${pickGroup ? `<div class="send-grp-list">${groups.map((g) => `<div class="send-grp-row ${g.g === group ? 'on' : ''}" data-g="${g.g}">
        <span>${esc(g.label)}</span><span class="send-count">${g.count || t('Empty')}</span></div>`).join('')}</div>` : ''}
      <div class="send-rk-list">${samples.map((s, k) => `<div class="send-rk-row">${ib(`data-play="${k}"`, 'play', t('Listen'), 10)}
        <span class="send-pad">${esc(s.padName)}</span><span class="send-rk-name" title="${esc(s.ref.name)}">${esc(s.ref.name)}</span></div>`).join('')}</div>
      <div class="send-rack"><wa-button size="xs" appearance="filled-outlined" data-add title="${t('Adds the sample to this group (on the selected pad or the first free one)')}"><wa-icon name="plus" label="${t('Add')}"></wa-icon></wa-button></div>
      <div class="send-sugg"></div>`;
    place();
    nGroup = samples.length;
    if (samples.some((s) => s.ref.kind === 'library')) renderSugg(tok);
  };

  // 3 suggestions for the group; `more` skips the ones already proposed (and starts over when none is left)
  let seen = new Set(), nGroup = 0;
  const renderSugg = async (tok, more = false) => {
    if (more) sugg.forEach((c) => seen.add(c.id));
    const skip = () => [...(ref.kind === 'library' ? [ref.id] : []), ...seen];
    let next = await rack.suggest(group, skip());
    if (!next.length && seen.size) { seen = new Set(); next = await rack.suggest(group, skip()); }
    if (tok !== token || !el.isConnected || !next.length) return;
    sugg = next;
    shown = [...shown.slice(0, nGroup), ...sugg];
    el.querySelector('.send-sugg').innerHTML = `<div class="send-sugg-title">${t('suggested')}
        ${ib('data-more', 'refresh-cw', t('Suggest 3 other samples'), 11)}</div><div class="send-sugg-row">
      ${sugg.map((c, k) => `<div class="send-sug">${ib(`data-play="${nGroup + k}"`, 'play', t('Listen'), 10)}
        <button class="send-sug-name" data-sug="${k}" title="${esc(t('Add {name} to the group', { name: c.name }))}">${esc(c.name)}</button></div>`).join('')}</div>`;
    place();
  };

  document.body.appendChild(el);
  renderBuses();
  place();
  renderRack();

  el.onclick = async (e) => {
    const b = (sel) => e.target.closest(sel);
    if (b('[data-open]')) { closeSendMenu(); onOpen(b('[data-open]').dataset.open); return; }
    if (b('[data-eye]')) {
      showAll = !showAll;
      try { localStorage.setItem(LS_ALL_BUSES, showAll ? '1' : '0'); } catch { /* private mode */ }
      renderBuses(); place(); return;
    }
    if (b('[data-grp]')) { pickGroup = !pickGroup; renderRack(); return; }
    if (b('[data-g]')) { group = +b('[data-g]').dataset.g; pickGroup = false; renderRack(); return; }
    if (b('[data-more]')) { renderSugg(token, true); return; }
    if (b('[data-play]')) { rack.preview(shown[+b('[data-play]').dataset.play]); return; }
    if (b('[data-add]') || b('[data-sug]')) {
      const r = b('[data-add]') ? ref : sugg[+b('[data-sug]').dataset.sug];
      await rack.add(r, group);
      renderRack(); return;
    }
    const btn = b('[data-mode]');
    if (!btn) return;
    closeSendMenu();
    onPick(btn.closest('[data-bus]').dataset.bus, btn.dataset.mode);
  };
  current = el;
  setTimeout(() => document.addEventListener('pointerdown', onOutside, true), 0);
}

// Small floating panel under `anchor` (closes on outside click / Esc); returns it, with .close().
export function showPopover(anchor, html, cls = '') {
  document.querySelector('.popover')?.close?.();
  const el = document.createElement('div');
  el.className = `popover ${cls}`.trim(); // before measuring: the class can change the width
  el.innerHTML = html;
  document.body.appendChild(el);
  // under the anchor, or over it when there is no room; again when the content grows (web components render late)
  const place = () => {
    const a = anchor.getBoundingClientRect(), r = el.getBoundingClientRect(), H = window.innerHeight;
    el.style.left = `${Math.max(8, Math.min(a.right - r.width, window.innerWidth - r.width - 8))}px`;
    const below = a.bottom + 6, above = a.top - r.height - 6;
    const top = below + r.height <= H - 8 ? below : above >= 8 ? above : H - r.height - 8;
    el.style.top = `${Math.max(8, Math.min(top, H - r.height - 8))}px`;
  };
  place();
  const ro = new ResizeObserver(place);
  ro.observe(el);
  const outside = (e) => { if (!el.contains(e.target) && !anchor.contains(e.target)) el.close(); };
  const esc_ = (e) => { if (e.key === 'Escape') el.close(); };
  el.close = () => {
    ro.disconnect();
    el.remove();
    document.removeEventListener('pointerdown', outside, true);
    document.removeEventListener('keydown', esc_, true);
  };
  setTimeout(() => {
    document.addEventListener('pointerdown', outside, true);
    document.addEventListener('keydown', esc_, true);
  }, 0);
  return el;
}

let toastTimer;
export function toast(msg) {
  let el = document.getElementById('toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast';
    el.className = 'toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
}
