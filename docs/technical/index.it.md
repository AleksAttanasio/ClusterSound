# Documentazione tecnica

Come è fatta ClusterSound dentro: processi, moduli Python, interfaccia web, dati su disco e integrazione con
Ableton Live. Per i modelli di machine learning vedi [Modelli AI](../ai/index.md); per le euristiche e gli
algoritmi di ogni funzione vedi [Algoritmi](../algorithms/index.md).

<div class="grid cards" markdown>

- **[Architettura](architecture.md)** — i pezzi e come comunicano.
- **[Backend](backend.md)** — i package Python, l'`Api` esposta alla UI, thread e job.
- **[Frontend](frontend.md)** — moduli ES, Web Awesome, Three.js, Web Audio.
- **[Dati e persistenza](data-and-persistence.md)** — cache SQLite, snapshot, impostazioni, export.
- **[Integrazione con Live](live-integration.md)** — bridge HTTP, device Max for Live, Remote Script.
- **[Sviluppo e test](development.md)** — dev server, test, strumenti, packaging.

</div>

## In breve

| | |
|---|---|
| Linguaggio | Python ≥ 3.11 (backend), JavaScript ES2020 senza bundler (UI) |
| Finestra | [pywebview](https://pywebview.flowrl.com/) — WKWebView su macOS, Edge WebView2 su Windows |
| Dipendenze di base | `numpy`, `soundfile`, `soxr`, `pywebview` (+ `soundcard` su Windows) |
| ML | YAMNet e head MLP in **numpy puro**; PyTorch solo per gli extra opzionali (Demucs, Apollo) |
| UI | Web Awesome 3.14, Three.js, Lucide, font Inter / JetBrains Mono — tutto vendorizzato, offline |
| Persistenza | SQLite (WAL) + `.npz` + JSON nella cartella dei dati dell'app |
| Integrazione | server HTTP solo locale per Max for Live, OSC/UDP verso una Remote Script |
| Distribuzione | PyInstaller (`.app` / `.exe`) |
