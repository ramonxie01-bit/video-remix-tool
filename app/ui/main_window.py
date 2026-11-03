from __future__ import annotations

from pathlib import Path

import flet as ft

from app.models import JobConfig
from app.pipeline.export import export_job
from app.pipeline.ingest import VIDEO_EXTS, ingest_with_report
from app.pipeline.styles import get_style, style_options
from app.services.update_check import LOCAL_VERSION, check_update

# Written beside a frozen exe after the window is built. The Windows smoke
# treats a missing file as a startup crash: Flet shows session errors in the
# client and does not always reach remix_crash.log.
STARTUP_OK_NAME = "remix_startup_ok.txt"


def make_import_pickers() -> tuple[ft.FilePicker, ft.FilePicker, ft.FilePicker, ft.FilePicker]:
    """Folder, video-files, script, and BGM pickers.

    Flet 0.86 FilePicker is a service. The constructor does not take
    on_result, and pick_files / get_directory_path are async and return
    the selection. Instances register themselves on the current page.
    Do not place them on the page overlay (that control is unknown in 0.86).
    """
    return ft.FilePicker(), ft.FilePicker(), ft.FilePicker(), ft.FilePicker()


def script_pick_kwargs() -> dict:
    # allowed_extensions is applied only when file_type is CUSTOM.
    return {
        "allow_multiple": False,
        "file_type": ft.FilePickerFileType.CUSTOM,
        "allowed_extensions": ["txt", "srt"],
        "dialog_title": "选择口播文案 (.txt / .srt)",
    }


def bgm_pick_kwargs() -> dict:
    return {
        "allow_multiple": False,
        "file_type": ft.FilePickerFileType.CUSTOM,
        "allowed_extensions": ["mp3", "wav", "m4a"],
        "dialog_title": "选择配乐文件",
    }


def video_pick_kwargs() -> dict:
    # allowed_extensions is applied only when file_type is CUSTOM.
    return {
        "allow_multiple": True,
        "file_type": ft.FilePickerFileType.CUSTOM,
        "allowed_extensions": sorted(ext.lstrip(".") for ext in VIDEO_EXTS),
        "dialog_title": "选择视频文件（可多选）",
    }


def apply_folder_pick(picked: list[str], path: str | None) -> str | None:
    """Replace inputs with one footage folder (mutually exclusive with file picks).

    None or blank means the dialog was cancelled. Choosing a folder clears any
    previously selected video files so JobConfig.inputs has a single source.
    """
    if not path:
        return None
    picked.clear()
    picked.append(path)
    return path


def apply_video_files_pick(picked: list[str], paths: list[str]) -> list[str] | None:
    """Replace inputs with multi-selected video files (mutually exclusive with folder).

    Empty list means cancelled / nothing usable. Choosing files clears any
    previously selected folder so JobConfig.inputs has a single source.
    """
    clean = [p for p in paths if p]
    if not clean:
        return None
    picked.clear()
    picked.extend(clean)
    return clean


def format_ingest_status(picked: list[str]) -> str:
    """Immediate ingest feedback for status bar after folder/file pick."""
    if not picked:
        return "未选择素材"
    report = ingest_with_report([Path(p) for p in picked])
    exts = ", ".join(sorted(ext.lstrip(".") for ext in VIDEO_EXTS))
    where = picked[0] if len(picked) == 1 else f"{len(picked)} 个文件"
    if report.scanned == 0:
        return (
            f"未找到视频（支持 {exts}）。已选：{where}。"
            "请用「导入视频文件」多选 mp4/mov，或把成片放进所选文件夹。"
        )
    parts = [f"已导入 {len(report.items)} 个视频（扫描到 {report.scanned} 个候选）"]
    if report.skips:
        detail = "；".join(f"{s.path.name}：{s.reason}" for s in report.skips[:5])
        more = f" 等{len(report.skips)}个" if len(report.skips) > 5 else ""
        parts.append(f"跳过 {len(report.skips)} 个——{detail}{more}")
    if len(report.items) == 0:
        parts.append(f"有效素材为 0，请检查 ffprobe / 文件是否损坏。路径：{where}")
    return "。".join(parts)


def apply_script_pick(file_path: str | None) -> tuple[str | None, Path | None, str]:
    """A script file was chosen. Return (text, path, status). text is None on failure."""
    if not file_path:
        return None, None, "无法读取文案文件"
    path = Path(file_path)
    if not path.is_file():
        return None, None, "无法读取文案文件"
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as ex:
        return None, None, f"读文案失败：{ex}"
    return raw, path, f"已导入文案：{path.name}"


def apply_bgm_pick(file_path: str | None) -> tuple[str | None, str]:
    """A BGM file was chosen. Return (path, status). path is None when unusable."""
    if not file_path:
        return None, "无法读取配乐文件"
    return file_path, f"已选配乐：{Path(file_path).name}"


async def take_directory(picker: ft.FilePicker) -> str | None:
    path = await picker.get_directory_path()
    return path or None


async def take_script_import(
    picker: ft.FilePicker,
) -> tuple[str | None, Path | None, str] | None:
    """None when the dialog is cancelled."""
    files = await picker.pick_files(**script_pick_kwargs())
    if not files:
        return None
    return apply_script_pick(files[0].path)


async def take_bgm_import(picker: ft.FilePicker) -> tuple[str | None, str] | None:
    """None when the dialog is cancelled."""
    files = await picker.pick_files(**bgm_pick_kwargs())
    if not files:
        return None
    return apply_bgm_pick(files[0].path)


async def take_video_files_import(picker: ft.FilePicker) -> list[str] | None:
    """None when the dialog is cancelled."""
    files = await picker.pick_files(**video_pick_kwargs())
    if not files:
        return None
    return [f.path for f in files if getattr(f, "path", None)]


def mark_startup_ok() -> None:
    """Record that FilePickers were constructed and the window was built."""
    import sys

    if not getattr(sys, "frozen", False):
        return
    dest = Path(sys.executable).resolve().parent / STARTUP_OK_NAME
    dest.write_text(f"ok v{LOCAL_VERSION}\n", encoding="utf-8")


def run_app() -> None:
    import os

    view = ft.AppView.FLET_APP
    if os.environ.get("REMIX_UI_WEB", "").strip().lower() in {"1", "true", "yes"}:
        view = ft.AppView.WEB_BROWSER
    ft.app(target=main, view=view)



def main(page: ft.Page) -> None:
    page.title = "社媒视频混剪"
    page.window.width = 780
    page.window.height = 680
    page.scroll = ft.ScrollMode.AUTO

    status = ft.Text("导入车间成片 → 勾选 10/15/30 → 一键出竖屏（字幕+配音）")
    out_field = ft.TextField(label="输出目录", value=str(Path.home() / "Desktop" / "remix_out"))
    bgm_field = ft.TextField(
        label="配乐路径",
        value="",
        hint_text="点「导入配乐」选择 mp3/wav/m4a，或手动粘贴路径",
        expand=True,
    )
    script_field = ft.TextField(
        label="口播文案（粘贴）",
        value="",
        hint_text="由内容 bot 出稿后粘贴或导入；同一稿驱动字幕+TTS。工具内只做轻改。",
        multiline=True,
        min_lines=4,
        max_lines=8,
        expand=True,
    )
    script_hint = ft.Text(
        "提示：内容 bot 出完整口播稿 → 粘贴或「导入文案」(.txt/.srt) → 生成时驱动字幕+TTS",
        size=12,
        color=ft.Colors.BLUE_GREY_400,
    )
    update_status = ft.Text(f"当前版本 v{LOCAL_VERSION}", size=12)
    dur_10 = ft.Checkbox(label="10s", value=True)
    dur_15 = ft.Checkbox(label="15s", value=True)
    dur_30 = ft.Checkbox(label="30s", value=True)
    voice = ft.Dropdown(
        label="配音音色",
        value="female_narration",
        options=[
            ft.dropdown.Option("female_narration", "女声解说"),
            ft.dropdown.Option("male_factory", "男声工厂感"),
        ],
    )
    _style_opts = style_options()
    template_dd = ft.Dropdown(
        label="成片类型",
        value=_style_opts[0][0] if _style_opts else "factory",
        options=[ft.dropdown.Option(sid, label) for sid, label in _style_opts],
        width=280,
    )
    style_tip = ft.Text(
        get_style(template_dd.value).tip,
        size=12,
        color=ft.Colors.BLUE_GREY_400,
    )

    def on_template_change(e: ft.ControlEvent) -> None:
        style_tip.value = get_style(template_dd.value).tip
        page.update()

    template_dd.on_change = on_template_change
    picked: list[str] = []
    script_path_held: list[Path | None] = [None]
    picked_label = ft.Text("未选择素材")

    folder_picker, video_picker, script_picker, bgm_picker = make_import_pickers()

    async def pick_folder(_e: ft.ControlEvent) -> None:
        shown = apply_folder_pick(picked, await take_directory(folder_picker))
        if shown is None:
            return
        picked_label.value = shown
        status.value = format_ingest_status(picked)
        page.update()

    async def pick_videos(_e: ft.ControlEvent) -> None:
        paths = await take_video_files_import(video_picker)
        if paths is None:
            return
        shown = apply_video_files_pick(picked, paths)
        if shown is None:
            return
        if len(shown) == 1:
            picked_label.value = shown[0]
        else:
            picked_label.value = f"已选 {len(shown)} 个视频文件"
        status.value = format_ingest_status(picked)
        page.update()

    async def pick_script(_e: ft.ControlEvent) -> None:
        result = await take_script_import(script_picker)
        if result is None:
            return
        text, path, message = result
        if text is None:
            status.value = message
        else:
            script_field.value = text
            script_path_held[0] = path
            status.value = message
        page.update()

    async def pick_bgm(_e: ft.ControlEvent) -> None:
        result = await take_bgm_import(bgm_picker)
        if result is None:
            return
        path, message = result
        if path is None:
            status.value = message
        else:
            bgm_field.value = path
            status.value = message
        page.update()

    def do_export(_e: ft.ControlEvent) -> None:
        if not picked:
            status.value = "请先「选择素材文件夹」或「导入视频文件」"
            page.update()
            return
        durs = []
        if dur_10.value:
            durs.append(10)
        if dur_15.value:
            durs.append(15)
        if dur_30.value:
            durs.append(30)
        if not durs:
            status.value = "至少勾选一个时长"
            page.update()
            return
        status.value = "生成中…"
        page.update()
        script_text = (script_field.value or "").strip() or None
        bgm_raw = (bgm_field.value or "").strip()
        spath = script_path_held[0]
        # .srt: keep file path for cue timings (text box is preview only)
        if spath is not None and spath.suffix.lower() == ".srt" and spath.is_file():
            use_text, use_path = None, spath
        else:
            use_text, use_path = script_text, (None if script_text else spath)
        cfg = JobConfig(
            inputs=[Path(p) for p in picked],
            out_dir=Path(out_field.value or "."),
            durations=durs,  # type: ignore[arg-type]
            voice=voice.value or "female_narration",  # type: ignore[arg-type]
            bgm_path=Path(bgm_raw) if bgm_raw else None,
            bgm_volume=None,  # use style default unless user override added later
            script_text=use_text,
            script_path=use_path,
            template_type=template_dd.value or "factory",
        )
        try:
            outs = export_job(cfg)
            status.value = f"完成：{', '.join(str(p) for p in outs)}" if outs else "未生成文件（检查 ffmpeg）"
        except Exception as ex:  # noqa: BLE001
            status.value = f"失败：{ex}"
        page.update()

    def do_check_update(_e: ft.ControlEvent) -> None:
        update_status.value = "正在检查更新…"
        page.update()
        info = check_update()
        if info.offline or info.error:
            update_status.value = f"离线可用，稍后再试（v{info.local}）"
        elif info.has_update:
            note = info.notes or ""
            dl = f" → {info.download_url}" if info.download_url else ""
            update_status.value = f"有新版本 v{info.remote}（本地 v{info.local}）{dl} {note}".strip()
        else:
            update_status.value = f"已是最新 v{info.local}" + (f"：{info.notes}" if info.notes else "")
        page.update()

    page.add(
        ft.Text("鲸点混剪 · 部门版 MVP", size=22, weight=ft.FontWeight.BOLD),
        ft.Row(
            [
                ft.ElevatedButton(
                    "选择素材文件夹",
                    on_click=pick_folder,
                ),
                ft.ElevatedButton(
                    "导入视频文件",
                    icon=ft.Icons.VIDEO_FILE,
                    on_click=pick_videos,
                ),
                picked_label,
            ]
        ),
        out_field,
        ft.Row([dur_10, dur_15, dur_30]),
        voice,
        ft.Text("成片类型", weight=ft.FontWeight.BOLD),
        template_dd,
        style_tip,
        ft.Divider(),
        ft.Text("口播文案", weight=ft.FontWeight.BOLD),
        script_hint,
        script_field,
        ft.ElevatedButton(
            "导入文案",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=pick_script,
        ),
        ft.Divider(),
        ft.Text("配乐（BGM）", weight=ft.FontWeight.BOLD),
        ft.Row(
            [
                bgm_field,
                ft.ElevatedButton(
                    "导入配乐",
                    icon=ft.Icons.LIBRARY_MUSIC,
                    bgcolor=ft.Colors.ORANGE_400,
                    color=ft.Colors.WHITE,
                    on_click=pick_bgm,
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
        ),
        ft.Divider(),
        ft.ElevatedButton("生成混剪", on_click=do_export, bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE),
        status,
        ft.Divider(),
        ft.Row(
            [
                ft.OutlinedButton("检查更新", icon=ft.Icons.SYSTEM_UPDATE, on_click=do_check_update),
                update_status,
            ]
        ),
    )
    mark_startup_ok()
