"""About + Donate page: credit to the creator and the UPI QR code (from "Donate ME QR/GooglePay_QR.png")."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from .. import __version__, help_text
from ..resources import DONATE_QR, resource_path
from . import theme as T

QR_CARD_BOX = (200, 416, 1240, 1584)      # the white card with the QR code inside GooglePay_QR.png (1440 x 2000)
QR_SHOW_W = 300                           # shown width -> QR itself ~260 px, easy to scan from a phone
QR_MIN_W = 220                            # never smaller (QR itself ~190 px, still scans)


def load_qr(width: int) -> Image.Image | None:
    path = resource_path(DONATE_QR)
    try:
        img = Image.open(path).convert("RGB")
    except (OSError, ValueError):
        return None
    if img.size == (1440, 2000):
        img = img.crop(QR_CARD_BOX)
    h = round(img.height * width / img.width)
    return img.resize((width, h), Image.LANCZOS)


class AboutPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="TFrame")
        card = ttk.Frame(self, style="Surface.TFrame", padding=T.px(T.GAP_XL))
        card.pack(fill="both", expand=True, padx=T.px(T.GAP_L), pady=(0, T.px(T.GAP_M)))
        card.columnconfigure(0, weight=1)

        left = ttk.Frame(card, style="Surface.TFrame")
        left.grid(row=0, column=0, sticky="nw", padx=(0, T.px(T.GAP_XL)))
        ttk.Label(left, image=T.icon("heart", 28, T.LINK), style="Body.TLabel").pack(anchor="w", pady=(0, T.px(T.GAP_S)))
        ttk.Label(left, text=T.WORDS["donate_title"], style="Section.TLabel", font=(T.FONT, 14, "bold")).pack(anchor="w")
        txt = tk.Text(left, wrap="word", bg=T.SURFACE, fg=T.TEXT_2, bd=0, highlightthickness=0, font=T.F_BODY, width=40,
                      height=7, cursor="arrow", spacing3=T.px(6))
        txt.tag_configure("b", font=T.F_BODY_BOLD, foreground=T.TEXT)
        for _kind, para in help_text.ABOUT:
            for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", para)):
                if part:
                    txt.insert("end", part, ("b",) if i % 2 else ())
            txt.insert("end", "\n")
        txt.insert("end", T.WORDS["donate_thanks"])
        txt.configure(state="disabled")
        txt.pack(anchor="w", fill="x", pady=(T.px(T.GAP_S), T.px(T.GAP_M)))

        upi = ttk.Frame(left, style="Surface.TFrame")
        upi.pack(anchor="w")
        ttk.Label(upi, text=f"{T.WORDS['upi']}:", style="Body2.TLabel").pack(side="left")
        ttk.Label(upi, text=help_text.UPI_ID, style="Name.TLabel").pack(side="left", padx=(T.px(T.GAP_XS), T.px(T.GAP_S)))
        self.copy_btn = ttk.Button(upi, text=f"  {T.WORDS['copy']}", image=T.icon("copy", T.ICON_SMALL, T.TEXT_2),
                                   compound="left", command=self._copy_upi)
        self.copy_btn.pack(side="left")
        ttk.Label(left, text=f"DuoSound {__version__}", style="Small.TLabel").pack(anchor="w", pady=(T.px(T.GAP_XL), 0))

        right = ttk.Frame(card, style="Surface.TFrame")
        right.grid(row=0, column=1, sticky="ne")
        self._qr_src = load_qr(T.px(QR_SHOW_W) * 2)
        self._qr_w = 0
        if self._qr_src is not None:
            self._qr_label = tk.Label(right, bg=T.SURFACE, bd=0)
            self._qr_label.pack()
            ttk.Label(right, text=T.WORDS["donate_scan"], style="Small.TLabel").pack(pady=(T.px(T.GAP_S), 0))
            self._fit_qr(T.px(QR_SHOW_W))
            card.bind("<Configure>", self._on_resize, add="+")

    def _on_resize(self, e) -> None:
        # card height minus padding and the caption under the QR; width capped so the text column keeps room
        room_h = e.height - 2 * T.px(T.GAP_XL) - T.px(30)
        room_w = e.width // 2
        self._fit_qr(max(T.px(QR_MIN_W), min(T.px(QR_SHOW_W), room_w, int(room_h * 1040 / 1168))))

    def _fit_qr(self, width: int) -> None:
        if self._qr_src is None or abs(width - self._qr_w) < 4:
            return
        self._qr_w = width
        h = round(self._qr_src.height * width / self._qr_src.width)
        self._qr = ImageTk.PhotoImage(self._qr_src.resize((width, h), Image.LANCZOS))
        self._qr_label.configure(image=self._qr)

    def _copy_upi(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(help_text.UPI_ID)
        self.copy_btn.configure(text=f"  {T.WORDS['copied']}", image=T.icon("check", T.ICON_SMALL, T.OK))
        self.after(2000, lambda: self.copy_btn.configure(text=f"  {T.WORDS['copy']}",
                                                         image=T.icon("copy", T.ICON_SMALL, T.TEXT_2)))
