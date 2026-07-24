from __future__ import annotations

import os


def _qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_window_placement_keeps_large_window_inside_active_screen() -> None:
    _qt_app()
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QWidget

    from app.window_placement import available_geometry_for_window, fit_window_to_current_screen

    window = QWidget()
    available = available_geometry_for_window(window)
    window.resize(available.width() + 400, available.height() + 400)
    window.move(available.right() + 500, available.bottom() + 500)

    assert fit_window_to_current_screen(window, margin=24)

    safe = QRect(available).adjusted(24, 24, -24, -24)
    if safe.width() <= 1 or safe.height() <= 1:
        safe = available
    assert window.width() <= safe.width()
    assert window.height() <= safe.height()
    assert safe.contains(window.geometry())


def test_window_placement_accounts_for_first_show_size_hint() -> None:
    _qt_app()
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QWidget

    from app.window_placement import available_geometry_for_window, fit_window_to_current_screen

    class HintHeavyWindow(QWidget):
        def sizeHint(self):  # noqa: N802 - Qt override
            available = available_geometry_for_window(self)
            return QSize(max(1, available.width() - 64), 520)

        def minimumSizeHint(self):  # noqa: N802 - Qt override
            available = available_geometry_for_window(self)
            return QSize(max(1, available.width() - 96), 480)

    window = HintHeavyWindow()
    available = available_geometry_for_window(window)
    window.resize(720, 420)

    assert fit_window_to_current_screen(window, margin=24)

    safe = available.adjusted(24, 24, -24, -24)
    assert window.width() >= available.width() - 96
    assert safe.contains(window.geometry())


def test_window_placement_ignores_popup_windows() -> None:
    _qt_app()
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget

    from app.window_placement import should_auto_place_window

    popup = QWidget(None, Qt.WindowType.Popup)
    assert should_auto_place_window(popup) is False


def test_global_window_placement_filter_is_installed_once() -> None:
    app = _qt_app()
    from app.window_placement import install_global_window_placement

    first = install_global_window_placement(app)
    second = install_global_window_placement(app)

    assert first is not None
    assert first is second


def test_global_window_placement_refits_after_late_layout_growth() -> None:
    app = _qt_app()
    from PySide6.QtCore import QEventLoop, QSize, QTimer
    from PySide6.QtWidgets import QWidget

    from app.window_placement import available_geometry_for_window, install_global_window_placement

    class LateGrowingWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.grown = False

        def sizeHint(self):  # noqa: N802 - Qt override
            available = available_geometry_for_window(self)
            if self.grown:
                return QSize(available.width() + 320, available.height() + 260)
            return QSize(320, 220)

        def minimumSizeHint(self):  # noqa: N802 - Qt override
            available = available_geometry_for_window(self)
            if self.grown:
                return QSize(available.width() + 120, available.height() + 80)
            return QSize(260, 180)

    install_global_window_placement(app)
    window = LateGrowingWindow()
    available = available_geometry_for_window(window)
    window.resize(320, 220)
    window.move(available.right() + 100, available.bottom() + 100)
    window.show()

    def grow_after_first_show() -> None:
        window.grown = True
        window.updateGeometry()
        window.adjustSize()

    QTimer.singleShot(30, grow_after_first_show)
    loop = QEventLoop()
    QTimer.singleShot(520, loop.quit)
    loop.exec()

    safe = available.adjusted(24, 24, -24, -24)
    if safe.width() <= 1 or safe.height() <= 1:
        safe = available
    assert window.width() <= safe.width()
    assert window.height() <= safe.height()
    assert safe.contains(window.geometry())
    window.close()
