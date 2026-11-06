# DuoSound

**One movie, many headphones, in sync.** Play your Windows laptop's sound on two or more Bluetooth (or wired) headphones
at the same time, so several people can watch one movie together without disturbing anyone.

Made by **Amon Lal** · version 0.1.1

---

## Installation

### Option A — Installer (recommended)
Download **DuoSound_Setup.exe** and run it. The installer lets you choose:

| Option | Best for |
|---|---|
| **Full Graphics** | Modern laptops — animated glass window with a moving moon/sun scene |
| **Classic Graphics** | Older PCs or battery use — plain window, faster start, lower idle CPU |

Both versions are installed so you can switch any time by running the other `.exe` from the install folder.

If Windows says *"Windows protected your PC"*, click **More info → Run anyway** (the program isn't code-signed yet).

### Option B — Portable ZIP
Download **DuoSound_Full_Portable.zip** or **DuoSound_Lite_Portable.zip**, unzip anywhere (USB stick works), and run the `.exe` inside. No install needed. Settings are saved to `%APPDATA%\DuoSound\`, not inside the ZIP folder.

### Option C — Run from source (terminal)
Needs Python 3.10+. Pick the edition when you install the requirements:

```bash
git clone https://github.com/AmonHooriLal/duosound.git
cd duosound
```

**Classic Graphics (Lite)** — smaller install, no Flet:
```bash
pip install -r requirements.txt
python main_lite.py
```

**Full Graphics** — adds Flet for the glass window:
```bash
pip install -r requirements-full.txt
python main.py
```

You can install both sets and switch by running the other script. `main.py` falls back to the
tkinter window by itself if Flet isn't installed, so it never hard-fails.

### System requirements
- Windows 10 or 11 (64-bit)
- No Python needed for Options A and B — the .exe includes everything
- Python 3.10+ for Option C

### Switching between Full and Lite after install
Run either `.exe` directly from the install folder (default: `%LOCALAPPDATA%\Programs\DuoSound\`).
They share your headphone settings. Setup installs for the current user, so it never asks for
administrator rights.

---

## Get it (old single-exe)
1. Download **DuoSound.exe** and double-click it. Nothing else to install: no Python, no drivers.
2. If Windows says *"Windows protected your PC"*, click **More info → Run anyway** (the program isn't code-signed yet).
3. Connect everyone's headphones in Windows (Settings → Bluetooth & devices), press **Start** in DuoSound and play the movie.

Everything below is also inside the app: press **Help** (or F1).

Windows 11 also has a built-in **Shared audio** option (Settings → Bluetooth & devices), but only for the newest
*LE Audio* headphones. DuoSound works with the ordinary headphones people already own.

## Help
<!-- help:start (generated from duosound/help_text.py - edit that file, then regenerate) -->
### Quick start
DuoSound plays your laptop's sound on two or more headphones at the same time, in sync, so several people can watch one movie.

1. Turn on everyone's headphones and connect them in Windows (Settings → Bluetooth & devices). Wired headphones work too.
2. Open DuoSound. It picks the sound source and ticks the headphones for you. Press **Start**.
3. Play the movie in any app: browser, VLC, Netflix. If the app was already open, pause and play again.

If two headphones sound out of step (an echo), see **Getting headphones in sync**.

### Choosing a sound source
Windows plays the movie into the **sound source**. DuoSound copies it from there to every pair of headphones. The best sources make no sound of their own:

- **VB-CABLE** (free, from vb-audio.com): totally silent. Install it, restart, and DuoSound picks "CABLE Input" by itself.
- **An unused HDMI / Digital Output**: silent if no TV or monitor with speakers is plugged in.
- **Laptop speakers**: always there. DuoSound mutes them while the headphones play.

Never pick a pair of headphones as the source. That person would hear the movie twice, out of step.

Leave "Switch Windows' sound output to the source" on (under Options). DuoSound then switches Windows for you and puts everything back when you press Stop.

### Getting headphones in sync
Every pair of Bluetooth headphones has its own delay. DuoSound lines them up in two ways:

- **Calibrate (automatic):** take the headphones off, put them all next to the laptop's microphone, keep the room quiet and press **Calibrate**. Each one plays a few chirps, and DuoSound sets the Delay sliders.
- **By ear:** play a video with clear claps or clicks, wear one earbud from each pair, and move the **Delay** of the pair that is **ahead** until both sound together. You can do this while the movie plays.

After that, DuoSound keeps them in step by itself for the whole movie.

### Laptop speakers are muted
While headphones are playing, DuoSound mutes the laptop speakers so the movie isn't heard out loud.

- Press **Unmute speakers** next to Stop (or in the tray menu) to hear it from the laptop too. Press again to mute.
- Stop puts the speakers back exactly as they were.
- To switch this off, open **Options** and untick "Mute the laptop speakers while headphones play".

### Lip sync
Bluetooth adds about 0.15 to 0.35 seconds of delay, so speech can look slightly late. Many players can delay the picture's audio to match. In VLC: Tools → Track Synchronization → Audio track synchronization (use a negative value). Browsers don't have this setting.

### How many headphones?
DuoSound itself has no limit, but every Bluetooth headset shares the laptop's one Bluetooth radio.

- **2** pairs work on almost every laptop. **3** usually work. **4–5** depend on the laptop and may crackle.
- A cheap **USB Bluetooth adapter** adds a second radio: connect some headphones to it.
- **Wired headphones** (jack or USB) don't use the radio at all.
- Keep the headphones near the laptop, and use 5 GHz Wi-Fi if you can (2.4 GHz Wi-Fi shares the air with Bluetooth).

### No sound in the headphones
- Look at the **Sound in** meter. If it stays empty, Windows isn't playing into the source: leave "Switch Windows' sound output to the source" on, or choose the source in the taskbar speaker menu.
- Make sure the movie is actually playing. Pause and play again if the app was open before Start.
- Check that the source isn't muted in Windows (except the laptop speakers, which DuoSound mutes on purpose).
- Press **Test** next to a pair of headphones to hear a beep in just that one.

### Troubleshooting
| Problem | Fix |
|---|---|
| Headphones aren't listed | Connect them in Windows (Settings → Bluetooth & devices), then press **Refresh**. Headphones must say Connected, not only Paired. |
| No sound at all | See **No sound in the headphones**. |
| One pair sounds tinny or mono | An app opened its microphone (Teams, Discord, Zoom…), which puts the headset into call mode. Close that app, or turn off "Hands-free telephony" for the headset in Control Panel → Devices and Printers. |
| Crackles with 3 or more headphones | One Bluetooth radio is at its limit. See **How many headphones?** |
| Headphones dropped out | DuoSound reconnects them by itself every 2 seconds; the others keep playing. |
| Echo between two pairs | See **Getting headphones in sync**. |
| Windows says "Windows protected your PC" | The program isn't signed yet. Click **More info → Run anyway**. |
| DuoSound is already running | Look for the orange icon in the taskbar's tray (click the ^ arrow). |
| Something else | Press **Copy diagnostics** below and send it together with your question. |
<!-- help:end -->

## Support DuoSound
DuoSound is free. If it made your movie night better, you can say thanks with a small donation:
UPI ID **amonh7-1@okicici**, or scan the QR code on the app's **Donate** page
([`Donate ME QR/GooglePay_QR.png`](Donate%20ME%20QR/GooglePay_QR.png)).

---

## For developers
| Task | How |
|---|---|
| Run from source | Python 3.10+, `pip install -r requirements.txt`, then double-click **`Run DuoSound.bat`** (or `pythonw main.py`) |
| Build the .exe | `pip install pyinstaller`, then `build_exe.bat installer` → `dist\DuoSound.exe` + `dist\DuoSound_Lite.exe` (and `dist\DuoSound_Setup.exe` if [Inno Setup](https://jrsoftware.org/isdl.php) is installed). `build_exe.bat portable` builds the ZIPs instead. The script needs one of those two arguments. |
| Check devices in a terminal | Double-click **`Test Devices.bat`** (`--yes`, `--no-beep`, `--no-art`, `--user NAME`) |
| Run the tests | `python tests/test_backend.py` and `python tests/test_ui_messages.py` |
| Bump the version | `python tools/bump_version.py patch\|minor\|major` — updates `__init__.py`, `version_info.txt` and the installer script together. `--check` verifies they agree. |
| Cut a release | Follow [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) |
| Git workflow | Conventional Commits, feature branches — see [CONTRIBUTING.md](CONTRIBUTING.md) |
| Change the look or wording | Only `duosound/ui/theme.py` (see [DESIGN.md](DESIGN.md)) |
| Change help text | `duosound/help_text.py`, then regenerate this README's Help section |
| Design and reasons | [CONTEXT.md](CONTEXT.md) · product: [PRODUCT.md](PRODUCT.md) · work log and test results: [PROGRESS.md](PROGRESS.md) |

Logs: `logs\` when run from source, `%LOCALAPPDATA%\DuoSound\logs` for the .exe.
Settings: `%APPDATA%\DuoSound\settings.json`.
