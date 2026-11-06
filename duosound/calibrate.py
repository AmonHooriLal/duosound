"""Measure each headset's delay with the laptop microphone and suggest per-headset delays.

How: the laptop mic records continuously. Each headset in turn plays a few short chirps (with the output already
running, so its buffer is in steady state). For each chirp we note when it was handed to the device and find when
the mic heard it (cross-correlation). Total latency = heard - sent. Systematic errors (mic latency, timer offsets)
are the same for every headset, so they cancel when we compare: delay_i = slowest - latency_i.

Headset microphones are never used (that would switch the headset into hands-free mode)."""
from __future__ import annotations

import threading
import time
import warnings
from dataclasses import dataclass

import numpy as np
import soundcard as sc

from . import BLOCK, CHANNELS, SAMPLERATE, log_setup
from .engine import CAPTURE_BUFFER_MS, MS, PLAYER_BUFFER_MS

log = log_setup.get("calibrate")

CHIRPS = 4
GAP_S = 1.2                 # silence between chirps (longer than SEARCH_S so a late chirp is not mistaken for the next)
PRIME_S = 0.4               # silence before the first chirp (lets the output buffer settle)
SEARCH_S = 1.0              # look for the chirp up to this long after it was sent (slow BT speakers reach ~0.6-0.9 s)
CHIRP_AMP = 0.35


def make_chirp(ms: int = 25) -> np.ndarray:
    n = SAMPLERATE * ms // 1000
    t = np.arange(n) / SAMPLERATE
    f0, f1 = 1500.0, 5000.0
    phase = 2 * np.pi * (f0 * t + (f1 - f0) * t * t / (2 * t[-1]))
    return (np.sin(phase) * np.hanning(n)).astype(np.float32)


@dataclass
class Measurement:
    target_id: str
    name: str
    latency_ms: float | None
    spread_ms: float | None
    hits: int
    message: str = ""


class _MicRecorder:
    """Records the mic in a thread; keeps (time-of-last-sample, block) so any sample can be placed in time."""

    def __init__(self, mic):
        self.mic = mic
        self.blocks: list[tuple[float, np.ndarray]] = []
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True, name="calib-mic")
        self.error: Exception | None = None

    def _run(self):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with self.mic.recorder(samplerate=SAMPLERATE, channels=1, blocksize=CAPTURE_BUFFER_MS * MS) as rec:
                    while not self._stop.is_set():
                        d = rec.record(numframes=BLOCK)
                        self.blocks.append((time.perf_counter(), d.reshape(-1).astype(np.float32)))
        except Exception as exc:  # noqa: BLE001
            self.error = exc
            log.error("Mic recording failed", exc_info=True)

    def __enter__(self):
        self._t.start()
        time.sleep(0.3)
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join(2)

    def signal(self) -> tuple[np.ndarray, np.ndarray]:
        """Whole recording and the perf_counter time of each sample."""
        if not self.blocks:
            return np.zeros(0, np.float32), np.zeros(0)
        sig = np.concatenate([b for _, b in self.blocks])
        times = np.concatenate([t_end - (len(b) - 1 - np.arange(len(b))) / SAMPLERATE for t_end, b in self.blocks])
        return sig, times


def find_chirp(sig: np.ndarray, times: np.ndarray, sent_at: float, chirp: np.ndarray) -> tuple[float | None, float]:
    """Return (latency seconds, confidence) of the chirp sent at `sent_at`, or (None, conf) if not found."""
    win = (times >= sent_at) & (times <= sent_at + SEARCH_S)
    idx = np.flatnonzero(win)
    if len(idx) < len(chirp) * 2:
        return None, 0.0
    seg = sig[idx[0]: idx[-1] + 1]
    seg = seg - seg.mean()
    corr = np.abs(np.correlate(seg, chirp, mode="valid"))
    if not len(corr):
        return None, 0.0
    k = int(np.argmax(corr))
    conf = float(corr[k] / (np.median(corr) + 1e-9))
    if conf < 12.0:           # peak not clearly above the noise (pure noise scores ~7, a real chirp ~100 in tests)
        return None, conf
    return float(times[idx[0] + k] - sent_at), conf


def measure_one(target_id: str, name: str, mic, progress=None) -> Measurement:
    chirp = make_chirp()
    block_chirp = np.zeros((BLOCK * ((len(chirp) // BLOCK) + 1), CHANNELS), np.float32)
    block_chirp[: len(chirp)] = (chirp * CHIRP_AMP)[:, None]
    silence = np.zeros((BLOCK, CHANNELS), np.float32)
    sent: list[float] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        spk = sc.get_speaker(target_id)
        with _MicRecorder(mic) as rec, spk.player(samplerate=SAMPLERATE, channels=CHANNELS, blocksize=PLAYER_BUFFER_MS * MS) as p:
            for _ in range(int(PRIME_S * 100)):
                p.play(silence)
            for i in range(CHIRPS):
                if progress:
                    progress(f"{name}: chirp {i + 1}/{CHIRPS}")
                p.play(block_chirp[:BLOCK])
                sent.append(time.perf_counter())   # first chirp block just entered the device buffer
                for j in range(1, len(block_chirp) // BLOCK):
                    p.play(block_chirp[j * BLOCK:(j + 1) * BLOCK])
                for _ in range(int(GAP_S * 100)):
                    p.play(silence)
    if rec.error:
        return Measurement(target_id, name, None, None, 0, f"Mic error: {rec.error}")
    sig, times = rec.signal()
    lats, confs = [], []
    for s in sent:
        lat, conf = find_chirp(sig, times, s, chirp)
        confs.append(conf)
        if lat is not None:
            lats.append(lat * 1000)
    log.info("Calibration %s: latencies %s ms (confidence %s)", name, [round(x) for x in lats], [round(c, 1) for c in confs])
    if len(lats) < 2:
        return Measurement(target_id, name, None, None, len(lats),
                           "Couldn't hear it - put the earbuds right next to the laptop's microphone and turn their volume up.")
    lats_arr = np.array(lats)
    return Measurement(target_id, name, float(np.median(lats_arr)), float(lats_arr.max() - lats_arr.min()), len(lats))


def suggest_delays(results: list[Measurement]) -> dict[str, int]:
    """Extra delay per headset so every headset ends up as late as the slowest one."""
    ok = [r for r in results if r.latency_ms is not None]
    if not ok:
        return {}
    slowest = max(r.latency_ms for r in ok)
    return {r.target_id: int(round(slowest - r.latency_ms)) for r in ok}


def run(targets: list[tuple[str, str]], progress=None) -> tuple[list[Measurement], dict[str, int]]:
    """Measure every (id, name) target with the first laptop mic. Engine must be stopped."""
    from .devices import laptop_microphones

    mics = laptop_microphones()
    if not mics:
        raise RuntimeError("No laptop microphone found for calibration.")
    mic = mics[0]
    log.info("Calibration started with mic '%s' for %s", mic.name, [n for _, n in targets])
    results = [measure_one(tid, name, mic, progress) for tid, name in targets]
    delays = suggest_delays(results)
    log.info("Calibration suggested delays: %s", {r.name: delays.get(r.target_id) for r in results})
    return results, delays
