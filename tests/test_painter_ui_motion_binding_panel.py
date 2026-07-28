from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _report(status: str = "ok") -> dict:
    return {
        "schema": "tigerstudio.painter.ui.motion_links.v2",
        "ok": status not in {
            "missing_binding",
            "missing_composition",
            "orphan_object",
        },
        "document_id": "painter-document-1",
        "document_revision": 17,
        "link_version": 2,
        "selected_object_id": "ui-button-1",
        "object_name": "Primary Button",
        "links": [
            {
                "object_id": "ui-button-1",
                "composition_id": "motion-composition-4",
                "binding_id": (
                    "" if status in {"legacy_link", "missing_binding"} else "binding-hover"
                ),
                "resolved_binding_id": (
                    "binding-hover" if status == "legacy_link" else ""
                ),
                "composition_revision": 7,
                "current_composition_revision": 9,
                "status": status,
            }
        ],
        "errors": [],
        "warnings": [],
    }


def test_motion_binding_panel_has_friendly_empty_states() -> None:
    _app()
    from app.painter_ui_motion_binding_panel import PainterUIMotionBindingPanel

    panel = PainterUIMotionBindingPanel()
    assert "No Motion link report" in panel.empty_label.text()
    assert not panel.migrate_button.isEnabled()
    assert not panel.relink_button.isEnabled()
    assert not panel.detach_button.isEnabled()

    panel.set_report(
        {
            "schema": "tigerstudio.painter.ui.motion_links.v2",
            "links": [],
        }
    )
    assert "no Motion link" in panel.empty_label.text()

    panel.set_report({"schema": "legacy-report.v1"})
    assert "not a supported v2 report" in panel.empty_label.text()
    panel.deleteLater()


@pytest.mark.parametrize(
    ("status", "badge", "migrate_enabled"),
    [
        ("ok", "Ready", False),
        ("legacy_link", "Legacy link", True),
        ("missing_binding", "Missing binding", False),
        ("missing_composition", "Missing composition", False),
        ("stale_revision", "Stale revision", False),
        ("orphan_object", "Orphan object", False),
    ],
)
def test_motion_binding_panel_displays_all_v2_statuses(
    status: str,
    badge: str,
    migrate_enabled: bool,
) -> None:
    _app()
    from app.painter_ui_motion_binding_panel import PainterUIMotionBindingPanel

    panel = PainterUIMotionBindingPanel()
    panel.set_report(_report(status))

    assert panel.status_badge.text() == badge
    assert panel.object_label.text() == "Primary Button"
    assert "motion-composition-4" in panel.identifiers_label.text()
    assert "7 linked / 9 current" in panel.identifiers_label.text()
    assert panel.migrate_button.isEnabled() is migrate_enabled
    assert panel.detach_button.isEnabled()
    panel.deleteLater()


def test_motion_binding_panel_emits_migrate_relink_and_detach_requests() -> None:
    app = _app()
    from app.painter_ui_motion_binding_panel import PainterUIMotionBindingPanel

    panel = PainterUIMotionBindingPanel()
    panel.set_report(_report("legacy_link"))
    migrated: list[str] = []
    relinked: list[tuple[str, str, str]] = []
    detached: list[str] = []
    panel.migrate_requested.connect(migrated.append)
    panel.relink_requested.connect(
        lambda object_id, composition_id, binding_id: relinked.append(
            (object_id, composition_id, binding_id)
        )
    )
    panel.detach_requested.connect(detached.append)

    panel.migrate_button.click()
    panel.composition_id_edit.setText("motion-composition-new")
    panel.binding_id_edit.setText("binding-hover-new")
    panel.relink_button.click()
    panel.detach_button.click()
    app.processEvents()

    assert migrated == ["ui-button-1"]
    assert relinked == [
        ("ui-button-1", "motion-composition-new", "binding-hover-new")
    ]
    assert detached == ["ui-button-1"]
    assert panel.detach_warning_label.isVisible() is False
    assert panel.detach_warning_label.text().startswith("Detach removes")
    assert panel.detach_button.objectName() == "painterMotionDangerButton"
    panel.deleteLater()


def test_motion_binding_panel_requires_both_relink_ids() -> None:
    _app()
    from app.painter_ui_motion_binding_panel import PainterUIMotionBindingPanel

    panel = PainterUIMotionBindingPanel()
    panel.set_report(_report("missing_binding"))
    panel.binding_id_edit.clear()
    assert not panel.relink_button.isEnabled()
    panel.binding_id_edit.setText("replacement-binding")
    assert panel.relink_button.isEnabled()
    panel.composition_id_edit.clear()
    assert not panel.relink_button.isEnabled()
    panel.deleteLater()
