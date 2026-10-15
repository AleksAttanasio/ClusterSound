# ClusterSound

[![Documentation](https://img.shields.io/badge/docs-documentation-00b09f?style=for-the-badge&logo=materialformkdocs&logoColor=white)](https://aleksattanasio.github.io/ClusterSound/)

A desktop app for macOS and Windows that analyses a folder of audio samples (recursively), assigns every file
to a sound class — kick, snare, hat, 808, pad… — and shows the whole library as a 3D cloud where similar
sounds sit close together. From there you build kits, grooves and progressions and take them into Ableton Live.
Everything runs locally and your original files are never modified.

![ClusterSound — 3D library map](docs/assets/screenshots/library-3d.png)

**📖 Full documentation: <https://aleksattanasio.github.io/ClusterSound/>** ([Italiano](https://aleksattanasio.github.io/ClusterSound/it/))

## Features

- **Library** — 34 classes, subgroups of similar sounds, t-SNE 3D map, *Find similar*, corrections that
  retrain the classifier.
- **Store** — free samples and packs from Freesound, Openverse, Internet Archive and ccMixter, with the licence
  shown alongside.
- **Recorder** — records the audio output, slices on transients, separates stems (Demucs), restores compressed
  audio (Apollo).
- **Sequencer** — 191 grooves in 47 genres to try samples, layers, arrangement, MIDI/WAV/Ableton export.
- **Drum Rack** — kits of similar samples for an 8×8 Launchpad and a Roland SPD-SX.
- **Compose** — progressions from a chord pack with harmonic suggestions, variations, generated melodies and
  bass lines.
- **Max for Live** — imports patterns, racks and progressions into Ableton Live without dragging files.

## Screenshots

| | |
|---|---|
| ![Library list](docs/assets/screenshots/library-list.png) | ![Sample detail](docs/assets/screenshots/library-detail.png) |
| **Library** — list view | **Library** — sample detail |
| ![Find similar](docs/assets/screenshots/library-similar.png) | ![Store home](docs/assets/screenshots/store-home.png) |
| **Library** — *Find similar* | **Store** — home |
| ![Store results](docs/assets/screenshots/store-results.png) | ![Recorder](docs/assets/screenshots/recorder.png) |
| **Store** — search results | **Recorder** |
| ![Sequencer](docs/assets/screenshots/sequencer.png) | ![Drum Rack](docs/assets/screenshots/drum-rack.png) |
| **Sequencer** | **Drum Rack** — Launchpad 8×8 |
| ![Drum Rack SPD-SX](docs/assets/screenshots/drum-rack-spdsx.png) | ![Compose harmony](docs/assets/screenshots/compose-harmony.png) |
| **Drum Rack** — Roland SPD-SX | **Compose** — harmony |
| ![Compose melody](docs/assets/screenshots/compose-melody.png) | ![Settings](docs/assets/screenshots/settings.png) |
| **Compose** — melody | **Settings** |

## Quick install

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -e ".[dev]"
.venv/bin/python -m clustersound            # GUI
.venv/bin/python -m clustersound --headless ~/Samples --out report.csv   # batch, no GUI
```

On Windows (10 or 11, with the Edge WebView2 runtime):

```powershell
py -3.12 -m venv .venv; .venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python -m clustersound
```

Optional extras: `stems` (Demucs), `enhance` (Apollo), `midi` (MIDI keyboard), `capture` (ScreenCaptureKit).
Details in [Installation](https://aleksattanasio.github.io/ClusterSound/guide/installation/).

## Documentation

| | |
|---|---|
| [Quick start](https://aleksattanasio.github.io/ClusterSound/guide/) | installation, first launch, Ableton Live, build, troubleshooting |
| [Manual](https://aleksattanasio.github.io/ClusterSound/manual/) | every section of the app, with screenshots |
| [Technical](https://aleksattanasio.github.io/ClusterSound/technical/) | architecture, backend, frontend, data, Live integration, development |
| [AI models](https://aleksattanasio.github.io/ClusterSound/ai/) | YAMNet in numpy, self-trained classifier, Demucs, Apollo |
| [Algorithms](https://aleksattanasio.github.io/ClusterSound/algorithms/) | classification, clustering, sample selection, grooves, harmony, melody |

The site sources live in [`docs/`](docs/) (MkDocs Material, English and Italian). To preview it locally
(http://127.0.0.1:8000):

```bash
uvx --with-requirements docs/requirements.txt mkdocs serve
```

## Development

```bash
.venv/bin/python -m pytest                    # tests
.venv/bin/python tools/devserver.py           # UI in a regular browser
tools/build_app.sh                            # dist/ClusterSound.app
```

## Model licences

- **YAMNet** (Google, Apache 2.0): weights converted into `clustersound/models/yamnet.npz`.
- **Demucs** (Meta, MIT): downloaded the first time you use *Extract stems*.
- **Apollo** (Kai Li, Yi Luo, 2024; CC BY-SA 4.0): downloaded the first time you use *Enhance*.
