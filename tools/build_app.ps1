# Builds dist\ClusterSound\ClusterSound.exe (onedir, windowed) on Windows.
#     powershell -ExecutionPolicy Bypass -File tools\build_app.ps1
# brand\ClusterSound.ico is committed (tools/build_icon.sh makes it on the Mac).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Ambiente non trovato: crea .venv e installa con pip install -e "".[dev]""" }
& $py -m PyInstaller --noconfirm ClusterSound.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller non riuscito ($LASTEXITCODE)" }
Write-Host "Ready: dist\ClusterSound\ClusterSound.exe"
