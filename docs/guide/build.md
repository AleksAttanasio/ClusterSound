# Building the app

PyInstaller only builds for the system it runs on.

=== "macOS"

    ```bash
    tools/build_app.sh
    ```

    Result: `dist/ClusterSound.app` (it also compiles the Recorder's `cs-tap` helper and the icon, if missing).
    Distribute only the `.app` bundle.

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy Bypass -File tools\build_app.ps1
    ```

    Result: `dist\ClusterSound\ClusterSound.exe`. Distribute the whole `dist\ClusterSound` folder.

Demucs and PyTorch are included only if installed in the build environment. Details on the spec and the native
helper in [Development and tests](../technical/development.md#packaging).
