"""PinSnap – local text recognition (OCR) via Tesseract.

Everything runs locally (like PixPin's OCR).  The heavy lifting is
done by the ``tesseract`` binary through :mod:`pytesseract`; both are
optional dependencies, so every entry point degrades gracefully with
an actionable error message instead of crashing.
"""

from __future__ import annotations

import io
import logging
import shutil
from typing import Optional, Tuple

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QPixmap

logger = logging.getLogger(__name__)

_INSTALL_HINT = (
    "OCR no disponible. Instálalo con:\n"
    "  sudo apt install tesseract-ocr tesseract-ocr-spa\n"
    "  .venv/bin/pip install pytesseract"
)


def ocr_available() -> bool:
    """True when both pytesseract and the tesseract binary are present."""
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def ocr_pixmap(pixmap: QPixmap) -> Tuple[Optional[str], Optional[str]]:
    """Recognise text in *pixmap*.

    Returns ``(text, None)`` on success or ``(None, error_message)``
    when OCR is unavailable or fails.  Tries Spanish+English first and
    falls back to English-only if the Spanish language pack is missing.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None, _INSTALL_HINT

    if shutil.which("tesseract") is None:
        return None, _INSTALL_HINT

    # QPixmap → PNG bytes → PIL image
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buf, "PNG")
    image = Image.open(io.BytesIO(bytes(buf.data())))

    last_error: Optional[Exception] = None
    for lang in ("spa+eng", "eng"):
        try:
            text = pytesseract.image_to_string(image, lang=lang)
            return text.strip(), None
        except Exception as exc:  # missing language pack, etc.
            last_error = exc

    logger.warning("OCR failed: %s", last_error)
    return None, f"El OCR falló: {last_error}"
