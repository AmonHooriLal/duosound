"""Every user-facing word of the Flet window (copied from duosound/ui/theme.py, sentence case, same verb through a flow:
Start -> "Playing", Stop -> "Stopped"). Views never hard-code a sentence."""
from __future__ import annotations

import re

APP_NAME = "DuoSound"
TAGLINE = "One movie, many headphones, in sync."
THEME_LABEL = {"light": "Light", "dark": "Dark", "system": "System"}

WORDS = {
    "source": "Sound source",
    "source_help": "Windows plays the movie here, and DuoSound copies it to every pair of headphones.",
    "options": "Options",
    "opt_auto": "Switch Windows' sound output to the source while playing (put back on Stop)",
    "opt_mute": "Mute the laptop speakers while headphones play (put back on Stop)",
    "refresh": "Refresh",
    "win_sound": "Windows sound settings",
    "win_bt": "Bluetooth settings",
    "headphones": "Headphones",
    "headphones_help": "Tick everyone who listens. Test plays a beep in a pair. Use Adjust sync if one pair is ahead.",
    "col_delay": "Delay",
    "adjust_sync": "Adjust sync",
    "hide_sync": "Hide sync",
    "delay_caption": "Delay {ms} ms",
    "sync_help": "Raise it if this pair plays ahead of the others.",
    "copying": "Copying sound from",
    "change": "Change",
    "done": "Done",
    "appearance": "Appearance",
    "synced_many": "{n} headphones playing in sync",
    "synced_one": "1 headphone playing",
    "col_volume": "Volume",
    "test": "Test",
    "empty_title": "No headphones connected",
    "empty_body": "Turn your headphones on and connect them in Windows Bluetooth settings, then press Refresh.",
    "start": "Start",
    "stop": "Stop",
    "starting": "Starting…",
    "stopping": "Stopping…",
    "calibrate": "Calibrate",
    "calibrating": "Calibrating…",
    "unmute": "Unmute speakers",
    "mute": "Mute speakers",
    "sound_in": "Sound from source",
    "log": "Log",
    "help": "Help",
    "back": "Back",
    "donate": "Donate",
    "made_by": "Made by",
    "how_to_fix": "How to fix",
    "continue": "Continue",
    "cancel": "Cancel",
    "dismiss": "Dismiss",
    "hint_connect": "Connect headphones to begin.",
    "hint_tick_one": "Tick at least one pair of headphones to start.",
    "hint_ready_one": "Ready. Calibrate needs two or more pairs ticked.",
    "ready": "Ready. Press Start, then play the movie.",
    "running": "Playing",
    "waiting": "Waiting for sound. Start the movie.",
    "stopped": "Stopped.",
    "cal_intro": ("Take the headphones off and put them all right next to the laptop's microphone (usually at the top of "
                  "the screen). Keep the room quiet. Each pair will play a few short chirps."),
    "cal_start": "Start calibration",
    "cal_done": "Delays set. Fine-tune by ear if needed.",
    "cal_need_two": "Tick at least two pairs of headphones to calibrate.",
    "copy": "Copy",
    "copied": "Copied",
    "copy_diag": "Copy diagnostics",
    "open_logs": "Open log folder",
    "donate_title": "Support DuoSound",
    "donate_scan": "Scan with any UPI app (Google Pay, PhonePe, Paytm…)",
    "donate_thanks": "Thank you! Every donation keeps DuoSound free and improving.",
    "upi": "UPI ID",
    "tray_hint": "DuoSound keeps playing in the background. Right-click the tray icon to stop or quit.",
    "recovered": "DuoSound didn't close properly last time. Your Windows sound settings have been put back.",
    "busy_refresh": "Stop first, then refresh.",
}

KIND_LABEL = {
    "bluetooth": "Bluetooth",
    "wired headphones": "Wired",
    "speakers": "Laptop speakers",
    "hdmi/digital": "HDMI / digital output",
    "virtual cable": "Virtual cable",
    "other": "Other output",
}

# live status per output state: (text, tone). Tones: ok / warn / bad / mute (see tokens.tone_color)
STATUS = {
    "idle": ("", "mute"), "starting": ("Connecting…", "warn"), "buffering": ("Filling buffer…", "warn"),
    "playing": ("Playing", "ok"), "reconnecting": ("Reconnecting…", "bad"), "stopped": ("Stopped", "mute"),
    "error": ("Error", "bad"), "waiting": ("Waiting for sound", "mute"),
}

SOURCE_HINT = {
    "speakers": "Laptop speakers: muted while headphones play",
    "virtual cable": "Virtual cable: the best choice, it makes no sound",
    "hdmi/digital": "HDMI output: good, silent if no TV or monitor is plugged in",
    "wired headphones": "Wired headphones: better as listeners than as the source",
    "bluetooth": "Bluetooth headset: can't be the source",
}

_GENERIC_NAME = re.compile(r"^(Headphones|Headset|Speakers|Speaker|Earphones)\s*\((.+)\)$", re.I)


def display_name(windows_name: str) -> str:
    """'Headphones (OnePlus Buds 4)' -> 'OnePlus Buds 4' (the type is shown separately)."""
    m = _GENERIC_NAME.match(windows_name.strip())
    return m.group(2).strip() if m else windows_name


def source_hint(kind: str, fallback: str = "") -> str:
    if kind in SOURCE_HINT:
        return SOURCE_HINT[kind]
    return f"{KIND_LABEL.get(kind, kind)}: {fallback}" if fallback else ""
