"""
Tool Call Layer — screen_capture.py

Captures a screenshot of the primary monitor and returns it as a
PIL Image.  Falls back gracefully when a display is unavailable
(headless / CI environments).
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image

logger = logging.getLogger(__name__)


def capture_screen() -> "Image | None":
    """
    Capture the primary screen and return a PIL ``Image``.

    Returns ``None`` when screen capture is not possible (e.g. headless
    environment or missing dependencies).
    """
    # Prefer mss for cross-platform, low-latency capture.
    try:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # index 1 → primary monitor
            raw = sct.grab(monitor)
            return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    except Exception as exc:  # pragma: no cover – environment-dependent
        logger.debug("mss capture failed (%s); trying PIL ImageGrab.", exc)

    # Fallback: PIL ImageGrab (Windows / macOS)
    try:
        from PIL import ImageGrab

        return ImageGrab.grab()
    except Exception as exc:  # pragma: no cover
        logger.warning("Screen capture unavailable: %s", exc)
        return None
