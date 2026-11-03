"""Bundled local version helpers."""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_VERSION_FILE = _ROOT / "assets" / "version.json"
_FALLBACK = {"version": "0.3.3", "channel": "dept", "notes": ""}


def version_file() -> Path:
    return _VERSION_FILE


def load_local_version() -> dict:
    try:
        data = json.loads(_VERSION_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("version"):
            return data
    except Exception:
        pass
    return dict(_FALLBACK)


LOCAL_VERSION: str = str(load_local_version().get("version", "0.3.3"))
