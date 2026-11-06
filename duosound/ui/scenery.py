"""Animated scenery behind the DuoSound window: a moonlit night (dark mode) or a sunny day (light mode).

Look: a flat, grainy "printed poster" landscape (inspired by Amon's reference): sky, moon or sun, distant hills, a lake
with a shimmering light path, a small house on the hill (windows lit at night), cypress and round trees, and a
meadow along the bottom. Trees and grass sway in a gusting wind; the light path on the water shimmers.

Kept cheap because DuoSound runs next to a playing movie:
- everything that never moves (sky, moon/sun, stars, hills, lake, house, grain) is painted ONCE with PIL
  (again only when the window size or the theme changes);
- only trees, grass blades, clouds and water glints are live canvas items; each frame only moves their points (15 fps);
- the animation pauses while the window is minimised and is off when Windows' "Show animations" is off.
Switching light/dark crossfades the painted layer and blends the live colours.
The scene has its own palettes (SCENES); the UI colour tokens in theme.py are untouched."""
from __future__ import annotations

import ctypes
import math
import random
import tkinter as tk

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageTk

FPS = 15
FADE_STEPS = 8

SCENES = {
    "dark": {
        "sky_top": (10, 18, 40), "sky_bottom": (30, 46, 84), "glow": (250, 236, 200), "body": (243, 231, 200),
        "spot": (205, 190, 156), "hill_far": (22, 36, 66), "hill_mid": (17, 29, 55), "water": (14, 26, 52),
        "water_line": (32, 50, 88), "path": (246, 230, 190), "ground": (10, 18, 34), "house": (20, 26, 40),
        "roof": (40, 30, 34), "window": (255, 196, 96), "tree": (9, 16, 31), "tree_lit": (44, 66, 104),
        "trunk": (7, 12, 22), "grass": (12, 23, 42), "grass_tip": (58, 82, 120), "cloud": (38, 54, 92),
        "star": (238, 230, 206),
    },
    "light": {
        "sky_top": (118, 186, 228), "sky_bottom": (253, 233, 198), "glow": (255, 222, 140), "body": (255, 206, 92),
        "spot": (255, 226, 150), "hill_far": (156, 190, 150), "hill_mid": (120, 162, 108), "water": (96, 160, 196),
        "water_line": (150, 200, 222), "path": (255, 246, 214), "ground": (82, 128, 66), "house": (238, 222, 196),
        "roof": (184, 92, 58), "window": (90, 110, 130), "tree": (44, 90, 56), "tree_lit": (126, 172, 96),
        "trunk": (96, 64, 42), "grass": (70, 118, 52), "grass_tip": (160, 198, 104), "cloud": (255, 251, 244),
        "star": (255, 255, 255),
    },
}


def animations_enabled() -> bool:
    """Windows 'Show animations in Windows' (SPI_GETCLIENTAREAANIMATION). True if it can't be read."""
    try:
        val = ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(val), 0)
        return bool(val.value)
    except Exception:  # noqa: BLE001
        return True


def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in c)


def _mix(a, b, t: float):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


class Layout:
    """Where things are, as fractions of the canvas, so painted and live layers line up at any size."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.horizon = h * 0.62                      # lake surface line
        self.sun = (w * 0.80, h * 0.20, max(24, min(w, h) * 0.07))
        self.lake = (w * 0.38, w * 1.0)              # lake spans the right part
        self.meadow = h * 0.90

    def hill(self, x: float) -> float:
        """Near hill on the left that falls towards the lake (house and trees stand on it)."""
        w, h = self.w, self.h
        f = x / w
        if f < 0.52:
            return h * (0.50 + 0.30 * (f / 0.52) ** 1.8) + h * 0.015 * math.sin(f * 21)
        return self.meadow + 4


def paint_static(mode: str, w: int, h: int) -> Image.Image:
    """Sky, moon/sun, stars, hills, lake, house and grain: everything that never moves."""
    c = SCENES[mode]
    w, h = max(w, 80), max(h, 80)
    L = Layout(w, h)
    t = np.linspace(0, 1, h)[:, None]
    top, bot = np.array(c["sky_top"], float), np.array(c["sky_bottom"], float)
    sky = (top + (bot - top) * t ** 1.3)[:, None, :].repeat(w, axis=1)
    img = Image.fromarray(sky.astype(np.uint8), "RGB")
    rnd = random.Random(7)
    cx, cy, r = L.sun
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse([cx - r * 3.2, cy - r * 3.2, cx + r * 3.2, cy + r * 3.2], fill=95 if mode == "dark" else 140)
    glow = glow.filter(ImageFilter.GaussianBlur(r * 1.4))
    img = Image.composite(Image.new("RGB", (w, h), c["glow"]), img, glow)
    d = ImageDraw.Draw(img)
    if mode == "dark":
        for _ in range(int(w * h / 7000)):
            x, y = rnd.randrange(w), rnd.randrange(int(L.horizon * 0.85))
            if math.hypot(x - cx, y - cy) < r * 2.5:
                continue
            s = rnd.choice((1, 1, 1, 2))
            d.ellipse([x, y, x + s, y + s], fill=c["star"])
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c["body"])
        for _ in range(int(r * r / 5)):                          # speckled, printed-looking moon
            a, rr = rnd.uniform(0, 6.283), r * math.sqrt(rnd.random()) * 0.96
            d.point((cx + rr * math.cos(a), cy + rr * math.sin(a)), fill=c["spot"])
    else:
        for k in range(16):
            a = k * math.pi / 8
            d.line([(cx + math.cos(a) * r * 1.3, cy + math.sin(a) * r * 1.3),
                    (cx + math.cos(a) * r * 1.65, cy + math.sin(a) * r * 1.65)], fill=c["body"], width=max(2, int(r / 8)))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c["body"])
    # distant hills across the horizon, then the lake
    for col, base, amp, seed in ((c["hill_far"], L.horizon - h * 0.05, h * 0.05, 3), (c["hill_mid"], L.horizon - h * 0.01, h * 0.03, 9)):
        rr = random.Random(seed)
        ph = [rr.uniform(0, 6.3) for _ in range(3)]
        pts = [(x, base - amp * (math.sin(x / w * 3.1 + ph[0]) + 0.5 * math.sin(x / w * 7.3 + ph[1]) + 0.25 * math.sin(x / w * 13 + ph[2])))
               for x in range(0, w + 10, 10)]
        d.polygon(pts + [(w, L.horizon), (0, L.horizon)], fill=col)
    d.rectangle([0, L.horizon, w, h], fill=c["water"])
    for k in range(18):                                          # calm water lines
        y = L.horizon + (h - L.horizon) * (k / 18) ** 1.6 + 3
        x0 = rnd.uniform(0, w * 0.6)
        d.line([(x0, y), (x0 + rnd.uniform(w * 0.1, w * 0.4), y)], fill=c["water_line"], width=1)
    # near hill (left) with a small house
    hill = [(x, L.hill(x)) for x in range(0, int(w * 0.56), 6)]
    d.polygon(hill + [(w * 0.56, h), (0, h)], fill=c["ground"])
    hx, hy = w * 0.13, L.hill(w * 0.13)
    hw, hh = w * 0.075, h * 0.07
    d.rectangle([hx, hy - hh, hx + hw, hy + 4], fill=c["house"])
    d.polygon([(hx - hw * 0.08, hy - hh), (hx + hw / 2, hy - hh * 1.55), (hx + hw * 1.08, hy - hh)], fill=c["roof"])
    for i in range(3):                                           # windows: lit at night
        wx = hx + hw * (0.14 + i * 0.3)
        d.rectangle([wx, hy - hh * 0.72, wx + hw * 0.15, hy - hh * 0.36], fill=c["window"])
    d.rectangle([0, L.meadow, w, h], fill=c["ground"])
    # printed grain
    noise = np.random.default_rng(5).normal(0, 8 if mode == "dark" else 5, (h, w, 1))
    arr = np.clip(np.asarray(img, float) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


class Scenery:
    """Draws the scene on a tk.Canvas and keeps it moving. Call set_mode('dark'|'light'). Put UI on top with
    canvas.create_window (opaque panels); the scene shows around them."""

    def __init__(self, canvas: tk.Canvas, mode: str = "dark", animate: bool | None = None):
        self.cv = canvas
        self.mode = mode
        self.animate = animations_enabled() if animate is None else animate
        self.t = 0.0
        self._w = self._h = 0
        self._img_id = None
        self._photo = None
        self._static: Image.Image | None = None
        self._fade: list = []
        self._blend = 1.0
        self._from_mode = mode
        self._job = None
        self._resize_job = None
        self.trees: list[dict] = []
        self.blades: list[dict] = []
        self.clouds: list[dict] = []
        self.stars: list[dict] = []
        self.glints: list[dict] = []
        canvas.bind("<Configure>", self._on_configure, add="+")

    # ------------------------------------------------------------------ public
    def set_mode(self, mode: str) -> None:
        if mode == self.mode or mode not in SCENES:
            return
        old = self._static
        self._from_mode, self.mode = self.mode, mode
        if self._w < 10 or old is None:
            self._rebuild()
            return
        new = paint_static(mode, self._w, self._h)
        self._static = new
        self._fade = [ImageTk.PhotoImage(Image.blend(old, new, (i + 1) / FADE_STEPS)) for i in range(FADE_STEPS)]
        self._blend = 0.0
        self._fade_step(0)

    def start(self) -> None:
        if self._job is None:
            self._tick()

    def stop(self) -> None:
        if self._job is not None:
            try:
                self.cv.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def lower_all(self) -> None:
        self.cv.tag_lower("scene")

    # ------------------------------------------------------------------ build
    def _on_configure(self, e) -> None:
        if (e.width, e.height) == (self._w, self._h):
            return
        if self._resize_job:
            self.cv.after_cancel(self._resize_job)
        self._resize_job = self.cv.after(120, lambda: self._resize(e.width, e.height))

    def _resize(self, w: int, h: int) -> None:
        self._resize_job = None
        self._w, self._h = w, h
        self._rebuild()

    def _rebuild(self) -> None:
        w, h = max(self._w, 80), max(self._h, 80)
        L = self.L = Layout(w, h)
        self.cv.delete("scene")
        self._static = paint_static(self.mode, w, h)
        self._photo = ImageTk.PhotoImage(self._static)
        self._img_id = self.cv.create_image(0, 0, image=self._photo, anchor="nw", tags=("scene",))
        rnd = random.Random(42)
        c = self._colors()
        item = self.cv.create_polygon
        self.clouds = []
        for _ in range(3):
            cw = rnd.uniform(0.12, 0.2) * w
            ids = [self.cv.create_oval(0, 0, 1, 1, fill=_hex(c["cloud"]), outline="", tags=("scene",)) for _ in range(3)]
            self.clouds.append({"x": rnd.uniform(0, w), "y": rnd.uniform(0.07, 0.3) * h, "w": cw, "ids": ids,
                                "speed": rnd.uniform(3, 7)})
        self.stars = []
        for _ in range(16):
            x, y = rnd.uniform(0, w * 0.7), rnd.uniform(0, L.horizon * 0.7)
            sid = self.cv.create_oval(x, y, x + 2, y + 2, fill=_hex(c["star"]), outline="", tags=("scene",))
            self.stars.append({"id": sid, "ph": rnd.uniform(0, 6.28), "sp": rnd.uniform(0.8, 2.2)})
        # glints: the moon/sun path on the lake, shimmering
        self.glints = []
        sx = L.sun[0]
        for k in range(26):
            f = (k / 26) ** 1.3
            y = L.horizon + 6 + (h * 0.88 - L.horizon) * f
            half = L.sun[2] * (0.35 + 1.4 * f)
            gid = self.cv.create_line(0, 0, 1, 1, fill=_hex(c["path"]), width=max(1, int(1 + f * 3)), tags=("scene",))
            self.glints.append({"id": gid, "x": sx, "y": y, "half": half, "ph": rnd.uniform(0, 6.28)})
        # trees: tall cypresses (Mediterranean) and round trees on the hill, two-tone (lit side towards the light)
        self.trees = []
        for fx, kind, scale in ((0.03, "cypress", 1.1), (0.075, "round", 0.9), (0.24, "cypress", 1.25), (0.29, "cypress", 0.95),
                                (0.36, "round", 1.05), (0.44, "cypress", 0.8), (0.97, "round", 0.8)):
            x = fx * w
            base = L.hill(x) + (3 if fx < 0.5 else -2)
            th = h * 0.2 * scale
            tw = th * (0.22 if kind == "cypress" else 0.5)
            trunk = item(0, 0, 0, 0, 0, 0, fill=_hex(c["trunk"]), outline="", tags=("scene",))
            crown = item(0, 0, 0, 0, 0, 0, fill=_hex(c["tree"]), outline="", smooth=True, tags=("scene",))
            lit = item(0, 0, 0, 0, 0, 0, fill=_hex(c["tree_lit"]), outline="", smooth=True, tags=("scene",))
            self.trees.append({"x": x, "y": base, "h": th, "w": tw, "kind": kind, "trunk": trunk, "crown": crown,
                               "lit": lit, "ph": rnd.uniform(0, 6.28), "stiff": rnd.uniform(0.75, 1.2)})
        # meadow
        self.blades = []
        n = int(w / 7)
        for i in range(n):
            x = i * w / n + rnd.uniform(-3, 3)
            bh = rnd.uniform(0.03, 0.075) * h
            tmix = rnd.uniform(0, 0.6)
            bid = self.cv.create_line(0, 0, 0, 0, 0, 0, fill=_hex(_mix(c["grass"], c["grass_tip"], tmix)),
                                      width=rnd.choice((1, 2, 2, 3)), smooth=True, capstyle="round", tags=("scene",))
            self.blades.append({"x": x, "y": L.meadow + rnd.uniform(0, h * 0.08), "h": bh, "id": bid, "t": tmix,
                                "ph": rnd.uniform(0, 6.28)})
        self._place_live()
        self.lower_all()

    # ------------------------------------------------------------------ animation
    def _colors(self) -> dict:
        a, b = SCENES[self._from_mode], SCENES[self.mode]
        return {k: _mix(a[k], b[k], self._blend) for k in b}

    def _wind(self, x: float) -> float:
        """Gusting wind: a slow sway plus gusts that roll across the scene from left to right."""
        t = self.t
        gust = max(0.0, math.sin(t * 0.42 - x * 0.004)) ** 3
        return 0.3 * math.sin(t * 1.2) + 0.22 * math.sin(t * 2.0 + x * 0.01) + 1.3 * gust

    def _place_live(self, dt: float = 0.0) -> None:
        cv, t = self.cv, self.t
        w = max(self._w, 80)
        for cl in self.clouds:
            cl["x"] = (cl["x"] + cl["speed"] * dt) % (w + cl["w"] * 2)
            x0, cw, y = cl["x"] - cl["w"], cl["w"], cl["y"]
            for cid, box in zip(cl["ids"], ((x0, y, x0 + cw * 0.6, y + cw * 0.2), (x0 + cw * 0.25, y - cw * 0.12, x0 + cw * 0.8, y + cw * 0.18),
                                            (x0 + cw * 0.5, y + cw * 0.02, x0 + cw, y + cw * 0.2))):
                cv.coords(cid, *box)
        night = self.mode == "dark"
        for s in self.stars:
            if night:
                v = 0.5 + 0.5 * math.sin(t * s["sp"] + s["ph"])
                cv.itemconfigure(s["id"], state="normal", fill=_hex(_mix((30, 40, 72), SCENES["dark"]["star"], v * self._blend)))
            else:
                cv.itemconfigure(s["id"], state="hidden")
        for g in self.glints:                                     # shimmer: each streak breathes and drifts slightly
            k = 0.55 + 0.45 * math.sin(t * 2.3 + g["ph"])
            off = 4 * math.sin(t * 0.9 + g["ph"] * 2)
            half = g["half"] * k
            cv.coords(g["id"], g["x"] - half + off, g["y"], g["x"] + half + off, g["y"])
        for tr in self.trees:
            sway = self._wind(tr["x"]) * tr["stiff"] * tr["h"] * 0.045 + 0.5 * math.sin(t * 1.6 + tr["ph"])
            x, y, h, hw = tr["x"], tr["y"], tr["h"], tr["w"] / 2
            tw = max(2.0, hw * (0.18 if tr["kind"] == "round" else 0.25))
            cv.coords(tr["trunk"], x - tw, y, x + tw, y, x + tw * 0.6 + sway * 0.2, y - h * 0.4, x - tw * 0.6 + sway * 0.2, y - h * 0.4)
            body, lit = [], []
            if tr["kind"] == "cypress":                           # tall flame shape, the tip bends most
                for k in range(16):
                    a = k / 16 * 2 * math.pi
                    py = y - h * 0.55 - math.cos(a) * h * 0.47
                    lift = max(0.0, (y - py) / h)
                    px = x + math.sin(a) * hw * (0.55 + 0.45 * math.sin((1 - lift) * math.pi * 0.9)) + sway * lift ** 1.5
                    body += [px, py]
                    if math.sin(a) > -0.1:                        # lit half towards the moon/sun (right)
                        lit += [px - hw * 0.1, py]
                lit += [x + sway * 0.4, y - h * 0.12]
            else:                                                 # round, lumpy crown
                for k in range(14):
                    a = k / 14 * 2 * math.pi
                    rr = 1 + 0.13 * math.sin(a * 3 + tr["ph"])
                    px = x + math.cos(a) * hw * rr
                    py = y - h * 0.66 + math.sin(a) * h * 0.3 * rr
                    lift = max(0.0, (y - py) / h)
                    body += [px + sway * lift, py]
                    if -1.2 < a - 2 * math.pi * (a > math.pi) < 0.9:
                        lit += [px + sway * lift - hw * 0.12 * math.cos(a), py + h * 0.03]
                if len(lit) < 6:
                    lit = body[:6]
            cv.coords(tr["crown"], *body)
            cv.coords(tr["lit"], *(lit if len(lit) >= 6 else body[:6]))
        for bl in self.blades:
            bend = self._wind(bl["x"]) * bl["h"] * 0.3 + 1.1 * math.sin(t * 2.3 + bl["ph"])
            x, y, h = bl["x"], bl["y"], bl["h"]
            cv.coords(bl["id"], x, y, x + bend * 0.35, y - h * 0.55, x + bend, y - h)

    def _recolor_live(self) -> None:
        c = self._colors()
        for tr in self.trees:
            self.cv.itemconfigure(tr["crown"], fill=_hex(c["tree"]))
            self.cv.itemconfigure(tr["lit"], fill=_hex(c["tree_lit"]))
            self.cv.itemconfigure(tr["trunk"], fill=_hex(c["trunk"]))
        for cl in self.clouds:
            for cid in cl["ids"]:
                self.cv.itemconfigure(cid, fill=_hex(c["cloud"]))
        for g in self.glints:
            self.cv.itemconfigure(g["id"], fill=_hex(c["path"]))
        for bl in self.blades:
            self.cv.itemconfigure(bl["id"], fill=_hex(_mix(c["grass"], c["grass_tip"], bl["t"])))

    def _fade_step(self, i: int) -> None:
        if i >= len(self._fade):
            self._photo = ImageTk.PhotoImage(self._static)
            self.cv.itemconfigure(self._img_id, image=self._photo)
            self._fade, self._blend, self._from_mode = [], 1.0, self.mode
            self._recolor_live()
            return
        self.cv.itemconfigure(self._img_id, image=self._fade[i])
        self._blend = (i + 1) / len(self._fade)
        self._recolor_live()
        self.cv.after(45, lambda: self._fade_step(i + 1))

    def _tick(self) -> None:
        try:
            visible = self.cv.winfo_viewable()
        except tk.TclError:
            return
        if visible and self.animate:
            self.t += 1 / FPS
            self._place_live(1 / FPS)
        self._job = self.cv.after(int(1000 / FPS), self._tick)
