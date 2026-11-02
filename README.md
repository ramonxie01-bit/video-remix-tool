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
- **文案**：内容 bot 出完整口播稿 → UI「口播文案（粘贴）」或「导入文案」(.txt / .srt) → 同一稿驱动 **字幕 + TTS**。空文案时仍走内置模板。
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
当前部门版 **0.3.2**（`assets/version.json`）：Flet 0.86 的 `FilePicker` 不再接受 `on_result`，素材文件夹、导入文案、导入配乐改为等待 `get_directory_path()` / `pick_files()` 的返回值。Windows 便携包仍内置 flet-desktop 与桌面客户端，离线启动不再 pip install。

## 打包（Windows）
见 `packaging/BUILD_WINDOWS.md`。摘要：在 Windows 或 GitHub Actions `windows-latest` 上执行 `packaging/build_windows.ps1`；ffmpeg 随包内嵌，Whisper 模型首次下载缓存。Linux 主机只能做源码交付 zip，不能产出 Windows exe。
