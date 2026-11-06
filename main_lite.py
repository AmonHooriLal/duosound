"""
DuoSound Lite
=============
Play one laptop's sound on two or more Bluetooth headphones at the same time, in sync, so several people can watch one movie.

This is the Lite (Classic Graphics) entry point. It uses the tkinter window and does not require Flet.
Run as:  pythonw main_lite.py   or use DuoSound_Lite.exe (the packaged build).
Made by Amon Lal.
"""
import sys

sys.coinit_flags = 0  # COM multi-threaded mode for soundcard + pycaw - must be set before anything imports comtypes
sys.setswitchinterval(0.001)  # yield GIL every 1 ms (default 5 ms) so audio threads aren't starved by heavy UI work

import ctypes  # noqa: E402

from duosound import MUTEX_NAME, __version__, log_setup  # noqa: E402

ERROR_ALREADY_EXISTS = 183


def _dpi_aware() -> None:
    """Sharp text at 125 % / 150 % display scaling (otherwise Windows blurs the window)."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001 - very old Windows
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def _single_instance():
    """Return a mutex handle, or None if DuoSound is already running (then bring that window forward).
    Uses the same MUTEX_NAME as main.py so DuoSound.exe and DuoSound_Lite.exe are mutually exclusive."""
    try:
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            hwnd = ctypes.windll.user32.FindWindowW(None, "DuoSound")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 9)          # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            return None
        return handle
    except Exception:  # noqa: BLE001 - never block start-up on this
        return True


def _error_box(text: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, text, "DuoSound", 0x10)
    except Exception:  # noqa: BLE001
        pass


def _run_ui(ctl, recovered: bool, log) -> None:
    """The tkinter window (Classic Graphics). No Flet dependency."""
    from duosound.ui.main_window import MainWindow
    log.info("User interface: tkinter (Lite)")
    MainWindow(ctl, recovered=recovered).run()


def main() -> None:
    try:
        log_file = log_setup.setup()
    except Exception:  # noqa: BLE001 - logging must never stop the app
        log_file = None
    log = log_setup.get("main_lite")
    if _single_instance() is None:
        log.info("DuoSound is already running - brought it to the front")
        return
    _dpi_aware()
    log.info("DuoSound Lite %s starting (Python %s)", __version__, sys.version.split()[0])
    try:
        from duosound.controller import AppController
        ctl = AppController()
        recovered = bool(getattr(ctl, "_recovered", False))
        _run_ui(ctl, recovered, log)
    except Exception:
        log.critical("DuoSound Lite crashed", exc_info=True)
        _error_box(f"DuoSound Lite hit an error and has to close.\n\nDetails are in:\n{log_file or log_setup.LOG_DIR}")
        raise
    log.info("DuoSound Lite closed")


if __name__ == "__main__":
    main()
