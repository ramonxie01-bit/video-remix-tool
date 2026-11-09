"""Generate a real mp4 and mov, then assert ingest counts them (not 0).

Uses the bundled assets/ffmpeg/*.exe when present, otherwise PATH.
Prints IMPORT_SMOKE valid=<n> scanned=<n> for the Windows CI log.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.pipeline.ingest import ingest_with_report
from app.services.ffmpeg import ffmpeg_bin, ffprobe_bin


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace")[-600:]
        raise SystemExit(f"command failed: {cmd[0]}\n{err}")


def build_samples(folder: Path) -> list[Path]:
    ffmpeg = ffmpeg_bin()
    mp4 = folder / "clip.mp4"
    mov = folder / "clip.mov"
    # Distinct basename: on a case-insensitive volume CLIP.MOV is the same
    # file as clip.mov, so an uppercase copy of that name never adds a count.
    upper = folder / "PHONE.MOV"
    chinese = folder / "车间成片.mp4"
    _run(
        [
            ffmpeg,
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
        ]
    )
    _run([ffmpeg, "-y", "-i", str(mp4), "-c", "copy", "-f", "mov", str(mov)])
    upper.write_bytes(mov.read_bytes())
    chinese.write_bytes(mp4.read_bytes())
    return [mp4, mov, upper, chinese]


def main() -> int:
    ffprobe = ffprobe_bin()
    print(f"ffmpeg={ffmpeg_bin()}")
    print(f"ffprobe={ffprobe}")
    with tempfile.TemporaryDirectory(prefix="remix-import-") as raw:
        folder = Path(raw)
        samples = build_samples(folder)
        report = ingest_with_report([folder])
        names = {item.path.name: item.duration_sec for item in report.items}
        print(
            f"IMPORT_SMOKE valid={len(report.items)} scanned={report.scanned} "
            f"skips={len(report.skips)}"
        )
        for item in report.items:
            print(f"  ok {item.path.name} duration={item.duration_sec}")
        for skip in report.skips:
            print(f"  skip {skip.path.name}: {skip.reason}")
        missing = [p.name for p in samples if p.name not in names]
        if report.scanned < len(samples) or len(report.items) < len(samples) or missing:
            print(f"expected {len(samples)} valid files, missing={missing}", file=sys.stderr)
            return 1
        if any((names[p.name] or 0) <= 0 for p in samples):
            print("duration was 0", file=sys.stderr)
            return 1
    print("IMPORT_SMOKE ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
