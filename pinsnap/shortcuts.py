"""PinSnap – global keyboard shortcut manager.

Uses ``pynput`` to listen for key-presses at the OS level (works on
X11; Wayland support is best-effort since :mod:`pynput` itself has
limited Wayland support).

Design notes
------------
* pynput delivers key events on its own background thread.  Qt GUI
  code must only run on the main thread, so the listener never calls
  callbacks directly: it emits :attr:`GlobalShortcutManager.shortcut_triggered`,
  which Qt automatically queues onto the main thread, and the manager's
  own slot then invokes the registered callback there.
* A hotkey fires once per physical press: after triggering, the combo
  is marked as "fired" and will not fire again until at least one of
  its keys is released (prevents auto-repeat storms).

Usage::

    mgr = GlobalShortcutManager(parent)
    mgr.register("capture", "F1", my_callback)
    # …
    mgr.unregister_all()
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, FrozenSet, Set

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

try:
    from pynput import keyboard

    _PYNPUT_AVAILABLE = True
except ImportError:
    keyboard = None  # type: ignore[assignment]
    _PYNPUT_AVAILABLE = False
    logger.warning("pynput is not installed – global shortcuts will be disabled")


def _build_key_maps():
    """Build the modifier maps only when pynput imported successfully."""
    mod_map: Dict[str, Any] = {
        "ctrl": keyboard.Key.ctrl,
        "control": keyboard.Key.ctrl,
        "shift": keyboard.Key.shift,
        "alt": keyboard.Key.alt,
        "super": keyboard.Key.cmd,
        "win": keyboard.Key.cmd,
        "meta": keyboard.Key.cmd,
    }
    generic: Dict[Any, Any] = {
        keyboard.Key.ctrl_l: keyboard.Key.ctrl,
        keyboard.Key.ctrl_r: keyboard.Key.ctrl,
        keyboard.Key.shift_l: keyboard.Key.shift,
        keyboard.Key.shift_r: keyboard.Key.shift,
        keyboard.Key.alt_l: keyboard.Key.alt,
        keyboard.Key.alt_gr: keyboard.Key.alt,
        keyboard.Key.alt_r: keyboard.Key.alt,
        keyboard.Key.cmd_l: keyboard.Key.cmd,
        keyboard.Key.cmd_r: keyboard.Key.cmd,
    }
    return mod_map, generic


if _PYNPUT_AVAILABLE:
    _MOD_MAP, _GENERIC_MODS = _build_key_maps()
else:
    _MOD_MAP, _GENERIC_MODS = {}, {}


class GlobalShortcutManager(QObject):
    """Manages global keyboard shortcuts using ``pynput``.

    Shortcuts are registered as *action → callback* pairs.  When the
    corresponding key-combination is pressed, the callback is invoked
    on the main (Qt) thread.
    """

    # Emitted from the listener thread; Qt queues it to the main thread.
    shortcut_triggered = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hotkeys: Dict[str, Dict[str, Any]] = {}
        self._listener: Any = None
        self._pressed_keys: Set[Any] = set()
        # Combos that already fired and must be re-armed by a key release
        self._fired: Set[FrozenSet[Any]] = set()
        self._lock = threading.Lock()

        # Cross-thread dispatch: the connection runs this slot on the
        # thread the manager lives in (the main thread).
        self.shortcut_triggered.connect(self._dispatch)

    # ------------------------------------------------------------------
    # Key-sequence parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_key_sequence(sequence: str) -> Set[Any]:
        """Parse ``"Ctrl+Shift+A"`` or ``"F1"`` into a set of pynput keys."""
        keys: Set[Any] = set()
        parts = [p.strip().lower() for p in sequence.replace(" ", "").split("+") if p.strip()]

        for part in parts:
            if part in _MOD_MAP:
                keys.add(_MOD_MAP[part])
            else:
                # Special key name like "f1", "tab", "esc" …
                try:
                    keys.add(getattr(keyboard.Key, part))
                except AttributeError:
                    # Single character – store as a normalised string
                    keys.add(part.upper() if len(part) == 1 else part)

        return keys

    @staticmethod
    def _normalise_key(key: Any) -> Any:
        """Normalise a pynput key for consistent comparison."""
        if key in _GENERIC_MODS:
            return _GENERIC_MODS[key]

        # KeyCode with a character – normalise to upper-case char
        char = getattr(key, "char", None)
        if char:
            # Ctrl+letter arrives as a control character (\x01–\x1a);
            # map it back to the letter so "Ctrl+Shift+A" matches.
            if len(char) == 1 and 1 <= ord(char) <= 26:
                return chr(ord(char) + ord("A") - 1)
            return char.upper()

        # KeyCode with only a virtual key code – not useful for us
        if keyboard is not None and isinstance(key, keyboard.KeyCode):
            return None

        return key

    # ------------------------------------------------------------------
    # Listener callbacks (run on the pynput thread!)
    # ------------------------------------------------------------------

    def _on_press(self, key: Any) -> None:
        norm = self._normalise_key(key)
        if norm is None:
            return

        to_fire = []
        with self._lock:
            self._pressed_keys.add(norm)
            pressed = frozenset(self._pressed_keys)
            for action, entry in self._hotkeys.items():
                required: FrozenSet[Any] = entry["keys"]
                if required and required.issubset(pressed) and required not in self._fired:
                    self._fired.add(required)
                    to_fire.append(action)

        # Emit outside the lock; Qt queues this onto the main thread.
        for action in to_fire:
            logger.debug("Hotkey fired: %s", action)
            self.shortcut_triggered.emit(action)

    def _on_release(self, key: Any) -> None:
        norm = self._normalise_key(key)
        if norm is None:
            return

        with self._lock:
            self._pressed_keys.discard(norm)
            # Re-arm any combo that included the released key
            self._fired = {combo for combo in self._fired if norm not in combo}

    # ------------------------------------------------------------------
    # Main-thread dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, action: str) -> None:
        """Invoke the callback for *action* (runs on the main thread)."""
        with self._lock:
            entry = self._hotkeys.get(action)
        if entry is None:
            return
        try:
            entry["callback"]()
        except Exception:
            logger.exception("Error invoking callback for %r", action)

    # ------------------------------------------------------------------
    # Registration API
    # ------------------------------------------------------------------

    def register(self, action: str, key_sequence: str, callback: Callable[[], None]) -> None:
        """Register a global shortcut (e.g. ``register("capture", "F1", cb)``)."""
        if not _PYNPUT_AVAILABLE:
            logger.warning("Cannot register shortcut %r – pynput unavailable", action)
            return

        keys = self._parse_key_sequence(key_sequence)
        if not keys:
            logger.warning("Failed to parse key sequence %r for action %r", key_sequence, action)
            return

        with self._lock:
            self._hotkeys[action] = {"keys": frozenset(keys), "callback": callback}

        logger.debug("Registered shortcut %r → %s", action, key_sequence)
        self._ensure_listener()

    def unregister(self, action: str) -> None:
        """Remove a single registered shortcut."""
        with self._lock:
            self._hotkeys.pop(action, None)
        logger.debug("Unregistered shortcut %r", action)

    def unregister_all(self) -> None:
        """Stop the listener and clear all registered shortcuts."""
        self._stop_listener()
        with self._lock:
            self._hotkeys.clear()
            self._pressed_keys.clear()
            self._fired.clear()
        logger.debug("All shortcuts unregistered")

    # ------------------------------------------------------------------
    # Listener lifecycle
    # ------------------------------------------------------------------

    def _ensure_listener(self) -> None:
        if self._listener is not None or not _PYNPUT_AVAILABLE:
            return

        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self._listener.daemon = True
            self._listener.start()
            logger.debug("Global keyboard listener started")
        except Exception:
            logger.exception("Failed to start global keyboard listener")
            self._listener = None

    def _stop_listener(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                logger.exception("Error stopping keyboard listener")
            self._listener = None
            logger.debug("Global keyboard listener stopped")
