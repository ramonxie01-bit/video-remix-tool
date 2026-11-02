# -*- mode: python ; coding: utf-8 -*-
# Windows PyInstaller spec for 社媒视频混剪部门版.
# Run from repo root on Windows:  pyinstaller packaging/remix.spec
# Or:  powershell -File packaging/build_windows.ps1

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "assets" / "ffmpeg"), "assets/ffmpeg"),
    (str(ROOT / "assets" / "version.json"), "assets"),
    (str(ROOT / "assets" / "templates_hot"), "assets/templates_hot"),
    (str(ROOT / "hot_update"), "hot_update"),
    (str(ROOT / "notices"), "notices"),
]

binaries = []
hiddenimports = [
    "flet",
    "edge_tts",
    "aiohttp",
    "numpy",
    "cv2",
    "app",
    "app.main",
    "app.models",
    "app.version",
    "app.ui",
    "app.ui.main_window",
    "app.pipeline",
    "app.pipeline.ingest",
    "app.pipeline.scenes",
    "app.pipeline.highlights",
    "app.pipeline.script",
    "app.pipeline.tts",
    "app.pipeline.compose",
    "app.pipeline.export",
    "app.pipeline.styles",
    "app.pipeline.templates",
    "app.services",
    "app.services.ffmpeg",
    "app.services.update_check",
    "app.services.whisper_tiktok_adapter",
]

# Optional heavy deps — collect if installed so frozen app finds them
for pkg in ("flet", "edge_tts", "faster_whisper", "ctranslate2"):
    try:
        pkg_datas, pkg_bins, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_bins
        hiddenimports += pkg_hidden
    except Exception:
        pass

try:
    hiddenimports += collect_submodules("app")
except Exception:
    pass

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="社媒视频混剪",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="社媒视频混剪",
)
