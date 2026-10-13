# PyInstaller spec: builds dist/ClusterSound.app (onedir, windowed).
#   pyinstaller --noconfirm ClusterSound.spec
from pathlib import Path

root = Path(SPECPATH)
pkg = root / "clustersound"

datas = [
    (str(pkg / "models" / "yamnet.npz"), "clustersound/models"),
    (str(pkg / "models" / "yamnet_class_map.csv"), "clustersound/models"),
    (str(pkg / "models" / "base_head.npz"), "clustersound/models"),
    (str(pkg / "patterns" / "templates" / "live10_racks.xml.gz"), "clustersound/patterns/templates"),
]
for f in (pkg / "ui").rglob("*"):
    if f.is_file():
        datas.append((str(f), str(Path("clustersound") / f.parent.relative_to(pkg))))

# Recorder helper, built by tools/build_tap.sh (build_app.sh runs it first)
binaries = [(str(pkg / "bin" / "cs-tap"), "clustersound/bin")] if (pkg / "bin" / "cs-tap").exists() else []

# Stem separation (extra `stems`): bundled only when Demucs is installed, otherwise the Recorder disables it
import importlib.util
stems_imports = []
if importlib.util.find_spec("demucs") is not None:
    from PyInstaller.utils.hooks import collect_submodules
    stems_imports = collect_submodules("demucs")
# "Migliora" (extra `enhance`): the app runs itself with --enhance-worker, which imports torch only in that process
if importlib.util.find_spec("torch") is not None:
    stems_imports += ["torch", "huggingface_hub", "clustersound.enhance.apollo_net"]

a = Analysis(
    [str(root / "launcher.py")],
    pathex=[str(root)],
    datas=datas,
    binaries=binaries,
    hiddenimports=["webview.platforms.cocoa", "ScreenCaptureKit", "CoreMedia"] + stems_imports,  # extras, if installed
    excludes=[m for m in [
        "tkinter", "_tkinter", "onnx", "onnxruntime", "h5py", "pytest", "IPython", "matplotlib", "scipy",
        "pandas", "PIL", "numpy.f2py", "numpy.distutils", "numpy.testing", "unittest",
        "pydoc", "webview.platforms.qt", "webview.platforms.gtk", "webview.platforms.cef",
        "webview.platforms.winforms", "webview.platforms.edgechromium", "PyQt5", "PyQt6",
        "PySide2", "PySide6", "gi",
    ] if not (stems_imports and m == "unittest")],  # PyTorch imports unittest
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ClusterSound",
          console=False, strip=False, upx=False, target_arch=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ClusterSound")
app = BUNDLE(
    coll,
    name="ClusterSound.app",
    icon=str(root / "brand" / "ClusterSound.icns"),
    bundle_identifier="com.clustersound.app",
    info_plist={
        "CFBundleShortVersionString": "0.6.1",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        "NSAudioCaptureUsageDescription": "Il Recorder registra l'audio in uscita dal Mac solo quando premi Registra.",
    },
)
