"""Find bundled files (the donate QR image) both when running from source and inside the PyInstaller .exe."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DONATE_QR = "Donate ME QR/GooglePay_QR.png"


def resource_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", PROJECT_DIR))   # PyInstaller unpacks bundled files to _MEIPASS
    return base / rel
