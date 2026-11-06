"""Scenery demo: the animated background with mock DuoSound panels on top, and a Day/Night switch.
Run:  python tools/demos/scenery_demo.py            (interactive)
      python scenery_demo.py shots DIR  (saves night/day/fade frames + CPU timing, then exits)"""
import ctypes
import sys
import time
import tkinter as tk

sys.path.insert(0, r"D:\Vs Code\Fun Projects\Multiple Bluetooth Paring")
ctypes.windll.shcore.SetProcessDpiAwareness(1)
from duosound.ui.scenery import Scenery  # noqa: E402

PANEL = {"dark": ("#211B16", "#F4EADF", "#C9B8A8"), "light": ("#FFFFFF", "#2A2017", "#5E4F42")}

root = tk.Tk()
root.title("DuoSound - scenery demo")
root.geometry("1000x700+40+40")
cv = tk.Canvas(root, highlightthickness=0, bd=0)
cv.pack(fill="both", expand=True)
scene = Scenery(cv, "dark", animate=True)

# mock UI panels sitting on top of the scene (the real app's sections would sit here the same way)
panels = []


def make_panels(mode):
    for p in panels:
        p.destroy()
    panels.clear()
    bg, fg, fg2 = PANEL[mode]
    head = tk.Frame(cv, bg=bg)
    tk.Label(head, text="DuoSound", font=("Segoe UI", 15, "bold"), bg=bg, fg=fg).pack(side="left", padx=12, pady=8)
    tk.Label(head, text="One movie, many headphones, in sync.", font=("Segoe UI", 9), bg=bg, fg=fg2).pack(side="left")
    btn = tk.Button(head, text="Switch to day" if mode == "dark" else "Switch to night", relief="flat", bg="#F28C2E",
                    fg="#1B1007", font=("Segoe UI", 10, "bold"), padx=12, command=toggle)
    btn.pack(side="right", padx=12)
    body = tk.Frame(cv, bg=bg)
    tk.Label(body, text="Headphones", font=("Segoe UI", 11, "bold"), bg=bg, fg=fg).pack(anchor="w", padx=16, pady=(12, 4))
    for name, st in (("OnePlus Buds 4", "Playing · 62 ms"), ("OnePlus Bullets Wireless Z3", "Playing · 60 ms"), ("Sony WH-1000XM5", "Playing · 61 ms")):
        row = tk.Frame(body, bg=bg)
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text=name, font=("Segoe UI", 10, "bold"), bg=bg, fg=fg).pack(side="left")
        tk.Label(row, text=st, font=("Segoe UI", 9), bg=bg, fg="#6CCB94" if mode == "dark" else "#2E7D4F").pack(side="right")
    tk.Frame(body, bg=bg, height=10).pack()
    panels.extend([head, body])
    cv.delete("ui")
    cv.create_window(24, 18, window=head, anchor="nw", tags=("ui",))
    cv.create_window(24, 120, window=body, anchor="nw", tags=("ui",), width=520)


def toggle():
    mode = "light" if scene.mode == "dark" else "dark"
    scene.set_mode(mode)
    make_panels(mode)


make_panels("dark")
scene.start()

if len(sys.argv) > 2 and sys.argv[1] == "shots":
    out = sys.argv[2]
    from PIL import Image
    import ctypes.wintypes as wt

    from PIL import ImageGrab

    def shot(name):
        root.attributes("-topmost", True); root.lift(); root.update(); time.sleep(0.05); root.update()
        x, y = root.winfo_rootx(), root.winfo_rooty()
        im = ImageGrab.grab((x, y, x + root.winfo_width(), y + root.winfo_height()), all_screens=True)
        im.save(f"{out}/{name}.png")
        return im

    def pump(sec):
        end = time.time() + sec
        while time.time() < end:
            root.update(); time.sleep(0.005)

    pump(1.0)
    frames = []
    shot("demo_night")
    # CPU cost of the animation
    t0 = time.process_time(); w0 = time.time(); pump(5.0)
    print(f"CPU while animating: {100 * (time.process_time() - t0) / (time.time() - w0):.1f}% of one core")
    toggle(); pump(0.15); shot("demo_fade"); pump(0.8)
    shot("demo_day")
    root.destroy()
else:
    root.mainloop()
