# Contributing to DuoSound

Notes for working on DuoSound — mostly for future me, but they apply to anyone sending a pull request.

---

## Getting set up

```bash
git clone https://github.com/AmonHooriLal/duosound.git
cd duosound

pip install -r requirements.txt        # Classic Graphics (tkinter) — enough to run and test
pip install -r requirements-full.txt   # adds Flet for the Full Graphics window
```

Run it:

```bash
python main_lite.py    # Classic Graphics
python main.py         # Full Graphics (falls back to tkinter if Flet is missing)
```

---

## The rules that must not break

These are architectural, not stylistic. Breaking one causes bugs that are hard to trace.

| Rule | Why |
|---|---|
| Nothing in `duosound/ui/` or `duosound/ui_flet/` may import `engine`, `volume`, `devices` or `calibrate` | The UI talks to the backend only through `AppController`. Direct imports let UI code block the audio thread. |
| All pycaw / COM calls stay on `volume._ComThread` | COM is apartment-threaded. Calling it from elsewhere deadlocks or corrupts state. |
| JSON writes are atomic — write `.tmp`, then `os.replace` | A half-written `settings.json` loses the user's whole configuration. |
| Both executables share `MUTEX_NAME` from `duosound/__init__.py` | Full and Lite must be mutually exclusive, or two engines fight over the same audio devices. |
| No hardcoded absolute paths | Use `os.environ.get("APPDATA")`. Hardcoded paths leak the developer's folder layout into a public release. |
| Tests never change Windows audio settings or press Start against real devices | A test run must not leave the machine muted. |

## Audio-thread discipline

DuoSound copies live audio while its own window is being used, so UI work can starve the audio
threads and cause audible crackling. Three defences are in place; don't undo them:

- `_elevate_thread_priority()` in `engine.py` — audio threads run at `THREAD_PRIORITY_HIGHEST`.
- `sys.setswitchinterval(0.001)` in `main.py` / `main_lite.py` — the GIL is released every 1 ms.
- Backdrop blur is switched off on the Flet glass panels while audio plays — GPU compositing
  caused DPC latency spikes that underran the WASAPI buffer.

If you add animation, timers or GPU effects, test by playing music, pressing **Start**, and then
clicking every button repeatedly. Any crackle or pause is a regression.

---

## Branches

Work on a branch, never directly on `main`.

```
feature/<what>     feature/audio-optimization
fix/<what>         fix/crackling-on-theme-switch
chore/<what>       chore/bump-version
docs/<what>        docs/release-checklist
```

Merge into `main` only when the tests pass.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/). The type prefix is what makes the
history readable a year later.

```
feat:     a new user-visible capability      feat: add 20ms block size saver mode
fix:      a bug fix                          fix: resolve audio crackling on button click
perf:     faster or lighter, same behaviour  perf: halve idle CPU in the scenery loop
refactor: restructure, no behaviour change   refactor: split requirements for Lite and Full
docs:     documentation only                 docs: add release checklist
test:     tests only                         test: cover single-instance mutex
build:    build system or packaging          build: fix PyInstaller 6.x spec flags
chore:    housekeeping                       chore: release v0.1.2
```

Write the subject in the imperative and keep it under ~72 characters. Put the reasoning in the
body — the *why* is what you'll want later, since the diff already shows the *what*.

---

## Before you push

```bash
python tests/test_backend.py       # 28 checks, must all pass
python tests/test_ui_messages.py
python tools/bump_version.py --check   # every file agrees on the version
```

For anything touching the UI or the audio path, also run the app and use it. Type checks and unit
tests verify correctness, not whether the feature actually works.

## Releasing

See [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md). Never bump the version by hand — run
`python tools/bump_version.py patch|minor|major`, which keeps all three version files in step.

---

## Where things live

| Path | What |
|---|---|
| `duosound/controller.py` | The only API the UI may call |
| `duosound/engine.py` | Capture, ring buffers, output threads, drift correction |
| `duosound/ui/` | Classic Graphics (tkinter). `theme.py` holds every colour, font and sentence. |
| `duosound/ui_flet/` | Full Graphics (Flet). `tokens.py` is its design system. |
| `packaging/` | PyInstaller specs, Inno Setup script, icon and wizard image generator |
| `tools/` | Developer utilities — version bump, device tester, demos |
| `tests/` | Backend tests plus `MANUAL_CHECKLIST.md` for the manual pass |

Background and decisions: [CONTEXT.md](CONTEXT.md) · [PRODUCT.md](PRODUCT.md) ·
[DESIGN.md](DESIGN.md) · [PROGRESS.md](PROGRESS.md)
