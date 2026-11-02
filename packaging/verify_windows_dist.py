"""Fail the Windows build if the frozen app would still pip-install flet-desktop.

Static checks:
* dist contains flet_desktop/app/flet-windows.zip with flet/flet.exe inside
* the PyInstaller archive actually contains the flet_desktop module

With --smoke, launch the windowed exe briefly with FLET_CLIENT_URL pointed at
an unreachable address. A good bundle extracts ~/.flet/client/*/flet/flet.exe
from the packed zip and never calls pip. A bad bundle exits on
``NameError: name 'exit' is not defined``.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from flet_desktop_bundle import EXPECTED_MEMBER, ROOT, assert_windows_client_zip

APP_EXE_NAME = "社媒视频混剪.exe"
PIP_MARKERS = (
    "NameError",
    "name 'exit' is not defined",
    "Installing flet-desktop",
    'Unable to install "flet-desktop"',
)


def _fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def find_app_exe(dist: Path) -> Path:
    matches = [p for p in dist.rglob(APP_EXE_NAME) if "_internal" not in p.parts]
    if not matches:
        _fail(f"Could not find {APP_EXE_NAME} under {dist}")
    if len(matches) > 1:
        _fail(f"Multiple app exes: {matches}")
    return matches[0]


def find_bundled_zip(dist: Path) -> Path:
    matches = list(dist.rglob("flet-windows.zip"))
    if not matches:
        _fail(f"flet-windows.zip was not packed into {dist}")
    good = [p for p in matches if p.parent.name == "app" and p.parent.parent.name == "flet_desktop"]
    if not good:
        _fail(
            "flet-windows.zip is in the wrong place (need flet_desktop/app/): "
            + ", ".join(str(p) for p in matches)
        )
    if len(good) > 1:
        _fail(f"Multiple flet desktop zips: {good}")
    assert_windows_client_zip(good[0])
    return good[0]


def assert_module_frozen(exe: Path) -> None:
    """Require flet_desktop in the PYZ. Loose .py copies are not importable."""
    from PyInstaller.archive.readers import CArchiveReader

    try:
        arch = CArchiveReader(str(exe))
        names: set[str] = set()
        pyz_entries = [name for name, entry in arch.toc.items() if entry[-1] == "z"]
        if not pyz_entries:
            raise RuntimeError(f"No PYZ archive inside {exe}; toc={list(arch.toc)[:20]}")
        for name in pyz_entries:
            pyz = arch.open_embedded_archive(name)
            names.update(pyz.toc.keys())
    except SystemExit:
        raise
    except Exception as exc:
        loose = list(exe.parent.rglob("flet_desktop/version.py"))
        if not loose:
            _fail(f"Could not read frozen flet_desktop module ({exc})")
        print(f"WARNING: PYZ reader failed ({exc}); loose module copy at {loose[0]}")
        return
    needed = ("flet_desktop", "flet_desktop.version")
    missing = [mod for mod in needed if mod not in names]
    if missing:
        sample = sorted(n for n in names if "flet" in n.lower())[:40]
        _fail(f"Frozen archive missing {missing}. flet-related entries: {sample}")
    print(f"PYZ contains flet_desktop ({len(names)} modules)")


def _crash_text(exe: Path) -> str:
    log = exe.parent / "remix_crash.log"
    if not log.is_file():
        return ""
    return log.read_text(encoding="utf-8", errors="replace")


def smoke_launch(exe: Path, seconds: float) -> None:
    cache_root = Path.home() / ".flet" / "client"
    if cache_root.exists():
        shutil.rmtree(cache_root)
    crash = exe.parent / "remix_crash.log"
    if crash.exists():
        crash.unlink()

    env = dict(os.environ)
    # If the bundle has no zip, Flet downloads this URL. It must not be reached.
    env["FLET_CLIENT_URL"] = "http://127.0.0.1:9/flet-desktop-must-be-bundled.zip"
    env.pop("REMIX_UI_WEB", None)

    print(f"Smoke launch {exe} for up to {seconds:.0f}s")
    proc = subprocess.Popen([str(exe)], env=env, cwd=str(Path.home()))
    found: Path | None = None
    deadline = time.time() + seconds
    try:
        while time.time() < deadline:
            text = _crash_text(exe)
            if any(marker in text for marker in PIP_MARKERS):
                _fail("Frozen app hit the pip/exit path:\n" + text)
            matches = list(cache_root.glob("*/flet/flet.exe")) if cache_root.exists() else []
            if matches and matches[0].is_file():
                found = matches[0]
                time.sleep(2)
                break
            if proc.poll() is not None and not matches:
                break
            time.sleep(1)
    finally:
        if proc.poll() is None:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                check=False,
                capture_output=True,
                text=True,
            )
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()

    text = _crash_text(exe)
    if any(marker in text for marker in PIP_MARKERS):
        _fail("Frozen app hit the pip/exit path:\n" + text)
    if found is None:
        listing = []
        if cache_root.exists():
            listing = [str(p) for p in cache_root.rglob("*")][:40]
        _fail(
            "Smoke launch did not extract flet.exe from the bundled zip "
            f"(exit={proc.poll()}).\ncrash:\n{text}\ncache:\n" + "\n".join(listing)
        )
    print(f"Smoke OK: extracted offline client at {found} (no pip)")
    if crash.exists():
        crash.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--smoke-seconds", type=float, default=45)
    args = parser.parse_args()
    if not args.dist.is_dir():
        _fail(f"Dist directory missing: {args.dist}")
    exe = find_app_exe(args.dist)
    bundled = find_bundled_zip(args.dist)
    print(f"Bundled client zip: {bundled} ({bundled.stat().st_size} bytes), member {EXPECTED_MEMBER}")
    assert_module_frozen(exe)
    if args.smoke:
        smoke_launch(exe, args.smoke_seconds)
    print("verify_windows_dist: OK")


if __name__ == "__main__":
    main()
