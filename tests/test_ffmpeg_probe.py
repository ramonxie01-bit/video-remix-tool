"""ffprobe failures keep stderr; stream duration still counts as a video."""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from app.services import ffmpeg as ffmpeg_mod
from app.services.ffmpeg import probe

ingest_mod = importlib.import_module("app.pipeline.ingest")


def test_bundled_ffprobe_is_found_under_internal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    internal = tmp_path / "_internal" / "assets" / "ffmpeg"
    internal.mkdir(parents=True)
    probe_exe = internal / "ffprobe.exe"
    probe_exe.write_bytes(b"MZ")
    monkeypatch.setattr(ffmpeg_mod, "asset_roots", lambda: [tmp_path / "_internal"])
    assert ffmpeg_mod.ffprobe_bin() == str(probe_exe)


def test_probe_surfaces_stderr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    class Proc:
        returncode = 1
        stdout = b""
        stderr = b"moov atom not found\n"

    monkeypatch.setattr("app.services.ffmpeg.subprocess.run", lambda *a, **k: Proc())
    meta = probe(tmp_path / "bad.mov")
    assert "moov atom not found" in meta["error"]
    assert "ffprobe:" in meta["error"]


def test_probe_missing_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def boom(*_a, **_k):
        raise FileNotFoundError(2, "not found")

    monkeypatch.setattr("app.services.ffmpeg.subprocess.run", boom)
    meta = probe(tmp_path / "a.mp4")
    assert "找不到 ffprobe" in meta["error"]


def test_probe_uses_stream_duration_when_format_has_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    payload = json.dumps(
        {
            "format": {},
            "streams": [
                {"codec_type": "video", "duration": "1.25", "width": 320, "height": 240}
            ],
        }
    ).encode()

    class Proc:
        returncode = 0
        stdout = payload
        stderr = b""

    monkeypatch.setattr("app.services.ffmpeg.subprocess.run", lambda *a, **k: Proc())
    meta = probe(tmp_path / "phone.mov")
    assert meta["duration"] == pytest.approx(1.25)
    assert meta["width"] == 320
    assert "error" not in meta


def test_skip_reason_includes_probe_stderr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clip = tmp_path / "bad.mp4"
    clip.write_bytes(b"nope")
    monkeypatch.setattr(
        ingest_mod,
        "probe",
        lambda _path: {"error": "Invalid data found when processing input"},
    )
    report = ingest_mod.ingest_with_report([clip])
    assert report.items == []
    assert report.scanned == 1
    assert "Invalid data found when processing input" in report.skips[0].reason
