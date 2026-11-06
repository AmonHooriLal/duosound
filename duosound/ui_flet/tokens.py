"""Design tokens of the Flet window: light and dark glass palettes, sizes and type.

Direction (Amon's design lead): movie night in a dim room, a moonlit-coast travel poster.
Dark = night ink + moon cream + lamplight amber. Light = white glass + ink + amber. Vermilion is the alert colour.
Colours are exposed as *theme colour names* (ft.Colors.ON_SURFACE ...): Flutter swaps them (and animates the change) when
page.theme_mode flips, so no widget needs re-colouring by hand. Scenery has its own palettes (scenery.SCENES)."""
from __future__ import annotations

import flet as ft

INK = "#0F1B33"          # night ink: dark glass tint and dark text on amber
CREAM = "#F2E6C8"        # moon cream: dark-mode text
AMBER = "#F4B03E"        # lamplight amber: primary action and live state (fill colour)
LIGHT_INK = "#14223F"    # light-mode text
MODES = ("light", "dark", "system")


def _mix(a: str, b: str, t: float) -> str:
    """Blend two #RRGGBB colours: t=0 gives a, t=1 gives b."""
    x, y = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (a, b))
    return "#%02X%02X%02X" % tuple(round(p + (q - p) * t) for p, q in zip(x, y))


# raw values per mode (also used by tests to check contrast)
PALETTES = {
    "dark": dict(
        glass=INK, glass_a=0.66, border=CREAM, border_a=0.18, text=CREAM, text2=_mix(INK, CREAM, 0.72),
        accent=AMBER, on_accent=INK, link=AMBER, ok="#8CCB8A", alert="#E5572F", on_alert=INK,
        field=_mix(INK, CREAM, 0.10), field_a=0.55, menu="#17274A", inverse=CREAM, on_inverse=INK,
    ),
    "light": dict(
        glass="#FFFFFF", glass_a=0.62, border="#FFFFFF", border_a=0.75, text=LIGHT_INK, text2=_mix("#FFFFFF", LIGHT_INK, 0.84),
        accent=AMBER, on_accent=LIGHT_INK, link="#8A5300", ok="#2F7A44", alert="#C2411F", on_alert="#FFFFFF",
        field="#FFFFFF", field_a=0.7, menu="#F6F8FC", inverse=LIGHT_INK, on_inverse="#FFFFFF",
    ),
}


def _scheme(mode: str) -> ft.ColorScheme:
    p = PALETTES[mode]
    return ft.ColorScheme(
        primary=p["accent"], on_primary=p["on_accent"], secondary=p["link"], on_secondary=p["on_accent"],
        tertiary=p["ok"], on_tertiary=p["on_accent"], error=p["alert"], on_error=p["on_alert"],
        surface=p["glass"], on_surface=p["text"], on_surface_variant=p["text2"], outline=p["text2"],
        outline_variant=_mix(p["glass"], p["text"], 0.25), surface_tint=p["glass"],
        surface_container=p["menu"], surface_container_low=p["menu"], surface_container_high=p["menu"],
        surface_container_highest=p["field"], inverse_surface=p["inverse"], on_inverse_surface=p["on_inverse"],
        scrim="#000000",
    )


def themes(font: str) -> tuple[ft.Theme, ft.Theme]:
    """(light theme, dark theme) for page.theme / page.dark_theme."""
    kw = dict(font_family=font, use_material3=True)
    return ft.Theme(color_scheme=_scheme("light"), **kw), ft.Theme(color_scheme=_scheme("dark"), **kw)


# ---- colour references (theme names: they follow page.theme_mode)
TEXT = ft.Colors.ON_SURFACE
TEXT_2 = ft.Colors.ON_SURFACE_VARIANT
ACCENT = ft.Colors.PRIMARY
ON_ACCENT = ft.Colors.ON_PRIMARY
LINK = ft.Colors.SECONDARY          # amber in dark, deep amber in light (amber text on white fails contrast)
OK = ft.Colors.TERTIARY
ALERT = ft.Colors.ERROR
ON_ALERT = ft.Colors.ON_ERROR
HAIRLINE = ft.Colors.with_opacity(0.16, ft.Colors.ON_SURFACE)
FIELD = ft.Colors.with_opacity(0.55, ft.Colors.SURFACE_CONTAINER_HIGHEST)
GLASS_A = 0.66
BORDER = ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)


def glass_fill(alpha: float | None = None) -> str:
    return ft.Colors.with_opacity(alpha if alpha is not None else GLASS_A, ft.Colors.SURFACE)


def tone_color(tone: str) -> str:
    return {"ok": OK, "warn": LINK, "bad": ALERT}.get(tone, TEXT_2)


# ---- type: Oswald only for the title, Atkinson Hyperlegible for everything else
FONT = "Atkinson"
FONT_BOLD = "Atkinson Bold"
FONT_TITLE = "Oswald"
FONT_FALLBACK = "Segoe UI"
S_CAPTION, S_BODY, S_NAME, S_SECTION, S_TITLE = 12, 14, 16, 20, 38

# ---- size and spacing
RADIUS_PANEL, RADIUS_CONTROL = 18, 10
BLUR = 16
GAP_XS, GAP_S, GAP_M, GAP_L, GAP_XL = 4, 8, 12, 16, 24
MIN_W, MIN_H = 680, 480
DEFAULT_W, DEFAULT_H = 1000, 700
COLUMN_W = 720               # content column (left aligned): leaves the moon / sun and the lake visible on the right
COMPACT_W = 800              # below this window width rows and the action bar use two lines
TAGLINE_MIN_W = 900
FPS = 12                     # scenery frame rate while idle


def system_mode() -> str:
    """What Windows is set to ("light" or "dark")."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return "light" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "dark"
    except (OSError, ImportError):
        return "dark"


def resolve(mode: str) -> str:
    return system_mode() if mode == "system" else ("light" if mode == "light" else "dark")


def contrast(fg: str, bg: str) -> float:
    """WCAG contrast ratio of two #RRGGBB colours."""
    def lum(c: str) -> float:
        v = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)
