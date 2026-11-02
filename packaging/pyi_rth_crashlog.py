# PyInstaller runtime hook: persist uncaught exceptions next to the exe.
# Windowed builds have no console, and PyInstaller does not define exit().
import sys
import traceback
from pathlib import Path


def _remix_excepthook(exc_type, exc, tb):
    try:
        log = Path(sys.executable).resolve().parent / "remix_crash.log"
        log.write_text("".join(traceback.format_exception(exc_type, exc, tb)), encoding="utf-8")
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _remix_excepthook
