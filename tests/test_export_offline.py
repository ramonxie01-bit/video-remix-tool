"""Script burn does not require edge-tts. Empty copy is a clear error."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.models import Clip, JobConfig, MediaItem, Scene
from app.pipeline import export as export_mod
from app.pipeline.script import script_rejection_reason
from app.pipeline.tts import _probe_dur


def test_empty_and_invalid_script_are_rejected():
    assert script_rejection_reason("  \n")
    assert "文案为空" in (script_rejection_reason("") or "")
    blank_srt = "1\n00:00:00,000 --> 00:00:01,000\n\n"
    assert "文案无效" in (script_rejection_reason(blank_srt) or "")
    assert script_rejection_reason("钩子\n正文") is None


def test_export_rejects_empty_script_before_touching_video(tmp_path: Path):
    cfg = JobConfig(
        inputs=[tmp_path / "missing.mp4"],
        out_dir=tmp_path / "out",
        durations=[10],
        script_text="   ",
    )
    with pytest.raises(ValueError, match="文案为空"):
        export_mod.export_job_result(cfg)


def test_export_rejects_blank_srt(tmp_path: Path):
    cfg = JobConfig(
        inputs=[tmp_path / "a.mp4"],
        out_dir=tmp_path / "out",
        durations=[10],
        script_text="1\n00:00:00,000 --> 00:00:01,000\n   \n",
    )
    with pytest.raises(ValueError, match="文案无效"):
        export_mod.export_job_result(cfg)


def test_export_errors_when_no_video_survives_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(export_mod, "ingest", lambda _paths: [])
    cfg = JobConfig(
        inputs=[tmp_path / "a.mp4"],
        out_dir=tmp_path / "out",
        durations=[10],
        script_text="钩子\n正文",
    )
    with pytest.raises(ValueError, match="有效数为 0"):
        export_mod.export_job_result(cfg)


def test_tts_failure_still_burns_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    video = tmp_path / "a.mp4"
    video.write_bytes(b"x")
    item = MediaItem(path=video, duration_sec=2.0, width=320, height=240)
    monkeypatch.setattr(export_mod, "ingest", lambda _paths: [item])
    monkeypatch.setattr(
        export_mod,
        "detect_scenes",
        lambda path: [Scene(source=path, start=0, end=2, score=1)],
    )
    monkeypatch.setattr(
        export_mod,
        "pick_highlights",
        lambda scenes, dur, style=None: [Clip(source=video, start=0, end=1.2)],
    )

    def boom(*_args, **_kwargs):
        raise ConnectionError("network down")

    monkeypatch.setattr(export_mod, "tts", boom)
    silent: dict = {}

    def fake_silent(path: Path, duration: float) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"silent")
        silent["path"] = path
        silent["duration"] = duration
        return path

    monkeypatch.setattr(export_mod, "write_silent_audio", fake_silent)
    captured: dict = {}

    def fake_compose(clips, script, audio, duration, out, **_kwargs):
        captured["script"] = script
        captured["audio"] = audio
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"mp4")
        return out

    monkeypatch.setattr(export_mod, "compose", fake_compose)
    cfg = JobConfig(
        inputs=[video],
        out_dir=tmp_path / "out",
        durations=[10],
        script_text="钩子第一句\n正文第二句",
    )
    result = export_mod.export_job_result(cfg)
    assert result.outputs
    assert "钩子第一句" in captured["script"].full_text
    assert captured["script"].lines
    assert "配音失败" in result.warnings[0]
    assert silent["duration"] == 10
    assert captured["audio"] == silent["path"]


def test_probe_dur_uses_bundled_ffprobe(monkeypatch: pytest.MonkeyPatch):
    import importlib

    tts_mod = importlib.import_module("app.pipeline.tts")
    seen: dict = {}

    def fake_check_output(cmd, **_kwargs):
        seen["cmd"] = list(cmd)
        return "2.5\n"

    monkeypatch.setattr(tts_mod.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(
        tts_mod,
        "ffprobe_bin",
        lambda: r"C:\remix\_internal\assets\ffmpeg\ffprobe.exe",
    )
    assert _probe_dur(Path("voice.mp3")) == pytest.approx(2.5)
    assert seen["cmd"][0].endswith("ffprobe.exe")
    assert seen["cmd"][0] != "ffprobe"
