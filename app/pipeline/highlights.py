from __future__ import annotations

import os
from pathlib import Path

from app.models import Clip, Scene
from app.pipeline.styles import RemixStyle, get_style, piece_sec_for_duration


def _same_media(left: Path, right: Path) -> bool:
    if left == right:
        return True
    try:
        if left.resolve() == right.resolve():
            return True
    except OSError:
        pass
    return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(
        os.path.normpath(str(right))
    )


def _hits_exclude(
    src: Path,
    start: float,
    end: float,
    exclude: list[tuple[Path, float, float]] | None,
) -> bool:
    if not exclude:
        return False
    for other, a, b in exclude:
        if not _same_media(src, other):
            continue
        overlap = min(end, b) - max(start, a)
        if overlap > 0.15:
            return True
    return False


def clips_use_excluded(
    clips: list[Clip],
    exclude: list[tuple[Path, float, float]] | None,
) -> bool:
    return any(_hits_exclude(c.source, c.start, c.end, exclude) for c in clips)


def pick_highlights(
    scenes: list[Scene],
    target_sec: int,
    style: RemixStyle | str | None = None,
    exclude: list[tuple[Path, float, float]] | None = None,
) -> list[Clip]:
    """Diversify: take short bites from EACH source, staggered windows per duration.

    Avoids dumping the same head-of-file for every length (platform duplicate risk).
    Cut pacing (piece_sec / region_bias / max_cuts / hook_sec) comes from 成片类型 style.
    ``exclude`` drops source ranges a reviewer marked 不用 (real scenes only).
    """
    if not scenes:
        return []
    st = style if isinstance(style, RemixStyle) else get_style(style)

    by_src: dict[Path, list[Scene]] = {}
    for s in scenes:
        by_src.setdefault(s.source, []).append(s)
    for src in by_src:
        by_src[src].sort(key=lambda s: s.start)

    sources = list(by_src.keys())
    region = float(st.region_bias)
    piece = piece_sec_for_duration(st, int(target_sec))
    max_cuts = max(1, int(st.max_cuts))

    clips: list[Clip] = []
    used = 0.0
    # Round-robin across sources for cross-cut energy
    round_i = 0
    safety = 0
    while used < target_sec - 0.15 and safety < 80 and len(clips) < max_cuts:
        safety += 1
        src = sources[round_i % len(sources)]
        round_i += 1
        pool = by_src[src]
        # first clip: prefer a scene long enough for hook_sec
        take_cap = max(piece, float(st.hook_sec)) if not clips else piece
        if not clips:
            long_enough = [s for s in pool if (s.end - s.start) >= take_cap - 1e-6]
            scene = long_enough[0] if long_enough else max(pool, key=lambda s: s.end - s.start)
        else:
            # pick a scene, then a sub-window shifted by duration + round
            scene = pool[(round_i + int(target_sec)) % len(pool)]
        span = scene.end - scene.start
        if span < 0.5:
            continue
        # offset into scene (region_bias driven by style)
        local = (region * span) + ((round_i * 0.37) % max(span * 0.5, 0.1))
        if not clips and span >= take_cap:
            start = scene.start + min(local, max(span - take_cap, 0.0))
        else:
            start = scene.start + min(local, max(span - 0.5, 0))
        take = min(take_cap, scene.end - start, target_sec - used)
        if take < 0.45:
            # try from head of another chunk
            start = scene.start
            take = min(take_cap, span, target_sec - used)
        if take < 0.45:
            continue
        end = start + take
        role = "hook" if not clips else "broll"
        # skip near-duplicate of last clip (same file + overlapping time)
        if clips and clips[-1].source == src and abs(clips[-1].start - start) < 0.4:
            start = min(scene.end - take, start + 0.8)
            end = start + take
            if end > scene.end + 1e-6:
                continue
        if _hits_exclude(src, start, end, exclude):
            continue
        clips.append(Clip(source=src, start=start, end=end, role=role))
        used += take

    if not clips:
        # Prefer a real scene that is not in the disabled ranges. If every
        # range was disabled, keep the first real scene (never invent a file).
        chosen = None
        for s0 in scenes:
            end = min(s0.end, s0.start + target_sec)
            if end - s0.start < 0.45:
                continue
            if not _hits_exclude(s0.source, s0.start, end, exclude):
                chosen = (s0, end)
                break
        if chosen is None:
            s0 = scenes[0]
            chosen = (s0, min(s0.end, s0.start + target_sec))
        s0, end = chosen
        clips = [
            Clip(
                source=s0.source,
                start=s0.start,
                end=end,
                role="hook",
            )
        ]

    if clips:
        clips[0].role = "hook"
    # light shuffle of middle beats keeps hook first
    if len(clips) > 3:
        mid = clips[1:-1]
        mid = mid[::-1]  # reverse mid for variety vs chronological dump
        clips = [clips[0]] + mid + [clips[-1]]
    return clips
