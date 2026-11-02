"""Thin adapter over Whisper-TikTok (Apache-2.0).

Vendor checkout: vendor/Whisper-TikTok → /workspace/vendor-whisper-tiktok

Reuse:
- edge-tts voice synthesis (voice_manager / TTS services)
- Whisper transcription → subtitle timing
- ffmpeg burn/mix helpers (prefer our hardened app.services.ffmpeg for Windows paths)

We do NOT import the full Streamlit app; only call library pieces behind our pipeline interfaces.
"""
from __future__ import annotations

import sys
from pathlib import Path

VENDOR_ROOT = Path(__file__).resolve().parents[2] / "vendor" / "Whisper-TikTok"


def ensure_vendor_on_path() -> Path:
    root = VENDOR_ROOT.resolve()
    if not root.exists():
        raise FileNotFoundError(
            f"Whisper-TikTok vendor missing at {root}. Clone MatteoFasulo/Whisper-TikTok there."
        )
    p = str(root)
    if p not in sys.path:
        sys.path.insert(0, p)
    return root


def list_edge_voices_hint() -> str:
    """Document default voices we map in app.pipeline.tts."""
    return "zh-CN-XiaoxiaoNeural | zh-CN-YunxiNeural"


def vendor_status() -> dict:
    root = VENDOR_ROOT.resolve()
    return {
        "vendor_path": str(root),
        "present": root.exists(),
        "package_dir": str(root / "whisper_tiktok") if root.exists() else None,
        "license": "Apache-2.0",
    }
