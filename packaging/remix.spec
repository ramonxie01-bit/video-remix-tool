# -*- mode: python ; coding: utf-8 -*-
# Windows PyInstaller spec for 社媒视频混剪部门版.
# Run from repo root on Windows:  pyinstaller packaging/remix.spec
# Or:  powershell -File packaging/build_windows.ps1
#
# flet-desktop is not part of the flet wheel. This spec packs the package and
# packaging/.flet_client/flet-windows.zip into flet_desktop/app so the frozen
# app imports flet_desktop and extracts the client offline (no pip, no GitHub).

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

sys.path.insert(0, str(Path(SPECPATH).resolve()))
from flet_desktop_bundle import BUNDLE_DEST, CLIENT_ZIP, assert_windows_client_zip

block_cipher = None
ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "assets" / "ffmpeg"), "assets/ffmpeg"),
    (str(ROOT / "assets" / "version.json"), "assets"),
    (str(ROOT / "assets" / "templates_hot"), "assets/templates_hot"),
    (str(ROOT / "hot_update"), "hot_update"),
    (str(ROOT / "notices"), "notices"),
]
font_dir = ROOT / "assets" / "fonts"
if font_dir.is_dir() and any(p.is_file() for p in font_dir.iterdir()):
    # Noto Sans SC for libass FontName. UPX must not rewrite the otf.
    datas.append((str(font_dir), "assets/fonts"))

binaries = []
hiddenimports = [
    "flet",
    "flet_desktop",
    "flet_desktop.version",
    "ctypes.util",
    "rich",
    "rich.progress",
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

# flet-desktop must be present. collect_all("flet") does not pull it in,
# and a missing import makes the frozen app call pip then exit().
for pkg in ("flet", "flet_desktop", "rich"):
    pkg_datas, pkg_bins, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_bins
    hiddenimports += pkg_hidden

for pkg in ("edge_tts", "faster_whisper", "ctranslate2"):
    try:
        pkg_datas, pkg_bins, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_bins
        hiddenimports += pkg_hidden
    except Exception:
        pass

# Icon fonts used by ft.Icons. Missing files degrade icons; they must not
# block the desktop client bundle.
for icon_pkg, icon_name in (
    ("flet.controls.material", "icons.json"),
    ("flet.controls.cupertino", "cupertino_icons.json"),
):
    try:
        datas += collect_data_files(icon_pkg, includes=[icon_name])
    except Exception:
        pass

assert_windows_client_zip(CLIENT_ZIP)
datas.append((str(CLIENT_ZIP), BUNDLE_DEST))

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
    runtime_hooks=[str(ROOT / "packaging" / "pyi_rth_crashlog.py")],
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
    upx_exclude=["flet-windows.zip", "NotoSansSC-Regular.otf"],
    name="社媒视频混剪",
)
