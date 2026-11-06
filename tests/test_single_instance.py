"""test_single_instance.py — verify that main.py and main_lite.py share the same mutex name.

Parse-only: no subprocess, no mutex creation, no Windows changes.
Run with:  python tests/test_single_instance.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from duosound import MUTEX_NAME  # the canonical value

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


EXPECTED = "Local\\DuoSound.SingleInstance"

# 1. The canonical export in duosound/__init__.py matches the expected string
check("MUTEX_NAME export equals expected string", MUTEX_NAME == EXPECTED)

# 2. main.py imports MUTEX_NAME from duosound (no local definition)
main_text = (ROOT / "main.py").read_text(encoding="utf-8")
check("main.py imports MUTEX_NAME from duosound",
      "from duosound import" in main_text and "MUTEX_NAME" in main_text)
check("main.py does NOT define MUTEX_NAME locally",
      'MUTEX_NAME = ' not in main_text)

# 3. main_lite.py imports MUTEX_NAME from duosound (no local definition)
lite_path = ROOT / "main_lite.py"
if not lite_path.exists():
    FAIL += 2
    print("FAIL main_lite.py not found")
    print("FAIL main_lite.py MUTEX_NAME import")
else:
    lite_text = lite_path.read_text(encoding="utf-8")
    check("main_lite.py imports MUTEX_NAME from duosound",
          "from duosound import" in lite_text and "MUTEX_NAME" in lite_text)
    check("main_lite.py does NOT define MUTEX_NAME locally",
          'MUTEX_NAME = ' not in lite_text)

# 4. Both entry points use MUTEX_NAME in their _single_instance function
check("main.py _single_instance uses MUTEX_NAME variable",
      "MUTEX_NAME" in main_text and "CreateMutexW" in main_text)
if lite_path.exists():
    check("main_lite.py _single_instance uses MUTEX_NAME variable",
          "MUTEX_NAME" in lite_text and "CreateMutexW" in lite_text)

total = PASS + FAIL
print()
print(f"{PASS}/{total} passed")
if FAIL:
    sys.exit(1)
