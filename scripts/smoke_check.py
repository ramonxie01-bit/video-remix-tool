"""Import-level smoke check (no ffmpeg required)."""
from app.models import JobConfig, MediaItem
from app.pipeline.highlights import pick_highlights
from app.pipeline.scenes import Scene
from pathlib import Path

print("models ok", JobConfig(inputs=[Path(".")], out_dir=Path("/tmp/out")))
print("highlights ok", pick_highlights([Scene(source=Path("a.mp4"), start=0, end=2, score=1)], 10))
print("smoke ok")
