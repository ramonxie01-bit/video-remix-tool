#!/usr/bin/env python3
"""Internal smoke: 4 template types × 15s → metrics.json (not a user deliverable)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models import JobConfig  # noqa: E402
from app.pipeline.export import export_job  # noqa: E402
from app.pipeline.highlights import pick_highlights  # noqa: E402
from app.pipeline.ingest import ingest  # noqa: E402
from app.pipeline.scenes import detect_scenes  # noqa: E402
from app.pipeline.styles import TEMPLATE_TYPE_IDS, get_style  # noqa: E402

SAMPLES = ROOT / "samples"
SKELETON = Path("/workspace/remix-sample-clips/templates_4types_10_15_30.txt")
OUT = ROOT / "out_type_verify"


def extract_type_duration(raw: str, type_id: str, dur: int) -> str:
    raw = raw.replace("\r\n", "\n")
    # Split on ===== ... id =====
    parts = re.split(r"(?m)^=====\s*.*?\b(\w+)\s*=====\s*$", raw)
    # parts: [preamble, id1, body1, id2, body2, ...]
    bodies: dict[str, str] = {}
    i = 1
    while i + 1 < len(parts):
        bodies[parts[i].strip()] = parts[i + 1]
        i += 2
    # alias
    key = type_id
    if key not in bodies and key == "edu":
        key = "explainer"
    body = bodies.get(key) or bodies.get(type_id) or raw
    # duration section
    m = re.search(rf"(?m)^##\s*{dur}s\s*$", body)
    if not m:
        return body.strip()
    start = m.end()
    m2 = re.search(r"(?m)^##\s*\d+s\s*$", body[start:])
    end = start + m2.start() if m2 else len(body)
    return body[start:end].strip()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not SAMPLES.is_dir():
        print("no samples", file=sys.stderr)
        return 1
    raw = SKELETON.read_text(encoding="utf-8") if SKELETON.is_file() else ""
    items = ingest([SAMPLES])
    scenes = []
    for it in items:
        scenes.extend(detect_scenes(it.path))

    metrics: dict = {"target_sec": 15, "types": {}}
    for tid in TEMPLATE_TYPE_IDS:
        style = get_style(tid)
        clips = pick_highlights(scenes, 15, style=style)
        mean_clip = (
            sum(c.end - c.start for c in clips) / len(clips) if clips else 0.0
        )
        script_text = extract_type_duration(raw, tid, 15) if raw else "钩子\n正文"
        if not (script_text or "").strip():
            script_text = "钩子\n正文"
        sub = OUT / tid
        if sub.exists():
            # wipe old remix only
            for old in sub.glob("remix_*.mp4"):
                old.unlink(missing_ok=True)
        cfg = JobConfig(
            inputs=[SAMPLES],
            out_dir=sub,
            durations=[15],
            voice="female_narration",
            bgm_path=None,
            bgm_volume=None,
            script_text=script_text,
            template_type=tid,
        )
        outs = export_job(cfg)
        metrics["types"][tid] = {
            "n_clips": len(clips),
            "mean_clip_sec": round(mean_clip, 3),
            "bgm_volume": style.bgm_volume_default,
            "fontsize": style.subtitle_fontsize,
            "margin_v": style.subtitle_margin_v,
            "piece_sec": style.piece_sec,
            "region_bias": style.region_bias,
            "hook_sec": style.hook_sec,
            "max_cuts": style.max_cuts,
            "outputs": [str(p) for p in outs],
            "script_preview": (script_text or "")[:80],
        }
        print(tid, metrics["types"][tid]["n_clips"], metrics["types"][tid]["mean_clip_sec"])

    fac = metrics["types"]["factory"]
    seed = metrics["types"]["seed"]
    exp = metrics["types"]["explainer"]
    ok = (
        exp["n_clips"] < fac["n_clips"]
        and exp["n_clips"] < seed["n_clips"]
        and exp["mean_clip_sec"] > fac["mean_clip_sec"]
        and exp["mean_clip_sec"] > seed["mean_clip_sec"]
        and exp["bgm_volume"] < fac["bgm_volume"]
        and exp["fontsize"] > fac["fontsize"]
    )
    metrics["assert_explainer_slower_than_factory_seed"] = bool(ok)
    (OUT / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("metrics →", OUT / "metrics.json", "OK" if ok else "FAIL")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
