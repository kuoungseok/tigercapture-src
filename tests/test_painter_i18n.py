from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _restore_language():
    from app.i18n import current_language, set_language

    previous = current_language()
    yield
    set_language(previous)


@pytest.mark.parametrize(
    ("language", "canvas", "ui_design", "motion_link"),
    [
        ("en", "New Canvas", "UI Design", "Motion Link"),
        ("ko", "새 캔버스", "UI 디자인", "모션 링크"),
        ("ja", "新規キャンバス", "UIデザイン", "モーションリンク"),
        ("zh", "新建画布", "UI 设计", "动效链接"),
        ("fr", "Nouveau canevas", "Design UI", "Lien d'animation"),
        ("de", "Neue Leinwand", "UI-Design", "Motion-Verknüpfung"),
    ],
)
def test_painter_text_supports_every_studio_language(
    language: str,
    canvas: str,
    ui_design: str,
    motion_link: str,
) -> None:
    from app.painter_i18n import painter_text

    assert painter_text("New Canvas", language) == canvas
    assert painter_text("UI Design", language) == ui_design
    assert painter_text("Motion Link", language) == motion_link


def test_painter_localizer_translates_existing_dynamic_and_switched_widgets() -> None:
    app = _app()
    from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

    from app.i18n import set_language
    from app.painter_i18n import PainterWidgetLocalizer

    set_language("ko")
    root = QWidget()
    layout = QVBoxLayout(root)
    canvas = QLabel("CANVAS", root)
    layout.addWidget(canvas)
    localizer = PainterWidgetLocalizer(root)
    assert canvas.text() == "캔버스"

    motion = QPushButton("Open Motion", root)
    layout.addWidget(motion)
    app.processEvents()
    localizer.refresh()
    assert motion.text() == "Motion 열기"

    set_language("fr")
    localizer.refresh()
    assert canvas.text() == "CANEVAS"
    assert motion.text() == "Ouvrir Motion"
    root.deleteLater()


@pytest.mark.parametrize(
    ("language", "title", "create"),
    [
        ("ko", "새 캔버스", "만들기"),
        ("ja", "新規キャンバス", "作成"),
        ("zh", "新建画布", "创建"),
        ("fr", "Nouveau canevas", "Créer"),
        ("de", "Neue Leinwand", "Erstellen"),
    ],
)
def test_new_canvas_dialog_uses_current_studio_language(
    language: str,
    title: str,
    create: str,
) -> None:
    _app()
    from PySide6.QtWidgets import QDialogButtonBox

    from app.drawing import NewCanvasDialog
    from app.i18n import set_language

    set_language(language)
    dialog = NewCanvasDialog()
    buttons = dialog.findChild(QDialogButtonBox)
    assert dialog.windowTitle() == title
    assert buttons is not None
    assert buttons.button(QDialogButtonBox.StandardButton.Ok).text() == create
    dialog.deleteLater()


def test_motion_binding_panel_is_localized_when_hosted_in_painter() -> None:
    _app()
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from app.i18n import set_language
    from app.painter_i18n import PainterWidgetLocalizer
    from app.painter_ui_motion_binding_panel import PainterUIMotionBindingPanel

    set_language("de")
    root = QWidget()
    layout = QVBoxLayout(root)
    panel = PainterUIMotionBindingPanel(root)
    layout.addWidget(panel)
    PainterWidgetLocalizer(root).refresh()

    assert panel.findChildren(type(panel.status_badge))
    assert panel.status_badge.text() == "Keine Verknüpfung"
    assert panel.migrate_button.text() == "Migrieren"
    assert panel.detach_button.text() == "Verknüpfung lösen"
    root.deleteLater()


def test_full_painter_chrome_and_ui_designer_follow_language_setting() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.i18n import set_language

    set_language("ko")
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(480, 270),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    app.processEvents()

    assert dialog.windowTitle() == "페인터 - Tiger Studio"
    assert dialog._active_tool_name.text() == "브러시"
    assert dialog.pen_btn.toolTip() == "브러시 도구 (B)"
    assert dialog._canvas_mode_paint_btn.text() == "페인트"
    assert dialog._canvas_mode_ui_btn.text() == "UI 디자인"
    assert dialog._canvas_mode_3d_btn.text() == "3D 배치"
    assert dialog._brush_preset_button.text() == "브러시 선택기"

    set_language("ja")
    dialog._painter_localizer.refresh()
    assert dialog.windowTitle() == "ペインター - Tiger Studio"
    assert dialog._canvas_mode_ui_btn.text() == "UIデザイン"
    assert dialog._brush_preset_button.text() == "ブラシセレクター"
    dialog.deleteLater()
