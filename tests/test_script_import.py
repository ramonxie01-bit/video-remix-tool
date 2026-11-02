"""Unit tests for SRT/txt parse and script_from_plain (no network)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.pipeline.script import (
    load_script_file,
    resolve_script,
    scale_script_to_duration,
    script_from_plain,
)


def test_script_from_plain_newlines():
    text = "钩子第一句\n正文第二句\n收口第三句"
    s = script_from_plain(text, 15)
    assert len(s.lines) == 3
    assert s.lines[0].start == 0.0
    assert s.lines[-1].end == pytest.approx(15.0)
    assert "钩子第一句" in s.full_text
    assert s.lines[0].end <= s.lines[1].start + 0.001


def test_script_from_plain_blank_paragraphs():
    text = "第一段钩子\n\n第二段正文\n\n第三段收口"
    s = script_from_plain(text, 10)
    assert len(s.lines) == 3
    assert s.lines[-1].end == pytest.approx(10.0)


def test_script_from_plain_chinese_punct():
    text = "小单也能当天出？看工厂怎么干。车间实拍，流程透明。"
    s = script_from_plain(text, 10)
    assert len(s.lines) >= 2
    assert s.lines[-1].end == pytest.approx(10.0)


def test_load_txt(tmp_path: Path):
    p = tmp_path / "demo.txt"
    p.write_text("开场钩子\n工厂实拍\n行动号召\n", encoding="utf-8")
    s = load_script_file(p)
    assert len(s.lines) == 3
    assert s.lines[0].text == "开场钩子"
    assert s.full_text


def test_load_srt(tmp_path: Path):
    p = tmp_path / "demo.srt"
    p.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:02,500\n"
        "小单也能当天出？\n"
        "\n"
        "2\n"
        "00:00:02,500 --> 00:00:05,000\n"
        "看工厂怎么干\n"
        "\n",
        encoding="utf-8",
    )
    s = load_script_file(p)
    assert len(s.lines) == 2
    assert s.lines[0].text == "小单也能当天出？"
    assert s.lines[0].start == pytest.approx(0.0)
    assert s.lines[0].end == pytest.approx(2.5)
    assert s.lines[1].start == pytest.approx(2.5)
    assert s.lines[1].end == pytest.approx(5.0)


def test_scale_script_to_duration():
    from app.models import Script, ScriptLine

    s = Script(
        lines=[
            ScriptLine("a", 0.0, 2.5),
            ScriptLine("b", 2.5, 5.0),
        ],
        full_text="a，b",
    )
    scaled = scale_script_to_duration(s, 10)
    assert scaled.lines[-1].end == pytest.approx(10.0)
    assert scaled.lines[0].end == pytest.approx(5.0)


def test_resolve_prefers_text_over_template():
    from app.models import Clip

    clips = [Clip(source=Path("a.mp4"), start=0, end=5)]
    s = resolve_script(
        script_text="自定义钩子\n自定义正文",
        script_path=None,
        clips=clips,
        target_sec=10,
    )
    assert "自定义钩子" in s.full_text
    assert s.lines[-1].end == pytest.approx(10.0)


def test_resolve_falls_back_to_gen_script():
    from app.models import Clip

    clips = [Clip(source=Path("a.mp4"), start=0, end=5)]
    s = resolve_script(script_text=None, script_path=None, clips=clips, target_sec=10)
    assert s.lines
    assert "小单" in s.full_text or "工厂" in s.full_text


def test_extract_duration_section_demo_file():
    from app.pipeline.script import extract_duration_section, script_from_plain
    raw = Path("/workspace/remix-sample-clips/demo_scripts_10_15_30.txt").read_text(encoding="utf-8")
    sec = extract_duration_section(raw, 10)
    assert "别只看机器响不响" in sec
    assert "很多老板怕色差" not in sec
    s = script_from_plain(sec, 10)
    assert len(s.lines) == 3
