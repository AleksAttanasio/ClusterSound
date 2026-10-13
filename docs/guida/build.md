# Build dell'app

PyInstaller costruisce solo per il sistema su cui gira.

=== "macOS"

    ```bash
    tools/build_app.sh
    ```

    Risultato: `dist/ClusterSound.app` (compila anche l'helper `cs-tap` del Recorder e l'icona, se manca).
    Distribuisci solo il bundle `.app`.

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy Bypass -File tools\build_app.ps1
    ```

    Risultato: `dist\ClusterSound\ClusterSound.exe`. Distribuisci l'intera cartella `dist\ClusterSound`.

Demucs e PyTorch vengono inclusi solo se installati nell'ambiente di build. Dettagli su spec e helper nativo in
[Sviluppo e test](../tecnica/sviluppo.md#packaging).
