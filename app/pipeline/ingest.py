from __future__ import annotations

from pathlib import Path

from app.models import MediaItem
from app.services.ffmpeg import probe


VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}


def ingest(paths: list[Path]) -> list[MediaItem]:
    """Scan files/folders → MediaItem list."""
    files: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files.extend(x for x in p.rglob("*") if x.suffix.lower() in VIDEO_EXTS)
        elif p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            files.append(p)
    items: list[MediaItem] = []
    for f in sorted(set(files)):
        meta = probe(f)
        items.append(
            MediaItem(
                path=f,
                duration_sec=meta.get("duration"),
                width=meta.get("width"),
                height=meta.get("height"),
            )
        )
    return items
