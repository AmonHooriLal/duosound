"""Shared logging: one file per day, console, and a queue for the in-window log pane.

Where the log files go:
- running from source in a writable project folder: <project>/logs (easy to find while developing);
- the packaged .exe, or a read-only folder: %LOCALAPPDATA%\\DuoSound\\logs.
Logging must never stop the app: if no folder is writable, it logs to the window/console only."""
from __future__ import annotations

import logging
import logging.handlers
import os
import queue
import sys
import tempfile
import warnings
from datetime import date
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
PROJECT_DIR = Path(__file__).resolve().parent.parent
FORMAT = "%(asctime)s  %(levelname)-7s  %(name)-18s  %(message)s"

gui_queue: "queue.Queue[str]" = queue.Queue(maxsize=5000)
LOG_DIR: Path = PROJECT_DIR / "logs"
LOG_FILE: Path | None = None


class _QueueHandler(logging.Handler):
    """Puts formatted records on gui_queue (dropped if the window is not reading)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            gui_queue.put_nowait(self.format(record))
        except queue.Full:
            pass


def _candidate_dirs() -> list[Path]:
    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "DuoSound" / "logs"
    dirs = [] if FROZEN else [PROJECT_DIR / "logs"]
    return dirs + [local, Path(tempfile.gettempdir()) / "DuoSound" / "logs"]


def _open_file_handler() -> logging.Handler | None:
    global LOG_DIR, LOG_FILE
    for d in _candidate_dirs():
        try:
            d.mkdir(parents=True, exist_ok=True)
            f = d / f"duosound_{date.today():%Y-%m-%d}.log"
            fh = logging.handlers.RotatingFileHandler(f, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
            LOG_DIR, LOG_FILE = d, f
            return fh
        except OSError:
            continue
    return None


def setup(level: int = logging.INFO) -> Path | None:
    """Configure the root 'duosound' logger once. Returns the log file path (None if no folder was writable)."""
    root = logging.getLogger("duosound")
    if root.handlers:
        return LOG_FILE
    root.setLevel(logging.DEBUG)

    fh = _open_file_handler()
    if fh is not None:
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(fh)

    qh = _QueueHandler()
    qh.setLevel(level)
    qh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S"))
    root.addHandler(qh)

    if sys.stderr is not None:  # pythonw / the windowed .exe have no console
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(ch)

    # soundcard warns on every tiny capture gap ("data discontinuity") - route to the debug log instead of stderr
    logging.captureWarnings(True)
    warnings.filterwarnings("once", message=".*discontinuity.*")

    def _excepthook(exc_type, exc, tb):
        root.critical("Unhandled error", exc_info=(exc_type, exc, tb))

    sys.excepthook = _excepthook
    root.info("==== DuoSound logging started -> %s ====", LOG_FILE or "(no writable log folder)")
    return LOG_FILE


def tail(lines: int = 50) -> list[str]:
    """Last lines of today's log file (for "Copy diagnostics")."""
    if not LOG_FILE or not LOG_FILE.exists():
        return []
    try:
        with LOG_FILE.open("r", encoding="utf-8", errors="replace") as f:
            return f.readlines()[-lines:]
    except OSError:
        return []


def get(name: str) -> logging.Logger:
    return logging.getLogger(f"duosound.{name}")
