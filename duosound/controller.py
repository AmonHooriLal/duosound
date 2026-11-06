"""AppController: everything DuoSound *does*, with no window code.

The UI (duosound/ui/) only calls this class and reads plain data back. It never imports engine, volume, devices or
calibrate itself, so changing the look can't break the audio (CONTEXT.md, "UI / backend split").

Problems are returned as data (Problem: code, plain text, help topic), never shown as dialogs here.
Slow work (start, stop, calibrate) is plain blocking methods; the UI runs them in a worker thread."""
from __future__ import annotations

import os
import platform
import threading
import time
import warnings
from dataclasses import dataclass, field

import numpy as np

from . import BLOCK, CHANNELS, SAMPLERATE, __version__, calibrate, devices, log_setup, settings, volume
from .engine import Engine, EngineStats, TargetConfig

log = log_setup.get("controller")

MANY_BLUETOOTH = 3          # more Bluetooth headsets than this -> warn about the radio limit
SWITCH_SETTLE_S = 0.5       # after switching Windows' default output, Bluetooth endpoints are briefly invalid (0x88890004)


@dataclass
class Problem:
    code: str            # stable id, e.g. "source_muted"
    text: str            # plain words for the user
    help_topic: str      # duosound.help_text topic key
    blocking: bool = False


@dataclass
class Device:
    """What the UI needs to know about one output."""
    id: str
    name: str
    kind: str
    is_listener: bool
    is_default: bool
    hint: str = ""


@dataclass
class TargetState:
    id: str
    name: str
    kind: str
    enabled: bool
    delay_ms: int
    volume: float        # 0..1.5


@dataclass
class Preflight:
    problems: list[Problem] = field(default_factory=list)
    confirm: str | None = None      # a yes/no question the UI must ask before start (None = nothing to ask)


@dataclass
class CalibrationLine:
    name: str
    ok: bool
    text: str


def _vol_to_dict(v: volume.VolumeState | None) -> dict | None:
    return None if v is None else {"level": v.level, "muted": v.muted}


def _vol_from_dict(d) -> volume.VolumeState | None:
    if not isinstance(d, dict):
        return None
    try:
        return volume.VolumeState(float(d["level"]), bool(d["muted"]))
    except (KeyError, TypeError, ValueError):
        return None


class AppController:
    def __init__(self) -> None:
        self.cfg = settings.load()
        self._outputs: list[devices.Output] = []
        self.engine: Engine | None = None
        self._restore: dict | None = None
        self._speakers_muted = False
        self._lock = threading.RLock()
        self._recovered = self.recover_leftover()

    # ------------------------------------------------------------------ crash recovery
    def recover_leftover(self) -> bool:
        """If the last run crashed or was killed, put Windows' sound settings back now. True if something was restored."""
        left = settings.load_restore()
        if not left:
            return False
        log.warning("Previous run didn't finish cleanly - restoring Windows sound settings now")
        self._restore = left
        self.restore_windows()
        return True

    # ------------------------------------------------------------------ devices
    def refresh_devices(self) -> None:
        self._outputs = devices.list_outputs()

    def _out(self, dev_id: str | None) -> devices.Output | None:
        return next((o for o in self._outputs if o.id == dev_id), None)

    def _device(self, o: devices.Output) -> Device:
        return Device(o.id, o.name, o.kind, o.kind in devices.LISTENER_KINDS, o.is_default, devices.SOURCE_HINT.get(o.kind, ""))

    def source_choices(self) -> list[Device]:
        return [self._device(o) for o in devices.source_candidates(self._outputs)]

    def preferred_source_id(self) -> str | None:
        cands = devices.source_candidates(self._outputs)
        saved = self.cfg.get("source_id")
        if any(o.id == saved for o in cands):
            return saved
        best = devices.suggest_source(self._outputs) or (cands[0] if cands else None)
        return best.id if best else None

    def targets_for(self, source_id: str | None) -> list[TargetState]:
        """Every output except the source, headphones first, with the saved delay/volume/ticked state."""
        saved = self.cfg.get("targets", {})
        outs = sorted([o for o in self._outputs if o.id != source_id],
                      key=lambda o: (o.kind not in devices.LISTENER_KINDS, o.name.lower()))
        res = []
        for o in outs:
            s = saved.get(o.id, {})
            res.append(TargetState(o.id, o.name, o.kind, bool(s.get("enabled", o.kind in devices.LISTENER_KINDS)),
                                   int(s.get("delay_ms", 0)), float(s.get("volume", 1.0))))
        return res

    def source_problems(self, source_id: str | None) -> list[Problem]:
        """Hints shown under the source choice before Start."""
        o = self._out(source_id)
        if o is None:
            return [Problem("no_source", "No sound output found to copy from.", "source", True)]
        if o.kind in devices.LISTENER_KINDS:
            return [Problem("headset_source", "A headset as the source would hear the movie twice, out of step. "
                                              "Pick another output.", "source")]
        if o.kind == devices.KIND_SPEAKERS and not self.cfg.get("mute_speakers", True):
            return [Problem("speakers_loud", "The movie will also play out loud from the laptop speakers.", "speakers")]
        return []

    # ------------------------------------------------------------------ settings
    def update_target(self, t: TargetState) -> None:
        self.cfg.setdefault("targets", {})[t.id] = {"name": t.name, "enabled": t.enabled, "delay_ms": int(t.delay_ms),
                                                    "volume": round(float(t.volume), 3)}
        if self.engine:
            self.engine.set_delay(t.id, t.delay_ms)
            self.engine.set_volume(t.id, t.volume)

    def set_option(self, key: str, value) -> None:
        self.cfg[key] = value

    def save(self) -> None:
        settings.save(self.cfg)

    # ------------------------------------------------------------------ start / stop
    def _speakers_to_mute(self, targets: list[TargetState]) -> list[devices.Output]:
        """Laptop speakers to mute: option on, someone listens on headphones, speakers not ticked as an output."""
        if not self.cfg.get("mute_speakers", True):
            return []
        kinds = {o.id: o.kind for o in self._outputs}
        if not any(kinds.get(t.id) in devices.LISTENER_KINDS for t in targets):
            return []
        ticked = {t.id for t in targets}
        return [o for o in devices.laptop_speakers(self._outputs) if o.id not in ticked]

    def preflight(self, source_id: str | None, targets: list[TargetState]) -> Preflight:
        """Cheap checks before Start (no Windows changes)."""
        pf = Preflight()
        src = self._out(source_id)
        chosen = [t for t in targets if t.enabled]
        if src is None:
            pf.problems.append(Problem("no_source", "Choose a sound source first.", "source", True))
            return pf
        if not chosen:
            pf.problems.append(Problem("no_targets", "Tick at least one pair of headphones.", "quickstart", True))
            return pf
        bt = sum(1 for t in chosen if t.kind == devices.KIND_BLUETOOTH)
        if bt > MANY_BLUETOOTH:
            log.warning("%d Bluetooth headsets ticked - one Bluetooth radio may not carry this many", bt)
            pf.problems.append(Problem("many_bt", f"{bt} Bluetooth headphones on one Bluetooth radio may crackle or drop out. "
                                                  "A USB Bluetooth adapter helps.", "many"))
        if self.cfg.get("auto_setup", True) and src.kind == devices.KIND_SPEAKERS and not self._speakers_to_mute(chosen):
            v = volume.get(src.id)
            if volume.source_needs_fix(v):
                pf.confirm = ("The laptop speakers are the source and must be turned up for DuoSound to hear the movie, "
                              "so the movie will also play out loud.\n\nContinue?")
        return pf

    def start(self, source_id: str, targets: list[TargetState]) -> list[Problem]:
        """Change Windows' sound settings as needed and start playing. Blocking (~0.5 s); call from a worker thread.
        Returns problems to show (empty = all good). Raises nothing."""
        with self._lock:
            if self.engine:
                return []
            src = self._out(source_id)
            chosen = [t for t in targets if t.enabled]
            if src is None or not chosen:
                return self.preflight(source_id, targets).problems
            problems: list[Problem] = []
            self._restore = {"source_id": src.id, "speakers": []}
            mute = self._speakers_to_mute(chosen)
            default_id = volume.default_output_id()
            if self.cfg.get("auto_setup", True):
                vol = volume.get(src.id)
                self._restore["volume"] = _vol_to_dict(vol)
                if default_id is None:
                    problems.append(Problem("default_unknown", f"Couldn't read Windows' sound output. Set it to "
                                                               f"\"{src.name}\" in the taskbar speaker menu.", "nosound"))
                elif default_id != src.id:
                    self._restore["default_id"] = default_id
                    self._persist_restore()             # before changing anything
                    if volume.set_default_output(src.id):
                        time.sleep(SWITCH_SETTLE_S)     # Bluetooth endpoints are briefly invalid right after a switch
                self._persist_restore()
                if src.kind == devices.KIND_SPEAKERS and any(o.id == src.id for o in mute):
                    pass   # muted below: the speakers' loopback is recorded before volume/mute (tested 2026-11-06)
                elif volume.source_needs_fix(vol):
                    volume.set(src.id, volume.VolumeState(1.0, False))
            else:
                vol = volume.get(src.id)
                if default_id is not None and default_id != src.id:
                    problems.append(Problem("not_default", f"Windows isn't playing into \"{src.name}\". Choose it in the "
                                                           "taskbar speaker menu.", "nosound"))
                if volume.source_needs_fix(vol) and src.kind != devices.KIND_SPEAKERS:
                    problems.append(Problem("source_muted", f"\"{src.name}\" is muted or turned down in Windows, so "
                                                            "the headphones will be silent.", "nosound"))
            for o in mute:
                st = volume.get(o.id)
                if st is not None:
                    self._restore["speakers"].append([o.id, st.muted])
                    self._persist_restore()
                    volume.set_mute(o.id, True)
            self._speakers_muted = bool(self._restore["speakers"])
            if self._speakers_muted:
                log.info("Laptop speakers muted while headphones play: %s", [o.name for o in mute])
            self._persist_restore()
            try:
                cfgs = [TargetConfig(t.id, t.name, t.delay_ms, t.volume, True) for t in chosen]
                self.engine = Engine(src.id, src.name, cfgs,
                                     block_size_ms=self.cfg.get("block_size_ms", 10))
                self.engine.start()
            except Exception as exc:  # noqa: BLE001
                log.error("Start failed", exc_info=True)
                self.engine = None
                self.restore_windows()
                return [Problem("start_failed", f"Couldn't start: {exc}", "trouble", True)]
            self.cfg["source_id"] = src.id
            self.save()
            return problems

    def stop(self) -> None:
        """Stop playing and put Windows back. Blocking (up to ~3 s); call from a worker thread. Safe to call twice."""
        with self._lock:
            eng, self.engine = self.engine, None
        if eng is not None:
            try:
                eng.stop()
            except Exception:  # noqa: BLE001
                log.error("Stop failed", exc_info=True)
        self.restore_windows()

    def shutdown(self) -> None:
        """App is closing: stop, restore, save. Always restores, even if Stop was already running."""
        self.stop()
        self.save()

    @property
    def running(self) -> bool:
        return self.engine is not None

    @property
    def block_size_ms(self) -> int:
        """Current block size in milliseconds (10 or 20). The UI can read this to show a toggle."""
        return self.cfg.get("block_size_ms", 10)

    def _persist_restore(self) -> None:
        if self._restore:
            settings.save_restore(self._restore)

    def restore_windows(self) -> None:
        """Put back everything Start changed. Idempotent."""
        with self._lock:
            rs, self._restore = self._restore, None
            self._speakers_muted = False
        if not rs:
            settings.clear_restore()
            return
        try:
            for dev_id, was_muted in rs.get("speakers", []):
                if dev_id != rs.get("source_id") or rs.get("volume") is None:
                    volume.set_mute(dev_id, bool(was_muted))
            v = _vol_from_dict(rs.get("volume"))
            if v is not None:
                volume.set(rs["source_id"], v)
            if rs.get("default_id") and rs["default_id"] != rs.get("source_id"):
                volume.set_default_output(rs["default_id"])
            log.info("Windows sound settings restored")
        finally:
            settings.clear_restore()

    # ------------------------------------------------------------------ speakers
    @property
    def speakers_mutable(self) -> bool:
        """True while running with speakers that DuoSound muted (the Unmute/Mute toggle applies)."""
        return bool(self.engine and self._restore and self._restore.get("speakers"))

    @property
    def speakers_muted(self) -> bool:
        return self._speakers_muted

    def toggle_speakers(self) -> bool:
        """Unmute (or mute again) the speakers DuoSound muted. Returns the new muted state."""
        if not self.speakers_mutable:
            return self._speakers_muted
        mute = not self._speakers_muted
        for dev_id, _ in self._restore.get("speakers", []):
            volume.set_mute(dev_id, mute)
        self._speakers_muted = mute
        log.info("Laptop speakers %s by the user", "muted" if mute else "unmuted")
        return mute

    # ------------------------------------------------------------------ live state
    def snapshot(self) -> EngineStats | None:
        eng = self.engine
        return eng.snapshot() if eng else None

    # ------------------------------------------------------------------ test tone / calibration
    def test_tone(self, dev_id: str, vol: float = 1.0) -> None:
        """Short two-note beep on one output (runs in its own thread)."""
        name = (self._out(dev_id) or devices.Output(dev_id, dev_id, "")).name

        def run():
            try:
                import soundcard as sc
                t = np.arange(int(SAMPLERATE * 0.25)) / SAMPLERATE
                beep = np.concatenate([np.sin(2 * np.pi * 660 * t), np.zeros(SAMPLERATE // 10), np.sin(2 * np.pi * 880 * t)])
                fade = np.minimum(1, np.minimum(np.arange(len(beep)), np.arange(len(beep))[::-1]) / 400)
                beep = (0.2 * vol * beep * fade).astype(np.float32)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    sc.get_speaker(dev_id).play(np.repeat(beep[:, None], CHANNELS, 1), samplerate=SAMPLERATE, blocksize=BLOCK)
                log.info("Test tone played on '%s'", name)
            except Exception:  # noqa: BLE001
                log.error("Test tone failed on '%s'", name, exc_info=True)
        threading.Thread(target=run, daemon=True, name="test-tone").start()

    def calibrate(self, targets: list[TargetState], progress=None) -> tuple[list[CalibrationLine], dict[str, int]]:
        """Measure each ticked headset with the laptop mic. Blocking (~6 s per headset). Raises RuntimeError with a
        plain message if there is no laptop microphone."""
        chosen = [(t.id, t.name) for t in targets if t.enabled]
        res, delays = calibrate.run(chosen, progress=progress)
        lines = []
        for m in res:
            if m.latency_ms is None:
                lines.append(CalibrationLine(m.name, False, m.message))
            else:
                lines.append(CalibrationLine(m.name, True, f"{m.latency_ms:.0f} ms → delay set to {delays.get(m.target_id, 0)} ms"))
        return lines, delays

    # ------------------------------------------------------------------ diagnostics
    def diagnostics(self) -> str:
        """Plain-text report for bug reports (no personal data beyond device names)."""
        lines = [f"DuoSound {__version__}",
                 f"Windows {platform.version()} ({platform.machine()}), Python {platform.python_version()}",
                 f"Running: {self.running}   Log: {log_setup.LOG_FILE}", "", "Outputs:"]
        try:
            for o in devices.list_outputs(include_hidden=True):
                lines.append(f"  - {o.name}  [{o.kind}{', default' if o.is_default else ''}]")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"  (could not list: {exc})")
        snap = self.snapshot()
        if snap:
            lines += ["", f"Capture: {snap.capture_state}"]
            for tid, s in snap.outputs.items():
                lines.append(f"  - {(self._out(tid) or devices.Output(tid, tid, '')).name}: {s.state}, buffer {s.level_ms:.0f} ms, "
                             f"underruns {s.underruns}, reconnects {s.reconnects}")
        lines += ["", "Last log lines:"] + [ln.rstrip() for ln in log_setup.tail(50)]
        return "\n".join(lines)

    @staticmethod
    def open_log_folder() -> None:
        try:
            os.startfile(str(log_setup.LOG_DIR))
        except OSError:
            log.warning("Could not open the log folder", exc_info=True)

    @staticmethod
    def open_windows_settings(page: str) -> None:
        """page: "sound" or "bluetooth"."""
        uri = {"sound": "ms-settings:sound", "bluetooth": "ms-settings:bluetooth"}.get(page, "ms-settings:")
        try:
            os.startfile(uri)
        except OSError:
            log.warning("Could not open %s", uri, exc_info=True)
