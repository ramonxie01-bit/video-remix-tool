"""Fail the Windows build if the frozen app would still pip-install flet-desktop.

Static checks:
* dist contains flet_desktop/app/flet-windows.zip with flet/flet.exe inside
* the PyInstaller archive actually contains the flet_desktop module

With --smoke, launch the windowed exe briefly with FLET_CLIENT_URL pointed at
an unreachable address. A good bundle extracts ~/.flet/client/*/flet/flet.exe
from the packed zip, never calls pip, and writes remix_startup_ok.txt after
the three FilePickers are constructed. A bad bundle exits on
``NameError: name 'exit' is not defined`` or leaves the startup marker missing
(for example FilePicker(on_result=...) on Flet 0.86).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from flet_desktop_bundle import EXPECTED_MEMBER, ROOT, assert_windows_client_zip

APP_EXE_NAME = "社媒视频混剪.exe"
STARTUP_OK_NAME = "remix_startup_ok.txt"
GUIDE_NAME = "同事使用说明.txt"
FFMPEG_NAMES = ("ffmpeg.exe", "ffprobe.exe")
PIP_MARKERS = (
    "NameError",
    "name 'exit' is not defined",
    "Installing flet-desktop",
    'Unable to install "flet-desktop"',
)


def _emit(message: str, *, err: bool = False) -> None:
    """Write UTF-8 without going through the Windows cp1252 console encoder.

    The dist path contains the app name. A cp1252 stdout raises
    UnicodeEncodeError before the frozen-app checks can finish.
    """
    stream = sys.stderr if err else sys.stdout
    data = (message + "\n").encode("utf-8", errors="backslashreplace")
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        buffer.write(data)
        buffer.flush()
        return
    stream.write(message + "\n")


def _fail(message: str) -> None:
    _emit(message, err=True)
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


def install_colleague_guide(exe: Path) -> None:
    """Copy the one-pager next to the Chinese exe name so it lands in the zip."""
    src = ROOT / "docs" / GUIDE_NAME
    if not src.is_file():
        _fail(f"缺少同事使用说明：{src}")
    guide = src.read_text(encoding="utf-8-sig")
    if "打开审片看板" not in guide:
        _fail("同事使用说明缺少「打开审片看板」")
    if "C:\\remix\\" not in guide:
        _fail("同事使用说明应写明解压到 C:\\remix\\")
    dest = exe.parent / GUIDE_NAME
    shutil.copy2(src, dest)
    _emit(f"同事使用说明: {dest.name}（与 {APP_EXE_NAME} 同目录，建议解压到 C:\\remix\\）")


def _ffmpeg_dir_candidates(exe: Path) -> list[Path]:
    return [
        exe.parent / "_internal" / "assets" / "ffmpeg",
        exe.parent / "assets" / "ffmpeg",
    ]


def locate_ffmpeg_bins(dist: Path, exe: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for name in FFMPEG_NAMES:
        for directory in _ffmpeg_dir_candidates(exe):
            candidate = directory / name
            if candidate.is_file():
                found[name] = candidate
                break
        if name in found:
            continue
        matches = [
            p
            for p in dist.rglob(name)
            if "assets" in p.parts and "ffmpeg" in p.parts and p.is_file()
        ]
        if matches:
            found[name] = matches[0]
    return found


def assert_ffmpeg_bins(dist: Path, exe: Path) -> dict[str, Path]:
    found = locate_ffmpeg_bins(dist, exe)
    missing = [name for name in FFMPEG_NAMES if name not in found]
    if missing:
        _fail(
            "便携包缺少 "
            + "、".join(missing)
            + "。请完整解压（含 _internal\\assets\\ffmpeg），不要只拷贝 "
            + APP_EXE_NAME
            + "。建议解压到短路径，例如 C:\\remix\\"
        )
    for name, path in found.items():
        _emit(f"bundled {name}: {path} ({path.stat().st_size} bytes)")
    if sys.platform == "win32":
        smoke_probe_samples(found["ffmpeg.exe"], found["ffprobe.exe"])
    return found


def _probe_duration(ffprobe: Path, media: Path) -> float:
    proc = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(media),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        _fail(f"ffprobe {media.name} failed: {err[-400:]}")
    try:
        return float((proc.stdout or "").strip() or 0)
    except ValueError:
        _fail(f"ffprobe {media.name} duration not a number: {proc.stdout!r}")
    return 0.0


def smoke_probe_samples(ffmpeg: Path, ffprobe: Path) -> None:
    """Prove the packed binaries accept an mp4 and a mov (duration > 0)."""
    work = Path(tempfile.mkdtemp(prefix="remix-probe-"))
    try:
        mp4 = work / "sample.mp4"
        mov = work / "sample.mov"
        made = subprocess.run(
            [
                str(ffmpeg),
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=size=160x120:rate=15:duration=1",
                "-pix_fmt",
                "yuv420p",
                "-c:v",
                "libx264",
                str(mp4),
            ],
            capture_output=True,
        )
        if made.returncode != 0 or not mp4.is_file():
            err = (made.stderr or b"").decode("utf-8", errors="replace")[-400:]
            _fail(f"bundled ffmpeg could not write sample mp4: {err}")
        wrapped = subprocess.run(
            [str(ffmpeg), "-y", "-i", str(mp4), "-c", "copy", "-f", "mov", str(mov)],
            capture_output=True,
        )
        if wrapped.returncode != 0 or not mov.is_file():
            err = (wrapped.stderr or b"").decode("utf-8", errors="replace")[-400:]
            _fail(f"bundled ffmpeg could not write sample mov: {err}")
        for sample in (mp4, mov):
            dur = _probe_duration(ffprobe, sample)
            _emit(f"probe {sample.name} duration={dur}")
            if dur <= 0:
                _fail(f"{sample.name} probe duration is {dur} (valid count would be 0)")
    finally:
        shutil.rmtree(work, ignore_errors=True)


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
        _emit(f"WARNING: PYZ reader failed ({exc}); loose module copy at {loose[0]}")
        return
    needed = ("flet_desktop", "flet_desktop.version")
    missing = [mod for mod in needed if mod not in names]
    if missing:
        sample = sorted(n for n in names if "flet" in n.lower())[:40]
        _fail(f"Frozen archive missing {missing}. flet-related entries: {sample}")
    _emit(f"PYZ contains flet_desktop ({len(names)} modules)")


def _crash_text(exe: Path) -> str:
    log = exe.parent / "remix_crash.log"
    if not log.is_file():
        return ""
    return log.read_text(encoding="utf-8", errors="replace")


def _startup_log_is_crash(text: str) -> bool:
    """remix_crash.log is written only by the frozen excepthook."""
    return bool(text.strip())


def smoke_launch(exe: Path, seconds: float) -> None:
    cache_root = Path.home() / ".flet" / "client"
    if cache_root.exists():
        shutil.rmtree(cache_root)
    crash = exe.parent / "remix_crash.log"
    startup_ok = exe.parent / STARTUP_OK_NAME
    if crash.exists():
        crash.unlink()
    if startup_ok.exists():
        startup_ok.unlink()

    env = dict(os.environ)
    # If the bundle has no zip, Flet downloads this URL. It must not be reached.
    env["FLET_CLIENT_URL"] = "http://127.0.0.1:9/flet-desktop-must-be-bundled.zip"
    env.pop("REMIX_UI_WEB", None)

    _emit(f"Smoke launch {exe} for up to {seconds:.0f}s")
    proc = subprocess.Popen([str(exe)], env=env, cwd=str(Path.home()))
    found: Path | None = None
    deadline = time.time() + seconds
    try:
        while time.time() < deadline:
            text = _crash_text(exe)
            if any(marker in text for marker in PIP_MARKERS):
                _fail("Frozen app hit the pip/exit path:\n" + text)
            if _startup_log_is_crash(text):
                _fail("Frozen app crashed during startup:\n" + text)
            matches = list(cache_root.glob("*/flet/flet.exe")) if cache_root.exists() else []
            if matches and matches[0].is_file():
                found = matches[0]
            # main() writes this only after the three FilePickers construct
            # and the page is built. A native folder dialog is not opened.
            if found is not None and startup_ok.is_file():
                time.sleep(1)
                text = _crash_text(exe)
                if any(marker in text for marker in PIP_MARKERS):
                    _fail("Frozen app hit the pip/exit path:\n" + text)
                if _startup_log_is_crash(text):
                    _fail("Frozen app crashed during startup:\n" + text)
                break
            if proc.poll() is not None and found is None and not startup_ok.is_file():
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
    if _startup_log_is_crash(text):
        _fail("Frozen app crashed during startup:\n" + text)
    if found is None:
        listing = []
        if cache_root.exists():
            listing = [str(p) for p in cache_root.rglob("*")][:40]
        _fail(
            "Smoke launch did not extract flet.exe from the bundled zip "
            f"(exit={proc.poll()}).\ncrash:\n{text}\ncache:\n" + "\n".join(listing)
        )
    if not startup_ok.is_file():
        _fail(
            "Smoke launch extracted the desktop client but the app did not "
            f"finish building the window ({STARTUP_OK_NAME} missing). "
            "FilePicker construction runs before that marker is written "
            f"(exit={proc.poll()}).\ncrash:\n{text}"
        )
    _emit(f"Smoke OK: extracted offline client at {found}; UI startup marker present")
    startup_ok.unlink()
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
    install_colleague_guide(exe)
    assert_ffmpeg_bins(args.dist, exe)
    bundled = find_bundled_zip(args.dist)
    _emit(f"Bundled client zip: {bundled} ({bundled.stat().st_size} bytes), member {EXPECTED_MEMBER}")
    assert_module_frozen(exe)
    if args.smoke:
        smoke_launch(exe, args.smoke_seconds)
    _emit("verify_windows_dist: OK")


if __name__ == "__main__":
    main()
