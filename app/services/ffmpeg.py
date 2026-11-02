from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.models import Clip, Script


def ffmpeg_bin() -> str:
    bundled = Path(__file__).resolve().parents[2] / "assets" / "ffmpeg" / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    return shutil.which("ffmpeg") or "ffmpeg"


def ffprobe_bin() -> str:
    bundled = Path(__file__).resolve().parents[2] / "assets" / "ffmpeg" / "ffprobe.exe"
    if bundled.exists():
        return str(bundled)
    return shutil.which("ffprobe") or "ffprobe"


def probe(path: Path) -> dict:
    cmd = [
        ffprobe_bin(),
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        raw = subprocess.check_output(cmd, text=True)
        data = json.loads(raw)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return {}
    duration = float(data.get("format", {}).get("duration") or 0)
    width = height = None
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            width = s.get("width")
            height = s.get("height")
            break
    return {"duration": duration, "width": width, "height": height}


def _srt_from_script(script: Script, srt_path: Path) -> Path:
    def ts(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int(round((sec - int(sec)) * 1000))
        if ms >= 1000:
            s += 1
            ms -= 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines: list[str] = []
    for i, line in enumerate(script.lines, 1):
        lines.append(str(i))
        lines.append(f"{ts(line.start)} --> {ts(line.end)}")
        lines.append(line.text.replace("\n", " ").strip())
        lines.append("")
    srt_path.write_text("\n".join(lines), encoding="utf-8-sig")  # BOM helps some Windows builds
    return srt_path


def _escape_concat_path(path: Path) -> str:
    """Path for ffmpeg concat demuxer `file '...'` lines (prefer POSIX, escape quotes)."""
    p = path.resolve().as_posix().replace("'", r"'\''")
    return p


def escape_subtitles_filter_path(path: Path, *, relative_to: Path | None = None) -> str:
    """Escape a path for ffmpeg `subtitles=` filter on Windows/macOS/Linux.

    Prefer a relative path without drive letters when `relative_to` is the process cwd.
    Otherwise convert to POSIX and escape the Windows drive colon as `C\\:/...`.
    """
    path = Path(path)
    if relative_to is not None:
        try:
            rel = path.resolve().relative_to(Path(relative_to).resolve())
            p = rel.as_posix()
        except ValueError:
            p = path.resolve().as_posix()
    else:
        p = path.resolve().as_posix()

    # Filtergraph treats `:` as option separator — escape drive letter form C:/...
    if len(p) >= 2 and p[1] == ":":
        p = p[0] + r"\:" + p[2:]
    p = p.replace("\\", r"\\").replace("'", r"\'").replace(",", r"\,").replace("[", r"\[").replace("]", r"\]")
    return p


def burn_vertical_remix(
    clips: list[Clip],
    script: Script,
    audio: Path,
    duration: int,
    out_path: Path,
    bgm_path: Path | None = None,
    bgm_volume: float = 0.22,
    subtitle_fontsize: int = 18,
    subtitle_margin_v: int = 48,
) -> Path:
    """Compose: diversify cuts → vertical → burn SRT timed to TTS → mix voice (+ optional BGM)."""
    if not clips:
        raise ValueError("no clips")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = out_path.parent / f"_compose_{duration}"
    work.mkdir(exist_ok=True)

    # Keep SRT next to workdir with ASCII-only name → relative subtitles= path (Windows-safe)
    srt = _srt_from_script(script, work / "subs.srt")

    parts: list[Path] = []
    for i, c in enumerate(clips):
        part = work / f"part_{i:02d}.mp4"
        vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
        cmd = [
            ffmpeg_bin(),
            "-y",
            "-ss",
            f"{c.start:.3f}",
            "-to",
            f"{c.end:.3f}",
            "-i",
            str(c.source),
            "-vf",
            vf,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            str(part),
        ]
        subprocess.run(cmd, check=False, capture_output=True)
        if part.exists() and part.stat().st_size > 0:
            parts.append(part)

    if not parts:
        raise RuntimeError("ffmpeg failed to cut parts")

    concat_list = work / "concat.txt"
    concat_list.write_text(
        "".join(f"file '{_escape_concat_path(p)}'\n" for p in parts),
        encoding="utf-8",
    )
    silent = work / "silent.mp4"
    subprocess.run(
        [
            ffmpeg_bin(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c",
            "copy",
            str(silent),
        ],
        check=False,
        capture_output=True,
    )
    if not silent.exists() or silent.stat().st_size == 0:
        raise RuntimeError("ffmpeg concat failed")

    # Relative subtitle path + cwd=work avoids `C:` filtergraph breakage on Windows
    sub_esc = escape_subtitles_filter_path(srt, relative_to=work)
    fs = int(subtitle_fontsize)
    mv = int(subtitle_margin_v)
    vf = (
        f"subtitles={sub_esc}:force_style='Fontsize={fs},Outline=2,"
        f"Alignment=2,MarginV={mv}'"
    )

    voice = Path(audio).resolve()
    cmd = [
        ffmpeg_bin(),
        "-y",
        "-i",
        str(silent.resolve()),
        "-i",
        str(voice),
    ]
    if bgm_path and Path(bgm_path).exists():
        cmd += ["-stream_loop", "-1", "-i", str(Path(bgm_path).resolve())]
        # voice padded + ducked BGM under narration
        fc = (
            f"[1:a]apad=whole_dur={duration}[va];"
            f"[2:a]volume={bgm_volume},atrim=0:{duration},asetpts=PTS-STARTPTS[ba];"
            f"[va][ba]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        cmd += [
            "-t", str(duration),
            "-vf", vf,
            "-filter_complex", fc,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            str(out_path.resolve()),
        ]
    else:
        cmd += [
            "-t", str(duration),
            "-vf", vf,
            "-af", f"apad=whole_dur={duration}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            str(out_path.resolve()),
        ]
    proc = subprocess.run(cmd, check=False, capture_output=True, cwd=str(work))
    if not out_path.exists() or out_path.stat().st_size == 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace")[-800:]
        raise RuntimeError(f"ffmpeg burn/subs failed: {err}")
    return out_path
