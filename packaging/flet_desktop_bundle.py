"""Shared checks for the offline Flet Windows desktop client archive.

Flet 0.86 splits the desktop runtime in two:

* ``flet-desktop`` is a small Python package. ``flet`` does not depend on it.
  At startup ``ensure_flet_desktop_package_installed()`` imports
  ``flet_desktop.version`` and, on any failure, runs ``pip install`` and then
  ``exit(1)``. PyInstaller does not provide the ``site`` builtin ``exit``, so a
  frozen app dies with ``NameError: name 'exit' is not defined``.
* Native binaries are not in the wheel. ``flet_desktop.ensure_client_cached()``
  looks for ``flet_desktop/app/flet-windows.zip`` and only then downloads from
  GitHub. Packing that zip next to the package is what keeps first launch
  offline.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENT_DIR = ROOT / "packaging" / ".flet_client"
CLIENT_ZIP = CLIENT_DIR / "flet-windows.zip"
# Destination inside the PyInstaller onedir folder (_MEIPASS / this path).
BUNDLE_DEST = "flet_desktop/app"
EXPECTED_MEMBER = "flet/flet.exe"


def windows_client_url(version: str) -> str:
    ver = version.strip().lstrip("v")
    if not ver:
        raise ValueError("empty flet version")
    return f"https://github.com/flet-dev/flet/releases/download/v{ver}/flet-windows.zip"


def installed_flet_desktop_version() -> str:
    """Return the installed flet-desktop version, or exit if it mismatches flet."""
    import flet.version as flet_version
    import flet_desktop.version as desktop_version

    sdk = str(flet_version.flet_version)
    desk = str(desktop_version.version)
    if sdk != desk:
        raise SystemExit(
            f"flet {sdk} and flet-desktop {desk} differ. "
            "Pin both to the same version in requirements.txt."
        )
    return desk


def assert_windows_client_zip(path: Path) -> None:
    path = Path(path)
    if not path.is_file():
        raise SystemExit(
            f"Missing {path}. Run: python packaging/fetch_flet_desktop_client.py"
        )
    if not zipfile.is_zipfile(path):
        raise SystemExit(f"{path} is not a zip archive")
    with zipfile.ZipFile(path) as zf:
        names = {name.replace("\\", "/") for name in zf.namelist()}
    if EXPECTED_MEMBER not in names:
        sample = ", ".join(sorted(names)[:8])
        raise SystemExit(
            f"{path} does not contain {EXPECTED_MEMBER} (sample: {sample})"
        )
