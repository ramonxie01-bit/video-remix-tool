"""Packaging contract: frozen Windows builds must ship flet-desktop offline."""
from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _bundle():
    path = ROOT / "packaging" / "flet_desktop_bundle.py"
    spec = importlib.util.spec_from_file_location("flet_desktop_bundle", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_requirements_pin_flet_and_desktop_together():
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "flet==0.86.5" in text
    assert "flet-desktop==0.86.5" in text


def test_spec_packs_client_zip_and_hides_flet_desktop():
    spec = (ROOT / "packaging" / "remix.spec").read_text(encoding="utf-8")
    assert "flet_desktop" in spec
    assert "flet-windows.zip" in spec
    assert "flet_desktop.version" in spec
    assert "ctypes.util" in spec


def test_windows_client_url_matches_release_asset():
    mod = _bundle()
    assert (
        mod.windows_client_url("0.86.5")
        == "https://github.com/flet-dev/flet/releases/download/v0.86.5/flet-windows.zip"
    )
    assert mod.windows_client_url("v0.86.5").endswith("/v0.86.5/flet-windows.zip")


def test_assert_windows_client_zip_requires_flet_exe(tmp_path: Path):
    mod = _bundle()
    good = tmp_path / "flet-windows.zip"
    with zipfile.ZipFile(good, "w") as zf:
        zf.writestr("flet/flet.exe", b"MZ")
        zf.writestr("flet/vcruntime140.dll", b"dll")
    mod.assert_windows_client_zip(good)

    bad = tmp_path / "empty.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("readme.txt", "no client")
    with pytest.raises(SystemExit):
        mod.assert_windows_client_zip(bad)


def test_verify_script_does_not_use_cp1252_print_for_dist_path():
    text = (ROOT / "packaging" / "verify_windows_dist.py").read_text(encoding="utf-8")
    assert "buffer.write" in text
    assert "Bundled client zip" in text
    # The dist folder name is not ASCII. print() on a cp1252 GitHub runner
    # raised UnicodeEncodeError before the frozen-module check ran.
    assert "print(f\"Bundled client zip:" not in text


def test_version_is_0_3_1():
    version = (ROOT / "assets" / "version.json").read_text(encoding="utf-8")
    assert '"version": "0.3.1"' in version
