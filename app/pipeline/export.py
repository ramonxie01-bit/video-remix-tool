from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.models import JobConfig
from app.pipeline.compose import compose
from app.pipeline.highlights import clips_use_excluded, pick_highlights
from app.review.bundle import exclusion_ranges, write_review_bundle
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
    # Pieces actually composed. plan.json lists these clips only (no fake slots).
    packed: list[dict] = []
    for dur in cfg.durations:
        # Disabled review slots from the previous board, if the colleague saved any.
        # enabled=false does not skip the file; see review_notes / 同事使用说明.
        exclude = exclusion_ranges(
            cfg.out_dir, theme=style.label_zh, duration_sec=int(dur)
        )
        if exclude:
            clips = pick_highlights(all_scenes, dur, style=style, exclude=exclude)
            if clips_use_excluded(clips, exclude):
                result.warnings.append(
                    f"{dur}s 有「不用」槽位没能完全避开（剩余素材不够），"
                    "本次仍使用真实镜头，没有编造素材。"
                )
        else:
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
            packed.append(
                {
                    "duration_sec": int(dur),
                    "output_path": out,
                    "clips": clips,
                    "copy": script.full_text,
                }
            )
    if packed:
        try:
            pack = write_review_bundle(
                cfg.out_dir,
                style_id=style.id,
                theme=style.label_zh,
                pieces=packed,
            )
        except Exception as ex:  # noqa: BLE001 — board must not fail a finished mp4
            result.warnings.append(f"审片计划未写入：{ex}")
        else:
            if pack.thumbs_failed and pack.thumbs_ok == 0:
                result.warnings.append(
                    "槽位缩略图未生成（ffmpeg 抽帧失败），审片看板仍可打开。"
                )
    return result
