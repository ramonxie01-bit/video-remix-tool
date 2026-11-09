from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.models import JobConfig
from app.pipeline.compose import compose
from app.pipeline.highlights import pick_highlights
from app.pipeline.ingest import ingest
from app.pipeline.scenes import detect_scenes
from app.pipeline.script import resolve_script, script_rejection_reason
from app.pipeline.styles import get_style
from app.pipeline.tts import tts
from app.services.ffmpeg import write_silent_audio


@dataclass
class ExportResult:
    outputs: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def user_script_text(cfg: JobConfig) -> str:
    """Paste wins; otherwise read the imported .txt/.srt. Missing both → empty."""
    text = cfg.script_text or ""
    if text.strip():
        return text
    path = cfg.script_path
    if path and Path(path).is_file():
        return Path(path).read_text(encoding="utf-8-sig")
    return ""


def export_job(cfg: JobConfig) -> list[Path]:
    return export_job_result(cfg).outputs


def export_job_result(cfg: JobConfig) -> ExportResult:
    """Burn the user script into the video. TTS is optional and may be silent."""
    user_text = user_script_text(cfg)
    reason = script_rejection_reason(user_text)
    if reason:
        raise ValueError(reason)
    items = ingest(list(cfg.inputs))
    if not items:
        raise ValueError(
            "没有识别到可用视频（有效数为 0）。"
            "请确认是 mp4/mov，并查看状态栏里的 ffprobe 报错；"
            "路径过长时请解压到 C:\\remix\\ 再导入。"
        )
    style = get_style(cfg.template_type)
    bgm_vol = cfg.bgm_volume if cfg.bgm_volume is not None else style.bgm_volume_default
    all_scenes = []
    for it in items:
        all_scenes.extend(detect_scenes(it.path))
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    work = cfg.out_dir / "_work"
    work.mkdir(exist_ok=True)
    result = ExportResult()
    for dur in cfg.durations:
        clips = pick_highlights(all_scenes, dur, style=style)
        script = resolve_script(
            script_text=user_text,
            script_path=None,
            clips=clips,
            target_sec=dur,
        )
        if not script.lines:
            raise ValueError(
                "文案无效：没有可用的字幕句子。"
                "请检查粘贴内容或 .txt/.srt（UTF-8）是否为空。"
            )
        try:
            audio, script = tts(script, cfg.voice, work / f"voice_{dur}.mp3")
        except Exception as ex:  # noqa: BLE001 — network, edge-tts, or ffprobe
            result.warnings.append(
                f"{dur}s 配音失败，已用静音导出并烧录字幕（可稍后自备口播）：{ex}"
            )
            audio = write_silent_audio(work / f"voice_{dur}.m4a", float(dur))
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
            result.outputs.append(out)
    return result
