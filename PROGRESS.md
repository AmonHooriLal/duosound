# DuoSound — Progress Log

Status: ☐ not started · ◐ in progress · ☑ done · ⚠ problem
Newest entries at the bottom of each phase. Design and reasons are in [CONTEXT.md](CONTEXT.md).

## Overview
| # | Phase | Status |
|---|---|---|
| 0 | Plan approved | ☑ |
| 1 | Docs + skeleton + logging | ☑ |
| 2 | Devices + test-tone tool | ☑ |
| 3 | Engine MVP (capture → many outputs) | ☑ |
| 4 | Sync: delay, volume, drift correction | ☑ (measured, see below) |
| 5 | GUI + tray + settings + launcher | ☑ |
| 6 | Calibration with laptop mic | ◐ code + synthetic test done; real-earbud test pending |
| 7 | Polish: reconnect, errors, README | ◐ |
| 8 | **Real-world test with 2 headsets + a movie** | ◐ short test passed + reconnect ✔; full movie pending |
| 9 | Mute laptop speakers while headphones play | ☑ (real headsets pending) |
| 10 | **Public release: compatibility audit, fixes, new UI, Help, Donate, .exe** | ☑ built + tested here; real headsets + other PCs pending |
| 11 | Editable Delay/Volume, responsive rows, light mode, resize grip | ☑ |
| 12 | One auto-vanishing message at a time; Start/Calibrate greyed out with a reason | ☑ |
| 13 | **Design critique (27/40) + fixes, animated scenery, Flet vs tkinter decision** | ◐ in progress, see Phase 13 |
| 14 | Flet glass window built and verified | ☑ |
| 15 | Dual-build pipeline + 20ms saver mode | ☑ |
| 16 | **Audio crackling fix during UI interaction** | ☑ |
| 17 | **Release engineering: build fixes, installer wizard, versioning, first public GitHub push** | ☑ |

---

## Phase 0 — Plan
- **2026-11-05** ☑ Plan approved (GUI/tray app chosen; context + progress files + full logging requested).
  VB-CABLE question left open, so both source modes are supported.

## Phase 1 — Docs + skeleton + logging
- **2026-11-05** ◐ Environment checked: Python 3.14.7, numpy, Pillow, tkinter, amon_welcome 1.4.0 present.
  Installed `soundcard` and `pystray` with pip.
- **2026-11-05** Devices found on the laptop:
  `Speakers (Realtek(R) Audio)`, `Headphones (OnePlus Buds 4)` (Bluetooth, current default), `Digital Output (2- HD Audio Driver for Display Audio)` (HDMI).
  No VB-CABLE. → Decision: the unused HDMI Digital Output can be a silent source with no install (added to CONTEXT §4).
- **2026-11-05** Created CONTEXT.md, PROGRESS.md, requirements.txt, `duosound/__init__.py` (48 kHz / stereo / 10 ms blocks), `duosound/log_setup.py`
  (daily rotating file `logs/duosound_YYYY-MM-DD.log` at DEBUG, GUI queue + console at INFO, uncaught errors logged). ☑ Phase 1 done.

## Phase 2 — Devices
- **2026-11-05** ◐ `duosound/devices.py`: lists outputs, classifies them (bluetooth / virtual cable / hdmi / speakers), suggests source + targets.
- **2026-11-05** ⚠ First Bluetooth detection used PowerShell `Get-PnpDeviceProperty` → took >20 s (timeout). Name-guess fallback still worked.
  → Fixed: read the registry `HKLM\...\MMDevices\Audio\{Render,Capture}\<guid>\Properties` value `{b3f8fa53-0004-438e-9003-51a46e139bfc},2`
  (driver path). Path containing `BTHENUM` / `BTHHFENUM` / `BTHLE` = Bluetooth. Whole device scan now ~0.1 s. Buds detected correctly.
- **2026-11-05** `laptop_microphones()` excludes headset mics (opening them forces hands-free mode). Found: Intel Smart Sound mic array.

## Phase 3 + 4 — Engine (capture → outputs, delay, drift)
- **2026-11-05** Checked: soundcard works with numpy 2.5.2; loopback capture keeps delivering zero frames in real time during silence
  (no stalls), so outputs only underrun on real problems.
- **2026-11-05** ◐ `duosound/engine.py`: Ring buffer per output, capture thread fan-out, one output thread per headset,
  base cushion 60 ms + delay, smoothed level control (±0.3 % resampling), jumps for >40 ms errors, reconnect loop, stats every 5 s (DEBUG).
- **2026-11-05** Headless test (16 s, source = HDMI Digital Output, targets = Buds + laptop speakers at volume 0):
  buffers held at target (60.3/60, 159.7/160 ms), delay change 0→150 ms jumped once to 210 ms target, 0 underruns, 0 reconnects. ✔
- **2026-11-05** ⚠ Test tone fed into the HDMI output was captured at ~1e-8 (silence). Cause: Windows had *Digital Output* at **0 % and muted**
  and **loopback records after the endpoint volume**. With it set to 100 %/unmuted the tone came through exactly (0.00109 vs 0.001 fed);
  volume restored to 0 %/muted afterwards.
  → Decision: new `duosound/volume.py` (pycaw). On Start the app checks the source; if muted/low it offers to set 100 % for the session
  and restores the old value on Stop. Consequence: with **laptop speakers** as source the movie also plays out loud (can't mute them) —
  VB-CABLE or a silent HDMI output is the real answer (CONTEXT §4 updated).
- **2026-11-05** ⚠ `pycaw`/`comtypes` crashed with "Cannot change thread mode" next to soundcard → fixed with `sys.coinit_flags = 0`
  before importing comtypes (done in `volume.py` and `main.py`).

### Sync measurements (scratch test: quiet −54 dB noise bursts into the source, loopback-record source + speakers, compare onsets)
- **Run 1** (60 s, compared Buds vs speakers) — ⚠ invalid: the Buds loopback peaked at 0.44 because other audio was playing to the Buds
  (they were the Windows default). → Re-designed: compare *source* vs *speakers* loopback (both carry only test audio).
- **Run 2** (90 s): delay change +100 ms measured **97.5 ms** ✔, but offset wandered 69–97 ms and both outputs jumped 11 times in total; one Buds underrun.
  → Cause A: `blocksize=BLOCK` gave Windows only a **10 ms buffer** for players and capture. Fixed: player buffer 80 ms, capture buffer 100 ms
  (`PLAYER_BUFFER_MS`, `CAPTURE_BUFFER_MS`), calibration uses the same. Jump threshold 40 → 80 ms.
- **Run 3** (90 s): delay change 106 ms, mostly ±5 ms, but slow 30–100 ms excursions; speaker buffer stuck ~50 ms over target with
  correction maxed at +0.3 %. → Added permanent rate counters to the 5-s STATS log line (captured / read / played / silence / dropped fps).
- **Rate test:** loopback capture averages 1.0002× real time (normal) — but one 5-s interval showed **48 466 fps (+1 %)**.
  → Cause B: `soundcard`'s `record()` invents zeros when WASAPI sends no packets for >40 ms, then Windows delivers the real audio anyway
  → extra audio → delay grows. **Fixed:** own `read_available()` in engine.py reads only real packets, never invents audio. True silence
  (paused movie) now makes outputs refill and re-align. Result: capture steady at ~48 000 fps, 0 jumps, 0 underruns in 60 s.
- **Controller tuned:** max speed change 0.3 → 0.6 % (≈1/10 semitone), 20 ms error → 0.3 %, ±3 ms dead band, faster smoothing (0.5 s).
- **Run 4** (90 s): delay change 112.8 ms (≈100 + recovery in progress); after each Windows-side step (+40–50 ms) the delay now returns smoothly
  at ~3 ms/s with no jumps.
- **Own-stall check:** added `late` / `maxgap` to STATS (time our thread is away from the device between blocks). Normal app run, 45 s:
  **maxgap ≤ 1 ms, late 0**, Buds 58–76 / 60 ms, speakers 157–168 / 160 ms, 0 jumps. → The remaining steps come from Windows/the measuring
  setup (extra loopback recorders), not DuoSound. Relative sync between headsets ≈ ±15 ms in normal use (echo is noticed above ~30 ms).
- ☑ Phases 3 + 4 done.

## Phase 5 — GUI + tray + settings + launcher
- **2026-11-05** `duosound/gui.py` (tkinter, Segoe UI, warm orange), `duosound/settings.py` (`%APPDATA%\DuoSound\settings.json`), `main.py`,
  `Run DuoSound.bat` (pythonw, no console). Tray icon via pystray (Show / Start-Stop / Quit); closing while running hides to tray.
- **2026-11-05** `duosound/volume.py` gained `default_output_id()` / `set_default_output()` (pycaw `SetDefaultDevice`) → "auto setup" option:
  on Start switch Windows output to the source + unmute it, on Stop put both back.
- **2026-11-05** GUI smoke test (auto-setup off): window opens, Start → "Playing · buffer 73 ms", Stop → clean exit. Screenshot checked.
  ⚠ Found: two warnings overwrote each other in one label → now joined + logged.
- **2026-11-05** Auto-setup test: before = default Buds, source 0 % muted → during = default HDMI source at 100 % → after Stop = default Buds,
  source 0 % muted. **RESTORED OK** ✔
- ☑ Phase 5 done.

## Phase 6 — Calibration
- **2026-11-05** `duosound/calibrate.py`: laptop mic (headset mics excluded), 4 chirps per headset, cross-correlation, median latency,
  suggested delay = slowest − own. Synthetic test: true 183 ms → found **183.0 ms** (confidence 109).
  ⚠ Pure noise scored 6.8 against threshold 6 (false hit) → threshold raised to 12.
- ◐ Not yet tried with real chirps through real earbuds (needs Amon + 2 headsets; it plays audible chirps).

## Phase 7 — Polish
- **2026-11-05** README.md written (setup, source options, sync by Calibrate / by ear, lip sync, tray, troubleshooting).
- **2026-11-05** ⚠ Final GUI test with nothing playing: capture 0 fps and headsets stuck on "Filling buffer…" (correct, but confusing).
  → Engine now reports capture state `waiting` after 0.5 s without packets; GUI shows "Waiting for sound… - start the movie".
  Re-test: no sound → "Waiting for sound…"; feeder on → "Playing · buffer 65 ms"; feeder off → back to waiting; Windows settings restored ✔.
- **2026-11-05** All modules compile (`py_compile`). Reconnect loop exists for outputs and capture (2 s retry) — not yet tested by
  switching a headset off mid-play (needs Amon).
- ◐ Open items for Amon: real 2-headset movie test, real Calibrate run, headset off/on mid-play, optional VB-CABLE install.

## Phase 2 tool
- **2026-11-05** `tools/test_devices.py` + `Test Devices.bat` / `tools/run_test_devices.cmd` (amon_welcome 1.4.0 welcome, bot progress,
  `--yes / --no-art / --user / --no-beep`, Windows Terminal launcher). Silent run OK. ⚠ `summary_box` needs (label, value) pairs → fixed.

## Phase 8 — Real-world test
- **2026-11-06** First real 2-headset test by Amon: source = *XV272U (HD Audio Driver for Display Audio)* (monitor, HDMI),
  targets = *OnePlus Buds 4* + *OnePlus Bullets Wireless Z3*. Auto-setup switched + restored Windows output every time ✔.
  - Clean run (42 s): both buffers 57–71 / 60 ms, speed ≤ 0.12 %, 0 underruns, 0 jumps, maxgap ≤ 2 ms ✔.
  - Delay by ear: Buds slider tried 0–45 ms, ended at **0 ms** (no offset needed for this pair).
  - **Reconnect** ✔: Z3 switched off mid-play (`0x88890004` device invalidated → "no device with id" ×2), reopened after **6 s**,
    refilled to 60 ms and played on; Buds kept playing throughout. While away its ring buffer overflowed (≈4.2 s discarded) — expected, no stale audio.
  - Earlier tries (16:55–16:59) used a headset (Buds / Z3) as the **source** — then that headset hears the movie directly, ahead of the copy.
    Calibrate with Z3 found no chirps (headset not near the mic) → returned no suggestion, as designed.
  - ◐ Still open: a full-length movie (drift over 1–2 h; longest run so far 65 s).
- **2026-11-06** Monitor unplugged → the HDMI Display Audio output disappears from Windows. Test with source = **Speakers (Realtek)**,
  targets = Buds 4 + Z3, 66 s: Amon: "working fine". Buffers 63/60 ms, 0 underruns, 0 jumps, settings restored (speakers back to 49 %) ✔.
  ⚠ On Start both headsets failed once with `0x88890004` (device invalidated, ~0.3 s after Windows' default output was switched) and
  reopened after the 2-s retry → ~2 s of silence at start. ⚠ The "fix source volume" step raised the **speakers to 100 %** → movie plays loudly
  out of the laptop. Possible fixes (not done): only unmute / raise speakers to a low level; wait briefly after switching the default output.

## Phase 9 — Mute laptop speakers while headphones play (Amon's request)
- **2026-11-06** Test first: Realtek speakers set to *muted 100 %*, *0 %* and *100 %* while a quiet tone played into them → loopback captured the
  tone at the same level (1.08e-3) every time → on this laptop muting the speakers does **not** silence DuoSound's capture.
- Added: option *"Mute the laptop speakers while headphones play (Bluetooth or wired; put back on Stop)"* (default on, saved as
  `mute_speakers`), *🔊 Unmute / 🔇 Mute speakers* button next to Stop while running, tray item *Mute / unmute laptop speakers*.
  Only the mute flag is changed; Stop restores the original mute state. When the speakers are the source they are now muted
  instead of being turned up to 100 % (fixes the "plays loudly" problem above).
- Added device kind `wired headphones` (names with Headphone/Headset/Earphone, not Bluetooth): ticked by default like Bluetooth, never muted.
- Test (real speakers, stand-in headset, dummy engine; headsets weren't connected): Start mutes ✔, Unmute/Mute ✔, Stop restores
  mute + level + default output ✔, button hidden ✔, option off / no headset → no mute ✔, wired/speaker naming ✔ (10/10).
  ⚠ First run caught a bug (`t.target_id` → `t.id`), fixed before the pass.
- ◐ Pending: try it with the real headsets connected.

## Phase 10 — Public release (Amon: "public release, single .exe, zero setup")
### Audit (2026-11-06): 3 agents, read-only, key claims re-checked by hand
- **Windows compatibility (Sonnet):** dependencies install as wheels on Python 3.9–3.13 (amd64), plus win32/arm64 on 3.12. Code parses as 3.9.
  Found:
  - The launcher only tried `pythonw`/`python`, which hits the Microsoft Store stub on fresh PCs.
  - A log folder that can't be written killed the app silently.
  - 32-bit Python sees an empty MMDevices registry key, so no Bluetooth was found.
  - pycaw `GetAllDevices()` took 255–271 ms per call on the GUI thread.
  - Text was blurry at 125 %+ and the window was clipped on 1366×768 at 125 %.
  - Old soundcard 0.4.3–0.4.5 breaks Calibrate on numpy 2.
  - `pycaw>=20240316` matches no release.
  - English-only name regexes.
  - There was no single-instance guard.
- **Bluetooth coverage (Sonnet):** 121 real endpoint names. Registry path 94/94 Bluetooth correct; name fallback 79/94. Found:
  - **Hands-free endpoints (`BTHHFENUM`) were listed and pre-ticked** (Windows 10 shows them; this PC's registry has 2, not listed on 26300).
  - USB dongle headsets named "Speakers (Corsair…)" were treated as speakers and **muted**.
  - The `Headphones \(` fallback was over-broad.
  - The calibration window (0.6 s) was too short for slow Bluetooth speakers.
  - soundcard opens streams with AUTOCONVERTPCM, so 44.1 kHz / mono devices play (verified in source).
- **Engine robustness (Haiku):** ring buffer correct under concurrent load; 8 outputs ≈ 0.25 ms CPU per 10 ms. Found:
  - **Quit during Stop skipped the Windows restore** (confirmed by reading the code).
  - A crash/kill left Windows changed.
  - Malformed settings crashed startup; delay/volume were not clamped.
  - Stop joined threads 3 s × N; `_tick` died on any exception.
  - False "6150 ms late" after a reconnect (seen in the 11-06 log); a silence-jump loop after a delay change.

### Fixes
- `devices.py`: one registry read (64-bit view) gives **driver path + form factor** per output, independent of the Windows language.
  Hands-free is hidden. USB headsets are wired listeners and never muted. Speakers are only the built-in chip. Name guessing is the fallback.
- `controller.py` (new): all logic out of the window. Restore state goes to `restore.json` **before** any change; Stop, Quit-during-Stop and the next
  launch after a crash all restore. The default output is never switched when the current one can't be read. Waits 0.5 s after switching the output
  (fixes the start-up `0x88890004` seen on 11-06). Warns at more than 3 Bluetooth headsets. Diagnostics text for bug reports.
- `settings.py`: validated + clamped, BOM-tolerant, unreadable file kept as `settings.bad.json`. `engine.py`: clamps on load, one 3-s Stop
  deadline for all threads, `_last_feed` reset on reconnect, refill instead of a silence-jump loop, guarded stats thread. `calibrate.py`: 1.0 s search,
  1.2 s gap. Delay slider 0–1000 ms.
- `volume.py`: direct `GetDevice(id)` (**3 ms vs 234 ms**). ⚠ Testing found a real crash: COM pointers freed by the garbage collector on
  another thread → access violation in `IUnknown.Release`. → **All pycaw/COM work now runs on one dedicated thread** with `gc.collect()` there.
- `log_setup.py`: `%LOCALAPPDATA%\DuoSound\logs` for the .exe or a read-only folder; never fatal.
- `main.py`: DPI aware, single instance (a second launch brings the window forward), plain error box. `Run DuoSound.bat`: `pyw` → `pythonw` → `py` → `python`,
  with clear install steps when none works. `requirements.txt`: `soundcard>=0.4.6,<0.5`, `pycaw>=20251023`.
- `tools/test_devices.py`: amon_welcome 1.4.0 **embedded**, so it runs on any PC.

### New UI (Amon: Help in the window, optimise the UI, credit + donate, design file separate from the backend)
- `duosound/ui/` package. **`theme.py` is the single design/UX file** (tokens, styles, drawn icons, every sentence). Views talk only to `AppController`.
  Checked with grep: `ui/` imports no `engine`/`volume`/`devices`/`calibrate`.
- `/impeccable` init: PRODUCT.md written from Amon's answers (public release, single .exe, zero setup). DESIGN.md records the system.
- Critique of the old window: jargon in the headings, a truncated source box, an empty state with no action, technical checkboxes in the main flow,
  the log taking 1/3 of the window, no help/credit. New design:
  - a dark warm "movie night" theme, with orange only for Start, selection and state;
  - Options collapsed; product names without the "Headphones (…)" wrapper; status under each name;
  - an empty state with Bluetooth settings + Refresh;
  - inline banners with "How to fix" (no popups);
  - Help page (8 topics + Copy diagnostics / Open log folder / Bluetooth settings), Donate & about page (QR 220–300 px, UPI ID + Copy);
  - "Made by Amon Lal" footer, dark title bar, Space = Start/Stop, F1 Help, F5 Refresh.
  - All text colour pairs pass ≥ 4.5:1 (lowest 5.46:1).
- `help_text.py` is the one source for the in-window Help and README's Help section.

### Packaging
- `build_exe.bat` + `packaging/` (icon at all sizes, version info: company/author **Amon Lal**) → `dist\DuoSound.exe`, 35 MB, one file, windowed.

### Tests (2026-11-06, all on this PC; headsets were not connected)
- **Backend 28/28:**
  - classification 18/18 (incl. German/Chinese speaker names, Corsair/Razer USB, hands-free, LE, HDMI TV, VB-CABLE);
  - name fallback 6/6; this PC's 2 hands-free endpoints recognised and never listed;
  - 6 broken settings files survive; values clamped;
  - real speakers: Start mutes (level kept), Unmute/Mute, **quit during Stop restores**, **crash → next launch restores**;
  - radio warning at 4 Bluetooth headsets; diagnostics; ring buffer order under load.
- **Real app:** window opens; a second launch exits in 0.3 s and brings it forward; closes cleanly. Double-clicking `Run DuoSound.bat` works.
- **.exe:** opens in 2.5 s; Donate page shows the bundled QR; log goes to `%LOCALAPPDATA%\DuoSound\logs`. It also ran with **no Python on PATH**
  from a folder named "Clean PC test – Ünïcødé folder".
- **Screens:** 980×720, 760×520 with 5 headphone rows (scrolls; names stay visible), simulated 150 % scaling (sharp).
- ◐ **Not yet done:**
  - a real Start/Stop with the two headsets through the new UI, and Calibrate with real earbuds;
  - 3–5 headsets (find the radio limit);
  - a full-length movie;
  - running the .exe on another PC or in Windows Sandbox (not installed here; needs admin + reboot).

## Phase 11 — Friendlier controls, light mode, resizable (Amon's request, 2026-11-06)
- Done with 2 parallel agents on separate files (theme/window vs. headphone rows), then merged and checked by screenshots.
- **Delay / Volume:** each row has its own captions, slider **and an editable number box** (ms / %), whole numbers only (typing letters is ignored,
  9999 → clamped to 1000, empty → reverts), arrows/wheel step 5 ms / 1 %. Delay and volume stay editable while playing.
- **Responsive:** rows drop the controls under the name when the list is narrow; all rows switch together (the longest name decides).
  Resize grip in the bottom-right corner, minimum 680×480, tagline hides below 820 px.
- **Light / Dark / System** selector in the header (saved as `theme`; System follows Windows, re-checked every 2 s). Switching rebuilds the window
  live without touching the audio. New `LINK` token for orange text; both palettes ≥ 4.5:1 (lowest 4.67 light, 4.89 dark). Title bar follows the mode.
- Tests: backend 28/28 still pass; screenshots light/dark at 980×700 and 700×500.

## Phase 12 — Messages that don't pile up (Amon's report, 2026-11-06)
- ⚠ Clicking Calibrate/Start repeatedly stacked identical messages that never went away.
- Fix (UX practice: prevent the error, then one message at a time, then let it go by itself):
  - Start is greyed out when nothing is ticked, Calibrate when fewer than two; the status line says why.
  - One message slot: a new message replaces the old one; the same message again only restarts its timer.
    Several problems at once show the most important one (blocking first); the rest go to the log.
  - Plain messages vanish after 5–9 s + 50 ms per character (max 15 s). Hovering pauses the countdown. × closes at once.
  - Questions with buttons (Calibrate instructions, "speakers will play out loud") stay until answered.
  - Problems about the chosen source stay under the source box while they are true (they describe the current choice).
- Test 9/9: button states for 0/1/2 ticked, reason text, 5× Calibrate + 5× Start → 1 message, auto-dismiss, question stays, hover pauses.

## Phase 13 — Design critique, animated scenery, Flet prototype (2026-11-06) ◐
### /impeccable critique of the main window: **27/40 (Acceptable)**
Snapshot: `.impeccable/critique/2026-11-06T13-17-55Z__duosound-ui-main-window-py.md` (method: design review only; the detector reads web markup only).
Priority issues and status:
1. [P1] Empty state said "Ready. Press Start" with Start lit. **☑ Fixed**: `_build_rows` now calls `_update_actions()` on the no-outputs path.
2. [P1] Ticked checkboxes draw ✕ (reads as "excluded"). ☐ Open: draw a real check mark.
3. [P2] Sound source takes ~1/3 of the window; the headphone list is squeezed at small sizes. ☐ Open: collapse it to one line "Copying sound from … · Change".
   The theme switch moves into Options and the meter is renamed "Sound from source".
4. [P2] 6 controls per headphone row. ☐ Open (Amon chose): Volume visible; Delay behind an "Adjust sync" link per row.
5. [P2] Long names clipped before the layout is measured. ☐ Open: re-decide after idle, ellipsize + tooltip.
Minor (Amon chose "all 5 + minor"): plain source hints, status line must not cut mid-word, "N headphones playing in sync" for ~4 s after Start.
Order chosen by Amon: harden → polish → layout → distill → adapt → clarify → polish.
A Sonnet agent started items 2–5 on the tkinter files and was **stopped** when Amon asked about Flet. The partial edits compile and `test_banners` still passes 9/9.
Whatever it changed is in `duosound/ui/{theme,main_window,widgets}.py` (not reviewed yet; check with screenshots before building on it).

### Animated scenery (Amon's request, inspired by a poster-style "moonlit coast" image)
- New `duosound/ui/scenery.py` (tkinter Canvas), **not wired into the window yet**:
  - dark = moonlit night (speckled moon + glow, stars, lit house windows); light = sunny day (sun with rays, clouds);
  - both have a lake with a shimmering light path, Italian cypress + round two-tone trees, and a grass meadow;
  - trees and grass sway in a gusting wind; theme switch = 8-step crossfade;
  - static parts are painted once with PIL; only trees, grass, clouds, stars and glints move;
  - 15 fps; pauses when minimised; off when Windows "Show animations" is off.
- Measured **~13 % of one CPU core** (the first version used 28 % before optimising).
- Demo: `tools/demos/scenery_demo.py` (it shows mock panels on top with a Day/Night button).
- Limitation found: **tkinter panels can't be transparent**, so the scene only shows around solid panels (no glass).

### Flet question (Amon: "can Flet do transparency / glassmorphism?")
- Yes: Flet (Python on Flutter) supports background blur, semi-transparent panels, GPU animation and Lottie.
  Current version **flet 1.1.0** (its API differs from the 0.2x docs).
- Cost: rewrite only `duosound/ui/` (the backend stays behind `controller.py`). Open questions: .exe size, pystray tray icon alongside Flet,
  `flet build windows` needs the Flutter SDK.
- **Amon chose: build a Flet prototype first, compare with the tkinter demo, then decide.** The tkinter review fixes are paused until then.
- The prototype is being built by an agent in an isolated venv (session scratchpad `flet_proto/`; nothing installed globally, project untouched).
- ☐ Next: show both demos side by side, then Amon decides: (a) Flet rewrite of `duosound/ui/` with glass + scenery + critique fixes,
  or (b) stay tkinter: finish the critique fixes and wire `scenery.py` in behind solid panels.

### Folder clean-up (2026-11-06)
- Deleted the `__pycache__` folders and 7 leftover `duosound_test_*` temp folders. Kept the logs (they are the evidence for the test results above).
- Test scripts moved from the session scratchpad into **`tests/`** (`test_backend.py` 28/28, `test_ui_messages.py` 9/9; both pass from there).
  The backend test now deletes its temp settings folder. The scenery demo lives in `tools/demos/`.

### Flet prototype result (2026-11-06)
- Built with flet 1.1.0 in an isolated venv. Saved as `tools/demos/flet_glass_demo.py`, with screenshots `flet_glass_dark.png` / `flet_glass_light.png`.
- **Frosted glass works**: the panels blur the moving scenery behind them in both themes, and the light/dark switch crossfades.
- Measured against the tkinter demo:

| | tkinter demo | Flet prototype |
|---|---|---|
| CPU while animating | ~13 % of one core | **~24 %** (8.6 % Python + 15.8 % Flutter client) |
| Memory | ~80 MB | **~410 MB** (77 MB Python + 331 MB client) |
| Packaged size (PyInstaller) | 35 MB single .exe | **~115 MB** folder (`flet pack`, onedir) |
| Start-up | ~2.5 s | ~2.7 s |
| Glass / see-through panels | no | yes |

- Flet 1.1 note: TextField border_* properties are deprecated (use `border=OutlineInputBorder(...)`).
- ☐ Amon to decide: Flet (glass look, heavier) or tkinter (lighter, solid panels).
- **Decision (Amon, 2026-11-06): Flet, but calmer.** Use the glass look; the scenery animates only while idle (~12 fps) and freezes while a movie is
  playing, when the window is minimised or unfocused, and when Windows animations are off.
- Plan:
  - build the new window in `duosound/ui_flet/`, keeping the tkinter `duosound/ui/` as a fallback until parity is verified, then remove it;
  - all critique fixes go into the new design; `main.py` tries Flet first;
  - flet==1.1.0 becomes a dependency.
- Done.

### Phase 14: Flet window built and verified (2026-11-06)
- `duosound/ui_flet/` (app, widgets, pages, scenery, tokens, words, icon, fonts: Oswald + Atkinson Hyperlegible, OFL). `main.py` uses Flet, with tkinter as the fallback.
- Verified by me: `tests/test_backend.py` 28/28, `tests/test_flet_smoke.py` 14/14 (fake controller drives the real window), settings.json backed up and restored.
  Screenshots look right in dark/light at 1000x700 and 700x500, plus Help, Donate, Options, sync, banner, confirm, empty and running.
- New .exe: one file, 87 MB (vs 35 MB tkinter). Starts in about 7 s (about 12 s on the very first run while it unpacks the Flet client).
  Built to the scratchpad. `dist\DuoSound.exe` is still the old tkinter build until Amon OKs replacing it.
- CPU: idle with animated scenery 22-40 % of one core; while a movie plays (scene frozen) about 2.7 %; frozen idle about 1 %.
- Packaging: `flet pack` crashes in 1.1.0, so the spec bundles the Flet client zip directly (`packaging/fetch_flet_client.py`, `rthook_flet.py`). `flet-cli` must not be installed (its hook doubles the exe).
- Known gaps:
  - at 700x500 only about 1.5 headphone rows are visible (the list scrolls);
  - window position is not restored;
  - tray menu, F1/F5/Space, the Copy buttons and saving the window size are written but not tested end to end;
  - one Donate screenshot showed Flet's logo in the title bar.
- Next: a real 2-headset run in the new window. Then remove the tkinter `duosound/ui/` (after Amon OKs).

### Phase 15: Dual-build pipeline + 20ms saver mode (2026-11-06)

**Decisions**
- Ship two executables via one Inno Setup installer: `DuoSound.exe` (Full/Flet glass UI) and `DuoSound_Lite.exe` (Classic/tkinter). Both are installed; shortcuts are created only for the user's chosen component. Users can switch by running the other exe from the install folder.
- Portable ZIPs are also available (`build_exe.bat portable`).
- Both exes share the same named mutex (`"Local\DuoSound.SingleInstance"` exported from `duosound/__init__.py`) — only one can run at a time.

**20ms block-size mode ("Battery / Old-PC saver")**
- Added `block_size_ms` setting (10 or 20ms). Default is 10ms (unchanged behaviour).
- At 20ms: player buffer 160ms, capture buffer 200ms, ring 4s — all 2× the 10ms values.
- Drift controller thresholds remain in absolute ms/frames and need no change.
- CPU overhead halved on the audio callback loop.

**Portable build**
- `build_exe.bat portable` builds both exes as `--onedir`, then uses `PowerShell Compress-Archive` to zip them. No extra dependencies.

**Files added / changed**
- `duosound/__init__.py`: added `MUTEX_NAME`, `BLOCK_SIZES`, bumped version to 0.1.1.
- `duosound/settings.py`: added `block_size_ms` with strict validation.
- `duosound/engine.py`: `Engine` and `OutputWorker` now accept block/buffer sizes; scaled at 20ms.
- `duosound/controller.py`: passes `block_size_ms` to `Engine`; exposes `block_size_ms` property.
- `main.py`: imports `MUTEX_NAME` from `duosound` (removed local constant).
- `main_lite.py`: new tkinter-only entry point, shared mutex.
- `packaging/duosound_flet.spec`, `packaging/duosound_lite.spec`: two separate build specs.
- `packaging/duosound_installer.iss`: Inno Setup with Full/Lite component selector.
- `build_exe.bat`: rewritten with `installer` and `portable` modes.
- `tests/test_block_size.py`: 10/10 pass.
- `tests/test_single_instance.py`: 7/7 pass.
- `tests/MANUAL_CHECKLIST.md`: manual test checklist for release.
- `.gitignore`: created.
- `duosound/help_text.py`: added `full_vs_lite` topic.
- `README.md`: added Installation section with installer/portable/switching guidance.

### Phase 16: Audio crackling fix during UI interaction (2026-11-06)

**Problem**
Clicking buttons in the Flet (Full) window caused audible crackling and brief sound pauses in both Bluetooth headphones during audio playback. The tkinter (Lite) window had no crackling — confirming it was Flet-specific.

**Root cause (three layers)**
1. Audio threads running at normal priority — UI events could preempt them past the WASAPI device buffer watermark.
2. Python GIL held for up to 5 ms per bytecode quantum — during heavy UI operations (theme change, Help page swap, PIL scene rebuild) the audio thread could be locked out for 30–100 ms.
3. Flutter backdrop blur (`blur=16`) rendering on the GPU at 60 fps even with the scenery frozen — GPU DPC (Deferred Procedure Call) latency spikes interrupted the Windows audio engine timer, causing device buffer underruns regardless of Python thread scheduling.

The third cause was confirmed by testing: tkinter (no backdrop blur) had zero crackling; Flet (blur on 5 glass panels) crackled on every button click.

**Fixes applied**
- `duosound/engine.py`: added `_elevate_thread_priority()` — called at thread start in `OutputWorker._run()` and `Engine._capture()`. Sets `THREAD_PRIORITY_HIGHEST` (value 2) via `kernel32.SetThreadPriority`, matching the priority Windows' own audio mixer uses.
- `main.py` + `main_lite.py`: `sys.setswitchinterval(0.001)` — reduces Python's GIL yield check from 5 ms to 1 ms. Audio threads (HIGHEST priority) win the GIL contest every 1 ms max, so even a 100 ms PIL scene rebuild can't lock them out.
- `duosound/ui_flet/app.py`: `_set_glass_blur(playing: bool)` — sets `blur=0` on all 5 static glass panels (`src_panel`, `opt_panel`, `list_card`, `log_panel`, `bottom`) when Start is pressed, restores `blur=16` on Stop. Called alongside `scenery.freeze("running", ...)` in `_do_start`, `_after_start` (failure path), and `stop`. Eliminates GPU DPC spikes entirely during playback; glass appearance (tint, border, shadow) is unchanged.

**Test result**
Theme toggle, Help button, Options, Log — all silent during playback. `tests/test_backend.py` 28/28.

---

## Phase 17 — Release engineering and first public GitHub push (2026-11-06) ☑

Everything between "the code works" and "a stranger can download and run it". The headline is that
the documented build was **completely broken** and nobody had noticed, because the last successful
build predated a PyInstaller upgrade.

### Tkinter redesign: tried and rolled back

A Flet-matching restyle of the tkinter UI was built (night-ink palette, Canvas rounded-corner `Card`
widget, three card sections) and then reverted at Amon's request — it did not look right in practice.
`theme.py`, `widgets.py` and `main_window.py` are back to the original warm-brown design. No git
history existed yet, so the rollback was a manual restore of the exact prior values; 28/28 tests
confirmed afterwards. The audio-crackling fixes from Phase 16 were deliberately **not** reverted.

Finding worth keeping: a static Canvas card costs nothing in CPU or GPU and would not reintroduce
crackling. The rollback was a taste decision, not a performance one.

### Build pipeline was broken — five bugs

| File | Bug | Effect |
|---|---|---|
| `build_exe.bat` | `--onefile --windowed` passed alongside a `.spec` | **PyInstaller 6.x hard error.** No exe could be built at all. |
| `build_exe.bat` | `--onedir` in the portable path | Same error; the specs have no `COLLECT` block, so one-dir was never possible. |
| `build_exe.bat` | Inno Setup looked for v6 in Program Files only | Installed copy was **v7, per-user** in `%LOCALAPPDATA%`. Never found. |
| `duosound_installer.iss` | Two `[Types]` entries with `Flags: iscustom` | Inno Setup 6 tolerated it; **v7 refuses to compile**. |
| `README.md` | "double-click `build_exe.bat`" | It needs an `installer` or `portable` argument, or it just prints usage. |

The onefile/windowed settings were already correct inside the `.spec` files (`a.binaries` inline,
`console=False`), so the CLI flags were redundant even before they became fatal.

### Installer: per-user, and it now has a wizard

- `PrivilegesRequired=lowest` — Setup never asks for administrator rights, installing to
  `%LOCALAPPDATA%\Programs\DuoSound`. Amon's call, and the right one for a product whose first
  priority is zero setup: a locked-down work laptop can still install it.
- `{commondesktop}` → `{autodesktop}` — the all-users desktop needs admin, so it had to follow.
- **`DisableWelcomePage=no`.** This was the "there is no setup wizard" complaint: Inno Setup 6+
  hides the Welcome page *by default*, and with `DisableProgramGroupPage=yes` already set, Setup
  jumped almost straight to installing.
- `packaging/make_icon.py` now also generates `wizard_banner.bmp` and `wizard_small.bmp` — warm
  gradient, app icon, and **Created by Amon Lal**. Regenerated on every build, so they never drift.
- `[Messages]` block puts the author credit on the Welcome and Finished pages, which are shared by
  both editions, so it shows whichever one the user picks.

Verified end to end, scripted: silent install with no admin → exit 0 → installed exe launches →
silent uninstall → **zero leftovers**.

### Terminal install: Lite and Full are now actually separable

`requirements.txt` listed `flet==1.1.0` as a hard dependency, but Lite never imports Flet. A
Lite-only user was downloading ~50 MB they would never use, and there was no way to choose.

- `requirements.txt` — core only. Enough for Classic Graphics.
- `requirements-full.txt` — `-r requirements.txt` plus Flet.

The choice *is* which file you install. `main.py` still falls back to tkinter on its own if Flet is
absent, so nothing hard-fails.

### Versioning: one source of truth

`duosound/__init__.py` is authoritative. `packaging/version_info.txt` was already generated from it
by `make_icon.py`; only `duosound_installer.iss` hardcoded the number.

**`tools/bump_version.py`** keeps all three in step:

```
python tools/bump_version.py patch|minor|major
python tools/bump_version.py --set 1.2.3
python tools/bump_version.py --check        # verify only
python tools/bump_version.py patch --dry-run
```

Atomic writes (`.tmp` → `os.replace`, house rule), refuses a non-increasing bump, self-verifies
after writing, and `--check` fails loudly on drift. Follows Amon's `amon_welcome` convention with
`--yes` / `--no-art` / `--user`, and the module is **embedded** so it works for anyone cloning from
GitHub without Amon's local copy. Tested with a real 0.1.1 → 0.1.2 bump and `--set` restore.

### Git organization

- **`.gitattributes`** — `* text=auto`, with `.bat`/`.cmd`/`.ps1`/`.iss` pinned to **CRLF**.
  A blanket `eol=lf` would have corrupted the `^` line continuations in `build_exe.bat`.
- **`CONTRIBUTING.md`** — Conventional Commits, feature branches, the architectural rules that must
  not break, and the audio-thread discipline from Phase 16.
- **`RELEASE_CHECKLIST.md`** — nine steps from clean tree to published GitHub Release.
- **`.gitignore`** — added `.pytest_cache/`, `settings.json`, `restore.json`, the wizard BMPs.

### First public release

**https://github.com/AmonHooriLal/duosound** — public, `main`, tag `v0.1.1`, 67 files / 2.0 MB.

Excluded as intended: `dist/` (215 MB), `packaging/flet_client/` (42 MB), logs, caches, runtime state.
A secret scan before committing found only false positives (design-system colour "tokens").

Two things caught before the push: the username in `README.md`, `CONTRIBUTING.md` and
`duosound_installer.iss` was `amonlal` but the real account is **`AmonHooriLal`**, so every published
link would have 404'd; and `.pytest_cache/` was not ignored.

The commit was later amended to drop the `Co-Authored-By` trailer and force-pushed
(`3b07e15` → `2944494`), with tag `v0.1.1` re-pointed to match.

### Still open

- **Amon has not yet manually run the new `DuoSound_Setup.exe`** to confirm the wizard.
- `dist/DuoSound_Setup.exe` predates the username fix, so its publisher URL still says `amonlal`.
  **Rebuild before attaching it to a GitHub Release.**
- No binaries attached to the release yet — `dist/` is gitignored by design; see
  `RELEASE_CHECKLIST.md` step 8.
- Portable ZIPs not built since the portable path was fixed.
- The donate QR is now public and permanent in git history (Amon's informed choice).
- Build is unsigned: Windows still shows "Windows protected your PC".
