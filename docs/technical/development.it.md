# Sviluppo e test

## Ambiente

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -e ".[dev]"
.venv/bin/python -m clustersound --debug     # con l'inspector della WebView
```

Gli extra `stems`, `enhance`, `midi`, `capture` servono solo per le rispettive funzioni (vedi
[Installazione](../guide/installation.md)).

## Dev server

```bash
.venv/bin/python tools/devserver.py --port 8765
```

Serve la UI in un **browser normale** (`http://localhost:8765`) con la stessa `Api` raggiungibile via HTTP: a
`index.html` viene iniettato uno shim che definisce `window.pywebview.api` come chiamate `fetch('/api/<metodo>')`,
così lo stesso `app.js` gira senza modifiche. I dialoghi nativi diventano `prompt()` e i salvataggi vanno nella
cartella di export. Il bridge per Live è spento di default (`--live-port` per accenderlo), così non entra in
conflitto con l'app aperta. Le configurazioni in `.claude/launch.json` avviano più istanze su porte diverse.

## Test

`pytest` (cartella `tests/`, circa 236 test) gira senza rete e senza GUI:

| File | Copre |
|---|---|
| `test_pipeline.py` | analisi, classificazione, cache, clustering e proiezione end-to-end su segnali sintetici |
| `test_snapshot.py` | impronta e validità degli snapshot |
| `test_online.py` | provider, filtri, etichettatura, licenze con risposte registrate in `tests/fixtures/online` |
| `test_patterns.py`, `test_arrange.py` | modello dei pattern, swing, alternanza, MIDI, export, sequenze |
| `test_racks.py`, `test_spdsx.py` | selezione, layout, limiti e export SPD-SX |
| `test_chords.py`, `test_melody.py` | teoria, suggerimenti, variazioni, esecuzione, generatori, armonizzazione |
| `test_sampler.py`, `test_recorder.py`, `test_wasapi.py` | slicing, export, writer, backend di registrazione (con moduli finti) |
| `test_stems.py`, `test_enhance.py` | job, blocchi e crossfade, protocollo del worker (senza PyTorch) |
| `test_live.py` | bridge HTTP, payload, protocollo OSC della Remote Script |
| `test_platform.py` | differenze macOS / Windows simulate |

`tests/synth.py` genera kick, snare, hat e rumori sintetici a 44,1 kHz. `CLUSTERSOUND_NETWORK_TESTS=1 pytest`
interroga anche i servizi reali dello Store.

## Strumenti (`tools/`)

| Script | Uso |
|---|---|
| `devserver.py` | UI nel browser (sopra) |
| `evaluate.py` | accuratezza della classificazione a nomi nascosti (`--oneshots`, `--all-hidden`, `--no-base`) |
| `train_base_head.py` | riaddestra la head base su una o più librerie |
| `build_yamnet_npz.py` | converte i pesi Keras di YAMNet nel modello numpy |
| `extract_adg_template.py` | rigenera i template (solo struttura) dei rack Live 10 |
| `build_amxd.py`, `install_live.py/.sh` | costruisce il device `.amxd` e lo installa con la Remote Script |
| `build_app.sh/.ps1`, `build_tap.sh`, `build_icon.sh`, `make_ico.py` | build dell'app, dell'helper e delle icone |

## Packaging

`ClusterSound.spec` (PyInstaller, *onedir*, finestra senza console, entry `launcher.py`) include i modelli, i
template dei rack, tutta la UI e, se compilato, `bin/cs-tap`. Gli import nascosti cambiano per piattaforma (Cocoa e
ScreenCaptureKit su macOS; WinForms, EdgeChromium e `soundcard` su Windows); Demucs e PyTorch entrano solo se
installati. Il bundle macOS (`com.clustersound.app`, macOS 12+) dichiara `NSAudioCaptureUsageDescription` per il
permesso di registrazione.

Un'app congelata non può lanciare `python -m …`: per il worker di Apollo rilancia sé stessa con
`--enhance-worker`.

### Helper `cs-tap`

`clustersound/native/cs_tap.swift` è una piccola CLI che registra l'uscita di un dispositivo con i **Core Audio
process tap** (macOS 14.2+): `cs-tap list` elenca le uscite, `cs-tap record --device <uid|all> --exclude-pid <pid>`
scrive una riga JSON di intestazione (frequenza, canali) e poi PCM float32 interleaved su stdout. `build_tap.sh` la
compila; da sorgente, con `swiftc`, l'app la compila da sola al primo uso nella cartella di cache.

## Convenzioni

- Branch per attività da `develop` (`feature/…`, `docs/…`), un commit per passo completato, merge in `develop` e
  release su `main` con tag `vX.Y.Z`.
- Testi dell'interfaccia in italiano; commenti e nomi nel codice in inglese.
- Nessun metodo pubblico su `Api` che non debba essere chiamabile da JS.
