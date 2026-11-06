# DuoSound Release Checklist

Follow this top to bottom for every published version. Each step says what "done" looks like, so
a half-finished release is obvious rather than silent.

Replace `X.Y.Z` with the new version throughout.

---

## 1. Start clean

```bash
git status                    # nothing uncommitted you care about
git switch main
git pull
```

- [ ] Working tree clean, on `main`, up to date.

## 2. Tests pass

```bash
python tests/test_backend.py        # expect: 28/28 passed
python tests/test_ui_messages.py
python tools/bump_version.py --check
```

- [ ] Backend tests all pass.
- [ ] UI message tests pass.
- [ ] Version check reports **all files agree**.

> A failing test blocks the release. Fix it, don't skip it.

## 3. Bump the version

```bash
python tools/bump_version.py patch     # bug fixes only
python tools/bump_version.py minor     # new features, still compatible
python tools/bump_version.py major     # breaking changes
```

This updates `duosound/__init__.py`, `packaging/version_info.txt` and
`packaging/duosound_installer.iss` together. Never edit them by hand.

- [ ] New version printed and the three files agree.

## 4. Build

```bash
build_exe.bat installer     # dist\DuoSound.exe, DuoSound_Lite.exe, DuoSound_Setup.exe
build_exe.bat portable      # dist\DuoSound_Full_Portable.zip, DuoSound_Lite_Portable.zip
```

Needs PyInstaller, and [Inno Setup](https://jrsoftware.org/isdl.php) for the installer. The script
finds Inno Setup in Program Files or `%LOCALAPPDATA%\Programs` — no PATH edit required.

- [ ] All five artifacts present in `dist\`.
- [ ] Each one's Properties → Details shows the new version.

## 5. Test the real artifacts

Not the source — the built files a user will actually download.

- [ ] `DuoSound_Setup.exe` runs with **no UAC prompt** (it installs per-user).
- [ ] Wizard shows the welcome page, the banner, and **Created by Amon Lal**.
- [ ] Both editions offered; the chosen one gets its shortcut.
- [ ] Installed app launches and plays to two Bluetooth headsets.
- [ ] **Crackling check:** with music playing, click theme / Help / Options repeatedly. Silence.
- [ ] Single instance: starting the other edition focuses the running one.
- [ ] Uninstall removes everything; `%APPDATA%\DuoSound\settings.json` may remain by design.
- [ ] Portable ZIPs run from an unzipped folder, including off a USB stick.

Full pass: [tests/MANUAL_CHECKLIST.md](tests/MANUAL_CHECKLIST.md).

## 6. Update the written record

- [ ] `PROGRESS.md` — what changed this release.
- [ ] `README.md` — if behaviour, install steps or requirements moved.
- [ ] `CONTEXT.md` — if architecture changed.

## 7. Commit and tag

```bash
git add -A
git commit -m "chore: release vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

- [ ] Commit pushed, tag visible on GitHub.

> `dist/` is gitignored — the binaries are attached to the Release, never committed.

## 8. Publish the GitHub Release

1. GitHub → **Releases** → **Draft a new release**.
2. Choose tag `vX.Y.Z`, title `DuoSound vX.Y.Z`.
3. Write notes grouped by Conventional-Commit type — Added / Fixed / Changed.
4. Attach from `dist\`:
   - `DuoSound_Setup.exe` (recommended download)
   - `DuoSound_Full_Portable.zip`
   - `DuoSound_Lite_Portable.zip`
5. Publish.

- [ ] Release published with all three files attached.
- [ ] Downloaded `DuoSound_Setup.exe` from GitHub and confirmed it installs.

## 9. After publishing

- [ ] Install the published build on a second PC if one is available.
- [ ] Note anything deferred as the first item for the next version.

---

## If something is wrong after publishing

Don't delete the tag if anyone may already have it. Fix forward:

```bash
python tools/bump_version.py patch     # X.Y.Z+1
```

Then rerun this checklist and mark the bad release as superseded in its GitHub notes.

---

## Not done yet

- **Code signing.** The build is unsigned, so Windows shows *"Windows protected your PC"* and
  users must click **More info → Run anyway**. A certificate removes that warning.
