"""
DuoSound Flet prototype
=======================
Glassmorphism UI (blurred translucent panels) over an animated moonlit-night / sunny-day scenery, to compare with the tkinter UI.

Run:  venv\\Scripts\\python proto.py [--light] [--toggle-after SECONDS] [--fps N]
"""
from __future__ import annotations

import argparse
import asyncio
import io
import os
import math
import random
import time

import flet as ft
import flet.canvas as cv
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# --------------------------------------------------------------------------------------------- palettes
# Scene palettes: copied from duosound/ui/scenery.py
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

# UI tokens (from duosound/ui/theme.py) + glass tints
UI = {
    "dark": dict(TEXT=(244, 234, 223), TEXT_2=(201, 184, 168), TEXT_3=(190, 176, 163), OK=(108, 203, 148),
                 LINK=(242, 140, 46), FIELD=(58, 48, 39), FIELD_A=0.55, GLASS=(33, 27, 22), GLASS_A=0.62,
                 BORDER=(255, 255, 255), BORDER_A=0.18, ROW=(58, 48, 39), ROW_A=0.45, SHADOW_A=0.35),
    "light": dict(TEXT=(42, 31, 23), TEXT_2=(84, 68, 58), TEXT_3=(84, 68, 58), OK=(20, 104, 59),
                  LINK=(150, 71, 0), FIELD=(255, 255, 255), FIELD_A=0.7, GLASS=(255, 255, 255), GLASS_A=0.62,
                  BORDER=(255, 255, 255), BORDER_A=0.85, ROW=(255, 255, 255), ROW_A=0.45, SHADOW_A=0.15),
}
ACCENT, ON_ACCENT = "#F28C2E", "#1B1007"
BLUR = float(os.environ.get('DS_BLUR', 14))
SWAP_SECONDS = 1.0
FONT = "Segoe UI"


def hexc(c) -> str:
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in c)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def rgba(c, a: float) -> str:
    """Flet colour with opacity: '#rrggbb,alpha' (what ft.Colors.with_opacity returns)."""
    return ft.Colors.with_opacity(max(0.0, min(1.0, a)), hexc(c))


def ui_tok(name: str, b: float):
    return mix(UI["dark"][name], UI["light"][name], b)


def ui_num(name: str, b: float) -> float:
    return UI["dark"][name] + (UI["light"][name] - UI["dark"][name]) * b


# --------------------------------------------------------------------------------------------- static scene (PIL)
class Layout:
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


def jpeg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


# --------------------------------------------------------------------------------------------- live scene
# Python-side per-frame canvas diffs cost ~75 us per changed shape in Flet (measured: ~50 ms for 650 shapes), so only the
# cheap, small things (stars, glints, clouds: ~70 shapes) go through a Canvas at ~15 fps. Trees and grass are STATIC canvases
# wrapped in Containers with an implicit rotation animation (client-side): Python sends one new target angle every 0.35 s.
WIND_EVERY = float(os.environ.get('DS_WIND_EVERY', 1 / 12))
TREES = ((0.03, "cypress", 1.1), (0.075, "round", 0.9), (0.24, "cypress", 1.25), (0.29, "cypress", 0.95),
         (0.36, "round", 1.05), (0.44, "cypress", 0.8), (0.97, "round", 0.8))


def fill(color: str) -> ft.Paint:
    return ft.Paint(color=color, style=ft.PaintingStyle.FILL)


def stroke(color: str, width: float) -> ft.Paint:
    return ft.Paint(color=color, style=ft.PaintingStyle.STROKE, stroke_width=width, stroke_cap=ft.StrokeCap.ROUND)


def smooth_closed(pts):
    """Closed smooth blob through the points (quadratic curves between edge midpoints)."""
    n = len(pts)
    mids = [((pts[i][0] + pts[(i + 1) % n][0]) / 2, (pts[i][1] + pts[(i + 1) % n][1]) / 2) for i in range(n)]
    els = [cv.Path.MoveTo(*mids[-1])]
    for i in range(n):
        els.append(cv.Path.QuadraticTo(pts[i][0], pts[i][1], mids[i][0], mids[i][1]))
    els.append(cv.Path.Close())
    return els


def wind(t: float, x: float) -> float:
    """Gusting wind: a slow sway plus gusts that roll across the scene from left to right (same as the tkinter scene)."""
    gust = max(0.0, math.sin(t * 0.42 - x * 0.004)) ** 3
    return 0.3 * math.sin(t * 1.2) + 0.22 * math.sin(t * 2.0 + x * 0.01) + 1.3 * gust


# Discrete updates (no implicit animation): an implicit rotation animation makes the Flutter client redraw at 60 fps
# (~100 % of a core with the blur panels); sending a new angle at ~12 Hz keeps the client at ~12 fps. DS_IMPLICIT=1 to compare.
SWAY = ft.Animation(int(WIND_EVERY * 1000 * 1.15), ft.AnimationCurve.LINEAR) if os.environ.get('DS_IMPLICIT') else None


def make_tree(c, L, h, fx, kind, scale, rnd):
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
                     cv.Path.LineTo(cx - tt * 0.6, H - th * 0.4), cv.Path.Close()], paint=fill(hexc(c["trunk"])))
    crown = cv.Path(smooth_closed(body), paint=fill(hexc(c["tree"])))
    litp = cv.Path(smooth_closed(lit), paint=fill(hexc(c["tree_lit"])))
    pivot_crown = ft.Alignment(0, ((H - th * 0.4) / H) * 2 - 1)           # bends where the crown meets the trunk
    crown_box = ft.Container(cv.Canvas([crown, litp], width=W, height=H), width=W, height=H,
                             rotate=ft.Rotate(0, alignment=pivot_crown), animate_rotation=SWAY)
    outer = ft.Container(ft.Stack([cv.Canvas([trunk], width=W, height=H), crown_box], width=W, height=H), width=W, height=H,
                         left=x - cx, top=base - H)
    return {"outer": outer, "crown": crown_box, "x": x, "ph": ph, "stiff": rnd.uniform(0.75, 1.2), "pc": pivot_crown}


class Layer:
    """One complete scene (night or day): painted art + live shapes. Two of these are crossfaded with animated opacity."""

    def __init__(self, mode: str, w: int, h: int, opacity: float):
        self.mode, self.w, self.h = mode, w, h
        c = SCENES[mode]
        L = Layout(w, h)
        rnd = random.Random(42)
        img = ft.Image(src=jpeg_bytes(paint_static(mode, w, h)), fit=ft.BoxFit.FILL, expand=True, gapless_playback=True)
        # fast canvas: clouds, stars, water glints
        shapes = []
        self.clouds = []
        for _ in range(3):
            cw = rnd.uniform(0.12, 0.2) * w
            ov = [cv.Oval(0, 0, 1, 1, paint=fill(hexc(c["cloud"]))) for _ in range(3)]
            shapes += ov
            self.clouds.append({"x": rnd.uniform(0, w), "y": rnd.uniform(0.07, 0.3) * h, "w": cw, "ov": ov, "speed": rnd.uniform(3, 7)})
        self.stars = []
        if mode == "dark":
            for _ in range(16):
                s = cv.Circle(rnd.uniform(0, w * 0.7), rnd.uniform(0, L.horizon * 0.7), 1.3, paint=fill(rgba(c["star"], 0.3)))
                shapes.append(s)
                self.stars.append({"s": s, "ph": rnd.uniform(0, 6.28), "sp": rnd.uniform(0.8, 2.2)})
        self.glints = []
        sx = L.sun[0]
        for k in range(22):
            f = (k / 22) ** 1.3
            y = L.horizon + 6 + (h * 0.88 - L.horizon) * f
            half = L.sun[2] * (0.35 + 1.4 * f)
            ln = cv.Line(sx - half, y, sx + half, y, paint=stroke(hexc(c["path"]), max(1, 1 + f * 3)))
            shapes.append(ln)
            self.glints.append({"s": ln, "x": sx, "half": half, "ph": rnd.uniform(0, 6.28)})
        self.fast = cv.Canvas(shapes, expand=True)
        # trees (static canvases in rotating containers)
        self.trees = [make_tree(c, L, h, fx, kind, sc, rnd) for fx, kind, sc in TREES]
        # grass: tufts of 9 blades, each tuft one rotating container
        self.tufts = []
        n_t = max(8, int(w / 46))
        ctrl = []
        for i in range(n_t):
            x = (i + 0.5) * w / n_t + rnd.uniform(-3, 3)
            bh = rnd.uniform(0.045, 0.085) * h
            W, H = 56.0, bh + 4
            y = L.meadow + rnd.uniform(0, h * 0.08)
            blades = []
            for _ in range(9):
                bx = W / 2 + rnd.uniform(-20, 20)
                lean = rnd.uniform(-5, 5)
                hh = bh * rnd.uniform(0.6, 1.0)
                col = hexc(mix(c["grass"], c["grass_tip"], rnd.uniform(0, 0.6)))
                blades.append(cv.Path([cv.Path.MoveTo(bx, H), cv.Path.QuadraticTo(bx + lean * 0.3, H - hh * 0.6, bx + lean, H - hh)],
                                      paint=stroke(col, rnd.choice((1.5, 2, 2.5, 3)))))
            box = ft.Container(cv.Canvas(blades, width=W, height=H), width=W, height=H, left=x - W / 2, top=y - H,
                               rotate=ft.Rotate(0, alignment=ft.Alignment.BOTTOM_CENTER), animate_rotation=SWAY)
            self.tufts.append({"box": box, "x": x, "ph": rnd.uniform(0, 6.28)})
            ctrl.append(box)
        art = ft.Stack([img, self.fast] + [t["outer"] for t in self.trees] + ctrl, expand=True)
        self.root = ft.Container(art, expand=True, opacity=opacity, animate_opacity=ft.Animation(int(SWAP_SECONDS * 1000), ft.AnimationCurve.EASE_IN_OUT))

    def set_wind(self, t: float) -> list:
        """New target angles (clockwise rad) for trees and tufts; Flutter animates towards them. Returns the controls to patch."""
        out = []
        for tr in self.trees:
            wv = wind(t, tr["x"]) * tr["stiff"]
            tr["crown"].rotate = ft.Rotate(0.085 * wv + 0.012 * math.sin(t * 1.6 + tr["ph"]), alignment=tr["pc"])
            out.append(tr["crown"])
        for tf in self.tufts:
            ang = 0.2 * wind(t, tf["x"]) + 0.05 * math.sin(t * 2.3 + tf["ph"])
            tf["box"].rotate = ft.Rotate(ang, alignment=ft.Alignment.BOTTOM_CENTER)
            out.append(tf["box"])
        return out

    def fast_step(self, t: float, dt: float):
        w = max(self.w, 80)
        for cl in self.clouds:
            cl["x"] = (cl["x"] + cl["speed"] * dt) % (w + cl["w"] * 2)
            x0, cw, y = cl["x"] - cl["w"], cl["w"], cl["y"]
            for o, box in zip(cl["ov"], ((x0, y, cw * 0.6, cw * 0.2), (x0 + cw * 0.25, y - cw * 0.12, cw * 0.55, cw * 0.30),
                                         (x0 + cw * 0.5, y + cw * 0.02, cw * 0.5, cw * 0.18))):
                o.x, o.y, o.width, o.height = box
        for s in self.stars:
            s["s"].paint.color = rgba(SCENES["dark"]["star"], 0.15 + 0.85 * (0.5 + 0.5 * math.sin(t * s["sp"] + s["ph"])))
        for g in self.glints:
            k = 0.55 + 0.45 * math.sin(t * 2.3 + g["ph"])
            off = 4 * math.sin(t * 0.9 + g["ph"] * 2)
            half = g["half"] * k
            g["s"].x1, g["s"].x2 = g["x"] - half + off, g["x"] + half + off


# --------------------------------------------------------------------------------------------- the app
COLUMN_W = 720


def main(page: ft.Page):
    args = ARGS
    page.title = "DuoSound"
    page.padding = 0
    page.spacing = 0
    page.bgcolor = hexc(SCENES["dark"]["sky_top"])
    page.theme = ft.Theme(font_family=FONT)
    page.window.width, page.window.height = 1000, 700
    page.window.min_width, page.window.min_height = 760, 560
    page.window.resizable = True

    start_b = 1.0 if args.light else 0.0
    state = {"target": start_b, "blend": start_b, "w": 1000, "h": 700, "painted": None}

    # ---- registry of things whose colour follows the theme (updated each frame while the swap runs)
    setters: list = []

    def reg(fn):
        setters.append(fn)
        return fn

    glass_boxes: list[ft.Container] = []
    SWAP = ft.Animation(int(SWAP_SECONDS * 1000), ft.AnimationCurve.EASE_IN_OUT)

    strength: dict[int, float] = {}                      # per-panel tint multiplier (small pills sit on busy grass: more opaque)

    def glass_deco(box: ft.Container, b: float):
        box.bgcolor = rgba(ui_tok("GLASS", b), min(1.0, ui_num("GLASS_A", b) * strength.get(id(box), 1.0)))
        box.border = ft.Border.all(1, rgba(ui_tok("BORDER", b), ui_num("BORDER_A", b)))
        box.shadow = ft.BoxShadow(blur_radius=28, offset=ft.Offset(0, 8), color=rgba((0, 0, 0), ui_num("SHADOW_A", b)))

    def glass(content, radius=16, padding=18, boost=1.0, **kw) -> ft.Container:
        """Frosted panel: backdrop blur + translucent tint + 1px light border + soft shadow. Tint/border animate client-side."""
        box = ft.Container(content=content, blur=BLUR, border_radius=radius, padding=padding, animate=SWAP, **kw)
        strength[id(box)] = boost
        glass_deco(box, state["blend"])
        glass_boxes.append(box)
        return box

    def text(value, size=14, weight=None, tok="TEXT", **kw) -> ft.Text:
        t = ft.Text(value, size=size, weight=weight, **kw)
        reg(lambda b, t=t, tok=tok: setattr(t, "color", hexc(ui_tok(tok, b))))
        return t

    def icon(name, size=20, tok="TEXT_2") -> ft.Icon:
        i = ft.Icon(name, size=size)
        reg(lambda b, i=i, tok=tok: setattr(i, "color", hexc(ui_tok(tok, b))))
        return i

    def icon_button(name, tooltip, on_click=None, size=20) -> ft.IconButton:
        ib = ft.IconButton(icon=name, icon_size=size, tooltip=tooltip, on_click=on_click)
        reg(lambda b, ib=ib: setattr(ib, "icon_color", hexc(ui_tok("TEXT", b))))
        return ib

    # ---- header
    def on_switch(e):
        state["target"] = 0.0 if sw.value else 1.0       # switch ON = dark

    sw = ft.Switch(value=not args.light, on_change=on_switch, active_color=ACCENT)
    toggle = ft.Row([icon(ft.Icons.LIGHT_MODE, 18, "TEXT"), sw, icon(ft.Icons.DARK_MODE, 18, "TEXT")], spacing=2,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER)
    header = glass(ft.Row([
        ft.Row([ft.Container(ft.Icon(ft.Icons.HEADPHONES, size=22, color=ON_ACCENT), bgcolor=ACCENT, border_radius=10,
                             width=40, height=40, alignment=ft.Alignment.CENTER),
                ft.Column([text("DuoSound", 22, ft.FontWeight.BOLD),
                           text("One movie, many headphones, in sync.", 13, tok="TEXT_2")], spacing=0)], spacing=12),
        ft.Row([toggle, icon_button(ft.Icons.HELP_OUTLINE, "Help")], spacing=4),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=18, vertical=10))

    # ---- headphone rows
    def make_field(v: int) -> ft.TextField:
        tf = ft.TextField(value=str(v), width=64, dense=True, text_align=ft.TextAlign.CENTER, text_size=14,
                          content_padding=ft.Padding.symmetric(horizontal=4, vertical=9), filled=True,
                          input_filter=ft.NumbersOnlyInputFilter())

        @reg
        def _(b, tf=tf):
            tf.color = hexc(ui_tok("TEXT", b))
            tf.fill_color = rgba(ui_tok("FIELD", b), ui_num("FIELD_A", b))
            line = ui_tok("TEXT", b)
            tf.border = {
                ft.ControlState.DEFAULT: ft.OutlineInputBorder(side=ft.BorderSide(1, rgba(line, 0.30)), border_radius=10),
                ft.ControlState.FOCUSED: ft.OutlineInputBorder(side=ft.BorderSide(2, hexc(ui_tok("LINK", b))), border_radius=10),
            }
        return tf

    def step_volume(tf: ft.TextField, delta: int):
        tf.value = str(max(0, min(100, int(tf.value or 0) + delta)))
        page.update(tf)

    def outlined(label, on_click=None) -> ft.OutlinedButton:
        btn = ft.OutlinedButton(label, on_click=on_click, height=36)

        @reg
        def _(b, btn=btn):
            btn.style = ft.ButtonStyle(color=hexc(ui_tok("TEXT", b)), side=ft.BorderSide(1, rgba(ui_tok("TEXT", b), 0.40)),
                                       shape=ft.RoundedRectangleBorder(radius=10))
        return btn

    def text_button(label, on_click=None) -> ft.TextButton:
        btn = ft.TextButton(label, on_click=on_click)

        @reg
        def _(b, btn=btn):
            btn.style = ft.ButtonStyle(color=hexc(ui_tok("LINK", b)), shape=ft.RoundedRectangleBorder(radius=10))
        return btn

    row_boxes: list[ft.Container] = []

    def hp_row(name: str, vol: int, latency: int) -> ft.Container:
        tf = make_field(vol)
        row = ft.Row([
            ft.Row([icon(ft.Icons.HEADPHONES, 24, "TEXT"),
                    ft.Column([text(name, 15, ft.FontWeight.W_600),
                               ft.Row([icon(ft.Icons.BLUETOOTH, 14, "OK"), text(f"Bluetooth · Playing · {latency} ms", 12.5, tok="OK")], spacing=4)],
                              spacing=1)], spacing=12, expand=True),
            ft.Row([icon_button(ft.Icons.REMOVE, "Quieter", lambda e, tf=tf: step_volume(tf, -5), 18), tf, text("%", 14, tok="TEXT_2"),
                    icon_button(ft.Icons.ADD, "Louder", lambda e, tf=tf: step_volume(tf, 5), 18)], spacing=0,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            outlined("Test"),
            text_button("Adjust sync"),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
        box = ft.Container(row, border_radius=12, padding=ft.Padding.symmetric(horizontal=12, vertical=7), animate=SWAP)
        row_boxes.append(box)
        return box

    card = glass(ft.Column([
        ft.Row([text("Headphones", 16, ft.FontWeight.BOLD), text("3 connected", 13, tok="TEXT_2")],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        hp_row("Amon's AirPods", 62, 62), hp_row("Sony WH-1000XM4", 48, 71), hp_row("JBL Tune 510BT", 70, 84),
    ], spacing=7), padding=ft.Padding.symmetric(horizontal=16, vertical=14))

    # ---- action bar + footer
    start = ft.FilledButton(content="Start", icon=ft.Icons.PLAY_ARROW, height=44,
                            style=ft.ButtonStyle(bgcolor=ACCENT, color=ON_ACCENT, icon_color=ON_ACCENT,
                                                 shape=ft.RoundedRectangleBorder(radius=12),
                                                 padding=ft.Padding.symmetric(horizontal=28),
                                                 text_style=ft.TextStyle(size=15, weight=ft.FontWeight.BOLD)))
    status = text("Ready. Press Start, then play the movie.", 14)
    action_bar = glass(ft.Row([status, start], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                              vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=ft.Padding.symmetric(horizontal=18, vertical=10))
    donate = ft.Row([text("Made by Amon Lal  ·", 12.5, tok="TEXT_2"), icon(ft.Icons.FAVORITE, 15, "LINK"),
                     text("Donate", 12.5, ft.FontWeight.W_600, "LINK")], spacing=5,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True)
    footer = ft.Row([glass(donate, radius=20, boost=1.45, padding=ft.Padding.symmetric(horizontal=14, vertical=6))], alignment=ft.MainAxisAlignment.CENTER)

    column = ft.Column([header, ft.Container(expand=True), card, action_bar, footer], spacing=12, expand=True, width=COLUMN_W)
    ui = ft.Container(content=ft.Row([column], alignment=ft.MainAxisAlignment.CENTER, expand=True),
                      padding=ft.Padding.symmetric(horizontal=24, vertical=16), expand=True)

    # ---- scenery: dark scene below, light scene above it with animated opacity (crossfade runs client-side)
    layers: dict[str, Layer] = {}
    stack = ft.Stack([ft.Container(expand=True), ft.Container(expand=True), ui], expand=True)

    def build_layers(w, h):
        layers["dark"] = Layer("dark", w, h, 1.0)
        layers["light"] = Layer("light", w, h, state["blend"])
        stack.controls[0] = layers["dark"].root
        stack.controls[1] = layers["light"].root
        layers["dark"].root.visible = state["target"] < 0.5          # the covered layer is not built/painted by Flutter
        layers["light"].root.visible = state["target"] >= 0.5
        state["painted"] = (w, h)

    def apply_ui(b: float, panels: bool = True):
        for fn in setters:
            fn(b)
        if panels:
            for g in glass_boxes:
                glass_deco(g, b)
            for r in row_boxes:
                r.bgcolor = rgba(ui_tok("ROW", b), ui_num("ROW_A", b))

    def current_size():
        return max(int(page.width or 1000), 300), max(int(page.height or 700), 300)

    page.add(stack)

    async def loop():
        w, h = current_size()
        state["w"], state["h"] = w, h
        build_layers(w, h)
        apply_ui(state["blend"])
        page.update()
        t0 = last = time.perf_counter()
        next_wind = 0.0
        toggled = False
        size_changed_at = None
        sw_t = 0.0
        sw_from = 0.0
        swapping = False
        acc = [0, 0.0, 0.0, 0.0]
        while True:
            now = time.perf_counter()
            dt, t = now - last, now - t0
            last = now
            if args.toggle_after and not toggled and t > args.toggle_after:
                toggled = True
                sw.value = not sw.value
                state["target"] = 0.0 if sw.value else 1.0
                page.update(sw)
            # ---- theme swap
            if not swapping and abs(state["blend"] - state["target"]) > 1e-3:
                swapping = True
                sw_t, sw_from = 0.0, state["blend"]
                layers["dark"].root.visible = layers["light"].root.visible = True
                page.update(layers["dark"].root, layers["light"].root)
                await asyncio.sleep(0.12)                       # let Flutter build the layer that was hidden
                layers["light"].root.opacity = state["target"]  # client animates the crossfade
                apply_ui(state["target"])                       # panel tints: set once, animated client-side; text follows per frame
                page.update()
                last = time.perf_counter()
                continue
            if swapping:
                sw_t += dt / SWAP_SECONDS
                x = min(1.0, sw_t)
                e = x * x * (3 - 2 * x)
                state["blend"] = sw_from + (state["target"] - sw_from) * e
                apply_ui(state["blend"], panels=False)
                if x >= 1.0:
                    swapping = False
                    state["blend"] = state["target"]
                    hidden = layers["dark"] if state["target"] >= 0.5 else layers["light"]
                    hidden.root.visible = False
                    page.update(hidden.root, ui)
                else:
                    page.update(ui)
            # ---- window resized: rebuild the scenes (debounced)
            nw, nh = current_size()
            if (nw, nh) != (state["w"], state["h"]):
                state["w"], state["h"] = nw, nh
                size_changed_at = now
            if size_changed_at and now - size_changed_at > 0.3 and state["painted"] != (nw, nh):
                size_changed_at = None
                build_layers(nw, nh)
                page.update(stack)
            # ---- live scenery
            ta = time.perf_counter()
            vis = [lay for lay in layers.values() if lay.root.visible]
            if t >= next_wind and not os.environ.get('DS_NOWIND'):
                next_wind = t + WIND_EVERY
                ctrls = []
                for lay in vis:
                    ctrls += lay.set_wind(t + WIND_EVERY)       # aim one interval ahead: animation reaches it on time
                page.update(*ctrls)
            tb = time.perf_counter()
            for lay in vis:
                lay.fast_step(t, dt)
            if not os.environ.get('DS_NOFAST'):
                page.update(*[lay.fast for lay in vis])
            tc = time.perf_counter()
            if os.environ.get("DS_TIMING"):
                acc[0] += 1
                acc[1] += tb - ta
                acc[2] += tc - tb
                if acc[0] == 30:
                    print(f"wind-tick {acc[1] / 30 * 1000:.1f} ms avg/frame, fast canvas {acc[2] / 30 * 1000:.1f} ms/frame", flush=True)
                    acc[:] = [0, 0.0, 0.0, 0.0]
            await asyncio.sleep(max(0.0, 1.0 / args.fps - (time.perf_counter() - now)))

    page.run_task(loop)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--light", action="store_true", help="start in light mode")
    ap.add_argument("--toggle-after", type=float, default=0, help="flip theme after N seconds (testing)")
    ap.add_argument("--fps", type=float, default=15)
    ARGS = ap.parse_args()
    ft.run(main)
