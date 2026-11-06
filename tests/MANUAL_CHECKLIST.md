# DuoSound Manual Test Checklist

Run these by hand before tagging a release. Record your findings in the table below each item.

---

## 1. Cold Launch Time (Full vs Lite)

| Exe | Machine | First launch | Subsequent launch |
|---|---|---|---|
| DuoSound.exe (Full) | | | |
| DuoSound_Lite.exe | | | |

- First launch of DuoSound.exe unpacks the Flet client (~12 s expected).
- Subsequent launches should be ~7 s (Full) and ~3 s (Lite).

---

## 2. Idle CPU / RAM

Measure with Task Manager or `tools/profile_resources.py` after the window has settled.

| Exe | Scenery animating | CPU (1 core %) | RAM (MB) |
|---|---|---|---|
| DuoSound.exe (Full) | Yes | | |
| DuoSound_Lite.exe | No scenery | | |

Target: Full ≤ 40 % one core idle; Lite ≤ 5 %.

---

## 3. Active CPU / RAM (2 Bluetooth headsets, movie playing)

Scenery should freeze while playing. Measure after 30 s of playback.

| Exe | CPU (1 core %) | RAM (MB) |
|---|---|---|
| DuoSound.exe (Full) | | |
| DuoSound_Lite.exe | | |

Target: ≤ 5 % one core while playing.

---

## 4. Mid-Session Block Size Switch (10ms → 20ms)

1. Start DuoSound (either exe).
2. With two headsets connected, press Start, start a movie.
3. Open Options, switch block size to 20ms (Battery mode).
4. Press Stop, then Start again.

| Step | Result |
|---|---|
| No audio glitches during switch | Pass / Fail |
| Log shows "Engine block_size=20ms  player_buf=160ms  capture_buf=200ms" | Pass / Fail |
| Both headsets still play in sync | Pass / Fail |

---

## 5. Inno Setup Installer — Component Selection

Build with `build_exe.bat installer`, then run `dist\DuoSound_Setup.exe` on a clean Windows VM.

| Check | Result |
|---|---|
| Welcome page appears, with the banner and "Created by Amon Lal" | Pass / Fail |
| **No UAC / administrator prompt at any point** (install is per-user) | Pass / Fail |
| Installs to `%LOCALAPPDATA%\Programs\DuoSound` | Pass / Fail |
| Installer shows "Full Graphics" and "Classic Graphics" radio buttons | Pass / Fail |
| Selecting Full → creates DuoSound shortcut (not Lite) | Pass / Fail |
| Selecting Lite → creates DuoSound (Lite) shortcut | Pass / Fail |
| Both DuoSound.exe and DuoSound_Lite.exe exist in install folder | Pass / Fail |
| "Full Graphics" and "Classic Graphics" shortcuts both present in Start Menu | Pass / Fail |
| **Tick "Launch DuoSound now" on the last page → the app actually opens** | Pass / Fail |

> **The last row must be done by hand, every release.** It cannot be automated: the `[Run]` entry
> carries `postinstall` (it is a checkbox on the Finished page) and `skipifsilent`, so a silent
> install never executes it. v0.1.1 shipped with that step broken — `GetMainExe` returned a full
> path while `[Run]` prepended the directory again, producing
> `...\DuoSound\...\DuoSound\DuoSound.exe` and "CreateProcess failed; code 2". Scripted testing
> reported a clean install because it never reached the one line that was wrong.

---

## 6. Uninstall (Clean Removal)

After the installer test above:

| Check | Result |
|---|---|
| Uninstall via Control Panel or Start Menu → Uninstall | Pass / Fail |
| Install folder removed | Pass / Fail |
| Start Menu shortcuts removed | Pass / Fail |
| Desktop shortcut removed | Pass / Fail |
| Settings file in %APPDATA%\DuoSound\ still exists (user data not wiped) | Pass / Fail |

---

## 7. Single Instance — Full and Lite Are Mutually Exclusive

1. Launch `DuoSound.exe`.
2. While it is running, double-click `DuoSound_Lite.exe`.

| Check | Result |
|---|---|
| Lite does NOT start a second engine | Pass / Fail |
| The existing DuoSound window is brought to the front | Pass / Fail |

Repeat in reverse (Lite running, then Full launched).

---

## 8. Portable Zip from USB / HDD

Build with `build_exe.bat portable`. Copy `dist\DuoSound_Lite_Portable.zip` to a USB stick.
Run DuoSound_Lite.exe from the extracted folder on a machine with an HDD and no Python.

| Check | Result |
|---|---|
| DuoSound_Lite.exe starts | Pass / Fail |
| Settings saved to %APPDATA%\DuoSound\ (not inside the USB folder) | Pass / Fail |
| Launch time ≤ 5 s on HDD | Pass / Fail |

---

## 9. No Crackling While Using the Window (regression test for Phase 16)

DuoSound copies live audio while its own window is in use, so UI work can starve the audio threads.
Three defences exist (thread priority, 1 ms GIL interval, blur off during playback) and all three
are invisible until they break. **Test both editions** — the blur fix only applies to Full.

Start with two Bluetooth headsets connected and a movie playing, then press **Start**.
Wear one earbud and click each control several times in a row.

| Check | Full | Lite |
|---|---|---|
| Theme switch (Light / Dark / System) — the worst case | Pass / Fail | Pass / Fail |
| Help button, and Back from Help | Pass / Fail | Pass / Fail |
| Options open / close | Pass / Fail | Pass / Fail |
| Log open / close | Pass / Fail | Pass / Fail |
| Unmute / mute speakers | Pass / Fail | Pass / Fail |
| Resizing and dragging the window | Pass / Fail | Pass / Fail |

Any crackle, pop or momentary pause is a **failure**, not a quirk of the headset. Confirm against
the log afterwards: `underruns`, `drop` and `late` must all stay at 0 in the FINAL STATS line.

---

## Sign-off

| Reviewer | Date | Version | Notes |
|---|---|---|---|
| | | 0.1.2 | |
