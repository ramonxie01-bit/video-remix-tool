"""Ingest report: valid videos, scanned count, and named probe skips."""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ingest_mod = importlib.import_module("app.pipeline.ingest")


def test_collect_video_files_keeps_known_exts_only(tmp_path: Path):
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    (tmp_path / "clip.MP4").write_bytes(b"a")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "take.mov").write_bytes(b"b")
    (nested / "still.jpg").write_bytes(b"c")

    names = {p.name for p in ingest_mod.collect_video_files([tmp_path, tmp_path / "clip.MP4"])}
    assert names == {"clip.MP4", "take.mov"}


def test_ingest_skips_probe_failures_and_returns_only_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    good = tmp_path / "ok.mp4"
    bad = tmp_path / "broken.mov"
    good.write_bytes(b"ok")
    bad.write_bytes(b"bad")

    def fake_probe(path: Path) -> dict:
        if path.name == "ok.mp4":
            return {"duration": 3.5, "width": 1280, "height": 720}
        return {}

    monkeypatch.setattr(ingest_mod, "probe", fake_probe)
    report = ingest_mod.ingest_with_report([tmp_path])
    assert report.scanned == 2
    assert [item.path.name for item in report.items] == ["ok.mp4"]
    assert report.items[0].duration_sec == 3.5
    assert len(report.skips) == 1
    assert report.skips[0].path.name == "broken.mov"
    assert "ffprobe" in report.skips[0].reason
    assert [item.path for item in ingest_mod.ingest([tmp_path])] == [good]


def test_missing_duration_is_a_named_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clip = tmp_path / "zero.mkv"
    clip.write_bytes(b"z")
    monkeypatch.setattr(
        ingest_mod,
        "probe",
        lambda _path: {"duration": 0, "width": None, "height": None},
    )
    report = ingest_mod.ingest_with_report([clip])
    assert report.scanned == 1
    assert report.items == []
    assert report.skips[0].path.name == "zero.mkv"
