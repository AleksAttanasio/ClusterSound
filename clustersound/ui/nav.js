// Left navigation: one entry per section, grouped, with Settings at the bottom.
// It can be reduced to icons only; the choice is remembered on this computer.
import { icon } from './kit.js';

const ITEMS = [
  { group: 'Sample' },
  { tab: 'library', label: 'Libreria', icon: 'library-big' },
  { tab: 'online', label: 'Store', icon: 'store' },
  { tab: 'sampler', label: 'Recorder', icon: 'mic' },
  { group: 'Crea' },
  { tab: 'pattern', label: 'Sequencer', icon: 'audio-lines' },
  { tab: 'rack', label: 'Drum Rack', icon: 'drum' },
  { tab: 'compose', label: 'Compose', icon: 'piano' },
  { spacer: true },
  { tab: 'settings', label: 'Impostazioni', icon: 'settings' },
];

export const TAB_LABELS = Object.fromEntries(ITEMS.filter((it) => it.tab).map((it) => [it.tab, it.label]));

const KEY = 'cs.navCollapsed';

export class Nav {
  constructor(root, { onSelect }) {
    this.root = root;
    this.onSelect = onSelect;
    const list = root.querySelector('#nav-items');
    list.innerHTML = ITEMS.map((it) => {
      if (it.group) return `<div class="nav-group">${it.group}</div>`;
      if (it.spacer) return '<div class="nav-spacer"></div>';
      return `<button type="button" class="nav-item" data-tab="${it.tab}" title="${it.label}">${icon(it.icon)}<span class="nav-label">${it.label}</span><span class="nav-badge" hidden></span></button>`;
    }).join('');
    list.onclick = (e) => {
      const b = e.target.closest('.nav-item');
      if (b) this.onSelect(b.dataset.tab);
    };
    root.querySelector('#nav-toggle').onclick = () => this.setCollapsed(!document.body.classList.contains('nav-collapsed'));
    let collapsed = false;
    try { collapsed = localStorage.getItem(KEY) === '1'; } catch { /* private mode */ }
    this.setCollapsed(collapsed, false);
  }

  setCollapsed(on, save = true) {
    document.body.classList.toggle('nav-collapsed', on);
    const t = this.root.querySelector('#nav-toggle');
    const label = on ? 'Espandi il pannello' : 'Riduci il pannello';
    t.title = label;
    t.innerHTML = icon(on ? 'panel-left-open' : 'panel-left-close', label);
    if (save) { try { localStorage.setItem(KEY, on ? '1' : '0'); } catch { /* private mode */ } }
    window.dispatchEvent(new Event('resize')); // the 3D view and the rack grid size themselves on resize
  }

  item(tab) { return this.root.querySelector(`.nav-item[data-tab="${tab}"]`); }

  setActive(tab) {
    this.root.querySelectorAll('.nav-item').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
  }

  // Small counter on the right of an entry (e.g. samples in the library); empty hides it.
  setBadge(tab, text) {
    const b = this.item(tab)?.querySelector('.nav-badge');
    if (!b) return;
    b.textContent = text ?? '';
    b.hidden = !text && text !== 0;
  }

  // Status dot on an entry's icon: 'recording', 'busy' or 'attention'.
  mark(tab, cls, on) { this.item(tab)?.classList.toggle(cls, !!on); }
}
