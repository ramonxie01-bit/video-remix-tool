from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

DurationSec = Literal[10, 15, 30]
VoiceId = Literal["female_narration", "male_factory"]
TemplateType = Literal["factory", "reverse_hook", "seed", "explainer"]


@dataclass
class MediaItem:
    path: Path
    duration_sec: float | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class Scene:
    source: Path
    start: float
    end: float
    score: float = 0.0


@dataclass
class Clip:
    source: Path
    start: float
    end: float
    role: str = "broll"


@dataclass
class ScriptLine:
    text: str
    start: float
    end: float


@dataclass
class Script:
    lines: list[ScriptLine] = field(default_factory=list)
    full_text: str = ""


@dataclass
class JobConfig:
    inputs: list[Path]
    out_dir: Path
    durations: list[DurationSec] = field(default_factory=lambda: [10, 15, 30])
    voice: VoiceId = "female_narration"
    keep_source_audio: bool = False
    bgm_path: Path | None = None
    # None → use RemixStyle.bgm_volume_default for the selected template_type
    bgm_volume: float | None = None
    # Optional override from content bot (paste / .txt / .srt). Empty → gen_script.
    script_text: str | None = None
    script_path: Path | None = None
    # 成片类型：factory / reverse_hook / seed / explainer
    template_type: TemplateType | str = "factory"
