"""In-window Help ("Read me"): topic list on the left, the topic on the right, self-help tools underneath.
Text comes from duosound.help_text (the same text the README uses)."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import Callable

from .. import help_text
from . import theme as T


class HelpPage(ttk.Frame):
    def __init__(self, parent, on_copy_diag: Callable[[], str], on_open_logs: Callable, on_bt_settings: Callable,
                 on_donate: Callable):
        super().__init__(parent, style="TFrame")
        self._nav: dict[str, ttk.Button] = {}
        self._copy_diag = on_copy_diag
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        nav = ttk.Frame(self, style="Nav.TFrame", padding=(T.px(T.GAP_S), T.px(T.GAP_M)))
        nav.grid(row=0, column=0, sticky="ns", padx=(T.px(T.GAP_L), T.px(T.GAP_S)), pady=(0, T.px(T.GAP_M)))
        for key, title, _ in help_text.TOPICS:
            b = ttk.Button(nav, text=title, style="Nav.TButton", command=lambda k=key: self.show(k), cursor="hand2")
            b.pack(fill="x", pady=1)
            self._nav[key] = b
        ttk.Frame(nav, style="Line.TFrame", height=1).pack(fill="x", pady=T.px(T.GAP_S))
        ttk.Button(nav, text=f"  {T.WORDS['donate']} & about", image=T.icon("heart", T.ICON_SMALL, T.LINK), compound="left",
                   style="Nav.TButton", command=on_donate, cursor="hand2").pack(fill="x", pady=1)

        body = ttk.Frame(self, style="Surface.TFrame")
        body.grid(row=0, column=1, sticky="nsew", padx=(0, T.px(T.GAP_L)), pady=(0, T.px(T.GAP_M)))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.text = tk.Text(body, wrap="word", bg=T.SURFACE, fg=T.TEXT, bd=0, highlightthickness=0, cursor="arrow",
                            padx=T.px(T.GAP_XL), pady=T.px(T.GAP_L), font=T.F_BODY, spacing1=T.px(2), spacing3=T.px(6),
                            selectbackground=T.ACCENT, selectforeground=T.ON_ACCENT, insertbackground=T.SURFACE,
                            width=60)
        sb = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        t = self.text
        t.tag_configure("h1", font=(T.FONT, 14, "bold"), foreground=T.TEXT, spacing3=T.px(10))
        t.tag_configure("p", foreground=T.TEXT_2, lmargin1=0, lmargin2=0)
        t.tag_configure("b", font=T.F_BODY_BOLD, foreground=T.TEXT)
        t.tag_configure("li", foreground=T.TEXT_2, lmargin1=T.px(8), lmargin2=T.px(26))
        t.tag_configure("q", font=T.F_BODY_BOLD, foreground=T.TEXT, spacing1=T.px(8), spacing3=T.px(1))
        t.tag_configure("a", foreground=T.TEXT_2, lmargin1=T.px(0), lmargin2=T.px(0))
        t.tag_configure("num", foreground=T.LINK, font=T.F_BODY_BOLD)

        tools = ttk.Frame(body, style="Surface.TFrame", padding=(T.px(T.GAP_XL), T.px(T.GAP_S), T.px(T.GAP_L), T.px(T.GAP_M)))
        tools.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.copy_btn = ttk.Button(tools, text=f"  {T.WORDS['copy_diag']}", image=T.icon("copy", T.ICON_SMALL, T.TEXT_2),
                                   compound="left", command=self._copy)
        self.copy_btn.pack(side="left")
        ttk.Button(tools, text=f"  {T.WORDS['open_logs']}", image=T.icon("folder", T.ICON_SMALL, T.TEXT_2), compound="left",
                   command=on_open_logs).pack(side="left", padx=(T.px(T.GAP_S), 0))
        ttk.Button(tools, text=f"  {T.WORDS['win_bt']}", image=T.icon("bluetooth", T.ICON_SMALL, T.TEXT_2), compound="left",
                   command=on_bt_settings).pack(side="left", padx=(T.px(T.GAP_S), 0))
        self.show(help_text.TOPICS[0][0])

    def _insert_rich(self, text: str, base: str) -> None:
        for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
            if part:
                self.text.insert("end", part, (base, "b") if i % 2 else (base,))

    def show(self, key: str) -> None:
        tp = help_text.topic(key) or help_text.TOPICS[0]
        for k, b in self._nav.items():
            b.configure(style="NavOn.TButton" if k == tp[0] else "Nav.TButton")
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", tp[1] + "\n", ("h1",))
        for kind, body in tp[2]:
            if kind == "p":
                self._insert_rich(body, "p")
                t.insert("end", "\n", ("p",))
            elif kind in ("steps", "ul"):
                for i, item in enumerate(body, 1):
                    t.insert("end", f"{i}.  " if kind == "steps" else "•  ", ("li", "num"))
                    self._insert_rich(item, "li")
                    t.insert("end", "\n", ("li",))
            elif kind == "faq":
                for q, a in body:
                    t.insert("end", q + "\n", ("q",))
                    self._insert_rich(a, "a")
                    t.insert("end", "\n", ("a",))
        t.configure(state="disabled")
        t.yview_moveto(0)

    def _copy(self) -> None:
        text = self._copy_diag()
        self.clipboard_clear()
        self.clipboard_append(text)
        self.copy_btn.configure(text=f"  {T.WORDS['copied']}", image=T.icon("check", T.ICON_SMALL, T.OK))
        self.after(2000, lambda: self.copy_btn.configure(text=f"  {T.WORDS['copy_diag']}",
                                                         image=T.icon("copy", T.ICON_SMALL, T.TEXT_2)))
