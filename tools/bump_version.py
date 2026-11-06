"""DuoSound Version Bump
=====================
Raises DuoSound's version number in every file that carries it, so the Python package, the .exe
file properties and the Windows installer can never disagree about which release this is.

`duosound/__init__.py` is the single source of truth. This script reads it, applies a SemVer
bump, and writes the new number back there plus into `packaging/version_info.txt` and
`packaging/duosound_installer.iss`.

Run:
    python tools/bump_version.py patch      0.1.1 -> 0.1.2   (bug fixes)
    python tools/bump_version.py minor      0.1.1 -> 0.2.0   (new features, still compatible)
    python tools/bump_version.py major      0.1.1 -> 1.0.0   (breaking changes)
    python tools/bump_version.py --set 1.2.3                 (exact version)
    python tools/bump_version.py --check                     (verify only, changes nothing)
    python tools/bump_version.py patch --dry-run             (show what would change)
"""
from __future__ import annotations

# >>> amon_welcome v1.4.0 >>>
# Embedded copy of the shared welcome module - do not edit here.
# Update it with:  python -m amon_welcome --embed <this file>
import base64 as _b64, sys as _sys, types as _types, zlib as _zlib
_aw = _types.ModuleType("amon_welcome")
exec(compile(_zlib.decompress(_b64.b64decode(
    "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"
    "ArvQaEQ="
    )).decode("utf-8"), "<amon_welcome>", "exec"), _aw.__dict__)
_sys.modules["amon_welcome"] = _aw
del _b64, _types, _zlib, _aw
# <<< amon_welcome <<<

import argparse
import os
import re
import sys
from pathlib import Path

from amon_welcome import fail, info, step, summary_box, warn, welcome

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "duosound" / "__init__.py"
VERSION_INFO = ROOT / "packaging" / "version_info.txt"
INSTALLER = ROOT / "packaging" / "duosound_installer.iss"

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# One entry per file that carries the version. Each pattern has exactly one capture group:
# the version text to replace. `build` turns a (major, minor, patch) tuple into that text.
TARGETS = [
    (INIT, [(re.compile(r'__version__\s*=\s*"([^"]+)"'), lambda v: f"{v[0]}.{v[1]}.{v[2]}")]),
    (INSTALLER, [(re.compile(r'#define\s+MyAppVersion\s+"([^"]+)"'), lambda v: f"{v[0]}.{v[1]}.{v[2]}")]),
    (VERSION_INFO, [
        (re.compile(r"filevers=\(([^)]*)\)"), lambda v: f"{v[0]}, {v[1]}, {v[2]}, 0"),
        (re.compile(r"prodvers=\(([^)]*)\)"), lambda v: f"{v[0]}, {v[1]}, {v[2]}, 0"),
        (re.compile(r"StringStruct\('FileVersion',\s*'([^']+)'\)"), lambda v: f"{v[0]}.{v[1]}.{v[2]}"),
        (re.compile(r"StringStruct\('ProductVersion',\s*'([^']+)'\)"), lambda v: f"{v[0]}.{v[1]}.{v[2]}"),
    ]),
]


def parse(text: str) -> tuple[int, int, int]:
    m = SEMVER.match(text.strip())
    if not m:
        raise ValueError(f"not a SemVer MAJOR.MINOR.PATCH version: {text!r}")
    return int(m[1]), int(m[2]), int(m[3])


def current() -> tuple[int, int, int]:
    """The version in duosound/__init__.py - the single source of truth."""
    m = re.search(r'__version__\s*=\s*"([^"]+)"', INIT.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"could not find __version__ in {INIT}")
    return parse(m[1])


def bump(v: tuple[int, int, int], part: str) -> tuple[int, int, int]:
    major, minor, patch = v
    if part == "major":
        return major + 1, 0, 0
    if part == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def found_versions() -> dict[Path, list[str]]:
    """What each file currently says, so --check can prove they agree."""
    out: dict[Path, list[str]] = {}
    for path, rules in TARGETS:
        if not path.exists():
            out[path] = []
            continue
        text = path.read_text(encoding="utf-8")
        out[path] = [m[1].strip() for pattern, _ in rules for m in [pattern.search(text)] if m]
    return out


def normalise(raw: str) -> str:
    """'0, 1, 1, 0' and '0.1.1' both mean 0.1.1, so --check can compare them."""
    parts = [p.strip() for p in re.split(r"[.,]", raw) if p.strip()]
    return ".".join(parts[:3])


def write_version(v: tuple[int, int, int], dry_run: bool) -> list[Path]:
    """Replace the version in every target file. Atomic: write .tmp, then os.replace."""
    changed = []
    for path, rules in TARGETS:
        if not path.exists():
            warn(f"skipped (missing): {path.relative_to(ROOT)}")
            continue
        text = original = path.read_text(encoding="utf-8")
        for pattern, build in rules:
            replacement = build(v)
            text = pattern.sub(lambda m, r=replacement: m.group(0).replace(m.group(1), r), text)
        if text == original:
            continue
        if not dry_run:
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
        changed.append(path)
    return changed


def do_check() -> int:
    """Report whether every file agrees with duosound/__init__.py. Exit 1 on drift."""
    src = ".".join(str(n) for n in current())
    info(f"source of truth (duosound/__init__.py): {src}")
    drift = []
    for path, versions in found_versions().items():
        rel = path.relative_to(ROOT)
        if not versions:
            warn(f"{rel}: no version found")
            drift.append(rel)
            continue
        odd = sorted({normalise(x) for x in versions} - {src})
        if odd:
            fail(f"{rel}: {', '.join(odd)}  (expected {src})")
            drift.append(rel)
        else:
            info(f"{rel}: {src}")
    if drift:
        fail(f"{len(drift)} file(s) out of sync - run: python tools/bump_version.py --set {src}")
        return 1
    info("all files agree")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.strip().splitlines()[0],
        epilog="duosound/__init__.py is the source of truth; the other files are kept in step with it.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("part", nargs="?", choices=("patch", "minor", "major"),
                    help="which part of MAJOR.MINOR.PATCH to raise")
    ap.add_argument("--set", dest="exact", metavar="X.Y.Z", help="set this exact version instead of bumping")
    ap.add_argument("--check", action="store_true", help="verify every file agrees; change nothing")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    ap.add_argument("--no-art", action="store_true", help="skip the welcome picture")
    ap.add_argument("--user", default="Amon")
    a = ap.parse_args()

    if not (a.check or a.part or a.exact):
        ap.print_help()
        return 2

    if not welcome(user=a.user, confirm=not (a.yes or a.check), art=not a.no_art):
        return 1

    if a.check:
        return do_check()

    old = current()
    try:
        new = parse(a.exact) if a.exact else bump(old, a.part)
    except ValueError as exc:
        fail(str(exc))
        return 2

    old_s, new_s = ".".join(map(str, old)), ".".join(map(str, new))
    if new <= old and not a.exact:
        fail(f"{new_s} is not newer than {old_s}")
        return 2
    if new == old:
        warn(f"already at {new_s}; nothing to do")
        return 0

    step(1, 2, f"{old_s}  ->  {new_s}")
    changed = write_version(new, a.dry_run)
    for p in changed:
        info(("would update " if a.dry_run else "updated ") + str(p.relative_to(ROOT)))

    step(2, 2, "verifying every file agrees")
    if a.dry_run:
        warn("dry run: nothing was written")
        return 0
    if do_check() != 0:
        return 1

    summary_box(
        f"DuoSound is now v{new_s}",
        facts=[("Was      ", old_s),
               ("Now      ", new_s),
               ("Commit   ", f'git commit -am "chore: release v{new_s}"'),
               ("Tag      ", f"git tag v{new_s}"),
               ("Push     ", "git push origin main --tags"),
               ("Then     ", "follow RELEASE_CHECKLIST.md to build and publish")],
        folder=ROOT,
        files=[p.relative_to(ROOT) for p in changed],
        files_title="Updated:")
    return 0


if __name__ == "__main__":
    sys.exit(main())
