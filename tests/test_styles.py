"""成片类型 styles: load JSON, pacing differs by type (no ffmpeg)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models import Scene
from app.pipeline.highlights import pick_highlights
from app.pipeline.styles import (
    TEMPLATE_TYPE_IDS,
    get_style,
    load_styles,
    piece_sec_for_duration,
)


def _fake_scenes(n_src: int = 3, n_per: int = 4) -> list[Scene]:
    scenes: list[Scene] = []
    for i in range(n_src):
        src = Path(f"/fake/src_{i}.mp4")
        for j in range(n_per):
            start = j * 5.0
            scenes.append(Scene(source=src, start=start, end=start + 4.5, score=1.0))
    return scenes


def test_builtin_ids():
    styles = load_styles(hot_path=Path("/nonexistent/styles.json"))
    assert set(TEMPLATE_TYPE_IDS) <= set(styles)
    assert styles["factory"].piece_sec < styles["explainer"].piece_sec
    assert styles["seed"].bgm_volume_default > styles["explainer"].bgm_volume_default
    assert styles["explainer"].subtitle_fontsize > styles["factory"].subtitle_fontsize


def test_hot_json_override(tmp_path: Path):
    p = tmp_path / "styles.json"
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "styles": {
                    "factory": {"piece_sec": 9.9, "label_zh": "工厂实拍-热更"},
                },
            }
        ),
        encoding="utf-8",
    )
    styles = load_styles(hot_path=p)
    assert styles["factory"].piece_sec == pytest.approx(9.9)
    assert styles["factory"].label_zh == "工厂实拍-热更"
    # untouched keys keep defaults from merge
    assert styles["explainer"].piece_sec > 2.0


def test_bundled_styles_json_loads():
    root = Path(__file__).resolve().parents[1]
    hot = root / "assets" / "templates_hot" / "styles.json"
    assert hot.is_file()
    styles = load_styles(hot_path=hot)
    for sid in TEMPLATE_TYPE_IDS:
        assert sid in styles
    assert get_style("explainer").id == "explainer"
    assert get_style("edu").id == "explainer"  # alias


def test_factory_vs_explainer_pacing():
    scenes = _fake_scenes()
    factory = pick_highlights(scenes, 15, style="factory")
    explainer = pick_highlights(scenes, 15, style="explainer")
    seed = pick_highlights(scenes, 15, style="seed")
    assert factory and explainer and seed

    def mean_len(clips):
        return sum(c.end - c.start for c in clips) / len(clips)

    assert len(explainer) < len(factory)
    assert len(explainer) < len(seed)
    assert mean_len(explainer) > mean_len(factory)
    assert mean_len(explainer) > mean_len(seed)


def test_piece_sec_for_duration_keeps_type_gap():
    f = get_style("factory")
    e = get_style("explainer")
    assert piece_sec_for_duration(e, 15) > piece_sec_for_duration(f, 15) * 1.5


def test_reverse_hook_first_clip_longer():
    scenes = _fake_scenes()
    clips = pick_highlights(scenes, 15, style="reverse_hook")
    assert clips
    first = clips[0].end - clips[0].start
    st = get_style("reverse_hook")
    # first beat should approach hook_sec when scene allows
    assert first >= min(st.hook_sec, 2.5) - 0.05
