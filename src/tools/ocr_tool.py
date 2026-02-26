"""
Tool Call Layer — ocr_tool.py

Extracts text from a PIL Image using Tesseract OCR via pytesseract.
Returns an empty string when OCR is unavailable.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image

logger = logging.getLogger(__name__)


def extract_text(image: "Image", ocr_language: str = "chi_sim+eng") -> str:
    """
    Run OCR on *image* and return the recognised text.

    Parameters
    ----------
    image:
        A PIL ``Image`` obtained from :func:`~tools.screen_capture.capture_screen`.
    ocr_language:
        Tesseract language string (default: Simplified Chinese + English).

    Returns
    -------
    str
        The extracted text, or an empty string on failure.
    """
    if image is None:
        return ""
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

        # text: str = pytesseract.image_to_string(image, lang=ocr_language)
        text = pytesseract.image_to_string(image, lang="chi_sim+eng")
        return text.strip()
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""
