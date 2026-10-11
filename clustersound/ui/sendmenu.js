// Popup "Invia": route a sample (library, online or file) to a sequencer bus (as a new layer or replacing
// the current one) or to the Drum Rack. Used from the 3D view, the list, the detail panel and the Online tab.

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LS_SIMILAR = 'clustersound.sendSimilar';

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

// buses: ui buses (id, label, color, melodic); counts: bus id -> number of layers (for the hint);
// rack: {target: 'gruppo 3 · Kick', onAdd(similar, open)} for the Drum Rack section
export function showSendMenu({ x, y, ref, buses, counts = {}, onPick, rack }) {
  closeSendMenu();
  const sug = suggestBus(buses, ref.cls);
  const ordered = sug ? [buses.find((b) => b.id === sug), ...buses.filter((b) => b.id !== sug)] : buses;
  let similar = false;
  try { similar = localStorage.getItem(LS_SIMILAR) === '1'; } catch { /* private mode */ }
  const canSimilar = ref.kind === 'library';
  const el = document.createElement('div');
  el.className = 'send-menu';
  el.innerHTML = `<div class="send-title" title="${esc(ref.name)}">Invia · <b>${esc(ref.name)}</b></div>
    ${rack ? `<div class="send-sec">Drum Rack <span>${esc(rack.target)}</span></div>
    <div class="send-rack">
      <button class="btn small" data-rack="add" title="Mette il sample sul pad selezionato (o sul primo libero del gruppo)">+ aggiungi</button>
      <button class="btn small" data-rack="open" title="Aggiunge e passa alla scheda Drum Rack">+ aggiungi e apri ▦</button>
      ${canSimilar ? `<label class="send-sim" title="Riempie tutto il gruppo con questo sample e i suoi simili"><input type="checkbox" data-sim ${similar ? 'checked' : ''}> con i simili</label>` : ''}
    </div>` : ''}
    <div class="send-sec">Sequencer</div>
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
  el.onchange = (e) => {
    if (!e.target.matches('[data-sim]')) return;
    try { localStorage.setItem(LS_SIMILAR, e.target.checked ? '1' : '0'); } catch { /* private mode */ }
  };
  el.onclick = (e) => {
    const rb = e.target.closest('button[data-rack]');
    if (rb) {
      const sim = canSimilar && !!el.querySelector('[data-sim]')?.checked;
      closeSendMenu();
      rack.onAdd(sim, rb.dataset.rack === 'open');
      return;
    }
    const btn = e.target.closest('button[data-mode]');
    if (!btn) return;
    closeSendMenu();
    onPick(btn.closest('[data-bus]').dataset.bus, btn.dataset.mode);
  };
  current = el;
  setTimeout(() => document.addEventListener('pointerdown', onOutside, true), 0);
}

// Small floating panel under `anchor` (closes on outside click / Esc); returns it, with .close().
export function showPopover(anchor, html) {
  document.querySelector('.popover')?.close?.();
  const el = document.createElement('div');
  el.className = 'popover';
  el.innerHTML = html;
  document.body.appendChild(el);
  const a = anchor.getBoundingClientRect(), r = el.getBoundingClientRect();
  el.style.left = `${Math.max(8, Math.min(a.right - r.width, window.innerWidth - r.width - 8))}px`;
  el.style.top = `${Math.min(a.bottom + 6, window.innerHeight - r.height - 8)}px`;
  const outside = (e) => { if (!el.contains(e.target) && !anchor.contains(e.target)) el.close(); };
  const esc_ = (e) => { if (e.key === 'Escape') el.close(); };
  el.close = () => {
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
