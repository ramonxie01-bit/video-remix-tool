"""Import-level smoke check (no ffmpeg, no native file dialog)."""
from __future__ import annotations

import asyncio
import inspect
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import flet as ft

from app.models import JobConfig
from app.pipeline.highlights import pick_highlights
from app.pipeline.scenes import Scene
from app.ui.main_window import (
    apply_bgm_pick,
    apply_folder_pick,
    apply_script_pick,
    make_import_pickers,
    take_bgm_import,
    take_directory,
    take_script_import,
)

print("models ok", JobConfig(inputs=[Path(".")], out_dir=Path("/tmp/out")))
print("highlights ok", pick_highlights([Scene(source=Path("a.mp4"), start=0, end=2, score=1)], 10))

pickers = make_import_pickers()
assert len(pickers) == 3, pickers
for picker in pickers:
    assert isinstance(picker, ft.FilePicker)
    assert inspect.iscoroutinefunction(picker.pick_files)
    assert inspect.iscoroutinefunction(picker.get_directory_path)
try:
    ft.FilePicker(on_result=lambda _e: None)
    raise SystemExit("FilePicker still accepts on_result")
except TypeError as exc:
    assert "on_result" in str(exc)

picked: list[str] = []
assert apply_folder_pick(picked, "/data/footage") == "/data/footage"
assert picked == ["/data/footage"]
assert apply_folder_pick(picked, None) is None


class _Dir:
    async def get_directory_path(self, **kwargs):
        assert kwargs == {}
        return "/data/footage"


assert asyncio.run(take_directory(_Dir())) == "/data/footage"


class _Cancel:
    async def get_directory_path(self, **_kwargs):
        return None

    async def pick_files(self, **_kwargs):
        return []


assert asyncio.run(take_directory(_Cancel())) is None
assert asyncio.run(take_script_import(_Cancel())) is None
assert asyncio.run(take_bgm_import(_Cancel())) is None

# tempfile, not /tmp: the Windows runner has no /tmp directory.
script = Path(tempfile.gettempdir()) / "remix_smoke_script.txt"
script.write_text("钩子\n正文\n", encoding="utf-8")


class _Script:
    def __init__(self) -> None:
        self.kwargs = None

    async def pick_files(self, **kwargs):
        self.kwargs = kwargs
        return [ft.FilePickerFile(id=1, name=script.name, size=8, path=str(script))]


script_picker = _Script()
imported = asyncio.run(take_script_import(script_picker))
assert imported is not None and imported[0] is not None and "钩子" in imported[0]
assert script_picker.kwargs is not None
assert script_picker.kwargs["allowed_extensions"] == ["txt", "srt"]
assert script_picker.kwargs["file_type"] == ft.FilePickerFileType.CUSTOM
text, path, status = apply_script_pick(str(script))
assert text is not None and path == script and status == f"已导入文案：{script.name}"


class _Bgm:
    def __init__(self) -> None:
        self.kwargs = None

    async def pick_files(self, **kwargs):
        self.kwargs = kwargs
        return [ft.FilePickerFile(id=2, name="bed.mp3", size=4, path="/music/bed.mp3")]


bgm_picker = _Bgm()
bgm = asyncio.run(take_bgm_import(bgm_picker))
assert bgm == ("/music/bed.mp3", "已选配乐：bed.mp3")
assert bgm_picker.kwargs is not None
assert bgm_picker.kwargs["allowed_extensions"] == ["mp3", "wav", "m4a"]
assert apply_bgm_pick(None) == (None, "无法读取配乐文件")

print("filepicker ok")
print("smoke ok")
