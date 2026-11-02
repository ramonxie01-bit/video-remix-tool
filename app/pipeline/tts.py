from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from app.models import Script, ScriptLine, VoiceId


VOICE_MAP: dict[VoiceId, str] = {
    "female_narration": "zh-CN-XiaoxiaoNeural",
    "male_factory": "zh-CN-YunxiNeural",
}


def _probe_dur(path: Path) -> float:
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            text=True,
        ).strip()
        return float(out or 0)
    except Exception:
        return 0.0


def align_script_to_audio(script: Script, audio_dur: float) -> Script:
    """Stretch/squash line timings to match real TTS length (A/V sync)."""
    if not script.lines or audio_dur <= 0:
        return script
    old_end = max(l.end for l in script.lines) or 1.0
    scale = audio_dur / old_end
    lines: list[ScriptLine] = []
    for l in script.lines:
        lines.append(
            ScriptLine(
                text=l.text,
                start=round(l.start * scale, 3),
                end=round(min(l.end * scale, audio_dur), 3),
            )
        )
    if lines:
        lines[-1].end = round(audio_dur, 3)
    return Script(lines=lines, full_text=script.full_text)


def tts(script: Script, voice: VoiceId, out_wav: Path) -> tuple[Path, Script]:
    """Synthesize narration; return (audio_path, timing-aligned script)."""
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    text = script.full_text or "，".join(l.text for l in script.lines)
    if not text.strip():
        text = "数码印花，小单快反。"
    voice_id = VOICE_MAP[voice]
    target = out_wav.with_suffix(".mp3")

    async def _run() -> None:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(str(target))

    asyncio.run(_run())
    audio = target if target.exists() else out_wav
    dur = _probe_dur(audio)
    aligned = align_script_to_audio(script, dur if dur > 0 else max(l.end for l in script.lines))
    return audio, aligned
