"""ReySnap – core application coordinator.

:class:`ReySnapApp` is the central hub that wires together every
sub-module (capture, annotation, pin, colour-picker, ruler,
preferences, global shortcuts and system tray).

Window lifetime note: PySide6 widgets created without a parent are
destroyed when their Python reference is garbage-collected, so every
top-level window we open (overlay, editor, picker, ruler, pins) is
kept in a container here and removed when the window closes.
"""

import datetime
import logging
from typing import List

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QClipboard, QGuiApplication, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QWidget

from .config import AppConfig
from .i18n import set_language, tr
from .theme import apply_theme
from .tray import SystemTray
from .shortcuts import GlobalShortcutManager
from .capture.overlay import CaptureOverlay
from .capture.backend import get_capture_backend
from .annotation.editor import AnnotationEditor
from .pin.pin_window import PinWindow
from .colorpicker.picker import ColorPicker
from .ruler.ruler import RulerTool
from .preferences.dialog import PreferencesDialog

logger = logging.getLogger(__name__)


class ReySnapApp(QObject):
    """Main application controller – coordinates all modules."""

    # Emitted whenever a screenshot has been captured (before editing).
    screenshot_taken = Signal(QPixmap)

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.config = AppConfig()
        apply_theme(app, self.config.theme)
        set_language(self.config.language)
        self.tray = SystemTray(self)
        self.shortcut_manager = GlobalShortcutManager(self)
        self._active_pinned: List[PinWindow] = []
        # Keeps overlays / editors / pickers / rulers alive (see module docstring)
        self._windows: List[QWidget] = []
        self._overlay_open = False
        self._prefs_dialog: PreferencesDialog | None = None

        self.tray.capture_requested.connect(self.start_capture)
        self.tray.pin_requested.connect(self.start_pin_capture)
        self.tray.annotate_requested.connect(self.start_annotate)
        self.tray.color_picker_requested.connect(self.start_color_picker)
        self.tray.ruler_requested.connect(self.start_ruler)
        self.tray.preferences_requested.connect(self.show_preferences)
        self.tray.quit_requested.connect(self.quit)

        self._setup_shortcuts()

        self.config.save_directory.mkdir(parents=True, exist_ok=True)
        self.tray.show()

        logger.info("ReySnap %s started", self.config.get("_version", "1.0.0"))

    # ------------------------------------------------------------------
    # Window bookkeeping
    # ------------------------------------------------------------------

    def _track(self, window: QWidget) -> None:
        """Keep *window* alive until it is destroyed."""
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._windows.append(window)
        window.destroyed.connect(lambda *_: self._untrack(window))

    def _untrack(self, window: QWidget) -> None:
        try:
            self._windows.remove(window)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Shortcut management
    # ------------------------------------------------------------------

    def _setup_shortcuts(self) -> None:
        """Register global keyboard shortcuts from configuration."""
        self.shortcut_manager.register(
            "capture", self.config.get_shortcut("capture"), self.start_capture
        )
        self.shortcut_manager.register(
            "pin", self.config.get_shortcut("pin"), self.start_pin_capture
        )
        self.shortcut_manager.register(
            "color_picker", self.config.get_shortcut("color_picker"), self.start_color_picker
        )
        self.shortcut_manager.register(
            "ruler", self.config.get_shortcut("ruler"), self.start_ruler
        )
        self.shortcut_manager.register(
            "annotate", self.config.get_shortcut("annotate"), self.start_annotate
        )

    def _reload_shortcuts(self) -> None:
        """Unregister all shortcuts and re-register from current config."""
        self.shortcut_manager.unregister_all()
        self._setup_shortcuts()
        logger.info("Shortcuts reloaded")

    # ------------------------------------------------------------------
    # Capture workflow (PixPin-style overlay)
    # ------------------------------------------------------------------

    def start_capture(self) -> None:
        """F1 – open the capture overlay (Enter/double-click copies)."""
        self._open_overlay(default_action="copy")

    def start_pin_capture(self) -> None:
        """F3 – pin the clipboard image if there is one, else capture-to-pin.

        Mirrors PixPin: F3 pastes the clipboard as a pin; when the
        clipboard has no image, a capture starts whose default action
        is pinning.
        """
        clipboard = QGuiApplication.clipboard()
        image = clipboard.image()
        if not image.isNull():
            self._pin_screenshot(QPixmap.fromImage(image))
            return
        self._open_overlay(default_action="pin")

    def _open_overlay(self, default_action: str) -> None:
        if self._overlay_open:
            logger.debug("Capture overlay already open – ignoring")
            return
        # A modal dialog (file chooser, message box…) blocks input to
        # every other window: opening the fullscreen overlay under it
        # would leave the screen covered and unresponsive.
        if QApplication.activeModalWidget() is not None:
            logger.debug("Modal dialog active – ignoring capture request")
            return

        backend = get_capture_backend()
        overlay = CaptureOverlay(backend, default_action=default_action)
        self._overlay_open = True
        self._track(overlay)
        overlay.finished.connect(self._on_capture_finished)
        overlay.cancelled.connect(self._on_capture_cancelled)
        overlay.show()

    def _on_capture_finished(self, action: str, pixmap: QPixmap) -> None:
        self._overlay_open = False
        if pixmap.isNull():
            logger.warning("Capture produced a null pixmap")
            return

        self.screenshot_taken.emit(pixmap)

        if action == "pin":
            self._pin_screenshot(pixmap)
            if self.config.copy_to_clipboard_after_capture:
                QApplication.clipboard().setPixmap(pixmap)
        elif action == "save":
            self._save_screenshot_dialog(pixmap)
        elif action == "ocr":
            self._run_ocr(pixmap)
        else:  # "copy"
            QApplication.clipboard().setPixmap(pixmap)
            logger.info("Screenshot copied to clipboard (%dx%d)", pixmap.width(), pixmap.height())

    def _on_capture_cancelled(self) -> None:
        self._overlay_open = False
        logger.debug("Capture cancelled")

    # ------------------------------------------------------------------
    # Annotation editor (for image files opened from the tray)
    # ------------------------------------------------------------------

    def _open_annotation_editor(self, pixmap: QPixmap) -> None:
        editor = AnnotationEditor(pixmap, self.config)
        self._track(editor)
        editor.save_requested.connect(self._save_screenshot)
        editor.pin_requested.connect(self._pin_screenshot)
        editor.show()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save_screenshot_dialog(self, pixmap: QPixmap) -> None:
        """Ask where to save *pixmap*, defaulting to the configured directory."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fmt = self.config.save_format
        suggested = str(self.config.save_directory / f"reysnap_{timestamp}.{fmt}")
        path, _ = QFileDialog.getSaveFileName(
            None,
            tr("Guardar captura"),
            suggested,
            "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp);;WebP (*.webp)",
        )
        if path:
            self._save_screenshot(pixmap, path)

    def _save_screenshot(self, pixmap: QPixmap, path: str | None = None) -> None:
        """Save *pixmap* to *path* (auto-generated if *None*)."""
        if path is None:
            save_dir = self.config.save_directory
            fmt = self.config.save_format
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = str(save_dir / f"reysnap_{timestamp}.{fmt}")

        ok = pixmap.save(path)
        if ok:
            logger.info("Screenshot saved to %s", path)
        else:
            logger.error("Failed to save screenshot to %s", path)

        if self.config.copy_to_clipboard_after_capture:
            clipboard: QClipboard = QApplication.clipboard()
            clipboard.setPixmap(pixmap)

    # ------------------------------------------------------------------
    # OCR
    # ------------------------------------------------------------------

    def _run_ocr(self, pixmap: QPixmap) -> None:
        """Recognise text in *pixmap*, copy it, and show it in a window."""
        from PySide6.QtWidgets import QMessageBox

        from .ocr import ocr_pixmap

        text, error = ocr_pixmap(pixmap)
        if error is not None:
            QMessageBox.warning(None, tr("ReySnap – OCR"), error)
            return
        if not text:
            QMessageBox.information(
                None, tr("ReySnap – OCR"), tr("No se reconoció ningún texto en la selección.")
            )
            return

        QGuiApplication.clipboard().setText(text)
        self._show_ocr_result(text)
        logger.info("OCR recognised %d characters (copied to clipboard)", len(text))

    def _show_ocr_result(self, text: str) -> None:
        from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

        window = QWidget()
        window.setWindowTitle(tr("ReySnap – Texto reconocido"))
        window.resize(460, 320)
        layout = QVBoxLayout(window)

        info = QLabel(tr("El texto ya está copiado al portapapeles. Puedes editarlo aquí:"))
        info.setWordWrap(True)
        layout.addWidget(info)

        edit = QPlainTextEdit(text)
        layout.addWidget(edit)

        btn = QPushButton(tr("Copiar de nuevo y cerrar"))
        btn.clicked.connect(
            lambda: (QGuiApplication.clipboard().setText(edit.toPlainText()), window.close())
        )
        layout.addWidget(btn)

        self._track(window)
        window.show()

    # ------------------------------------------------------------------
    # Pin to screen
    # ------------------------------------------------------------------

    def _pin_screenshot(self, pixmap: QPixmap) -> None:
        """Pin *pixmap* to the screen as an always-on-top overlay."""
        pin = PinWindow(pixmap, self.config)
        self._active_pinned.append(pin)

        pin.closed.connect(
            lambda p=pin: (
                self._active_pinned.remove(p) if p in self._active_pinned else None
            )
        )

        pin.show()
        logger.debug("Pinned screenshot (%d active)", len(self._active_pinned))

    # ------------------------------------------------------------------
    # Colour picker
    # ------------------------------------------------------------------

    def start_color_picker(self) -> None:
        picker = ColorPicker()
        self._track(picker)
        picker.color_picked.connect(self._on_color_picked)
        picker.showFullScreen()

    def _on_color_picked(self, color) -> None:  # QColor
        hex_color = color.name()  # e.g. "#ff6600"
        QGuiApplication.clipboard().setText(hex_color)
        logger.info("Color picked: %s (copied to clipboard)", hex_color)

    # ------------------------------------------------------------------
    # Ruler
    # ------------------------------------------------------------------

    def start_ruler(self) -> None:
        ruler = RulerTool()
        self._track(ruler)
        ruler.showFullScreen()

    # ------------------------------------------------------------------
    # Annotate (open file)
    # ------------------------------------------------------------------

    def start_annotate(self) -> None:
        """Open a file dialog to load an image for annotation."""
        path, _ = QFileDialog.getOpenFileName(
            None,
            tr("Abrir imagen para anotar"),
            str(self.config.save_directory),
            tr("Imágenes") + " (*.png *.jpg *.jpeg *.bmp *.webp);;" + tr("Todos los archivos") + " (*)",
        )
        if path:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self._open_annotation_editor(pixmap)
            else:
                logger.warning("Could not load image: %s", path)

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    def show_preferences(self) -> None:
        # Single instance, non-modal: a modal dialog would freeze a
        # capture started via global hotkey while it is open.
        if self._prefs_dialog is not None:
            self._prefs_dialog.raise_()
            self._prefs_dialog.activateWindow()
            return

        dialog = PreferencesDialog(self.config)
        self._prefs_dialog = dialog
        dialog.shortcuts_changed.connect(self._reload_shortcuts)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.finished.connect(self._on_prefs_closed)
        dialog.show()

    def _on_settings_saved(self) -> None:
        apply_theme(self.app, self.config.theme)
        set_language(self.config.language)
        # The tray menu is long-lived: rebuild it in the new language.
        self.tray.retranslate()

    def _on_prefs_closed(self, *_args) -> None:
        if self._prefs_dialog is not None:
            self._prefs_dialog.deleteLater()
            self._prefs_dialog = None

    # ------------------------------------------------------------------
    # Quit
    # ------------------------------------------------------------------

    def quit(self) -> None:
        """Gracefully shut down ReySnap."""
        logger.info("Shutting down ReySnap…")

        self.shortcut_manager.unregister_all()

        for pin in list(self._active_pinned):
            pin.close()
        self._active_pinned.clear()

        for window in list(self._windows):
            window.close()
        self._windows.clear()

        QApplication.instance().quit()
