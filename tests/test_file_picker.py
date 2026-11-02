"""Flet 0.86 FilePicker: no on_result, results come back from the async methods."""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

import flet as ft
import pytest

from app.ui.main_window import (
    apply_bgm_pick,
    apply_folder_pick,
    apply_script_pick,
    bgm_pick_kwargs,
    make_import_pickers,
    mark_startup_ok,
    script_pick_kwargs,
    take_bgm_import,
    take_directory,
    take_script_import,
)


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
    assert len(pickers) == 3
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
