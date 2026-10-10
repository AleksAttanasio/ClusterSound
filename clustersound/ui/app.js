import { Scene3D } from './scene3d.js';
import { Panel } from './panel.js';
import { Player } from './player.js';

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const state = {
  api: null,
  classes: [], groups: [], types: [],
  data: null, version: -1,
  classOn: new Set(), typeOn: new Set(), minConf: 0, search: '',
  mask: null, selected: -1, scanning: false,
  view: '3d', sort: { key: 'cls', dir: 1 }, rows: [],
};

const player = new Player({ onState: onPlayState });
window.__cs = { state, player }; // handy from the web inspector (--debug)

// ------------------------------------------------------------------ boot
function whenApiReady() {
  return new Promise((resolve) => {
    if (window.pywebview?.api?.init) return resolve(window.pywebview.api);
    window.addEventListener('pywebviewready', () => resolve(window.pywebview.api), { once: true });
  });
}

let scene, panel;

async function main() {
  state.api = await whenApiReady();
  const init = await state.api.init();
  state.classes = init.classes;
  state.groups = init.groups;
  state.types = init.types;
  state.classOn = new Set(state.classes.map((_, i) => i));
  state.typeOn = new Set(state.types.map((_, i) => i));

  scene = new Scene3D($('#view3d'), { onHover, onClick: (i) => { if (i >= 0) select(i, true); } });
  scene.onFrame = drawLabels;
  panel = new Panel($('#panel'), $('#panel-content'), {
    classes: state.classes, groups: state.groups,
    onRelabel: relabel, onReveal: (id) => state.api.reveal(id), onSimilar: showSimilar,
    onPlayToggle: togglePlay, onSeek: seek, onClose: closePanel,
  });

  buildSidebar();
  bindUi();
  if (init.last_folder) setFolder(init.last_folder, false);
  poll();
}

// ------------------------------------------------------------------ sidebar
function buildSidebar() {
  $('#type-filters').innerHTML = state.types.map((t, i) => `<button class="chip on" data-type="${i}">${esc(t)}</button>`).join('');
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
  $('#progress-wrap').hidden = !busy && p.phase !== 'error';
  const wrap = $('#progress-wrap');
  const pct = p.total ? (100 * p.done) / p.total : 0;
  wrap.classList.toggle('indeterminate', busy && !p.total);
  $('#progress-bar').style.width = `${pct}%`;
  const label = { scanning: 'Ricerca file', analysing: 'Analisi', classifying: 'Classificazione', layout: 'Layout 3D', error: 'Errore' }[p.phase] || '';
  $('#progress-text').textContent = p.phase === 'analysing'
    ? `${label} ${p.done}/${p.total} · ${p.message}` : `${label} ${p.message && p.phase !== 'analysing' ? '· ' + p.message : ''}`;
  if (p.phase === 'error') $('#progress-text').classList.add('error');
  $('#btn-rescan').disabled = busy || !$('#folder-path').title;
  const badge = $('#layout-badge');
  badge.hidden = !state.data;
  badge.textContent = p.layout === 'pca' ? 'Layout rapido (PCA) · t-SNE in corso…' : p.layout === 'tsne' ? 'Layout t-SNE · punti vicini = suoni simili' : '';
}

async function loadResults() {
  const d = await state.api.results();
  state.version = d.version;
  if (!d.cls.length) return;
  state.data = d;
  $('#empty').hidden = true;
  $('#btn-export').disabled = false;
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
  if (!labelsOn || !centroids.length || state.view !== '3d') return;
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
  tip.innerHTML = `<div class="t-name">${esc(d.name[i])}</div>
    <div class="t-sub"><span class="dot" style="background:${c.color}"></span>${esc(c.label)} · ${d.user[i] ? 'manuale' : Math.round(d.conf[i] * 100) + '%'} · gruppo ${d.sub[i]}</div>`;
  tip.hidden = false;
  const W = $('#view3d').clientWidth;
  tip.style.left = `${Math.min(x + 14, W - tip.offsetWidth - 8)}px`;
  tip.style.top = `${y + 14}px`;
  document.body.style.cursor = 'pointer';
}

async function select(i, play) {
  const d = state.data;
  if (!d || i < 0) return;
  state.selected = i;
  scene.setSelected(i);
  scene.setSimilar([]);
  highlightRow();
  const item = { name: d.name[i], rel: d.rel[i], conf: d.conf[i], user: d.user[i] };
  panel.loading(item, state.classes[d.cls[i]]);
  if (play) playItem(i);
  const det = await state.api.details(i);
  if (state.selected !== i) return; // user moved on
  panel.render(det, player.playing && player.id === i);
}

function closePanel() {
  player.stop();
  panel.close();
  state.selected = -1;
  scene.setSelected(-1);
  scene.setSimilar([]);
  highlightRow();
}

async function showSimilar(id) {
  const ids = await state.api.similar(id, 12);
  scene.setSimilar(ids);
  if (state.view === '3d') scene.focus(id);
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

function onPlayState(playing) {
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
  $('#folder-path').textContent = path;
  $('#folder-path').title = path;
  $('#btn-rescan').disabled = false;
  if (scan) startScan(path);
}

async function startScan(path) {
  closePanel();
  state.scanning = true;
  const ok = await state.api.start_scan(path);
  if (!ok) { $('#progress-text').textContent = 'Cartella non valida'; }
}

function setView(v) {
  state.view = v;
  $('#view-3d').classList.toggle('active', v === '3d');
  $('#view-list').classList.toggle('active', v === 'list');
  $('#view3d').hidden = v !== '3d';
  $('#viewlist').hidden = v !== 'list';
  if (v === 'list') { renderHead(); renderList(true); } else scene.resize();
}

function bindUi() {
  $('#btn-folder').onclick = async () => {
    const p = await state.api.pick_folder();
    if (p) setFolder(p);
  };
  $('#btn-rescan').onclick = () => startScan($('#folder-path').title);
  $('#btn-export').onclick = async () => {
    const p = await state.api.export_report();
    if (p) { $('#progress-wrap').hidden = false; $('#progress-text').textContent = `Report salvato: ${p}`; }
  };
  $('#view-3d').onclick = () => setView('3d');
  $('#view-list').onclick = () => setView('list');
  $('#search').oninput = (e) => { state.search = e.target.value; applyFilters(); };
  $('#conf').oninput = (e) => {
    state.minConf = +e.target.value / 100;
    $('#conf-value').textContent = `${e.target.value}%`;
    applyFilters();
  };
  $('#panel-close').onclick = closePanel;
  $('#btn-rotate').onclick = (e) => { const on = e.currentTarget.classList.toggle('active'); scene.setAutoRotate(on); };
  $('#btn-reset').onclick = () => scene.resetView();
  $('#btn-labels').onclick = (e) => {
    labelsOn = e.currentTarget.classList.toggle('active');
    $('#labels').hidden = !labelsOn;
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
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    if (e.key === 'Escape') closePanel();
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
