# Installation

**Requirements**: Python 3.11+ (3.12 recommended) · macOS 12+ or Windows 10/11 with the Edge WebView2 runtime
(already present on Windows 11).

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

Without `uv` on macOS: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.

## Optional extras

The heavy features are extras, to install only if you need them:

| Extra | Enables | Command |
|---|---|---|
| `stems` | *Extract stems* in the Recorder (Demucs + PyTorch) | `pip install -e ".[stems]"` |
| `enhance` | *Enhance* in the Recorder (Apollo + PyTorch) | `pip install -e ".[enhance]"` |
| `midi` | Recording from a MIDI keyboard in Compose | `pip install -e ".[midi]"` |
| `capture` | Recorder *All outputs* through ScreenCaptureKit (macOS, without the `cs-tap` helper) | `pip install -e ".[capture]"` |

The model weights of `stems` and `enhance` are downloaded by the app on first use (only once).

## Without the interface

```bash
.venv/bin/python -m clustersound --headless ~/Samples --out report.csv
```

Analyses the folder, prints the count per class and writes a CSV or JSON report.

Options: `--debug` opens the WebView inspector.

## Language

The interface starts in English. To switch to Italian open **Settings › General › Language**: the app reloads in
the chosen language and remembers it.
