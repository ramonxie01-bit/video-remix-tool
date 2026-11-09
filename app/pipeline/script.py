from __future__ import annotations

import re
from pathlib import Path

from app.models import Clip, Script, ScriptLine
from app.pipeline.templates import get_template

_SRT_TIME = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)
_CN_PUNCT_SPLIT = re.compile(r"(?<=[。！？；!?;])\s*|(?<=[，,、])\s+|\n+")


def _hms_to_sec(h: str, m: str, s: str, ms: str) -> float:
    ms_pad = (ms + "000")[:3]
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms_pad) / 1000.0


def _parse_srt(text: str) -> Script:
    blocks = re.split(r"\n\s*\n", text.strip())
    lines: list[ScriptLine] = []
    for block in blocks:
        raw = block.strip()
        if not raw:
            continue
        rows = raw.splitlines()
        # skip optional numeric index line
        i = 0
        if rows and rows[0].strip().isdigit():
            i = 1
        if i >= len(rows):
            continue
        m = _SRT_TIME.search(rows[i])
        if not m:
            continue
        start = _hms_to_sec(*m.groups()[:4])
        end = _hms_to_sec(*m.groups()[4:])
        cue_text = " ".join(r.strip() for r in rows[i + 1 :] if r.strip())
        if not cue_text:
            continue
        if end <= start:
            end = start + 0.5
        lines.append(ScriptLine(text=cue_text, start=start, end=end))
    full = "，".join(l.text for l in lines)
    return Script(lines=lines, full_text=full)


def extract_duration_section(text: str, target_sec: int | float) -> str:
    """If content-bot file has ## 10s / ## 15s / ## 30s sections, pick matching block."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Strip full-line # comments that are not ## duration headers
    cleaned_lines = []
    for ln in text.split("\n"):
        s = ln.strip()
        if s.startswith("#") and not re.match(r"^##\s*\d+s\b", s, re.I):
            continue
        cleaned_lines.append(ln)
    text = "\n".join(cleaned_lines)
    dur = int(target_sec)
    # Split on ## NNs headers
    parts = re.split(r"(?m)^(##\s*\d+s)\s*$", text)
    if len(parts) < 3:
        return text.strip()
    # parts: [preamble, header1, body1, header2, body2, ...]
    by_dur: dict[int, str] = {}
    i = 1
    while i + 1 < len(parts):
        header, body = parts[i], parts[i + 1]
        m = re.search(r"(\d+)", header)
        if m:
            by_dur[int(m.group(1))] = body.strip()
        i += 2
    if dur in by_dur and by_dur[dur].strip():
        return by_dur[dur].strip()
    # fallback: nearest or full cleaned text
    if by_dur:
        nearest = min(by_dur.keys(), key=lambda d: abs(d - dur))
        return by_dur[nearest].strip()
    return text.strip()


def _split_plain_cues(text: str) -> list[str]:
    """One line per cue, or blank-line paragraphs; also soft-split long Chinese sentences."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    # Prefer blank-line paragraphs if present
    if re.search(r"\n\s*\n", text):
        parts = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
        return parts
    # Else one non-empty line per cue
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) >= 2:
        return lines
    # Single blob: split on Chinese / common punctuation
    blob = lines[0] if lines else text
    parts = [p.strip() for p in _CN_PUNCT_SPLIT.split(blob) if p and p.strip()]
    # Drop dangling lone punctuation leftovers
    parts = [p for p in parts if p and not re.fullmatch(r"[，,、。！？；!?;]+", p)]
    return parts or [blob]


def script_from_plain(text: str, target_sec: float) -> Script:
    """Split plain copy into cues and distribute timings across target_sec (char-weighted)."""
    cues = _split_plain_cues(text)
    if not cues:
        return Script()
    target = max(float(target_sec), 0.5)
    weights = [max(len(c), 1) for c in cues]
    total_w = float(sum(weights))
    lines: list[ScriptLine] = []
    t = 0.0
    for i, cue in enumerate(cues):
        share = weights[i] / total_w
        dur = max(target * share, 0.35)
        end = target if i == len(cues) - 1 else min(t + dur, target)
        if end - t < 0.2 and i < len(cues) - 1:
            # tiny slice — merge forward by skipping empty gap
            end = min(t + 0.35, target)
        lines.append(ScriptLine(text=cue, start=round(t, 3), end=round(end, 3)))
        t = end
        if t >= target:
            break
    if lines:
        lines[-1].end = round(target, 3)
    full = "，".join(l.text for l in lines)
    return Script(lines=lines, full_text=full)


def scale_script_to_duration(script: Script, target_sec: float) -> Script:
    """Linearly rescale cue timings so the last end == target_sec."""
    if not script.lines:
        return script
    target = max(float(target_sec), 0.5)
    old_end = max(l.end for l in script.lines) or 1.0
    if abs(old_end - target) < 0.05:
        return script
    scale = target / old_end
    lines = [
        ScriptLine(
            text=l.text,
            start=round(l.start * scale, 3),
            end=round(min(l.end * scale, target), 3),
        )
        for l in script.lines
    ]
    if lines:
        lines[-1].end = round(target, 3)
    return Script(lines=lines, full_text=script.full_text)


def load_script_file(path: Path) -> Script:
    """Load `.txt` (line/paragraph cues) or `.srt` into a Script (raw timings for SRT)."""
    path = Path(path)
    raw = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    if suffix == ".srt":
        return _parse_srt(raw)
    # .txt and unknown → plain
    # timings left at 0..1 placeholder; caller should script_from_plain / scale
    cues = _split_plain_cues(raw)
    if not cues:
        return Script()
    # provisional equal slots in [0, 1]; export will re-time via script_from_plain or scale
    n = len(cues)
    lines = [
        ScriptLine(text=c, start=i / n, end=(i + 1) / n) for i, c in enumerate(cues)
    ]
    return Script(lines=lines, full_text="，".join(cues))


def script_rejection_reason(text: str | None) -> str | None:
    """Colleague-facing error when copy cannot drive burnt-in subtitles.

    ``None`` means the text has at least one cue. Empty paste and an ``.srt``
    with timestamps but no dialogue are rejected instead of falling back to
    the built-in factory template.
    """
    raw = text or ""
    if "-->" in raw and _SRT_TIME.search(raw):
        if not _parse_srt(raw).lines:
            return (
                "文案无效：没有可用字幕。请检查 .srt 的时间轴和文字，"
                "或改贴纯文本口播稿。"
            )
        return None
    if not _split_plain_cues(raw):
        return (
            "文案为空或无效。请粘贴口播稿（一行一句），或导入含句子的 .txt / .srt。"
            "没有文案就不会烧录字幕。"
        )
    return None


def resolve_script(
    *,
    script_text: str | None,
    script_path: Path | None,
    clips: list[Clip],
    target_sec: int | float,
) -> Script:
    """Prefer imported paste/file; fall back to built-in templates."""
    text = (script_text or "").strip()
    if not text and script_path:
        p = Path(script_path)
        if p.is_file():
            if p.suffix.lower() == ".srt":
                loaded = load_script_file(p)
                if loaded.lines:
                    return scale_script_to_duration(loaded, float(target_sec))
            # keep raw for duration-section extraction (## 10s blocks)
            text = p.read_text(encoding="utf-8-sig")
    if text:
        # pasted SRT body (contains -->) — parse cues then scale
        if "-->" in text and _SRT_TIME.search(text):
            return scale_script_to_duration(_parse_srt(text), float(target_sec))
        section = extract_duration_section(text, target_sec)
        return script_from_plain(section, float(target_sec))
    return gen_script(clips, target_sec=int(target_sec) if target_sec else None)


def gen_script(clips: list[Clip], topic: str = "数码印花工厂小单快反", target_sec: int | None = None) -> Script:
    """Rule-based MVP copy sized to target duration."""
    if not clips:
        return Script()
    total = float(target_sec) if target_sec else sum(c.end - c.start for c in clips)
    dur = int(target_sec) if target_sec in (10, 15, 30) else (10 if total <= 12 else 15 if total <= 20 else 30)
    try:
        tpl = get_template(int(round(total)) if int(round(total)) in (10, 15, 30) else dur)
    except ValueError:
        tpl = get_template(dur)

    if tpl.duration_sec <= 10:
        texts = [
            "小单也能当天出？看工厂怎么干",
            "车间实拍，流程透明，打样快返单稳",
        ]
        edges = [0.0, min(2.5, total * 0.35), total]
    elif tpl.duration_sec <= 15:
        texts = [
            "面料印花避坑：这三个细节别忽略",
            "来料加工，交期怎么压到最短",
            "电商小单、定制款，这里都能接",
        ]
        edges = [0.0, 3.0, min(9.0, total * 0.65), total]
    else:
        texts = [
            "数码印花源头工厂，小单快反怎么做",
            "第一步：看布定工艺，少走弯路",
            "第二步：打样确认，颜色一次过",
            "第三步：返单稳交期，适合电商备货",
            "需要打样或询盘，评论区扣1",
        ]
        edges = [0.0, 3.0, 10.0, 18.0, 25.0, total]
        # clamp edges to total
        edges = [min(e, total) for e in edges]
        if edges[-1] < total:
            edges[-1] = total

    lines: list[ScriptLine] = []
    for i, text in enumerate(texts):
        if i + 1 >= len(edges):
            break
        start, end = edges[i], edges[i + 1]
        if end - start < 0.3:
            continue
        lines.append(ScriptLine(text=text, start=start, end=end))
    full = "，".join(l.text for l in lines)
    return Script(lines=lines, full_text=full)
