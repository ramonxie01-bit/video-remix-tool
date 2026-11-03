from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.models import MediaItem
from app.services.ffmpeg import probe


VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}


@dataclass(frozen=True)
class Skip:
    path: Path
    reason: str


@dataclass
class IngestReport:
    items: list[MediaItem] = field(default_factory=list)
    skips: list[Skip] = field(default_factory=list)
    scanned: int = 0  # candidates matching VIDEO_EXTS before probe


def collect_video_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files.extend(x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in VIDEO_EXTS)
        elif p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            files.append(p)
    # de-dupe by resolved path when possible
    out: list[Path] = []
    seen: set[str] = set()
    for f in sorted(files, key=lambda x: str(x).lower()):
        key = str(f.resolve()) if f.exists() else str(f)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def ingest_with_report(paths: list[Path]) -> IngestReport:
    """Scan files/folders; probe failures go to skips (not silent MediaItems)."""
    files = collect_video_files(paths)
    report = IngestReport(scanned=len(files))
    for f in files:
        meta = probe(f)
        # probe returns {} on failure; also treat missing duration as unusable
        if not meta or not meta.get("duration"):
            reason = "ffprobe 无法识别（损坏、非视频、缺 codec，或本机/打包未带上 ffprobe）"
            report.skips.append(Skip(path=f, reason=reason))
            continue
        report.items.append(
            MediaItem(
                path=f,
                duration_sec=meta.get("duration"),
                width=meta.get("width"),
                height=meta.get("height"),
            )
        )
    return report


def ingest(paths: list[Path]) -> list[MediaItem]:
    """Scan files/folders → MediaItem list (skips probe failures)."""
    return ingest_with_report(paths).items
