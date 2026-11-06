"""Audio engine: capture the source by WASAPI loopback and play it on several outputs, each with delay, volume
and automatic clock-drift correction. See CONTEXT.md §4 for the design."""
from __future__ import annotations

import threading
import time
import warnings
from dataclasses import dataclass, field

import numpy as np
import soundcard as sc

from . import BLOCK, BLOCK_SIZES, CHANNELS, SAMPLERATE, log_setup

log = log_setup.get("engine")


def _elevate_thread_priority() -> None:
    """THREAD_PRIORITY_HIGHEST on Windows so UI rendering and GIL-holders can't starve audio threads.
    Clicking any button in Flet triggers glass-panel animations and page.update() serialization that
    can hold the GIL or cause GPU DPC latency spikes long enough to underrun the WASAPI device buffer.
    Setting HIGHEST (not TIME_CRITICAL, which interferes with the system) pre-empts those spikes."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        # 2 = THREAD_PRIORITY_HIGHEST; matches the priority Windows' own audio mixer uses
        k32.SetThreadPriority(k32.GetCurrentThread(), 2)
    except Exception:  # noqa: BLE001
        pass

MS = SAMPLERATE // 1000                 # frames per millisecond
BASE_LATENCY_MS = 60                    # cushion every buffer keeps on top of its delay (absorbs capture jitter)
HARD_CORRECT_MS = 80                    # bigger error than this -> jump (drop frames / insert silence) instead of resampling
PLAYER_BUFFER_MS = 80                   # Windows-side buffer per output. 10 ms was too small: short stalls made the device
                                        # play silence, the lost time piled up in the ring and caused jumps (PROGRESS 2026-11-05)
CAPTURE_BUFFER_MS = 100                 # Windows-side capture buffer, so stalls don't lose captured audio
MAX_RATIO_DEV = 0.006                   # resampling never changes speed by more than 0.6 % (~1/10 semitone, inaudible on film sound)
KP = 0.003 / (20 * MS)                  # 20 ms error -> 0.3 % speed change
DEADBAND_MS = 3                         # within +-3 ms of target: no resampling at all
EMA_ALPHA = 0.02                        # buffer-level smoothing (~0.5 s at 10 ms blocks)
RING_SECONDS = 2.0
STATS_EVERY_S = 5.0
RECONNECT_WAIT_S = 2.0
MAX_DELAY_MS = 1000                     # slider range; ring (2 s) still has ~0.9 s headroom
STOP_DEADLINE_S = 3.0                   # Stop waits at most this long for ALL threads together


# --------------------------------------------------------------------------------------------- capture read
def read_available(rec) -> np.ndarray | None:
    """Return every frame the loopback capture has right now (frames x channels), or None if there is nothing.

    Why not rec.record(): when WASAPI delivers no packets for >40 ms, soundcard invents zeros for the waiting time,
    but Windows usually delivers the real audio for that gap afterwards -> the stream gets *extra* audio and every
    output's delay grows (measured: up to +1 % / +48 ms per 5 s, PROGRESS 2026-11-05). We never invent audio: if
    the source is truly silent (no packets) the outputs underrun, play silence and re-align when sound returns.
    Uses soundcard's private recorder helpers (soundcard 0.4.x)."""
    from soundcard.mediafoundation import _ffi, _ole32
    chunks = []
    nch = len(set(rec.channelmap))
    while rec._capture_available_frames() > 0:
        data_ptr, nframes, flags = rec._capture_buffer()
        if nframes <= 0:
            break
        if data_ptr == _ffi.NULL:
            raise RuntimeError("Could not read capture buffer")
        chunk = np.frombuffer(_ffi.buffer(data_ptr, nframes * 4 * nch), dtype=np.float32).copy()
        if flags & _ole32.AUDCLNT_BUFFERFLAGS_SILENT:
            chunk[:] = 0
        rec._capture_release(nframes)
        chunks.append(chunk)
    if not chunks:
        return None
    data = np.concatenate(chunks).reshape(-1, nch)
    return data[:, rec.channelmap]


# --------------------------------------------------------------------------------------------- ring buffer
class Ring:
    """Thread-safe circular buffer of float32 frames (N x CHANNELS). On overflow the oldest frames are dropped."""

    def __init__(self, seconds: float = RING_SECONDS):
        self.cap = int(seconds * SAMPLERATE)
        self.buf = np.zeros((self.cap, CHANNELS), np.float32)
        self.r = 0
        self.n = 0
        self.lock = threading.Lock()
        self.overflow_frames = 0

    @property
    def level(self) -> int:
        return self.n

    def write(self, x: np.ndarray) -> None:
        k = len(x)
        with self.lock:
            if k >= self.cap:
                x, k = x[-self.cap:], self.cap
            over = self.n + k - self.cap
            if over > 0:
                self.r = (self.r + over) % self.cap
                self.n -= over
                self.overflow_frames += over
            w = (self.r + self.n) % self.cap
            first = min(k, self.cap - w)
            self.buf[w:w + first] = x[:first]
            if first < k:
                self.buf[:k - first] = x[first:]
            self.n += k

    def read(self, k: int) -> np.ndarray:
        """Remove and return exactly min(k, level) frames."""
        with self.lock:
            k = min(k, self.n)
            first = min(k, self.cap - self.r)
            out = np.empty((k, CHANNELS), np.float32)
            out[:first] = self.buf[self.r:self.r + first]
            if first < k:
                out[first:] = self.buf[:k - first]
            self.r = (self.r + k) % self.cap
            self.n -= k
            return out

    def drop(self, k: int) -> int:
        with self.lock:
            k = min(k, self.n)
            self.r = (self.r + k) % self.cap
            self.n -= k
            return k

    def clear(self) -> None:
        with self.lock:
            self.r = self.n = 0


# --------------------------------------------------------------------------------------------- one output
@dataclass
class TargetConfig:
    id: str
    name: str
    delay_ms: int = 0
    volume: float = 1.0          # 0.0 - 1.5
    enabled: bool = True


@dataclass
class OutputStats:
    state: str = "idle"          # idle / starting / buffering / playing / reconnecting / stopped / error
    level_ms: float = 0.0
    target_ms: float = 0.0
    ratio: float = 1.0
    underruns: int = 0
    jumps: int = 0
    reconnects: int = 0
    last_error: str = ""
    # diagnostics counters (frames) - their rates are logged every STATS_EVERY_S
    frames_read: int = 0         # taken from the ring and played
    frames_played: int = 0       # handed to the device (incl. silence)
    frames_silence: int = 0      # silence played (buffering / jumps)
    frames_dropped: int = 0      # thrown away by jumps or ring overflow
    late_feeds: int = 0          # times this thread fed the device late (possible gap caused by us)
    max_gap_ms: float = 0.0      # longest time between two blocks handed to the device (reset every stats line)


class OutputWorker:
    """Plays one ring buffer on one device, at that device's own clock pace."""

    def __init__(self, cfg: TargetConfig, stop: threading.Event,
                 block: int = BLOCK, player_buf_ms: int = 80, ring_seconds: float = 2.0):
        cfg.delay_ms = int(max(0, min(MAX_DELAY_MS, cfg.delay_ms)))     # never trust saved values
        cfg.volume = float(max(0.0, min(1.5, cfg.volume)))
        self.cfg = cfg
        self.block = block
        self.player_buf_ms = player_buf_ms
        self.ring = Ring(ring_seconds)
        self.stats = OutputStats()
        self._stop = stop
        self._ema: float | None = None
        self._carry = 0.0
        self._last_feed: float | None = None
        self._silence = np.zeros((self.block, CHANNELS), np.float32)
        self._t = threading.Thread(target=self._run, name=f"out:{cfg.name}", daemon=True)
        self.log = log_setup.get(f"out.{cfg.name[:24]}")

    # -- control (called from GUI thread) --
    def start(self) -> None:
        self._t.start()

    def join(self, timeout: float = 3.0) -> None:
        self._t.join(max(0.0, timeout))

    def set_delay(self, ms: int) -> None:
        ms = int(max(0, min(MAX_DELAY_MS, ms)))
        if ms != self.cfg.delay_ms:
            self.log.info("Delay %d ms -> %d ms", self.cfg.delay_ms, ms)
            self.cfg.delay_ms = ms

    def set_volume(self, v: float) -> None:
        self.cfg.volume = float(max(0.0, min(1.5, v)))

    @property
    def target_frames(self) -> int:
        return (BASE_LATENCY_MS + self.cfg.delay_ms) * MS

    # -- audio thread --
    def _run(self) -> None:
        _elevate_thread_priority()
        while not self._stop.is_set():
            try:
                self.stats.state = "starting"
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    spk = sc.get_speaker(self.cfg.id)
                self.log.info("Opening output '%s'", spk.name)
                with spk.player(samplerate=SAMPLERATE, channels=CHANNELS, blocksize=self.player_buf_ms * MS) as player:
                    self._play_loop(player)
            except Exception as exc:  # noqa: BLE001 - device vanished, driver error, ...
                if self._stop.is_set():
                    break
                self.stats.state = "reconnecting"
                self.stats.reconnects += 1
                self.stats.last_error = f"{type(exc).__name__}: {exc}"
                self.log.warning("Output failed (%s) - retrying in %.0f s", self.stats.last_error, RECONNECT_WAIT_S,
                                 exc_info=self.stats.reconnects <= 1)
                self._stop.wait(RECONNECT_WAIT_S)
        self.stats.state = "stopped"
        self.log.info("Output thread ended")

    def _play_loop(self, player) -> None:
        self.ring.clear()
        self._ema = None
        self._carry = 0.0
        self._last_feed = None          # a reconnect pause is not "our" stall
        buffering = True
        self.stats.state = "buffering"
        while not self._stop.is_set():
            target = self.target_frames
            level = self.ring.level

            # 1. (re)fill to the target level before playing - keeps all outputs aligned after a start or underrun
            if buffering:
                if level >= target:
                    buffering = False
                    self._ema = float(level)
                    self.stats.state = "playing"
                    self.log.info("Buffer filled (%d ms) - playing", level // MS)
                else:
                    self._play_silence(player)
                    continue

            # 2. smoothed buffer level and error vs. target
            self._ema = level if self._ema is None else (1 - EMA_ALPHA) * self._ema + EMA_ALPHA * level
            err = self._ema - target

            # 3. big error (delay slider moved, hiccup) -> jump at once
            if err < -HARD_CORRECT_MS * MS and level < self.block:
                # nothing to play at all (source silent after a delay change): refill instead of looping silence jumps
                buffering = True
                self.stats.state = "buffering"
                self._play_silence(player)
                continue
            if abs(err) > HARD_CORRECT_MS * MS:
                self.stats.jumps += 1
                if err > 0:
                    dropped = self.ring.drop(int(level - target))
                    self.stats.frames_dropped += dropped
                    self.log.info("Jump: dropped %d ms to reach target %d ms", dropped // MS, target // MS)
                else:
                    gap = int(target - level)
                    self.log.info("Jump: inserting %d ms silence to reach target %d ms", gap // MS, target // MS)
                    for _ in range(max(1, gap // self.block)):
                        if self._stop.is_set():
                            return
                        self._play_silence(player)
                self._ema = float(self.ring.level)
                continue

            # 4. small error -> resample this block slightly faster/slower (drift correction)
            e = 0.0 if abs(err) < DEADBAND_MS * MS else err - np.sign(err) * DEADBAND_MS * MS
            ratio = 1.0 + float(np.clip(KP * e, -MAX_RATIO_DEV, MAX_RATIO_DEV))
            self._carry += self.block * ratio
            need = int(self._carry)
            self._carry -= need

            if level < need:  # underrun: source went silent (paused movie) or stalled
                self.stats.underruns += 1
                self.log.info("Buffer empty (source silent or paused) - waiting for sound, then re-aligning")
                buffering = True
                self.stats.state = "buffering"
                self._play_silence(player)
                continue

            chunk = self.ring.read(need)
            self.stats.frames_read += len(chunk)
            if need != self.block:
                xp = np.linspace(0.0, need - 1, self.block)
                idx = np.arange(need)
                chunk = np.column_stack([np.interp(xp, idx, chunk[:, c]) for c in range(CHANNELS)]).astype(np.float32)
            vol = self.cfg.volume
            if vol != 1.0:
                chunk = np.clip(chunk * vol, -1.0, 1.0)
            self.stats.ratio = ratio
            self.stats.level_ms = self._ema / MS
            self.stats.target_ms = target / MS
            self._feed(player, chunk)

    def _play_silence(self, player) -> None:
        self._feed(player, self._silence)
        self.stats.frames_silence += self.block

    def _feed(self, player, block: np.ndarray) -> None:
        """Hand one block to the device and watch for our own stalls: if this thread came back more than
        ~3/4 of the device buffer late, the device may have run dry (an audible gap + extra delay)."""
        now = time.perf_counter()
        if self._last_feed is not None:
            gap_ms = (now - self._last_feed) * 1000
            self.stats.max_gap_ms = max(self.stats.max_gap_ms, gap_ms)
            if gap_ms > self.player_buf_ms * 0.75:
                self.stats.late_feeds += 1
                self.log.debug("Late feed: %.0f ms since last block (device buffer %d ms)", gap_ms, self.player_buf_ms)
        player.play(block)
        self._last_feed = time.perf_counter()
        self.stats.frames_played += self.block


# --------------------------------------------------------------------------------------------- engine
@dataclass
class EngineStats:
    running: bool = False
    capture_state: str = "idle"
    capture_error: str = ""
    seconds: float = 0.0
    peak: float = 0.0                                   # loudness of the last captured block (0..1)
    frames_captured: int = 0
    outputs: dict[str, OutputStats] = field(default_factory=dict)


class Engine:
    """Capture `source_id` (loopback) and fan it out to every target."""

    def __init__(self, source_id: str, source_name: str, targets: list[TargetConfig],
                 block_size_ms: int = 10):
        if any(t.id == source_id for t in targets):
            raise ValueError("The source device can't also be a headphone target (the movie would play twice).")
        if not targets:
            raise ValueError("Choose at least one headphone.")
        self.source_id = source_id
        self.source_name = source_name
        # Scale buffers proportionally with block size (2× at 20ms vs 10ms default)
        buf_scale = block_size_ms / 10.0
        self._block = BLOCK_SIZES.get(block_size_ms, BLOCK)
        self._player_buf_ms = int(PLAYER_BUFFER_MS * buf_scale)   # 80 ms at 10ms, 160 ms at 20ms
        self._capture_buf_ms = int(CAPTURE_BUFFER_MS * buf_scale) # 100 ms at 10ms, 200 ms at 20ms
        self._ring_seconds = RING_SECONDS * buf_scale              # 2.0 s at 10ms, 4.0 s at 20ms
        log.info("Engine block_size=%dms  player_buf=%dms  capture_buf=%dms  ring=%.1fs",
                 block_size_ms, self._player_buf_ms, self._capture_buf_ms, self._ring_seconds)
        self._stop = threading.Event()
        self.workers: dict[str, OutputWorker] = {
            t.id: OutputWorker(t, self._stop,
                               block=self._block,
                               player_buf_ms=self._player_buf_ms,
                               ring_seconds=self._ring_seconds)
            for t in targets
        }
        self.stats = EngineStats()
        self._cap_t = threading.Thread(target=self._capture, name="capture", daemon=True)
        self._stats_t = threading.Thread(target=self._stats_logger, name="stats", daemon=True)
        self._t0 = 0.0

    # -- control --
    def start(self) -> None:
        log.info("START  source='%s'  targets=%s", self.source_name,
                 [f"{w.cfg.name} (delay {w.cfg.delay_ms} ms, vol {w.cfg.volume:.2f})" for w in self.workers.values()])
        self._t0 = time.monotonic()
        self.stats.running = True
        for w in self.workers.values():
            w.start()
        self._cap_t.start()
        self._stats_t.start()

    def stop(self) -> None:
        if not self.stats.running:
            return
        log.info("STOP requested after %.0f s", time.monotonic() - self._t0)
        self._stop.set()
        deadline = time.monotonic() + STOP_DEADLINE_S       # one shared deadline, not 3 s per headset
        self._cap_t.join(max(0.0, deadline - time.monotonic()))
        for w in self.workers.values():
            w.join(deadline - time.monotonic())
        self.stats.running = False
        self._log_stats(final=True)

    def set_delay(self, target_id: str, ms: int) -> None:
        if target_id in self.workers:
            self.workers[target_id].set_delay(ms)

    def set_volume(self, target_id: str, v: float) -> None:
        if target_id in self.workers:
            self.workers[target_id].set_volume(v)

    def snapshot(self) -> EngineStats:
        self.stats.seconds = time.monotonic() - self._t0 if self.stats.running else self.stats.seconds
        self.stats.outputs = {tid: w.stats for tid, w in self.workers.items()}
        return self.stats

    # -- threads --
    def _capture(self) -> None:
        _elevate_thread_priority()
        while not self._stop.is_set():
            try:
                self.stats.capture_state = "starting"
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    mic = sc.get_microphone(self.source_id, include_loopback=True)
                log.info("Capturing (loopback) from '%s'", mic.name)
                with mic.recorder(samplerate=SAMPLERATE, channels=CHANNELS, blocksize=self._capture_buf_ms * MS) as rec:
                    self.stats.capture_state = "waiting"
                    last_packet = time.monotonic()
                    while not self._stop.is_set():
                        data = read_available(rec)
                        if data is None:
                            # no packets = nothing is playing into the source (movie not started / paused / wrong output)
                            if self.stats.capture_state == "running" and time.monotonic() - last_packet > 0.5:
                                self.stats.capture_state = "waiting"
                                self.stats.peak = 0.0
                                log.info("No sound arriving from the source - waiting (is the movie playing into '%s'?)", self.source_name)
                            time.sleep(0.003)          # WASAPI delivers ~every 10 ms
                            continue
                        last_packet = time.monotonic()
                        if self.stats.capture_state != "running":
                            self.stats.capture_state = "running"
                            log.info("Sound is arriving from the source")
                        if data.ndim == 1:
                            data = data[:, None]
                        if data.shape[1] != CHANNELS:
                            data = np.repeat(data[:, :1], CHANNELS, axis=1)
                        data = data.astype(np.float32, copy=False)
                        self.stats.peak = float(np.max(np.abs(data))) if len(data) else 0.0
                        self.stats.frames_captured += len(data)
                        for w in self.workers.values():
                            w.ring.write(data)
            except Exception as exc:  # noqa: BLE001
                if self._stop.is_set():
                    break
                self.stats.capture_state = "reconnecting"
                self.stats.capture_error = f"{type(exc).__name__}: {exc}"
                log.warning("Capture failed (%s) - retrying in %.0f s", self.stats.capture_error, RECONNECT_WAIT_S,
                            exc_info=True)
                self._stop.wait(RECONNECT_WAIT_S)
        self.stats.capture_state = "stopped"
        log.info("Capture thread ended")

    def _stats_logger(self) -> None:
        while not self._stop.wait(STATS_EVERY_S):
            try:
                self._log_stats()
            except Exception:  # noqa: BLE001 - stats must never end the session's logging
                log.debug("Stats line failed", exc_info=True)

    def _log_stats(self, final: bool = False) -> None:
        """One line per interval. Rates are in frames/s over the interval (48000 = exactly real time):
        cap = captured, rd = read from ring, pl = handed to device, sil = silence, drop = thrown away."""
        now = time.monotonic()
        prev = getattr(self, "_prev_counts", None)
        dt = now - prev["t"] if prev else 0.0
        cur = {"t": now, "cap": self.stats.frames_captured}

        def rate(key: str, value: int) -> str:
            if not prev or dt <= 0 or key not in prev:
                return "-"
            return f"{(value - prev[key]) / dt:.0f}"

        parts = []
        for i, w in enumerate(self.workers.values()):
            s = w.stats
            counts = {f"rd{i}": s.frames_read, f"pl{i}": s.frames_played, f"sil{i}": s.frames_silence, f"dr{i}": s.frames_dropped}
            parts.append(f"{w.cfg.name[:20]}: {s.state} buf {s.level_ms:.0f}/{s.target_ms:.0f} ms "
                         f"speed {100 * (s.ratio - 1):+.3f}% rd {rate(f'rd{i}', s.frames_read)} pl {rate(f'pl{i}', s.frames_played)} "
                         f"sil {rate(f'sil{i}', s.frames_silence)} drop {rate(f'dr{i}', s.frames_dropped)} "
                         f"underruns {s.underruns} jumps {s.jumps} reconnects {s.reconnects} ring-overflow {w.ring.overflow_frames} "
                         f"late {s.late_feeds} maxgap {s.max_gap_ms:.0f}ms")
            s.max_gap_ms = 0.0
            cur.update(counts)
        log.log(20 if final else 10, "%sSTATS t=%.0fs capture=%s cap %s fps | %s", "FINAL " if final else "",
                now - self._t0, self.stats.capture_state, rate("cap", self.stats.frames_captured), " | ".join(parts))
        self._prev_counts = cur
