"""Fixed short-form duration templates for Douyin / Xiaohongshu."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RemixTemplate:
    duration_sec: int
    hook_sec: float
    label: str
    tip: str


TEMPLATES: dict[int, RemixTemplate] = {
    10: RemixTemplate(10, 2.0, "10s 钩子", "前2秒强开场，只留1个卖点"),
    15: RemixTemplate(15, 3.0, "15s 快剪", "前3秒钩子 + 车间实拍 + 收口CTA"),
    30: RemixTemplate(30, 3.0, "30s 讲解", "钩子→流程3步→下单/询盘"),
}


def get_template(duration_sec: int) -> RemixTemplate:
    if duration_sec not in TEMPLATES:
        raise ValueError(f"unsupported duration: {duration_sec}")
    return TEMPLATES[duration_sec]
