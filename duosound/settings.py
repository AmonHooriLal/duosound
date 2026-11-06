"""Remember the user's choices between runs: %APPDATA%\\DuoSound\\settings.json (kept out of the program folder).

Also keeps restore.json: what DuoSound changed in Windows' sound settings during a run, so it can be put back
on the next launch if the app crashed or was killed (PRODUCT.md principle 2)."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

from . import log_setup

log = log_setup.get("settings")

SETTINGS_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "DuoSound"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
RESTORE_FILE = SETTINGS_DIR / "restore.json"

DELAY_MAX_MS = 1000
VOLUME_MAX = 1.5

DEFAULTS: dict = {
    "source_id": None,
    "targets": {},          # id -> {"name", "enabled", "delay_ms", "volume"}
    "auto_setup": True,     # switch Windows output to the source + unmute it on Start, restore on Stop
    "mute_speakers": True,  # mute the laptop speakers while headphones play
    "geometry": None,
    "log_open": False,      # the developer log pane under the window (closed for normal users)
    "theme": "dark",        # "light", "dark" or "system" (follow Windows)
    "block_size_ms": 10,    # 10 (default) or 20 (Battery/Old-PC saver: 2× buffers, lower CPU overhead)
}


def _num(v, default: float, lo: float, hi: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if math.isnan(f) or math.isinf(f):
        return default
    return max(lo, min(hi, f))


def sanitize(raw) -> dict:
    """Defaults + whatever valid values `raw` has. Never raises: wrong types are dropped, numbers are clamped."""
    data = dict(DEFAULTS)
    data["targets"] = {}
    if not isinstance(raw, dict):
        return data
    if isinstance(raw.get("source_id"), str):
        data["source_id"] = raw["source_id"]
    for key in ("auto_setup", "mute_speakers", "log_open"):
        if isinstance(raw.get(key), (bool, int)):
            data[key] = bool(raw[key])
    if raw.get("theme") in ("light", "dark", "system"):
        data["theme"] = raw["theme"]
    if isinstance(raw.get("geometry"), str):
        data["geometry"] = raw["geometry"]
    raw_bs = raw.get("block_size_ms")
    if raw_bs == 20:
        data["block_size_ms"] = 20
    elif raw_bs is not None and raw_bs != 10:
        log.warning("block_size_ms %r is not valid (must be 10 or 20) - using default 10", raw_bs)
    targets = raw.get("targets")
    if isinstance(targets, dict):
        for tid, t in targets.items():
            if not isinstance(tid, str) or not isinstance(t, dict):
                continue
            data["targets"][tid] = {
                "name": str(t.get("name", "")),
                "enabled": bool(t.get("enabled", True)) if isinstance(t.get("enabled", True), (bool, int)) else True,
                "delay_ms": int(_num(t.get("delay_ms"), 0, 0, DELAY_MAX_MS)),
                "volume": round(_num(t.get("volume"), 1.0, 0.0, VOLUME_MAX), 3),
            }
    return data


def _read_json(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(text)


def load() -> dict:
    if not SETTINGS_FILE.exists():
        return sanitize({})
    try:
        data = sanitize(_read_json(SETTINGS_FILE))
        log.info("Settings loaded from %s", SETTINGS_FILE)
        return data
    except Exception:  # noqa: BLE001
        log.warning("Settings file unreadable - using defaults (a copy is kept as settings.bad.json)", exc_info=True)
        try:
            SETTINGS_FILE.replace(SETTINGS_FILE.with_name("settings.bad.json"))
        except OSError:
            pass
        return sanitize({})


def _write_json(path: Path, data) -> bool:
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except Exception:  # noqa: BLE001
        log.warning("Could not write %s", path, exc_info=True)
        return False


def save(data: dict) -> None:
    if _write_json(SETTINGS_FILE, data):
        log.debug("Settings saved")


# ---- restore state (what to put back in Windows) -------------------------------------------------------------
def save_restore(state: dict) -> None:
    _write_json(RESTORE_FILE, state)


def load_restore() -> dict | None:
    try:
        if RESTORE_FILE.exists():
            data = _read_json(RESTORE_FILE)
            return data if isinstance(data, dict) and data else None
    except Exception:  # noqa: BLE001
        log.warning("restore.json unreadable - ignoring", exc_info=True)
    return None


def clear_restore() -> None:
    try:
        RESTORE_FILE.unlink(missing_ok=True)
    except OSError:
        log.warning("Could not remove %s", RESTORE_FILE, exc_info=True)
