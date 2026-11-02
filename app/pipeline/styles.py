"""成片类型（template / style）：驱动切镜密度、字幕样式、默认配乐音量。

规则优先读 assets/templates_hot/styles.json（热更新），否则用内置默认。
ids: factory / reverse_hook / seed / explainer
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

TemplateTypeId = Literal["factory", "reverse_hook", "seed", "explainer"]

TEMPLATE_TYPE_IDS: tuple[str, ...] = ("factory", "reverse_hook", "seed", "explainer")

_ROOT = Path(__file__).resolve().parents[2]
_HOT_STYLES = _ROOT / "assets" / "templates_hot" / "styles.json"


@dataclass(frozen=True)
class RemixStyle:
    id: str
    label_zh: str
    tip: str
    piece_sec: float
    region_bias: float
    max_cuts: int
    hook_sec: float
    subtitle_fontsize: int
    subtitle_margin_v: int
    bgm_volume_default: float


_BUILTIN: dict[str, RemixStyle] = {
    "factory": RemixStyle(
        id="factory",
        label_zh="工厂实拍",
        tip="快切车间/仓库，前几秒出货画面",
        piece_sec=1.55,
        region_bias=0.08,
        max_cuts=14,
        hook_sec=2.0,
        subtitle_fontsize=18,
        subtitle_margin_v=48,
        bgm_volume_default=0.22,
    ),
    "reverse_hook": RemixStyle(
        id="reverse_hook",
        label_zh="反向钩子",
        tip="先反常识/避雷，再给解法；首镜稍长",
        piece_sec=1.75,
        region_bias=0.18,
        max_cuts=12,
        hook_sec=3.2,
        subtitle_fontsize=20,
        subtitle_margin_v=52,
        bgm_volume_default=0.18,
    ),
    "seed": RemixStyle(
        id="seed",
        label_zh="种草",
        tip="成果特写多、切得更密、强 CTA",
        piece_sec=1.35,
        region_bias=0.55,
        max_cuts=16,
        hook_sec=2.2,
        subtitle_fontsize=22,
        subtitle_margin_v=56,
        bgm_volume_default=0.26,
    ),
    "explainer": RemixStyle(
        id="explainer",
        label_zh="知识科普",
        tip="切镜偏慢、字幕更大、配乐压低保解说",
        piece_sec=3.2,
        region_bias=0.22,
        max_cuts=6,
        hook_sec=2.8,
        subtitle_fontsize=26,
        subtitle_margin_v=64,
        bgm_volume_default=0.12,
    ),
}


def _style_from_dict(sid: str, raw: dict) -> RemixStyle:
    base = _BUILTIN.get(sid)
    return RemixStyle(
        id=sid,
        label_zh=str(raw.get("label_zh") or (base.label_zh if base else sid)),
        tip=str(raw.get("tip") or (base.tip if base else "")),
        piece_sec=float(raw.get("piece_sec", base.piece_sec if base else 2.0)),
        region_bias=float(raw.get("region_bias", base.region_bias if base else 0.1)),
        max_cuts=int(raw.get("max_cuts", base.max_cuts if base else 12)),
        hook_sec=float(raw.get("hook_sec", base.hook_sec if base else 2.0)),
        subtitle_fontsize=int(
            raw.get("subtitle_fontsize", base.subtitle_fontsize if base else 18)
        ),
        subtitle_margin_v=int(
            raw.get("subtitle_margin_v", base.subtitle_margin_v if base else 48)
        ),
        bgm_volume_default=float(
            raw.get("bgm_volume_default", base.bgm_volume_default if base else 0.22)
        ),
    )


def load_styles(hot_path: Path | None = None) -> dict[str, RemixStyle]:
    """Load styles; file override if present else builtins. Unknown ids ignored."""
    out = dict(_BUILTIN)
    path = Path(hot_path) if hot_path is not None else _HOT_STYLES
    if not path.is_file():
        return out
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    block = data.get("styles") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        return out
    for sid, raw in block.items():
        if sid not in TEMPLATE_TYPE_IDS or not isinstance(raw, dict):
            continue
        out[sid] = _style_from_dict(sid, raw)
    return out


def get_style(template_type: str | None = None, *, hot_path: Path | None = None) -> RemixStyle:
    styles = load_styles(hot_path)
    key = (template_type or "factory").strip() or "factory"
    if key not in styles:
        # alias: older brief used "edu"
        if key == "edu" and "explainer" in styles:
            return styles["explainer"]
        return styles["factory"]
    return styles[key]


def style_options() -> list[tuple[str, str]]:
    """(id, Chinese label) for UI dropdown, stable order."""
    styles = load_styles()
    return [(sid, styles[sid].label_zh) for sid in TEMPLATE_TYPE_IDS if sid in styles]


def piece_sec_for_duration(style: RemixStyle, target_sec: int) -> float:
    """Light duration scaling around style.piece_sec (keep philosophy; don't erase type gap)."""
    base = float(style.piece_sec)
    # 10s slightly shorter bites, 30s slightly longer — small nudge only
    if target_sec <= 10:
        return max(0.9, base * 0.92)
    if target_sec >= 30:
        return base * 1.12
    return base
