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

from .i18n import tr

logger = logging.getLogger(__name__)

# Preferred recognition languages, best first.  The actual string passed
# to tesseract is the intersection with what is installed on the system.
PREFERRED_LANGS = ["spa", "eng", "chi_sim", "chi_tra", "rus"]

_APT_PACKAGES = (
    "tesseract-ocr tesseract-ocr-spa tesseract-ocr-chi-sim "
    "tesseract-ocr-chi-tra tesseract-ocr-rus"
)


def _install_hint() -> str:
    return (
        tr("OCR no disponible. Instálalo con:") + "\n"
        f"  sudo apt install {_APT_PACKAGES}\n"
        "  .venv/bin/pip install pytesseract"
    )


def _lang_string() -> str:
    """Return the '+'-joined preferred languages that are installed."""
    try:
        import pytesseract
        available = set(pytesseract.get_languages(config=""))
    except Exception:
        return "eng"
    langs = [lang for lang in PREFERRED_LANGS if lang in available]
    return "+".join(langs) if langs else "eng"


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
    when OCR is unavailable or fails.  Uses every installed language
    from :data:`PREFERRED_LANGS` (es/en/zh-Hans/zh-Hant/ru) and falls
    back to English-only as a last resort.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None, _install_hint()

    if shutil.which("tesseract") is None:
        return None, _install_hint()

    # QPixmap → PNG bytes → PIL image
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buf, "PNG")
    image = Image.open(io.BytesIO(bytes(buf.data())))

    last_error: Optional[Exception] = None
    for lang in (_lang_string(), "eng"):
        try:
            text = pytesseract.image_to_string(image, lang=lang)
            return text.strip(), None
        except Exception as exc:  # missing language pack, etc.
            last_error = exc

    logger.warning("OCR failed: %s", last_error)
    return None, tr("El OCR falló: {error}").format(error=last_error)
