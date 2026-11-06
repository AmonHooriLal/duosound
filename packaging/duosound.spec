# PyInstaller spec for the single-file DuoSound.exe.  Build with:  build_exe.bat   (or: pyinstaller packaging/duosound.spec)
# - windowed (no console), one file, icon + version info (author Amon Lal) from packaging/make_icon.py
# - bundles the donate QR image, the two fonts (Oswald, Atkinson Hyperlegible; SIL OFL) and the Flet desktop client
#   (packaging/flet_client/flet-windows.zip, fetched by fetch_flet_client.py; unpacked to ~/.flet/client on first run)
# - soundcard brings its own PyInstaller hook for mediafoundation.py.h
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "Donate ME QR" / "GooglePay_QR.png"), "Donate ME QR"),
    (str(ROOT / "duosound" / "ui_flet" / "fonts"), "duosound/ui_flet/fonts"),
    (str(ROOT / "packaging" / "duosound.ico"), "packaging"),
    (str(ROOT / "packaging" / "flet_client" / "flet-windows.zip"), "flet_desktop/app"),
]
datas += collect_data_files("flet.controls.material", includes=["icons.json"])
datas += collect_data_files("flet.controls.cupertino", includes=["cupertino_icons.json"])

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=["pystray._win32", "PIL._tkinter_finder", "comtypes.stream", "flet_desktop", "flet_desktop.win_taskbar",
                   "flet_desktop.extensions"] + collect_submodules("flet"),
    runtime_hooks=[str(ROOT / "packaging" / "rthook_flet.py")],
    excludes=["matplotlib", "pandas", "scipy", "IPython", "pytest", "amon_welcome", "flet_cli", "flet_web"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DuoSound",
    icon=str(ROOT / "packaging" / "duosound.ico"),
    version=str(ROOT / "packaging" / "version_info.txt"),
    console=False,
    upx=False,
    runtime_tmpdir=None,
)
