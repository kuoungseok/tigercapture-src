"""Shared multi-monitor placement helpers for top-level Qt windows."""
from __future__ import annotations

from PySide6.QtCore import QObject, QEvent, QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QCursor, QGuiApplication, QScreen
from PySide6.QtWidgets import QApplication, QWidget


_PLACEMENT_DONE_PROPERTY = "_tiger_window_placement_done"
_PLACEMENT_DISABLED_PROPERTY = "tiger_no_auto_place"
_PLACEMENT_FILTER_PROPERTY = "_tiger_window_placement_filter"


def target_screen_for_window(
    widget: QWidget | None = None,
    *,
    reference: QWidget | QPoint | QRect | None = None,
) -> QScreen | None:
    """Choose the screen that should own a newly opened top-level window.

    Preference order intentionally follows what users perceive as the active
    workspace: explicit reference/parent, focused widget, active window, the
    window's current screen, mouse cursor, then primary screen.
    """

    for candidate in _screen_candidates(widget, reference):
        screen = _screen_from_candidate(candidate)
        if screen is not None:
            return screen
    return QGuiApplication.primaryScreen()


def available_geometry_for_window(
    widget: QWidget | None = None,
    *,
    reference: QWidget | QPoint | QRect | None = None,
) -> QRect:
    screen = target_screen_for_window(widget, reference=reference)
    if screen is not None:
        return QRect(screen.availableGeometry())
    return QRect(0, 0, 1920, 1080)


def fit_window_to_current_screen(
    widget: QWidget,
    *,
    reference: QWidget | QPoint | QRect | None = None,
    margin: int = 24,
    center_on_target_screen: bool = True,
    mark_done: bool = False,
) -> bool:
    """Resize and move ``widget`` so it is fully inside the target monitor.

    Returns True when geometry changed. Menus, tooltips, and combobox popups are
    intentionally not handled by this function; callers should screen for real
    windows/dialogs before calling it from a global event filter.
    """

    if widget is None or not isinstance(widget, QWidget):
        return False
    screen = target_screen_for_window(widget, reference=reference)
    if screen is None:
        return False

    available = QRect(screen.availableGeometry())
    safe = _safe_rect(available, margin)
    if safe.width() <= 1 or safe.height() <= 1:
        safe = available

    changed = False
    desired_w, desired_h = _desired_window_size(widget)
    current_w = max(1, int(widget.width() or 1))
    current_h = max(1, int(widget.height() or 1))
    frame_extra_w = 0
    frame_extra_h = 0
    if widget.isVisible():
        frame = QRect(widget.frameGeometry())
        frame_extra_w = max(0, int(frame.width()) - current_w)
        frame_extra_h = max(0, int(frame.height()) - current_h)
    target_w = min(desired_w, max(1, safe.width() - frame_extra_w))
    target_h = min(desired_h, max(1, safe.height() - frame_extra_h))
    if target_w != current_w or target_h != current_h:
        widget.resize(target_w, target_h)
        changed = True
    if widget.isVisible():
        rect = QRect(widget.frameGeometry())
        width = int(rect.width())
        height = int(rect.height())
    else:
        width = int(widget.width())
        height = int(widget.height())
        rect = QRect(widget.geometry())
        if rect.width() <= 1 or rect.height() <= 1:
            rect = QRect(widget.x(), widget.y(), width, height)

    current_screen = QGuiApplication.screenAt(rect.center())
    is_on_target = current_screen is screen
    if safe.contains(rect):
        if mark_done:
            widget.setProperty(_PLACEMENT_DONE_PROPERTY, True)
        return changed

    if center_on_target_screen or not is_on_target:
        x = safe.left() + max(0, (safe.width() - width) // 2)
        y = safe.top() + max(0, (safe.height() - height) // 2)
    else:
        x = min(max(rect.x(), safe.left()), max(safe.left(), safe.right() - width + 1))
        y = min(max(rect.y(), safe.top()), max(safe.top(), safe.bottom() - height + 1))
    if x != widget.x() or y != widget.y():
        widget.move(x, y)
        changed = True
    if mark_done:
        widget.setProperty(_PLACEMENT_DONE_PROPERTY, True)
    return changed


def install_global_window_placement(app: QApplication | None = None) -> QObject | None:
    """Install one app-wide first-show placement guard for real top-level windows."""

    application = app or QApplication.instance()
    if application is None:
        return None
    existing = application.property(_PLACEMENT_FILTER_PROPERTY)
    if isinstance(existing, QObject):
        return existing
    event_filter = _WindowPlacementEventFilter(application)
    application.installEventFilter(event_filter)
    application.setProperty(_PLACEMENT_FILTER_PROPERTY, event_filter)
    return event_filter


def should_auto_place_window(widget: QWidget | None) -> bool:
    if widget is None or not isinstance(widget, QWidget):
        return False
    if not widget.isWindow():
        return False
    if bool(widget.property(_PLACEMENT_DISABLED_PROPERTY)):
        return False
    flags = widget.windowFlags()
    window_type = flags & Qt.WindowType.WindowType_Mask
    if window_type in (
        Qt.WindowType.Popup,
        Qt.WindowType.ToolTip,
        Qt.WindowType.SplashScreen,
    ):
        return False
    if flags & Qt.WindowType.FramelessWindowHint:
        return False
    # A parentless QWidget can be a real native top-level window while its
    # window-type bits still read as Widget instead of Window/Dialog/Tool. If it
    # survived the popup/tooltip/splash/frameless exclusions above and
    # ``isWindow()`` is true, treat it as a Studio window that should be placed.
    return True


class _WindowPlacementEventFilter(QObject):
    def eventFilter(self, obj, event) -> bool:  # pragma: no cover - Qt event glue
        if event is not None and event.type() == QEvent.Type.Show and should_auto_place_window(obj):
            widget = obj
            if bool(widget.property(_PLACEMENT_DONE_PROPERTY)):
                return False
            reference = widget.parentWidget()
            _schedule_first_show_placement(widget, reference)
        return False


def _schedule_first_show_placement(widget: QWidget, reference: QWidget | None) -> None:
    """Place a new window across a few early layout passes.

    Dense Studio windows often grow after their initial ``show()`` when late
    layouts, OpenGL surfaces, or moved dock contents publish a larger
    size-hint. A single immediate fit can still leave the final frame straddling
    monitors. These short follow-up passes keep first-show windows inside the
    active screen without adding per-frame tracking.
    """

    for delay_ms, final_pass in ((0, False), (120, False), (360, True)):
        QTimer.singleShot(
            delay_ms,
            lambda w=widget, r=reference, done=final_pass: _place_from_event_filter(w, r, done),
        )


def _place_from_event_filter(widget: QWidget, reference: QWidget | None, mark_done: bool) -> None:
    try:
        if should_auto_place_window(widget):
            if bool(widget.property(_PLACEMENT_DONE_PROPERTY)):
                return
            fit_window_to_current_screen(
                widget,
                reference=reference,
                margin=24,
                center_on_target_screen=True,
                mark_done=mark_done,
            )
    except RuntimeError:
        pass
    except Exception:
        # Placement must never prevent a tool window from opening.
        pass


def _screen_candidates(widget: QWidget | None, reference: QWidget | QPoint | QRect | None):
    if reference is not None:
        yield reference
    if widget is not None:
        parent = widget.parentWidget()
        if parent is not None:
            yield parent
    app = QApplication.instance()
    if app is not None:
        focus = app.focusWidget()
        if focus is not None and focus is not widget:
            yield focus
        active = app.activeWindow()
        if active is not None and active is not widget:
            yield active
    try:
        yield QCursor.pos()
    except Exception:
        pass
    if widget is not None:
        yield widget


def _screen_from_candidate(candidate: QWidget | QPoint | QRect | None) -> QScreen | None:
    if candidate is None:
        return None
    if isinstance(candidate, QWidget):
        try:
            screen = candidate.window().screen()
            if screen is not None:
                return screen
        except Exception:
            pass
        try:
            rect = candidate.window().frameGeometry()
            screen = QGuiApplication.screenAt(rect.center())
            if screen is not None:
                return screen
        except Exception:
            pass
        return None
    if isinstance(candidate, QRect):
        return QGuiApplication.screenAt(candidate.center())
    if isinstance(candidate, QPoint):
        return QGuiApplication.screenAt(candidate)
    return None


def _safe_rect(rect: QRect, margin: int) -> QRect:
    pad = max(0, int(margin))
    if rect.width() <= pad * 2 or rect.height() <= pad * 2:
        return QRect(rect)
    return rect.adjusted(pad, pad, -pad, -pad)


def _desired_window_size(widget: QWidget) -> tuple[int, int]:
    """Return the first-show size Qt is likely to enforce for a top-level tool.

    Several dense tool windows start with a conservative ``resize(...)`` but
    expand to their layout minimum on first show. Placement has to account for
    that future size, otherwise the window is centered as if it were small and
    then grows across monitor boundaries.
    """

    values_w = [int(widget.width() or 0)]
    values_h = [int(widget.height() or 0)]
    for size in (widget.sizeHint(), widget.minimumSizeHint(), widget.minimumSize()):
        try:
            values_w.append(int(size.width()))
            values_h.append(int(size.height()))
        except Exception:
            pass
    width = max(1, max(values_w))
    height = max(1, max(values_h))
    return width, height
