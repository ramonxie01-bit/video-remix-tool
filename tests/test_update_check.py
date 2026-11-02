"""Update check skeleton — offline / no network required for local bits."""
from __future__ import annotations

import zipfile
from pathlib import Path

from app.services.update_check import (
    LOCAL_VERSION,
    apply_hot_pack,
    check_update,
)
from app.version import load_local_version


def test_local_version_loaded():
    meta = load_local_version()
    assert meta["version"]
    assert LOCAL_VERSION == meta["version"]


def test_check_update_offline_friendly():
    # default URL is example.invalid → must not raise, report offline
    info = check_update()
    assert info.local == LOCAL_VERSION
    assert info.has_update is False
    assert info.offline or info.error
    assert "离线" in (info.notes or "") or info.error


def test_apply_hot_pack(tmp_path: Path):
    zpath = tmp_path / "pack.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("templates/demo.txt", "hello")
    result = apply_hot_pack(zpath)
    assert result["ok"] is True
    assert any("demo.txt" in m for m in result["members"])
    assert result["extract_dir"]
    assert Path(result["extract_dir"]).exists()


def test_apply_hot_pack_missing():
    result = apply_hot_pack("/tmp/does-not-exist-remix-hot.zip")
    assert result["ok"] is False
    assert result["error"]
