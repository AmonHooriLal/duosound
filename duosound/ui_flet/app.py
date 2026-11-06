"""DuoSound window in Flet: glass panels over an animated moonlit / sunny scene.

Talks only to AppController (duosound/controller.py). Slow controller calls (start, stop, calibrate) run in worker threads
(asyncio.to_thread) and the UI is updated when they return, so the window never freezes. Same features as the tkinter window
in duosound/ui/main_window.py, which stays as the fallback.

    from duosound.ui_flet.app import run
    run(ctl, recovered)        # blocks until the window is closed"""
from __future__ import annotations

import asyncio
import queue
import re
import threading
import time

import flet as ft

from .. import __version__, help_text, log_setup
from ..controller import AppController, Problem
from ..resources import resource_path
from . import tokens as T
from .icon import make_app_icon
from .pages import AboutPage, HelpPage
from .scenery import Scenery, animations_enabled
from .widgets import (FOCUS, Banner, TargetRow, glass, hairline, link_button, primary_button, primary_style, safe_update,
                      secondary_button, txt)
from .words import APP_NAME, TAGLINE, THEME_LABEL, WORDS, display_name, source_hint

log = log_setup.get("ui")
FONT_DIR = "fonts"
TICK_S = 0.25
AWAY_S = 10.0              # window unfocused this long -> the scenery freezes


def _font_files() -> dict[str, str]:
    from pathlib import Path
    d = Path(__file__).resolve().parent / FONT_DIR
    base = getattr(__import__("sys"), "_MEIPASS", None)
    if base:
        d = Path(base) / "duosound" / "ui_flet" / FONT_DIR
    return {T.FONT_TITLE: str(d / "Oswald-Variable.ttf"), T.FONT: str(d / "AtkinsonHyperlegible-Regular.ttf"),
            T.FONT_BOLD: str(d / "AtkinsonHyperlegible-Bold.ttf")}


class DuoApp:
    def __init__(self, ctl: AppController, recovered: bool = False) -> None:
        self.ctl = ctl
        self.recovered = recovered
        self.page: ft.Page | None = None
        self.scenery: Scenery | None = None
        self.rows: dict[str, TargetRow] = {}
        self.sources = []
        self.source_id: str | None = None
        self.banner: Banner | None = None
        self.tray = None
        self.busy = False
        self.compact = False
        self.page_name = "main"
        self.src_expanded = False
        self.opts_open = False
        self.log_open = bool(ctl.cfg.get("log_open"))
        self.sync_open: set[str] = set()
        self.synced_until = 0.0
        self.pref = ctl.cfg.get("theme", "dark")
        if self.pref not in T.MODES:
            self.pref = "dark"
        self.eff = T.resolve(self.pref)
        self._save_task: asyncio.Task | None = None
        self._away_task: asyncio.Task | None = None
        self._resize_task: asyncio.Task | None = None
        self._ticks = 0
        self._progress: str | None = None
        self._status = ("", "mute")
        self._meter = 0.0
        self._log_lines: list[str] = []
        self._log_dirty = False
        self._closing = False

    # ================================================================== start-up
    async def main(self, page: ft.Page) -> None:
        self.page = page
        page.title = APP_NAME
        page.padding = 0
        page.spacing = 0
        page.fonts = _font_files()
        light, dark = T.themes(T.FONT)
        page.theme, page.dark_theme = light, dark
        page.theme_mode = {"light": ft.ThemeMode.LIGHT, "dark": ft.ThemeMode.DARK, "system": ft.ThemeMode.SYSTEM}[self.pref]
        page.bgcolor = "#0A1228" if self.eff == "dark" else "#8EC4E6"
        w, h = self._saved_size()
        page.window.width, page.window.height = w, h
        page.window.min_width, page.window.min_height = T.MIN_W, T.MIN_H
        page.window.resizable = True
        ico = resource_path("packaging/duosound.ico")
        if ico.exists():
            page.window.icon = str(ico)
        page.window.prevent_close = True
        page.window.on_event = self._on_window_event
        page.on_resize = self._on_resize
        page.on_keyboard_event = self._on_key
        page.on_platform_brightness_change = lambda e: page.run_task(self._sync_system_theme)
        self.clipboard = ft.Clipboard()
        self._build_ui()
        self.stack = ft.Stack([ft.Container(expand=True), self.ui], expand=True)
        page.add(self.stack)
        await asyncio.sleep(0.15)                       # the client reports its real size
        pw, ph = int(page.width or w), int(page.height or h - 31)
        self.scenery = Scenery(page, self.eff, pw, ph)
        self.stack.controls[0] = self.scenery.control
        self._apply_layout(initial=True)
        page.update()
        if not animations_enabled():
            self.scenery.freeze("anim_off", True)
        self.scenery.start()
        self._start_tray()
        page.run_task(self._tick_loop)
        page.run_task(self._title_bar_later)
        await self.refresh()
        if self.recovered:
            self.add_banner(Problem("recovered", WORDS["recovered"], "trouble"), level="info")
        log.info("Window opened (Flet %s)", ft.__version__ if hasattr(ft, "__version__") else "?")

    def _saved_size(self) -> tuple[int, int]:
        m = re.match(r"\s*(\d+)x(\d+)", str(self.ctl.cfg.get("geometry") or ""))
        if m:
            return max(T.MIN_W, int(m.group(1))), max(T.MIN_H, int(m.group(2)))
        return T.DEFAULT_W, T.DEFAULT_H

    # ================================================================== layout
    def _build_ui(self) -> None:
        # ---- header: title directly on the scene (Oswald, the only place it is used), Help top right
        self.title = ft.Text(APP_NAME, size=T.S_TITLE, font_family=T.FONT_TITLE, weight=ft.FontWeight.W_600, color=T.TEXT)
        self.tagline = txt(TAGLINE, T.S_BODY, color=T.TEXT)           # on the bare sky: full-strength text (the lighter one fails contrast)
        self.help_btn = link_button(WORDS["help"], lambda e: self.show_page("help"), ft.Icons.HELP_OUTLINE, T.S_NAME, color=T.TEXT)
        self.help_btn.tooltip = "Help (F1)"
        header = ft.Row([self.title, ft.Container(self.tagline, padding=ft.Padding.only(left=T.GAP_M, top=14)),
                         ft.Container(expand=True), self.help_btn], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # ---- main page: one line for the source, headphones list
        self.src_name = txt("", T.S_NAME, True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.src_name_box = ft.Container(self.src_name)
        self.src_change = link_button(WORDS["change"], lambda e: self.expand_source(), size=T.S_NAME)
        self.src_summary = ft.Row([ft.Icon(ft.Icons.SPEAKER, size=20, color=T.TEXT_2), txt(WORDS["copying"], T.S_NAME, color=T.TEXT),
                                   self.src_name_box, self.src_change], spacing=6, tight=True,
                                  vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.src_title = txt(WORDS["source"], T.S_NAME, True, visible=False)
        self.opt_btn = link_button(WORDS["options"], lambda e: self.toggle_options(), ft.Icons.KEYBOARD_ARROW_RIGHT, T.S_BODY, color=T.TEXT)
        self.src_line = ft.Row([self.src_summary, self.src_title, ft.Container(expand=True), self.opt_btn],
                               vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self.source_dd = ft.Dropdown(options=[], expand=True, text_size=T.S_BODY, color=T.TEXT, filled=True, fill_color=T.FIELD,
                                     dense=True, on_select=self._on_source_picked,
                                     border=ft.OutlineInputBorder(side=ft.BorderSide(1, ft.Colors.with_opacity(0.32, ft.Colors.ON_SURFACE)),
                                                                  border_radius=T.RADIUS_CONTROL))
        FOCUS.watch(self.source_dd)
        self.refresh_btn = secondary_button(WORDS["refresh"], ft.Icons.REFRESH, lambda e: self.page.run_task(self.refresh), T.S_BODY, 40)
        self.done_btn = link_button(WORDS["done"], lambda e: self.collapse_source(), size=T.S_BODY)
        self.src_hint = txt("", T.S_CAPTION, color=T.TEXT_2)
        self.src_probs = ft.Column([], spacing=T.GAP_XS)
        self.src_panel = glass(ft.Column([
            txt(WORDS["source_help"], T.S_CAPTION, color=T.TEXT_2),
            ft.Row([self.source_dd, self.refresh_btn, self.done_btn], spacing=T.GAP_S, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.src_hint, self.src_probs], spacing=T.GAP_S), visible=False, opacity=0)

        self.auto_sw = ft.Switch(value=bool(self.ctl.cfg.get("auto_setup", True)), on_change=lambda e: self._set_opt("auto_setup", bool(e.control.value)),
                                 active_color=T.ACCENT)
        self.mute_sw = ft.Switch(value=bool(self.ctl.cfg.get("mute_speakers", True)), on_change=lambda e: self._set_opt("mute_speakers", bool(e.control.value)),
                                 active_color=T.ACCENT)
        FOCUS.watch(self.auto_sw)
        FOCUS.watch(self.mute_sw)
        self.seg: dict[str, ft.TextButton] = {}
        for mode in T.MODES:
            self.seg[mode] = ft.TextButton(content=THEME_LABEL[mode], on_click=lambda e, m=mode: self.page.run_task(self.set_theme, m))
        self._style_seg()
        self.opt_panel = glass(ft.Column([
            ft.Row([txt(WORDS["appearance"], T.S_BODY, color=T.TEXT_2), ft.Row(list(self.seg.values()), spacing=2)], spacing=T.GAP_M,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([self.auto_sw, ft.Container(txt(WORDS["opt_auto"], T.S_BODY), expand=True)], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([self.mute_sw, ft.Container(txt(WORDS["opt_mute"], T.S_BODY), expand=True)], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            link_button(WORDS["win_sound"], lambda e: self.ctl.open_windows_settings("sound"), ft.Icons.OPEN_IN_NEW, T.S_BODY),
        ], spacing=T.GAP_XS), visible=False, opacity=0)

        self.list_col = ft.Column([], spacing=0)
        self.list_caption = txt(WORDS["headphones_help"], T.S_CAPTION, color=T.TEXT_2)
        self.list_card = glass(ft.Column([
            ft.Row([ft.Column([txt(WORDS["headphones"], T.S_SECTION, True), self.list_caption], spacing=0, expand=True),
                    link_button(WORDS["win_bt"], lambda e: self.ctl.open_windows_settings("bluetooth"), ft.Icons.BLUETOOTH, T.S_BODY)],
                   vertical_alignment=ft.CrossAxisAlignment.START),
            hairline(), self.list_col], spacing=T.GAP_S), padding=ft.Padding.symmetric(horizontal=T.GAP_L, vertical=T.GAP_M))
        self.empty = ft.Column([
            ft.Row([ft.Icon(ft.Icons.HEADPHONES, size=28, color=T.TEXT_2), txt(WORDS["empty_title"], T.S_NAME, True)], spacing=T.GAP_S),
            txt(WORDS["empty_body"], T.S_BODY, color=T.TEXT_2),
            ft.Row([secondary_button(WORDS["win_bt"], ft.Icons.BLUETOOTH, lambda e: self.ctl.open_windows_settings("bluetooth"), T.S_BODY, 40),
                    secondary_button(WORDS["refresh"], ft.Icons.REFRESH, lambda e: self.page.run_task(self.refresh), T.S_BODY, 40)],
                   spacing=T.GAP_S, wrap=True)], spacing=T.GAP_S, visible=False)
        self.main_col = ft.Column([self.src_line, self.src_panel, self.opt_panel, self.list_card], spacing=T.GAP_M, scroll=ft.ScrollMode.AUTO, expand=True)

        self.help_page = HelpPage(self.ctl.diagnostics, self.ctl.open_log_folder, lambda: self.ctl.open_windows_settings("bluetooth"),
                                  lambda: self.show_page("about"), self._copy_text)
        self.about_page = AboutPage(self._copy_text)
        self.body = ft.Container(self.main_col, expand=True)

        # ---- banner slot, log pane, bottom glass bar (actions + footer)
        self.banner_slot = ft.Container()
        self.log_text = ft.Text("", size=T.S_CAPTION, font_family="Cascadia Mono", color=T.TEXT_2, selectable=True)
        self.log_col = ft.Column([self.log_text], scroll=ft.ScrollMode.AUTO, auto_scroll=True, expand=True)
        self.log_panel = glass(self.log_col, radius=14, padding=T.GAP_S, height=130, visible=self.log_open)

        self.start_btn = primary_button(WORDS["start"], ft.Icons.PLAY_ARROW, lambda e: self.toggle())
        self.start_btn.tooltip = "Start / Stop (Space)"
        self.cal_btn = secondary_button(WORDS["calibrate"], ft.Icons.MY_LOCATION, lambda e: self.ask_calibrate())
        self.spk_btn = secondary_button(WORDS["mute"], ft.Icons.VOLUME_OFF, lambda e: self.toggle_speakers(), visible=False)
        self.status = txt(WORDS["ready"], T.S_BODY, color=T.TEXT_2, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
        self.meter = ft.ProgressBar(value=0, width=124, bar_height=6, color=T.ACCENT, bgcolor=T.HAIRLINE, border_radius=3)
        self.meter_caption = txt(WORDS["sound_in"], T.S_CAPTION, color=T.TEXT_2)
        self.meter_box = ft.Column([self.meter_caption, self.meter], spacing=4, tight=True)
        self.actions = ft.Container()
        self.log_btn = link_button(WORDS["log"], lambda e: self.toggle_log(), ft.Icons.KEYBOARD_ARROW_RIGHT, T.S_CAPTION, color=T.TEXT_2)
        footer = ft.Row([txt(f"{WORDS['made_by']} ", T.S_CAPTION, color=T.TEXT_2), txt(help_text.AUTHOR, T.S_CAPTION, True, T.TEXT),
                         link_button(WORDS["donate"], lambda e: self.show_page("about"), ft.Icons.FAVORITE, T.S_CAPTION),
                         ft.Container(expand=True), self.log_btn, txt(f"v{__version__}", T.S_CAPTION, color=T.TEXT_2)],
                        spacing=T.GAP_S, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.bottom = glass(ft.Column([self.actions, hairline(), footer], spacing=T.GAP_XS),
                            padding=ft.Padding.symmetric(horizontal=T.GAP_L, vertical=T.GAP_S))
        # blur is set to 0 while audio plays (GPU DPC relief) and restored on Stop
        self._glass_panels = [self.src_panel, self.opt_panel, self.list_card, self.log_panel, self.bottom]

        self.col = ft.Column([self.body, self.banner_slot, self.log_panel, self.bottom], spacing=T.GAP_M, expand=True)
        self.col_box = ft.Container(self.col, left=32, top=70, bottom=14, width=T.COLUMN_W)
        self.header_box = ft.Container(header, left=32, right=32, top=14)        # full width: Help sits top right
        self.ui = ft.Stack([self.col_box, self.header_box], expand=True)
        self._header_tag = self.tagline

    def _col_width(self, w: int) -> int:
        wide = self.page_name != "main"
        return int(max(300, min(900 if wide else T.COLUMN_W, w - 64)))

    def _build_actions(self) -> None:
        if self.compact:
            self.meter_box.controls = [self.meter_caption, self.meter]
            self.actions.content = ft.Column([
                ft.Row([self.start_btn, self.cal_btn, self.spk_btn], spacing=T.GAP_S, wrap=True, run_spacing=T.GAP_S),
                ft.Row([ft.Container(self.status, expand=True), ft.Row([self.meter_caption, self.meter], spacing=T.GAP_S, tight=True)],
                       spacing=T.GAP_M, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=T.GAP_S)
        else:
            self.meter_box.controls = [self.meter_caption, self.meter]
            self.actions.content = ft.Row([self.start_btn, self.cal_btn, self.spk_btn, ft.Container(self.status, expand=True, padding=ft.Padding.only(left=T.GAP_S)),
                                           self.meter_box], spacing=T.GAP_S, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _apply_layout(self, initial: bool = False) -> None:
        w = int(self.page.width or T.DEFAULT_W)
        compact = w < T.COMPACT_W
        short = int(self.page.height or T.DEFAULT_H) < 600            # small windows: smaller title, tighter top
        self.title.size = 30 if short else T.S_TITLE
        self.list_caption.visible = not short
        self.header_box.top = 8 if short else 14
        self.col_box.top = 50 if short else 70
        self.col_box.width = self._col_width(w)
        self.tagline.visible = w >= T.TAGLINE_MIN_W and not short
        if compact != self.compact or initial:
            self.compact = compact
            self._build_actions()
            self.help_page.set_compact(compact)
            if self.rows:
                self._build_rows(self.source_id, [r.state for r in self.rows.values()])
        self._fit_source_name()

    def _fit_source_name(self) -> None:
        """Very long names are cut with an ellipsis so the one-line summary never pushes Options out of the window."""
        full = getattr(self, "_src_full", "")
        room = self.col_box.width - 330
        self.src_name.value = full
        self.src_name_box.width = room if len(full) * 8.6 > room else None
        self.src_name_box.tooltip = full if self.src_name_box.width else None

    def _on_resize(self, e) -> None:
        self._apply_layout()
        self.page.update()
        if self._resize_task:
            self._resize_task.cancel()
        self._resize_task = self.page.run_task(self._after_resize)

    async def _after_resize(self) -> None:
        await asyncio.sleep(0.4)                            # wait until the user stops dragging
        self._resize_task = None
        if self.scenery and not self._closing:
            await self.scenery.resize(int(self.page.width or T.DEFAULT_W), int(self.page.height or T.DEFAULT_H))
        self.ctl.set_option("geometry", f"{int(self.page.window.width)}x{int(self.page.window.height)}")
        self._schedule_save()

    # ================================================================== theme
    def _style_seg(self) -> None:
        for mode, b in self.seg.items():
            on = mode == self.pref
            b.style = ft.ButtonStyle(color=T.TEXT if on else T.TEXT_2, bgcolor=ft.Colors.with_opacity(0.16, ft.Colors.ON_SURFACE) if on else None,
                                     shape=ft.RoundedRectangleBorder(radius=T.RADIUS_CONTROL), padding=ft.Padding.symmetric(horizontal=14, vertical=6),
                                     text_style=ft.TextStyle(size=T.S_BODY, font_family=T.FONT_BOLD if on else T.FONT))

    def _effective(self) -> str:
        if self.pref != "system":
            return self.pref
        b = getattr(self.page, "platform_brightness", None)
        if b is not None:
            return "dark" if b == ft.Brightness.DARK else "light"
        return T.system_mode()

    async def set_theme(self, mode: str) -> None:
        if mode not in T.MODES or mode == self.pref:
            return
        self.pref = mode
        self.ctl.set_option("theme", mode)
        self._schedule_save()
        self.page.theme_mode = {"light": ft.ThemeMode.LIGHT, "dark": ft.ThemeMode.DARK, "system": ft.ThemeMode.SYSTEM}[mode]
        self._style_seg()
        self.page.update()
        await self._apply_effective()

    async def _apply_effective(self) -> None:
        eff = self._effective()
        if eff == self.eff:
            return
        self.eff = eff
        self._title_bar()
        if self.scenery:
            await self.scenery.set_mode(eff)

    async def _sync_system_theme(self) -> None:
        if self.pref == "system":
            await asyncio.sleep(0.2)
            await self._apply_effective()

    def _title_bar(self) -> None:
        """Windows title bar in the window's own colours (Windows 11 caption colours; the dark flag for Windows 10). Cosmetic."""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.FindWindowW(None, APP_NAME)
            if not hwnd:
                return
            dwm = ctypes.windll.dwmapi

            def put(attr: int, value: int) -> int:
                v = ctypes.c_int(value)
                return dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

            def ref(hex_color: str) -> int:
                h = hex_color.lstrip("#")
                return int(h[0:2], 16) | int(h[2:4], 16) << 8 | int(h[4:6], 16) << 16
            dark = self.eff == "dark"
            if put(20, 1 if dark else 0) != 0:
                put(19, 1 if dark else 0)
            put(35, ref(T.INK if dark else "#EAF1F8"))
            put(36, ref(T.CREAM if dark else T.LIGHT_INK))
        except Exception:  # noqa: BLE001
            pass

    async def _title_bar_later(self) -> None:
        await asyncio.sleep(0.6)
        self._title_bar()

    # ================================================================== pages
    def show_page(self, name: str) -> None:
        self.page_name = name
        self.body.content = {"main": self.main_col, "help": self.help_page.control, "about": self.about_page.control}[name]
        if name == "main":
            self.help_btn.content, self.help_btn.icon, self.help_btn.on_click = WORDS["help"], ft.Icons.HELP_OUTLINE, lambda e: self.show_page("help")
            self.help_btn.tooltip = "Help (F1)"
        else:
            self.help_btn.content, self.help_btn.icon, self.help_btn.on_click = WORDS["back"], ft.Icons.ARROW_BACK, lambda e: self.show_page("main")
            self.help_btn.tooltip = "Back (Esc)"
        self._apply_layout()
        self.page.update()

    def show_help(self, topic: str) -> None:
        self.help_page.show(topic)
        self.show_page("help")

    def expand_source(self) -> None:
        self.src_expanded = True
        self._render_source_panel()
        self.page.update()

    def collapse_source(self) -> None:
        self.src_expanded = False
        self._render_source_panel()
        self.page.update()

    def toggle_options(self) -> None:
        self.opts_open = not self.opts_open
        self.opt_btn.icon = ft.Icons.KEYBOARD_ARROW_DOWN if self.opts_open else ft.Icons.KEYBOARD_ARROW_RIGHT
        self._reveal(self.opt_panel, self.opts_open)
        self.page.update(self.opt_btn)

    def toggle_log(self) -> None:
        self.log_open = not self.log_open
        self.log_panel.visible = self.log_open
        self.log_btn.icon = ft.Icons.KEYBOARD_ARROW_DOWN if self.log_open else ft.Icons.KEYBOARD_ARROW_RIGHT
        self.ctl.set_option("log_open", self.log_open)
        self._schedule_save()
        self._log_dirty = True
        self.page.update()

    def _reveal(self, ctrl: ft.Container, show: bool) -> None:
        """Fade a panel in or out (180 ms, ease-out). Only ever in response to an action."""
        async def go():
            if show:
                ctrl.visible, ctrl.opacity = True, 0
                safe_update(ctrl)
                await asyncio.sleep(0.03)
                ctrl.opacity = 1
            else:
                ctrl.opacity = 0
                safe_update(ctrl)
                await asyncio.sleep(0.2)
                ctrl.visible = False
            safe_update(ctrl)
        self.page.run_task(go)

    # ================================================================== banners
    def add_banner(self, p: Problem, level: str = "warn", actions=None, dismiss: bool = True) -> Banner:
        """Show ONE message in the banner slot (a new message replaces the old one; the same message again restarts its timer)."""
        cur = self.banner
        if cur is not None and actions is None and cur.code == p.code and cur.text == p.text:
            cur.arm(self.page)
            return cur
        if cur is not None:
            cur.cancel()
        b = Banner(p.code, p.text, level, p.help_topic or None, self.show_help, actions, on_close=self._close_banner)
        self.banner = b
        self.banner_slot.content = b.control
        self.page.update(self.banner_slot)

        async def fade_in():
            await asyncio.sleep(0.03)
            b.control.opacity = 1
            safe_update(b.control)
            b.arm(self.page)
        self.page.run_task(fade_in)
        return b

    def _close_banner(self, b: Banner) -> None:
        if self.banner is not b:
            return
        self.banner = None

        async def fade_out():
            b.control.opacity = 0
            safe_update(b.control)
            await asyncio.sleep(0.2)
            if self.banner is None:
                self.banner_slot.content = None
                safe_update(self.banner_slot)
        self.page.run_task(fade_out)

    def clear_banners(self, keep: tuple[str, ...] = ()) -> None:
        b = self.banner
        if b is not None and b.code not in keep:
            b.cancel()
            self.banner = None
            self.banner_slot.content = None
            safe_update(self.banner_slot)

    def _show_source_problems(self) -> None:
        probs = self.ctl.source_problems(self.source_id)
        self._src_problem_count = len(probs)
        self.src_probs.controls = [ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=18, color=T.LINK),
                                           ft.Container(txt(p.text, T.S_BODY), expand=True),
                                           link_button(WORDS["how_to_fix"], lambda e, t=p.help_topic: self.show_help(t))] if p.help_topic else
                                          [ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=18, color=T.LINK), ft.Container(txt(p.text, T.S_BODY), expand=True)],
                                          spacing=T.GAP_S, vertical_alignment=ft.CrossAxisAlignment.CENTER) for p in probs]

    # ================================================================== devices
    async def refresh(self) -> None:
        if self.ctl.running or self.busy:
            self.add_banner(Problem("busy", WORDS["busy_refresh"], ""), level="info")
            return
        self.refresh_btn.disabled = True
        safe_update(self.refresh_btn)
        try:
            await asyncio.to_thread(self.ctl.refresh_devices)
        except Exception:  # noqa: BLE001
            log.error("Refresh failed", exc_info=True)
        self.refresh_btn.disabled = False
        self.sources = self.ctl.source_choices()
        pick = self.ctl.preferred_source_id()
        self.source_id = pick if any(d.id == pick for d in self.sources) else (self.sources[0].id if self.sources else None)
        if self.source_id:
            self.ctl.set_option("source_id", self.source_id)
        self.source_dd.options = [ft.DropdownOption(key=d.id, text=display_name(d.name)) for d in self.sources]
        self.source_dd.value = self.source_id
        self._render_source(rebuild_rows=True)
        self._schedule_save()
        self.page.update()

    @property
    def source(self):
        return next((d for d in self.sources if d.id == self.source_id), None)

    def _on_source_picked(self, e) -> None:
        self.source_id = self.source_dd.value
        self.src_expanded = False
        if self.source_id:
            self.ctl.set_option("source_id", self.source_id)
        self._render_source(rebuild_rows=True)
        self._schedule_save()
        self.page.update()

    def _render_source(self, rebuild_rows: bool = False) -> None:
        src = self.source
        hint = source_hint(src.kind, src.hint) if src and src.hint else ""
        self.src_hint.value, self.src_hint.visible = hint, bool(hint)
        self._show_source_problems()
        self._render_source_panel()
        if rebuild_rows:
            self._build_rows(self.source_id)

    def _render_source_panel(self) -> None:
        """One line when the source is fine; the full panel for Change, no source, or a source with problems."""
        src = self.source
        valid = src is not None and not self._src_problem_count
        expanded = self.src_expanded or not valid
        self.done_btn.visible = valid
        self.src_summary.visible = not expanded
        self.src_title.visible = expanded
        self._src_full = display_name(src.name) if src else ""
        self._fit_source_name()
        if expanded != self.src_panel.visible:
            self._reveal(self.src_panel, expanded)

    def _build_rows(self, source_id: str | None, targets=None) -> None:
        self._remember_sync()
        if targets is None:
            targets = self.ctl.targets_for(source_id)
        running = self.ctl.running
        self.rows.clear()
        items: list[ft.Control] = []
        for i, t in enumerate(targets):
            if i:
                items.append(hairline())
            r = TargetRow(t, self.compact, t.id in self.sync_open, running, self._on_row_change, self.ctl.test_tone, lambda: self.page)
            self.rows[t.id] = r
            items.append(r.control)
        listeners = [t for t in targets if t.kind in ("bluetooth", "wired headphones")]
        if not listeners:
            items.insert(0, self.empty)
        self.empty.visible = not listeners
        self.list_col.controls = items
        self._update_actions()

    def _remember_sync(self) -> None:
        if self.rows:
            self.sync_open = {tid for tid, r in self.rows.items() if r.sync_open}

    def _on_row_change(self, state) -> None:
        self.ctl.update_target(state)
        self._schedule_save()
        self._update_actions()

    def _set_opt(self, key: str, value) -> None:
        self.ctl.set_option(key, value)
        self._show_source_problems()
        self._render_source_panel()
        self._schedule_save()
        self.page.update()

    def _schedule_save(self) -> None:
        if self._save_task:
            self._save_task.cancel()

        async def go():
            await asyncio.sleep(0.8)
            self._save_task = None
            self.ctl.save()
        self._save_task = self.page.run_task(go)

    # ================================================================== start / stop
    def toggle(self) -> None:
        if self.busy:
            return
        self.page.run_task(self.stop if self.ctl.running else self.start)

    async def start(self) -> None:
        src = self.source
        targets = [r.state for r in self.rows.values()]
        self.clear_banners(keep=("recovered",))
        pf = self.ctl.preflight(src.id if src else None, targets)
        self._show_most_important(pf.problems)
        if any(p.blocking for p in pf.problems):
            return
        if pf.confirm:
            def go(e=None):
                self.clear_banners()
                self.page.run_task(self._do_start, src.id, targets)
            self.add_banner(Problem("confirm", pf.confirm, "speakers"), level="warn",
                            actions=[(WORDS["continue"], go, True), (WORDS["cancel"], lambda e: self.clear_banners(), False)])
            return
        await self._do_start(src.id, targets)

    def _show_most_important(self, probs: list[Problem]) -> None:
        """Only one message at a time: blocking problems first; the others are only logged."""
        if not probs:
            return
        top = sorted(probs, key=lambda p: not p.blocking)[0]
        for p in probs:
            if p is not top:
                log.info("Also: %s", p.text)
        self.add_banner(top, level="bad" if top.blocking else "warn")

    def _ticked(self) -> int:
        return sum(1 for r in self.rows.values() if r.state.enabled)

    def _update_actions(self) -> None:
        """Prevent errors instead of reporting them: grey out Start/Calibrate when they can't work and say why."""
        if self.busy or self.ctl.running:
            return
        n = self._ticked()
        can_start = self.source is not None and n >= 1
        self.start_btn.disabled = not can_start
        self.cal_btn.disabled = n < 2
        if not self.rows:
            self.say(WORDS["hint_connect"], "mute")
        elif not can_start:
            self.say(WORDS["hint_tick_one"], "mute")
        elif n < 2:
            self.say(WORDS["hint_ready_one"], "mute")
        else:
            self.say(WORDS["ready"], "mute")
        safe_update(self.start_btn)
        safe_update(self.cal_btn)

    def say(self, text: str, tone: str = "mute") -> None:
        """Action-bar status line."""
        if (text, tone) == self._status:
            return
        self._status = (text, tone)
        self.status.value, self.status.color = text, T.tone_color(tone)
        safe_update(self.status)

    def _set_start_button(self, running: bool, label: str | None = None) -> None:
        b = self.start_btn
        b.content, b.icon = (label or WORDS["stop"], ft.Icons.STOP) if running else (label or WORDS["start"], ft.Icons.PLAY_ARROW)
        b.style = primary_style(alert=running)
        safe_update(b)

    def _set_busy(self, text: str, label: str | None = None) -> None:
        self.busy = True
        for b in (self.start_btn, self.cal_btn, self.refresh_btn):
            b.disabled = True
            safe_update(b)
        if label:
            self.start_btn.content = label
            safe_update(self.start_btn)
        self.say(text, "warn")

    async def _do_start(self, source_id: str, targets) -> None:
        self._set_busy(WORDS["starting"], WORDS["starting"])
        if self.scenery:
            self.scenery.freeze("running", True)               # a movie is about to play: stop the motion first
        self._set_glass_blur(True)                             # stop GPU backdrop-blur DPC spikes during playback
        try:
            probs = await asyncio.to_thread(self.ctl.start, source_id, targets)
        except Exception as exc:  # noqa: BLE001
            log.error("Start crashed", exc_info=True)
            probs = [Problem("start_failed", f"Couldn't start: {exc}", "trouble", True)]
        self._after_start(probs)

    def _after_start(self, probs: list[Problem]) -> None:
        self.busy = False
        self._show_most_important(probs)
        running = self.ctl.running
        self.start_btn.disabled = False
        self._set_start_button(running)
        self.cal_btn.disabled = running
        self.refresh_btn.disabled = running
        self.source_dd.disabled = running
        safe_update(self.cal_btn)
        safe_update(self.refresh_btn)
        safe_update(self.source_dd)
        for r in self.rows.values():
            r.set_running(running)
        self._update_speaker_btn()
        if not running:
            if self.scenery:
                self.scenery.freeze("running", False)
            self._set_glass_blur(False)
            self._update_actions()
        elif not any(p.blocking for p in probs):
            n = self._ticked()
            self.synced_until = time.monotonic() + 4.0           # a short "all good" moment, then the live status
            self.say(WORDS["synced_one"] if n == 1 else WORDS["synced_many"].format(n=n), "ok")

    async def stop(self) -> None:
        self._set_busy(WORDS["stopping"], WORDS["stopping"])
        await asyncio.to_thread(self.ctl.stop)
        self.busy = False
        self.synced_until = 0.0
        if self.scenery:
            self.scenery.freeze("running", False)              # the scenery wakes up again
        self._set_glass_blur(False)                            # restore backdrop blur now that audio has stopped
        for b in (self.start_btn, self.cal_btn, self.refresh_btn):
            b.disabled = False
            safe_update(b)
        self._set_start_button(False)
        self.source_dd.disabled = False
        safe_update(self.source_dd)
        for tid, r in self.rows.items():
            r.set_running(False)
            r.show_status("stopped")
        self._update_speaker_btn()
        self.meter.value = 0
        self._meter = 0.0
        safe_update(self.meter)
        self.clear_banners(keep=("recovered",))
        self._update_actions()

    def _update_speaker_btn(self) -> None:
        if self.ctl.speakers_mutable:
            muted = self.ctl.speakers_muted
            self.spk_btn.content = WORDS["unmute" if muted else "mute"]
            self.spk_btn.icon = ft.Icons.VOLUME_UP if muted else ft.Icons.VOLUME_OFF
            self.spk_btn.visible = True
        else:
            self.spk_btn.visible = False
        safe_update(self.spk_btn)

    def _set_glass_blur(self, playing: bool) -> None:
        """Set blur=0 on all glass panels while audio plays to stop GPU DPC latency spikes."""
        val = 0 if playing else T.BLUR
        for panel in self._glass_panels:
            panel.blur = val
            safe_update(panel)

    def toggle_speakers(self) -> None:
        self.ctl.toggle_speakers()
        self._update_speaker_btn()

    # ================================================================== calibration
    def ask_calibrate(self) -> None:
        if self.busy or self.ctl.running:
            return
        targets = [r.state for r in self.rows.values()]
        if sum(1 for t in targets if t.enabled) < 2:
            self.add_banner(Problem("cal_two", WORDS["cal_need_two"], "sync"), level="info")
            return
        self.clear_banners(keep=("recovered",))

        def go(e=None):
            self.clear_banners()
            self.page.run_task(self._do_calibrate, targets)
        self.add_banner(Problem("cal_intro", WORDS["cal_intro"], "sync"), level="info",
                        actions=[(WORDS["cal_start"], go, True), (WORDS["cancel"], lambda e: self.clear_banners(), False)])

    async def _do_calibrate(self, targets) -> None:
        self._set_busy(WORDS["calibrating"])
        error = None
        lines, delays = [], {}
        try:
            lines, delays = await asyncio.to_thread(
                self.ctl.calibrate, targets, lambda m: setattr(self, "_progress", m))
        except Exception as exc:  # noqa: BLE001
            log.error("Calibration failed", exc_info=True)
            error = str(exc)
        self._progress = None
        self.busy = False
        self.refresh_btn.disabled = False
        safe_update(self.refresh_btn)
        self._update_actions()
        if error:
            self.add_banner(Problem("cal_failed", f"Calibration failed: {error}", "sync"), level="bad")
            return
        for tid, ms in delays.items():
            if tid in self.rows:
                self.rows[tid].set_delay(ms)
        ok = all(l.ok for l in lines)
        text = "\n".join(f"{l.name}: {l.text}" if l.ok else f"{l.name}: not heard. {l.text}" for l in lines)
        if delays:
            text += f"\n{WORDS['cal_done']}"
        self.add_banner(Problem("cal_result", text, "sync"), level="ok" if ok else "warn")

    # ================================================================== live updates
    async def _tick_loop(self) -> None:
        while not self._closing:
            try:
                self._update_live()
                self._drain_log()
                self._ticks += 1
                if self._ticks % 5 == 0 and self.scenery:
                    self.scenery.freeze("anim_off", not animations_enabled())
                if self.pref == "system" and self._ticks % 8 == 0 and T.system_mode() != self.eff and self._effective() != self.eff:
                    await self._apply_effective()
            except Exception:  # noqa: BLE001 - the UI loop must survive anything
                log.error("UI update failed", exc_info=True)
            await asyncio.sleep(TICK_S)

    def _update_live(self) -> None:
        if self._progress and self.busy and not self.ctl.running:
            self.say(self._progress, "warn")
        snap = self.ctl.snapshot()
        if not snap or self.busy:
            return
        peak = min(1.0, snap.peak * 1.4)
        if abs(peak - self._meter) > 0.03 or (peak == 0 and self._meter):
            self._meter = peak
            self.meter.value = peak
            safe_update(self.meter)
        waiting = snap.capture_state == "waiting"
        for tid, s in snap.outputs.items():
            row = self.rows.get(tid)
            if not row:
                continue
            if waiting and s.state in ("buffering", "playing"):
                row.show_status("waiting")
            elif s.state == "playing":
                row.show_status("playing", f"{s.level_ms:.0f} ms" + (f" · {s.underruns} gaps" if s.underruns else ""))
            else:
                row.show_status(s.state)
        m, sec = divmod(int(snap.seconds), 60)
        if waiting:
            self.say(f"{m}:{sec:02d}  ·  {WORDS['waiting']}", "warn")
        elif snap.capture_state != "running":
            self.say(f"{m}:{sec:02d}  ·  Sound source {snap.capture_state}", "warn")
        elif time.monotonic() < self.synced_until:
            n = sum(1 for s in snap.outputs.values() if s.state == "playing") or self._ticked()
            self.say(WORDS["synced_one"] if n == 1 else WORDS["synced_many"].format(n=n), "ok")
        else:
            self.say(f"{m}:{sec:02d}  ·  {WORDS['running']}", "ok")

    def _drain_log(self) -> None:
        got = False
        try:
            while len(self._log_lines) < 5000:
                self._log_lines.append(log_setup.gui_queue.get_nowait())
                got = True
        except queue.Empty:
            pass
        if got:
            del self._log_lines[:-300]
            self._log_dirty = True
        if self._log_dirty and self.log_open:
            self._log_dirty = False
            self.log_text.value = "\n".join(self._log_lines)
            safe_update(self.log_text)

    # ================================================================== keyboard
    def _on_key(self, e) -> None:
        key = str(e.key)
        if key in (" ", "Space"):
            if not FOCUS.busy:
                self.toggle()
        elif key == "F1":
            self.show_page("help")
        elif key == "F5":
            self.page.run_task(self.refresh)
        elif key == "Escape" and self.page_name != "main":
            self.show_page("main")

    # ================================================================== window / tray
    async def _copy_text(self, text: str) -> None:
        try:
            await self.clipboard.set(text)
        except Exception:  # noqa: BLE001
            log.warning("Clipboard unavailable", exc_info=True)

    async def _on_window_event(self, e) -> None:
        t = e.type
        if t == ft.WindowEventType.CLOSE:
            await self.on_close()
        elif t == ft.WindowEventType.BLUR:
            self._away_later()
        elif t in (ft.WindowEventType.MINIMIZE, ft.WindowEventType.HIDE):
            self._cancel_away()
            if self.scenery:
                self.scenery.freeze("away", True)
        elif t in (ft.WindowEventType.FOCUS, ft.WindowEventType.RESTORE, ft.WindowEventType.SHOW):
            self._cancel_away()
            if self.scenery:
                self.scenery.freeze("away", False)

    def _cancel_away(self) -> None:
        if self._away_task:
            self._away_task.cancel()
            self._away_task = None

    def _away_later(self) -> None:
        self._cancel_away()

        async def go():
            await asyncio.sleep(AWAY_S)
            if self.scenery:
                self.scenery.freeze("away", True)
        self._away_task = self.page.run_task(go)

    def _start_tray(self) -> None:
        try:
            import pystray

            def put(cmd):
                return lambda: self.page.run_task(self._tray_cmd, cmd)
            menu = pystray.Menu(
                pystray.MenuItem("Show DuoSound", put("show"), default=True),
                pystray.MenuItem("Start / Stop", put("toggle")),
                pystray.MenuItem("Mute / unmute laptop speakers", put("speakers")),
                pystray.MenuItem("Help", put("help")),
                pystray.MenuItem("Donate", put("about")),
                pystray.MenuItem("Quit", put("quit")),
            )
            self.tray = pystray.Icon("DuoSound", make_app_icon(64), "DuoSound", menu)
            threading.Thread(target=self.tray.run, daemon=True, name="tray").start()
        except Exception:  # noqa: BLE001
            self.tray = None
            log.warning("Tray icon unavailable", exc_info=True)

    async def _tray_cmd(self, cmd: str) -> None:
        if cmd == "quit":
            await self.quit()
            return
        if cmd == "toggle":
            self.toggle()
            return
        if cmd == "speakers":
            self.toggle_speakers()
            return
        await self.show_window()
        if cmd in ("help", "about"):
            self.show_page(cmd)

    async def show_window(self) -> None:
        w = self.page.window
        w.visible, w.minimized = True, False
        self.page.update()
        await w.to_front()

    async def on_close(self) -> None:
        if self.ctl.running and self.tray is not None:
            self.page.window.visible = False
            self.page.update()
            try:
                self.tray.notify(WORDS["tray_hint"], "DuoSound")
            except Exception:  # noqa: BLE001
                pass
            return
        await self.quit()

    async def quit(self) -> None:
        if self._closing:
            return
        self._closing = True
        log.info("Quitting")
        try:
            self.ctl.save()
            await asyncio.to_thread(self.ctl.shutdown)    # always stops + restores Windows, even if a Stop was still running
        finally:
            if self.tray is not None:
                try:
                    self.tray.stop()
                except Exception:  # noqa: BLE001
                    pass
            await self.page.window.destroy()


def _prepare_client() -> None:
    """Unpack the Flet desktop client now (first run only). Windows Defender sometimes holds the freshly unpacked folder for a
    moment, which makes Flet's own rename fail once; trying again a little later works."""
    try:
        import flet_desktop
        ensure = flet_desktop.ensure_client_cached
    except Exception:  # noqa: BLE001
        return
    for attempt in range(4):
        try:
            ensure()
            return
        except Exception:  # noqa: BLE001
            log.warning("Preparing the Flet client failed (attempt %d)", attempt + 1, exc_info=True)
            time.sleep(1.5)


def run(ctl: AppController, recovered: bool = False) -> None:
    """Open the window and block until it is closed. The controller is always shut down (Windows settings restored) on the way out."""
    app = DuoApp(ctl, recovered)
    try:
        _prepare_client()
        ft.run(app.main)
    finally:
        try:
            ctl.shutdown()
        except Exception:  # noqa: BLE001
            log.error("Shutdown after window close failed", exc_info=True)
        if app.tray is not None:
            try:
                app.tray.stop()
            except Exception:  # noqa: BLE001
                pass
