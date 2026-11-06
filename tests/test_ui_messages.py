"""DuoSound window message/button tests.  Run:  python tests/test_ui_messages.py

UX test of messages and button states in the real window (no audio, settings restored)."""
import sys
import time
from pathlib import Path

sys.coinit_flags = 0
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from duosound import log_setup, settings  # noqa: E402

log_setup.setup()
bak = settings.SETTINGS_FILE.read_bytes() if settings.SETTINGS_FILE.exists() else None
from duosound.controller import AppController, Problem, TargetState  # noqa: E402
from duosound.ui.main_window import MainWindow  # noqa: E402
from duosound.ui.widgets import Banner  # noqa: E402

res = []


def check(label, cond):
    res.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)


ctl = AppController()
fake = [TargetState("a", "Headphones (A)", "bluetooth", True, 0, 1.0), TargetState("b", "Headphones (B)", "bluetooth", False, 0, 1.0)]
ctl.targets_for = lambda sid: [TargetState(t.id, t.name, t.kind, t.enabled, t.delay_ms, t.volume) for t in fake]
w = MainWindow(ctl)
r = w.root


def pump(t=0.2):
    e = time.time() + t
    while time.time() < e:
        r.update(); time.sleep(0.01)


def banners():
    return [b for b in w.banners.winfo_children() if isinstance(b, Banner)]


w.clear_banners(); w._build_rows(None); pump()
check("1 ticked: Start enabled, Calibrate disabled", w.start_btn.instate(["!disabled"]) and w.cal_btn.instate(["disabled"]))
check(f"status explains why: '{w.status.cget('text')}'", "Calibrate" in w.status.cget("text"))
w.rows["b"].enabled.set(True); w.rows["b"]._changed(); pump()
check("2 ticked: Calibrate enabled", w.cal_btn.instate(["!disabled"]))
for t in w.rows.values():
    t.enabled.set(False); t._changed()
pump()
check("0 ticked: Start disabled with reason", w.start_btn.instate(["disabled"]) and "Tick" in w.status.cget("text"))
for _ in range(5):                                   # hammer: keyboard/space path still calls the handlers
    w.ask_calibrate(); w.start()
pump()
check(f"5x Calibrate + 5x Start -> only {len(banners())} message", len(banners()) == 1)
w.add_banner(Problem("x", "Short info", ""), level="info"); pump()
b = banners()[0]
check(f"auto-dismiss timer set ({b.timeout} ms)", b.timeout and 5000 <= b.timeout <= 15000)
b.timeout = 400; w._arm_banner(b); pump(0.8)
check("message vanished by itself", len(banners()) == 0)
w.add_banner(Problem("q", "Question?", ""), level="info", actions=[("OK", lambda: None, "TButton")], dismiss=False); pump(0.3)
check("question with buttons has no timer (stays until answered)", banners() and banners()[0].timeout is None)
w.add_banner(Problem("y", "Hover me", ""), level="warn"); pump()
b = banners()[0]; b.timeout = 300; w._arm_banner(b); w._cancel_banner_timer(b); pump(0.6)
check("hover pauses the countdown", len(banners()) == 1)
try:
    w.tray and w.tray.stop()
except Exception:
    pass
r.destroy()
if bak is not None:
    settings.SETTINGS_FILE.write_bytes(bak)
print(f"{sum(res)}/{len(res)} passed")
