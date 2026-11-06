"""Help and Donate & about pages: glass panels that replace the main page inside the same window."""
from __future__ import annotations

import asyncio
import io
import re
from typing import Callable

import flet as ft
from PIL import Image

from .. import __version__, help_text
from ..resources import DONATE_QR, resource_path
from . import tokens as T
from .widgets import glass, hairline, link_button, page_of, safe_update, secondary_button, txt
from .words import WORDS

QR_CARD_BOX = (200, 416, 1240, 1584)      # the white card with the QR code inside GooglePay_QR.png (1440 x 2000)


def rich(text: str, size: float = T.S_BODY, color: str = T.TEXT, **kw) -> ft.Text:
    """Text with **bold** parts."""
    spans = []
    for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        if part:
            spans.append(ft.TextSpan(part, style=ft.TextStyle(font_family=T.FONT_BOLD if i % 2 else T.FONT, color=T.TEXT if i % 2 else color)))
    return ft.Text(spans=spans, size=size, color=color, font_family=T.FONT, selectable=True, **kw)


class HelpPage:
    def __init__(self, on_copy_diag: Callable[[], str], on_open_logs: Callable, on_bt_settings: Callable, on_donate: Callable,
                 copy_text: Callable[[str], "asyncio.Future"]):
        self._copy_diag, self._copy_text = on_copy_diag, copy_text
        self.compact = False
        self.key = help_text.TOPICS[0][0]
        self.nav: dict[str, ft.TextButton] = {}
        for key, title, _ in help_text.TOPICS:
            b = ft.TextButton(content=title, on_click=lambda e, k=key: self.show(k))
            self.nav[key] = b
        self.donate_btn = link_button(f"{WORDS['donate']} & about", lambda e: on_donate(), ft.Icons.FAVORITE, T.S_BODY)
        self.body = ft.Column([], spacing=T.GAP_S, scroll=ft.ScrollMode.AUTO, expand=True)
        self.copy_btn = secondary_button(WORDS["copy_diag"], ft.Icons.CONTENT_COPY, self._copy, T.S_BODY, 38)
        self.tools = ft.Row([self.copy_btn,
                             secondary_button(WORDS["open_logs"], ft.Icons.FOLDER_OPEN, lambda e: on_open_logs(), T.S_BODY, 38),
                             secondary_button(WORDS["win_bt"], ft.Icons.BLUETOOTH, lambda e: on_bt_settings(), T.S_BODY, 38)],
                            spacing=T.GAP_S, wrap=True, run_spacing=T.GAP_S)
        self.control = glass(None, expand=True)
        self._layout()
        self.show(self.key)

    def _style_nav(self) -> None:
        for k, b in self.nav.items():
            on = k == self.key
            b.style = ft.ButtonStyle(color=T.TEXT if on else T.TEXT_2, bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE) if on else None,
                                     shape=ft.RoundedRectangleBorder(radius=T.RADIUS_CONTROL), alignment=ft.Alignment.CENTER_LEFT,
                                     padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                                     text_style=ft.TextStyle(size=T.S_BODY, font_family=T.FONT_BOLD if on else T.FONT))

    def _layout(self) -> None:
        self._style_nav()
        if self.compact:
            nav = ft.Row(list(self.nav.values()), wrap=True, spacing=0, run_spacing=0)
            inner = ft.Column([nav, hairline(), self.body, hairline(), self.tools], spacing=T.GAP_S, expand=True)
        else:
            nav = ft.Column(list(self.nav.values()) + [hairline(), self.donate_btn], spacing=2, width=210)
            inner = ft.Column([ft.Row([nav, ft.VerticalDivider(width=T.GAP_L, color=T.HAIRLINE), self.body], expand=True,
                                      vertical_alignment=ft.CrossAxisAlignment.START), hairline(), self.tools],
                              spacing=T.GAP_S, expand=True)
        self.control.content = inner

    def set_compact(self, compact: bool) -> None:
        if compact != self.compact:
            self.compact = compact
            self._layout()
            safe_update(self.control)

    def show(self, key: str) -> None:
        tp = help_text.topic(key) or help_text.TOPICS[0]
        self.key = tp[0]
        self._style_nav()
        items: list[ft.Control] = [txt(tp[1], T.S_SECTION, True)]
        for kind, body in tp[2]:
            if kind == "p":
                items.append(rich(body))
            elif kind in ("steps", "ul"):
                for i, item in enumerate(body, 1):
                    items.append(ft.Row([txt(f"{i}." if kind == "steps" else "•", T.S_BODY, True, T.LINK, width=24),
                                         ft.Container(rich(item), expand=True)], vertical_alignment=ft.CrossAxisAlignment.START, spacing=4))
            elif kind == "faq":
                for q, a in body:
                    items.append(ft.Container(txt(q, T.S_BODY, True, selectable=True), padding=ft.Padding.only(top=T.GAP_S)))
                    items.append(rich(a, color=T.TEXT_2))
        self.body.controls = items
        safe_update(self.control)
        page = page_of(self.control)
        if page is not None:
            page.run_task(self.body.scroll_to, offset=0, duration=0)

    def _copy(self, e) -> None:
        page = page_of(self.control)
        if page is None:
            return

        async def go():
            await self._copy_text(self._copy_diag())
            self.copy_btn.content, self.copy_btn.icon = WORDS["copied"], ft.Icons.CHECK
            safe_update(self.copy_btn)
            await asyncio.sleep(2)
            self.copy_btn.content, self.copy_btn.icon = WORDS["copy_diag"], ft.Icons.CONTENT_COPY
            safe_update(self.copy_btn)
        page.run_task(go)


def load_qr(width: int = 320) -> bytes | None:
    """The donate QR card from "Donate ME QR/GooglePay_QR.png", cropped and scaled, as PNG bytes."""
    try:
        img = Image.open(resource_path(DONATE_QR)).convert("RGB")
    except (OSError, ValueError):
        return None
    if img.size == (1440, 2000):
        img = img.crop(QR_CARD_BOX)
    img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class AboutPage:
    """Credit to the creator, the UPI ID with Copy, and the QR code (large enough for a phone to scan)."""

    def __init__(self, copy_text: Callable[[str], "asyncio.Future"]):
        self._copy_text = copy_text
        self.copy_btn = secondary_button(WORDS["copy"], ft.Icons.CONTENT_COPY, self._copy, T.S_BODY, 36)
        about: list[ft.Control] = []
        for _kind, para in help_text.ABOUT:
            about.append(rich(para))
        about.append(txt(WORDS["donate_thanks"], T.S_BODY, color=T.TEXT))
        left = ft.Column([
            ft.Row([ft.Icon(ft.Icons.FAVORITE, size=28, color=T.LINK), txt(WORDS["donate_title"], T.S_SECTION, True)], spacing=T.GAP_S),
            *about,
            ft.Row([txt(f"{WORDS['upi']}:", T.S_BODY, color=T.TEXT_2), txt(help_text.UPI_ID, T.S_NAME, True, selectable=True), self.copy_btn],
                   spacing=T.GAP_S, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            txt(f"DuoSound {__version__}", T.S_CAPTION, color=T.TEXT_2),
        ], spacing=T.GAP_M, width=330)
        qr = load_qr()
        right: list[ft.Control] = []
        if qr:
            right = [ft.Column([ft.Image(src=qr, width=260, border_radius=12), txt(WORDS["donate_scan"], T.S_CAPTION, color=T.TEXT_2, width=260)],
                               spacing=T.GAP_S)]
        self.control = glass(ft.Column([ft.Row([left] + right, wrap=True, spacing=T.GAP_XL, run_spacing=T.GAP_L,
                                               vertical_alignment=ft.CrossAxisAlignment.START)],
                                       scroll=ft.ScrollMode.AUTO, expand=True), padding=T.GAP_XL, expand=True)

    def _copy(self, e) -> None:
        page = page_of(self.control)
        if page is None:
            return

        async def go():
            await self._copy_text(help_text.UPI_ID)
            self.copy_btn.content, self.copy_btn.icon = WORDS["copied"], ft.Icons.CHECK
            safe_update(self.copy_btn)
            await asyncio.sleep(2)
            self.copy_btn.content, self.copy_btn.icon = WORDS["copy"], ft.Icons.CONTENT_COPY
            safe_update(self.copy_btn)
        page.run_task(go)
