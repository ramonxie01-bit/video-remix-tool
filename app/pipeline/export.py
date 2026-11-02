from __future__ import annotations

from pathlib import Path

from app.models import JobConfig
from app.pipeline.compose import compose
from app.pipeline.highlights import pick_highlights
from app.pipeline.ingest import ingest
from app.pipeline.scenes import detect_scenes
from app.pipeline.script import resolve_script
from app.pipeline.styles import get_style
from app.pipeline.tts import tts


def export_job(cfg: JobConfig) -> list[Path]:
    items = ingest(list(cfg.inputs))
    if not items:
        return []
    style = get_style(cfg.template_type)
    bgm_vol = cfg.bgm_volume if cfg.bgm_volume is not None else style.bgm_volume_default
    all_scenes = []
    for it in items:
        all_scenes.extend(detect_scenes(it.path))
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    work = cfg.out_dir / "_work"
    work.mkdir(exist_ok=True)
    outputs: list[Path] = []
    for dur in cfg.durations:
        clips = pick_highlights(all_scenes, dur, style=style)
        script = resolve_script(
            script_text=cfg.script_text,
            script_path=cfg.script_path,
            clips=clips,
            target_sec=dur,
        )
        audio, script = tts(script, cfg.voice, work / f"voice_{dur}.mp3")
        # pad script end to video target if TTS shorter — compose pads audio
        if script.lines and script.lines[-1].end < dur:
            # keep subtitle end = TTS end (sync); video may continue under BGM
            pass
        out = cfg.out_dir / f"remix_{dur}s.mp4"
        compose(
            clips,
            script,
            audio,
            dur,
            out,
            bgm_path=cfg.bgm_path,
            bgm_volume=bgm_vol,
            subtitle_fontsize=style.subtitle_fontsize,
            subtitle_margin_v=style.subtitle_margin_v,
        )
        if out.exists():
            outputs.append(out)
    return outputs
