"""DuoSound design / UX file: every colour, font, size, icon and user-facing word of the window.

A redesign touches only this file. Views (main_window, widgets, help_page, about_page) read tokens from here and
never hard-code a colour, font or sentence. The recorded visual system is in DESIGN.md.

Direction: a warm "movie night" surface, dark by default because DuoSound is used in a dimmed room next to a playing
film; a light palette is offered for bright rooms (Light / Dark / System). The orange accent appears only on the primary
action, the current selection and live state."""
from __future__ import annotations

import re
import tkinter as tk
from functools import lru_cache
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

# ---------------------------------------------------------------------------------------------- colour tokens
# Two palettes with the same token names. use(mode) copies one of them into the module-level names below, so views
# keep reading T.BG / T.TEXT ... and a mode switch is "use(...) then rebuild the window". Every text/background pair
# reaches WCAG 4.5:1 in both palettes (verified by script when the palettes were set).
# LINK is the accent as *text*: the orange button colour is too light to read on a white surface, so light mode has a
# darker orange for links, ticks, focus rings and small accent icons. In dark mode LINK == ACCENT.
PALETTES = {
    "dark": dict(
        BG="#16120F",            # window
        SURFACE="#211B16",       # sections
        SURFACE_2="#2C241D",     # inputs, rows on hover, secondary buttons
        SURFACE_3="#3A3027",     # pressed / selected nav
        LINE="#3D3229",          # hairlines
        TEXT="#F4EADF",          # primary text
        TEXT_2="#C9B8A8",        # secondary text
        TEXT_3="#A08F80",        # tertiary (captions); >= 4.5:1 on SURFACE
        ACCENT="#F28C2E",        # primary action, selection, live state (fill colour)
        ACCENT_HOVER="#FFA04A",
        ACCENT_PRESSED="#D2721A",
        ON_ACCENT="#1B1007",     # text on the orange button (white on orange fails contrast)
        LINK="#F28C2E",          # accent used as text / thin strokes
        LINK_HOVER="#FFA04A",
        OK="#6CCB94", WARN="#F2BE55", BAD="#F27A63", INFO="#8DB8F0",
        LOG_BG="#0F0C0A",
    ),
    "light": dict(
        BG="#F6F1EB",            # warm off-white window
        SURFACE="#FFFFFF",
        SURFACE_2="#EFE7DD",
        SURFACE_3="#E3D8CB",
        LINE="#D9CCBE",
        TEXT="#2A1F17",          # warm dark brown
        TEXT_2="#54443A",
        TEXT_3="#6B5B4F",
        ACCENT="#F28C2E",        # same orange as dark: it is a fill, with dark text on it
        ACCENT_HOVER="#FFA04A",
        ACCENT_PRESSED="#D2721A",
        ON_ACCENT="#1B1007",
        LINK="#964700",          # darker orange: 4.5:1+ on white and on every warm grey
        LINK_HOVER="#7F3C00",
        OK="#14683B", WARN="#80540A", BAD="#B02E19", INFO="#1D5CA8",
        LOG_BG="#EFE7DD",
    ),
}
MODES = ("light", "dark", "system")
_current = "dark"                                  # the palette in use ("light" or "dark")

BG = SURFACE = SURFACE_2 = SURFACE_3 = LINE = TEXT = TEXT_2 = TEXT_3 = ""
ACCENT = ACCENT_HOVER = ACCENT_PRESSED = ON_ACCENT = LINK = LINK_HOVER = ""
OK = WARN = BAD = INFO = LOG_BG = ""


def system_mode() -> str:
    """What Windows is set to ("light" or "dark"): the app-mode switch in Settings > Personalization > Colors."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return "light" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "dark"
    except (OSError, ImportError):
        return "dark"


def resolve(mode: str) -> str:
    """'light' / 'dark' / 'system' (anything else counts as dark) -> the palette name to draw with."""
    return system_mode() if mode == "system" else ("light" if mode == "light" else "dark")


def current() -> str:
    return _current


def use(mode: str) -> str:
    """Switch the colour tokens to `mode` and return the palette name. Views must be rebuilt afterwards: widgets keep the
    colours they were created with. The icon cache is keyed by colour, so it needs no clearing for correctness."""
    global _current
    name = resolve(mode)
    globals().update(PALETTES[name])
    _current = name
    STATUS.clear()
    STATUS.update({
        "idle": ("", TEXT_3), "starting": ("Connecting…", WARN), "buffering": ("Filling buffer…", WARN),
        "playing": ("Playing", OK), "reconnecting": ("Reconnecting…", BAD), "stopped": ("Stopped", TEXT_3),
        "error": ("Error", BAD), "waiting": ("Waiting for sound", TEXT_3),
    })
    return name


# ---------------------------------------------------------------------------------------------- type + spacing
FONT = "Segoe UI"
F_TITLE = (FONT, 15, "bold")
F_SECTION = (FONT, 11, "bold")
F_BODY = (FONT, 10)
F_BODY_BOLD = (FONT, 10, "bold")
F_SMALL = (FONT, 9)
F_BUTTON = (FONT, 10, "bold")
F_PRIMARY = (FONT, 11, "bold")
F_MONO = ("Cascadia Mono", 9)

_SCALE = 1.0


def set_scale(root: tk.Misc) -> None:
    """Pixel sizes follow Windows' display scaling (125 %, 150 % ...)."""
    global _SCALE
    try:
        _SCALE = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except tk.TclError:
        _SCALE = 1.0


def px(n: float) -> int:
    return int(round(n * _SCALE))


GAP_XS, GAP_S, GAP_M, GAP_L, GAP_XL = 4, 8, 12, 16, 24
MIN_W, MIN_H = 680, 480
DELAY_SLIDER_W, VOLUME_SLIDER_W = 140, 90
DEFAULT_W, DEFAULT_H = 980, 720
TAGLINE_MIN_W = 820          # below this window width the header tagline is hidden
ICON = 18
ICON_SMALL = 14

# ---------------------------------------------------------------------------------------------- words
APP_NAME = "DuoSound"
THEME_LABEL = {"light": "Light", "dark": "Dark", "system": "System"}
THEME_TIP = "Colour theme"
TAGLINE = "One movie, many headphones, in sync."
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
    "already_running": "DuoSound is already running. Look for its orange icon in the taskbar tray.",
    "tray_hint": "DuoSound keeps playing in the background. Right-click the tray icon to stop or quit.",
    "recovered": "DuoSound didn't close properly last time. Your Windows sound settings have been put back.",
}

_GENERIC_NAME = re.compile(r"^(Headphones|Headset|Speakers|Speaker|Earphones)\s*\((.+)\)$", re.I)


def display_name(windows_name: str) -> str:
    """'Headphones (OnePlus Buds 4)' -> 'OnePlus Buds 4' (the type is shown separately)."""
    m = _GENERIC_NAME.match(windows_name.strip())
    return m.group(2).strip() if m else windows_name


# plain-words source hint per output kind (the controller's own hints read like a spec, so the window says it this way)
SOURCE_HINT = {
    "speakers": "Laptop speakers: muted while headphones play",
    "virtual cable": "Virtual cable: the best choice, it makes no sound",
    "hdmi/digital": "HDMI output: good, silent if no TV or monitor is plugged in",
    "wired headphones": "Wired headphones: better as listeners than as the source",
    "bluetooth": "Bluetooth headset: can't be the source",
}


def source_hint(kind: str, fallback: str = "") -> str:
    """The hint line under the source dropdown ('' = show none)."""
    if kind in SOURCE_HINT:
        return SOURCE_HINT[kind]
    return f"{KIND_LABEL.get(kind, kind)}: {fallback}" if fallback else ""


KIND_LABEL = {
    "bluetooth": "Bluetooth",
    "wired headphones": "Wired",
    "speakers": "Laptop speakers",
    "hdmi/digital": "HDMI / digital output",
    "virtual cable": "Virtual cable",
    "other": "Other output",
}

# live status per output state: (text, colour); filled by use() because the colours depend on the mode
STATUS: dict[str, tuple[str, str]] = {}
use("dark")                                       # tokens must exist before anything imports them


# ---------------------------------------------------------------------------------------------- ttk styles
def apply_styles(root: tk.Tk) -> None:
    set_scale(root)
    root.configure(bg=BG)
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure(".", font=F_BODY, background=BG, foreground=TEXT, bordercolor=LINE, lightcolor=BG, darkcolor=BG,
                 troughcolor=SURFACE_2, focuscolor=LINK, selectbackground=ACCENT, selectforeground=ON_ACCENT,
                 insertcolor=TEXT, fieldbackground=SURFACE_2)
    for name, bg in (("TFrame", BG), ("Surface.TFrame", SURFACE), ("Row.TFrame", SURFACE), ("RowHover.TFrame", SURFACE_2),
                     ("Bar.TFrame", SURFACE), ("Line.TFrame", LINE), ("Nav.TFrame", SURFACE)):
        st.configure(name, background=bg)
    for name, bg, fg, font in (("TLabel", BG, TEXT, F_BODY), ("Title.TLabel", BG, TEXT, F_TITLE),
                               ("Tag.TLabel", BG, TEXT_3, F_SMALL),
                               ("Section.TLabel", SURFACE, TEXT, F_SECTION), ("Body.TLabel", SURFACE, TEXT, F_BODY),
                               ("Body2.TLabel", SURFACE, TEXT_2, F_BODY), ("Small.TLabel", SURFACE, TEXT_3, F_SMALL),
                               ("Name.TLabel", SURFACE, TEXT, F_BODY_BOLD), ("Value.TLabel", SURFACE, TEXT_2, F_SMALL),
                               ("BarStatus.TLabel", SURFACE, TEXT_2, F_BODY), ("Foot.TLabel", BG, TEXT_3, F_SMALL),
                               ("FootStrong.TLabel", BG, TEXT_2, F_SMALL)):
        st.configure(name, background=bg, foreground=fg, font=font)
    # buttons
    st.configure("TButton", font=F_BUTTON, background=SURFACE_2, foreground=TEXT, bordercolor=LINE, lightcolor=SURFACE_2,
                 darkcolor=SURFACE_2, padding=(px(12), px(6)), focusthickness=1, focuscolor=LINK)
    st.map("TButton", background=[("disabled", SURFACE), ("pressed", SURFACE_3), ("active", SURFACE_3)],
           foreground=[("disabled", TEXT_3)], bordercolor=[("focus", LINK)])
    st.configure("Primary.TButton", font=F_PRIMARY, background=ACCENT, foreground=ON_ACCENT, bordercolor=ACCENT,
                 lightcolor=ACCENT, darkcolor=ACCENT, padding=(px(22), px(8)))
    st.map("Primary.TButton", background=[("disabled", SURFACE_3), ("pressed", ACCENT_PRESSED), ("active", ACCENT_HOVER)],
           foreground=[("disabled", TEXT_3)], bordercolor=[("focus", TEXT)])
    st.configure("Row.TButton", font=F_BODY, padding=(px(10), px(3)))
    st.configure("Ghost.TButton", font=F_BODY, background=BG, foreground=TEXT_2, bordercolor=BG, lightcolor=BG, darkcolor=BG,
                 padding=(px(8), px(4)))
    st.map("Ghost.TButton", background=[("pressed", SURFACE_3), ("active", SURFACE_2)], foreground=[("active", TEXT)],
           bordercolor=[("focus", LINK)])
    st.configure("SurfaceGhost.TButton", font=F_BODY, background=SURFACE, foreground=TEXT_2, bordercolor=SURFACE,
                 lightcolor=SURFACE, darkcolor=SURFACE, padding=(px(8), px(4)))
    st.map("SurfaceGhost.TButton", background=[("pressed", SURFACE_3), ("active", SURFACE_2)], foreground=[("active", TEXT)],
           bordercolor=[("focus", LINK)])
    st.configure("Link.TButton", font=F_SMALL, background=SURFACE, foreground=LINK, bordercolor=SURFACE, lightcolor=SURFACE,
                 darkcolor=SURFACE, padding=(px(2), 0))
    st.map("Link.TButton", foreground=[("active", LINK_HOVER)], background=[("active", SURFACE)], bordercolor=[("focus", LINK)])
    st.configure("LinkBody.TButton", font=F_BODY, background=SURFACE, foreground=LINK, bordercolor=SURFACE, lightcolor=SURFACE,
                 darkcolor=SURFACE, padding=(px(4), 0))
    st.map("LinkBody.TButton", foreground=[("active", LINK_HOVER)], background=[("active", SURFACE)], bordercolor=[("focus", LINK)])
    st.configure("Nav.TButton", font=F_BODY, background=SURFACE, foreground=TEXT_2, bordercolor=SURFACE, lightcolor=SURFACE,
                 darkcolor=SURFACE, anchor="w", padding=(px(12), px(7)))
    st.map("Nav.TButton", background=[("active", SURFACE_2)], foreground=[("active", TEXT)], bordercolor=[("focus", LINK)])
    st.configure("NavOn.TButton", font=F_BODY_BOLD, background=SURFACE_3, foreground=TEXT, bordercolor=SURFACE_3,
                 lightcolor=SURFACE_3, darkcolor=SURFACE_3, anchor="w", padding=(px(12), px(7)))
    st.map("NavOn.TButton", background=[("active", SURFACE_3)], bordercolor=[("focus", LINK)])
    # segmented control (theme switch in the header): one pill, the current segment raised and bold
    st.configure("Seg.TFrame", background=SURFACE_2)
    st.configure("Seg.TButton", font=F_SMALL, background=SURFACE_2, foreground=TEXT_2, bordercolor=SURFACE_2,
                 lightcolor=SURFACE_2, darkcolor=SURFACE_2, padding=(px(10), px(3)))
    st.map("Seg.TButton", background=[("active", SURFACE_3)], foreground=[("active", TEXT)], bordercolor=[("focus", LINK)])
    st.configure("SegOn.TButton", font=(FONT, 9, "bold"), background=SURFACE_3, foreground=TEXT, bordercolor=SURFACE_3,
                 lightcolor=SURFACE_3, darkcolor=SURFACE_3, padding=(px(10), px(3)))
    st.map("SegOn.TButton", background=[("active", SURFACE_3)], bordercolor=[("focus", LINK)])
    st.configure("TSizegrip", background=BG)         # the resize grip in the window corner
    # inputs
    _checkbox_style(root, st)
    st.configure("TCombobox", fieldbackground=SURFACE_2, background=SURFACE_2, foreground=TEXT, arrowcolor=TEXT_2,
                 bordercolor=LINE, lightcolor=SURFACE_2, darkcolor=SURFACE_2, padding=(px(8), px(5)))
    st.map("TCombobox", fieldbackground=[("readonly", SURFACE_2), ("disabled", SURFACE)],
           foreground=[("readonly", TEXT), ("disabled", TEXT_3)], selectbackground=[("readonly", SURFACE_2)],
           selectforeground=[("readonly", TEXT)], bordercolor=[("focus", ACCENT)], arrowcolor=[("disabled", TEXT_3)])
    root.option_add("*TCombobox*Listbox.background", SURFACE_2)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", ON_ACCENT)
    root.option_add("*TCombobox*Listbox.font", F_BODY)
    st.configure("Horizontal.TScale", background=TEXT_2, troughcolor=SURFACE_3, bordercolor=SURFACE, lightcolor=TEXT_2,
                 darkcolor=TEXT_2, sliderthickness=px(14), gripcount=0)
    st.map("Horizontal.TScale", background=[("active", LINK), ("disabled", SURFACE_3)])
    st.configure("Meter.Horizontal.TProgressbar", background=LINK, troughcolor=SURFACE_2, bordercolor=SURFACE,
                 lightcolor=LINK, darkcolor=LINK, thickness=px(8))
    st.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
        ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])         # thin bar, no arrow buttons
    st.configure("Vertical.TScrollbar", background=SURFACE_2, troughcolor=SURFACE, bordercolor=SURFACE, arrowcolor=TEXT_3,
                 lightcolor=SURFACE_2, darkcolor=SURFACE_2, gripcount=0, arrowsize=px(8), width=px(8))
    st.map("Vertical.TScrollbar", background=[("active", SURFACE_3)])


# ---------------------------------------------------------------------------------------------- checkbox (drawn)
def _mix(c1: str, c2: str, t: float) -> str:
    """Blend two #RRGGBB colours: t=0 gives c1, t=1 gives c2."""
    a, b = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (c1, c2))
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _checkbox_image(checked: bool, disabled: bool, focus: bool, box: int, margin: int) -> Image.Image:
    """One checkbox state: rounded box (outline when off, ACCENT fill + ON_ACCENT tick when on), drawn 4x then shrunk.
    The image is `box + margin` wide: the transparent margin is the gap before the label."""
    k = 4
    img = Image.new("RGBA", ((box + margin) * k, box * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = box * k
    m, r, w = s * 0.06, s * 0.24, max(3, round(s * 0.09))
    rect = [m, m, s - m, s - m]
    if checked:
        fill = _mix(ACCENT, SURFACE, 0.55) if disabled else ACCENT
        d.rounded_rectangle(rect, radius=r, fill=fill, outline=TEXT if focus else fill, width=w if focus else 0)
        d.line([(s * .26, s * .52), (s * .43, s * .69), (s * .75, s * .32)], fill=ON_ACCENT, width=max(3, round(s * 0.13)),
               joint="curve")
    else:
        outline = LINE if disabled else (LINK if focus else TEXT_3)
        d.rounded_rectangle(rect, radius=r, fill=SURFACE if disabled else SURFACE_2, outline=outline,
                            width=w + (round(s * 0.03) if focus else 0))
    return img.resize((box + margin, box), Image.LANCZOS)


def _checkbox_style(root: tk.Tk, st: ttk.Style) -> None:
    """Replace ttk's drawn indicator (an X when ticked) with a real tick box. The element is registered once per palette
    and size; its images are kept on the root so Tk's image names stay valid."""
    box, margin = px(18), px(6)
    name = f"Duo.Checkbutton.indicator.{_current}.{box}"
    try:
        known = name in st.element_names()
    except tk.TclError:
        known = False
    if not known:
        imgs = {}
        for key, (checked, disabled, focus) in {"off": (False, False, False), "on": (True, False, False),
                                                "off_dis": (False, True, False), "on_dis": (True, True, False),
                                                "off_focus": (False, False, True), "on_focus": (True, False, True)}.items():
            imgs[key] = ImageTk.PhotoImage(_checkbox_image(checked, disabled, focus, box, margin), master=root)
        root.__dict__.setdefault("_duo_checkbox_imgs", {})[name] = imgs
        i = {k: str(v) for k, v in imgs.items()}
        st.element_create(name, "image", i["off"], ("disabled selected", i["on_dis"]), ("disabled", i["off_dis"]),
                          ("focus selected", i["on_focus"]), ("focus", i["off_focus"]), ("selected", i["on"]), sticky="w")
    st.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
        (name, {"side": "left", "sticky": ""}),
        ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [("Checkbutton.label", {"sticky": "nswe"})]})]})])
    st.configure("TCheckbutton", background=SURFACE, foreground=TEXT, font=F_BODY, focuscolor=SURFACE, focusthickness=0)
    st.map("TCheckbutton", background=[("active", SURFACE)], foreground=[("disabled", TEXT_3)])


# ---------------------------------------------------------------------------------------------- icons (drawn, not emoji)
def _canvas(size: int):
    k = 4                                    # draw 4x, then shrink for smooth edges
    img = Image.new("RGBA", (size * k, size * k), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), size * k


def _draw(name: str, d: ImageDraw.ImageDraw, s: int, c: str) -> None:
    w = max(2, s // 11)
    if name == "headphones":
        d.arc([s * .14, s * .12, s * .86, s * .84], 180, 360, fill=c, width=w)
        for x0 in (s * .1, s * .7):
            d.rounded_rectangle([x0, s * .5, x0 + s * .2, s * .86], radius=s * .06, fill=c)
    elif name == "bluetooth":
        pts = [(s * .3, s * .3), (s * .7, s * .66), (s * .5, s * .86), (s * .5, s * .14), (s * .7, s * .34), (s * .3, s * .7)]
        d.line(pts, fill=c, width=w, joint="curve")
    elif name == "plug":
        d.rounded_rectangle([s * .3, s * .3, s * .7, s * .62], radius=s * .06, fill=c)
        d.line([(s * .4, s * .12), (s * .4, s * .3)], fill=c, width=w)
        d.line([(s * .6, s * .12), (s * .6, s * .3)], fill=c, width=w)
        d.line([(s * .5, s * .62), (s * .5, s * .9)], fill=c, width=w)
    elif name in ("speaker", "speaker_off"):
        d.polygon([(s * .12, s * .38), (s * .3, s * .38), (s * .52, s * .18), (s * .52, s * .82), (s * .3, s * .62), (s * .12, s * .62)], fill=c)
        if name == "speaker":
            d.arc([s * .44, s * .3, s * .74, s * .7], 300, 60, fill=c, width=w)
            d.arc([s * .44, s * .16, s * .9, s * .84], 300, 60, fill=c, width=w)
        else:
            d.line([(s * .62, s * .36), (s * .88, s * .64)], fill=c, width=w)
            d.line([(s * .62, s * .64), (s * .88, s * .36)], fill=c, width=w)
    elif name == "help":
        d.ellipse([s * .1, s * .1, s * .9, s * .9], outline=c, width=w)
        d.arc([s * .36, s * .26, s * .64, s * .52], 200, 20, fill=c, width=w)
        d.line([(s * .62, s * .44), (s * .5, s * .54), (s * .5, s * .62)], fill=c, width=w)
        d.ellipse([s * .46, s * .7, s * .54, s * .78], fill=c)
    elif name == "heart":
        d.ellipse([s * .1, s * .2, s * .52, s * .6], fill=c)
        d.ellipse([s * .48, s * .2, s * .9, s * .6], fill=c)
        d.polygon([(s * .13, s * .48), (s * .87, s * .48), (s * .5, s * .88)], fill=c)
    elif name == "back":
        d.line([(s * .55, s * .22), (s * .27, s * .5), (s * .55, s * .78)], fill=c, width=w, joint="curve")
        d.line([(s * .3, s * .5), (s * .82, s * .5)], fill=c, width=w)
    elif name == "play":
        d.polygon([(s * .28, s * .16), (s * .84, s * .5), (s * .28, s * .84)], fill=c)
    elif name == "stop":
        d.rounded_rectangle([s * .22, s * .22, s * .78, s * .78], radius=s * .08, fill=c)
    elif name == "target":
        d.ellipse([s * .12, s * .12, s * .88, s * .88], outline=c, width=w)
        d.ellipse([s * .3, s * .3, s * .7, s * .7], outline=c, width=w)
        d.ellipse([s * .44, s * .44, s * .56, s * .56], fill=c)
    elif name == "refresh":
        d.arc([s * .16, s * .16, s * .84, s * .84], 30, 320, fill=c, width=w)
        d.polygon([(s * .66, s * .1), (s * .9, s * .3), (s * .62, s * .38)], fill=c)
    elif name == "folder":
        d.polygon([(s * .1, s * .26), (s * .4, s * .26), (s * .48, s * .34), (s * .9, s * .34), (s * .9, s * .8), (s * .1, s * .8)],
                  outline=c, width=w)
    elif name == "copy":
        d.rounded_rectangle([s * .3, s * .1, s * .86, s * .7], radius=s * .06, outline=c, width=w)
        d.rounded_rectangle([s * .14, s * .3, s * .7, s * .9], radius=s * .06, outline=c, width=w)
    elif name == "chevron_right":
        d.line([(s * .38, s * .2), (s * .66, s * .5), (s * .38, s * .8)], fill=c, width=w, joint="curve")
    elif name == "chevron_down":
        d.line([(s * .2, s * .38), (s * .5, s * .66), (s * .8, s * .38)], fill=c, width=w, joint="curve")
    elif name == "warning":
        d.polygon([(s * .5, s * .1), (s * .92, s * .86), (s * .08, s * .86)], outline=c, width=w)
        d.line([(s * .5, s * .38), (s * .5, s * .62)], fill=c, width=w)
        d.ellipse([s * .46, s * .7, s * .54, s * .78], fill=c)
    elif name == "check":
        d.line([(s * .18, s * .52), (s * .42, s * .76), (s * .84, s * .26)], fill=c, width=w, joint="curve")
    elif name == "cross":
        d.line([(s * .24, s * .24), (s * .76, s * .76)], fill=c, width=w)
        d.line([(s * .24, s * .76), (s * .76, s * .24)], fill=c, width=w)
    elif name == "settings":
        d.line([(s * .12, s * .3), (s * .88, s * .3)], fill=c, width=w)
        d.line([(s * .12, s * .7), (s * .88, s * .7)], fill=c, width=w)
        d.ellipse([s * .54, s * .2, s * .74, s * .4], fill=c)
        d.ellipse([s * .26, s * .6, s * .46, s * .8], fill=c)
    elif name == "dot":
        d.ellipse([s * .25, s * .25, s * .75, s * .75], fill=c)


@lru_cache(maxsize=256)
def _icon_image(name: str, size: int, color: str) -> Image.Image:
    img, d, s = _canvas(size)
    _draw(name, d, s, color)
    return img.resize((size, size), Image.LANCZOS)


_photo_cache: dict = {}


def clear_icon_cache() -> None:
    """Drop cached Tk icons. Call only after the widgets that used them are destroyed."""
    _photo_cache.clear()


def icon(name: str, size: int = ICON, color: str = TEXT_2) -> ImageTk.PhotoImage:
    """A drawn icon as a Tk image (cached; Tk needs the object kept alive)."""
    key = (name, px(size), color)
    if key not in _photo_cache:
        _photo_cache[key] = ImageTk.PhotoImage(_icon_image(name, px(size), color))
    return _photo_cache[key]


def make_app_icon(size: int = 64) -> Image.Image:
    """Orange rounded square with two pairs of headphones (window, tray and .exe icon)."""
    s = size
    img = Image.new("RGBA", (s * 4, s * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    S = s * 4
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=S // 5, fill=ACCENT)
    w = max(2, S // 16)
    for cx, col in ((S * 0.36, ON_ACCENT), (S * 0.64, "#5A3410")):
        r = S * 0.2
        d.arc([cx - r, S * 0.24, cx + r, S * 0.24 + 2 * r], 180, 360, fill=col, width=w)
        cup = S * 0.08
        for x in (cx - r, cx + r):
            d.rounded_rectangle([x - cup, S * 0.44, x + cup, S * 0.68], radius=cup // 2 or 1, fill=col)
    return img.resize((s, s), Image.LANCZOS)
