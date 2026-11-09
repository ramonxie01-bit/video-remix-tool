"""槽位 id 与中文标签。只给真实用到的镜头编号，不补空槽。"""
from __future__ import annotations

# 与 Mac 审片页同一套叫法。
SLOT_CN: dict[str, str] = {
    "hook": "钩子",
    "show": "展示",
    "detail": "细节",
    "close": "收尾",
    "ask": "提问",
    "explain": "讲解",
    "tip": "要点",
    "pain": "痛点误区",
    "twist": "反转",
    "proof": "展示证据",
    "power": "实力开场",
    "result": "过程结果",
    "broll": "空镜",
}

# reverse_hook 对齐 Mac「反向钩子」；factory 对齐「实力展示」的四段。
# 其余类型用钩子/展示/讲解，多出来的镜头才标空镜。
STYLE_SLOT_IDS: dict[str, tuple[str, ...]] = {
    "reverse_hook": ("pain", "twist", "proof", "close"),
    "factory": ("power", "detail", "result", "close"),
    "seed": ("hook", "show", "detail", "close"),
    "explainer": ("ask", "explain", "tip", "close"),
}

# 10/15/30 固定成 v01/v02/v03，只重导 15s 时仍对得上上次的备注。
DURATION_INDEX: dict[int, int] = {10: 1, 15: 2, 30: 3}


def slot_label(slot_id: str) -> str:
    if slot_id in SLOT_CN:
        return SLOT_CN[slot_id]
    if slot_id.startswith("broll"):
        suffix = slot_id[5:]
        return f"空镜{suffix}" if suffix else "空镜"
    return slot_id


def assign_slot_ids(style_id: str, count: int) -> list[str]:
    """Map ``count`` real clips onto slot ids. Never invents an extra slot."""
    if count <= 0:
        return []
    primary = STYLE_SLOT_IDS.get(style_id or "")
    if not primary:
        ids: list[str] = []
        for i in range(count):
            if i == 0:
                ids.append("hook")
            elif i == count - 1:
                ids.append("close")
            elif i == 1:
                ids.append("broll")
            else:
                ids.append(f"broll{i}")
        return ids
    if count == 1:
        return [primary[0]]
    head = [sid for sid in primary if sid != "close"]
    tail = "close" if "close" in primary else head[-1]
    if count - 1 <= len(head):
        return head[: count - 1] + [tail]
    ids = list(head)
    extra = count - 1 - len(head)
    for i in range(1, extra + 1):
        ids.append(f"broll{i}")
    ids.append(tail)
    return ids


def piece_id_for(theme: str, duration_sec: int) -> str:
    idx = DURATION_INDEX.get(int(duration_sec))
    if idx is None:
        idx = int(duration_sec)
    return f"{theme}_v{idx:02d}"


def thumbs_for_row(slots: list[dict], style_id: str) -> list[dict]:
    """Up to four thumbs. When there are more cuts, keep the named slots and 收尾."""
    if len(slots) <= 4:
        return list(slots)
    primary = [sid for sid in STYLE_SLOT_IDS.get(style_id, ()) if sid != "close"]
    by_id: dict[str, dict] = {}
    for slot in slots:
        by_id.setdefault(str(slot.get("slot_id")), slot)
    chosen: list[dict] = []
    for sid in primary:
        slot = by_id.get(sid)
        if slot is not None and len(chosen) < 3:
            chosen.append(slot)
    for slot in slots:
        if len(chosen) >= 3:
            break
        if slot in chosen or slot.get("slot_id") == "close":
            continue
        chosen.append(slot)
    close = by_id.get("close")
    if close is not None:
        chosen.append(close)
    elif slots[-1] not in chosen:
        chosen.append(slots[-1])
    return chosen[:4]
