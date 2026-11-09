"""Render the Mac-style 工厂成片审片 page from plan.json."""
from __future__ import annotations

import csv
import html
from datetime import datetime
from pathlib import Path

from app.review.slots import slot_label, thumbs_for_row


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_review_html(plan: dict, notes: dict, review_dir: Path) -> str:
    pieces = list(plan.get("pieces") or [])
    note_pieces = notes.get("pieces") if isinstance(notes.get("pieces"), dict) else {}
    when = str(plan.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M"))
    style_id = str(plan.get("style_id") or "")
    body_rows: list[str] = []
    for piece in pieces:
        pid = str(piece.get("id") or "")
        meta = note_pieces.get(pid) if isinstance(note_pieces.get(pid), dict) else {}
        enabled = piece.get("enabled", True)
        if isinstance(meta, dict) and "enabled" in meta:
            enabled = bool(meta.get("enabled"))
        copy_default = piece.get("copy") or ""
        if isinstance(meta, dict) and "copy" in meta:
            copy_default = meta.get("copy") or ""
        slots = list(piece.get("slots") or [])
        thumb_slots = thumbs_for_row(slots, style_id)
        thumbs: list[str] = []
        for slot in thumb_slots:
            label = slot_label(str(slot.get("slot_id") or ""))
            src_name = Path(str(slot.get("source_file") or "")).name
            title = (
                f"{label} | {slot.get('source_file', '')} | "
                f"{slot.get('start_sec')}–{slot.get('end_sec')}s"
            )
            clip = str(slot.get("clip_file") or "")
            has = bool(clip) and (review_dir / clip).is_file()
            if has:
                thumbs.append(
                    f'<div class="thumb" title="{esc(title)}">'
                    f'<span class="tag">{esc(label)}</span>'
                    f'<img alt="{esc(label)}" src="{esc(clip)}"/>'
                    f'<span class="cap">{esc(src_name)} · {esc(slot.get("start_sec"))}s</span>'
                    f"</div>"
                )
            else:
                thumbs.append(
                    f'<div class="thumb miss" title="{esc(title)}">'
                    f'<span class="tag">{esc(label)}</span><span class="cap">无镜头</span></div>'
                )
        slot_controls: list[str] = []
        for slot in slots:
            sid = str(slot.get("slot_id") or "")
            label = slot_label(sid)
            title = (
                f"{label} | {slot.get('source_file', '')} | "
                f"{slot.get('start_sec')}–{slot.get('end_sec')}s"
            )
            slot_controls.append(
                f'<label class="slot-dis" title="{esc(title)}">'
                f'<input type="checkbox" data-slot="{esc(sid)}"/> 不用{esc(label)}'
                f"</label>"
            )
        out = str(piece.get("output_file") or "")
        out_name = Path(out).name or out
        final_thumb = str(piece.get("final_thumb") or "")
        video_ok = bool(out) and (review_dir / out).is_file()
        thumb_ok = bool(final_thumb) and (review_dir / final_thumb).is_file()
        if video_ok:
            poster = f' poster="{esc(final_thumb)}"' if thumb_ok else ""
            out_cell = (
                f'<video class="final" muted preload="metadata"{poster} '
                f'src="{esc(out)}" title="成片"></video>'
            )
        elif thumb_ok:
            out_cell = f'<img class="final" alt="成片预览" src="{esc(final_thumb)}"/>'
        else:
            out_cell = '<span class="miss">无成片</span>'
        checked = "checked" if enabled else ""
        enabled_flag = "true" if enabled else "false"
        body_rows.append(
            f'<tr data-id="{esc(pid)}" data-default-enabled="{enabled_flag}">'
            f'<td class="col-on"><input type="checkbox" class="en" {checked}/></td>'
            f'<td class="col-id"><div class="id">{esc(pid)}</div>'
            f'<div class="sub">{esc(piece.get("theme") or "")} · {esc(out_name)}</div>'
            f'<div class="sub path" title="{esc(out)}">{esc(out)}</div></td>'
            f'<td class="col-final">{out_cell}</td>'
            f'<td class="col-thumbs"><div class="thumbs">{"".join(thumbs)}</div>'
            f'<div class="slot-ops">{"".join(slot_controls)}</div></td>'
            f'<td class="col-copy"><textarea class="copy" rows="3" '
            f'placeholder="口播/字幕底稿…">{esc(copy_default)}</textarea></td>'
            f'<td class="col-note"><textarea class="note" rows="3" '
            f'placeholder="备注：换镜/不要这条…"></textarea></td>'
            f"</tr>"
        )

    rows_html = "".join(body_rows)
    count = len(pieces)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>工厂成片审片</title>
<style>
:root {{
  --bg:#0f1419; --row:#151c27; --row2:#1a2332; --line:#2a3544;
  --text:#e7ecf3; --muted:#8b9bb0; --accent:#3b82f6; --ok:#22c55e; --warn:#f59e0b;
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; font:13px/1.35 "Segoe UI", "Microsoft YaHei", "Noto Sans SC", sans-serif;
  background:var(--bg); color:var(--text);
}}
.bar {{
  position:sticky; top:0; z-index:20; display:flex; flex-wrap:wrap; gap:10px; align-items:center;
  padding:10px 14px; background:rgba(15,20,25,.94); border-bottom:1px solid var(--line);
}}
.bar h1 {{ margin:0; font-size:15px; font-weight:700; }}
.bar .meta {{ color:var(--muted); font-size:12px; }}
.bar button {{
  border:0; border-radius:8px; padding:7px 12px; font-weight:600; cursor:pointer;
  background:var(--accent); color:#fff;
}}
.bar button.secondary {{ background:#334155; }}
.bar #status {{ font-size:12px; color:var(--muted); }}
.bar #status.ok {{ color:var(--ok); }}
.bar #status.err {{ color:#f87171; }}
.warn {{
  margin:0; padding:8px 14px; background:#422006; color:#fde68a; font-size:12px;
  display:none;
}}
.warn.show {{ display:block; }}
.wrap {{ padding:8px 10px 40px; overflow-x:auto; }}
table {{ border-collapse:collapse; width:max-content; min-width:980px; }}
thead th {{
  position:sticky; top:52px; z-index:10; background:#111827; color:var(--muted);
  font-size:11px; font-weight:600; text-align:left; padding:6px 8px;
  border-bottom:1px solid var(--line);
}}
tbody tr {{ background:var(--row); border-bottom:1px solid var(--line); }}
tbody tr:nth-child(even) {{ background:var(--row2); }}
tbody tr.off {{ opacity:.55; }}
td {{ padding:6px 8px; vertical-align:middle; }}
.col-on {{ width:44px; text-align:center; }}
.col-id {{ width:168px; }}
.col-id .id {{ font-weight:700; font-size:13px; }}
.col-id .sub {{ color:var(--muted); font-size:11px; margin-top:2px; word-break:break-all; }}
.col-final {{ width:84px; }}
video.final, img.final {{
  width:72px; height:96px; object-fit:cover; background:#000; border-radius:6px; display:block;
}}
.thumbs {{ display:flex; gap:6px; flex-wrap:nowrap; }}
.thumb {{
  width:84px; position:relative; background:#000; border-radius:6px; overflow:hidden;
  border:1px solid var(--line);
}}
.thumb img {{ width:84px; height:84px; object-fit:cover; display:block; background:#000; }}
.thumb .tag {{
  position:absolute; left:3px; top:3px; z-index:1; font-size:10px; font-weight:700;
  background:var(--accent); color:#fff; padding:1px 4px; border-radius:3px;
}}
.thumb .cap {{
  display:block; font-size:9px; color:var(--muted); padding:2px 3px; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis; background:#0b1220;
}}
.thumb.miss {{ height:84px; display:flex; align-items:center; justify-content:center; color:var(--warn); }}
.slot-ops {{ display:flex; flex-wrap:wrap; gap:6px 10px; margin-top:4px; }}
.slot-dis {{ font-size:11px; color:var(--muted); white-space:nowrap; }}
.col-thumbs {{ white-space:nowrap; }}
.col-copy {{ width:260px; }}
.col-note {{ width:200px; }}
textarea.copy {{ width:250px; }}
textarea.note {{ width:190px; }}
textarea.copy, textarea.note {{
  min-height:64px; resize:vertical; border-radius:6px; border:1px solid var(--line);
  background:#0b1220; color:var(--text); padding:6px; font:12px/1.35 inherit;
}}
.miss {{ color:var(--warn); font-size:11px; }}
</style>
</head>
<body>
<div class="bar">
  <h1>工厂成片审片</h1>
  <span class="meta">{count}条 · {esc(when)} · 含主题文案</span>
  <button type="button" id="btnSave">保存备注</button>
  <button type="button" class="secondary" id="btnReload">重新加载</button>
  <span id="status"></span>
</div>
<p class="warn" id="fileWarn">当前是用 file:// 打开的，备注无法写入。请回到「社媒视频混剪」点「打开审片看板」，不要双击 html 文件。</p>
<div class="wrap">
<table>
<thead>
<tr>
  <th>启用</th>
  <th>成片</th>
  <th>成片预览</th>
  <th>关键槽位</th>
  <th>主题文案（口播/字幕底稿）</th>
  <th>备注</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>
<script>
const statusEl = document.getElementById('status');
const fileWarn = document.getElementById('fileWarn');
if (location.protocol === 'file:') fileWarn.classList.add('show');

function setStatus(msg, ok) {{
  statusEl.textContent = msg;
  statusEl.className = ok === true ? 'ok' : (ok === false ? 'err' : '');
}}

function collect() {{
  const pieces = {{}};
  document.querySelectorAll('tbody tr').forEach(tr => {{
    const id = tr.dataset.id;
    const enabled = tr.querySelector('.en').checked;
    const note = tr.querySelector('.note').value.trim();
    const copy = tr.querySelector('.copy').value.trim();
    const disabled_slots = [];
    tr.querySelectorAll('.slot-dis input').forEach(cb => {{
      if (cb.checked) disabled_slots.push(cb.dataset.slot);
    }});
    pieces[id] = {{ enabled, note, copy, disabled_slots }};
    tr.classList.toggle('off', !enabled);
  }});
  return {{ pieces }};
}}

function applyNotes(data) {{
  const pieces = (data && data.pieces) || {{}};
  document.querySelectorAll('tbody tr').forEach(tr => {{
    const id = tr.dataset.id;
    const meta = pieces[id] || {{}};
    const en = tr.querySelector('.en');
    if ('enabled' in meta) en.checked = !!meta.enabled;
    else en.checked = tr.dataset.defaultEnabled === 'true';
    tr.querySelector('.note').value = meta.note || '';
    if ('copy' in meta) tr.querySelector('.copy').value = meta.copy || '';
    const disabled = new Set(meta.disabled_slots || []);
    tr.querySelectorAll('.slot-dis input').forEach(cb => {{
      cb.checked = disabled.has(cb.dataset.slot);
    }});
    tr.classList.toggle('off', !en.checked);
  }});
}}

async function loadNotes() {{
  if (location.protocol === 'file:') {{
    setStatus('file:// 模式：请改用审片服务', false);
    return;
  }}
  try {{
    const r = await fetch('/api/notes', {{ cache: 'no-store' }});
    const data = await r.json();
    applyNotes(data);
    setStatus('已加载 review_notes.json', true);
  }} catch (e) {{
    setStatus('加载失败：' + e, false);
  }}
}}

async function saveNotes() {{
  if (location.protocol === 'file:') {{
    setStatus('请先在软件里点「打开审片看板」', false);
    fileWarn.classList.add('show');
    return;
  }}
  const payload = collect();
  try {{
    const r = await fetch('/api/save', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(payload),
    }});
    const data = await r.json();
    if (!data.ok) throw new Error(data.error || 'save failed');
    setStatus('已保存 review_notes.json', true);
  }} catch (e) {{
    setStatus('保存失败：' + e, false);
  }}
}}

document.getElementById('btnSave').onclick = saveNotes;
document.getElementById('btnReload').onclick = loadNotes;
document.querySelectorAll('tbody tr .en').forEach(en => {{
  en.addEventListener('change', () => {{
    en.closest('tr').classList.toggle('off', !en.checked);
  }});
}});
loadNotes();
</script>
</body>
</html>
"""


CSV_FIELDS = [
    "主题",
    "成片名",
    "启用",
    "成片文件",
    "槽位",
    "槽位ID",
    "源文件",
    "起秒",
    "止秒",
    "时长秒",
    "镜头文件",
    "主题文案",
    "备注",
]


def csv_rows(plan: dict, notes: dict) -> list[dict]:
    note_pieces = notes.get("pieces") if isinstance(notes.get("pieces"), dict) else {}
    rows: list[dict] = []
    for piece in plan.get("pieces") or []:
        pid = str(piece.get("id") or "")
        meta = note_pieces.get(pid) if isinstance(note_pieces.get(pid), dict) else {}
        enabled = piece.get("enabled", True)
        if isinstance(meta, dict) and "enabled" in meta:
            enabled = bool(meta.get("enabled"))
        copy_text = piece.get("copy") or ""
        if isinstance(meta, dict) and "copy" in meta:
            copy_text = meta.get("copy") or ""
        note_text = meta.get("note", "") if isinstance(meta, dict) else ""
        disabled = set(meta.get("disabled_slots") or []) if isinstance(meta, dict) else set()
        for slot in piece.get("slots") or []:
            sid = str(slot.get("slot_id") or "")
            extra = f"[槽位禁用:{sid}]" if sid in disabled else ""
            rows.append(
                {
                    "主题": piece.get("theme") or "",
                    "成片名": pid,
                    "启用": "是" if enabled else "否",
                    "成片文件": piece.get("output_file") or "",
                    "槽位": slot_label(sid),
                    "槽位ID": sid,
                    "源文件": slot.get("source_file") or "",
                    "起秒": slot.get("start_sec"),
                    "止秒": slot.get("end_sec"),
                    "时长秒": slot.get("duration_sec"),
                    "镜头文件": slot.get("clip_file") or "",
                    "主题文案": copy_text,
                    "备注": " ".join(x for x in [str(note_text or ""), extra] if x).strip(),
                }
            )
    return rows


def write_csv(path: Path, plan: dict, notes: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(csv_rows(plan, notes))
