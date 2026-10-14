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
[Sviluppo e test](../technical/development.md#packaging).

## Release automatiche

Il push di un tag `vX.Y.Z` avvia il workflow `release` (`.github/workflows/release.yml`): costruisce l'app su
GitHub per Apple Silicon e Intel, con tutti gli extra (`midi`, `capture`, `stems`, `enhance`), e pubblica
`ClusterSound-X.Y.Z-macos-arm64.zip` e `ClusterSound-X.Y.Z-macos-x86_64.zip` come
[GitHub Release](https://github.com/AleksAttanasio/ClusterSound/releases).

1. Imposta `version` in `pyproject.toml` (il bundle la legge da lì) e fai il merge di `develop` in `main`.
2. Tagga il merge su `main` e pusha il tag:

    ```bash
    git tag -a vX.Y.Z -m "ClusterSound X.Y.Z" && git push origin vX.Y.Z
    ```

Il workflow si ferma se il tag non è su `main` o non coincide con la versione in `pyproject.toml`. Lanciato a mano
dalla scheda *Actions*, costruisce soltanto e lascia gli zip come artifact del workflow.

L'app è firmata ad hoc, non notarizzata: al primo avvio macOS chiede di aprirla con tasto destro › **Apri** (o
`xattr -cr ClusterSound.app`).
