"""Review plan uses real clips, and the local board can save notes."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from app.models import Clip, JobConfig, MediaItem, Scene
from app.pipeline import export as export_mod
from app.pipeline.highlights import pick_highlights
from app.review.bundle import exclusion_ranges, write_review_bundle
from app.review.server import ensure_review_server, open_review_board, stop_review_server
from app.review.slots import assign_slot_ids


def _grab(src: Path, _t: float, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\xff\xd8\xff\xd9")
    return True


def _clips(phone: Path, extra: Path) -> list[Clip]:
    return [
        Clip(source=phone, start=0.2, end=2.4, role="hook"),
        Clip(source=phone, start=3.0, end=5.1, role="broll"),
        Clip(source=extra, start=1.0, end=3.5, role="broll"),
        Clip(source=extra, start=4.0, end=6.2, role="broll"),
    ]


def _write_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, duration: int = 10, style: str = "reverse_hook", theme: str = "反向钩子", clips: list[Clip] | None = None):
    monkeypatch.setattr("app.review.bundle.grab_jpeg", _grab)
    phone = tmp_path / "PHONE.MOV"
    extra = tmp_path / "extra_b.mp4"
    phone.write_bytes(b"phone")
    extra.write_bytes(b"extra")
    out = tmp_path / "out"
    mp4 = out / f"remix_{duration}s.mp4"
    mp4.parent.mkdir(parents=True, exist_ok=True)
    mp4.write_bytes(b"mp4")
    used = clips if clips is not None else _clips(phone, extra)
    pack = write_review_bundle(
        out,
        style_id=style,
        theme=theme,
        pieces=[
            {
                "duration_sec": duration,
                "output_path": mp4,
                "clips": used,
                "copy": "别再踩这个坑：常见误区可能刚好说反了。",
            }
        ],
    )
    return out, phone, extra, pack


def test_slot_ids_follow_style_and_never_pad():
    assert assign_slot_ids("reverse_hook", 4) == ["pain", "twist", "proof", "close"]
    assert assign_slot_ids("reverse_hook", 2) == ["pain", "close"]
    assert assign_slot_ids("factory", 4) == ["power", "detail", "result", "close"]
    assert assign_slot_ids("seed", 3) == ["hook", "show", "close"]
    assert assign_slot_ids("explainer", 4) == ["ask", "explain", "tip", "close"]
    assert assign_slot_ids("custom", 3) == ["hook", "broll", "close"]
    assert assign_slot_ids("reverse_hook", 6)[-1] == "close"
    assert "pain" in assign_slot_ids("reverse_hook", 6)
    assert len(assign_slot_ids("reverse_hook", 6)) == 6


def test_plan_lists_only_real_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    out, phone, extra, pack = _write_bundle(tmp_path, monkeypatch, duration=15)
    plan = json.loads(pack.plan_path.read_text(encoding="utf-8"))
    piece = plan["pieces"][0]
    assert piece["id"] == "反向钩子_v02"
    assert piece["theme"] == "反向钩子"
    assert piece["duration_sec"] == 15
    assert [slot["slot_id"] for slot in piece["slots"]] == ["pain", "twist", "proof", "close"]
    sources = {slot["source_file"] for slot in piece["slots"]}
    assert sources == {str(phone), str(extra)}
    assert "FAKE" not in pack.plan_path.read_text(encoding="utf-8")
    assert piece["output_file"].endswith("remix_15s.mp4")
    assert piece["copy"].startswith("别再踩这个坑")
    pain = out / "_review" / "thumbs" / "反向钩子_v02_pain.jpg"
    assert pain.is_file() and pain.stat().st_size > 0
    html = pack.html_path.read_text(encoding="utf-8")
    assert "工厂成片审片" in html
    assert "保存备注" in html
    assert "重新加载" in html
    assert "含主题文案" in html
    assert "痛点误区" in html
    assert "不用收尾" in html
    assert "已加载 review_notes.json" in html
    assert "PHONE.MOV" in html


def test_disabled_slot_ranges_and_enabled_stick(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    out, phone, _extra, pack = _write_bundle(tmp_path, monkeypatch)
    notes_path = out / "_review" / "review_notes.json"
    notes_path.write_text(
        json.dumps(
            {
                "version": 1,
                "pieces": {
                    "反向钩子_v01": {
                        "enabled": False,
                        "note": "整条先不要",
                        "copy": "【手改】文案",
                        "disabled_slots": ["pain"],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ranges = exclusion_ranges(out, theme="反向钩子", duration_sec=10)
    assert len(ranges) == 1
    assert ranges[0][0] == phone
    assert ranges[0][1] == pytest.approx(0.2)
    assert ranges[0][2] == pytest.approx(2.4)
    write_review_bundle(
        out,
        style_id="reverse_hook",
        theme="反向钩子",
        pieces=[
            {
                "duration_sec": 10,
                "output_path": out / "remix_10s.mp4",
                "clips": _clips(phone, tmp_path / "extra_b.mp4"),
                "copy": "新生成的口播",
            }
        ],
    )
    plan = json.loads(pack.plan_path.read_text(encoding="utf-8"))
    assert plan["pieces"][0]["enabled"] is False
    # Saved notes stay the source of the edited copy; the new script is the plan baseline
    # only when notes have no copy. This rewrite keeps the notes file.
    kept = json.loads(notes_path.read_text(encoding="utf-8"))
    assert kept["pieces"]["反向钩子_v01"]["copy"] == "【手改】文案"
    assert kept["pieces"]["反向钩子_v01"]["disabled_slots"] == ["pain"]
    assert "review_apply" in plan


def test_pick_skips_excluded_source_without_inventing_one(tmp_path: Path):
    phone = Path("PHONE.MOV")
    extra = Path("extra_b.mp4")
    scenes = [
        Scene(source=phone, start=0, end=12, score=1),
        Scene(source=extra, start=0, end=12, score=1),
    ]
    clips = pick_highlights(
        scenes, 10, style="reverse_hook", exclude=[(phone, 0.0, 12.0)]
    )
    assert clips
    assert {c.source for c in clips} == {extra}

    only = [Scene(source=phone, start=0, end=12, score=1)]
    fallback = pick_highlights(only, 10, style="explainer", exclude=[(phone, 0.0, 12.0)])
    assert fallback
    assert fallback[0].source == phone


def test_export_writes_review_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    phone = tmp_path / "PHONE.MOV"
    extra = tmp_path / "extra_b.mp4"
    phone.write_bytes(b"phone")
    extra.write_bytes(b"extra")
    clips = _clips(phone, extra)
    monkeypatch.setattr(
        export_mod, "ingest", lambda _paths: [MediaItem(path=phone, duration_sec=8, width=320, height=240)]
    )
    monkeypatch.setattr(
        export_mod,
        "detect_scenes",
        lambda path: [Scene(source=path, start=0, end=8, score=1)],
    )
    monkeypatch.setattr(
        export_mod,
        "pick_highlights",
        lambda scenes, dur, style=None, exclude=None: list(clips),
    )

    def boom(*_args, **_kwargs):
        raise ConnectionError("network down")

    monkeypatch.setattr(export_mod, "tts", boom)

    def fake_silent(path: Path, duration: float) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"silent")
        return path

    monkeypatch.setattr(export_mod, "write_silent_audio", fake_silent)

    def fake_compose(used, script, audio, duration, out, **_kwargs):
        assert [c.source for c in used] == [c.source for c in clips]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"mp4")
        return out

    monkeypatch.setattr(export_mod, "compose", fake_compose)
    monkeypatch.setattr("app.review.bundle.grab_jpeg", _grab)
    cfg = JobConfig(
        inputs=[phone, extra],
        out_dir=tmp_path / "out",
        durations=[10],
        script_text="钩子第一句\n正文第二句",
        template_type="reverse_hook",
    )
    result = export_mod.export_job_result(cfg)
    assert result.outputs
    plan = json.loads((cfg.out_dir / "_review" / "plan.json").read_text(encoding="utf-8"))
    piece = plan["pieces"][0]
    assert piece["id"] == "反向钩子_v01"
    assert [slot["slot_id"] for slot in piece["slots"]] == ["pain", "twist", "proof", "close"]
    assert {slot["source_file"] for slot in piece["slots"]} == {str(phone), str(extra)}
    assert "钩子第一句" in piece["copy"]
    assert (cfg.out_dir / "_review" / "review.html").is_file()


def test_next_export_passes_disabled_ranges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    out, phone, extra, _pack = _write_bundle(tmp_path, monkeypatch)
    (out / "_review" / "review_notes.json").write_text(
        json.dumps(
            {
                "version": 1,
                "pieces": {
                    "反向钩子_v01": {
                        "enabled": True,
                        "note": "",
                        "copy": "留着文案",
                        "disabled_slots": ["twist"],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    seen: dict = {}

    def spy(scenes, dur, style=None, exclude=None):
        seen["exclude"] = list(exclude or [])
        return _clips(phone, extra)

    monkeypatch.setattr(export_mod, "ingest", lambda _paths: [MediaItem(path=phone, duration_sec=8)])
    monkeypatch.setattr(
        export_mod,
        "detect_scenes",
        lambda path: [Scene(source=phone, start=0, end=8, score=1)],
    )
    monkeypatch.setattr(export_mod, "pick_highlights", spy)
    monkeypatch.setattr(export_mod, "tts", lambda *_a, **_k: (_ for _ in ()).throw(ConnectionError("x")))

    def fake_silent(path: Path, duration: float) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"silent")
        return path

    monkeypatch.setattr(export_mod, "write_silent_audio", fake_silent)

    def fake_compose(_used, _script, _audio, _duration, dest, **_kwargs):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"mp4")
        return dest

    monkeypatch.setattr(export_mod, "compose", fake_compose)
    cfg = JobConfig(
        inputs=[phone],
        out_dir=out,
        durations=[10],
        script_text="钩子\n正文",
        template_type="reverse_hook",
    )
    export_mod.export_job_result(cfg)
    assert seen["exclude"]
    assert seen["exclude"][0][0] == phone
    assert seen["exclude"][0][1] == pytest.approx(3.0)


def test_board_save_persists_notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.review.server.webbrowser.open", lambda *_a, **_k: None)
    out, _phone, _extra, _pack = _write_bundle(tmp_path, monkeypatch)
    try:
        url = open_review_board(out, open_browser=False)
        assert url.endswith("/review.html")
        page = urllib.request.urlopen(url, timeout=5)
        body = page.read().decode("utf-8")
        assert "工厂成片审片" in body
        assert "保存备注" in body
        base = url.split("/review.html", 1)[0]
        payload = {
            "pieces": {
                "反向钩子_v01": {
                    "enabled": False,
                    "note": "整条先不要",
                    "copy": "【手改】工厂实拍种草口播",
                    "disabled_slots": ["close", "pain"],
                }
            }
        }
        req = urllib.request.Request(
            base + "/api/save",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        saved = json.loads(urllib.request.urlopen(req, timeout=5).read().decode("utf-8"))
        assert saved["ok"] is True
        notes = json.loads((out / "_review" / "review_notes.json").read_text(encoding="utf-8"))
        piece = notes["pieces"]["反向钩子_v01"]
        assert piece["enabled"] is False
        assert piece["disabled_slots"] == ["close", "pain"]
        assert piece["copy"] == "【手改】工厂实拍种草口播"
        assert notes["version"] == 1
        plan = json.loads((out / "_review" / "plan.json").read_text(encoding="utf-8"))
        assert plan["pieces"][0]["enabled"] is False
        assert plan["pieces"][0]["copy"] == piece["copy"]
        loaded = json.loads(
            urllib.request.urlopen(base + "/api/notes", timeout=5).read().decode("utf-8")
        )
        assert loaded["pieces"]["反向钩子_v01"]["note"] == "整条先不要"
        with pytest.raises(FileNotFoundError):
            open_review_board(tmp_path / "empty", open_browser=False)
    finally:
        stop_review_server()


def test_spec_and_ui_ship_the_board():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "packaging" / "remix.spec").read_text(encoding="utf-8")
    assert "app.review" in spec
    ui = (root / "app" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "打开审片看板" in ui
    guide = (root / "docs" / "同事使用说明.txt").read_text(encoding="utf-8")
    assert "C:\\remix\\" in guide
    assert "不需要 Mac" in guide
