"""Download the Flet desktop client (flet-windows.zip, ~43 MB) that DuoSound.exe bundles, into packaging/flet_client/.
Run by build_exe.bat. The version always matches the installed `flet-desktop` package; a copy that is already there is reused."""
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEST = HERE / "flet_client" / "flet-windows.zip"


def main() -> int:
    import flet_desktop.version as v
    version = v.version
    stamp = DEST.with_suffix(".version")
    if DEST.exists() and stamp.exists() and stamp.read_text().strip() == version:
        print(f"Flet client {version} already downloaded: {DEST}")
        return 0
    url = f"https://github.com/flet-dev/flet/releases/download/v{version}/flet-windows.zip"
    DEST.parent.mkdir(exist_ok=True)
    print(f"Downloading {url} ...")
    urllib.request.urlretrieve(url, DEST)
    stamp.write_text(version)
    print(f"Saved {DEST} ({DEST.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
