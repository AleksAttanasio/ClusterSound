# Frontend

The interface (`clustersound/ui/`) is a single page in **modern JavaScript with no bundler and no build**:
`index.html` loads native ES modules and vendored libraries. It works offline, identical in the macOS WebView, in
WebView2 on Windows and in a normal browser with the [dev server](development.md#dev-server).

## Modules

| Module | Lines | Role |
|---|---|---|
| `app.js` | ~730 | boot, global state, Library (sidebar, filters, list, similar view), routing between sections |
| `nav.js` | ~70 | navigation panel (sections, badges, compact mode) |
| `scene3d.js` | ~650 | 3D cloud with Three.js: point shader, picking, similar view, animations |
| `panel.js` | ~260 | detail drawer (dynamics, spectrogram, measures, class) |
| `player.js` | ~75 | Web Audio playback with an LRU cache of the buffers |
| `online.js` | ~950 | Store: home, results, pack and provider pages, downloads |
| `pattern.js` | ~900 | Sequencer: genres, buses, layers, random kit, export |
| `sequencer.js` | ~300 | Web Audio step engine, mirror of `patterns/render.py` |
| `arranger.js` | ~500 | timeline of the sequence of patterns |
| `drumrack.js` | ~1000 | 8×8 and SPD-SX Drum Rack |
| `compose.js` | ~2500 | Compose: browser, timeline, suggestions, variations, piano roll, synth |
| `sampler.js` | ~1230 | Recorder: devices, editor, regions, stems, Enhance |
| `settings.js` | ~140 | Settings page split by section |
| `i18n.js`, `locales/it.js` | | interface language: `t()`, `applyI18n()`, Italian catalogue |
| `sendmenu.js`, `live.js` | | *Send* menu, toasts, sending to Live |
| `kit.js`, `icons.js` | | HTML helpers for the `wa-*` components, inline SVG icons |

## Libraries (in `ui/vendor/`)

- **[Web Awesome](https://webawesome.com/) 3.14** — web components (`wa-button`, `wa-select`, `wa-slider`,
  `wa-checkbox`…) with the **Lucide** icons registered as an offline library (~50 SVGs).
- **[Three.js](https://threejs.org/)** + `OrbitControls` — the 3D view.
- **Inter** (UI) and **JetBrains Mono** (numbers, times, paths) fonts.

## State and communication

- Every module gets `api` (`window.pywebview.api`) in its constructor and calls `await api.method(...)`. There is
  no framework and no reactive store: `app.js` keeps a `state` object (classes, library data, filters, selection,
  similar view) and every editor has its own internal state.
- The library results arrive **column-wise** (`name[]`, `cls[]`, `conf[]`, `xyz[]`…) to handle tens of thousands
  of points without one object per item.
- Long jobs are followed by **polling** the status methods (see [Architecture](architecture.md)).
- Interface preferences (active section, compact nav, how many similar samples to show…) in `localStorage` with
  `cs.*` keys; the real settings are in Python.
- `window.__cs` exposes state and editors for debugging from the inspector (`--debug`).

## Translations

English is the source language: every text in the code is English and goes through `t()`, which uses the English
text itself as the key — `t('Settings')`, `t('Saved to {path}.', { path })`. `locales/it.js` maps English text to
Italian; it is strict JSON after `export default`, so Python can read it too: the backend's `i18n.tr()` uses the same
catalogue, and every sentence is translated once.

- **Choosing the language**: `api.init()` returns the language saved in `settings.json`; `app.js` calls `setLang()`
  and `applyI18n()` before building the sections. *Settings › General › Language* saves the choice and reloads the
  page.
- **Static markup**: `index.html` is written in English with `data-i18n`, `data-i18n-title`, `data-i18n-placeholder`
  and `data-i18n-label` attributes, which `applyI18n()` fills in.
- **Module constants** (sort orders, modes, labels) are built before the language is known, so they keep English
  text and are translated with `t()` where they are shown.
- **Missing translations**: `t()` falls back to English and logs `[i18n] missing it: …` once in the console.
  `tests/test_i18n.py` checks that every literal `t('…')`, every `data-i18n*` attribute and every backend
  `tr("…")` / `N_("…")` has an Italian entry, and that the `{placeholders}` match.

## 3D view

A single `THREE.Points` with a `ShaderMaterial`: colour, size and alpha are per-point attributes, so filters and
selection only update buffers, without recreating geometry. **Picking** does not use the raycaster: it projects the
visible points on the screen and picks the one closest to the cursor within a radius, preferring the ones closer to
the camera. The class labels are HTML divs placed on the centroids on every frame. The *similar* view animates the
points towards a radial layout around the centre and draws the trail.

## Audio

- **Player**: a single `AudioContext`, unlocked at the user's first gesture (WKWebView would block `<audio>.play()`
  in asynchronous callbacks); decoded buffers stay in a small LRU cache.
- **Sequencer**: a classic "lookahead" scheduler — a timer every **25 ms** schedules the notes of the next
  **120 ms** on the Web Audio clock. Gains (`(v/127)^1.5`), swing, rolls, choke and the layer alternation hash are
  identical to those of `render.py`, so what you hear is what you export.
- **Compose**: a small synth with Web Audio oscillators plays the events computed by `perform.py` (the same events
  as the exported MIDI).

## Theme

`theme.css` is the only place where Web Awesome's `--wa-*` tokens are redefined: neutral greys with a single
**teal** accent (`#00b09f`, `#2fd1bd` for text), the same as the drop of the logo. The app is dark only.
`style.css` defines short aliases (`--bg`, `--line`, `--accent`, `--mono`…) and the layout of the sections.
