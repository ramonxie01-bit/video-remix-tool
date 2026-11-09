# Windows 打包说明（部门版 v0.3.4）

本机是 Linux 时 **不能** 产出可用的 Windows `.exe`。请在 **Windows x64** 或 **GitHub Actions `windows-latest`** 上打包。

## 一键（推荐：同事 Windows 构建机）

1. 解压 `remix_tool_windows_pack_v0.3.4.zip` 到任意目录。
2. 放入 ffmpeg（二选一）:
   - 手动：把 `ffmpeg.exe` / `ffprobe.exe` 放到 `assets\ffmpeg\`（见该目录 README）
   - 或跳过手动，直接用 CI workflow 里的下载步骤
3. 安装 Python 3.11+（勾选 Add to PATH）。
4. 可选：安装 [Inno Setup 6](https://jrsoftware.org/isinfo.php) 或 `choco install innosetup -y`（用于 Setup.exe）。
5. 在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

6. 产物：
   - 便携目录：`dist\社媒视频混剪\`
   - 安装包（有 Inno 时）：`deliver_win\社媒视频混剪_Setup_v0.3.4.exe`（缺语言文件时仍生成英文安装包，失败也不影响便携目录）

仅要便携目录、跳过安装包：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -SkipInno
```

## GitHub Actions（Ramon 已确认「走 CI」）

工作流文件：`.github/workflows/windows-build.yml`

- runner：`windows-latest`
- 自动下载 win64 ffmpeg 静态包到 `assets/ffmpeg`
- `pip install` + PyInstaller `packaging/remix.spec`
- 尝试 `choco install innosetup` 后跑 ISCC；失败则仍上传便携 zip
- 上传 artifact：`windows-remix-dist`（含 dist 与 Setup.exe 若生成）

推送到默认分支或手动 **workflow_dispatch** 即可触发。  
**本仓库若尚未 push：** 由有权限的同事用 GitHub 连接推送；构建机 / bot 不要强行 `gh auth`。

## 版本

- `assets/version.json` → `0.3.4`
- 便携包文件名：`remix_tool_portable_v0.3.4.zip`
- `requirements.txt` 固定 `flet==0.86.5` 与 `flet-desktop==0.86.5`。打包前 `packaging/fetch_flet_desktop_client.py` 下载对应的 `flet-windows.zip`，`remix.spec` 把它放进 `flet_desktop/app/`。冻结程序因此能 import `flet_desktop`，并离线解压桌面客户端，不会再走 `pip install flet-desktop` / `exit(1)`。
- 成片类型：`assets/templates_hot/styles.json`（factory / reverse_hook / seed / explainer）随包打入

## 注意

- Linux 上跑 PyInstaller 只会得到 **linux-smoke** 产物，**不可分发给 Windows 同事**。
- Whisper 模型仍按设计首次运行下载到 `%LOCALAPPDATA%\video-remix\models`（可选）。
