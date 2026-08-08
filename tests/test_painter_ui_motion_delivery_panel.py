from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _report() -> dict:
    return {
        "selection": {
            "id": "ui-button-1",
            "name": "Primary Button",
            "component_id": "ui-component-1",
        },
        "binding": {
            "id": "ui-motion-binding-1",
            "animation_name": "PrimaryButtonHover",
            "scope": "transition",
            "trigger": "pointer_enter",
            "from_state": "normal",
            "to_state": "hover",
            "duration_ms": 160,
        },
        "features": [
            {
                "feature": "position",
                "targets": {
                    "web": {"resolved": "Native"},
                    "app": {"resolved": "Native"},
                    "umg": {"resolved": "Native"},
                },
            },
            {
                "feature": "fill",
                "targets": {
                    "web": {"resolved": "Vector"},
                    "app": {"resolved": "Platform Effect"},
                    "umg": {"resolved": "Material"},
                },
            },
            {
                "feature": "blur",
                "targets": {
                    "web": {"resolved": "Native"},
                    "app": {"resolved": "Baked"},
                    "umg": {
                        "resolved": "Blocked",
                        "reasons": ["UI Material adapter is unavailable."],
                    },
                },
            },
            {
                "feature": "embedded composition",
                "targets": {
                    "web": {"resolved": "Actor Only"},
                    "app": {"resolved": "Actor Only"},
                    "umg": {"resolved": "Baked"},
                },
            },
        ],
    }


def test_motion_delivery_panel_has_friendly_empty_states() -> None:
    _app()
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSizePolicy

    from app.painter_ui_motion_delivery_panel import PainterUIMotionDeliveryPanel

    panel = PainterUIMotionDeliveryPanel()
    assert panel.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert panel.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum
    assert "#15191F" in panel.styleSheet()
    assert panel.empty_label.isVisible() is False  # Hidden parent widgets are not visible.
    assert "No Motion delivery report" in panel.empty_label.text()
    assert not panel.open_motion_button.isEnabled()
    assert not panel.preview_hover_button.isEnabled()
    assert not panel.bake_flipbook_button.isEnabled()

    panel.set_report({"selection": {"name": "Checkout Card"}})
    assert "Checkout Card has no Motion binding" in panel.empty_label.text()
    assert not panel.open_motion_button.isEnabled()
    assert not panel.bake_flipbook_button.isEnabled()
    panel.deleteLater()


def test_motion_delivery_panel_summarizes_binding_targets_and_blockers() -> None:
    _app()
    from app.painter_ui_motion_delivery_panel import PainterUIMotionDeliveryPanel

    panel = PainterUIMotionDeliveryPanel()
    panel.set_report(_report())

    assert panel.object_label.text() == "Primary Button"
    assert "PrimaryButtonHover" in panel.binding_label.text()
    assert "pointer_enter" in panel.binding_label.text()
    assert panel.transition_label.text() == "normal -> hover"
    assert panel.open_motion_button.isEnabled()
    assert panel.preview_hover_button.isEnabled()
    assert panel.bake_flipbook_button.isEnabled()

    assert panel.target_count_labels["web"]["native"].text() == "Native 2"
    assert panel.target_count_labels["web"]["vector"].text() == "Vector 1"
    assert panel.target_count_labels["app"]["platform_effect"].text() == "Effect 1"
    assert panel.target_count_labels["app"]["baked"].text() == "Baked 1"
    assert panel.target_count_labels["umg"]["material"].text() == "Material 1"
    assert panel.target_count_labels["umg"]["blocked"].text() == "Blocked 1"
    assert "Unreal UMG: blur: UI Material adapter is unavailable." in (
        panel.blocker_label.text()
    )
    panel.deleteLater()


def test_motion_delivery_panel_emits_binding_requests() -> None:
    app = _app()
    from app.painter_ui_motion_delivery_panel import PainterUIMotionDeliveryPanel

    panel = PainterUIMotionDeliveryPanel()
    panel.set_report(_report())
    opened: list[str] = []
    previewed: list[str] = []
    baked: list[str] = []
    panel.open_motion_requested.connect(opened.append)
    panel.preview_hover_requested.connect(previewed.append)
    panel.bake_flipbook_requested.connect(baked.append)

    panel.open_motion_button.click()
    panel.preview_hover_button.click()
    panel.bake_flipbook_button.click()
    app.processEvents()

    assert opened == ["ui-motion-binding-1"]
    assert previewed == ["ui-motion-binding-1"]
    assert baked == ["ui-motion-binding-1"]
    panel.deleteLater()


def test_motion_delivery_panel_accepts_aggregated_target_report() -> None:
    _app()
    from app.painter_ui_motion_delivery_panel import PainterUIMotionDeliveryPanel

    panel = PainterUIMotionDeliveryPanel()
    panel.set_report(
        {
            "object_name": "Status Chip",
            "binding": {
                "binding_id": "binding-chip",
                "from_state": "normal",
                "to_state": "selected",
            },
            "targets": {
                "web": {"counts": {"native": 3, "blocked": 0}},
                "app": {"counts": {"platform_effect": 2}},
                "umg": {
                    "counts": {"blocked": 1},
                    "blockers": [
                        {
                            "feature": "gradient",
                            "reason": "Material generator missing",
                        }
                    ],
                },
            },
        }
    )

    assert panel.object_label.text() == "Status Chip"
    assert panel.target_count_labels["web"]["native"].text() == "Native 3"
    assert panel.target_count_labels["app"]["platform_effect"].text() == "Effect 2"
    assert "gradient: Material generator missing" in panel.blocker_label.text()
    assert not panel.preview_hover_button.isEnabled()
    panel.deleteLater()


def test_motion_delivery_panel_accepts_canonical_target_rows() -> None:
    _app()
    from app.painter_ui_motion_delivery_panel import PainterUIMotionDeliveryPanel

    panel = PainterUIMotionDeliveryPanel()
    panel.set_report(
        {
            "object_id": "checkout",
            "object_name": "Checkout",
            "bindings": [
                {
                    "id": "binding-checkout",
                    "animation_name": "Hover",
                    "scope": "transition",
                    "from_state": "normal",
                    "to_state": "hover",
                }
            ],
            "targets": [
                {
                    "target": "umg",
                    "counts": {"Native": 1, "Blocked": 1},
                    "features": [
                        {
                            "feature": "blur",
                            "resolved": "Blocked",
                            "reasons": ["No deterministic bake exists"],
                        }
                    ],
                }
            ],
        }
    )

    assert panel.object_label.text() == "Checkout"
    assert panel.target_count_labels["umg"]["native"].text() == "Native 1"
    assert panel.target_count_labels["umg"]["blocked"].text() == "Blocked 1"
    assert "blur: No deterministic bake exists" in panel.blocker_label.text()
    panel.deleteLater()
