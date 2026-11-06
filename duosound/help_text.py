"""The Help pages shown inside DuoSound - the one source of truth for help text.

README.md's "Help" section is generated from this file:  python -m duosound.help_text > help.md
Blocks: ("p", text) paragraph · ("steps", [..]) numbered list · ("ul", [..]) bullets · ("faq", [(problem, fix), ..])
Words in **double stars** are shown bold."""
from __future__ import annotations

from . import __version__

AUTHOR = "Amon Lal"
UPI_ID = "amonh7-1@okicici"

TOPICS: list[tuple[str, str, list]] = [
    ("quickstart", "Quick start", [
        ("p", "DuoSound plays your laptop's sound on two or more headphones at the same time, in sync, so several people "
              "can watch one movie."),
        ("steps", [
            "Turn on everyone's headphones and connect them in Windows (Settings → Bluetooth & devices). "
            "Wired headphones work too.",
            "Open DuoSound. It picks the sound source and ticks the headphones for you. Press **Start**.",
            "Play the movie in any app: browser, VLC, Netflix. If the app was already open, pause and play again.",
        ]),
        ("p", "If two headphones sound out of step (an echo), see **Getting headphones in sync**."),
    ]),
    ("source", "Choosing a sound source", [
        ("p", "Windows plays the movie into the **sound source**. DuoSound copies it from there to every pair of "
              "headphones. The best sources make no sound of their own:"),
        ("ul", [
            "**VB-CABLE** (free, from vb-audio.com): totally silent. Install it, restart, and DuoSound picks "
            "\"CABLE Input\" by itself.",
            "**An unused HDMI / Digital Output**: silent if no TV or monitor with speakers is plugged in.",
            "**Laptop speakers**: always there. DuoSound mutes them while the headphones play.",
        ]),
        ("p", "Never pick a pair of headphones as the source. That person would hear the movie twice, out of step."),
        ("p", "Leave \"Switch Windows' sound output to the source\" on (under Options). DuoSound then switches Windows "
              "for you and puts everything back when you press Stop."),
    ]),
    ("sync", "Getting headphones in sync", [
        ("p", "Every pair of Bluetooth headphones has its own delay. DuoSound lines them up in two ways:"),
        ("ul", [
            "**Calibrate (automatic):** take the headphones off, put them all next to the laptop's microphone, keep the "
            "room quiet and press **Calibrate**. Each one plays a few chirps, and DuoSound sets the Delay sliders.",
            "**By ear:** play a video with clear claps or clicks, wear one earbud from each pair, and move the **Delay** "
            "of the pair that is **ahead** until both sound together. You can do this while the movie plays.",
        ]),
        ("p", "After that, DuoSound keeps them in step by itself for the whole movie."),
    ]),
    ("speakers", "Laptop speakers are muted", [
        ("p", "While headphones are playing, DuoSound mutes the laptop speakers so the movie isn't heard out loud."),
        ("ul", [
            "Press **Unmute speakers** next to Stop (or in the tray menu) to hear it from the laptop too. Press again to mute.",
            "Stop puts the speakers back exactly as they were.",
            "To switch this off, open **Options** and untick \"Mute the laptop speakers while headphones play\".",
        ]),
    ]),
    ("lipsync", "Lip sync", [
        ("p", "Bluetooth adds about 0.15 to 0.35 seconds of delay, so speech can look slightly late. Many players can "
              "delay the picture's audio to match. In VLC: Tools → Track Synchronization → Audio track synchronization "
              "(use a negative value). Browsers don't have this setting."),
    ]),
    ("many", "How many headphones?", [
        ("p", "DuoSound itself has no limit, but every Bluetooth headset shares the laptop's one Bluetooth radio."),
        ("ul", [
            "**2** pairs work on almost every laptop. **3** usually work. **4–5** depend on the laptop and may crackle.",
            "A cheap **USB Bluetooth adapter** adds a second radio: connect some headphones to it.",
            "**Wired headphones** (jack or USB) don't use the radio at all.",
            "Keep the headphones near the laptop, and use 5 GHz Wi-Fi if you can (2.4 GHz Wi-Fi shares the air with Bluetooth).",
        ]),
    ]),
    ("full_vs_lite", "Full vs Lite — which should I use?", [
        ("p", "DuoSound comes in two versions installed side by side:"),
        ("ul", [
            "**DuoSound (Full Graphics)** uses an animated glass window with a moving moon or sun scene. "
            "It looks great on modern laptops but uses about 20–40 % of one processor core while idle.",
            "**DuoSound Lite (Classic Graphics)** uses a plain window with no animation. "
            "It uses under 5 % of one core while idle and starts faster — good for older PCs and battery use.",
            "Both versions play audio exactly the same way and support the same headphones.",
        ]),
        ("p", "To switch, just run the other .exe from the install folder: "
              "**DuoSound.exe** (Full) or **DuoSound_Lite.exe** (Lite). "
              "They share your settings, so you won't lose your headphone delays or volume levels."),
        ("p", "**Battery / Old-PC saver mode** (under Options in either version): doubles the audio block size from "
              "10 ms to 20 ms, halving the number of times per second the engine has to wake up. "
              "Use it if the PC struggles or runs hot."),
    ]),
    ("nosound", "No sound in the headphones", [
        ("ul", [
            "Look at the **Sound in** meter. If it stays empty, Windows isn't playing into the source: leave "
            "\"Switch Windows' sound output to the source\" on, or choose the source in the taskbar speaker menu.",
            "Make sure the movie is actually playing. Pause and play again if the app was open before Start.",
            "Check that the source isn't muted in Windows (except the laptop speakers, which DuoSound mutes on purpose).",
            "Press **Test** next to a pair of headphones to hear a beep in just that one.",
        ]),
    ]),
    ("trouble", "Troubleshooting", [
        ("faq", [
            ("Headphones aren't listed", "Connect them in Windows (Settings → Bluetooth & devices), then press "
                                         "**Refresh**. Headphones must say Connected, not only Paired."),
            ("No sound at all", "See **No sound in the headphones**."),
            ("One pair sounds tinny or mono", "An app opened its microphone (Teams, Discord, Zoom…), which puts the "
                                              "headset into call mode. Close that app, or turn off \"Hands-free "
                                              "telephony\" for the headset in Control Panel → Devices and Printers."),
            ("Crackles with 3 or more headphones", "One Bluetooth radio is at its limit. See **How many headphones?**"),
            ("Headphones dropped out", "DuoSound reconnects them by itself every 2 seconds; the others keep playing."),
            ("Echo between two pairs", "See **Getting headphones in sync**."),
            ("Windows says \"Windows protected your PC\"", "The program isn't signed yet. Click **More info → Run anyway**."),
            ("DuoSound is already running", "Look for the orange icon in the taskbar's tray (click the ^ arrow)."),
            ("Something else", "Press **Copy diagnostics** below and send it together with your question."),
        ]),
    ]),
]

ABOUT = [
    ("p", f"**DuoSound** {__version__}: one movie, many headphones."),
    ("p", f"Made by **{AUTHOR}**."),
    ("p", "If DuoSound made your movie night better, you can say thanks with a small donation."),
]


def topic(key: str) -> tuple[str, str, list] | None:
    return next((t for t in TOPICS if t[0] == key), None)


def to_markdown() -> str:
    out = []
    for _key, title, blocks in TOPICS:
        out.append(f"### {title}")
        for kind, body in blocks:
            if kind == "p":
                out.append(body)
            elif kind == "steps":
                out += [f"{i}. {s}" for i, s in enumerate(body, 1)]
            elif kind == "ul":
                out += [f"- {s}" for s in body]
            elif kind == "faq":
                out += ["| Problem | Fix |", "|---|---|"] + [f"| {p} | {f} |" for p, f in body]
            out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")   # arrows/dashes must survive a cp1252 console or a redirect
    print(to_markdown())
