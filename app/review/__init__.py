"""工厂成片审片，挂在 Windows 混剪导出后面。

导出成功后在输出目录 ``_review/`` 写 plan.json、槽位缩略图和 review.html。
「打开审片看板」在本机起一个只监听 127.0.0.1 的页面。保存备注写入
``_review/review_notes.json``（enabled、copy、disabled_slots）。

下次对同一输出目录再生成时：disabled_slots 会尽量避开对应源时间段
（只用真实素材，不编造镜头）。enabled 为 false 仍会重新导出该 mp4，
plan 里保持未启用。不依赖 Mac。
"""

from app.review.bundle import write_review_bundle
from app.review.server import open_review_board

__all__ = ["open_review_board", "write_review_bundle"]
