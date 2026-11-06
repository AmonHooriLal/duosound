"""Reusable Flet controls: glass panel, buttons, number field, banner, headphone row.

All colours are theme colour names from tokens.py, so a light/dark switch needs no re-colouring here."""
from __future__ import annotations

import asyncio
from typing import Callable

import flet as ft

from ..controller import TargetState
from . import tokens as T
from .words import KIND_LABEL, STATUS, WORDS, display_name


# ------------------------------------------------------------------------------------------------ small helpers
def txt(value: str, size: float = T.S_BODY, bold: bool = False, color: str = T.TEXT, **kw) -> ft.Text:
    return ft.Text(value, size=size, color=color, font_family=T.FONT_BOLD if bold else T.FONT, **kw)


def safe_update(ctrl: ft.Control) -> None:
    """Update a control if it is on the page (rows are built before they are attached)."""
    try:
        ctrl.update()
    except Exception:  # noqa: BLE001 - not attached yet, or the window is closing
        pass


def page_of(ctrl: ft.Control):
    """The page a control is on, or None when it is not attached yet (Flet raises instead of returning None)."""
    try:
        return ctrl.page
    except Exception:  # noqa: BLE001
        return None


class FocusGuard:
    """Which interactive controls have keyboard focus. Space starts/stops only when none has (a focused button or field
    uses Space itself)."""

    def __init__(self) -> None:
        self.focused: set[int] = set()

    def watch(self, ctrl):
        key = id(ctrl)
        ctrl.on_focus = lambda e: self.focused.add(key)
        ctrl.on_blur = lambda e: self.focused.discard(key)
        return ctrl

    @property
    def busy(self) -> bool:
        return bool(self.focused)


FOCUS = FocusGuard()


def hairline() -> ft.Divider:
    return ft.Divider(height=1, thickness=1, color=T.HAIRLINE)


def glass(content, radius: float = T.RADIUS_PANEL, padding=None, boost: float = 1.0, **kw) -> ft.Container:
    """Frosted panel: backdrop blur + translucent tint + 1 px light border + a soft shadow."""
    return ft.Container(
        content=content, blur=T.BLUR, border_radius=radius,
        padding=padding if padding is not None else ft.Padding.symmetric(horizontal=T.GAP_L, vertical=T.GAP_M),
        bgcolor=T.glass_fill(min(1.0, T.GLASS_A * boost)), border=ft.Border.all(1, T.BORDER),
        shadow=ft.BoxShadow(blur_radius=28, offset=ft.Offset(0, 8), color=ft.Colors.with_opacity(0.22, "#000000")),
        animate_opacity=ft.Animation(180, ft.AnimationCurve.EASE_OUT), **kw)


def _state(default, disabled=None):
    d = {ft.ControlState.DEFAULT: default}
    if disabled is not None:
        d[ft.ControlState.DISABLED] = disabled
    return d


def _style(size=T.S_BODY, bold=False, fg=T.TEXT, bg=None, side=None, radius=T.RADIUS_CONTROL, padding=None, disabled_fg=None,
           disabled_bg=None) -> ft.ButtonStyle:
    return ft.ButtonStyle(
        color=_state(fg, disabled_fg or ft.Colors.with_opacity(0.45, fg)),
        icon_color=_state(fg, disabled_fg or ft.Colors.with_opacity(0.45, fg)),
        bgcolor=_state(bg if bg is not None else ft.Colors.TRANSPARENT, disabled_bg) if (bg is not None or disabled_bg) else None,
        side=side, shape=ft.RoundedRectangleBorder(radius=radius), padding=padding,
        text_style=ft.TextStyle(size=size, font_family=T.FONT_BOLD if bold else T.FONT),
        overlay_color=ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE))


def primary_style(alert: bool = False) -> ft.ButtonStyle:
    bg, fg = (T.ALERT, T.ON_ALERT) if alert else (T.ACCENT, T.ON_ACCENT)
    return _style(T.S_NAME, True, fg, bg, padding=ft.Padding.symmetric(horizontal=22),
                  disabled_bg=ft.Colors.with_opacity(0.16, ft.Colors.ON_SURFACE), disabled_fg=T.TEXT_2)


def primary_button(label: str, icon, on_click, alert: bool = False, **kw) -> ft.FilledButton:
    """The one amber button (red while it means Stop). Dark text on amber: white fails contrast."""
    btn = ft.FilledButton(content=label, icon=icon, on_click=on_click, height=44, **kw)
    btn.style = primary_style(alert)
    return FOCUS.watch(btn)


def secondary_button(label: str, icon, on_click, size: float = T.S_NAME, height: float = 44, **kw) -> ft.OutlinedButton:
    btn = ft.OutlinedButton(content=label, icon=icon, on_click=on_click, height=height, **kw)
    btn.style = _style(size, False, T.TEXT, None, side=_state(ft.BorderSide(1, ft.Colors.with_opacity(0.42, ft.Colors.ON_SURFACE)),
                                                              ft.BorderSide(1, T.HAIRLINE)),
                       padding=ft.Padding.symmetric(horizontal=16))
    return FOCUS.watch(btn)


def link_button(label: str, on_click, icon=None, size: float = T.S_BODY, color: str = T.LINK, **kw) -> ft.TextButton:
    btn = ft.TextButton(content=label, icon=icon, on_click=on_click, **kw)
    btn.style = _style(size, False, color, padding=ft.Padding.symmetric(horizontal=8, vertical=4))
    return FOCUS.watch(btn)


def icon_button(icon, tooltip: str, on_click, size: float = 20, color: str = T.TEXT) -> ft.IconButton:
    ib = ft.IconButton(icon=icon, icon_size=size, tooltip=tooltip, on_click=on_click, icon_color=color,
                       style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=T.RADIUS_CONTROL),
                                            overlay_color=ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)))
    return FOCUS.watch(ib)


class NumField:
    """A whole-number box with - / + and a unit: digits only, clamped to lo..hi, committed live."""

    def __init__(self, value: int, lo: int, hi: int, step: int, unit: str, on_change: Callable[[int], None], tip: str):
        self.lo, self.hi, self.step, self.on_change = lo, hi, step, on_change
        self.value = self._clamp(value)
        self.tf = ft.TextField(
            value=str(self.value), width=60, dense=True, text_align=ft.TextAlign.CENTER, text_size=T.S_BODY, color=T.TEXT,
            text_style=ft.TextStyle(font_family=T.FONT), keyboard_type=ft.KeyboardType.NUMBER, filled=True, fill_color=T.FIELD,
            content_padding=ft.Padding.symmetric(horizontal=4, vertical=8), input_filter=ft.NumbersOnlyInputFilter(),
            tooltip=tip, on_change=self._typed, on_blur=self._commit, on_submit=self._commit,
            border={ft.ControlState.DEFAULT: ft.OutlineInputBorder(side=ft.BorderSide(1, ft.Colors.with_opacity(0.32, ft.Colors.ON_SURFACE)),
                                                                   border_radius=T.RADIUS_CONTROL),
                    ft.ControlState.FOCUSED: ft.OutlineInputBorder(side=ft.BorderSide(2, T.LINK), border_radius=T.RADIUS_CONTROL)})
        self.tf.on_focus = lambda e: FOCUS.focused.add(id(self.tf))
        self._unit = txt(unit, T.S_BODY, color=T.TEXT_2)
        self.minus = icon_button(ft.Icons.REMOVE, f"{tip}: less", lambda e: self.nudge(-self.step), 18)
        self.plus = icon_button(ft.Icons.ADD, f"{tip}: more", lambda e: self.nudge(self.step), 18)
        self.control = ft.Row([self.minus, self.tf, self._unit, self.plus], spacing=0, tight=True,
                              vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _clamp(self, n) -> int:
        try:
            return max(self.lo, min(self.hi, int(n)))
        except (TypeError, ValueError):
            return self.lo

    def _typed(self, e) -> None:
        digits = "".join(ch for ch in (self.tf.value or "") if ch.isdigit())[:4]
        if digits:
            n = self._clamp(digits)
            shown = str(n) if int(digits) != n or digits != str(int(digits)) else digits
            if shown != self.tf.value:
                self.tf.value = shown
                safe_update(self.tf)
            self._set(n)
        elif self.tf.value:
            self.tf.value = ""
            safe_update(self.tf)

    def _commit(self, e) -> None:
        FOCUS.focused.discard(id(self.tf))
        self.tf.value = str(self.value)
        safe_update(self.tf)

    def _set(self, n: int, notify: bool = True) -> None:
        if n != self.value:
            self.value = n
            if notify:
                self.on_change(n)

    def nudge(self, delta: int) -> None:
        n = self._clamp(round((self.value + delta) / self.step) * self.step if self.step > 1 else self.value + delta)
        self.tf.value = str(n)
        safe_update(self.tf)
        self._set(n)

    def show(self, n: int) -> None:
        self.value = self._clamp(n)
        self.tf.value = str(self.value)
        safe_update(self.tf)


# ------------------------------------------------------------------------------------------------ banner
LEVEL_ICON = {"info": (ft.Icons.INFO_OUTLINE, T.TEXT_2), "ok": (ft.Icons.CHECK_CIRCLE_OUTLINE, T.OK),
              "warn": (ft.Icons.WARNING_AMBER_ROUNDED, T.LINK), "bad": (ft.Icons.ERROR_OUTLINE, T.ALERT)}
BANNER_MS = {"info": 5000, "ok": 6000, "warn": 8000, "bad": 9000}


class Banner:
    """ONE message at a time. Plain messages vanish by themselves (4 s + 50 ms per character, paused while the pointer is on
    them); questions with buttons stay until answered."""

    def __init__(self, code: str, text: str, level: str, help_topic: str | None, on_help, actions=None, on_close=None):
        self.code, self.text, self.level = code, text, level
        self.on_close = on_close
        self.timeout: float | None = None if actions else min(15.0, (BANNER_MS.get(level, 8000) + 50 * len(text)) / 1000)
        self._task: asyncio.Task | None = None
        ic, col = LEVEL_ICON.get(level, LEVEL_ICON["info"])
        parts: list[ft.Control] = [ft.Icon(ic, size=22, color=col),
                                   ft.Container(txt(text, T.S_BODY, selectable=True), expand=True, padding=ft.Padding.symmetric(vertical=2))]
        if help_topic:
            parts.append(link_button(WORDS["how_to_fix"], lambda e: on_help(help_topic)))
        for label, fn, primary in actions or []:
            parts.append(primary_button(label, None, fn) if primary else secondary_button(label, None, fn, T.S_BODY, 36))
        if not actions:
            parts.append(icon_button(ft.Icons.CLOSE, WORDS["dismiss"], lambda e: self.close(), 18, T.TEXT_2))
        self.control = glass(ft.Row(parts, spacing=T.GAP_S, vertical_alignment=ft.CrossAxisAlignment.CENTER), radius=14,
                             padding=ft.Padding.symmetric(horizontal=T.GAP_M, vertical=T.GAP_S), boost=1.25,
                             opacity=0, on_hover=self._hover)

    def close(self) -> None:
        self.cancel()
        if self.on_close:
            self.on_close(self)

    def cancel(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    def arm(self, page: ft.Page) -> None:
        self.cancel()
        if self.timeout:
            self._task = page.run_task(self._expire)

    async def _expire(self) -> None:
        await asyncio.sleep(self.timeout or 0)
        self._task = None
        self.close()

    def _hover(self, e) -> None:
        inside = str(getattr(e, "data", "")).lower() == "true"
        page = page_of(self.control)
        if inside:
            self.cancel()
        elif page is not None:
            self.arm(page)


# ------------------------------------------------------------------------------------------------ headphone row
KIND_ICON = {"bluetooth": ft.Icons.BLUETOOTH, "wired headphones": ft.Icons.CABLE}


class TargetRow:
    """One pair of headphones: tick, type icon, name (ellipsis + tooltip), kind · live status, Volume, Test, Adjust sync.

    Wide: one line. Compact: the controls move to a second line. 'Adjust sync' fades in a Delay line (0-1000 ms)."""

    def __init__(self, state: TargetState, compact: bool, sync_open: bool, running: bool, on_change: Callable[[TargetState], None],
                 on_test: Callable[[str, float], None], page_getter: Callable[[], ft.Page]):
        self.state, self.on_change, self._page = state, on_change, page_getter
        self.sync_open = sync_open
        self.full = display_name(state.name)
        self.chk = ft.Checkbox(value=state.enabled, on_change=self._ticked, disabled=running, active_color=T.ACCENT,
                               check_color=T.ON_ACCENT, border_side=ft.BorderSide(2, T.TEXT_2), tooltip=f"Use {self.full}")
        FOCUS.watch(self.chk)
        icon = KIND_ICON.get(state.kind, ft.Icons.SPEAKER_GROUP if state.kind == "speakers" else ft.Icons.SPEAKER)
        self.name = txt(self.full, T.S_NAME, True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.kind = txt(KIND_LABEL.get(state.kind, state.kind), T.S_CAPTION, color=T.TEXT_2)
        self.dot = ft.Icon(ft.Icons.CIRCLE, size=8, color=T.TEXT_2, visible=False)
        self.status = txt("", T.S_CAPTION, color=T.TEXT_2)
        self.delay_cap = txt("", T.S_CAPTION, color=T.TEXT_2, visible=False)
        sub = ft.Row([self.kind, self.dot, self.status, self.delay_cap], spacing=6, wrap=False,
                     vertical_alignment=ft.CrossAxisAlignment.CENTER)
        namebox = ft.Column([ft.Container(self.name, tooltip=self.full), sub], spacing=1, expand=True)
        left = ft.Row([self.chk, ft.Icon(icon, size=22, color=T.TEXT_2), namebox], spacing=T.GAP_S, expand=True,
                      vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.vol = NumField(round(state.volume * 100), 0, 150, 5, "%", self._on_vol, "Volume")
        self.test = secondary_button(WORDS["test"], None, lambda e: on_test(state.id, self.state.volume), T.S_BODY, 36)
        self.sync_btn = link_button(WORDS["hide_sync" if sync_open else "adjust_sync"], lambda e: self.toggle_sync())
        self.sync_btn.width = 106                      # same width for "Adjust sync" / "Hide sync": nothing shifts
        controls = ft.Row([ft.Icon(ft.Icons.VOLUME_UP, size=18, color=T.TEXT_2, tooltip=WORDS["col_volume"]), self.vol.control, self.test, self.sync_btn],
                          spacing=T.GAP_S, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.delay = NumField(state.delay_ms, 0, 1000, 5, "ms", self._on_delay, "Delay")
        self.sync_row = ft.Container(
            ft.Row([txt(WORDS["col_delay"], T.S_BODY, color=T.TEXT_2), self.delay.control,
                    txt(WORDS["sync_help"], T.S_CAPTION, color=T.TEXT_2)], spacing=T.GAP_S, wrap=True,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(left=44, top=4), visible=sync_open, opacity=1 if sync_open else 0,
            animate_opacity=ft.Animation(180, ft.AnimationCurve.EASE_OUT))
        if compact:
            top = ft.Column([left, ft.Container(controls, padding=ft.Padding.only(left=44))], spacing=T.GAP_XS)
        else:
            top = ft.Row([left, controls], spacing=T.GAP_M, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.control = ft.Container(ft.Column([top, self.sync_row], spacing=2), padding=ft.Padding.symmetric(vertical=T.GAP_S))
        self._caption()

    # -- events
    def _ticked(self, e) -> None:
        self.state.enabled = bool(self.chk.value)
        self.on_change(self.state)

    def _on_vol(self, pct: int) -> None:
        self.state.volume = pct / 100
        self.on_change(self.state)

    def _on_delay(self, ms: int) -> None:
        self.state.delay_ms = int(ms)
        self._caption()
        self.on_change(self.state)

    def _caption(self) -> None:
        ms = int(self.state.delay_ms)
        show = ms > 0 and not self.sync_open
        self.delay_cap.value = WORDS["delay_caption"].format(ms=ms) if show else ""
        self.delay_cap.visible = show
        safe_update(self.delay_cap)

    def toggle_sync(self) -> None:
        self.set_sync_open(not self.sync_open)

    def set_sync_open(self, open_: bool) -> None:
        self.sync_open = open_
        self.sync_btn.content = WORDS["hide_sync" if open_ else "adjust_sync"]
        safe_update(self.sync_btn)
        page = self._page()
        if open_:
            self.sync_row.visible, self.sync_row.opacity = True, 0
        else:
            self.sync_row.opacity = 0
        safe_update(self.sync_row)
        if page:
            async def settle():
                await asyncio.sleep(0.03 if self.sync_open else 0.2)
                if self.sync_open:
                    self.sync_row.opacity = 1
                else:
                    self.sync_row.visible = False
                safe_update(self.sync_row)
            page.run_task(settle)
        self._caption()

    # -- values pushed in from outside
    def set_delay(self, ms: int) -> None:
        ms = int(round(max(0, min(1000, ms)) / 5) * 5)
        self.delay.show(ms)
        self._on_delay(ms)

    def set_running(self, running: bool) -> None:
        self.chk.disabled = running           # delay and volume stay editable: they apply live
        safe_update(self.chk)

    def show_status(self, key: str, extra: str = "") -> None:
        text, tone = STATUS.get(key, (key, "mute"))
        if extra:
            text = f"{text} · {extra}" if text else extra
        col = T.tone_color(tone)
        if (self.status.value, self.status.color) == (text, col):
            return
        self.status.value, self.status.color = text, col
        self.dot.visible, self.dot.color = bool(text), col
        safe_update(self.status)
        safe_update(self.dot)
