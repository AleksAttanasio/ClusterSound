# ClusterSound

[![Documentazione](https://img.shields.io/badge/docs-documentazione-00b09f?style=for-the-badge&logo=materialformkdocs&logoColor=white)](https://aleksattanasio.github.io/ClusterSound/)

App desktop per macOS e Windows che analizza una cartella di sample audio (ricorsivamente), assegna ogni
file a una classe di suono — kick, snare, hat, 808, pad… — e mostra l'intera libreria come nuvola 3D in
cui suoni simili stanno vicini. Da lì costruisci kit, groove e progressioni e li porti in Ableton Live.
Tutto gira in locale e i file originali non vengono mai modificati.

![ClusterSound](docs/assets/screenshots/libreria-3d.png)

**📖 Documentazione completa: <https://aleksattanasio.github.io/ClusterSound/>**

## Funzionalità

- **Libreria** — 34 classi, sottogruppi di suoni simili, mappa 3D t-SNE, *Trova simili*, correzioni che
  riaddestrano il classificatore.
- **Store** — sample e pack gratuiti da Freesound, Openverse, Internet Archive e ccMixter, con licenza accanto.
- **Recorder** — registra l'uscita audio, taglia sui transienti, separa gli stem (Demucs), restaura l'audio
  compresso (Apollo).
- **Sequencer** — 191 groove di 47 generi per provare i sample, layer, arrangiamento, export MIDI/WAV/Ableton.
- **Drum Rack** — kit di sample simili per Launchpad 8×8 e Roland SPD-SX.
- **Compose** — progressioni da un chord pack con suggerimenti armonici, variazioni, melodie e bassi generati.
- **Max for Live** — importa pattern, rack e progressioni in Ableton Live senza trascinare file.

## Installazione rapida

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -e ".[dev]"
.venv/bin/python -m clustersound            # GUI
.venv/bin/python -m clustersound --headless ~/Samples --out report.csv   # batch, senza GUI
```

Su Windows (10 o 11, con il runtime Edge WebView2):

```powershell
py -3.12 -m venv .venv; .venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python -m clustersound
```

Extra opzionali: `stems` (Demucs), `enhance` (Apollo), `midi` (tastiera MIDI), `capture` (ScreenCaptureKit).
Dettagli in [Installazione](https://aleksattanasio.github.io/ClusterSound/guida/installazione/).

## Documentazione

| | |
|---|---|
| [Guida rapida](https://aleksattanasio.github.io/ClusterSound/guida/) | installazione, primo avvio, Ableton Live, build, problemi |
| [Manuale](https://aleksattanasio.github.io/ClusterSound/manuale/) | ogni sezione dell'app, con screenshot |
| [Tecnica](https://aleksattanasio.github.io/ClusterSound/tecnica/) | architettura, backend, frontend, dati, integrazione con Live, sviluppo |
| [Modelli AI](https://aleksattanasio.github.io/ClusterSound/ai/) | YAMNet in numpy, classificatore auto-addestrato, Demucs, Apollo |
| [Algoritmi](https://aleksattanasio.github.io/ClusterSound/algoritmi/) | classificazione, clustering, scelta dei sample, groove, armonia, melodia |

I sorgenti del sito sono in [`docs/`](docs/) (MkDocs Material). Per vederlo in locale (http://127.0.0.1:8000):

```bash
uvx --with mkdocs-material==9.5.39 mkdocs serve
```

## Sviluppo

```bash
.venv/bin/python -m pytest                    # test
.venv/bin/python tools/devserver.py           # UI in un browser normale
tools/build_app.sh                            # dist/ClusterSound.app
```

## Licenze dei modelli

- **YAMNet** (Google, Apache 2.0): pesi convertiti in `clustersound/models/yamnet.npz`.
- **Demucs** (Meta, MIT): scaricato al primo uso di *Estrai stem*.
- **Apollo** (Kai Li, Yi Luo, 2024; CC BY-SA 4.0): scaricato al primo uso di *Migliora*.
