# 社媒视频混剪工具（Windows 优先）

轻量本地桌面软件：导入多段素材 → 自动出 10s / 15s / 30s 竖屏混剪（烧录字幕 + TTS 配音）。

## Tech stack
- Python 3.11
- Flet（UI）
- ffmpeg（内嵌静态包）
- faster-whisper（字幕 ASR / 可选；文案也可外部生成）
- edge-tts（配音）
- PyInstaller（Windows 安装包 / 便携目录）

## MVP 模块
| 模块 | 函数 | 说明 |
|------|------|------|
| ingest | `ingest(paths) -> list[MediaItem]` | 导入素材清单 |
| scenes | `detect_scenes(video) -> list[Scene]` | 镜头时间戳 |
| highlights | `pick_highlights(scenes, target_sec) -> list[Clip]` | 抽高光段 |
| script | `gen_script` / `resolve_script` / `load_script_file` | 内置模板或导入文案 |
| tts | `tts(script, voice) -> Path` | 配音 wav |
| compose | `compose(clips, srt, audio, duration) -> Path` | 合成竖屏 mp4 |
| export | `export_job(cfg) -> list[Path]` | 导出成片 |

## 文案导入 / 配乐 / 检查更新
- **素材**：UI「选择素材文件夹」或「导入视频文件」（多选 mp4 / mov / mkv / avi / m4v / webm）。两种来源互斥；选完后状态栏显示有效数 / 扫描数。probe 失败会跳过，并写出文件名和原因。
- **文案**：内容 bot 出完整口播稿 → UI「口播文案（粘贴）」或「导入文案」(.txt / .srt) → 同一稿烧录字幕。文案为空或 srt 无字幕时直接报错。配音（edge-tts）失败时仍导出烧录字幕的无声成片。
- **配乐**：明显的「导入配乐」按钮，选本地 mp3 / wav / m4a（`JobConfig.bgm_path`）。
- **更新**：`assets/version.json` +「检查更新」（读 `REMIX_UPDATE_URL` 或占位 URL）；离线不挡剪辑。模板热更新包见 `apply_hot_pack()` 骨架。

## 本地开发
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# Linux/mac:
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## 测试
```bash
pip install pytest
pytest tests/ -q
```

## 版本
当前部门版 **0.3.4**（`assets/version.json`）：文件对话框没有返回路径时会写明原因；ffprobe 失败会带上原始报错；口播文案烧录中文字幕（Noto Sans SC / 微软雅黑）；没有网络时跳过配音仍出字幕。请整包解压到 `C:\remix\`，说明见 `docs/同事使用说明.txt`。Flet 0.86 的 `FilePicker` 仍不接受 `on_result`。

## 打包（Windows）
见 `packaging/BUILD_WINDOWS.md`。摘要：在 Windows 或 GitHub Actions `windows-latest` 上执行 `packaging/build_windows.ps1`；ffmpeg 随包内嵌，Whisper 模型首次下载缓存。Linux 主机只能做源码交付 zip，不能产出 Windows exe。
