"""Read / change a Windows output's master volume and mute, and the Windows default output (via pycaw/comtypes).

Why: WASAPI loopback records the sound *after* the device's volume on most outputs. If the source device is muted
or at 0 % (Windows does this to an unused HDMI output) DuoSound captures silence. Found 2026-11-05, see PROGRESS.md.

COM rules (found 2026-11-06, see PROGRESS.md):
- soundcard uses COM in multi-threaded mode; comtypes must agree, so sys.coinit_flags = 0 is set before comtypes is
  imported (main.py also sets it first thing).
- Every pycaw/COM call runs on ONE dedicated thread (_ComThread). COM pointers made on a worker thread and later
  freed by Python's garbage collector on another thread crashed the process (access violation in IUnknown.Release).
  So all COM objects are created, used and freed on that one thread, with gc.collect() there after each call."""
from __future__ import annotations

import sys

sys.coinit_flags = 0  # COINIT_MULTITHREADED - must happen before comtypes/pycaw import

import gc  # noqa: E402
import queue  # noqa: E402
import threading  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Callable, TypeVar  # noqa: E402

from . import log_setup  # noqa: E402

log = log_setup.get("volume")
R = TypeVar("R")
CALL_TIMEOUT_S = 10.0


@dataclass
class VolumeState:
    level: float   # 0.0 - 1.0
    muted: bool


class _ComThread:
    """One long-lived thread that owns every COM object this module creates."""

    def __init__(self) -> None:
        self._q: "queue.Queue[tuple]" = queue.Queue()
        self._t = threading.Thread(target=self._loop, name="com-volume", daemon=True)
        self._started = False
        self._lock = threading.Lock()

    def _loop(self) -> None:
        try:
            import comtypes
            comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
        except Exception:  # noqa: BLE001 - already initialised, or comtypes missing (calls then fail one by one)
            pass
        while True:
            fn, box, done = self._q.get()
            try:
                box["result"] = fn()
            except BaseException as exc:  # noqa: BLE001
                box["error"] = exc
            finally:
                gc.collect()            # free any COM pointer cycles HERE, never on another thread
                done.set()

    def call(self, fn: Callable[[], R]) -> R:
        if threading.current_thread() is self._t:
            return fn()
        with self._lock:
            if not self._started:
                self._t.start()
                self._started = True
        box: dict = {}
        done = threading.Event()
        self._q.put((fn, box, done))
        if not done.wait(CALL_TIMEOUT_S):
            raise TimeoutError("Windows audio settings didn't answer in time")
        if "error" in box:
            raise box["error"]
        return box.get("result")


_com = _ComThread()


def _endpoint_volume(dev_id: str):
    """IAudioEndpointVolume of one device (call only on the COM thread). Opens that device directly (~3 ms) instead
    of pycaw's GetAllDevices(), which reads every property of every endpoint (~250 ms here, seconds on big PCs)."""
    import comtypes
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    dev = AudioUtilities.GetDeviceEnumerator().GetDevice(dev_id)
    return dev.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None).QueryInterface(IAudioEndpointVolume)


def get(dev_id: str) -> VolumeState | None:
    def work():
        ev = _endpoint_volume(dev_id)
        return VolumeState(float(ev.GetMasterVolumeLevelScalar()), bool(ev.GetMute()))
    try:
        return _com.call(work)
    except Exception:  # noqa: BLE001 - device gone, or pycaw/COM unavailable
        log.warning("Could not read the volume of %s", dev_id, exc_info=True)
        return None


def set(dev_id: str, state: VolumeState) -> bool:  # noqa: A001 - module-level verb is clearest here
    def work():
        ev = _endpoint_volume(dev_id)
        ev.SetMasterVolumeLevelScalar(max(0.0, min(1.0, state.level)), None)
        ev.SetMute(1 if state.muted else 0, None)
    try:
        _com.call(work)
        log.info("Set volume of %s to %.0f%%%s", dev_id, state.level * 100, " (muted)" if state.muted else "")
        return True
    except Exception:  # noqa: BLE001
        log.warning("Could not set the volume of %s", dev_id, exc_info=True)
        return False


def set_mute(dev_id: str, muted: bool) -> bool:
    """Mute / unmute only (the volume level is left alone)."""
    try:
        _com.call(lambda: _endpoint_volume(dev_id).SetMute(1 if muted else 0, None))
        log.info("%s %s", "Muted" if muted else "Unmuted", dev_id)
        return True
    except Exception:  # noqa: BLE001
        log.warning("Could not %s %s", "mute" if muted else "unmute", dev_id, exc_info=True)
        return False


def default_output_id() -> str | None:
    """Id of the current Windows default output ("{0.0.0.00000000}.{guid}")."""
    def work():
        from pycaw.pycaw import AudioUtilities, EDataFlow, ERole
        dev = AudioUtilities.GetDeviceEnumerator().GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
        return dev.GetId()
    try:
        return _com.call(work)
    except Exception:  # noqa: BLE001
        log.warning("Could not read the default output", exc_info=True)
        return None


def set_default_output(dev_id: str) -> bool:
    """Make dev_id the Windows default output (all roles: console, multimedia, communications)."""
    def work():
        from pycaw.pycaw import AudioUtilities
        AudioUtilities.SetDefaultDevice(dev_id)
    try:
        _com.call(work)
        log.info("Windows default output set to %s", dev_id)
        return True
    except Exception:  # noqa: BLE001
        log.warning("Could not change the Windows default output to %s", dev_id, exc_info=True)
        return False


def source_needs_fix(state: VolumeState | None) -> bool:
    """True if the source is muted or so low that the captured sound would be silent/weak."""
    return state is not None and (state.muted or state.level < 0.95)
