import { Scene3D } from './scene3d.js';
import { Panel } from './panel.js';
import { Player } from './player.js';
import { Online } from './online.js';
import { PatternEditor } from './pattern.js';
import { DrumRackEditor } from './drumrack.js';
import { ComposeEditor } from './compose.js';
import { SamplerEditor } from './sampler.js';
import { showSendMenu } from './sendmenu.js';
import { isTypingTarget } from './kit.js';
import { Nav, TAB_LABELS } from './nav.js';
import { Settings, generalSection, setRow } from './settings.js';

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const state = {
  api: null,
  classes: [], groups: [], types: [],
  data: null, version: -1,
  classOn: new Set(), typeOn: new Set(), minConf: 0, search: '',
  mask: null, selected: -1, scanning: false,
  view: '3d', sort: { key: 'cls', dir: 1 }, rows: [], tab: 'library', folder: '',
  focus: null, // {center, items: [{id, sim}], trail: [id…]} while the similar-samples view is open
  lastTrail: [], // trail of the last similar-samples view (kept after closing it, for the Drum Rack)
  simK: (() => { try { return Math.min(60, Math.max(5, +localStorage.getItem('cs.simK') || 12)); } catch { return 12; } })(),
};

const player = new Player({ onState: onPlayState });
window.__cs = { state, player, get pattern() { return pattern; }, get rack() { return rack; }, get compose() { return compose; }, get sampler() { return sampler; }, get scene() { return scene; }, get online() { return online; } }; // handy from the web inspector (--debug)

// ------------------------------------------------------------------ boot
function whenApiReady() {
  return new Promise((resolve) => {
    if (window.pywebview?.api?.init) return resolve(window.pywebview.api);
    window.addEventListener('pywebviewready', () => resolve(window.pywebview.api), { once: true });
  });
}

let scene, panel, online, pattern, rack, compose, sampler, nav, settings;

const TABS = ['library', 'online', 'pattern', 'rack', 'compose', 'sampler', 'settings'];

async function main() {
  state.api = await whenApiReady();
  const init = await state.api.init();
  state.classes = init.classes;
  state.groups = init.groups;
  state.types = init.types;
  state.classOn = new Set(state.classes.map((_, i) => i));
  state.typeOn = new Set(state.types.map((_, i) => i));

  scene = new Scene3D($('#view3d'), {
    onHover, onClick: (i) => { if (i >= 0) select(i, true); },
    onDoubleClick: (i) => showSimilar(i),
    onContext: (i, x, y) => sendLibraryItem(i, x, y),
  });
  scene.onFrame = drawLabels;
  panel = new Panel($('#panel'), $('#panel-content'), {
    classes: state.classes, groups: state.groups,
    onRelabel: relabel, onReveal: (id) => state.api.reveal(id), onSimilar: showSimilar,
    onPlayToggle: togglePlay, onSeek: seek, onClose: closePanel,
    onSend: (id, x, y) => sendLibraryItem(id, x, y),
    onStore: (cls) => openStore([cls]),
  });

  online = new Online({ api: state.api, player, classes: state.classes, groups: state.groups, types: state.types });
  pattern = new PatternEditor({ api: state.api, player, classes: state.classes, onLoadFromRack: () => rack.openLoadDialog() });
  rack = new DrumRackEditor({ api: state.api, player, classes: state.classes, getTrail,
    getSequencer: () => pattern, onOpenSequencer: () => setTab('pattern') });
  compose = new ComposeEditor({ api: state.api, player, getPattern: () => pattern, onOpenSequencer: () => setTab('pattern') });
  sampler = new SamplerEditor({ api: state.api, player, classes: state.classes, onSendToRack: async (refs) => {
    if (await rack.addSamples(refs)) setTab('rack');
  } });
  online.onSend = (ref, x, y) => sendRef(ref, x, y);
  online.onLibrary = (path) => { setTab('library'); setFolder(path); };
  nav = new Nav($('#nav'), { onSelect: (tab) => setTab(tab) });
  window.__cs.nav = nav;
  settings = new Settings($('#settings'));
  settings.add('general', 'Generale', 'settings', generalSection(state.api, (s) => online.onSettings(s)));
  settings.add('library', 'Libreria', 'library-big', renderLibrarySettings);
  settings.add('online', 'Store', 'store', (body) => online.renderSettings(body));
  settings.add('pattern', 'Sequencer', 'audio-lines', (body) => pattern.renderSettings(body));
  window.addEventListener('cs:open-settings', (e) => setTab('settings', e.detail));
  buildSidebar();
  bindUi();
  if (init.last_folder) {
    setFolder(init.last_folder, false);
    state.api.restore(init.last_folder);
  }
  let last = 'library';
  try { last = localStorage.getItem('cs.tab') || 'library'; } catch { /* private mode */ }
  setTab(TABS.includes(last) && last !== 'settings' ? last : 'library');
  poll();
}

// ------------------------------------------------------------------ sidebar
function buildSidebar() {
  $('#type-filters').innerHTML = state.types.map((t, i) => `<wa-button size="xs" pill class="chip on" data-type="${i}">${esc(t)}</wa-button>`).join('');
  $('#type-filters').onclick = (e) => {
    const b = e.target.closest('.chip'); if (!b) return;
    const i = +b.dataset.type;
    state.typeOn.has(i) ? state.typeOn.delete(i) : state.typeOn.add(i);
    b.classList.toggle('on', state.typeOn.has(i));
    applyFilters();
  };

  const html = [];
  for (const g of state.groups) {
    const members = state.classes.map((c, i) => [c, i]).filter(([c]) => c.group === g);
    html.push(`<div class="group" data-group="${esc(g)}"><div class="group-title" data-group="${esc(g)}"><span>${esc(g)}</span><span class="cls-count" data-gcount="${esc(g)}"></span></div>`);
    for (const [c, i] of members) {
      html.push(`<div class="cls-row" data-cls="${i}" title="Clic: mostra/nascondi · Alt+clic: solo questa classe">
        <span class="dot" style="background:${c.color}"></span><span class="cls-name">${esc(c.label)}</span><span class="cls-count" data-count="${i}">0</span></div>`);
    }
    html.push('</div>');
  }
  $('#class-list').innerHTML = html.join('');
  $('#class-list').onclick = (e) => {
    const row = e.target.closest('.cls-row');
    const gt = e.target.closest('.group-title');
    if (row) {
      const i = +row.dataset.cls;
      if (e.altKey) { state.classOn = new Set([i]); }
      else state.classOn.has(i) ? state.classOn.delete(i) : state.classOn.add(i);
    } else if (gt) {
      const ids = state.classes.map((c, i) => [c, i]).filter(([c]) => c.group === gt.dataset.group).map(([, i]) => i);
      const allOn = ids.every((i) => state.classOn.has(i));
      ids.forEach((i) => (allOn ? state.classOn.delete(i) : state.classOn.add(i)));
    } else return;
    syncClassRows();
    applyFilters();
  };
  $('#cls-all').onclick = (e) => { e.preventDefault(); state.classOn = new Set(state.classes.map((_, i) => i)); syncClassRows(); applyFilters(); };
  $('#cls-none').onclick = (e) => { e.preventDefault(); state.classOn = new Set(); syncClassRows(); applyFilters(); };
}

function syncClassRows() {
  document.querySelectorAll('.cls-row').forEach((r) => r.classList.toggle('off', !state.classOn.has(+r.dataset.cls)));
}

function updateCounts() {
  const counts = new Array(state.classes.length).fill(0);
  if (state.data) state.data.cls.forEach((c) => counts[c]++);
  const gcount = {};
  document.querySelectorAll('[data-count]').forEach((el) => {
    const i = +el.dataset.count;
    el.textContent = counts[i];
    el.closest('.cls-row').classList.toggle('empty', counts[i] === 0 && !!state.data);
    const g = state.classes[i].group;
    gcount[g] = (gcount[g] || 0) + counts[i];
  });
  document.querySelectorAll('[data-gcount]').forEach((el) => { el.textContent = gcount[el.dataset.gcount] || 0; });
  const d = state.data;
  if (!d) return;
  const vis = state.mask ? state.mask.reduce((a, b) => a + b, 0) : 0;
  $('#stats').innerHTML = `${d.cls.length} sample · ${vis} visibili${d.errors ? ` · ${d.errors} illeggibili` : ''}<br>
    Head addestrata su ${d.stats.head_samples || 0} esempi (${d.stats.head_classes || 0} classi)`;
}

// ------------------------------------------------------------------ filters
function applyFilters() {
  const d = state.data;
  if (!d) return;
  const n = d.cls.length;
  const mask = new Uint8Array(n);
  const q = state.search.trim().toLowerCase();
  for (let i = 0; i < n; i++) {
    mask[i] = state.classOn.has(d.cls[i]) && state.typeOn.has(d.type[i]) && d.conf[i] >= state.minConf
      && (!q || d.rel[i].toLowerCase().includes(q)) ? 1 : 0;
  }
  state.mask = mask;
  scene.setVisible(mask);
  buildRows();
  updateCounts();
}

// ------------------------------------------------------------------ data
async function poll() {
  try {
    const p = await state.api.progress();
    showProgress(p);
    if (p.version > 0 && p.version !== state.version) await loadResults();
  } catch (e) { console.error(e); }
  setTimeout(poll, state.scanning ? 400 : 1200);
}

function showProgress(p) {
  const busy = ['scanning', 'analysing', 'classifying', 'layout'].includes(p.phase);
  state.scanning = busy;
  $('#progress-wrap').hidden = !busy && p.phase !== 'error' && p.phase !== 'stale';
  const wrap = $('#progress-wrap');
  const pct = p.total ? (100 * p.done) / p.total : 0;
  $('#progress-bar').indeterminate = busy && !p.total;
  $('#progress-bar').value = pct;
  const label = { scanning: 'Ricerca file', analysing: 'Analisi', classifying: 'Classificazione', layout: 'Layout 3D', error: 'Errore', stale: 'Snapshot' }[p.phase] || '';
  $('#progress-text').textContent = p.phase === 'analysing'
    ? `${label} ${p.done}/${p.total} · ${p.message}` : `${label} ${p.message && p.phase !== 'analysing' ? '· ' + p.message : ''}`;
  if (p.phase === 'error') $('#progress-text').classList.add('error');
  const badge = $('#layout-badge');
  badge.hidden = !state.data;
  badge.textContent = p.layout === 'pca' ? 'Layout rapido (PCA) · t-SNE in corso…' : p.layout === 'tsne' ? 'Layout t-SNE · punti vicini = suoni simili' : '';
}

async function loadResults() {
  const d = await state.api.results();
  state.version = d.version;
  if (!d.cls.length) return;
  if (d.cls.length !== state.data?.cls.length) { exitFocus(false); state.lastTrail = []; }
  state.data = d;
  $('#empty').hidden = true;
  nav.setBadge('library', d.cls.length);
  scene.setData(d, state.classes.map((c) => c.color));
  applyFilters();
  computeCentroids();
  if (state.selected >= d.cls.length) closePanel();
  else if (state.selected >= 0) scene.setSelected(state.selected);
}

// ------------------------------------------------------------------ labels
let centroids = [];
// Label anchor per class: the densest spot of its points (a plain mean lands in the middle
// of the cloud for classes that are spread out, and labels pile up there).
function computeCentroids() {
  const d = state.data;
  const members = state.classes.map(() => []);
  for (let i = 0; i < d.cls.length; i++) members[d.cls[i]].push(i);
  const R2 = 10 * 10;
  centroids = [];
  members.forEach((ids, ci) => {
    if (ids.length < 3) return;
    const step = Math.max(1, Math.floor(ids.length / 300));
    const s = ids.filter((_, k) => k % step === 0);
    let best = s[0], bestN = -1;
    for (const a of s) {
      let n = 0;
      for (const b of s) {
        const dx = d.xyz[a * 3] - d.xyz[b * 3], dy = d.xyz[a * 3 + 1] - d.xyz[b * 3 + 1], dz = d.xyz[a * 3 + 2] - d.xyz[b * 3 + 2];
        if (dx * dx + dy * dy + dz * dz < R2) n++;
      }
      if (n > bestN) { bestN = n; best = a; }
    }
    let x = 0, y = 0, z = 0, m = 0;
    for (const b of s) {
      const dx = d.xyz[best * 3] - d.xyz[b * 3], dy = d.xyz[best * 3 + 1] - d.xyz[b * 3 + 1], dz = d.xyz[best * 3 + 2] - d.xyz[b * 3 + 2];
      if (dx * dx + dy * dy + dz * dz < R2) { x += d.xyz[b * 3]; y += d.xyz[b * 3 + 1]; z += d.xyz[b * 3 + 2]; m++; }
    }
    centroids.push({ ci, x: x / m, y: y / m, z: z / m, n: ids.length });
  });
  const box = $('#labels');
  box.innerHTML = centroids.map((c) => {
    const cls = state.classes[c.ci];
    return `<div class="lbl" data-ci="${c.ci}" style="color:${cls.color}">${esc(cls.label)}</div>`;
  }).join('');
}

let labelsOn = true;
function drawLabels() {
  if (state.view !== '3d') return;
  if (state.focus) { drawFocusLabels(); return; }
  if (!labelsOn || !centroids.length) return;
  const els = $('#labels').children;
  for (let k = 0; k < centroids.length; k++) {
    const c = centroids[k];
    const el = els[k];
    const p = state.classOn.has(c.ci) ? scene.project(c.x, c.y, c.z) : null;
    if (!p) { el.style.display = 'none'; continue; }
    el.style.display = '';
    el.style.left = `${p[0]}px`;
    el.style.top = `${p[1]}px`;
  }
}

// ------------------------------------------------------------------ hover / select
function onHover(i, x, y) {
  const tip = $('#tooltip');
  if (i < 0 || !state.data) { tip.hidden = true; document.body.style.cursor = ''; return; }
  const d = state.data;
  const c = state.classes[d.cls[i]];
  const sim = state.focus?.items.find((it) => it.id === i);
  tip.innerHTML = `<div class="t-name">${esc(d.name[i])}</div>
    <div class="t-sub"><span class="dot" style="background:${c.color}"></span>${esc(c.label)} · ${d.user[i] ? 'manuale' : Math.round(d.conf[i] * 100) + '%'} · gruppo ${d.sub[i]}</div>
    ${sim ? `<div class="t-sub">Somiglianza ${Math.round(sim.sim * 100)}%</div>` : ''}
    <div class="t-hint">Tasto destro: invia al Sequencer o al Drum Rack</div>`;
  tip.hidden = false;
  const W = $('#view3d').clientWidth;
  tip.style.left = `${Math.min(x + 14, W - tip.offsetWidth - 8)}px`;
  tip.style.top = `${y + 14}px`;
  document.body.style.cursor = 'pointer';
}

async function select(i, play) {
  const d = state.data;
  if (!d || i < 0) return;
  if (state.focus && !inFocus(i)) exitFocus();
  state.selected = i;
  scene.setSelected(i);
  highlightRow();
  if (state.focus) syncFocusLabels();
  const item = { name: d.name[i], rel: d.rel[i], conf: d.conf[i], user: d.user[i] };
  panel.loading(item, state.classes[d.cls[i]]);
  if (play) playItem(i);
  if (state.focus) syncInset();
  const det = await state.api.details(i);
  if (state.selected !== i) return; // user moved on
  panel.render(det, player.playing && player.id === i);
}

function closePanel() {
  player.stop();
  panel.close();
  state.selected = -1;
  scene.setSelected(-1);
  exitFocus();
  highlightRow();
}

// ------------------------------------------------------------------ similar-samples focus
const inFocus = (i) => !!state.focus && (i === state.focus.center || state.focus.trail.includes(i)
  || state.focus.items.some((it) => it.id === i));

let focusTok = 0;
// Open the close-up of `id` and its neighbours, or re-centre it on `id`. Every centre visited is
// appended to the trail (revisits too); `backTo` = index of a breadcrumb to go back to, cutting the trail there.
async function showSimilar(id, backTo = -1) {
  if (!state.data || id < 0) return;
  if (state.view !== '3d') setView('3d');
  const prev = state.focus?.trail || [];
  const trail = backTo >= 0 ? prev.slice(0, backTo + 1) : prev[prev.length - 1] === id ? prev : [...prev, id];
  await loadFocus(id, trail);
}

async function loadFocus(center, trail) {
  const tok = ++focusTok;
  const items = await state.api.similar(center, state.simK);
  if (tok !== focusTok) return; // a newer request (slider, re-centre) won
  const entering = !state.focus;
  state.focus = { center, items, trail };
  state.lastTrail = trail;
  renderFocusBar();
  syncInset();
  scene.setFocus(center, items, trail);
  if (entering) $('#labels').hidden = true;
  syncFocusLabels();
}

function exitFocus(restoreView = true) {
  if (!state.focus) return;
  focusTok++;
  state.focus = null;
  scene.clearFocus(restoreView);
  $('#focus-bar').hidden = true;
  $('#labels').hidden = !labelsOn;
  syncInset();
  syncFocusLabels();
}

// keep the close-up out from under the detail panel
function syncInset() {
  const px = state.focus && panel.isOpen() ? $('#panel').offsetWidth : 0;
  const bar = $('#focus-bar');
  scene.setInset(px, state.focus && !bar.hidden ? bar.offsetTop + bar.offsetHeight : 0);
  $('#view3d').style.setProperty('--inset', `${px}px`);
}

function renderFocusBar() {
  const f = state.focus, d = state.data;
  $('#focus-bar').hidden = false;
  $('#fb-name').textContent = d.name[f.center];
  $('#fb-name').title = d.rel[f.center];
  $('#fb-k').value = state.simK;
  $('#fb-k-val').textContent = state.simK;
  $('#fb-trail').hidden = f.trail.length < 2;
  const crumbs = $('#fb-crumbs');
  crumbs.hidden = f.trail.length < 2;
  crumbs.innerHTML = f.trail.map((id, k) => `${k ? '<span class="sep">›</span>' : ''}<button data-k="${k}"
    class="${k === f.trail.length - 1 ? 'cur' : ''}" title="Torna qui · ${esc(d.rel[id])}">${k + 1} · ${esc(d.name[id])}</button>`).join('');
}

// one HTML label per neighbour (name + similarity) and a numbered badge per trail stop
let focusLabels = new Map(); // key -> element
function syncFocusLabels() {
  const box = $('#focus-labels');
  const f = state.focus, d = state.data;
  const want = new Map();
  if (f) {
    want.set(`c${f.center}`, { id: f.center, cls: 'center', html: `<span class="nm">${esc(d.name[f.center])}</span>` });
    f.items.forEach((it, k) => want.set(`n${it.id}`, { id: it.id, cls: '', rank: k + 1,
      html: `<span class="nm">${esc(d.name[it.id])} </span><b>${Math.round(it.sim * 100)}%</b>` }));
    const steps = new Map(); // a sample visited more than once shows all its step numbers
    f.trail.forEach((id, k) => steps.set(id, [...(steps.get(id) || []), k + 1]));
    for (const [id, ks] of steps) want.set(`t${id}`, { id, cls: 'stop', html: ks.join('·') });
  }
  for (const [key, el] of focusLabels) {
    if (want.has(key)) continue;
    el.classList.remove('in');
    setTimeout(() => el.remove(), 300);
    focusLabels.delete(key);
  }
  for (const [key, w] of want) {
    let el = focusLabels.get(key);
    if (!el) {
      el = document.createElement('div');
      box.appendChild(el);
      focusLabels.set(key, el);
      requestAnimationFrame(() => el.classList.add('in'));
    }
    const sel = w.cls !== 'stop' && w.id === state.selected;
    el.dataset.id = w.id;
    // drawing order for collisions: centre and selection first, then the most similar
    el.dataset.prio = w.cls === 'stop' ? -1 : w.cls === 'center' ? 0 : sel ? 0.5 : w.rank;
    el.className = `flbl ${w.cls} ${sel ? 'sel' : ''} ${el.classList.contains('in') ? 'in' : ''}`;
    el.innerHTML = w.html;
    el._w = null; // re-measure
  }
  focusOrder = [...focusLabels.values()].sort((a, b) => a.dataset.prio - b.dataset.prio);
}

// Names whose box would overlap a label already placed collapse to just the percentage.
let focusOrder = [];
function drawFocusLabels() {
  const placed = [];
  const hit = (r) => placed.some((o) => r[0] < o[2] && r[2] > o[0] && r[1] < o[3] && r[3] > o[1]);
  for (const el of focusOrder) {
    const p = scene.pos(+el.dataset.id);
    const s = p && scene.project(...p);
    if (!s) { el.style.display = 'none'; continue; }
    el.style.display = '';
    el.style.left = `${s[0]}px`;
    el.style.top = `${s[1]}px`;
    if (el.classList.contains('stop')) { placed.push([s[0] - 18, s[1] - 9, s[0] - 4, s[1] + 9]); continue; }
    if (!el._w) { // full and compact widths, measured once
      el.classList.remove('compact'); const full = el.offsetWidth;
      el.classList.add('compact'); el._w = [full, el.offsetWidth];
    }
    const box = (w) => [s[0] + 10, s[1] - 9, s[0] + 10 + w, s[1] + 9];
    const compact = hit(box(el._w[0])) && el.dataset.prio > 0;
    el.classList.toggle('compact', compact);
    placed.push(box(el._w[compact ? 1 : 0]));
  }
}

async function relabel(id, cls) {
  const res = await state.api.relabel(id, cls);
  if (!res.ok) return;
  if (cls !== null) {
    // recolour right away; the retrained results arrive through polling
    state.data.cls[id] = state.classes.findIndex((c) => c.id === cls);
    state.data.conf[id] = 1;
    state.data.user[id] = 1;
    scene.refreshStyle();
    updateCounts();
    buildRows();
  }
  state.scanning = true;
  setTimeout(async () => { if (state.selected === id) panel.render(await state.api.details(id), player.playing && player.id === id); }, 150);
}

// ------------------------------------------------------------------ audio
async function playItem(i, offset = 0) {
  player.stop();
  const buf = await player.load(i, (id) => state.api.audio(id));
  if (!buf || state.selected !== i) return; // the user already clicked something else
  player.play(i, buf, offset);
}

function togglePlay() {
  if (state.selected < 0) return;
  if (player.playing) player.stop();
  else playItem(state.selected);
}

function seek(t) {
  if (state.selected >= 0) playItem(state.selected, Math.max(0, t));
}

function onPlayState(playing, id) {
  if (id !== state.selected) { panel.setPlaying(false); return; } // an online preview
  panel.setPlaying(playing);
  if (playing) requestAnimationFrame(playheadLoop);
  else panel.drawPlayhead(null);
}

function playheadLoop() {
  if (!player.playing || player.id !== state.selected) return;
  panel.drawPlayhead(player.currentTime);
  requestAnimationFrame(playheadLoop);
}

// ------------------------------------------------------------------ list view
const COLS = [
  ['', null], ['Nome', 'name'], ['Cartella', 'rel'], ['Classe', 'cls'], ['Conf.', 'conf'],
  ['Grp', 'sub'], ['Tipo', 'type'], ['Durata', 'dur'],
];
const ROW_H = 28;

function buildRows() {
  const d = state.data;
  if (!d) return;
  const rows = [];
  for (let i = 0; i < d.cls.length; i++) if (state.mask[i]) rows.push(i);
  const { key, dir } = state.sort;
  const val = (i) => d[key][i]; // classes sort in taxonomy order
  rows.sort((a, b) => {
    const va = val(a), vb = val(b);
    return (va < vb ? -1 : va > vb ? 1 : a - b) * dir;
  });
  state.rows = rows;
  $('#list-spacer').style.height = `${rows.length * ROW_H}px`;
  renderList(true);
}

function renderHead() {
  $('#list-head').innerHTML = COLS.map(([label, key]) => {
    const s = state.sort.key === key;
    return `<div data-key="${key ?? ''}" class="${s ? 'sorted' : ''} ${['conf', 'sub', 'dur'].includes(key) ? 'num' : ''}">${label}${s ? (state.sort.dir > 0 ? ' ↑' : ' ↓') : ''}</div>`;
  }).join('');
}

let lastRange = '';
function renderList(force = false) {
  if (state.view !== 'list' || !state.data) return;
  const body = $('#list-body');
  const first = Math.max(0, Math.floor(body.scrollTop / ROW_H) - 10);
  const last = Math.min(state.rows.length, first + Math.ceil(body.clientHeight / ROW_H) + 20);
  const key = `${first}:${last}:${state.rows.length}`;
  if (!force && key === lastRange) return;
  lastRange = key;
  const d = state.data;
  const html = [];
  for (let k = first; k < last; k++) {
    const i = state.rows[k];
    const c = state.classes[d.cls[i]];
    const folder = d.rel[i].includes('/') ? d.rel[i].slice(0, d.rel[i].lastIndexOf('/')) : '';
    html.push(`<div class="list-row ${i === state.selected ? 'sel' : ''}" data-i="${i}" style="top:${k * ROW_H}px">
      <div><span class="dot" style="background:${c.color};display:inline-block"></span></div>
      <div title="${esc(d.name[i])}">${esc(d.name[i])}</div>
      <div class="muted" title="${esc(folder)}">${esc(folder)}</div>
      <div>${esc(c.label)}</div>
      <div class="num">${d.user[i] ? '✓' : Math.round(d.conf[i] * 100) + '%'}</div>
      <div class="num">${d.sub[i]}</div>
      <div>${esc(state.types[d.type[i]])}</div>
      <div class="num">${d.dur[i].toFixed(2)}s</div></div>`);
  }
  $('#list-body').querySelectorAll('.list-row').forEach((r) => r.remove());
  $('#list-body').insertAdjacentHTML('beforeend', html.join(''));
}

function highlightRow() {
  document.querySelectorAll('.list-row').forEach((r) => r.classList.toggle('sel', +r.dataset.i === state.selected));
}

// ------------------------------------------------------------------ ui
function setFolder(path, scan = true) {
  state.folder = path;
  showCrumb();
  if (scan) startScan(path);
}

async function pickFolder() {
  const p = await state.api.pick_folder();
  if (p) { setTab('library'); setFolder(p); }
}

// Library section of the Settings page: the analysed folder and the report.
async function renderLibrarySettings(body) {
  const f = state.folder;
  body.innerHTML =
    setRow('Cartella dei sample', 'Analizzata ricorsivamente (wav, aif, flac, ogg, mp3, caf). I risultati restano in cache; i file originali non vengono mai modificati.',
      `${f ? `<span class="set-path" title="${esc(f)}">${esc(f)}</span>` : '<span class="hint">Nessuna cartella</span>'}
       <wa-button id="set-lib-pick" size="s" variant="brand"><wa-icon slot="start" name="folder-open"></wa-icon>Scegli…</wa-button>`)
    + setRow('Riscansiona', 'Rianalizza la cartella: i file invariati vengono letti dalla cache.',
      `<wa-button id="set-lib-rescan" size="s" appearance="filled-outlined"${!f || state.scanning ? ' disabled' : ''}><wa-icon slot="start" name="refresh-cw"></wa-icon>Riscansiona</wa-button>`)
    + setRow('Report', 'CSV o JSON con classe, confidenza, alternative, sottocluster e tipo di ogni sample. <span id="set-lib-report"></span>',
      `<wa-button id="set-lib-export" size="s" appearance="filled-outlined"${state.data ? '' : ' disabled'}><wa-icon slot="start" name="file-down"></wa-icon>Esporta report</wa-button>`);
  body.querySelector('#set-lib-pick').onclick = pickFolder;
  body.querySelector('#set-lib-rescan').onclick = () => { setTab('library'); startScan(state.folder); };
  body.querySelector('#set-lib-export').onclick = async () => {
    const p = await state.api.export_report();
    if (p) body.querySelector('#set-lib-report').textContent = `Salvato in ${p}.`;
  };
}

// Breadcrumb of the page header: the analysed folder in the Library, a link to its settings.
function showCrumb() {
  const sub = $('#crumb-sub');
  sub.hidden = state.tab !== 'library' || !state.folder;
  sub.textContent = state.folder;
  sub.title = `${state.folder}\nClic: cambia cartella nelle Impostazioni`;
}

async function startScan(path) {
  closePanel();
  state.scanning = true;
  const ok = await state.api.start_scan(path);
  if (!ok) { $('#progress-text').textContent = 'Cartella non valida'; }
}

function setView(v) {
  state.view = v;
  $('#view-toggle').value = v;
  $('#view3d').hidden = v !== '3d';
  $('#viewlist').hidden = v !== 'list';
  if (v === 'list') { renderHead(); renderList(true); } else scene.resize();
}

const getTrail = () => (state.data ? state.lastTrail.map((id) => ({ id, name: state.data.name[id] })) : []);

// ------------------------------------------------------------------ send to pattern buses / drum rack
async function sendRef(ref, x, y) {
  await pattern.ensure();
  showSendMenu({ x, y, ref, buses: pattern.buses, counts: pattern.layerCounts(),
    onPick: (bus, mode) => pattern.addSample(bus, ref, mode),
    rack: { target: await rack.sendTarget(), onAdd: async (similar, open) => {
      await rack.addSample(ref, { similar });
      if (open) setTab('rack');
    } } });
}

async function sendLibraryItem(id, x, y) {
  const ref = await state.api.library_ref(id);
  sendRef(ref, x, y);
}

// One section at a time; the left navigation and the page header follow it.
function setTab(tab, section = '') {
  state.tab = tab;
  if (tab !== 'settings') { try { localStorage.setItem('cs.tab', tab); } catch { /* private mode */ } }
  player.stop();
  if (tab !== 'pattern' && pattern) pattern.hide();
  if (tab !== 'rack' && rack) rack.hide();
  if (tab !== 'compose' && compose) compose.hide();
  if (tab !== 'sampler' && sampler) sampler.hide();
  nav.setActive(tab);
  $('#crumb-title').textContent = TAB_LABELS[tab] || '';
  showCrumb();
  $('#head-more').hidden = tab === 'settings';
  $('#head-more').dataset.settingsLink = tab;
  for (const t of TABS) $('#' + t).hidden = t !== tab;
  document.querySelectorAll('.head-tools').forEach((el) => { el.hidden = el.dataset.for !== tab; });
  if (tab === 'online') online.show(); else if (tab === 'pattern') pattern.show();
  else if (tab === 'rack') rack.show(); else if (tab === 'compose') compose.show();
  else if (tab === 'sampler') sampler.show(); else if (tab === 'settings') settings.show(section);
  else scene.resize();
}

// From the library: open the store on one instrument (the class of a sample)
function openStore(instruments = null) {
  setTab('online');
  if (instruments) online.browse({ instruments });
}

function bindUi() {
  $('#btn-empty-store').onclick = () => openStore();
  $('#list-body').addEventListener('contextmenu', (e) => {
    const r = e.target.closest('.list-row');
    if (!r) return;
    e.preventDefault();
    sendLibraryItem(+r.dataset.i, e.clientX, e.clientY);
  });
  $('#btn-empty-folder').onclick = pickFolder;
  $('#crumb-sub').dataset.settingsLink = 'library';
  $('#view-toggle').addEventListener('change', (e) => { if (e.target.id === 'view-toggle') setView(e.target.value); });
  $('#search').oninput = (e) => { state.search = e.target.value || ''; applyFilters(); };
  $('#search').addEventListener('wa-clear', () => { state.search = ''; applyFilters(); });
  $('#conf').oninput = (e) => {
    state.minConf = +e.target.value / 100;
    $('#conf-value').textContent = `${e.target.value}%`;
    applyFilters();
  };
  $('#panel-close').onclick = closePanel;
  $('#btn-rotate').onclick = (e) => { const on = e.currentTarget.classList.toggle('active'); scene.setAutoRotate(on); };
  $('#btn-reset').onclick = () => { exitFocus(false); scene.resetView(); };
  $('#fb-exit').onclick = () => exitFocus();
  $('#fb-trail').onclick = () => scene.frameTrail();
  $('#fb-rack').onclick = () => rack.sendTrail(getTrail());
  let kTimer = 0;
  $('#fb-k').oninput = (e) => {
    state.simK = +e.target.value;
    $('#fb-k-val').textContent = state.simK;
    try { localStorage.setItem('cs.simK', state.simK); } catch { /* private mode */ }
    clearTimeout(kTimer);
    kTimer = setTimeout(() => { if (state.focus) loadFocus(state.focus.center, state.focus.trail); }, 120);
  };
  $('#fb-crumbs').onclick = (e) => {
    const b = e.target.closest('button[data-k]');
    if (!b || !state.focus) return;
    const k = +b.dataset.k, id = state.focus.trail[k];
    showSimilar(id, k).then(() => select(id, true));
  };
  $('#btn-labels').onclick = (e) => {
    labelsOn = e.currentTarget.classList.toggle('active');
    $('#labels').hidden = !labelsOn || !!state.focus;
  };
  $('#list-body').addEventListener('scroll', () => renderList());
  $('#list-body').onclick = (e) => {
    const r = e.target.closest('.list-row');
    if (r) select(+r.dataset.i, true);
  };
  $('#list-head').onclick = (e) => {
    const k = e.target.closest('[data-key]')?.dataset.key;
    if (!k) return;
    state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : 1 };
    renderHead();
    buildRows();
  };
  window.addEventListener('keydown', (e) => {
    if (document.querySelector('wa-dialog[open]') || isTypingTarget(e)) return; // dialogs handle their own Esc
    if (state.tab === 'pattern' && e.key === ' ') { e.preventDefault(); pattern.togglePlay(); return; }
    if (state.tab === 'compose') { if (!document.querySelector('.popover') && compose.onKey(e)) e.preventDefault(); return; }
    if (state.tab === 'sampler') { if (sampler.onKey(e)) e.preventDefault(); return; }
    if (state.tab !== 'library') return;
    if (e.key === 'Escape') { if (state.focus) exitFocus(); else closePanel(); }
    if (e.key === ' ' && state.selected >= 0) { e.preventDefault(); togglePlay(); }
    if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && state.view === 'list' && state.rows.length) {
      e.preventDefault();
      const k = state.rows.indexOf(state.selected);
      const nk = Math.max(0, Math.min(state.rows.length - 1, k + (e.key === 'ArrowDown' ? 1 : -1)));
      select(state.rows[nk], true);
      const body = $('#list-body');
      const top = nk * ROW_H;
      if (top < body.scrollTop || top > body.scrollTop + body.clientHeight - ROW_H) body.scrollTop = top - body.clientHeight / 2;
    }
  });
}

main();
