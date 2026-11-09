"""Write plan.json, slot JPEGs, and review.html under out_dir/_review."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.models import Clip
from app.review.board import render_review_html, write_csv
from app.review.slots import assign_slot_ids, piece_id_for
from app.review.thumbs import grab_jpeg

REVIEW_DIRNAME = "_review"
NOTES_NAME = "review_notes.json"
PLAN_NAME = "plan.json"

# Shown in plan.json and the colleague guide. Next export reads this file.
REVIEW_APPLY_NOTE = (
    "下次对同一输出目录生成时：review_notes.json 里的 disabled_slots "
    "会尽量避开对应源时间段（只用真实镜头，不编造素材；素材不够时仍用剩余镜头）。"
    "enabled 为 false 仍会重新导出该 mp4，plan.json 里保持未启用。"
)


@dataclass
class ReviewPack:
    plan_path: Path
    html_path: Path
    notes_path: Path
    thumbs_ok: int = 0
    thumbs_failed: int = 0


def review_dir(out_dir: Path) -> Path:
    return Path(out_dir) / REVIEW_DIRNAME


def plan_path_for(out_dir: Path) -> Path:
    return review_dir(out_dir) / PLAN_NAME


def notes_path_for(out_dir: Path) -> Path:
    return review_dir(out_dir) / NOTES_NAME


def empty_notes() -> dict:
    return {"version": 1, "pieces": {}}


def read_notes(path: Path) -> dict:
    if not path.is_file():
        return empty_notes()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_notes()
    if not isinstance(data, dict):
        return empty_notes()
    pieces = data.get("pieces")
    if not isinstance(pieces, dict):
        pieces = {}
    return {"version": 1, "pieces": pieces}


def sanitize_notes(payload: dict) -> dict:
    """Keep enabled / note / copy / disabled_slots. Drop anything else."""
    raw = payload.get("pieces") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        raw = {}
    pieces: dict = {}
    for pid, meta in raw.items():
        if not isinstance(pid, str) or not isinstance(meta, dict):
            continue
        disabled = meta.get("disabled_slots") or []
        if not isinstance(disabled, list):
            disabled = []
        pieces[pid] = {
            "enabled": bool(meta.get("enabled", True)),
            "note": str(meta.get("note") or ""),
            "copy": str(meta.get("copy") or ""),
            "disabled_slots": [str(item) for item in disabled if str(item)],
        }
    return {"version": 1, "pieces": pieces}


def write_notes(path: Path, notes: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = sanitize_notes(notes)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _rel(path: Path, start: Path) -> str:
    try:
        rel = os.path.relpath(Path(path), Path(start))
    except ValueError:
        rel = str(path)
    return Path(rel).as_posix()


def _find_piece(plan: dict, *, theme: str, duration_sec: int) -> dict | None:
    want_id = piece_id_for(theme, duration_sec)
    fallback = None
    for piece in plan.get("pieces") or []:
        if not isinstance(piece, dict):
            continue
        if piece.get("id") == want_id:
            return piece
        try:
            same_dur = int(piece.get("duration_sec") or 0) == int(duration_sec)
        except (TypeError, ValueError):
            same_dur = False
        if piece.get("theme") == theme and same_dur:
            fallback = piece
    return fallback


def exclusion_ranges(
    out_dir: Path, *, theme: str, duration_sec: int
) -> list[tuple[Path, float, float]]:
    """Source ranges the last review marked 不用… for this theme and duration.

    Missing files yield an empty list. Callers still export from real footage.
    """
    plan_file = plan_path_for(out_dir)
    notes_file = notes_path_for(out_dir)
    if not plan_file.is_file() or not notes_file.is_file():
        return []
    try:
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
        notes = read_notes(notes_file)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(plan, dict):
        return []
    piece = _find_piece(plan, theme=theme, duration_sec=duration_sec)
    if not piece:
        return []
    meta = (notes.get("pieces") or {}).get(piece.get("id")) or {}
    if not isinstance(meta, dict):
        return []
    disabled = {str(item) for item in (meta.get("disabled_slots") or [])}
    if not disabled:
        return []
    ranges: list[tuple[Path, float, float]] = []
    for slot in piece.get("slots") or []:
        if not isinstance(slot, dict):
            continue
        if str(slot.get("slot_id") or "") not in disabled:
            continue
        src = slot.get("source_file")
        if not src:
            continue
        try:
            start = float(slot.get("start_sec"))
            end = float(slot.get("end_sec"))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        ranges.append((Path(str(src)), start, end))
    return ranges


def merge_notes_into_plan(plan_file: Path, notes: dict) -> None:
    """Copy enabled / copy from notes into plan.json. Leaves slots' sources alone."""
    if not plan_file.is_file():
        return
    try:
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(plan, dict):
        return
    pieces_meta = notes.get("pieces") or {}
    changed = False
    for piece in plan.get("pieces") or []:
        if not isinstance(piece, dict):
            continue
        meta = pieces_meta.get(piece.get("id")) or {}
        if not isinstance(meta, dict):
            continue
        if "enabled" in meta:
            new_v = bool(meta.get("enabled"))
            if piece.get("enabled", True) != new_v:
                piece["enabled"] = new_v
                changed = True
        if "copy" in meta:
            new_c = meta.get("copy") or ""
            if piece.get("copy", "") != new_c:
                piece["copy"] = new_c
                changed = True
    if changed:
        plan_file.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def _build_piece(
    review: Path,
    *,
    theme: str,
    style_id: str,
    spec: dict,
    notes: dict,
) -> tuple[dict, int, int]:
    duration = int(spec["duration_sec"])
    pid = piece_id_for(theme, duration)
    meta = (notes.get("pieces") or {}).get(pid) or {}
    if not isinstance(meta, dict):
        meta = {}
    output_path = Path(spec["output_path"])
    clips: list[Clip] = list(spec.get("clips") or [])
    slot_ids = assign_slot_ids(style_id, len(clips))
    ok = fail = 0
    slots: list[dict] = []
    for clip, sid in zip(clips, slot_ids):
        length = max(0.0, float(clip.end) - float(clip.start))
        thumb_rel = f"thumbs/{pid}_{sid}.jpg"
        mid = float(clip.start) + length / 2.0
        if grab_jpeg(Path(clip.source), mid, review / thumb_rel):
            ok += 1
        else:
            fail += 1
        slots.append(
            {
                "slot_id": sid,
                "source_file": str(clip.source),
                "start_sec": round(float(clip.start), 3),
                "end_sec": round(float(clip.end), 3),
                "duration_sec": round(length, 3),
                "clip_file": thumb_rel,
            }
        )
    final_rel = f"thumbs/{pid}_final.jpg"
    if output_path.is_file() and grab_jpeg(output_path, 0.4, review / final_rel):
        ok += 1
    else:
        fail += 1
        final_rel = ""
    enabled = bool(meta["enabled"]) if "enabled" in meta else True
    return (
        {
            "id": pid,
            "theme": theme,
            "enabled": enabled,
            "copy": spec.get("copy") or "",
            "duration_sec": duration,
            "output_file": _rel(output_path, review),
            "final_thumb": final_rel,
            "slots": slots,
        },
        ok,
        fail,
    )


def write_review_bundle(
    out_dir: Path,
    *,
    style_id: str,
    theme: str,
    pieces: list[dict],
) -> ReviewPack:
    """Write the board for clips that were actually composed.

    Each piece dict needs duration_sec, output_path, clips, and copy.
    Existing review_notes.json is kept. enabled from notes is copied onto the plan.
    """
    out_dir = Path(out_dir)
    review = review_dir(out_dir)
    review.mkdir(parents=True, exist_ok=True)
    thumbs = review / "thumbs"
    thumbs.mkdir(exist_ok=True)
    for old in thumbs.glob("*.jpg"):
        try:
            old.unlink()
        except OSError:
            pass
    notes = read_notes(notes_path_for(out_dir))
    built: list[dict] = []
    ok = fail = 0
    for spec in pieces:
        piece, piece_ok, piece_fail = _build_piece(
            review, theme=theme, style_id=style_id, spec=spec, notes=notes
        )
        built.append(piece)
        ok += piece_ok
        fail += piece_fail
    plan = {
        "version": 1,
        "style_id": style_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "review_apply": REVIEW_APPLY_NOTE,
        "pieces": built,
    }
    plan_file = review / PLAN_NAME
    plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path = review / "review.html"
    html_path.write_text(render_review_html(plan, notes, review), encoding="utf-8")
    write_csv(review / "审片清单.csv", plan, notes)
    return ReviewPack(
        plan_path=plan_file,
        html_path=html_path,
        notes_path=notes_path_for(out_dir),
        thumbs_ok=ok,
        thumbs_failed=fail,
    )
