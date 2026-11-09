from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.models import Clip, Script

# Bundled first (portable zip), then Windows system fonts. Family names must
# match the font name table so libass does not draw Chinese as boxes.
_FONT_PRIORITY: tuple[tuple[str, str], ...] = (
    ("NotoSansSC-Regular.otf", "Noto Sans SC"),
    ("NotoSansSC-Regular.ttf", "Noto Sans SC"),
    ("NotoSansCJKsc-Regular.otf", "Noto Sans CJK SC"),
    ("msyh.ttc", "Microsoft YaHei"),
    ("msyh.ttf", "Microsoft YaHei"),
    ("msyhbd.ttc", "Microsoft YaHei"),
    ("msyhl.ttc", "Microsoft YaHei"),
    ("simhei.ttf", "SimHei"),
    ("simsun.ttc", "SimSun"),
    ("wqy-microhei.ttc", "WenQuanYi Micro Hei"),
)


def asset_roots() -> list[Path]:
    """Source checkout, PyInstaller _MEIPASS, and the folder next to the exe.

    PyInstaller 6 onedir puts assets in ``_internal`` and ``Path(__file__).parents[2]``
    already lands there. The extra roots cover a layout that sits beside the exe.
    """
    roots: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen:
            return
        seen.add(key)
        roots.append(path)

    add(Path(__file__).resolve().parents[2])
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        add(Path(meipass))
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        add(exe_dir)
        add(exe_dir / "_internal")
    return roots


def _bundled_tool(filename: str) -> Path | None:
    for root in asset_roots():
        candidate = root / "assets" / "ffmpeg" / filename
        if candidate.is_file():
            return candidate
    return None


def ffmpeg_bin() -> str:
    bundled = _bundled_tool("ffmpeg.exe")
    if bundled is not None:
        return str(bundled)
    return shutil.which("ffmpeg") or "ffmpeg"


def ffprobe_bin() -> str:
    bundled = _bundled_tool("ffprobe.exe")
    if bundled is not None:
        return str(bundled)
    return shutil.which("ffprobe") or "ffprobe"


def _decode_output(raw: bytes | str | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    return raw.decode("utf-8", errors="replace").strip()


def _stream_duration(stream: dict) -> float:
    try:
        dur = float(stream.get("duration") or 0)
    except (TypeError, ValueError):
        dur = 0.0
    if dur > 0:
        return dur
    frames = stream.get("nb_frames")
    rate = str(stream.get("avg_frame_rate") or "")
    if not frames or "/" not in rate:
        return 0.0
    num, den = rate.split("/", 1)
    try:
        fps = float(num) / float(den)
        if fps <= 0:
            return 0.0
        return float(frames) / fps
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _media_duration(data: dict) -> float:
    fmt = data.get("format") or {}
    try:
        dur = float(fmt.get("duration") or 0)
    except (TypeError, ValueError):
        dur = 0.0
    if dur > 0:
        return dur
    for stream in data.get("streams") or []:
        if stream.get("codec_type") != "video":
            continue
        dur = _stream_duration(stream)
        if dur > 0:
            return dur
    return 0.0


def probe(path: Path) -> dict:
    """Return duration/size, or ``{"error": "<ffprobe stderr>"}`` on failure.

    stderr is kept. A bare ``{}`` used to surface as a vague “ffprobe 无法识别”.
    """
    bin_path = ffprobe_bin()
    cmd = [
        bin_path,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True)
    except FileNotFoundError:
        return {"error": f"找不到 ffprobe（{bin_path}）。请完整解压便携包，不要只拷贝 exe。"}
    except OSError as ex:
        return {"error": f"无法启动 ffprobe（{bin_path}）：{ex}"}
    stderr = _decode_output(proc.stderr)
    stdout = _decode_output(proc.stdout)
    if proc.returncode != 0:
        detail = stderr or stdout or f"退出码 {proc.returncode}"
        return {"error": f"{detail[-400:]}（ffprobe: {bin_path}）"}
    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        extra = f"：{stderr[:200]}" if stderr else ""
        return {"error": f"ffprobe 输出不是 JSON{extra}（ffprobe: {bin_path}）"}
    if not isinstance(data, dict):
        return {"error": f"ffprobe 输出不是对象（ffprobe: {bin_path}）"}
    duration = _media_duration(data)
    width = height = None
    for stream in data.get("streams") or []:
        if stream.get("codec_type") == "video":
            width = stream.get("width")
            height = stream.get("height")
            break
    if duration <= 0:
        detail = stderr or "ffprobe 没有读到视频时长"
        return {
            "error": f"{detail[-400:]}（ffprobe: {bin_path}）",
            "duration": 0,
            "width": width,
            "height": height,
        }
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


def font_search_dirs() -> list[Path]:
    dirs: list[Path] = []
    for root in asset_roots():
        dirs.append(root / "assets" / "fonts")
    windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if windir:
        dirs.append(Path(windir) / "Fonts")
    elif os.name == "nt":
        dirs.append(Path(r"C:\Windows\Fonts"))
    dirs.extend(
        [
            Path("/usr/share/fonts/opentype/noto"),
            Path("/usr/share/fonts/truetype/noto"),
            Path("/usr/share/fonts/truetype/wqy"),
        ]
    )
    return dirs


def resolve_cjk_font() -> tuple[Path, str] | None:
    """First matching bundled Noto, then YaHei / SimHei / WenQuanYi."""
    dirs = font_search_dirs()
    for filename, family in _FONT_PRIORITY:
        for directory in dirs:
            candidate = directory / filename
            if candidate.is_file():
                return candidate, family
    return None


def subtitle_vf(
    srt: Path,
    work: Path,
    *,
    fontsize: int,
    margin_v: int,
    font_file: Path | None = None,
    font_name: str | None = None,
) -> str:
    """subtitles= filter with a CJK FontName and, when known, fontsdir.

    ``work`` is the ffmpeg cwd, so paths stay relative (no ``C:`` in the filtergraph).
    """
    work = Path(work)
    sub_esc = escape_subtitles_filter_path(Path(srt), relative_to=work)
    family = font_name or "Microsoft YaHei"
    fonts_opt = ""
    if font_file is not None:
        dest_dir = work / "fonts"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / Path(font_file).name
        try:
            same = dest.resolve() == Path(font_file).resolve()
        except OSError:
            same = False
        if not same:
            shutil.copy2(font_file, dest)
        fonts_dir_esc = escape_subtitles_filter_path(dest_dir, relative_to=work)
        fonts_opt = f":fontsdir={fonts_dir_esc}"
    style = (
        f"FontName={family},Fontsize={int(fontsize)},Outline=2,"
        f"Alignment=2,MarginV={int(margin_v)}"
    )
    return f"subtitles={sub_esc}{fonts_opt}:force_style='{style}'"


def write_silent_audio(path: Path, duration: float) -> Path:
    """AAC silence so subtitle burn can finish when TTS has no network."""
    path = Path(path)
    if path.suffix.lower() not in {".m4a", ".aac", ".mp4", ".wav"}:
        path = path.with_suffix(".m4a")
    path.parent.mkdir(parents=True, exist_ok=True)
    seconds = max(float(duration), 0.5)
    cmd = [
        ffmpeg_bin(),
        "-y",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t",
        f"{seconds:.3f}",
        "-c:a",
        "aac",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if not path.is_file() or path.stat().st_size == 0:
        err = _decode_output(proc.stderr)[-400:]
        raise RuntimeError(f"无法生成静音音轨：{err or 'ffmpeg 失败'}")
    return path


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

    # Relative subtitle path + cwd=work avoids `C:` filtergraph breakage on Windows.
    # FontName is required: Fontsize alone draws Chinese as empty boxes on Windows.
    found = resolve_cjk_font()
    if found:
        font_file, font_name = found
    else:
        font_file, font_name = None, "Microsoft YaHei"
    vf = subtitle_vf(
        srt,
        work,
        fontsize=subtitle_fontsize,
        margin_v=subtitle_margin_v,
        font_file=font_file,
        font_name=font_name,
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
