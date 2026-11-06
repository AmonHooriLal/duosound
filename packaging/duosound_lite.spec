# PyInstaller spec for DuoSound_Lite.exe (Classic Graphics / tkinter UI).
# Build with: build_exe.bat installer   or: pyinstaller packaging/duosound_lite.spec
# - windowed (no console), one file, icon + version info (author Amon Lal)
# - no Flet dependency: smaller download, faster cold start, lower idle CPU
# - bundles: donate QR image; soundcard hook for mediafoundation.py.h
from pathlib import Path

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "Donate ME QR" / "GooglePay_QR.png"), "Donate ME QR"),
    (str(ROOT / "packaging" / "duosound.ico"), "packaging"),
]

a = Analysis(
    [str(ROOT / "main_lite.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=["pystray._win32", "PIL._tkinter_finder", "comtypes.stream"],
    runtime_hooks=[],
    excludes=[
        "matplotlib", "pandas", "scipy", "IPython", "pytest", "amon_welcome",
        "flet", "flet_desktop", "flet_cli", "flet_web",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DuoSound_Lite",
    icon=str(ROOT / "packaging" / "duosound.ico"),
    version=str(ROOT / "packaging" / "version_info.txt"),
    console=False,
    upx=False,
    runtime_tmpdir=None,
)
