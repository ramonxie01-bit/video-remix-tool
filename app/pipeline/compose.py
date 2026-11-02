from __future__ import annotations

from pathlib import Path

from app.models import Clip, Script
from app.services.ffmpeg import burn_vertical_remix


def compose(
    clips: list[Clip],
    script: Script,
    audio: Path,
    duration: int,
    out_path: Path,
    bgm_path: Path | None = None,
    bgm_volume: float = 0.22,
    subtitle_fontsize: int = 18,
    subtitle_margin_v: int = 48,
) -> Path:
    return burn_vertical_remix(
        clips=clips,
        script=script,
        audio=Path(audio),
        duration=duration,
        out_path=Path(out_path),
        bgm_path=Path(bgm_path) if bgm_path else None,
        bgm_volume=bgm_volume,
        subtitle_fontsize=subtitle_fontsize,
        subtitle_margin_v=subtitle_margin_v,
    )
