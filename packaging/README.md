# Windows 打包

完整步骤见 **[BUILD_WINDOWS.md](./BUILD_WINDOWS.md)**。

摘要：
1. 将 `ffmpeg.exe` / `ffprobe.exe` 放入 `assets/ffmpeg/`（或走 CI 自动下载）。
2. `powershell -File packaging\build_windows.ps1`
3. 便携目录：`dist/社媒视频混剪/`；安装包：`deliver_win/社媒视频混剪_Setup_v0.3.0.exe`（需 Inno Setup 6）。

CI：`.github/workflows/windows-build.yml`（windows-latest）。
