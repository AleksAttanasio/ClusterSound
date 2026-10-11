// Popup "Invia al bus": route a sample (library, online or file) to a pattern bus, as a new layer or
// replacing the current one. Used from the 3D view, the list, the detail panel and the Online tab.

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

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

// buses: ui buses (id, label, color, melodic); counts: bus id -> number of layers (for the hint)
export function showSendMenu({ x, y, ref, buses, counts = {}, onPick }) {
  closeSendMenu();
  const sug = suggestBus(buses, ref.cls);
  const ordered = sug ? [buses.find((b) => b.id === sug), ...buses.filter((b) => b.id !== sug)] : buses;
  const el = document.createElement('div');
  el.className = 'send-menu';
  el.innerHTML = `<div class="send-title" title="${esc(ref.name)}">Invia al bus · <b>${esc(ref.name)}</b></div>
    ${ordered.map((b) => `<div class="send-row ${b.id === sug ? 'sug' : ''}" data-bus="${b.id}">
      <span class="dot" style="background:${b.color}"></span><span class="send-bus">${esc(b.label)}${b.id === sug ? ' <i>consigliato</i>' : ''}</span>
      <span class="send-count">${counts[b.id] ? counts[b.id] + ' layer' : 'vuoto'}</span>
      <button class="btn small" data-mode="add" title="Aggiungi come nuovo layer del bus">+ layer</button>
      <button class="btn small" data-mode="replace" title="Sostituisci il layer selezionato (o il primo)" ${counts[b.id] ? '' : 'disabled'}>sostituisci</button>
    </div>`).join('')}`;
  document.body.appendChild(el);
  const W = window.innerWidth, H = window.innerHeight;
  const r = el.getBoundingClientRect();
  el.style.left = `${Math.max(8, Math.min(x, W - r.width - 8))}px`;
  el.style.top = `${Math.max(8, Math.min(y, H - r.height - 8))}px`;
  el.onclick = (e) => {
    const btn = e.target.closest('button[data-mode]');
    if (!btn) return;
    const bus = btn.closest('[data-bus]').dataset.bus;
    closeSendMenu();
    onPick(bus, btn.dataset.mode);
  };
  current = el;
  setTimeout(() => document.addEventListener('pointerdown', onOutside, true), 0);
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
