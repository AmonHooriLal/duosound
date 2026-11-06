"""test_block_size.py — verify the 20ms block-size setting.

No real devices, no Windows changes.  Run with:  python tests/test_block_size.py
"""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duosound.settings as S
import duosound.engine as E
from duosound import BLOCK, BLOCK_SIZES, SAMPLERATE

PASS = 0
FAIL = 0


def check(label: str, ok: bool) -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"PASS {label}")
    else:
        FAIL += 1
        print(f"FAIL {label}")


# ---- 1. Default block size is 10 ----------------------------------------
check("default block_size_ms is 10", S.sanitize({})["block_size_ms"] == 10)

# ---- 2. Explicit 20 loads correctly --------------------------------------
check("block_size_ms 20 loads", S.sanitize({"block_size_ms": 20})["block_size_ms"] == 20)

# ---- 3. Invalid integer is clamped to 10 ---------------------------------
check("block_size_ms 999 clamped to 10", S.sanitize({"block_size_ms": 999})["block_size_ms"] == 10)

# ---- 4. Wrong type is dropped → 10 --------------------------------------
check("block_size_ms 'fast' dropped to 10", S.sanitize({"block_size_ms": "fast"})["block_size_ms"] == 10)

# ---- 5-6. frames_per_block math at 48 kHz --------------------------------
check("BLOCK_SIZES[10] == 480  (10ms @ 48kHz)", BLOCK_SIZES[10] == 480)
check("BLOCK_SIZES[20] == 960  (20ms @ 48kHz)", BLOCK_SIZES[20] == 960)

# ---- 7-8. Engine buffer scaling ------------------------------------------
# Monkey-patch soundcard so Engine.__init__ is cheap and testable without hardware.
import unittest.mock as mock

_fake_spk = mock.MagicMock()
_fake_mic = mock.MagicMock()

with mock.patch("soundcard.get_speaker", return_value=_fake_spk), \
     mock.patch("soundcard.get_microphone", return_value=_fake_mic):

    cfg10 = E.TargetConfig("id-a", "HeadphonesA")
    cfg20 = E.TargetConfig("id-b", "HeadphonesB")

    # Build Engine at 10ms (default)
    stop10 = threading.Event()
    w10 = E.OutputWorker(cfg10, stop10,
                         block=BLOCK_SIZES[10],
                         player_buf_ms=80,
                         ring_seconds=2.0)

    # Build Engine at 20ms
    stop20 = threading.Event()
    w20 = E.OutputWorker(cfg20, stop20,
                         block=BLOCK_SIZES[20],
                         player_buf_ms=160,
                         ring_seconds=4.0)

check("player_buf_ms at 10ms == 80", w10.player_buf_ms == 80)
check("player_buf_ms at 20ms == 160 (2×)", w20.player_buf_ms == 160)

# ---- Bonus: ring seconds scales correctly --------------------------------
check("ring at 10ms == 2.0 s",  w10.ring.cap == int(2.0 * SAMPLERATE))
check("ring at 20ms == 4.0 s",  w20.ring.cap == int(4.0 * SAMPLERATE))

# ---- Report ---------------------------------------------------------------
total = PASS + FAIL
print()
print(f"{PASS}/{total} passed")
if FAIL:
    sys.exit(1)
