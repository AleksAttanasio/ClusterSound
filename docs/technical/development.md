# Development and tests

## Environment

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -e ".[dev]"
.venv/bin/python -m clustersound --debug     # with the WebView inspector
```

The `stems`, `enhance`, `midi`, `capture` extras are only needed for their features (see
[Installation](../guide/installation.md)).

## Dev server

```bash
.venv/bin/python tools/devserver.py --port 8765
```

Serves the UI in a **normal browser** (`http://localhost:8765`) with the same `Api` reachable over HTTP: a shim is
injected into `index.html` that defines `window.pywebview.api` as `fetch('/api/<method>')` calls, so the same
`app.js` runs unchanged. Native dialogs become `prompt()` and saves go to the export folder. The Live bridge is off by
default (`--live-port` to turn it on), so it does not clash with the open app. The configurations in
`.claude/launch.json` start several instances on different ports.

## Tests

`pytest` (folder `tests/`, about 340 tests) runs without network and without GUI:

| File | Covers |
|---|---|
| `test_pipeline.py` | analysis, classification, cache, clustering and projection end-to-end on synthetic signals |
| `test_snapshot.py` | fingerprint and validity of the snapshots |
| `test_online.py` | providers, filters, labelling, licences with responses recorded in `tests/fixtures/online` |
| `test_patterns.py`, `test_arrange.py` | pattern model, swing, alternation, MIDI, export, sequences |
| `test_racks.py`, `test_spdsx.py` | selection, layouts, limits and SPD-SX export |
| `test_chords.py`, `test_melody.py` | theory, suggestions, variations, playing, generators, harmonisation |
| `test_sampler.py`, `test_recorder.py`, `test_wasapi.py` | slicing, export, writer, recording backends (with fake modules) |
| `test_stems.py`, `test_enhance.py` | jobs, blocks and crossfades, worker protocol (without PyTorch) |
| `test_live.py` | HTTP bridge, payloads, OSC protocol of the Remote Script |
| `test_platform.py` | simulated macOS / Windows differences |
| `test_i18n.py` | every translated text of UI and backend has an Italian entry with the same placeholders |

`tests/synth.py` generates synthetic kicks, snares, hats and noises at 44.1 kHz. `CLUSTERSOUND_NETWORK_TESTS=1 pytest`
also queries the real Store services.

## Tools (`tools/`)

| Script | Use |
|---|---|
| `devserver.py` | UI in the browser (above) |
| `evaluate.py` | classification accuracy with hidden names (`--oneshots`, `--all-hidden`, `--no-base`) |
| `train_base_head.py` | retrains the base head on one or more libraries |
| `build_yamnet_npz.py` | converts YAMNet's Keras weights into the numpy model |
| `extract_adg_template.py` | regenerates the (structure-only) templates of the Live 10 racks |
| `build_amxd.py`, `install_live.py/.sh` | builds the `.amxd` device and installs it with the Remote Script |
| `build_app.sh/.ps1`, `build_tap.sh`, `build_icon.sh`, `make_ico.py` | build of the app, the helper and the icons |

## Packaging

`ClusterSound.spec` (PyInstaller, *onedir*, window without console, entry `launcher.py`) includes the models, the rack
templates, the whole UI (with `ui/locales`) and, if compiled, `bin/cs-tap`. The hidden imports change per platform
(Cocoa and ScreenCaptureKit on macOS; WinForms, EdgeChromium and `soundcard` on Windows); Demucs and PyTorch go in
only if installed. The macOS bundle (`com.clustersound.app`, macOS 12+) declares `NSAudioCaptureUsageDescription` for
the recording permission.

A frozen app cannot run `python -m …`: for the Apollo worker it launches itself again with `--enhance-worker`.

### `cs-tap` helper

`clustersound/native/cs_tap.swift` is a small CLI that records a device's output with **Core Audio process taps**
(macOS 14.2+): `cs-tap list` lists the outputs, `cs-tap record --device <uid|all> --exclude-pid <pid>` writes a
JSON header line (sample rate, channels) and then interleaved float32 PCM on stdout. `build_tap.sh` compiles it;
from source, with `swiftc`, the app compiles it by itself on first use in the cache folder.

## Conventions

- One branch per task from `develop` (`feature/…`, `docs/…`), one commit per completed step, merge into `develop`
  and release on `main` with a `vX.Y.Z` tag.
- Interface texts are written in English and go through `t()` (UI) or `tr()` (backend); the Italian translation is
  added to `ui/locales/it.js` in the same commit. Comments and names in the code are in English.
- No public method on `Api` that should not be callable from JS.
