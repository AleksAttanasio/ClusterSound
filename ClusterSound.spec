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

a = Analysis(
    [str(root / "launcher.py")],
    pathex=[str(root)],
    datas=datas,
    hiddenimports=["webview.platforms.cocoa"],
    excludes=[
        "tkinter", "_tkinter", "onnx", "onnxruntime", "h5py", "pytest", "IPython", "matplotlib", "scipy",
        "pandas", "PIL", "numpy.f2py", "numpy.distutils", "numpy.testing", "unittest",
        "pydoc", "webview.platforms.qt", "webview.platforms.gtk", "webview.platforms.cef",
        "webview.platforms.winforms", "webview.platforms.edgechromium", "PyQt5", "PyQt6",
        "PySide2", "PySide6", "gi",
    ],
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
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
    },
)
