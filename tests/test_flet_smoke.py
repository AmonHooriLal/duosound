"""Smoke test of the Flet window with a FAKE controller (no audio, no Windows settings touched, no files written).

Run:  python tests/test_flet_smoke.py        (needs flet; opens the window for ~8 s, then closes it itself)

Checks: the window opens, shows the 4 fake headphones, Start/Calibrate are enabled, the one-line source summary is shown,
theme switching works, the help and donate pages open, and quitting calls controller.shutdown()."""
import asyncio
import sys
from pathlib import Path

sys.coinit_flags = 0
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from duosound import controller as C  # noqa: E402


class FakeCtl:
    """Same public surface as AppController, with canned data."""

    def __init__(self, delay_demo: bool = True):
        self.cfg = {"theme": "dark", "auto_setup": True, "mute_speakers": True, "log_open": False, "targets": {}}
        self.engine = None
        self.speakers_muted = False
        self._t0 = 0.0
        self.shutdown_called = False
        self.updates = []
        self.targets = [
            C.TargetState("bt1", "Headphones (OnePlus Buds 4)", "bluetooth", True, 0, 0.62),
            C.TargetState("bt2", "Headphones (OnePlus Bullets Wireless Z3)", "bluetooth", True, 35 if delay_demo else 0, 0.8),
            C.TargetState("bt3", "Headphones (Sony WH-1000XM4 Wireless Noise Cancelling)", "bluetooth", False, 0, 1.0),
            C.TargetState("wire", "Headphones (USB Audio)", "wired headphones", True, 0, 1.0),
        ]

    running = property(lambda self: self.engine is not None)
    speakers_mutable = property(lambda self: self.engine is not None)

    def refresh_devices(self): pass
    def source_choices(self): return [C.Device("spk", "Speakers (Realtek(R) Audio)", "speakers", False, True, "muted while headphones play")]
    def preferred_source_id(self): return "spk"
    def targets_for(self, source_id): return [C.TargetState(**t.__dict__) for t in self.targets]
    def source_problems(self, source_id): return []
    def update_target(self, t): self.updates.append(t)
    def set_option(self, key, value): self.cfg[key] = value
    def save(self): pass
    def preflight(self, source_id, targets): return C.Preflight()
    def start(self, source_id, targets):
        import time
        self.engine, self._t0 = object(), time.time()
        return []

    def snapshot(self):
        """Fake live stats while 'running' (same fields as engine.EngineStats)."""
        import time
        from types import SimpleNamespace as NS
        if self.engine is None:
            return None
        outs = {t.id: NS(state="playing", level_ms=62.0, underruns=0) for t in self.targets if t.enabled}
        return NS(capture_state="running", outputs=outs, peak=0.4, seconds=time.time() - self._t0)

    def stop(self): self.engine = None
    def test_tone(self, dev_id, vol=1.0): pass
    def toggle_speakers(self): return False
    def diagnostics(self): return "fake diagnostics"
    def open_log_folder(self): pass
    def open_windows_settings(self, page): pass
    def shutdown(self): self.shutdown_called = True


def run_app(ctl, driver=None, size=None):
    """Open the real window with `ctl`; `driver(app)` is an async function run after start-up (it must end by calling app.quit())."""
    import flet as ft
    from duosound.ui_flet.app import DuoApp

    class Driven(DuoApp):
        async def main(self, page):
            await super().main(page)
            if driver:
                page.run_task(driver, self)

    if size:
        ctl.cfg["geometry"] = f"{size[0]}x{size[1]}"
    app = Driven(ctl)
    ft.run(app.main)
    return app


if __name__ == "__main__":
    ctl = FakeCtl()
    checks = []

    async def driver(app):
        await asyncio.sleep(3.0)
        checks.append(("4 headphone rows", len(app.rows) == 4))
        checks.append(("source is one line (summary shown)", app.src_summary.visible and not app.src_panel.visible))
        checks.append(("Start enabled", not app.start_btn.disabled))
        checks.append(("Calibrate enabled (3 ticked)", not app.cal_btn.disabled))
        checks.append(("status says Ready", app.status.value.startswith("Ready")))
        await app.set_theme("light")
        await asyncio.sleep(2.0)
        checks.append(("theme switched to light", app.scenery.mode == "light" and ctl.cfg["theme"] == "light"))
        app.show_page("help")
        await asyncio.sleep(0.5)
        app.show_page("about")
        await asyncio.sleep(0.5)
        app.show_page("main")
        await app.start()                                   # fake controller: no audio, no Windows settings
        await asyncio.sleep(1.0)
        checks.append(("Start: running, scenery frozen, Stop button", ctl.running and app.scenery.frozen and app.start_btn.content == "Stop"))
        checks.append(("status: 3 headphones playing in sync", "3 headphones playing in sync" in app.status.value))
        checks.append(("Mute speakers button shown while running", app.spk_btn.visible))
        await asyncio.sleep(4.5)
        checks.append(("status: m:ss Playing", app.status.value.endswith("Playing") and ":" in app.status.value))
        checks.append(("row status live", app.rows["bt1"].status.value.startswith("Playing")))
        await app.stop()
        checks.append(("Stop: scenery runs again, Start button back", not app.scenery.frozen and app.start_btn.content == "Start"))
        checks.append(("status Ready after Stop", app.status.value.startswith("Ready")))
        await app.quit()

    run_app(ctl, driver)
    checks.append(("shutdown called on quit", ctl.shutdown_called))
    ok = True
    for label, cond in checks:
        print(("PASS " if cond else "FAIL ") + label)
        ok &= bool(cond)
    print(f"{sum(bool(c) for _, c in checks)}/{len(checks)} passed")
    sys.exit(0 if ok else 1)
