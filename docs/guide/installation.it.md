# Installazione

**Requisiti**: Python 3.11+ (consigliato 3.12) · macOS 12+ oppure Windows 10/11 con il runtime Edge WebView2
(già presente su Windows 11).

=== "macOS"

    ```bash
    git clone https://github.com/AleksAttanasio/ClusterSound.git && cd ClusterSound
    uv venv -p 3.12 .venv && uv pip install -p .venv -e ".[dev]"
    .venv/bin/python -m clustersound
    ```

=== "Windows"

    ```powershell
    git clone https://github.com/AleksAttanasio/ClusterSound.git; cd ClusterSound
    py -3.12 -m venv .venv; .venv\Scripts\pip install -e ".[dev]"
    .venv\Scripts\python -m clustersound
    ```

Senza `uv` su macOS: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.

## App pronta (macOS)

Scarica lo zip per il tuo Mac (`arm64` per Apple Silicon, `x86_64` per Intel) dalla pagina
[Releases](https://github.com/AleksAttanasio/ClusterSound/releases): contiene `ClusterSound.app` con tutti gli
extra. L'app non è notarizzata: la prima volta aprila con tasto destro › **Apri**.

## Extra opzionali

Le funzioni pesanti sono extra, da installare solo se servono:

| Extra | Abilita | Comando |
|---|---|---|
| `stems` | *Estrai stem* nel Recorder (Demucs + PyTorch) | `pip install -e ".[stems]"` |
| `enhance` | *Migliora* nel Recorder (Apollo + PyTorch) | `pip install -e ".[enhance]"` |
| `midi` | Registrazione da tastiera MIDI in Compose | `pip install -e ".[midi]"` |
| `capture` | Recorder *Tutte le uscite* via ScreenCaptureKit (macOS, senza helper `cs-tap`) | `pip install -e ".[capture]"` |

I pesi dei modelli di `stems` ed `enhance` si scaricano dall'app al primo uso (una sola volta).

## Senza interfaccia

```bash
.venv/bin/python -m clustersound --headless ~/Samples --out report.csv
```

Analizza la cartella, stampa il conteggio per classe e scrive un report CSV o JSON.

Opzioni: `--debug` apre l'inspector della WebView.

## Lingua

L'interfaccia parte in inglese. Per passare all'italiano apri **Settings › General › Language** e scegli
*Italiano*: l'app si ricarica nella lingua scelta e la ricorda.
