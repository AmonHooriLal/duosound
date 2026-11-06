"""DuoSound backend tests.  Run:  python tests/test_backend.py   (needs a Realtek-style laptop speaker output)

Backend tests for the public-release fixes. Settings/restore files go to a temp folder; the real laptop speakers
are muted/unmuted briefly (always put back). Engine is a stand-in (no audio played)."""
import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.coinit_flags = 0
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from duosound import controller as C, devices as D, engine as E, log_setup, settings as S, volume as V  # noqa: E402

log_setup.setup()
TMP = Path(tempfile.mkdtemp(prefix="duosound_test_"))
S.SETTINGS_DIR, S.SETTINGS_FILE, S.RESTORE_FILE = TMP, TMP / "settings.json", TMP / "restore.json"
results = []


def check(label, cond):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + label)


# ---------------------------------------------------------------- 1. classification from driver path + form factor
EI = D.EndpointInfo
A2DP = "{1}.BTHENUM\\{0000110B-0000-1000-8000-00805F9B34FB}_VID&0001"
HFP = "{1}.BTHHFENUM\\BTHHFPAUDIO\\8&231FCFD2&4&97"
LE = "{1}.BTHLEDEVICE\\{0000184E-0000-1000-8000-00805F9B34FB}"
HDA = "{1}.HDAUDIO\\FUNC_01&VEN_10EC&DEV_0236"
INTEL = "{1}.INTELAUDIO\\FUNC_01&VEN_10EC&DEV_0236"
USB = "{1}.USB\\VID_1B1C&PID_0A51&MI_00"
cases = [
    ("Headphones (OnePlus Buds 4)", EI(A2DP, 3), D.KIND_BLUETOOTH),
    ("Headset (OnePlus Buds 4 Hands-Free)", EI(HFP, 5), D.KIND_HANDSFREE),
    ("Headphones (AirPods Pro)", EI(A2DP, 3), D.KIND_BLUETOOTH),
    ("Speakers (UE BOOM 3)", EI(A2DP, 1), D.KIND_BLUETOOTH),
    ("Speakers (JBL Flip 6)", EI(A2DP, 1), D.KIND_BLUETOOTH),
    ("Car Audio (Honda Connect)", EI(A2DP, 1), D.KIND_BLUETOOTH),
    ("Headset (Phonak Lumity)", EI(LE, 5), D.KIND_BLUETOOTH),
    ("Speakers (Corsair VOID ELITE Wireless)", EI(USB, 1), D.KIND_WIRED),
    ("Speakers (Razer BlackShark V2 Pro)", EI(USB, 1), D.KIND_WIRED),
    ("Headphones (Sony INZONE H9)", EI(USB, 3), D.KIND_WIRED),
    ("Speakers (USB Audio Device)", EI(USB, 1), D.KIND_OTHER),          # plain USB speakers: neither ticked nor muted
    ("Headphones (Realtek(R) Audio)", EI(INTEL, 3), D.KIND_WIRED),
    ("Speakers (Realtek(R) Audio)", EI(INTEL, 1), D.KIND_SPEAKERS),
    ("Lautsprecher (Realtek(R) Audio)", EI(HDA, 1), D.KIND_SPEAKERS),   # German Windows
    ("扬声器 (Realtek(R) Audio)", EI(HDA, 1), D.KIND_SPEAKERS),          # Chinese Windows
    ("XV272U (HD Audio Driver for Display Audio)", EI("{1}.HDAUDIO\\SUBFUNC_01&VEN_8086", 9), D.KIND_HDMI),
    ("LG TV (AMD High Definition Audio Device)", EI("{1}.HDAUDIO\\FUNC_01&VEN_1002", 9), D.KIND_HDMI),
    ("CABLE Input (VB-Audio Virtual Cable)", EI("{1}.ROOT\\VBAUDIOVACMME", 10), D.KIND_CABLE),
]
bad = [(n, D.classify(n, i), want) for n, i, want in cases if D.classify(n, i) != want]
check(f"registry classification {len(cases) - len(bad)}/{len(cases)}" + (f"  wrong: {bad}" if bad else ""), not bad)
fallback = [("Headphones (Realtek(R) Audio)", D.KIND_WIRED), ("Headphones (OnePlus Buds 4)", D.KIND_BLUETOOTH),
            ("Speakers (UE BOOM 3)", D.KIND_BLUETOOTH), ("Headset (X Hands-Free AG Audio)", D.KIND_HANDSFREE),
            ("Speakers (Realtek(R) Audio)", D.KIND_SPEAKERS), ("Digital Output (HD Audio)", D.KIND_HDMI)]
fb_bad = [(n, D.classify(n, None), w) for n, w in fallback if D.classify(n, None) != w]
check(f"name fallback {len(fallback) - len(fb_bad)}/{len(fallback)}" + (f"  wrong: {fb_bad}" if fb_bad else ""), not fb_bad)
reg = D.endpoint_registry()
check(f"real registry readable (64-bit view): {len(reg or {})} endpoints", reg and len(reg) > 3)
real_hfp = [g for g, i in (reg or {}).items() if D.classify("Headset (x)", i) == D.KIND_HANDSFREE]
check(f"this PC's hands-free endpoints recognised: {len(real_hfp)}", len(real_hfp) >= 1)
outs = D.list_outputs()
check("hands-free never listed as an output", all(o.kind != D.KIND_HANDSFREE for o in outs))

# ---------------------------------------------------------------- 2. settings: never crash, clamp, keep a bad copy
for label, content in [("empty file", ""), ("truncated JSON", '{"targets": {'), ("JSON list", "[1,2]"),
                       ("targets null", '{"targets": null}'), ("UTF-8 BOM", "\ufeff{\"auto_setup\": false}"),
                       ("garbage bytes", None)]:
    if content is None:
        S.SETTINGS_FILE.write_bytes(b"\xff\xfe\x00garbage")
    else:
        S.SETTINGS_FILE.write_text(content, encoding="utf-8")
    try:
        d = S.load()
        ok = isinstance(d["targets"], dict) and isinstance(d["auto_setup"], bool)
    except Exception as exc:  # noqa: BLE001
        ok, d = False, exc
    check(f"settings load survives: {label}", ok)
check("BOM file still read (auto_setup False)", (S.SETTINGS_FILE.write_text("\ufeff{\"auto_setup\": false}", encoding="utf-8"),
                                                 S.load()["auto_setup"])[1] is False)
S.SETTINGS_FILE.write_text(json.dumps({"targets": {"a": {"delay_ms": 9999, "volume": -1}, "b": {"delay_ms": "NaN", "volume": "x"},
                                                   "c": "notadict"}}), encoding="utf-8")
t = S.load()["targets"]
check(f"values clamped: a={t.get('a')}", t["a"]["delay_ms"] == 1000 and t["a"]["volume"] == 0.0)
check(f"bad values -> defaults: b={t.get('b')}, c dropped", t["b"]["delay_ms"] == 0 and t["b"]["volume"] == 1.0 and "c" not in t)
S.SETTINGS_FILE.write_text("{broken", encoding="utf-8")
S.load()
check("unreadable file kept as settings.bad.json", (TMP / "settings.bad.json").exists())
w = E.OutputWorker(E.TargetConfig("x", "x", 99999, 7.0), threading.Event())
check("engine clamps saved delay/volume", w.cfg.delay_ms == 1000 and w.cfg.volume == 1.5)

# ---------------------------------------------------------------- 3. controller with the real speakers + stand-in engine
class DummyEngine:
    def __init__(self, *a, **kw): self.stopped = False
    def start(self): pass
    def stop(self): time.sleep(0.3); self.stopped = True
    def set_delay(self, *a): pass
    def set_volume(self, *a): pass
    def snapshot(self): return E.EngineStats()


C.Engine = DummyEngine
C.SWITCH_SETTLE_S = 0.05
S.SETTINGS_FILE.unlink(missing_ok=True)
ctl = C.AppController()
ctl.refresh_devices()
spk = D.laptop_speakers(ctl._outputs)[0]
before, default_before = V.get(spk.id), V.default_output_id()
fake = D.Output("{fake}.{bt}", "Headphones (Test BT)", D.KIND_BLUETOOTH)
ctl._outputs.append(fake)
targets = [C.TargetState(fake.id, fake.name, fake.kind, True, 0, 1.0)]
try:
    probs = ctl.start(spk.id, targets)
    s = V.get(spk.id)
    check(f"start: speakers muted, level kept ({s.level:.2f}), no problems {probs}", s.muted and abs(s.level - before.level) < .01 and not probs)
    check("restore.json written while running", S.RESTORE_FILE.exists())
    ctl.toggle_speakers(); check("unmute", not V.get(spk.id).muted and not ctl.speakers_muted)
    ctl.toggle_speakers(); check("mute again", V.get(spk.id).muted and ctl.speakers_muted)
    # quit while a Stop is still running: both must end with Windows restored
    th = threading.Thread(target=ctl.stop); th.start(); time.sleep(0.05)
    ctl.shutdown(); th.join()
    s = V.get(spk.id)
    check("quit during Stop restores mute + level + default", s.muted == before.muted and abs(s.level - before.level) < .01
          and V.default_output_id() == default_before)
    check("restore.json removed after restore", not S.RESTORE_FILE.exists())

    # crash recovery: start, then "crash" (drop the controller without stopping), then a new launch restores
    ctl2 = C.AppController(); ctl2.refresh_devices(); ctl2._outputs.append(fake)
    ctl2.start(spk.id, targets)
    check("crash scenario: speakers muted", V.get(spk.id).muted)
    del ctl2                                            # killed: no stop, no restore
    ctl3 = C.AppController()
    ctl3.refresh_devices()
    s = V.get(spk.id)
    check("next launch restores after a crash", ctl3._recovered and s.muted == before.muted and abs(s.level - before.level) < .01)

    # preflight
    many = [C.TargetState(f"{{b{i}}}", f"BT {i}", D.KIND_BLUETOOTH, True, 0, 1.0) for i in range(4)]
    pf = ctl3.preflight(spk.id, many)
    check("4 Bluetooth headsets -> radio warning", any(p.code == "many_bt" for p in pf.problems))
    check("nothing ticked -> blocking problem", any(p.blocking for p in ctl3.preflight(spk.id, []).problems))
    diag = ctl3.diagnostics()
    check("diagnostics lists outputs + log lines", "Outputs:" in diag and "Last log lines:" in diag)
finally:
    V.set(spk.id, before)
    if default_before:
        V.set_default_output(default_before)

# ---------------------------------------------------------------- 4. ring buffer under concurrent load
ring = E.Ring(0.05)
import numpy as np  # noqa: E402
total, got, stop = 300_000, [], threading.Event()


def writer():
    n = 0
    while n < total:
        k = int(np.random.randint(1, 700))
        ring.write(np.repeat(np.arange(n, n + k, dtype=np.float32)[:, None], 2, 1))
        n += k
    stop.set()


th = threading.Thread(target=writer); th.start()
while not (stop.is_set() and ring.level == 0):
    got.append(ring.read(int(np.random.randint(1, 500)))[:, 0])
th.join()
seq = np.concatenate(got)
check(f"ring keeps order under load (read {len(seq)}, dropped {ring.overflow_frames})",
      np.all(np.diff(seq) > 0) and len(seq) + ring.overflow_frames >= total)

shutil.rmtree(TMP, ignore_errors=True)          # temp settings folder: leave nothing behind
print(f"\n{sum(results)}/{len(results)} passed")
