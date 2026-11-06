# DuoSound — Project Context

> One laptop, two (or more) Bluetooth headphones, one movie — everyone hears it at the same time.
> This file explains **what** we are building, **how** it works and **why** each decision was made.
> Keep it current whenever a decision changes. Day-by-day work is tracked in [PROGRESS.md](PROGRESS.md).
> Who it's for and the product principles: [PRODUCT.md](PRODUCT.md). Visual system: [DESIGN.md](DESIGN.md). Made by **Amon Lal**.

## 1. Goal
Let 2+ people watch a movie/video on one Windows laptop, each wearing their own Bluetooth headphones,
with the audio playing on all headphones **in sync** (no echo between people).

## 2. The problem
- Windows can *connect* several Bluetooth headphones at once — each one appears as a separate audio output.
- But Windows plays sound to only **one** default output at a time. There is no built-in "play on all" for normal (A2DP) headphones.
- Every Bluetooth headset has its own delay (≈100–300 ms) and its own clock, so even if we copy the sound, the headsets would be out of step and slowly drift apart.

## 3. Check first: built-in Windows "Shared audio"
Windows 11 24H2+ has **Settings → Bluetooth & devices → Shared audio** for **LE Audio** headphones on supported laptops.
If the laptop and both headsets support LE Audio, it works without this app. Most headphones today are classic A2DP, which is what DuoSound is for.

## 4. How DuoSound works
```
Movie player ──► Windows default output = SOURCE device (not one of the headsets)
                    │  WASAPI loopback capture — 48 kHz, stereo, float32, 10 ms blocks
                    ▼
            Capture thread ──► fan-out ──► Ring buffer A ──► Output thread A ──► Headset A
                                    └────► Ring buffer B ──► Output thread B ──► Headset B   (… N)
Each output: + delay (ms)  × volume  ~ drift correction (tiny resampling, ±0.3 %)
```
1. **Capture** — the app records whatever Windows plays on the *source* device ("loopback").
2. **Fan-out** — every captured block is copied into one ring buffer per headset.
3. **Play** — each headset has its own thread that pulls from its buffer and plays it. `player.play()` blocks at the headset's own clock pace.
4. **Delay** — each buffer is kept at `base latency + delay_ms`. A headset that is "faster" gets extra delay so all line up.
5. **Drift correction** — each output measures its buffer level (smoothed). If it is creeping up/down, the output reads slightly more/fewer input frames per block and stretches them to exactly one block (linear interpolation). This cancels clock drift over a 2-hour movie without audible pitch change. Big jumps (after a delay change or a hiccup) are corrected at once by dropping frames or inserting silence.

### Source device options (best first)
| Option | How | Notes |
|---|---|---|
| **VB-CABLE** (free virtual driver) | Set "CABLE Input" as Windows default output | Cleanest. Nothing plays out loud. Needs a driver install. |
| **Unused HDMI / Digital Output** | Set it as default output while no TV/monitor is attached to it | Silent sink, no install. Found on Amon's laptop: *Digital Output (HD Audio Driver for Display Audio)*. |
| **Laptop speakers** | Default output = speakers; DuoSound mutes them while headphones play | No install. On Amon's laptop (Realtek) the speakers' loopback is recorded *before* volume/mute, so muted speakers still feed the headsets (tested 2026-11-06). Other laptops may differ: if the headsets go silent, press Unmute. |

**Rule:** the source can never be one of the headsets (that would play the movie twice, out of step). The app enforces this.

**Important (found in testing):** WASAPI loopback records the sound **after** the device's Windows volume. A muted or 0 % source = silence.
Windows keeps an unused HDMI output muted at 0 %, so on Start DuoSound checks the source and offers to set it to 100 % / unmuted,
then restores the old setting on Stop (`duosound/volume.py`). The Realtek laptop speakers behave differently: their loopback is taken
*before* volume and mute, so they can be muted while they are the source (tested 2026-11-06).

**Speaker mute (2026-11-06, Amon's request):** while Bluetooth or wired headphones are playing, DuoSound mutes the laptop speakers
(option "Mute the laptop speakers while headphones play", on by default). An *Unmute speakers* button (and a tray item) turns them back on;
Stop puts the original mute state back. Speakers ticked as an output are never muted.

**Never leave Windows changed:** before changing anything, DuoSound writes what it changes to `%APPDATA%\DuoSound\restore.json`.
Stop, Quit (even during a Stop) and the next launch after a crash all put Windows back from it, then delete it.

### How outputs are recognised (2026-11-06, public-release audit)
Each output's registry entry (`HKLM\...\MMDevices\Audio\Render\<guid>\Properties`, read in the 64-bit view) gives a **driver path** and a
**form factor**. Both work in every Windows language:

| Driver path / form factor | Kind | Behaviour |
|---|---|---|
| `BTHENUM\{0000110B…}`, `BTHLE…` | bluetooth | listener, ticked by default |
| `BTHHFENUM` | hands-free | **hidden**: playing to it puts the headset in mono call quality (Windows 10 lists it; Windows 11 26300 doesn't) |
| form factor 3/5 (headphones/headset), or `USB\` with a headset name (Corsair, Razer, HyperX…) | wired headphones | listener, never muted |
| form factor 1 on the built-in chip (`HDAUDIO`/`INTELAUDIO`) | speakers | muted while headphones play |
| form factor 8/9 | hdmi/digital | good silent source |
| name `CABLE`/VB-Audio | virtual cable | best source |

Name guessing is only the fallback when the registry can't be read.

## 5. Sync
- **Manual:** a delay slider per headset (0–1000 ms, which also covers slow Bluetooth speakers). Play a clicky video, wear one earbud from each headset, slide until the clicks line up.
- **Assisted calibration:** "Calibrate" plays a short click on each headset in turn. The **laptop's** microphone hears it and the app measures each headset's delay, then sets the sliders (fastest gets the most extra delay). Headset microphones are never used, because opening one switches that headset into low-quality "hands-free" mode.
- **Drift:** automatic, see §4.5.

## 6. Key decisions (and why)
| Decision | Why |
|---|---|
| Python 3 + `soundcard` (WASAPI) | Loopback capture and "open any output by id" are built in, pure Python wrapper, no compiled extras. |
| numpy | Fast copying, volume and resampling of audio blocks. |
| tkinter GUI + pystray tray icon | Amon chose a small GUI/tray app. tkinter ships with Python; pystray is tiny. |
| 48 kHz stereo float32, 10 ms blocks | Native rate of Windows audio engine and Bluetooth A2DP; small blocks = low added latency. |
| Windows buffers: player 80 ms, capture 100 ms | 10 ms buffers made devices run dry on tiny stalls → extra delay + jumps (measured). |
| Own capture reader (`read_available`) instead of `soundcard.record()` | `record()` invents zeros during short packet gaps, then the real audio arrives too → delay grew up to 1 %. We never invent audio. |
| Controller: 60 ms cushion, ±3 ms dead band, 20 ms → 0.3 %, max 0.6 %, jump only >80 ms | Tuned from measurements: holds ±5–15 ms, recovers Windows glitches at ~3 ms/s without audible jumps. |
| Rates + `late`/`maxgap` in every 5-s STATS log line | Lets any future sync problem be diagnosed from the log alone. |
| One thread per output | Each headset runs at its own clock; a slow/disconnected headset can't stall the others. |
| Buffer-level drift control (not timestamps) | Simple and robust; the buffer level *is* the accumulated clock difference. |
| Settings in `%APPDATA%\DuoSound\settings.json`, validated on load | Keeps user state out of the program folder. Wrong types are dropped, numbers are clamped and an unreadable file is kept as `settings.bad.json`, so a bad file can never stop the app starting. |
| Logs in `logs/` (from source) or `%LOCALAPPDATA%\DuoSound\logs` (.exe / read-only folder) | Everything is logged and easy to find. A log folder that can't be written never stops the app. |
| Mute laptop speakers while headphones play (option, default on) | Amon: speakers must be silent when headsets are in use, with a way to unmute. Only the mute flag is changed, never the level. |
| Wired headphones = their own kind (`wired headphones`) | They are listeners like Bluetooth headsets: ticked by default, never muted, never suggested as source. |
| GUI app → no terminal welcome screen | `amon_welcome` is for terminal scripts. `tools/test_devices.py` uses it (embedded copy, so it runs anywhere). |
| **UI / backend split** | `duosound/controller.py` (AppController) does everything; `duosound/ui/` only draws and calls it. **Rule: nothing in `duosound/ui/` imports `engine`, `volume`, `devices` or `calibrate`.** Changing the look can't break the audio. |
| All look + wording in `duosound/ui/theme.py` | One design/UX file holds the colours, fonts, spacing, icons and every sentence. A redesign touches only this file (see DESIGN.md). |
| Help text in `duosound/help_text.py` | The in-window Help and README's help section come from the same text (`python -m duosound.help_text`). |
| All pycaw/COM calls on one thread (`volume._ComThread`) | COM pointers freed by the garbage collector on another thread crashed the process (access violation in `Release`, found in testing 2026-11-06). |
| Volume lookup opens one device directly | pycaw's `GetAllDevices()` took ~250 ms per call (seconds on PCs with many devices); a direct `GetDevice(id)` takes ~3 ms. |
| Single `.exe` (PyInstaller one-file, windowed) | Public users mustn't need Python or pip. `build_exe.bat` → `dist\DuoSound.exe`; icon + version info (author Amon Lal) come from `packaging/`. |
| Single instance (named mutex) + DPI aware | A second double-click brings the running window forward instead of starting a second engine. Text stays sharp at 125/150 % scaling. |
| Help, Donate and confirmations are inline pages/banners, not popups | Fewer lost windows; every problem banner has a "How to fix" link into Help. |

### Decision (2026-11-06): Flet for the window, with calm scenery (was an open question)
Amon wants glassmorphism (frosted, see-through panels) over an animated moon/sun scenery with trees and grass moving in the wind.
tkinter can't make panels transparent; Flet (Flutter) can. Because of the UI/backend split only `duosound/ui/` would be rewritten.
Prototype comparison: Flet ~24 % CPU / ~410 MB / ~115 MB download vs tkinter ~13 % / ~80 MB / 35 MB. Amon chose **Flet, but calmer**:
the scenery freezes while a movie plays. New UI in `duosound/ui_flet/`; tkinter `duosound/ui/` stays as a fallback until parity is verified.

## 7. Constraints & known limits
- **One Bluetooth radio** carries all streams. Two A2DP streams usually work; three may stutter on weak adapters. DuoSound warns when more than 3 Bluetooth headsets are ticked (a USB Bluetooth adapter adds a second radio). Tips: headsets close to the laptop, prefer 5 GHz Wi-Fi (2.4 GHz Wi-Fi shares the air with Bluetooth).
- **Hands-free mode:** if any app opens a headset's microphone (Teams, Discord…), that headset drops to mono low quality. Disable "Hands-Free Telephony" for the headset in Control Panel → Devices and Printers if this happens.
- **Absolute latency** (≈150–350 ms total) means lip-sync is a little late. Many players (VLC, MPC-HC) have an audio-delay setting to compensate; browsers don't.
- WASAPI loopback delivers no data during silence — outputs just play silence then; this is normal.

## 8. Files
| File | Purpose |
|---|---|
| `main.py` | Entry point: single-instance check, DPI awareness, starts AppController + MainWindow |
| `PRODUCT.md` / `DESIGN.md` | Who it's for and principles / visual system (impeccable) |
| `duosound/controller.py` | **Backend API for the UI**: devices, start/stop, restore Windows, speaker mute, calibrate, diagnostics |
| `duosound/engine.py` | Capture, ring buffers, output threads, delay, volume, drift correction, reconnect |
| `duosound/devices.py` | List outputs and classify them from the registry (driver path + form factor); pick the source |
| `duosound/volume.py` | Volume / mute / Windows default output (pycaw) on one COM thread |
| `duosound/calibrate.py` | Chirps + laptop-mic measurement of each headset's delay |
| `duosound/settings.py` | Load (validated) / save settings; `restore.json` crash recovery |
| `duosound/log_setup.py` | Daily log file + in-window log pane |
| `duosound/help_text.py` | All Help topics (in-window Help + README) |
| `duosound/resources.py` | Finds bundled files (donate QR) from source and inside the .exe |
| `duosound/ui/theme.py` | **Design/UX file**: colours, fonts, spacing, icons, all wording |
| `duosound/ui/main_window.py` | Window: source, headphones, action bar, banners, pages, tray |
| `duosound/ui/widgets.py` | Headphone row, scroll list, inline banner |
| `duosound/ui/help_page.py`, `about_page.py` | Help (Read me) page; About + Donate page |
| `duosound/ui/scenery.py` | Animated moon/sun landscape (tkinter Canvas); **not wired in yet**, pending the tkinter/Flet decision |
| `Donate ME QR/GooglePay_QR.png` | Amon's UPI QR, shown on the Donate page (bundled into the .exe) |
| `packaging/` + `build_exe.bat` | Build `dist\DuoSound.exe` (icon, version info, PyInstaller spec) |
| `tools/test_devices.py` | Terminal check: list devices, play a test tone on each (amon_welcome style, embedded) |
| `tools/demos/scenery_demo.py` | Standalone demo of the animated scenery (Day/Night button) |
| `tests/test_backend.py` | 28 checks: device types, settings, restore/crash recovery (real speakers, stand-in engine), ring buffer |
| `tests/test_ui_messages.py` | 9 checks: one auto-vanishing message, Start/Calibrate greyed out with a reason |
| `Run DuoSound.bat` | Run from source (finds `pyw`/`py`/`pythonw`/`python`, explains if Python is missing) |
| `Test Devices.bat` | Double-click launcher for the device test (Windows Terminal) |

## 9. Glossary
- **A2DP** — the classic Bluetooth profile for stereo music.
- **LE Audio / Auracast** — newer Bluetooth audio that supports sharing natively.
- **WASAPI** — Windows audio API. **Loopback** = recording what an output is playing.
- **Ring buffer** — fixed-size circular queue of audio samples.
- **Drift** — two devices' clocks run at very slightly different speeds (e.g. 48 000 vs 48 005 Hz), so they slowly move apart.
