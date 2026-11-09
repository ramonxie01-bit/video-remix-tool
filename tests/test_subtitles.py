"""Burnt-in subtitles name a CJK font and point libass at that file."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import ffmpeg as ffmpeg_mod
from app.services.ffmpeg import resolve_cjk_font, subtitle_vf


def test_subtitle_vf_sets_fontname_and_relative_fontsdir(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    srt = work / "subs.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n钩子\n", encoding="utf-8")
    font = tmp_path / "NotoSansSC-Regular.otf"
    font.write_bytes(b"otf")

    vf = subtitle_vf(
        srt,
        work,
        fontsize=18,
        margin_v=48,
        font_file=font,
        font_name="Noto Sans SC",
    )
    assert "FontName=Noto Sans SC" in vf
    assert "Fontsize=18" in vf
    assert "fontsdir=fonts" in vf
    assert "subs.srt" in vf
    assert ":\\" not in vf
    assert (work / "fonts" / "NotoSansSC-Regular.otf").is_file()


def test_subtitle_vf_defaults_to_microsoft_yahei(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    srt = work / "subs.srt"
    srt.write_text("1\n", encoding="utf-8")
    vf = subtitle_vf(srt, work, fontsize=20, margin_v=52)
    assert "FontName=Microsoft YaHei" in vf
    assert "fontsdir=" not in vf


def test_resolve_prefers_bundled_noto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "msyh.ttc").write_bytes(b"ttc")
    (fonts / "NotoSansSC-Regular.otf").write_bytes(b"otf")
    monkeypatch.setattr(ffmpeg_mod, "font_search_dirs", lambda: [fonts])
    path, family = resolve_cjk_font()
    assert path.name == "NotoSansSC-Regular.otf"
    assert family == "Noto Sans SC"


def test_resolve_yahei_when_noto_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fonts = tmp_path / "Fonts"
    fonts.mkdir()
    (fonts / "msyh.ttc").write_bytes(b"ttc")
    monkeypatch.setattr(ffmpeg_mod, "font_search_dirs", lambda: [fonts])
    path, family = resolve_cjk_font()
    assert path.name == "msyh.ttc"
    assert family == "Microsoft YaHei"
