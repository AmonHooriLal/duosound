"""The DuoSound app icon (tray, window): a lamplight-amber rounded square with two pairs of night-ink headphones."""
from __future__ import annotations

from PIL import Image, ImageDraw

from . import tokens as T


def make_app_icon(size: int = 64) -> Image.Image:
    s = size
    img = Image.new("RGBA", (s * 4, s * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    S = s * 4
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=S // 5, fill=T.AMBER)
    w = max(2, S // 16)
    for cx, col in ((S * 0.36, T.INK), (S * 0.64, "#5B4A22")):
        r = S * 0.2
        d.arc([cx - r, S * 0.24, cx + r, S * 0.24 + 2 * r], 180, 360, fill=col, width=w)
        cup = S * 0.08
        for x in (cx - r, cx + r):
            d.rounded_rectangle([x - cup, S * 0.44, x + cup, S * 0.68], radius=cup // 2 or 1, fill=col)
    return img.resize((s, s), Image.LANCZOS)
