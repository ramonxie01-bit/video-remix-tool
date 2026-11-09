"""Flet 0.86 FilePicker: no on_result, results come back from the async methods."""
from __future__ import annotations

import asyncio
import importlib
import inspect
from pathlib import Path

import flet as ft
import pytest

from app.ui.main_window import (
    apply_bgm_pick,
    apply_folder_pick,
    apply_script_pick,
    apply_video_files_pick,
    bgm_pick_kwargs,
    extract_picker_path,
    format_ingest_status,
    make_import_pickers,
    mark_startup_ok,
    script_pick_kwargs,
    take_bgm_import,
    take_directory,
    take_script_import,
    take_video_files_import,
    video_pick_kwargs,
    video_pick_unusable_status,
)

ingest_mod = importlib.import_module("app.pipeline.ingest")
VIDEO_EXTS = ingest_mod.VIDEO_EXTS


class _Picker:
    def __init__(self, *, files=None, directory=None):
        self.files = [] if files is None else files
        self.directory = directory
        self.pick_kwargs = None
        self.dir_kwargs = None

    async def pick_files(self, **kwargs):
        self.pick_kwargs = kwargs
        return self.files

    async def get_directory_path(self, **kwargs):
        self.dir_kwargs = kwargs
        return self.directory


def test_filepicker_constructor_rejects_on_result():
    pickers = make_import_pickers()
    assert len(pickers) == 4
    for picker in pickers:
        assert isinstance(picker, ft.FilePicker)
        assert inspect.iscoroutinefunction(picker.pick_files)
        assert inspect.iscoroutinefunction(picker.get_directory_path)
        assert "on_result" not in ft.FilePicker.__dataclass_fields__
    with pytest.raises(TypeError, match="on_result"):
        ft.FilePicker(on_result=lambda _e: None)


def test_folder_pick_replaces_previous_path():
    picked = ["/old"]
    assert apply_folder_pick(picked, None) is None
    assert picked == ["/old"]
    assert apply_folder_pick(picked, "") is None
    assert apply_folder_pick(picked, "/footage") == "/footage"
    assert picked == ["/footage"]


def test_folder_and_file_picks_are_mutually_exclusive():
    picked = ["/old/folder"]
    shown = apply_video_files_pick(picked, ["/v/a.mp4", "", "/v/b.mov"])
    assert shown == ["/v/a.mp4", "/v/b.mov"]
    assert picked == ["/v/a.mp4", "/v/b.mov"]
    assert apply_video_files_pick(picked, []) is None
    assert apply_video_files_pick(picked, ["", ""]) is None
    assert picked == ["/v/a.mp4", "/v/b.mov"]
    assert apply_folder_pick(picked, "/new/folder") == "/new/folder"
    assert picked == ["/new/folder"]


def test_video_pick_kwargs_allow_multiple_video_exts():
    kwargs = video_pick_kwargs()
    assert kwargs["allow_multiple"] is True
    assert kwargs["file_type"] is ft.FilePickerFileType.CUSTOM
    assert kwargs["dialog_title"]
    assert set(kwargs["allowed_extensions"]) == {ext.lstrip(".") for ext in VIDEO_EXTS}
    assert "mp4" in kwargs["allowed_extensions"]
    assert "mov" in kwargs["allowed_extensions"]


def test_take_video_files_import_uses_pick_files():
    chosen = [
        ft.FilePickerFile(id=1, name="a.mp4", size=1, path="/v/a.mp4"),
        ft.FilePickerFile(id=2, name="b.mov", size=1, path="/v/b.mov"),
        ft.FilePickerFile(id=3, name="c.mkv", size=1, path=None),
    ]
    picker = _Picker(files=chosen)
    result = asyncio.run(take_video_files_import(picker))
    assert result is not None
    assert result.paths == ["/v/a.mp4", "/v/b.mov"]
    assert result.missing_path == 1
    assert picker.pick_kwargs == video_pick_kwargs()
    assert asyncio.run(take_video_files_import(_Picker(files=[]))) is None
    assert asyncio.run(take_video_files_import(_Picker(files=None))) is None


def test_extract_picker_path_uses_alternate_fields_when_path_is_none(tmp_path: Path):
    assert extract_picker_path(ft.FilePickerFile(id=1, name="a.mp4", size=1, path=None)) is None
    windows = ft.FilePickerFile(id=2, name=r"D:\素材\车间.MOV", size=1, path=None)
    assert extract_picker_path(windows) == r"D:\素材\车间.MOV"
    assert extract_picker_path({"name": "a.mov", "path": "", "full_path": "/data/a.mov"}) == "/data/a.mov"

    class _Alt:
        path = None
        name = "clip.mp4"
        file_path = str(tmp_path / "clip.mp4")

    assert extract_picker_path(_Alt()) == str(tmp_path / "clip.mp4")


def test_video_pick_without_paths_has_a_clear_status():
    chosen = [
        ft.FilePickerFile(id=1, name="a.mp4", size=1, path=None),
        ft.FilePickerFile(id=2, name="b.MOV", size=1, path=""),
    ]
    result = asyncio.run(take_video_files_import(_Picker(files=chosen)))
    assert result is not None
    assert result.paths == []
    assert result.missing_path == 2
    status = video_pick_unusable_status(result.missing_path)
    assert "已选择 2 个文件" in status
    assert "没有返回可用路径" in status
    assert "C:\\remix\\" in status


def test_format_ingest_status_reports_counts_and_skips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    assert format_ingest_status([]) == "未选择素材"

    empty = tmp_path / "footage"
    empty.mkdir()
    (empty / "notes.txt").write_text("not a video", encoding="utf-8")
    missing = format_ingest_status([str(empty)])
    assert "未找到视频" in missing
    assert "mp4" in missing and "mov" in missing
    assert str(empty) in missing

    good = tmp_path / "ok.mp4"
    bad = tmp_path / "broken.mov"
    good.write_bytes(b"x")
    bad.write_bytes(b"x")

    def fake_probe(path: Path) -> dict:
        if path.name == "ok.mp4":
            return {"duration": 2.5, "width": 1920, "height": 1080}
        return {}

    monkeypatch.setattr(ingest_mod, "probe", fake_probe)
    status = format_ingest_status([str(good), str(bad)])
    assert "已导入 1 个视频（扫描到 2 个候选）" in status
    assert "broken.mov" in status
    assert "ffprobe" in status

    only_bad = format_ingest_status([str(bad)])
    assert "已导入 0 个视频（扫描到 1 个候选）" in only_bad
    assert "有效素材为 0" in only_bad
    assert bad.name in only_bad
    assert str(bad) in only_bad


def test_script_and_bgm_results(tmp_path: Path):  # noqa: C901
    missing_text, missing_path, missing_status = apply_script_pick(None)
    assert missing_text is None and missing_path is None
    assert missing_status == "无法读取文案文件"

    gone = tmp_path / "missing.txt"
    assert apply_script_pick(str(gone))[0] is None

    script = tmp_path / "口播.txt"
    script.write_text("\ufeff钩子\n正文\n", encoding="utf-8")
    text, path, status = apply_script_pick(str(script))
    assert text == "钩子\n正文\n"
    assert path == script
    assert status == "已导入文案：口播.txt"

    script_ok = tmp_path / "ok.txt"
    script_ok.write_text("ok", encoding="utf-8")

    def _boom(self, *args, **kwargs):
        raise OSError("denied")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(Path, "read_text", _boom)
    try:
        text, _path, status = apply_script_pick(str(script_ok))
        assert text is None
        assert status == "读文案失败：denied"
    finally:
        monkeypatch.undo()

    assert apply_bgm_pick(None) == (None, "无法读取配乐文件")
    assert apply_bgm_pick("") == (None, "无法读取配乐文件")
    path, status = apply_bgm_pick(str(tmp_path / "bed.mp3"))
    assert path == str(tmp_path / "bed.mp3")
    assert status == "已选配乐：bed.mp3"


def test_take_directory_and_files_use_086_result_api(tmp_path: Path):
    folder = _Picker(directory="/data/footage")
    assert asyncio.run(take_directory(folder)) == "/data/footage"
    assert folder.dir_kwargs == {}

    assert asyncio.run(take_directory(_Picker(directory=None))) is None
    assert asyncio.run(take_directory(_Picker(directory=""))) is None

    script = tmp_path / "a.txt"
    script.write_text("一行口播", encoding="utf-8")
    chosen = ft.FilePickerFile(id=1, name="a.txt", size=4, path=str(script))
    script_picker = _Picker(files=[chosen])
    result = asyncio.run(take_script_import(script_picker))
    assert result is not None
    assert result[0] == "一行口播"
    assert script_picker.pick_kwargs == script_pick_kwargs()
    assert script_picker.pick_kwargs["file_type"] is ft.FilePickerFileType.CUSTOM

    no_path = _Picker(files=[ft.FilePickerFile(id=2, name="a.txt", size=1, path=None)])
    failed = asyncio.run(take_script_import(no_path))
    assert failed is not None and failed[0] is None
    assert "没有返回可用路径" in failed[2]

    script_via_name = tmp_path / "口播.txt"
    script_via_name.write_text("钩子一句\n", encoding="utf-8")
    named = _Picker(
        files=[ft.FilePickerFile(id=4, name=str(script_via_name), size=8, path=None)]
    )
    named_result = asyncio.run(take_script_import(named))
    assert named_result is not None and named_result[0] is not None
    assert "钩子一句" in named_result[0]

    assert asyncio.run(take_script_import(_Picker(files=[]))) is None

    bgm = _Picker(files=[ft.FilePickerFile(id=3, name="bed.mp3", size=8, path="/music/bed.mp3")])
    bgm_result = asyncio.run(take_bgm_import(bgm))
    assert bgm_result == ("/music/bed.mp3", "已选配乐：bed.mp3")
    assert bgm.pick_kwargs == bgm_pick_kwargs()
    assert bgm.pick_kwargs["allowed_extensions"] == ["mp3", "wav", "m4a"]
    assert asyncio.run(take_bgm_import(_Picker(files=[]))) is None


def test_startup_marker_is_frozen_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import sys

    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "社媒视频混剪.exe"))
    marker = tmp_path / "remix_startup_ok.txt"
    mark_startup_ok()
    assert not marker.exists()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    mark_startup_ok()
    assert marker.read_text(encoding="utf-8").startswith("ok v")
