"""Offscreen smoke tests for PinSnap (no real display needed)."""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
# Isolate config writes from the user's real ~/.config
fake_home = tempfile.mkdtemp(prefix="pinsnap_test_home_")
os.environ["HOME"] = fake_home

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

failures = []

def check(name, fn):
    try:
        fn()
        print(f"  OK  {name}")
    except Exception as e:
        failures.append((name, e))
        import traceback
        print(f"FAIL  {name}: {e}")
        traceback.print_exc()


# ----------------------------------------------------------------- imports
def test_imports():
    import pinsnap.main
    import pinsnap.app
    import pinsnap.config
    import pinsnap.shortcuts
    import pinsnap.tray
    import pinsnap.capture.backend
    import pinsnap.capture.overlay
    import pinsnap.annotation.editor
    import pinsnap.pin.pin_window
    import pinsnap.colorpicker.picker
    import pinsnap.ruler.ruler
    import pinsnap.preferences.dialog

check("import all modules", test_imports)

# ----------------------------------------------------------------- Qt app
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect, QPoint, Qt
from PySide6.QtGui import QPixmap, QColor, QImage

app = QApplication(sys.argv)

# ----------------------------------------------------------------- config
def test_config():
    from pinsnap.config import AppConfig, DEFAULT_SHORTCUTS
    cfg = AppConfig()
    # PixPin's documented defaults: Ctrl+1 screenshot, Ctrl+2 pin
    assert cfg.get_shortcut("capture") == "Ctrl+1", cfg.get_shortcut("capture")
    assert cfg.get_shortcut("pin") == "Ctrl+2"
    cfg.set_shortcut("capture", "Ctrl+Shift+X")
    cfg2 = AppConfig()
    assert cfg2.get_shortcut("capture") == "Ctrl+Shift+X"
    cfg2.reset_shortcuts()
    assert AppConfig().get_shortcut("capture") == "Ctrl+1"
    # corrupted values get clamped
    cfg.set("pin_opacity", 500)
    cfg3 = AppConfig()
    assert cfg3.pin_opacity == 100, cfg3.pin_opacity

check("config load/save/validate", test_config)

# ----------------------------------------------------------------- shortcuts
def test_i18n_complete():
    from pinsnap.i18n import _T, LANGUAGES, set_language, tr
    others = [code for code in LANGUAGES if code != "es"]
    for source, translations in _T.items():
        missing = [code for code in others if code not in translations]
        assert not missing, f"{source!r} sin traducción a {missing}"
    set_language("en")
    assert tr("Regla") == "Ruler"
    assert tr("cadena inexistente") == "cadena inexistente"  # fallback seguro
    set_language("ru")
    assert tr("Salir") == "Выход"
    set_language("es")

check("i18n: 5 idiomas completos y fallback seguro", test_i18n_complete)

def test_shortcut_parsing():
    from pinsnap.shortcuts import GlobalShortcutManager, _PYNPUT_AVAILABLE
    if not _PYNPUT_AVAILABLE:
        print("      (pynput no disponible aquí; se omite)")
        return
    from pynput import keyboard
    mgr = GlobalShortcutManager()
    keys = mgr._parse_key_sequence("Ctrl+Shift+A")
    assert keyboard.Key.ctrl in keys and keyboard.Key.shift in keys and "A" in keys, keys
    keys = mgr._parse_key_sequence("F1")
    assert keys == {keyboard.Key.f1}, keys
    # normalisation: ctrl variants and control chars
    assert mgr._normalise_key(keyboard.Key.ctrl_l) == keyboard.Key.ctrl
    assert mgr._normalise_key(keyboard.KeyCode(char="a")) == "A"
    assert mgr._normalise_key(keyboard.KeyCode(char="\x01")) == "A"  # Ctrl+A
    assert mgr._normalise_key(keyboard.KeyCode(vk=255)) is None

def test_shortcut_fire_once():
    from pinsnap.shortcuts import GlobalShortcutManager, _PYNPUT_AVAILABLE
    if not _PYNPUT_AVAILABLE:
        print("      (pynput no disponible aquí; se omite)")
        return
    from pynput import keyboard
    mgr = GlobalShortcutManager()
    fired = []
    mgr._hotkeys["capture"] = {"keys": frozenset({keyboard.Key.f1}), "callback": lambda: fired.append(1)}
    mgr._on_press(keyboard.Key.f1)
    mgr._on_press(keyboard.Key.f1)   # auto-repeat: must NOT refire
    app.processEvents()
    assert len(fired) == 1, fired
    mgr._on_release(keyboard.Key.f1)
    mgr._on_press(keyboard.Key.f1)   # re-armed after release
    app.processEvents()
    assert len(fired) == 2, fired

check("shortcut parsing/normalisation", test_shortcut_parsing)
check("shortcut fires once per press (main-thread dispatch)", test_shortcut_fire_once)

# ----------------------------------------------------------------- overlay
def make_fake_backend(w=800, h=600):
    from pinsnap.capture.backend import CaptureBackend
    class FakeBackend(CaptureBackend):
        def capture_screen(self, region=None):
            pm = QPixmap(w, h)
            pm.fill(QColor("#336699"))
            return pm
        def get_screen_geometry(self):
            return (0, 0, w, h)
    return FakeBackend()

def test_overlay_flow():
    from pinsnap.capture.overlay import CaptureOverlay, _State, _Tool
    from pinsnap.annotation.editor import RectItem
    ov = CaptureOverlay(make_fake_backend())
    ov.resize(800, 600)
    # simulate drag selection
    ov._state = _State.DRAGGING
    ov._drag_origin = QPoint(100, 100)
    ov._sel = QRect(QPoint(100, 100), QPoint(300, 250))
    ov._enter_selected()
    assert ov._state is _State.SELECTED
    assert ov._toolbar.isVisibleTo(ov)
    # add an annotation and render the result
    ov._items.append(RectItem(QRect(120, 120, 50, 40), QColor("red"), 3))
    result = ov._render_result()
    assert result.width() == 201 and result.height() == 151, (result.width(), result.height())
    img = result.toImage()
    # border pixel of the rect annotation should be red-ish, not background
    c = QColor(img.pixel(20, 20))
    assert c.red() > 200 and c.blue() < 100, c.name()
    # background pixel keeps the snapshot colour
    c2 = QColor(img.pixel(5, 5))
    assert c2.name() == "#336699", c2.name()
    ov.close()

def test_overlay_finish_signal():
    from pinsnap.capture.overlay import CaptureOverlay, _State
    ov = CaptureOverlay(make_fake_backend(), default_action="pin")
    ov.resize(800, 600)
    ov._sel = QRect(10, 10, 100, 80)
    ov._state = _State.SELECTED
    got = []
    ov.finished.connect(lambda action, pm: got.append((action, pm.size())))
    ov._finish(ov._default_action)
    assert got and got[0][0] == "pin", got
    assert got[0][1].width() == 100, got

def test_overlay_paint():
    # Exercise every paint path (picking, selected+items, magnifier)
    from pinsnap.capture.overlay import CaptureOverlay, _State
    from pinsnap.annotation.editor import ArrowItem, FreehandItem, TextItem, EllipseItem
    ov = CaptureOverlay(make_fake_backend())
    ov.resize(800, 600)
    target = QImage(800, 600, QImage.Format.Format_ARGB32)
    ov._hover_window = QRect(50, 50, 200, 150)
    ov.render(target)  # PICKING paint path + magnifier
    ov._sel = QRect(100, 100, 200, 150)
    ov._state = _State.SELECTED
    ov._items.extend([
        ArrowItem(QPoint(110, 110), QPoint(200, 200), QColor("red"), 3),
        FreehandItem([QPoint(120, 120), QPoint(130, 140), QPoint(150, 130)], QColor("blue"), 2),
        TextItem(QPoint(150, 150), "hola", QColor("black"), 14),
        EllipseItem(QRect(160, 120, 60, 40), QColor("green"), 2),
    ])
    ov._reposition_toolbar()
    ov.render(target)  # SELECTED paint path
    ov.close()

def test_overlay_resize_logic():
    from pinsnap.capture.overlay import CaptureOverlay, _State
    ov = CaptureOverlay(make_fake_backend())
    ov.resize(800, 600)
    ov._sel = QRect(100, 100, 200, 150)
    ov._state = _State.SELECTED
    # hit-test edges
    assert ov._edges_at(QPoint(100, 175)) == 1   # left
    assert ov._edges_at(QPoint(300, 175)) & 2    # right (uses right edge)
    assert ov._edges_at(QPoint(100, 100)) == 5   # top-left corner
    # resize from right edge
    ov._resizing = True
    ov._resize_edges = 2
    ov._adjust_start = QPoint(299, 175)
    ov._sel_start = QRect(ov._sel)
    ov._apply_resize(QPoint(349, 175))
    assert ov._sel.width() == 250, ov._sel
    ov.close()

def test_number_balloons():
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent
    from pinsnap.capture.overlay import CaptureOverlay, _State, _Tool
    from pinsnap.annotation.editor import NumberItem

    def press(ov, x, y):
        ev = QMouseEvent(
            QEvent.Type.MouseButtonPress, QPointF(x, y), QPointF(x, y),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        ov.mousePressEvent(ev)

    ov = CaptureOverlay(make_fake_backend())
    ov.resize(800, 600)
    ov._sel = QRect(100, 100, 300, 200)
    ov._state = _State.SELECTED
    ov._tool = _Tool.NUMBER
    for x in (150, 220, 290):
        press(ov, x, 150)
    balloons = [it for it in ov._items if isinstance(it, NumberItem)]
    assert [b.number for b in balloons] == [1, 2, 3], balloons
    # undo removes the last balloon; the next click re-uses its number
    ov._undo()
    press(ov, 320, 150)
    balloons = [it for it in ov._items if isinstance(it, NumberItem)]
    assert [b.number for b in balloons] == [1, 2, 3], balloons
    # the balloon is drawn into the final render: sample inside the circle
    # but away from the white digit at the centre (radius is 10 + width*2)
    img = ov._render_result().toImage()
    c = QColor(img.pixel(150 - 100 + 10, 150 - 100 + 8))
    assert c.red() > 180 and c.green() < 100, c.name()
    ov.close()

check("overlay selection → annotated render", test_overlay_flow)
check("numbered balloons place/undo/render", test_number_balloons)
check("overlay finished signal (pin default)", test_overlay_finish_signal)
check("overlay paint paths render without crash", test_overlay_paint)
check("overlay edge hit-testing / resize", test_overlay_resize_logic)

# ----------------------------------------------------------------- backends
def test_backend_factory():
    from pinsnap.capture.backend import get_capture_backend, QtCaptureBackend
    b = get_capture_backend()
    assert b is not None
    # offscreen: Qt grab may be null, but must not raise
    QtCaptureBackend().capture_screen()

check("backend factory (offscreen)", test_backend_factory)

# ----------------------------------------------------------------- pin window
def test_pin_window():
    from pinsnap.pin.pin_window import PinWindow
    from pinsnap.config import AppConfig
    pm = QPixmap(200, 150)
    pm.fill(QColor("red"))
    pin = PinWindow(pm, AppConfig())
    pin.show()
    closed = []
    pin.closed.connect(lambda: closed.append(1))
    pin.close()
    assert closed

def test_pin_interactions():
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    from pinsnap.pin.pin_window import PinWindow
    from pinsnap.config import AppConfig

    def wheel(pin, dy, mods=Qt.KeyboardModifier.NoModifier):
        ev = QWheelEvent(
            QPointF(50, 50), QPointF(50, 50), QPoint(0, 0), QPoint(0, dy),
            Qt.MouseButton.NoButton, mods, Qt.ScrollPhase.NoScrollPhase, False,
        )
        pin.wheelEvent(ev)

    pm = QPixmap(200, 150)
    pm.fill(QColor("red"))
    pin = PinWindow(pm, AppConfig())
    pin.show()
    assert (pin.width(), pin.height()) == (200, 150)

    # wheel up zooms in (aspect ratio preserved)
    wheel(pin, 120)
    assert pin.width() > 200
    assert abs(pin.width() / pin.height() - 200 / 150) < 0.05

    # Ctrl+wheel down lowers opacity
    op0 = pin._opacity
    wheel(pin, -120, Qt.KeyboardModifier.ControlModifier)
    assert pin._opacity == op0 - 5, (op0, pin._opacity)

    # locked pin ignores zoom
    pin._toggle_lock()
    w_locked = pin.width()
    wheel(pin, 120)
    assert pin.width() == w_locked
    pin._toggle_lock()

    # middle-click reset restores original size and configured opacity
    pin._reset()
    assert (pin.width(), pin.height()) == (200, 150)
    assert pin._opacity == AppConfig().pin_opacity
    pin.close()

check("pin window open/close", test_pin_window)
check("pin zoom/opacity/lock/reset (PixPin interactions)", test_pin_interactions)

# ----------------------------------------------------------------- theme
def test_theme():
    from PySide6.QtGui import QPalette
    from pinsnap.theme import apply_theme
    apply_theme(app, "dark")
    dark_window = app.palette().color(QPalette.ColorRole.Window)
    assert dark_window.lightness() < 100, dark_window.name()
    apply_theme(app, "light")
    light_window = app.palette().color(QPalette.ColorRole.Window)
    assert light_window.lightness() > dark_window.lightness()
    apply_theme(app, "system")  # restores the startup palette

check("theme switches dark/light/system", test_theme)

# ----------------------------------------------------------------- OCR
def test_ocr_graceful():
    from pinsnap.ocr import ocr_available, ocr_pixmap
    pm = QPixmap(200, 60)
    pm.fill(QColor("white"))
    text, error = ocr_pixmap(pm)
    if ocr_available():
        # blank image → empty text, no error
        assert error is None, error
    else:
        # missing dependency → actionable message, never a crash
        assert text is None and error and "tesseract" in error.lower(), (text, error)

check("OCR degrades gracefully without tesseract", test_ocr_graceful)

# ----------------------------------------------------------------- app wiring
def test_app_controller():
    from pinsnap.app import PinSnapApp
    ctrl = PinSnapApp(app)
    # finished-capture path: pin action creates a PinWindow
    pm = QPixmap(120, 90)
    pm.fill(QColor("green"))
    ctrl._on_capture_finished("pin", pm)
    assert len(ctrl._active_pinned) == 1
    ctrl._on_capture_finished("copy", pm)
    cb_img = QApplication.clipboard().image()
    assert not cb_img.isNull()
    # F3 with image in clipboard pins directly (no overlay)
    ctrl.start_pin_capture()
    assert len(ctrl._active_pinned) == 2
    # Preferences must be non-modal (show_preferences returns immediately)
    ctrl.show_preferences()
    assert ctrl._prefs_dialog is not None and ctrl._prefs_dialog.isVisible()
    assert not ctrl._prefs_dialog.isModal()
    ctrl.show_preferences()  # second call must reuse the same dialog
    ctrl._prefs_dialog.close()
    app.processEvents()
    assert ctrl._prefs_dialog is None
    # OCR flow with a blank capture must not crash regardless of tesseract
    ctrl.quit()

check("app controller wiring (pin/copy/F3-clipboard)", test_app_controller)

print()
if failures:
    print(f"{len(failures)} FAILURES")
    sys.exit(1)
print("ALL TESTS PASSED")
