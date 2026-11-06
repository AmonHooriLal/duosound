"""DuoSound main window: header, pages (main / Help / About & donate), action bar, log, footer, tray icon.

Talks only to AppController (duosound/controller.py). Slow controller calls (start, stop, calibrate) run in worker
threads and report back through a queue that _tick() reads every 250 ms, so the window never freezes."""
from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from PIL import ImageTk

from .. import __version__, help_text, log_setup
from ..controller import AppController, Problem
from . import theme as T
from .about_page import AboutPage
from .help_page import HelpPage
from .widgets import Banner, ScrollFrame, TargetRow, Tooltip, bind_wraplength, ellipsize

log = log_setup.get("ui")
TICK_MS = 250


class MainWindow:
    def __init__(self, ctl: AppController, recovered: bool = False) -> None:
        self.ctl = ctl
        self.q: "queue.Queue[tuple]" = queue.Queue()
        self.rows: dict[str, TargetRow] = {}
        self._sources = []
        self._busy = False
        self._save_job = None
        self._page = "main"
        self.tray = None
        self._ticks = 0
        self._status_now = (T.WORDS["ready"], "TEXT_2")      # (text, token name): the colour is re-read after a theme switch
        self._row_status: dict[str, tuple[str, str]] = {}
        self._tag_shown = True
        self._opts_open = False
        self._src_expanded = False           # source section: False = one line once a valid source is picked
        self._sync_open: set[str] = set()    # rows whose "Adjust sync" is open (survives list rebuilds)
        self._synced_until = 0.0             # monotonic time until which the "playing in sync" message shows
        saved_mode = self.ctl.cfg.get("theme", "dark")
        self._mode = saved_mode if saved_mode in T.MODES else "dark"
        T.use(self._mode)

        self.root = tk.Tk()
        self.root.title(T.APP_NAME)
        T.apply_styles(self.root)
        self._apply_banner_colors()
        self._app_icon = ImageTk.PhotoImage(T.make_app_icon(64))
        self.root.iconphoto(True, self._app_icon)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.minsize(min(T.px(T.MIN_W), sw - 40), min(T.px(T.MIN_H), sh - 90))   # never larger than the screen
        geo = self.ctl.cfg.get("geometry")
        if geo:
            try:
                self.root.geometry(geo)
            except tk.TclError:
                pass
        else:
            self.root.geometry(f"{min(T.px(T.DEFAULT_W), sw - 40)}x{min(T.px(T.DEFAULT_H), sh - 90)}")
        self._build()
        self._title_bar()
        self.root.bind("<Configure>", self._on_root_configure, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind_all("<KeyPress-space>", self._on_space)
        self.root.bind_all("<F1>", lambda e: self.show_page("help"))
        self.root.bind_all("<F5>", lambda e: self.refresh())
        self._start_tray()
        self.refresh()
        if recovered:
            self.add_banner(Problem("recovered", T.WORDS["recovered"], "trouble"), level="info", dismiss=True)
        self.root.after(TICK_MS, self._tick)

    # ================================================================== layout
    def _title_bar(self) -> None:
        """Title bar in the window's own colours: Windows 11 caption colours (attributes 35/36), plus the dark-mode flag
        for Windows 10 (attribute 20, or 19 before 20H1; 0 for the light palette). Silently ignored where unsupported -
        purely cosmetic."""
        try:
            import ctypes
            self.root.update_idletasks()
            hwnd = int(self.root.wm_frame(), 16)      # the real top-level window (winfo_id is Tk's inner child)
            dwm = ctypes.windll.dwmapi

            def setattr_int(attr: int, value: int) -> int:
                v = ctypes.c_int(value)
                return dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

            def colorref(hex_color: str) -> int:
                h = hex_color.lstrip("#")
                return int(h[0:2], 16) | int(h[2:4], 16) << 8 | int(h[4:6], 16) << 16
            dark = 1 if T.current() == "dark" else 0
            if setattr_int(20, dark) != 0:
                setattr_int(19, dark)
            setattr_int(35, colorref(T.BG))           # DWMWA_CAPTION_COLOR
            setattr_int(36, colorref(T.TEXT))         # DWMWA_TEXT_COLOR
        except Exception:  # noqa: BLE001
            pass

    def _build(self) -> None:
        r = self.root
        # header
        head = ttk.Frame(r, padding=(T.px(T.GAP_L), T.px(T.GAP_S), T.px(T.GAP_L), T.px(T.GAP_S)))
        head.pack(fill="x")
        self._head_icon = ImageTk.PhotoImage(T.make_app_icon(T.px(28)))
        ttk.Label(head, image=self._head_icon).pack(side="left", padx=(0, T.px(T.GAP_S)))
        self._title_lbl = ttk.Label(head, text=T.APP_NAME, style="Title.TLabel")
        self._title_lbl.pack(side="left")
        self._tagline = ttk.Label(head, text=f"  {T.TAGLINE}", style="Tag.TLabel")
        self._tagline.pack(side="left", pady=(T.px(4), 0))
        self._tag_shown = True
        self.head_btn = ttk.Button(head, style="Ghost.TButton", compound="left", cursor="hand2")
        self.head_btn.pack(side="right")

        # footer + log + action bar are packed bottom-up so the pages take the rest
        foot = ttk.Frame(r, padding=(T.px(T.GAP_L), T.px(T.GAP_XS), T.px(T.GAP_L), T.px(T.GAP_S)))
        foot.pack(side="bottom", fill="x")
        ttk.Label(foot, text=f"{T.WORDS['made_by']} ", style="Foot.TLabel").pack(side="left")
        ttk.Label(foot, text=help_text.AUTHOR, style="FootStrong.TLabel").pack(side="left")
        ttk.Button(foot, text=f" {T.WORDS['donate']}", image=T.icon("heart", T.ICON_SMALL, T.LINK), compound="left",
                   style="Ghost.TButton", cursor="hand2", command=lambda: self.show_page("about")).pack(side="left", padx=(T.px(T.GAP_M), 0))
        ttk.Label(foot, text=f"v{__version__}", style="Foot.TLabel").pack(side="right", padx=(0, T.px(18)))   # room for the grip
        self.log_btn = ttk.Button(foot, text=T.WORDS["log"], image=T.icon("chevron_right", T.ICON_SMALL, T.TEXT_3),
                                  compound="right", style="Ghost.TButton", command=self.toggle_log)
        self.log_btn.pack(side="right", padx=(0, T.px(T.GAP_M)))

        # resize grip in the true bottom-right corner (placed over the footer, so the footer's padding doesn't push it in)
        self._grip = ttk.Sizegrip(r)
        self._grip.place(relx=1.0, rely=1.0, anchor="se")

        self.log_frame = ttk.Frame(r, padding=(T.px(T.GAP_L), 0, T.px(T.GAP_L), T.px(T.GAP_XS)))
        self.log_box = tk.Text(self.log_frame, height=6, font=T.F_MONO, bg=T.LOG_BG, fg=T.TEXT_2, bd=0, highlightthickness=0,
                               padx=T.px(T.GAP_S), pady=T.px(T.GAP_XS), state="disabled", wrap="none",
                               selectbackground=T.ACCENT, selectforeground=T.ON_ACCENT)
        self.log_box.pack(fill="both", expand=True)

        bar = ttk.Frame(r, style="Bar.TFrame", padding=(T.px(T.GAP_L), T.px(T.GAP_S)))
        bar.pack(side="bottom", fill="x", padx=T.px(T.GAP_L), pady=(0, T.px(T.GAP_S)))
        self._bar = bar
        self.start_btn = ttk.Button(bar, text=f"  {T.WORDS['start']}", image=T.icon("play", T.ICON_SMALL, T.ON_ACCENT),
                                    compound="left", style="Primary.TButton", command=self.toggle, cursor="hand2")
        self.start_btn.pack(side="left")
        self.cal_btn = ttk.Button(bar, text=f"  {T.WORDS['calibrate']}", image=T.icon("target", T.ICON_SMALL, T.TEXT_2),
                                  compound="left", command=self.ask_calibrate)
        self.cal_btn.pack(side="left", padx=(T.px(T.GAP_S), 0))
        self.spk_btn = ttk.Button(bar, compound="left", command=self.toggle_speakers)
        meter = ttk.Frame(bar, style="Bar.TFrame")
        meter.pack(side="right", padx=(T.px(T.GAP_M), 0))
        ttk.Label(meter, text=T.WORDS["sound_in"], style="Small.TLabel").pack(anchor="w")
        self.meter = ttk.Progressbar(meter, style="Meter.Horizontal.TProgressbar", length=T.px(120), maximum=100)
        self.meter.pack(anchor="w", pady=(T.px(2), 0))
        self.status = ttk.Label(bar, text=T.WORDS["ready"], style="BarStatus.TLabel", anchor="w", justify="left", width=1)
        self.status.pack(side="left", padx=(T.px(T.GAP_L), 0), fill="x", expand=True)
        # wrap at word breaks to the label's own width instead of cutting mid-word
        self.status.bind("<Configure>", lambda e: self.status.configure(wraplength=max(T.px(80), e.width - 2)))

        self.banners = ttk.Frame(r)
        self.banners.pack(side="bottom", fill="x", padx=T.px(T.GAP_L))

        # pages
        self.pages = ttk.Frame(r)
        self.pages.pack(fill="both", expand=True)
        self.main_page = self._build_main(self.pages)
        self.help_page = HelpPage(self.pages, on_copy_diag=self.ctl.diagnostics, on_open_logs=self.ctl.open_log_folder,
                                  on_bt_settings=lambda: self.ctl.open_windows_settings("bluetooth"),
                                  on_donate=lambda: self.show_page("about"))
        self.about_page = AboutPage(self.pages)
        self.show_page("main")
        if self.ctl.cfg.get("log_open"):
            self.toggle_log()
        self._grip.lift()

    def _on_root_configure(self, e) -> None:
        """Hide the tagline when the window is too narrow for it, so the header never overlaps itself."""
        if e.widget is self.root:
            self._fit_header(e.width)

    def _fit_header(self, width: int) -> None:
        show = width >= T.px(T.TAGLINE_MIN_W)
        if show == self._tag_shown:
            return
        self._tag_shown = show
        if show:
            self._tagline.pack(side="left", pady=(T.px(4), 0), after=self._title_lbl)
        else:
            self._tagline.pack_forget()

    # ================================================================== theme
    @staticmethod
    def _apply_banner_colors() -> None:
        """Banner (widgets.py) reads its level colours into a class attribute when it is imported; refresh it per mode."""

    def set_theme(self, mode: str) -> None:
        if mode not in T.MODES or (mode == self._mode and T.resolve(mode) == T.current()):
            return
        self._mode = mode
        self.ctl.set_option("theme", mode)
        self._schedule_save()
        self._rebuild()

    def _snapshot(self) -> dict:
        """Everything the widgets hold that the controller does not: restored after a rebuild."""
        cb = self.source_cb
        self._remember_sync()
        return dict(
            page=self._page, opts_open=self._opts_open, log=self.log_box.get("1.0", "end-1c"),
            status=self._status_now, banners=[w.spec for w in self.banners.winfo_children() if hasattr(w, "spec")],
            src_idx=cb.current(), src_off=cb.instate(["disabled"]), start_text=self.start_btn.cget("text"),
            off={n: b.instate(["disabled"]) for n, b in (("start", self.start_btn), ("cal", self.cal_btn),
                                                         ("refresh", self.refresh_btn))},
            states=[r.state for r in self.rows.values()], meter=float(self.meter["value"]))

    def _rebuild(self) -> None:
        """Apply the current mode live. Widgets keep the colours they were made with, so the simplest robust way is to
        rebuild them all. The controller (devices, running engine) and the tray are untouched, and the tick loop keeps
        its single timer because nothing here schedules it."""
        snap = self._snapshot()
        T.use(self._mode)
        for w in self.root.winfo_children():
            w.destroy()
        self.rows.clear()
        self._opts_open = False                  # toggle_options() below flips it back on if it was open
        T.clear_icon_cache()
        T.apply_styles(self.root)
        self._apply_banner_colors()
        self._tag_shown = True
        self._build()
        self._title_bar()
        # source list and rows: reuse what is known, so a running session never re-enumerates devices
        self.source_cb["values"] = [d.name for d in self._sources]
        if snap["src_idx"] >= 0:
            self.source_cb.current(snap["src_idx"])
        if snap["src_off"]:
            self.source_cb.state(["disabled"])
        self._render_source(snap["states"])
        running = self.ctl.running
        self.start_btn.configure(text=snap["start_text"],
                                 image=T.icon("stop" if running else "play", T.ICON_SMALL, T.ON_ACCENT))
        for name, btn in (("start", self.start_btn), ("cal", self.cal_btn), ("refresh", self.refresh_btn)):
            btn.state(["disabled"] if snap["off"][name] else ["!disabled"])
        for r in self.rows.values():
            r.set_running(running)
        for tid, (key, extra) in self._row_status.items():
            if tid in self.rows:
                self.rows[tid].show_status(key, extra)
        self._update_speaker_btn()
        self.meter["value"] = snap["meter"]
        self._say(*snap["status"])
        if snap["log"]:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", snap["log"] + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        if snap["opts_open"]:
            self.toggle_options()
        for p, level, dismiss in snap["banners"]:
            self.add_banner(p, level=level, dismiss=dismiss)
        self.show_page(snap["page"])
        self.root.update_idletasks()
        self._fit_header(self.root.winfo_width())

    def _say(self, text: str, tone: str = "TEXT_2") -> None:
        """Action-bar status line. `tone` is a theme token name (not a hex), so it can be redrawn in another mode."""
        self._status_now = (text, tone)
        self.status.configure(text=text, foreground=getattr(T, tone))

    def _section(self, parent, title: str, subtitle: str, expand: bool = False) -> tuple[ttk.Frame, ttk.Frame]:
        sec = ttk.Frame(parent, style="Surface.TFrame", padding=(T.px(T.GAP_L), T.px(T.GAP_M)))
        sec.pack(fill="both" if expand else "x", expand=expand, padx=T.px(T.GAP_L), pady=(0, T.px(T.GAP_S)))
        top = ttk.Frame(sec, style="Surface.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text=title, style="Section.TLabel").pack(side="left")
        sub = ttk.Label(sec, text=subtitle, style="Small.TLabel", justify="left")
        sub.pack(anchor="w", fill="x", pady=(T.px(2), T.px(T.GAP_S)))
        bind_wraplength(sub, sec, T.px(2 * T.GAP_L))
        return sec, top

    def _build_main(self, parent) -> ttk.Frame:
        page = ttk.Frame(parent)
        # --- source: one line once a valid source is picked (Change opens the full section)
        sec = ttk.Frame(page, style="Surface.TFrame", padding=(T.px(T.GAP_L), T.px(T.GAP_M)))
        sec.pack(fill="x", padx=T.px(T.GAP_L), pady=(0, T.px(T.GAP_S)))
        self.src_head = head = ttk.Frame(sec, style="Surface.TFrame")
        head.pack(fill="x")
        self.opt_btn = ttk.Button(head, text=T.WORDS["options"], image=T.icon("chevron_right", T.ICON_SMALL, T.TEXT_3),
                                  compound="right", style="SurfaceGhost.TButton", command=self.toggle_options)
        self.opt_btn.pack(side="right")
        self.src_title = ttk.Label(head, text=T.WORDS["source"], style="Section.TLabel")
        self.src_summary = ttk.Frame(head, style="Surface.TFrame")
        ttk.Label(self.src_summary, image=T.icon("speaker", T.ICON, T.TEXT_2), style="Body.TLabel").pack(side="left")
        ttk.Label(self.src_summary, text=f" {T.WORDS['copying']} ", style="Body2.TLabel").pack(side="left")
        self.src_name = ttk.Label(self.src_summary, text="", style="Name.TLabel")
        self.src_name.pack(side="left")
        self.src_change = ttk.Button(self.src_summary, text=T.WORDS["change"], style="LinkBody.TButton", cursor="hand2",
                                     command=self.expand_source)
        self.src_change.pack(side="left", padx=(T.px(T.GAP_S), 0))
        self._src_full = ""
        self._src_font = tkfont.Font(root=self.root, font=T.F_BODY_BOLD)
        Tooltip(self.src_name, lambda: self._src_full if self.src_name.cget("text") != self._src_full else None)
        head.bind("<Configure>", lambda e: self._fit_source_name())
        self.src_body = ttk.Frame(sec, style="Surface.TFrame")
        sub = ttk.Label(self.src_body, text=T.WORDS["source_help"], style="Small.TLabel", justify="left")
        sub.pack(anchor="w", fill="x", pady=(T.px(2), T.px(T.GAP_S)))
        bind_wraplength(sub, sec, T.px(2 * T.GAP_L))
        line = ttk.Frame(self.src_body, style="Surface.TFrame")
        line.pack(fill="x")
        self.source_var = tk.StringVar()
        self.source_cb = ttk.Combobox(line, textvariable=self.source_var, state="readonly", font=T.F_BODY)
        self.source_cb.pack(side="left", fill="x", expand=True)
        self.source_cb.bind("<<ComboboxSelected>>", lambda e: self._on_source_picked())
        self.refresh_btn = ttk.Button(line, text=f"  {T.WORDS['refresh']}", image=T.icon("refresh", T.ICON_SMALL, T.TEXT_2),
                                      compound="left", command=self.refresh)
        self.refresh_btn.pack(side="left", padx=(T.px(T.GAP_S), 0))
        self.done_btn = ttk.Button(line, text=T.WORDS["done"], style="LinkBody.TButton", cursor="hand2",
                                   command=self.collapse_source)
        self.source_hint = ttk.Label(self.src_body, style="Body2.TLabel", compound="left")
        self.source_hint.pack(anchor="w", pady=(T.px(T.GAP_S), 0))
        self.source_probs = ttk.Frame(sec, style="Surface.TFrame")
        self.source_probs.pack(fill="x")
        self.opts = ttk.Frame(sec, style="Surface.TFrame", padding=(0, T.px(T.GAP_S), 0, 0))
        self.auto_var = tk.BooleanVar(value=bool(self.ctl.cfg.get("auto_setup", True)))
        self.mute_var = tk.BooleanVar(value=bool(self.ctl.cfg.get("mute_speakers", True)))
        look = ttk.Frame(self.opts, style="Surface.TFrame")                 # Appearance: Light / Dark / System
        look.pack(anchor="w", pady=(0, T.px(T.GAP_S)))
        ttk.Label(look, text=T.WORDS["appearance"], style="Body2.TLabel").pack(side="left", padx=(0, T.px(T.GAP_M)))
        seg = ttk.Frame(look, style="Seg.TFrame", padding=T.px(2))
        seg.pack(side="left")
        self._seg: dict[str, ttk.Button] = {}
        for mode in T.MODES:
            b = ttk.Button(seg, text=T.THEME_LABEL[mode], cursor="hand2", width=7, command=lambda m=mode: self.set_theme(m),
                           style="SegOn.TButton" if mode == self._mode else "Seg.TButton")
            b.pack(side="left")
            self._seg[mode] = b
        ttk.Checkbutton(self.opts, text=T.WORDS["opt_auto"], variable=self.auto_var,
                        command=lambda: self._set_opt("auto_setup", self.auto_var.get())).pack(anchor="w", pady=T.px(2))
        ttk.Checkbutton(self.opts, text=T.WORDS["opt_mute"], variable=self.mute_var,
                        command=lambda: self._set_opt("mute_speakers", self.mute_var.get())).pack(anchor="w", pady=T.px(2))
        ttk.Button(self.opts, text=T.WORDS["win_sound"], style="Link.TButton", cursor="hand2",
                   command=lambda: self.ctl.open_windows_settings("sound")).pack(anchor="w", pady=(T.px(T.GAP_XS), 0))

        # --- headphones
        sec, top = self._section(page, T.WORDS["headphones"], T.WORDS["headphones_help"], expand=True)
        ttk.Button(top, text=T.WORDS["win_bt"], style="SurfaceGhost.TButton", cursor="hand2",
                   image=T.icon("bluetooth", T.ICON_SMALL, T.TEXT_3), compound="left",
                   command=lambda: self.ctl.open_windows_settings("bluetooth")).pack(side="right")
        self.list = ScrollFrame(sec)
        self.list.pack(fill="both", expand=True)
        self.empty = ttk.Frame(sec, style="Surface.TFrame", padding=(0, T.px(T.GAP_XS)))
        # icon beside the title (not above it) so the whole empty state still fits when the window is at its smallest
        ttk.Label(self.empty, image=T.icon("headphones", T.ICON, T.TEXT_3), text=f"  {T.WORDS['empty_title']}",
                  compound="left", style="Name.TLabel").pack()
        msg = ttk.Label(self.empty, text=T.WORDS["empty_body"], style="Body2.TLabel", justify="center")
        msg.pack(pady=(T.px(2), T.px(T.GAP_S)))
        bind_wraplength(msg, self.empty, T.px(40))
        btns = ttk.Frame(self.empty, style="Surface.TFrame")
        btns.pack()
        ttk.Button(btns, text=T.WORDS["win_bt"], command=lambda: self.ctl.open_windows_settings("bluetooth")).pack(side="left")
        ttk.Button(btns, text=f"  {T.WORDS['refresh']}", image=T.icon("refresh", T.ICON_SMALL, T.TEXT_2), compound="left",
                   command=self.refresh).pack(side="left", padx=(T.px(T.GAP_S), 0))
        return page

    # ================================================================== pages
    def show_page(self, name: str) -> None:
        for p in (self.main_page, self.help_page, self.about_page):
            p.pack_forget()
        {"main": self.main_page, "help": self.help_page, "about": self.about_page}[name].pack(fill="both", expand=True)
        self._page = name
        if name == "main":
            self.head_btn.configure(text=f" {T.WORDS['help']}", image=T.icon("help", T.ICON, T.TEXT_2),
                                    command=lambda: self.show_page("help"))
        else:
            self.head_btn.configure(text=f" {T.WORDS['back']}", image=T.icon("back", T.ICON, T.TEXT_2),
                                    command=lambda: self.show_page("main"))

    def show_help(self, topic: str) -> None:
        self.help_page.show(topic)
        self.show_page("help")

    def toggle_options(self) -> None:
        self._opts_open = not self._opts_open
        if not self._opts_open:
            self.opts.pack_forget()
            self.opt_btn.configure(image=T.icon("chevron_right", T.ICON_SMALL, T.TEXT_3))
        else:
            self.opts.pack(fill="x", after=self.source_probs)
            self.opt_btn.configure(image=T.icon("chevron_down", T.ICON_SMALL, T.TEXT_3))

    def toggle_log(self) -> None:
        if self.log_frame.winfo_ismapped():
            self.log_frame.pack_forget()
            self.log_btn.configure(image=T.icon("chevron_right", T.ICON_SMALL, T.TEXT_3))
        else:
            self.log_frame.pack(side="bottom", fill="x", before=self._bar)
            self.log_btn.configure(image=T.icon("chevron_down", T.ICON_SMALL, T.TEXT_3))
        self.ctl.set_option("log_open", self.log_frame.winfo_ismapped())
        self._schedule_save()

    # ================================================================== banners
    @staticmethod
    def _collapse_if_empty(frame: ttk.Frame) -> None:
        """Tk keeps an emptied frame at its old size; shrink it back so no gap is left."""
        try:
            if not frame.winfo_children():
                frame.configure(height=1)
        except tk.TclError:          # the window was rebuilt (theme switch) before this idle callback ran
            pass

    # How long a message stays (UX: long enough to read ~ 4 s + 50 ms per character, paused while the mouse is on it).
    BANNER_MS = {"info": 5000, "ok": 6000, "warn": 8000, "bad": 9000}

    def add_banner(self, p: Problem, level: str = "warn", actions=None, dismiss: bool = True) -> Banner:
        """Show ONE message in the banner slot (a new message replaces the old one; the same message again just
        restarts its timer). Plain messages vanish by themselves; questions with buttons stay until answered."""
        holder = self.banners
        current = [w for w in holder.winfo_children() if isinstance(w, Banner)]
        same = next((w for w in current if getattr(w, "code", None) == p.code and getattr(w, "text", None) == p.text), None)
        if same is not None and actions is None:
            self._arm_banner(same)
            return same
        for w in current:
            self._cancel_banner_timer(w)
            w.destroy()
        b = None

        def close():
            if b is not None and b.winfo_exists():
                self._cancel_banner_timer(b)
                b.destroy()
                self.root.after_idle(lambda: self._collapse_if_empty(holder))
        b = Banner(holder, p.text, level=level, help_topic=p.help_topic if p.help_topic else None, on_help=self.show_help,
                   actions=actions, on_dismiss=close if dismiss else None)
        b.pack(fill="x", pady=(0, T.px(T.GAP_S)))
        b.code, b.text, b.close = p.code, p.text, close
        b.timeout = None if actions else min(15000, self.BANNER_MS.get(level, 8000) + 50 * len(p.text))
        if actions is None:                 # button banners hold callbacks into this build, so only plain ones survive a rebuild
            b.spec = (p, level, dismiss)
        self._arm_banner(b)
        for w in [b] + list(self._descendants(b)):      # hovering pauses the countdown (time to read / click "How to fix")
            w.bind("<Enter>", lambda e, bb=b: self._cancel_banner_timer(bb), add="+")
            w.bind("<Leave>", lambda e, bb=b: self._arm_banner(bb), add="+")
        return b

    @staticmethod
    def _descendants(w):
        for c in w.winfo_children():
            yield c
            yield from MainWindow._descendants(c)

    def _arm_banner(self, b) -> None:
        self._cancel_banner_timer(b)
        if getattr(b, "timeout", None):
            b.job = self.root.after(b.timeout, b.close)

    def _cancel_banner_timer(self, b) -> None:
        job = getattr(b, "job", None)
        if job:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
            b.job = None

    def clear_banners(self, keep: tuple[str, ...] = ()) -> None:
        for w in self.banners.winfo_children():
            if getattr(w, "code", None) not in keep:
                self._cancel_banner_timer(w)
                w.destroy()
        self._collapse_if_empty(self.banners)

    def _show_source_problems(self, probs: list[Problem]) -> None:
        for w in self.source_probs.winfo_children():
            w.destroy()
        self._collapse_if_empty(self.source_probs)
        for p in probs:
            Banner(self.source_probs, p.text, level="warn", help_topic=p.help_topic, on_help=self.show_help).pack(
                fill="x", pady=(T.px(T.GAP_S), 0))

    # ================================================================== devices
    def refresh(self) -> None:
        if self.ctl.running or self._busy:
            self.add_banner(Problem("busy", "Stop first, then refresh.", ""), level="info")
            return
        self.ctl.refresh_devices()
        self._sources = self.ctl.source_choices()
        self.source_cb["values"] = [d.name for d in self._sources]
        pick = self.ctl.preferred_source_id()
        idx = next((i for i, d in enumerate(self._sources) if d.id == pick), 0 if self._sources else -1)
        if idx >= 0:
            self.source_cb.current(idx)
        else:
            self.source_var.set("")
        self.on_source_changed()

    @property
    def source(self):
        i = self.source_cb.current()
        return self._sources[i] if 0 <= i < len(self._sources) else None

    def _on_source_picked(self) -> None:
        """The user chose from the dropdown: a valid choice folds the section back to one line."""
        self._src_expanded = False
        self.on_source_changed()

    def on_source_changed(self) -> None:
        src = self.source
        if src:
            self.ctl.set_option("source_id", src.id)
        self._render_source()
        self._schedule_save()

    def expand_source(self) -> None:
        self._src_expanded = True
        self._set_source_expanded(True)

    def collapse_source(self) -> None:
        self._src_expanded = False
        self._set_source_expanded(False)

    def _set_source_expanded(self, expanded: bool) -> None:
        """Full section (title, dropdown, Refresh, hint) or the one-line summary. No source, or a source with problems,
        always shows the full section; Done is offered only when the source is fine."""
        src = self.source
        valid = src is not None and not self.source_probs.winfo_children()
        if expanded or not valid:
            self.src_summary.pack_forget()
            self.src_title.pack(side="left")
            self.src_body.pack(fill="x", after=self.src_head)
            if valid:
                self.done_btn.pack(side="left", padx=(T.px(T.GAP_S), 0))
            else:
                self.done_btn.pack_forget()
        else:
            self.src_title.pack_forget()
            self.src_body.pack_forget()
            self._src_full = T.display_name(src.name)
            self.src_name.configure(text=self._src_full)
            self.src_summary.pack(side="left")
            self.root.after_idle(self._fit_source_name)

    def _fit_source_name(self) -> None:
        """Shorten a very long source name so the one-line summary never pushes Options out of the window."""
        try:
            if not self.src_summary.winfo_ismapped() or not self._src_full:
                return
            used = self.src_summary.winfo_reqwidth() - self.src_name.winfo_reqwidth()
            room = self.src_head.winfo_width() - self.opt_btn.winfo_reqwidth() - used - T.px(T.GAP_L)
            text = ellipsize(self._src_full, self._src_font, max(T.px(80), room))
            if text != self.src_name.cget("text"):
                self.src_name.configure(text=text)
        except tk.TclError:
            pass

    def _render_source(self, targets=None) -> None:
        """Hint, problems and rows for the chosen source. `targets` reuses existing row states (theme rebuild)."""
        src = self.source
        hint = T.source_hint(src.kind, src.hint) if src and src.hint else ""
        if hint:
            self.source_hint.configure(text=f"  {hint}", image=T.icon("speaker", T.ICON_SMALL, T.TEXT_3))
            self.source_hint.pack(anchor="w", pady=(T.px(T.GAP_S), 0))
        else:
            self.source_hint.pack_forget()          # an empty label would still reserve a row of height
        self._show_source_problems(self.ctl.source_problems(src.id if src else None))
        self._set_source_expanded(self._src_expanded)
        self._build_rows(src.id if src else None, targets)

    def _build_rows(self, source_id: str | None, targets=None) -> None:
        inner = self.list.inner
        self._remember_sync()
        for w in inner.winfo_children():
            w.destroy()
        self.rows.clear()
        if targets is None:
            targets = self.ctl.targets_for(source_id)
        listeners = [t for t in targets if t.kind in ("bluetooth", "wired headphones")]
        if not listeners:
            self.empty.pack(fill="x")
        else:
            self.empty.pack_forget()
        if not targets:
            self.list.pack_forget()
            self._update_actions()        # nothing connected: Start greyed out + "Connect headphones to begin" (critique P1)
            return
        if not self.list.winfo_ismapped():
            self.list.pack(fill="both", expand=True, before=self.empty if self.empty.winfo_ismapped() else None)
        inner.columnconfigure(2, weight=1)
        for i, t in enumerate(targets, start=1):
            self.rows[t.id] = TargetRow(inner, i, t, on_change=self._on_row_change, on_test=self.ctl.test_tone)
            if t.id in self._sync_open:
                self.rows[t.id].set_sync_open(True)
        self._update_actions()

    def _remember_sync(self) -> None:
        """Which rows have their sync controls open: kept across list and theme rebuilds."""
        if self.rows:
            self._sync_open = {tid for tid, r in self.rows.items() if r.sync_open}

    def _on_row_change(self, state) -> None:
        self.ctl.update_target(state)
        self._schedule_save()
        self._update_actions()

    def _set_opt(self, key: str, value) -> None:
        self.ctl.set_option(key, value)
        src = self.source
        self._show_source_problems(self.ctl.source_problems(src.id if src else None))
        self._schedule_save()

    def _schedule_save(self) -> None:
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(800, self._save)

    def _save(self) -> None:
        self._save_job = None
        try:
            if self.root.state() == "normal":
                self.ctl.set_option("geometry", self.root.geometry())
        except tk.TclError:
            pass
        self.ctl.save()

    # ================================================================== start / stop
    def _on_space(self, e):
        cls = e.widget.winfo_class() if hasattr(e.widget, "winfo_class") else ""
        if cls in ("TButton", "TCheckbutton", "TCombobox", "TScale", "Text", "TEntry", "Entry"):
            return None
        self.toggle()
        return "break"

    def toggle(self) -> None:
        if self._busy:
            return
        if self.ctl.running:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        src = self.source
        targets = [r.state for r in self.rows.values()]
        self.clear_banners(keep=("recovered",))
        pf = self.ctl.preflight(src.id if src else None, targets)
        self._show_most_important(pf.problems)
        if any(p.blocking for p in pf.problems):
            return
        if pf.confirm:
            holder: list[Banner] = []

            def go():
                holder[0].destroy()
                self._collapse_if_empty(self.banners)
                self._do_start(src.id, targets)
            b = self.add_banner(Problem("confirm", pf.confirm, "speakers"), level="warn", dismiss=False,
                                actions=[(T.WORDS["continue"], go, "TButton"),
                                         (T.WORDS["cancel"], lambda: holder[0].destroy(), "SurfaceGhost.TButton")])
            holder.append(b)
            return
        self._do_start(src.id, targets)

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
        """Prevent errors instead of reporting them: grey out Start/Calibrate when they can't work and say why
        in the status line (shown only while idle)."""
        if self._busy or self.ctl.running:
            return
        n = self._ticked()
        can_start = self.source is not None and n >= 1
        can_cal = n >= 2
        self.start_btn.state(["!disabled"] if can_start else ["disabled"])
        self.cal_btn.state(["!disabled"] if can_cal else ["disabled"])
        if not self.rows:
            self._say(T.WORDS["hint_connect"], "TEXT_3")
        elif not can_start:
            self._say(T.WORDS["hint_tick_one"], "TEXT_3")
        elif not can_cal:
            self._say(T.WORDS["hint_ready_one"], "TEXT_2")
        else:
            self._say(T.WORDS["ready"], "TEXT_2")

    def _set_busy(self, text: str) -> None:
        self._busy = True
        self.start_btn.state(["disabled"])
        self.cal_btn.state(["disabled"])
        self.refresh_btn.state(["disabled"])
        self._say(text, "WARN")

    def _do_start(self, source_id: str, targets) -> None:
        self._set_busy(T.WORDS["starting"])
        self.start_btn.configure(text=f"  {T.WORDS['starting']}")

        def work():
            try:
                probs = self.ctl.start(source_id, targets)
            except Exception as exc:  # noqa: BLE001
                log.error("Start crashed", exc_info=True)
                probs = [Problem("start_failed", f"Couldn't start: {exc}", "trouble", True)]
            self.q.put(("started", probs))
        threading.Thread(target=work, daemon=True, name="starter").start()

    def _after_start(self, probs: list[Problem]) -> None:
        self._busy = False
        self.start_btn.state(["!disabled"])
        self._show_most_important(probs)
        running = self.ctl.running
        self.start_btn.configure(text=f"  {T.WORDS['stop' if running else 'start']}",
                                 image=T.icon("stop" if running else "play", T.ICON_SMALL, T.ON_ACCENT))
        self.cal_btn.state(["disabled"] if running else ["!disabled"])
        self.refresh_btn.state(["disabled"] if running else ["!disabled"])
        self.source_cb.state(["disabled"] if running else ["!disabled", "readonly"])
        for r in self.rows.values():
            r.set_running(running)
        self._update_speaker_btn()
        if not running:
            self._update_actions()
        elif not any(p.blocking for p in probs):
            n = self._ticked()
            self._synced_until = time.monotonic() + 4.0           # a short "all good" moment, then the live status
            self._say(T.WORDS["synced_one"] if n == 1 else T.WORDS["synced_many"].format(n=n), "OK")

    def stop(self) -> None:
        self._set_busy(T.WORDS["stopping"])
        self.start_btn.configure(text=f"  {T.WORDS['stopping']}")
        threading.Thread(target=lambda: (self.ctl.stop(), self.q.put(("stopped",))), daemon=True, name="stopper").start()

    def _after_stop(self) -> None:
        self._busy = False
        self._synced_until = 0.0
        for b in (self.start_btn, self.cal_btn, self.refresh_btn):
            b.state(["!disabled"])
        self.start_btn.configure(text=f"  {T.WORDS['start']}", image=T.icon("play", T.ICON_SMALL, T.ON_ACCENT))
        self.source_cb.state(["!disabled", "readonly"])
        for r in self.rows.values():
            r.set_running(False)
        for tid in self.rows:
            self._show_row(tid, "stopped")
        self._update_speaker_btn()
        self.meter["value"] = 0
        self.clear_banners(keep=("recovered",))
        self._update_actions()

    def _show_row(self, tid: str, key: str, extra: str = "") -> None:
        """Show a row's live status and remember it, so a theme rebuild can draw it again."""
        self._row_status[tid] = (key, extra)
        self.rows[tid].show_status(key, extra)

    def _update_speaker_btn(self) -> None:
        if self.ctl.speakers_mutable:
            muted = self.ctl.speakers_muted
            self.spk_btn.configure(text=f"  {T.WORDS['unmute' if muted else 'mute']}",
                                   image=T.icon("speaker" if muted else "speaker_off", T.ICON_SMALL, T.TEXT_2))
            if not self.spk_btn.winfo_ismapped():
                self.spk_btn.pack(side="left", padx=(T.px(T.GAP_S), 0), after=self.cal_btn)
        elif self.spk_btn.winfo_ismapped():
            self.spk_btn.pack_forget()

    def toggle_speakers(self) -> None:
        self.ctl.toggle_speakers()
        self._update_speaker_btn()

    # ================================================================== calibration
    def ask_calibrate(self) -> None:
        if self._busy or self.ctl.running:
            return
        targets = [r.state for r in self.rows.values()]
        if sum(1 for t in targets if t.enabled) < 2:
            self.add_banner(Problem("cal_two", T.WORDS["cal_need_two"], "sync"), level="info")
            return
        self.clear_banners(keep=("recovered",))
        holder: list[Banner] = []

        def go():
            holder[0].destroy()
            self._collapse_if_empty(self.banners)
            self._do_calibrate(targets)
        holder.append(self.add_banner(Problem("cal_intro", T.WORDS["cal_intro"], "sync"), level="info", dismiss=False,
                                      actions=[(T.WORDS["cal_start"], go, "TButton"),
                                               (T.WORDS["cancel"], lambda: holder[0].destroy(), "SurfaceGhost.TButton")]))

    def _do_calibrate(self, targets) -> None:
        self._set_busy(T.WORDS["calibrating"])

        def work():
            try:
                lines, delays = self.ctl.calibrate(targets, progress=lambda m: self.q.put(("status", m)))
                self.q.put(("calibrated", lines, delays, None))
            except Exception as exc:  # noqa: BLE001
                log.error("Calibration failed", exc_info=True)
                self.q.put(("calibrated", [], {}, str(exc)))
        threading.Thread(target=work, daemon=True, name="calibrate").start()

    def _after_calibrate(self, lines, delays, error) -> None:
        self._busy = False
        self.refresh_btn.state(["!disabled"])
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
            text += f"\n{T.WORDS['cal_done']}"
        self.add_banner(Problem("cal_result", text, "sync"), level="ok" if ok else "warn")

    # ================================================================== live updates
    def _tick(self) -> None:
        try:
            self._drain_queue()
            self._update_live()
            self._drain_log()
            self._ticks += 1
            if self._mode == "system" and self._ticks % 8 == 0 and T.system_mode() != T.current():
                self._rebuild()                  # Windows switched between light and dark while we were open
        except Exception:  # noqa: BLE001 - the UI loop must survive anything
            log.error("UI update failed", exc_info=True)
        finally:
            try:
                self.root.after(TICK_MS, self._tick)
            except tk.TclError:
                pass

    def _drain_queue(self) -> None:
        while True:
            try:
                cmd = self.q.get_nowait()
            except queue.Empty:
                return
            kind = cmd[0]
            if kind == "started":
                self._after_start(cmd[1])
            elif kind == "stopped":
                self._after_stop()
            elif kind == "calibrated":
                self._after_calibrate(*cmd[1:])
            elif kind == "status":
                self._say(cmd[1], "WARN")
            elif kind == "show":
                self.show_window()
            elif kind == "page":
                self.show_window()
                self.show_page(cmd[1])
            elif kind == "toggle":
                self.toggle()
            elif kind == "speakers":
                self.toggle_speakers()
            elif kind == "quit":
                self.quit()
                return

    def _update_live(self) -> None:
        snap = self.ctl.snapshot()
        if not snap or self._busy:
            return
        self.meter["value"] = min(100, snap.peak * 140)
        waiting = snap.capture_state == "waiting"
        for tid, s in snap.outputs.items():
            row = self.rows.get(tid)
            if not row:
                continue
            if waiting and s.state in ("buffering", "playing"):
                self._show_row(tid, "waiting")
            elif s.state == "playing":
                self._show_row(tid, "playing", f"{s.level_ms:.0f} ms" + (f" · {s.underruns} gaps" if s.underruns else ""))
            else:
                self._show_row(tid, s.state)
        m, sec = divmod(int(snap.seconds), 60)
        if waiting:
            self._say(f"{m}:{sec:02d}  ·  {T.WORDS['waiting']}", "WARN")
        elif snap.capture_state != "running":
            self._say(f"{m}:{sec:02d}  ·  Sound source {snap.capture_state}", "WARN")
        elif time.monotonic() < self._synced_until:
            n = sum(1 for s in snap.outputs.values() if s.state == "playing") or self._ticked()
            self._say(T.WORDS["synced_one"] if n == 1 else T.WORDS["synced_many"].format(n=n), "OK")
        else:
            self._say(f"{m}:{sec:02d}  ·  {T.WORDS['running']}", "OK")

    def _drain_log(self) -> None:
        lines = []
        try:
            while len(lines) < 200:
                lines.append(log_setup.gui_queue.get_nowait())
        except queue.Empty:
            pass
        if not lines:
            return
        b = self.log_box
        b.configure(state="normal")
        b.insert("end", "\n".join(lines) + "\n")
        if int(b.index("end-1c").split(".")[0]) > 1500:
            b.delete("1.0", "500.0")
        b.see("end")
        b.configure(state="disabled")

    # ================================================================== window / tray
    def _start_tray(self) -> None:
        try:
            import pystray
            put = self.q.put
            menu = pystray.Menu(
                pystray.MenuItem("Show DuoSound", lambda: put(("show",)), default=True),
                pystray.MenuItem("Start / Stop", lambda: put(("toggle",))),
                pystray.MenuItem("Mute / unmute laptop speakers", lambda: put(("speakers",))),
                pystray.MenuItem("Help", lambda: put(("page", "help"))),
                pystray.MenuItem("Donate", lambda: put(("page", "about"))),
                pystray.MenuItem("Quit", lambda: put(("quit",))),
            )
            self.tray = pystray.Icon("DuoSound", T.make_app_icon(64), "DuoSound", menu)
            threading.Thread(target=self.tray.run, daemon=True, name="tray").start()
        except Exception:  # noqa: BLE001
            self.tray = None
            log.warning("Tray icon unavailable", exc_info=True)

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def on_close(self) -> None:
        if self.ctl.running and self.tray is not None:
            self.root.withdraw()
            try:
                self.tray.notify(T.WORDS["tray_hint"], "DuoSound")
            except Exception:  # noqa: BLE001
                pass
            return
        self.quit()

    def quit(self) -> None:
        log.info("Quitting")
        self._save()
        self.ctl.shutdown()            # always stops + restores Windows, even if a Stop was still running
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:  # noqa: BLE001
                pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self) -> None:
        log.info("Window opened")
        self.root.mainloop()
