import json
import os
import copy
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default PixPin-compatible shortcuts.  PixPin's documented defaults
# are Ctrl+1 (screenshot) and Ctrl+2 (pin); the rest are PinSnap
# additions since PixPin does not document defaults for them.
DEFAULT_SHORTCUTS: Dict[str, str] = {
    "capture": "Ctrl+1",
    "pin": "Ctrl+2",
    "color_picker": "Ctrl+Shift+C",
    "ruler": "Ctrl+Shift+R",
    "annotate": "Ctrl+Shift+E",
}

# Default settings
DEFAULT_SETTINGS: Dict[str, Any] = {
    "shortcuts": DEFAULT_SHORTCUTS.copy(),
    "save_directory": str(Path.home() / "Pictures" / "PinSnap"),
    "save_format": "png",
    "copy_to_clipboard_after_capture": True,
    "show_cursor_in_capture": False,
    "pin_opacity": 90,
    "pin_border": True,
    "autostart": False,
    "theme": "system",  # system, light, dark
    "language": "es",
    "capture_delay": 0,
}

# Keys that should be validated / clamped
_INT_KEYS = {"pin_opacity", "capture_delay"}
_BOOL_KEYS = {
    "copy_to_clipboard_after_capture",
    "show_cursor_in_capture",
    "pin_border",
    "autostart",
}
_STR_ENUM_KEYS = {
    "save_format": ("png", "jpg", "bmp", "webp"),
    "theme": ("system", "light", "dark"),
    "language": ("es", "en", "zh_CN", "zh_TW", "ru"),
}


class AppConfig:
    """Manages application configuration with JSON persistence.

    Settings are loaded from ``~/.config/pinsnap/config.json`` on
    instantiation.  Missing keys are back-filled from
    :data:`DEFAULT_SETTINGS` so that the file always contains a
    complete, valid configuration after the first save.
    """

    CONFIG_DIR = Path.home() / ".config" / "pinsnap"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    def __init__(self) -> None:
        self._settings: Dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load settings from disk, creating defaults if needed."""
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as fh:
                    disk_settings: Dict[str, Any] = json.load(fh)
                # Merge: start from defaults, overlay what is on disk so
                # that new default keys added in later versions appear
                # automatically.
                merged = copy.deepcopy(DEFAULT_SETTINGS)
                merged.update(disk_settings)
                self._settings = merged
                logger.debug("Loaded config from %s", self.CONFIG_FILE)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load config: %s – using defaults", exc)
                self._settings = copy.deepcopy(DEFAULT_SETTINGS)
                self._save()
        else:
            self._settings = copy.deepcopy(DEFAULT_SETTINGS)
            self._save()
            logger.debug("Created default config at %s", self.CONFIG_FILE)

        # Validate / clamp values
        self._validate()

    def _validate(self) -> None:
        """Clamp or fix values that may have been corrupted."""
        # Integer clamping
        if "pin_opacity" in self._settings:
            self._settings["pin_opacity"] = max(10, min(100, int(self._settings["pin_opacity"])))
        if "capture_delay" in self._settings:
            self._settings["capture_delay"] = max(0, min(30, int(self._settings["capture_delay"])))

        # Enum strings
        for key, allowed in _STR_ENUM_KEYS.items():
            if key in self._settings and self._settings[key] not in allowed:
                self._settings[key] = DEFAULT_SETTINGS[key]

    def _save(self) -> None:
        """Persist current settings to disk."""
        try:
            self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            tmp_path = self.CONFIG_FILE.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(self._settings, fh, indent=2, ensure_ascii=False)
            # Atomic-ish: rename temp to real
            os.replace(tmp_path, self.CONFIG_FILE)
            logger.debug("Saved config to %s", self.CONFIG_FILE)
        except OSError as exc:
            logger.error("Failed to save config: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value and persist."""
        self._settings[key] = value
        self._save()

    # ------------------------------------------------------------------
    # Shortcut helpers
    # ------------------------------------------------------------------

    def get_shortcut(self, action: str) -> str:
        """Return the key-sequence string for *action*.

        Falls back to :data:`DEFAULT_SHORTCUTS` when the action is not
        present in the user's configuration.
        """
        shortcuts = self._settings.get("shortcuts", DEFAULT_SHORTCUTS)
        return shortcuts.get(action, DEFAULT_SHORTCUTS.get(action, ""))

    def set_shortcut(self, action: str, key_sequence: str) -> None:
        """Set a shortcut key-sequence and persist."""
        shortcuts = self._settings.get("shortcuts", copy.deepcopy(DEFAULT_SHORTCUTS))
        shortcuts[action] = key_sequence
        self.set("shortcuts", shortcuts)

    def reset_shortcuts(self) -> None:
        """Restore all shortcuts to their default values."""
        self.set("shortcuts", copy.deepcopy(DEFAULT_SHORTCUTS))

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def save_directory(self) -> Path:
        """Path to the directory where screenshots are saved."""
        return Path(self._settings.get("save_directory", str(Path.home() / "Pictures" / "PinSnap")))

    @save_directory.setter
    def save_directory(self, value: Path) -> None:
        self.set("save_directory", str(value))

    @property
    def save_format(self) -> str:
        return self._settings.get("save_format", "png")

    @property
    def pin_opacity(self) -> int:
        return self._settings.get("pin_opacity", 90)

    @property
    def pin_border(self) -> bool:
        return self._settings.get("pin_border", True)

    @property
    def copy_to_clipboard_after_capture(self) -> bool:
        return self._settings.get("copy_to_clipboard_after_capture", True)

    @property
    def show_cursor_in_capture(self) -> bool:
        return self._settings.get("show_cursor_in_capture", False)

    @property
    def theme(self) -> str:
        return self._settings.get("theme", "system")

    @property
    def language(self) -> str:
        return self._settings.get("language", "es")

    @property
    def capture_delay(self) -> int:
        return self._settings.get("capture_delay", 0)

    @property
    def autostart(self) -> bool:
        return self._settings.get("autostart", False)

    @autostart.setter
    def autostart(self, value: bool) -> None:
        self.set("autostart", bool(value))
        self._update_autostart_desktop_file()

    # ------------------------------------------------------------------
    # Autostart (XDG)
    # ------------------------------------------------------------------

    def _update_autostart_desktop_file(self) -> None:
        """Create or remove the XDG autostart desktop entry."""
        autostart_dir = Path.home() / ".config" / "autostart"
        desktop_path = autostart_dir / "pinsnap.desktop"

        if self._settings.get("autostart", False):
            autostart_dir.mkdir(parents=True, exist_ok=True)
            # Point Exec at the interpreter actually running PinSnap so
            # autostart works from a venv without anything on $PATH.
            import sys
            exec_cmd = f'"{sys.executable}" -m pinsnap'
            desktop_path.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=PinSnap\n"
                f"Exec={exec_cmd}\n"
                "Icon=pinsnap\n"
                "Terminal=false\n"
                "Categories=Utility;\n"
                "X-GNOME-Autostart-enabled=true\n",
                encoding="utf-8",
            )
        else:
            if desktop_path.exists():
                desktop_path.unlink()