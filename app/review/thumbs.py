"""Lightweight ffmpeg frame grabs for the review board. Failure is non-fatal."""
from __future__ import annotations

import subprocess
from pathlib import Path

from app.services.ffmpeg import ffmpeg_bin


def grab_jpeg(src: Path, t_sec: float, dest: Path) -> bool:
    """Write one JPEG at ``t_sec``. Returns False if ffmpeg cannot decode ``src``."""
    src = Path(src)
    dest = Path(dest)
    if not src.is_file():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    t = max(0.0, float(t_sec))
    cmd = [
        ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{t:.3f}",
        "-i",
        str(src),
        "-frames:v",
        "1",
        "-vf",
        "scale=168:-2",
        str(dest),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0
