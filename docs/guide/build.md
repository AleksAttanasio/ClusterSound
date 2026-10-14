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

## Automatic releases

Pushing a `vX.Y.Z` tag runs the `release` workflow (`.github/workflows/release.yml`): it builds the app on GitHub,
in parallel, for Apple Silicon, Intel and Windows x64, with all the extras (`midi`, `capture` on the Mac, `stems`,
`enhance`), and publishes `ClusterSound-X.Y.Z-macos-arm64.zip`, `ClusterSound-X.Y.Z-macos-x86_64.zip` and
`ClusterSound-X.Y.Z-windows-x64.zip` (the `ClusterSound\` folder with `ClusterSound.exe`) as a
[GitHub Release](https://github.com/AleksAttanasio/ClusterSound/releases).

1. Set `version` in `pyproject.toml` (the bundle reads it from there) and merge `develop` into `main`.
2. Tag the merge on `main` and push the tag:

    ```bash
    git tag -a vX.Y.Z -m "ClusterSound X.Y.Z" && git push origin vX.Y.Z
    ```

The workflow stops if the tag is not on `main` or differs from the version in `pyproject.toml`. Run by hand from
the *Actions* tab, it only builds and leaves the zips as workflow artifacts.

The app is signed ad hoc, not notarized: on first launch macOS asks to open it with right-click › **Open** (or
`xattr -cr ClusterSound.app`). The Windows exe is not signed: SmartScreen asks for *More info* › **Run
anyway**.
