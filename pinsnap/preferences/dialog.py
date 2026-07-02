"""PinSnap – preferences dialog.

:class:`PreferencesDialog` presents a tabbed dialog with:

* **General** – save directory, format, clipboard options, capture delay
* **Shortcuts** – edit global keyboard shortcuts
* **Pinned** – default opacity and border for pinned windows
* **Advanced** – autostart, theme, language
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import (
    DEFAULT_SHORTCUTS,
    AppConfig,
)

logger = logging.getLogger(__name__)


class PreferencesDialog(QDialog):
    """Preferences dialog for PinSnap.

    Signals
    -------
    shortcuts_changed()
        Emitted after the user saves modified shortcuts.
    """

    shortcuts_changed = Signal()
    settings_saved = Signal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._pending_shortcuts: Dict[str, str] = copy.deepcopy(
            config.get("shortcuts", DEFAULT_SHORTCUTS)
        )

        self.setWindowTitle("PinSnap – Preferencias")
        self.setMinimumSize(520, 480)
        # Non-modal: a modal dialog blocks the whole app, so a capture
        # started via global hotkey would freeze under it.
        self.setModal(False)

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._build_general_tab()
        self._build_shortcuts_tab()
        self._build_pinned_tab()
        self._build_advanced_tab()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_reset_shortcuts = QPushButton("Restablecer atajos")
        self._btn_reset_shortcuts.clicked.connect(self._reset_shortcuts)
        btn_layout.addWidget(self._btn_reset_shortcuts)

        self._btn_cancel = QPushButton("Cancelar")
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)

        self._btn_save = QPushButton("Guardar")
        self._btn_save.setDefault(True)
        self._btn_save.clicked.connect(self._save)
        btn_layout.addWidget(self._btn_save)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # General tab
    # ------------------------------------------------------------------

    def _build_general_tab(self) -> None:
        page = QWidget()
        form = QFormLayout(page)

        # Save directory
        dir_layout = QHBoxLayout()
        self._dir_edit = QLineEdit(str(self._config.save_directory))
        self._dir_edit.setReadOnly(True)
        dir_layout.addWidget(self._dir_edit)
        btn_browse = QPushButton("Examinar…")
        btn_browse.clicked.connect(self._browse_dir)
        dir_layout.addWidget(btn_browse)
        form.addRow("Carpeta de guardado:", dir_layout)

        # Save format
        self._format_combo = QComboBox()
        self._format_combo.addItems(["png", "jpg", "bmp", "webp"])
        self._format_combo.setCurrentText(self._config.get("save_format", "png"))
        form.addRow("Formato de imagen:", self._format_combo)

        # Copy to clipboard
        self._cb_clipboard = QCheckBox("Copiar al portapapeles tras capturar")
        self._cb_clipboard.setChecked(self._config.get("copy_to_clipboard_after_capture", True))
        form.addRow("", self._cb_clipboard)

        # Show cursor
        self._cb_cursor = QCheckBox("Mostrar cursor en la captura")
        self._cb_cursor.setChecked(self._config.get("show_cursor_in_capture", False))
        form.addRow("", self._cb_cursor)

        # Capture delay
        self._delay_spin = QSpinBox()
        self._delay_spin.setRange(0, 30)
        self._delay_spin.setSuffix(" s")
        self._delay_spin.setValue(self._config.get("capture_delay", 0))
        form.addRow("Retardo de captura:", self._delay_spin)

        self._tabs.addTab(page, "General")

    # ------------------------------------------------------------------
    # Shortcuts tab
    # ------------------------------------------------------------------

    def _build_shortcuts_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        info = QLabel(
            "Haga clic en el campo de atajo y pulse la combinación de teclas deseada."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info)

        self._shortcut_edits: Dict[str, QKeySequenceEdit] = {}
        form = QFormLayout()

        labels = {
            "capture": "Capturar pantalla:",
            "pin": "Anclar captura:",
            "color_picker": "Selector de color:",
            "ruler": "Regla:",
            "annotate": "Anotar imagen:",
        }

        for action, label_text in labels.items():
            seq = self._pending_shortcuts.get(action, "")
            edit = QKeySequenceEdit(QKeySequence(seq))
            edit.keySequenceChanged.connect(
                lambda ks, a=action: self._on_shortcut_edited(a, ks)
            )
            self._shortcut_edits[action] = edit
            form.addRow(label_text, edit)

        layout.addLayout(form)
        layout.addStretch()

        self._tabs.addTab(page, "Atajos")

    # ------------------------------------------------------------------
    # Pinned tab
    # ------------------------------------------------------------------

    def _build_pinned_tab(self) -> None:
        page = QWidget()
        form = QFormLayout(page)

        # Opacity
        self._opacity_spin = QSpinBox()
        self._opacity_spin.setRange(10, 100)
        self._opacity_spin.setSuffix(" %")
        self._opacity_spin.setValue(self._config.get("pin_opacity", 90))
        form.addRow("Opacidad predeterminada:", self._opacity_spin)

        # Border
        self._cb_border = QCheckBox("Mostrar borde en ventanas ancladas")
        self._cb_border.setChecked(self._config.get("pin_border", True))
        form.addRow("", self._cb_border)

        self._tabs.addTab(page, "Ancladas")

    # ------------------------------------------------------------------
    # Advanced tab
    # ------------------------------------------------------------------

    def _build_advanced_tab(self) -> None:
        page = QWidget()
        form = QFormLayout(page)

        # Theme
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["system", "light", "dark"])
        theme_labels = {"system": "Sistema", "light": "Claro", "dark": "Oscuro"}
        idx = self._theme_combo.findText(self._config.get("theme", "system"))
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        form.addRow("Tema:", self._theme_combo)

        # Language
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["es", "en"])
        lang_labels = {"es": "Español", "en": "English"}
        idx = self._lang_combo.findText(self._config.get("language", "es"))
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        form.addRow("Idioma:", self._lang_combo)

        # Autostart
        self._cb_autostart = QCheckBox("Iniciar automáticamente al iniciar sesión")
        self._cb_autostart.setChecked(self._config.get("autostart", False))
        form.addRow("", self._cb_autostart)

        self._tabs.addTab(page, "Avanzado")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta de guardado", self._dir_edit.text()
        )
        if path:
            self._dir_edit.setText(path)

    def _on_shortcut_edited(self, action: str, sequence: QKeySequence) -> None:
        self._pending_shortcuts[action] = sequence.toString()

    def _reset_shortcuts(self) -> None:
        self._pending_shortcuts = copy.deepcopy(DEFAULT_SHORTCUTS)
        for action, edit in self._shortcut_edits.items():
            seq = self._pending_shortcuts.get(action, "")
            edit.setKeySequence(QKeySequence(seq))

    def _check_shortcut_conflicts(self) -> bool:
        """Return True if there are duplicate shortcuts."""
        seen: Dict[str, str] = {}
        for action, seq in self._pending_shortcuts.items():
            if not seq:
                continue
            if seq in seen:
                QMessageBox.warning(
                    self,
                    "Conflicto de atajos",
                    f'El atajo "{seq}" está asignado tanto a '
                    f'"{action}" como a "{seen[seq]}".\n'
                    f"Por favor, elija atajos diferentes.",
                )
                return False
            seen[seq] = action
        return True

    def _save(self) -> None:
        """Persist all settings and close."""
        if not self._check_shortcut_conflicts():
            return

        old_shortcuts = self._config.get("shortcuts", {})
        shortcuts_changed = old_shortcuts != self._pending_shortcuts

        # General
        self._config.save_directory = Path(self._dir_edit.text())
        self._config.set("save_format", self._format_combo.currentText())
        self._config.set("copy_to_clipboard_after_capture", self._cb_clipboard.isChecked())
        self._config.set("show_cursor_in_capture", self._cb_cursor.isChecked())
        self._config.set("capture_delay", self._delay_spin.value())

        # Shortcuts
        self._config.set("shortcuts", copy.deepcopy(self._pending_shortcuts))

        # Pinned
        self._config.set("pin_opacity", self._opacity_spin.value())
        self._config.set("pin_border", self._cb_border.isChecked())

        # Advanced
        self._config.set("theme", self._theme_combo.currentText())
        self._config.set("language", self._lang_combo.currentText())
        self._config.autostart = self._cb_autostart.isChecked()

        logger.info("Preferences saved")

        if shortcuts_changed:
            self.shortcuts_changed.emit()
        self.settings_saved.emit()

        self.accept()