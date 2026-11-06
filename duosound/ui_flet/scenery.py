"""Animated scenery behind the Flet window: a moonlit night (dark) or a sunny day (light).

Same composition and palettes as duosound/ui/scenery.py (tkinter): sky gradient, moon with speckles + glow / sun with rays,
distant hills, a lake with a shimmering light path, a small house on a left hill (windows lit at night), Italian cypresses and
round two-tone trees, a meadow of grass tufts, drifting clouds, twinkling stars.

Kept calm (measured in the prototype: a Python-side canvas diff costs ~75 us per changed shape, a client-side animation makes
Flutter redraw at 60 fps, both far too much next to a playing movie):
- everything static (sky, moon/sun, hills, lake, house, grain) is ONE picture per theme, painted with PIL;
- trees and grass are static canvases in Containers; the wind is a new rotation angle sent ~12 times a second (no implicit
  animation, so the client redraws only 12 fps);
- stars, clouds and water glints are ~70 shapes on one small canvas;
- the loop FREEZES (last frame stays, zero work) while `freeze(reason)` has any reason: a movie is playing, the window has been
  away for a while, or Windows animations are off.
Only the visible theme layer exists; the other one is built when the theme switches and crossfades in with animated opacity."""
from __future__ import annotations

import asyncio
import ctypes
import io
import math
import random
import time

import flet as ft
import flet.canvas as cv
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .. import log_setup
from . import tokens as T

log = log_setup.get("scenery")

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
SWAP_S = 0.9                                 # theme crossfade (a calmer 0.9 s; the client animates it)
TREES = ((0.03, "cypress", 1.1), (0.075, "round", 0.9), (0.24, "cypress", 1.25), (0.29, "cypress", 0.95),
         (0.36, "round", 1.05), (0.44, "cypress", 0.8), (0.97, "round", 0.8))


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


def _mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _rgba(c, a: float) -> str:
    return ft.Colors.with_opacity(max(0.0, min(1.0, a)), _hex(c))


class Layout:
    """Where things are, as fractions of the window, so painted and live parts line up at any size."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.horizon = h * 0.62
        self.sun = (w * 0.80, h * 0.20, max(24, min(w, h) * 0.07))
        self.meadow = h * 0.90

    def hill(self, x: float) -> float:
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
        for _ in range(int(r * r / 5)):
            a, rr = rnd.uniform(0, 6.283), r * math.sqrt(rnd.random()) * 0.96
            d.point((cx + rr * math.cos(a), cy + rr * math.sin(a)), fill=c["spot"])
    else:
        for k in range(16):
            a = k * math.pi / 8
            d.line([(cx + math.cos(a) * r * 1.3, cy + math.sin(a) * r * 1.3),
                    (cx + math.cos(a) * r * 1.65, cy + math.sin(a) * r * 1.65)], fill=c["body"], width=max(2, int(r / 8)))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c["body"])
    for col, base, amp, seed in ((c["hill_far"], L.horizon - h * 0.05, h * 0.05, 3), (c["hill_mid"], L.horizon - h * 0.01, h * 0.03, 9)):
        rr = random.Random(seed)
        ph = [rr.uniform(0, 6.3) for _ in range(3)]
        pts = [(x, base - amp * (math.sin(x / w * 3.1 + ph[0]) + 0.5 * math.sin(x / w * 7.3 + ph[1]) + 0.25 * math.sin(x / w * 13 + ph[2])))
               for x in range(0, w + 10, 10)]
        d.polygon(pts + [(w, L.horizon), (0, L.horizon)], fill=col)
    d.rectangle([0, L.horizon, w, h], fill=c["water"])
    for k in range(18):
        y = L.horizon + (h - L.horizon) * (k / 18) ** 1.6 + 3
        x0 = rnd.uniform(0, w * 0.6)
        d.line([(x0, y), (x0 + rnd.uniform(w * 0.1, w * 0.4), y)], fill=c["water_line"], width=1)
    hill = [(x, L.hill(x)) for x in range(0, int(w * 0.56), 6)]
    d.polygon(hill + [(w * 0.56, h), (0, h)], fill=c["ground"])
    hx, hy = w * 0.13, L.hill(w * 0.13)
    hw, hh = w * 0.075, h * 0.07
    d.rectangle([hx, hy - hh, hx + hw, hy + 4], fill=c["house"])
    d.polygon([(hx - hw * 0.08, hy - hh), (hx + hw / 2, hy - hh * 1.55), (hx + hw * 1.08, hy - hh)], fill=c["roof"])
    for i in range(3):
        wx = hx + hw * (0.14 + i * 0.3)
        d.rectangle([wx, hy - hh * 0.72, wx + hw * 0.15, hy - hh * 0.36], fill=c["window"])
    d.rectangle([0, L.meadow, w, h], fill=c["ground"])
    noise = np.random.default_rng(5).normal(0, 8 if mode == "dark" else 5, (h, w, 1))
    arr = np.clip(np.asarray(img, float) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def prepare(mode: str, w: int, h: int) -> bytes:
    """The heavy part of a layer (PIL painting + JPEG): safe to run in a worker thread."""
    buf = io.BytesIO()
    paint_static(mode, w, h).save(buf, "JPEG", quality=86)
    return buf.getvalue()


# ------------------------------------------------------------------------------------------------ shapes
def _fill(color: str) -> ft.Paint:
    return ft.Paint(color=color, style=ft.PaintingStyle.FILL)


def _stroke(color: str, width: float) -> ft.Paint:
    return ft.Paint(color=color, style=ft.PaintingStyle.STROKE, stroke_width=width, stroke_cap=ft.StrokeCap.ROUND)


def _smooth_closed(pts):
    """Closed smooth blob through the points (quadratic curves between edge midpoints)."""
    n = len(pts)
    mids = [((pts[i][0] + pts[(i + 1) % n][0]) / 2, (pts[i][1] + pts[(i + 1) % n][1]) / 2) for i in range(n)]
    els = [cv.Path.MoveTo(*mids[-1])]
    for i in range(n):
        els.append(cv.Path.QuadraticTo(pts[i][0], pts[i][1], mids[i][0], mids[i][1]))
    els.append(cv.Path.Close())
    return els


def wind(t: float, x: float) -> float:
    """Gusting wind: a slow sway plus gusts that roll across the scene from left to right."""
    gust = max(0.0, math.sin(t * 0.42 - x * 0.004)) ** 3
    return 0.3 * math.sin(t * 1.2) + 0.22 * math.sin(t * 2.0 + x * 0.01) + 1.3 * gust


def _make_tree(c, L, h, fx, kind, scale, rnd):
    x = fx * L.w
    base = L.hill(x) + (3 if fx < 0.5 else -2)
    th = h * 0.2 * scale
    tw = th * (0.22 if kind == "cypress" else 0.5)
    hw = tw / 2
    W, H = hw * 2.5 + 10, th * 1.1
    cx = W / 2
    ph = rnd.uniform(0, 6.28)

    def loc(px, py):
        return (cx + px - x, H + py - base)

    body, lit = [], []
    if kind == "cypress":
        for k in range(16):
            a = k / 16 * 2 * math.pi
            py = base - th * 0.55 - math.cos(a) * th * 0.47
            lift = max(0.0, (base - py) / th)
            px = x + math.sin(a) * hw * (0.55 + 0.45 * math.sin((1 - lift) * math.pi * 0.9))
            body.append(loc(px, py))
            if math.sin(a) > -0.1:
                lit.append(loc(px - hw * 0.1, py))
        lit.append(loc(x, base - th * 0.12))
    else:
        for k in range(14):
            a = k / 14 * 2 * math.pi
            rr = 1 + 0.13 * math.sin(a * 3 + ph)
            px = x + math.cos(a) * hw * rr
            py = base - th * 0.66 + math.sin(a) * th * 0.3 * rr
            body.append(loc(px, py))
            if -1.2 < a - 2 * math.pi * (a > math.pi) < 0.9:
                lit.append(loc(px - hw * 0.12 * math.cos(a), py + th * 0.03))
        if len(lit) < 3:
            lit = body[:3]
    tt = max(2.0, hw * (0.18 if kind == "round" else 0.25))
    trunk = cv.Path([cv.Path.MoveTo(cx - tt, H), cv.Path.LineTo(cx + tt, H), cv.Path.LineTo(cx + tt * 0.6, H - th * 0.4),
                     cv.Path.LineTo(cx - tt * 0.6, H - th * 0.4), cv.Path.Close()], paint=_fill(_hex(c["trunk"])))
    crown = cv.Path(_smooth_closed(body), paint=_fill(_hex(c["tree"])))
    litp = cv.Path(_smooth_closed(lit), paint=_fill(_hex(c["tree_lit"])))
    pivot = ft.Alignment(0, ((H - th * 0.4) / H) * 2 - 1)               # the crown bends where it meets the trunk
    crown_box = ft.Container(cv.Canvas([crown, litp], width=W, height=H), width=W, height=H, rotate=ft.Rotate(0, alignment=pivot))
    outer = ft.Container(ft.Stack([cv.Canvas([trunk], width=W, height=H), crown_box], width=W, height=H), width=W, height=H,
                         left=x - cx, top=base - H)
    return {"outer": outer, "crown": crown_box, "x": x, "ph": ph, "stiff": rnd.uniform(0.75, 1.2), "pivot": pivot}


class Layer:
    """One complete scene (night or day) as controls: picture + live shapes."""

    def __init__(self, mode: str, w: int, h: int, jpeg: bytes, opacity: float = 1.0):
        self.mode, self.w, self.h = mode, w, h
        c = SCENES[mode]
        L = Layout(w, h)
        rnd = random.Random(42)
        img = ft.Image(src=jpeg, fit=ft.BoxFit.FILL, expand=True, gapless_playback=True)
        shapes = []
        self.clouds = []
        for _ in range(3):
            cw = rnd.uniform(0.12, 0.2) * w
            ov = [cv.Oval(0, 0, 1, 1, paint=_fill(_hex(c["cloud"]))) for _ in range(3)]
            shapes += ov
            self.clouds.append({"x": rnd.uniform(0, w), "y": rnd.uniform(0.07, 0.3) * h, "w": cw, "ov": ov, "speed": rnd.uniform(3, 7)})
        self.stars = []
        if mode == "dark":
            for _ in range(16):
                s = cv.Circle(rnd.uniform(0, w * 0.7), rnd.uniform(0, L.horizon * 0.7), 1.3, paint=_fill(_rgba(c["star"], 0.3)))
                shapes.append(s)
                self.stars.append({"s": s, "ph": rnd.uniform(0, 6.28), "sp": rnd.uniform(0.8, 2.2)})
        self.glints = []
        sx = L.sun[0]
        for k in range(22):
            f = (k / 22) ** 1.3
            y = L.horizon + 6 + (h * 0.88 - L.horizon) * f
            half = L.sun[2] * (0.35 + 1.4 * f)
            ln = cv.Line(sx - half, y, sx + half, y, paint=_stroke(_hex(c["path"]), max(1, 1 + f * 3)))
            shapes.append(ln)
            self.glints.append({"s": ln, "x": sx, "half": half, "ph": rnd.uniform(0, 6.28)})
        self.fast = cv.Canvas(shapes, expand=True)
        self.trees = [_make_tree(c, L, h, fx, kind, sc, rnd) for fx, kind, sc in TREES]
        self.tufts = []
        n_t = max(8, int(w / 46))
        boxes = []
        for i in range(n_t):
            x = (i + 0.5) * w / n_t + rnd.uniform(-3, 3)
            bh = rnd.uniform(0.045, 0.085) * h
            W, H = 56.0, bh + 4
            y = L.meadow + rnd.uniform(0, h * 0.08)
            blades = []
            for _b in range(9):
                bx = W / 2 + rnd.uniform(-20, 20)
                lean = rnd.uniform(-5, 5)
                hh = bh * rnd.uniform(0.6, 1.0)
                col = _hex(_mix(c["grass"], c["grass_tip"], rnd.uniform(0, 0.6)))
                blades.append(cv.Path([cv.Path.MoveTo(bx, H), cv.Path.QuadraticTo(bx + lean * 0.3, H - hh * 0.6, bx + lean, H - hh)],
                                      paint=_stroke(col, rnd.choice((1.5, 2, 2.5, 3)))))
            box = ft.Container(cv.Canvas(blades, width=W, height=H), width=W, height=H, left=x - W / 2, top=y - H,
                               rotate=ft.Rotate(0, alignment=ft.Alignment.BOTTOM_CENTER))
            self.tufts.append({"box": box, "x": x, "ph": rnd.uniform(0, 6.28)})
            boxes.append(box)
        art = ft.Stack([img, self.fast] + [t["outer"] for t in self.trees] + boxes, expand=True)
        self.root = ft.Container(art, expand=True, opacity=opacity,
                                 animate_opacity=ft.Animation(int(SWAP_S * 1000), ft.AnimationCurve.EASE_IN_OUT))

    def wind_controls(self, t: float) -> list:
        """New (discrete) rotation angles for trees and tufts. Returns only the controls whose angle really changed
        (every patch costs Python time; in calm air most of them stay put)."""
        out = []
        for tr in self.trees:
            ang = 0.085 * wind(t, tr["x"]) * tr["stiff"] + 0.012 * math.sin(t * 1.6 + tr["ph"])
            if abs(ang - tr.get("a", 9.0)) > 0.002:
                tr["a"] = ang
                tr["crown"].rotate = ft.Rotate(ang, alignment=tr["pivot"])
                out.append(tr["crown"])
        for tf in self.tufts:
            ang = 0.2 * wind(t, tf["x"]) + 0.05 * math.sin(t * 2.3 + tf["ph"])
            if abs(ang - tf.get("a", 9.0)) > 0.003:
                tf["a"] = ang
                tf["box"].rotate = ft.Rotate(ang, alignment=ft.Alignment.BOTTOM_CENTER)
                out.append(tf["box"])
        return out

    def fast_step(self, t: float, dt: float) -> None:
        w = max(self.w, 80)
        for cl in self.clouds:
            cl["x"] = (cl["x"] + cl["speed"] * dt) % (w + cl["w"] * 2)
            x0, cw, y = cl["x"] - cl["w"], cl["w"], cl["y"]
            for o, box in zip(cl["ov"], ((x0, y, cw * 0.6, cw * 0.2), (x0 + cw * 0.25, y - cw * 0.12, cw * 0.55, cw * 0.30),
                                         (x0 + cw * 0.5, y + cw * 0.02, cw * 0.5, cw * 0.18))):
                o.x, o.y, o.width, o.height = box
        for s in self.stars:
            s["s"].paint.color = _rgba(SCENES["dark"]["star"], 0.15 + 0.85 * (0.5 + 0.5 * math.sin(t * s["sp"] + s["ph"])))
        for g in self.glints:
            k = 0.55 + 0.45 * math.sin(t * 2.3 + g["ph"])
            off = 4 * math.sin(t * 0.9 + g["ph"] * 2)
            half = g["half"] * k
            g["s"].x1, g["s"].x2 = g["x"] - half + off, g["x"] + half + off


class Scenery:
    """The two theme layers, the crossfade between them and the (freezable) animation loop.

    Put `.control` at the bottom of a Stack. `await set_mode("dark"|"light")` crossfades; `freeze(reason, True/False)` stops and
    resumes the motion; `await resize(w, h)` repaints for a new window size."""

    def __init__(self, page: ft.Page, mode: str, w: int, h: int):
        self.page = page
        self.mode = mode if mode in SCENES else "dark"
        self.w, self.h = max(w, 300), max(h, 300)
        self.layers: dict[str, Layer] = {}
        self.slots = {"dark": ft.Container(expand=True), "light": ft.Container(expand=True)}
        self.control = ft.Stack([self.slots["dark"], self.slots["light"]], expand=True)
        self.t = 0.0
        self._gen = 0
        self._freeze: set[str] = set()
        self._go = asyncio.Event()
        self._go.set()
        self._task: asyncio.Task | None = None
        self._build(self.mode, prepare(self.mode, self.w, self.h), 1.0 if self.mode == "dark" else 1.0)
        self.slots["light" if self.mode == "dark" else "dark"].visible = False

    # ---- building
    def _build(self, mode: str, jpeg: bytes, opacity: float) -> Layer:
        lay = Layer(mode, self.w, self.h, jpeg, opacity)
        self.layers[mode] = lay
        self.control.controls[0 if mode == "dark" else 1] = lay.root
        self.slots[mode] = lay.root
        return lay

    def _visible(self) -> list[Layer]:
        return [lay for m, lay in self.layers.items() if lay.root.visible]

    async def _ensure(self, mode: str) -> Layer:
        lay = self.layers.get(mode)
        if lay is not None and (lay.w, lay.h) == (self.w, self.h):
            return lay
        jpeg = await asyncio.to_thread(prepare, mode, self.w, self.h)
        return self._build(mode, jpeg, 0.0 if mode == "light" else 1.0)

    # ---- theme
    async def set_mode(self, mode: str) -> None:
        if mode not in SCENES or mode == self.mode:
            return
        self._gen += 1
        gen = self._gen
        self.mode = mode
        new = await self._ensure(mode)
        if gen != self._gen:
            return
        dark, light = self.layers.get("dark"), self.layers.get("light")
        if dark is None or light is None:
            return
        dark.root.visible = light.root.visible = True
        dark.root.opacity = 1.0
        self.page.update(self.control)                              # attaches a freshly built layer
        await asyncio.sleep(0.15)                                   # let Flutter build the layer that was hidden
        light.root.opacity = 1.0 if mode == "light" else 0.0        # the client animates the crossfade
        self.page.update(light.root)
        await asyncio.sleep(SWAP_S + 0.1)
        if gen != self._gen:
            return
        (dark if mode == "light" else light).root.visible = False   # the covered layer costs nothing
        self.page.update(dark.root, light.root)

    async def resize(self, w: int, h: int) -> None:
        w, h = max(int(w), 300), max(int(h), 300)
        if (w, h) == (self.w, self.h):
            return
        self.w, self.h = w, h
        self._gen += 1
        for m in list(self.layers):
            if m != self.mode:
                del self.layers[m]                                  # rebuilt when the theme next switches
        self.slots["light" if self.mode == "dark" else "dark"] = ft.Container(expand=True, visible=False)
        self.control.controls[1 if self.mode == "dark" else 0] = self.slots["light" if self.mode == "dark" else "dark"]
        jpeg = await asyncio.to_thread(prepare, self.mode, w, h)
        lay = self._build(self.mode, jpeg, 1.0 if self.mode == "dark" else 1.0)
        lay.root.opacity = 1.0
        self.page.update(self.control)

    # ---- motion
    def freeze(self, reason: str, on: bool = True) -> None:
        (self._freeze.add if on else self._freeze.discard)(reason)
        if self._freeze:
            self._go.clear()
        else:
            self._go.set()

    @property
    def frozen(self) -> bool:
        return bool(self._freeze)

    def pause(self) -> None:
        self.freeze("pause", True)

    def resume(self) -> None:
        self.freeze("pause", False)

    def start(self) -> None:
        if self._task is None:
            self._task = self.page.run_task(self._loop)

    async def _loop(self) -> None:
        interval = 1.0 / T.FPS
        last = time.perf_counter()
        while True:
            await self._go.wait()                                    # blocks (no work at all) while frozen
            now = time.perf_counter()
            dt = min(now - last, 0.25)
            last = now
            self.t += dt
            vis = self._visible()
            try:
                ctrls = []
                for lay in vis:
                    ctrls += lay.wind_controls(self.t)
                    lay.fast_step(self.t, dt)
                    ctrls.append(lay.fast)
                if ctrls:
                    self.page.update(*ctrls)
            except Exception:  # noqa: BLE001 - window closing, or a layer being replaced
                log.debug("scenery frame skipped", exc_info=True)
                await asyncio.sleep(0.5)
            await asyncio.sleep(max(0.0, interval - (time.perf_counter() - now)))
            if self._freeze:
                last = time.perf_counter()
