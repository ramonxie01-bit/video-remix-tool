from __future__ import annotations

from pathlib import Path

import numpy as np

from app.models import Scene


def _equal_chunks(video: Path, dur: float, parts: int = 8) -> list[Scene]:
    step = min(3.0, max(1.0, dur / max(parts, 1)))
    scenes: list[Scene] = []
    t = 0.0
    while t < dur - 1e-6:
        end = min(t + step, dur)
        if end - t >= 0.4:
            scenes.append(Scene(source=video, start=t, end=end, score=1.0))
        t = end
    return scenes or [Scene(source=video, start=0.0, end=dur, score=1.0)]


def _merge_short(scenes: list[Scene], min_len: float = 0.8) -> list[Scene]:
    if not scenes:
        return scenes
    merged: list[Scene] = [scenes[0]]
    for s in scenes[1:]:
        prev = merged[-1]
        if s.end - s.start < min_len or prev.end - prev.start < min_len:
            merged[-1] = Scene(
                source=prev.source,
                start=prev.start,
                end=s.end,
                score=max(prev.score, s.score),
            )
        else:
            merged.append(s)
    return merged


def _histogram_cuts(
    video: Path,
    dur: float,
    threshold: float,
    sample_fps: float = 2.0,
) -> list[Scene] | None:
    try:
        import cv2
    except ImportError:
        return None

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return None

    native_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if native_fps <= 1e-3:
        native_fps = 25.0
    step = max(1, int(round(native_fps / max(sample_fps, 0.1))))

    prev_hist = None
    cut_times: list[float] = [0.0]
    frame_idx = 0
    diffs: list[tuple[float, float]] = []

    try:
        while True:
            ok = cap.grab()
            if not ok:
                break
            if frame_idx % step != 0:
                frame_idx += 1
                continue
            ok, frame = cap.retrieve()
            frame_idx += 1
            if not ok or frame is None:
                continue
            t = frame_idx / native_fps
            if t > dur + 0.5:
                break
            small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            if prev_hist is not None:
                # correlation: 1 similar, -1 opposite → distance in [0, 1]
                corr = float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL))
                dist = max(0.0, min(1.0, 1.0 - corr))
                diffs.append((t, dist))
                if dist >= threshold:
                    if t - cut_times[-1] >= 0.5:
                        cut_times.append(t)
            prev_hist = hist
    finally:
        cap.release()

    if len(cut_times) <= 1 and not diffs:
        return None

    # Adaptive: if too few cuts, lower threshold once using percentile
    if len(cut_times) < 2 and diffs:
        vals = sorted(d for _, d in diffs)
        adaptive = max(threshold * 0.7, vals[int(len(vals) * 0.85)] if vals else threshold)
        cut_times = [0.0]
        for t, dist in diffs:
            if dist >= adaptive and t - cut_times[-1] >= 0.5:
                cut_times.append(t)

    if dur not in cut_times and cut_times[-1] < dur - 0.05:
        cut_times.append(dur)

    scenes: list[Scene] = []
    for i in range(len(cut_times) - 1):
        start, end = cut_times[i], cut_times[i + 1]
        if end - start < 0.35:
            continue
        # score by mean cut strength near start (hook-friendly)
        nearby = [d for t, d in diffs if start - 0.25 <= t <= start + 0.25]
        score = float(np.mean(nearby)) if nearby else 0.5
        scenes.append(Scene(source=video, start=float(start), end=float(end), score=score))

    return _merge_short(scenes) if scenes else None


def detect_scenes(video: Path, threshold: float = 0.35) -> list[Scene]:
    """Detect cut points via OpenCV HSV-histogram diffs; fall back to equal chunks."""
    from app.services.ffmpeg import probe

    video = Path(video)
    meta = probe(video)
    dur = float(meta.get("duration") or 0)
    if dur <= 0:
        return []

    try:
        scenes = _histogram_cuts(video, dur, threshold=threshold)
        if scenes:
            return scenes
    except Exception:
        pass

    return _equal_chunks(video, dur)
