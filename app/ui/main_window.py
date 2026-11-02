from __future__ import annotations

from pathlib import Path

import flet as ft

from app.models import JobConfig
from app.pipeline.export import export_job
from app.pipeline.styles import get_style, style_options
from app.services.update_check import LOCAL_VERSION, check_update


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

    def on_folder(e: ft.FilePickerResultEvent) -> None:
        if e.path:
            picked.clear()
            picked.append(e.path)
            picked_label.value = e.path
            page.update()

    def on_script_file(e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        f = e.files[0]
        path = Path(f.path) if f.path else None
        if path is None or not path.is_file():
            status.value = "无法读取文案文件"
            page.update()
            return
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except OSError as ex:
            status.value = f"读文案失败：{ex}"
            page.update()
            return
        script_field.value = raw
        script_path_held[0] = path
        status.value = f"已导入文案：{path.name}"
        page.update()

    def on_bgm_file(e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        f = e.files[0]
        path = f.path
        if not path:
            status.value = "无法读取配乐文件"
            page.update()
            return
        bgm_field.value = path
        status.value = f"已选配乐：{Path(path).name}"
        page.update()

    folder_picker = ft.FilePicker(on_result=on_folder)
    script_picker = ft.FilePicker(on_result=on_script_file)
    bgm_picker = ft.FilePicker(on_result=on_bgm_file)
    page.overlay.extend([folder_picker, script_picker, bgm_picker])

    def do_export(_e: ft.ControlEvent) -> None:
        if not picked:
            status.value = "请先选择素材文件夹"
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
            inputs=[Path(picked[0])],
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
                    on_click=lambda _: folder_picker.get_directory_path(),
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
            on_click=lambda _: script_picker.pick_files(
                allow_multiple=False,
                allowed_extensions=["txt", "srt"],
                dialog_title="选择口播文案 (.txt / .srt)",
            ),
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
                    on_click=lambda _: bgm_picker.pick_files(
                        allow_multiple=False,
                        allowed_extensions=["mp3", "wav", "m4a"],
                        dialog_title="选择配乐文件",
                    ),
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
