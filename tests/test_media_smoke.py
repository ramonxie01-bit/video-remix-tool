"""Real mp4/mov containers are counted by ingest (not a mocked probe)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_smoke():
    path = ROOT / "scripts" / "smoke_import_media.py"
    spec = importlib.util.spec_from_file_location("smoke_import_media", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ingest_counts_real_mp4_and_mov():
    mod = _load_smoke()
    try:
        code = mod.main()
    except SystemExit as exc:
        pytest.fail(str(exc))
    assert code == 0
