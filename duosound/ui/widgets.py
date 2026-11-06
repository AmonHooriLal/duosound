"""Reusable window parts: scrollable list, headphone row, inline banner, hover tip. No audio code here."""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from typing import Callable

from . import theme as T


def bind_wraplength(label: ttk.Label, container: tk.Misc, pad: int = 0) -> None:
    """Keep a label's text wrapped to its container's width."""
    container.bind("<Configure>", lambda e: label.configure(wraplength=max(T.px(200), e.width - pad)), add="+")


def ellipsize(text: str, font: tkfont.Font, max_px: int) -> str:
    """`text` cut with an ellipsis so it measures at most `max_px` (binary search on the measured width)."""
    if font.measure(text) <= max_px:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.measure(text[:mid].rstrip() + "…") <= max_px:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + "…"


class Tooltip:
    """Small hover tip in the theme's colours. `text` is a callable returning the tip, or ''/None for no tip."""

    DELAY_MS = 450

    def __init__(self, widget: tk.Misc, text: Callable[[], str | None]):
        self.widget, self.text, self._job, self._tip = widget, text, None, None
        widget.bind("<Enter>", self._enter, add="+")
        for seq in ("<Leave>", "<ButtonPress>", "<Destroy>"):
            widget.bind(seq, self._hide, add="+")

    def _enter(self, e) -> None:
        self._hide()
        try:
            self._job = self.widget.after(self.DELAY_MS, lambda x=e.x_root, y=e.y_root: self._show(x, y))
        except tk.TclError:
            self._job = None

    def _show(self, x: int, y: int) -> None:
        self._job = None
        tip = self.text()
        if not tip:
            return
        try:
            self._tip = top = tk.Toplevel(self.widget)
            top.wm_overrideredirect(True)
            top.configure(bg=T.LINE)
            tk.Label(top, text=tip, bg=T.SURFACE_3, fg=T.TEXT, font=T.F_SMALL, padx=T.px(T.GAP_S),
                     pady=T.px(T.GAP_XS)).pack(padx=1, pady=1)
            top.wm_geometry(f"+{x + T.px(12)}+{y + T.px(18)}")
        except tk.TclError:
            self._tip = None

    def _hide(self, _e=None) -> None:
        try:
            if self._job:
                self.widget.after_cancel(self._job)
            if self._tip is not None:
                self._tip.destroy()
        except tk.TclError:
            pass
        self._job = self._tip = None


class ScrollFrame(ttk.Frame):
    """A vertically scrolling area. Put children in `.inner`."""

    def __init__(self, parent, style: str = "Surface.TFrame", max_height: int | None = None):
        super().__init__(parent, style=style)
        self.canvas = tk.Canvas(self, bg=T.SURFACE, highlightthickness=0, bd=0, height=T.px(150))
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style=style)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.max_height = max_height
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        for w in (self.canvas, self.inner):
            w.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
            w.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_inner(self, _e=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        h = self.inner.winfo_reqheight()
        if self.max_height:
            self.canvas.configure(height=min(h, self.max_height))
        overflow = h > self.canvas.winfo_height() + 2
        if overflow and not self.vbar.winfo_ismapped():
            self.vbar.pack(side="right", fill="y")
        elif not overflow and self.vbar.winfo_ismapped():
            self.vbar.pack_forget()

    def _wheel(self, e) -> None:
        if self.inner.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-e.delta / 120), "units")


class Banner(ttk.Frame):
    """Inline message (never a popup): icon, text, optional action buttons and a "How to fix" link."""

    ICONS = {"warn": "warning", "bad": "warning", "ok": "check", "info": "help"}

    def __init__(self, parent, text: str, level: str = "warn", help_topic: str | None = None,
                 on_help: Callable[[str], None] | None = None, actions: list[tuple[str, Callable, str]] | None = None,
                 on_dismiss: Callable | None = None):
        super().__init__(parent, style="Surface.TFrame", padding=(T.px(T.GAP_M), T.px(T.GAP_S)))
        color = {"warn": T.WARN, "bad": T.BAD, "ok": T.OK, "info": T.INFO}.get(level, T.WARN)   # per instance: follows light/dark
        ttk.Label(self, image=T.icon(self.ICONS.get(level, "warning"), T.ICON, color), style="Body.TLabel").grid(
            row=0, column=0, sticky="n", padx=(0, T.px(T.GAP_S)), pady=(T.px(2), 0))
        body = ttk.Frame(self, style="Surface.TFrame")
        body.grid(row=0, column=1, sticky="ew")
        self.columnconfigure(1, weight=1)
        msg = ttk.Label(body, text=text, style="Body.TLabel", justify="left")
        msg.pack(anchor="w", fill="x")
        bind_wraplength(msg, body)
        links = ttk.Frame(body, style="Surface.TFrame")
        if help_topic and on_help:
            ttk.Button(links, text=T.WORDS["how_to_fix"], style="Link.TButton", cursor="hand2",
                       command=lambda: on_help(help_topic)).pack(side="left")
        if links.winfo_children():
            links.pack(anchor="w", pady=(T.px(2), 0))
        btns = ttk.Frame(self, style="Surface.TFrame")
        btns.grid(row=0, column=2, sticky="e", padx=(T.px(T.GAP_M), 0))
        for label, cmd, style in actions or []:
            ttk.Button(btns, text=label, command=cmd, style=style).pack(side="left", padx=(T.px(T.GAP_XS), 0))
        if on_dismiss:
            ttk.Button(btns, image=T.icon("cross", T.ICON_SMALL, T.TEXT_3), style="SurfaceGhost.TButton",
                       command=on_dismiss).pack(side="left", padx=(T.px(T.GAP_XS), 0))


class _SliderBox:
    """Caption + (optional slider) + editable whole-number box + unit, kept in step with each other.

    Typing only accepts digits (max 4). Enter, leaving the box or the spin arrows clamp the number to the range, write it
    back and move the slider. The slider snaps to `snap`; typed numbers keep their exact value. With `length=0` there is
    no slider: just the number box with its arrows."""

    MAX_CHARS = 4

    def __init__(self, parent, caption: str, unit: str, lo: int, hi: int, step: int, length: int, snap: int,
                 value: int, on_value: Callable[[int], None]):
        self.lo, self.hi, self.step, self.snap, self.on_value = lo, hi, step, snap, on_value
        self.value = self.clamp(value)
        self._sync = False
        self.frame = ttk.Frame(parent, style="Surface.TFrame")
        col = 0
        ttk.Label(self.frame, text=caption, style="Small.TLabel").grid(row=0, column=col)
        col += 1
        self.scale = None
        if length:
            self.frame.columnconfigure(col, weight=1)                  # the slider gives way first when the row gets tight
            self.scale = ttk.Scale(self.frame, from_=lo, to=hi, orient="horizontal", length=length, command=self._slid)
            self.scale.grid(row=0, column=col, sticky="ew", padx=(T.px(T.GAP_S), T.px(T.GAP_S)))
            self.scale.bind("<MouseWheel>", lambda e: "break")        # wheel over a slider must not move it by accident
            col += 1
        self.var = tk.StringVar()
        self.box = ttk.Spinbox(self.frame, from_=lo, to=hi, increment=step, width=5, justify="right", format="%.0f",
                               textvariable=self.var, validate="key", command=self._commit,
                               validatecommand=(self.frame.register(self._valid), "%P"))
        self.box.grid(row=0, column=col, padx=(0 if length else T.px(T.GAP_S), 0))
        ttk.Label(self.frame, text=unit, style="Value.TLabel", width=3, anchor="w").grid(
            row=0, column=col + 1, padx=(T.px(T.GAP_XS), 0))
        self.box.bind("<MouseWheel>", self._wheel)
        for seq in ("<Return>", "<KP_Enter>", "<FocusOut>"):
            self.box.bind(seq, self._commit, add="+")
        self.show(self.value)

    def clamp(self, n) -> int:
        return max(self.lo, min(self.hi, int(n)))

    def _valid(self, proposed: str) -> bool:
        return proposed == "" or (len(proposed) <= self.MAX_CHARS and proposed.isascii() and proposed.isdigit())

    def show(self, v: int) -> None:
        """Put a value on the slider and in the box without telling anyone."""
        self.value = v = self.clamp(v)
        self._sync = True
        try:
            if self.scale is not None:
                self.scale.set(v)
        finally:
            self._sync = False
        self.var.set(str(v))

    def _slid(self, raw) -> None:
        if self._sync:
            return
        v = self.clamp(round(float(raw) / self.snap) * self.snap)
        self.var.set(str(v))
        if v != self.value:
            self.value = v
            self.on_value(v)

    def _typed(self) -> int:
        try:
            text = self.var.get().strip()
        except tk.TclError:
            return self.value
        return self.clamp(int(text)) if text.isascii() and text.isdigit() else self.value      # empty/odd text: keep old

    def _commit(self, _e=None) -> None:
        try:
            v = self._typed()
            changed = v != self.value
            self.show(v)                                                # clamp, write back, move the slider
            if changed:
                self.on_value(v)
        except tk.TclError:                                             # row was destroyed while focus left
            pass

    def _wheel(self, e) -> str:
        v = self.clamp(self._typed() + self.step * (1 if e.delta > 0 else -1))
        changed = v != self.value
        self.show(v)
        if changed:
            self.on_value(v)
        return "break"


class TargetRow:
    """One pair of headphones, one self-contained row that adapts to the list width.

    Wide:   [x] icon  name / kind . status . Delay 35 ms        Volume [ 83 ] %   [Test]  Adjust sync
    Narrow: [x] icon  name / kind . status . Delay 35 ms
                      Volume [ 83 ] %   [Test]  Adjust sync
    "Adjust sync" opens a line below with the delay slider and number box (hidden by default).

    The wide/narrow choice is made for the whole list once the names are measured (after_idle) and again on every
    resize; a name too long for the room is cut with an ellipsis and shows in full in a hover tip."""

    MIN_NAME_PX = 140          # a name is shortened (instead of moving the controls below it) only down to this width

    def __init__(self, parent: ttk.Frame, row: int, state, on_change: Callable, on_test: Callable[[str, float], None]):
        self.state, self.on_change = state, on_change
        self.widgets: list[tk.Widget] = []
        self._narrow = False
        self._parent = parent
        self._full_name = T.display_name(state.name)
        self.sync_open = False
        parent.columnconfigure(0, weight=1)
        self._siblings = parent.__dict__.setdefault("_duo_rows", [])   # all rows in this list switch layout together
        self._siblings[:] = [r for r in self._siblings if r.frame.winfo_exists()] if self._siblings else []
        for w in parent.grid_slaves(row=0):                 # old shared column captions: captions live in each row now
            if row > 0 and isinstance(w, ttk.Label):
                w.grid_remove()
        self.frame = ttk.Frame(parent, style="Surface.TFrame")
        self.frame.grid(row=row, column=0, columnspan=8, sticky="ew")
        if row > 1:                                          # hairline between rows
            ttk.Frame(self.frame, style="Line.TFrame", height=1).pack(fill="x")
        box = ttk.Frame(self.frame, style="Surface.TFrame")
        box.pack(fill="x", padx=T.px(T.GAP_M), pady=T.px(T.GAP_S))
        box.columnconfigure(0, weight=1)
        self._box = box

        left = ttk.Frame(box, style="Surface.TFrame")
        left.grid(row=0, column=0, sticky="ew")
        self.enabled = tk.BooleanVar(value=state.enabled)
        self.chk = ttk.Checkbutton(left, variable=self.enabled, command=self._changed, takefocus=True)
        self.chk.pack(side="left", padx=(0, T.px(T.GAP_XS)))
        kind_icon = "bluetooth" if state.kind == "bluetooth" else "plug" if state.kind == "wired headphones" else "speaker"
        ttk.Label(left, image=T.icon(kind_icon, T.ICON, T.TEXT_2), style="Body.TLabel").pack(side="left", padx=(0, T.px(T.GAP_S)))
        name = ttk.Frame(left, style="Surface.TFrame")
        name.pack(side="left", fill="x")
        self._name = name
        self._font = tkfont.Font(root=parent, font=T.F_BODY_BOLD)
        self.name_lbl = ttk.Label(name, text=self._full_name, style="Name.TLabel")
        self.name_lbl.pack(anchor="w")
        Tooltip(self.name_lbl, lambda: self._full_name if self.name_lbl.cget("text") != self._full_name else None)
        sub = ttk.Frame(name, style="Surface.TFrame")
        sub.pack(anchor="w")
        self._sub = sub
        ttk.Label(sub, text=T.KIND_LABEL.get(state.kind, state.kind), style="Small.TLabel").pack(side="left")
        self.status = ttk.Label(sub, text="", style="Small.TLabel", compound="left")   # live state, under the name
        self.status.pack(side="left", padx=(T.px(T.GAP_S), 0))
        self.delay_cap = ttk.Label(sub, text="", style="Value.TLabel")                   # "Delay 35 ms" while sync is closed

        self.ctl = ttk.Frame(box, style="Surface.TFrame")
        self.vol_ctl = _SliderBox(self.ctl, T.WORDS["col_volume"], T.WORDS.get("unit_pct", "%"), 0, 150, 1,
                                  0, 1, round(state.volume * 100), self._on_vol)
        self.vol_ctl.frame.grid(row=0, column=0)
        self.test = ttk.Button(self.ctl, text=T.WORDS["test"], style="Row.TButton",
                               command=lambda: on_test(state.id, self.state.volume))
        self.test.grid(row=0, column=1, padx=(T.px(T.GAP_L), 0))
        self.sync_btn = ttk.Button(self.ctl, text=T.WORDS["adjust_sync"], style="Link.TButton", cursor="hand2", width=11,
                                   command=self.toggle_sync)
        self.sync_btn.grid(row=0, column=2, padx=(T.px(T.GAP_S), 0))

        # delay controls: built now (so set_delay always works) but shown only after "Adjust sync"
        self.sync = ttk.Frame(box, style="Surface.TFrame")
        self.delay_ctl = _SliderBox(self.sync, T.WORDS["col_delay"], T.WORDS.get("unit_ms", "ms"), 0, 1000, 5,
                                    T.px(T.DELAY_SLIDER_W), 5, state.delay_ms, self._on_delay)
        self.delay_ctl.frame.pack(side="left")
        ttk.Label(self.sync, text=T.WORDS["sync_help"], style="Small.TLabel").pack(side="left", padx=(T.px(T.GAP_M), 0))
        self.delay, self.vol = self.delay_ctl.scale, self.vol_ctl.scale          # the sliders (volume has none now)
        self.delay_box, self.vol_box = self.delay_ctl.box, self.vol_ctl.box      # the number boxes
        self._siblings.append(self)
        self._show_delay_caption()
        self._place(False)
        self.frame.bind("<Configure>", lambda e: self.schedule_layout() if e.width > 1 else None)
        sub.bind("<Configure>", lambda e: self.schedule_layout())
        self.schedule_layout()

    # ---------------------------------------------------------------- layout
    def _indent(self) -> int:
        x = self._name.winfo_x()
        return x if x > 0 else T.px(T.GAP_XS + T.GAP_S + T.ICON + 22)

    def _place(self, narrow: bool) -> None:
        self._narrow = narrow
        if narrow:
            self.ctl.grid(row=1, column=0, sticky="w", padx=(self._indent(), 0), pady=(T.px(T.GAP_S), 0))
        else:
            self.ctl.grid(row=0, column=1, sticky="e", padx=(T.px(T.GAP_M), 0), pady=0)
        self._place_sync()

    def _place_sync(self) -> None:
        if self.sync_open:
            self.sync.grid(row=2, column=0, columnspan=2, sticky="w", padx=(self._indent(), 0), pady=(T.px(T.GAP_S), 0))
        else:
            self.sync.grid_remove()

    def schedule_layout(self) -> None:
        """Re-run the one-line / two-line decision when Tk is idle (names are measured by then). One job per list."""
        p = self._parent
        if getattr(p, "_duo_layout_job", None):
            return
        try:
            p._duo_layout_job = p.after_idle(lambda: self._run_layout(p))
        except tk.TclError:
            pass

    @staticmethod
    def _run_layout(p) -> None:
        p._duo_layout_job = None
        try:
            rows = [r for r in p.__dict__.get("_duo_rows", []) if r.frame.winfo_exists()]
            if rows:
                rows[0]._layout(rows)
        except tk.TclError:
            pass

    def _room(self, wide: bool) -> int:
        """Width left for the name block in the wide or the narrow arrangement."""
        total = self._box.winfo_width() - self._name.winfo_x() - T.px(T.GAP_S)
        return total - (self.ctl.winfo_reqwidth() + T.px(T.GAP_M) if wide else 0)

    def _layout(self, rows: list["TargetRow"]) -> None:
        if self.frame.winfo_width() <= 1:
            return
        for r in rows:
            r.frame.update_idletasks()

        def need(r: "TargetRow") -> int:           # least width the block may get: the status line, and the name down to a floor
            return max(r._sub.winfo_reqwidth(), min(r._font.measure(r._full_name), T.px(self.MIN_NAME_PX)))
        wide = all(r._room(True) >= need(r) for r in rows)      # the tightest row decides for every row (consistent list)
        for r in rows:
            if r._narrow == wide:
                r._place(not wide)
            r._fit_name(r._room(wide))
            r._place_sync()

    def _fit_name(self, room: int) -> None:
        text = ellipsize(self._full_name, self._font, max(T.px(60), room - T.px(6)))
        if text != self.name_lbl.cget("text"):
            self.name_lbl.configure(text=text)

    # ---------------------------------------------------------------- sync
    def toggle_sync(self) -> None:
        self.set_sync_open(not self.sync_open)

    def set_sync_open(self, open_: bool) -> None:
        self.sync_open = open_
        self.sync_btn.configure(text=T.WORDS["hide_sync" if open_ else "adjust_sync"])
        self._place_sync()
        self._show_delay_caption()

    def _show_delay_caption(self) -> None:
        ms = int(self.state.delay_ms)
        if ms > 0 and not self.sync_open:
            self.delay_cap.configure(text=T.WORDS["delay_caption"].format(ms=ms))
            self.delay_cap.pack(side="left", padx=(T.px(T.GAP_S), 0))
        else:
            self.delay_cap.pack_forget()

    # ---------------------------------------------------------------- values
    def _changed(self) -> None:
        self.state.enabled = self.enabled.get()
        self.on_change(self.state)

    def _on_delay(self, ms: int, notify: bool = True) -> None:
        self.state.delay_ms = int(ms)
        self._show_delay_caption()
        if notify:
            self.on_change(self.state)

    def _on_vol(self, pct: int, notify: bool = True) -> None:
        self.state.volume = int(pct) / 100
        if notify:
            self.on_change(self.state)

    def set_delay(self, ms: int) -> None:
        ms = int(round(max(0, min(1000, ms)) / 5) * 5)
        self.delay_ctl.show(ms)
        self._on_delay(ms)

    def set_running(self, running: bool) -> None:
        self.chk.state(["disabled"] if running else ["!disabled"])    # delay and volume stay editable: they apply live

    def show_status(self, key: str, extra: str = "") -> None:
        text, color = T.STATUS.get(key, (key, T.TEXT_3))
        if extra:
            text = f"{text} · {extra}" if text else extra
        self.status.configure(text=f"{text}" if text else "", foreground=color,
                              image=T.icon("dot", 10, color) if text else "")
