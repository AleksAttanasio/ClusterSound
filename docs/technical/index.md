# Technical documentation

How ClusterSound is built inside: processes, Python modules, web interface, data on disk and integration with
Ableton Live. For the machine learning models see [AI models](../ai/index.md); for the heuristics and the
algorithms of every feature see [Algorithms](../algorithms/index.md).

<div class="grid cards" markdown>

- **[Architecture](architecture.md)** — the pieces and how they talk to each other.
- **[Backend](backend.md)** — the Python packages, the `Api` exposed to the UI, threads and jobs.
- **[Frontend](frontend.md)** — ES modules, Web Awesome, Three.js, Web Audio, translations.
- **[Data and persistence](data-and-persistence.md)** — SQLite cache, snapshots, settings, exports.
- **[Live integration](live-integration.md)** — HTTP bridge, Max for Live device, Remote Script.
- **[Development and tests](development.md)** — dev server, tests, tools, packaging.

</div>

## In short

| | |
|---|---|
| Language | Python ≥ 3.11 (backend), ES2020 JavaScript without a bundler (UI) |
| Window | [pywebview](https://pywebview.flowrl.com/) — WKWebView on macOS, Edge WebView2 on Windows |
| Base dependencies | `numpy`, `soundfile`, `soxr`, `pywebview` (+ `soundcard` on Windows) |
| ML | YAMNet and MLP head in **pure numpy**; PyTorch only for the optional extras (Demucs, Apollo) |
| UI | Web Awesome 3.14, Three.js, Lucide, Inter / JetBrains Mono fonts — all vendored, offline |
| Interface languages | English (default) and Italian, one catalogue shared by UI and backend |
| Persistence | SQLite (WAL) + `.npz` + JSON in the app's data folder |
| Integration | local-only HTTP server for Max for Live, OSC/UDP to a Remote Script |
| Distribution | PyInstaller (`.app` / `.exe`) |
