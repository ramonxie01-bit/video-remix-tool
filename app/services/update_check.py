"""Offline-friendly update check skeleton (whole package + template hot pack)."""
from __future__ import annotations

import json
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.version import LOCAL_VERSION, load_local_version, version_file

DEFAULT_UPDATE_URL = "https://example.invalid/remix/version.json"
_ROOT = Path(__file__).resolve().parent.parent.parent
HOT_DIRS = (
    _ROOT / "assets" / "templates_hot",
    _ROOT / "hot_update",
)


@dataclass
class UpdateInfo:
    local: str
    remote: str | None
    has_update: bool
    download_url: str | None = None
    notes: str = ""
    error: str | None = None
    offline: bool = False


def _parse_remote(payload: Any) -> tuple[str | None, str | None, str]:
    if not isinstance(payload, dict):
        return None, None, ""
    ver = payload.get("version")
    url = payload.get("download_url") or payload.get("url")
    notes = str(payload.get("notes") or "")
    return (str(ver) if ver else None), (str(url) if url else None), notes


def _version_tuple(v: str) -> tuple[int, ...]:
    parts: list[int] = []
    for bit in v.strip().lstrip("vV").split("."):
        try:
            parts.append(int(bit))
        except ValueError:
            parts.append(0)
    return tuple(parts) or (0,)


def check_update(url: str | None = None) -> UpdateInfo:
    """Fetch remote version.json. Network errors never raise — offline stays usable."""
    local_meta = load_local_version()
    local = str(local_meta.get("version") or LOCAL_VERSION)
    target = (url or os.environ.get("REMIX_UPDATE_URL") or DEFAULT_UPDATE_URL).strip()
    try:
        req = Request(target, headers={"User-Agent": "RemixTool/0.2"})
        with urlopen(req, timeout=4) as resp:  # noqa: S310 — dept URL / env override
            raw = resp.read().decode("utf-8", errors="replace")
        remote_ver, dl, notes = _parse_remote(json.loads(raw))
        if not remote_ver:
            return UpdateInfo(
                local=local,
                remote=None,
                has_update=False,
                notes=notes,
                error="远程 version.json 缺少 version 字段",
            )
        has = _version_tuple(remote_ver) > _version_tuple(local)
        return UpdateInfo(
            local=local,
            remote=remote_ver,
            has_update=has,
            download_url=dl,
            notes=notes or (f"发现新版本 {remote_ver}" if has else "已是最新"),
        )
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as ex:
        return UpdateInfo(
            local=local,
            remote=None,
            has_update=False,
            error=str(ex),
            offline=True,
            notes="离线可用，稍后再试",
        )


def apply_hot_pack(zip_path: Path | str) -> dict[str, Any]:
    """Validate a template hot-update zip; list members; safe-extract to hot_update/.

    Does not overwrite the main install tree. Future: merge into assets/templates_hot.
    """
    path = Path(zip_path)
    result: dict[str, Any] = {
        "ok": False,
        "path": str(path),
        "members": [],
        "extract_dir": None,
        "error": None,
    }
    if not path.is_file():
        result["error"] = "zip 不存在"
        return result
    if path.suffix.lower() != ".zip":
        result["error"] = "需要 .zip 热更新包"
        return result
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            # reject path traversal
            for name in names:
                if name.startswith("/") or ".." in Path(name).parts:
                    result["error"] = f"不安全路径: {name}"
                    return result
            result["members"] = names
            dest = _ROOT / "hot_update" / path.stem
            dest.mkdir(parents=True, exist_ok=True)
            zf.extractall(dest)
            result["extract_dir"] = str(dest)
            result["ok"] = True
    except zipfile.BadZipFile as ex:
        result["error"] = f"损坏的 zip: {ex}"
    except OSError as ex:
        result["error"] = str(ex)
    return result


def hot_pack_dirs() -> list[Path]:
    """Stub: directories that may hold future template packs."""
    return [p for p in HOT_DIRS if p.exists()]


# re-export for UI convenience
__all__ = [
    "UpdateInfo",
    "LOCAL_VERSION",
    "check_update",
    "apply_hot_pack",
    "hot_pack_dirs",
    "version_file",
    "DEFAULT_UPDATE_URL",
]
