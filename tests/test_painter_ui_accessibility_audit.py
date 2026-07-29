from __future__ import annotations

import copy
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_accessibility_audit_reports_labels_targets_contrast_and_focus() -> None:
    from app.painter_ui_accessibility_audit import audit_ui_accessibility
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(390, 844)
    document, first = add_ui_object(
        document,
        kind="button",
        name="Tiny action",
        width=32,
        height=24,
        style={
            "fill": "#FFFFFF",
            "text_color": "#D0D0D0",
            "font_size": 14,
        },
        content={"text": ""},
    )
    document, first = update_ui_object(
        document,
        first["id"],
        {
            "accessibility": {
                "role": "button",
                "label": "",
                "focus_order": 1,
            }
        },
    )
    document, second = add_ui_object(
        document,
        kind="button",
        name="Hidden action",
        x=8,
        y=100,
        width=80,
        height=48,
        content={"text": "Hidden"},
    )
    document, second = update_ui_object(
        document,
        second["id"],
        {
            "visible": False,
            "accessibility": {
                "role": "button",
                "label": "Hidden action",
                "focus_order": 1,
            }
        },
    )

    report = audit_ui_accessibility(document)

    assert report["schema"] == "tigerstudio.painter.ui.accessibility_audit.v1"
    assert report["ok"] is False
    rules = {row["rule_id"] for row in report["issues"]}
    assert {
        "accessible_name",
        "touch_target_size",
        "text_contrast",
        "focus_order_unique",
        "focus_target_available",
    }.issubset(rules)
    assert report["coverage"]["contrast_checked"] == 1


def test_accessibility_audit_resolves_theme_tokens_before_contrast() -> None:
    from app.painter_ui_accessibility_audit import audit_ui_accessibility
    from app.painter_ui_document import (
        add_ui_object,
        add_ui_token,
        create_ui_document,
    )

    document = create_ui_document()
    document, token = add_ui_token(
        document,
        name="Ink",
        kind="color",
        token_value="#111111",
    )
    document, row = add_ui_object(
        document,
        kind="text",
        name="Readable",
        style={"text_color": "#FFFFFF", "font_size": 16},
        content={"text": "Readable"},
    )
    from app.painter_ui_document import update_ui_object

    document, _row = update_ui_object(
        document,
        row["id"],
        {"token_bindings": {"style.text_color": token["id"]}},
    )

    report = audit_ui_accessibility(document)

    assert report["coverage"]["contrast_checked"] == 1
    assert not any(
        row["rule_id"] == "text_contrast" for row in report["issues"]
    )


def test_accessibility_panel_has_friendly_empty_and_compact_report_states() -> None:
    app = _app()
    from app.painter_ui_accessibility_panel import (
        PainterUIAccessibilityPanel,
    )

    panel = PainterUIAccessibilityPanel()
    assert panel.issue_list.item(0).text().strip()

    panel.set_report(
        {
            "severity_counts": {"error": 1, "warning": 1, "info": 0},
            "coverage": {
                "object_count": 3,
                "contrast_checked": 2,
                "contrast_unknown": 1,
            },
            "issues": [
                {
                    "severity": "error",
                    "rule_id": "accessible_name",
                    "object_id": "button-1",
                    "object_name": "Continue",
                    "message": "Missing accessible name.",
                    "remediation": "Set a label.",
                }
            ],
        }
    )

    assert "1" in panel.summary_label.text()
    assert "3" in panel.coverage_label.text()
    assert panel.issue_list.item(0).data(256) == "button-1"
    assert panel.issue_list.maximumHeight() == 180
    panel.deleteLater()
    app.processEvents()


def test_product_qa_panel_displays_nested_accessibility_report() -> None:
    app = _app()
    from app.painter_ui_production_panel import PainterUIProductionPanel

    panel = PainterUIProductionPanel()
    panel.set_audit_report(
        {
            "accessibility": {
                "severity_counts": {"error": 0, "warning": 0, "info": 0},
                "coverage": {
                    "object_count": 2,
                    "contrast_checked": 1,
                    "contrast_unknown": 0,
                },
                "issues": [],
            }
        }
    )

    assert panel.accessibility_panel.summary_label.text().count("0") >= 2
    assert panel.accessibility_panel.issue_list.item(0).text().strip()
    panel.deleteLater()
    app.processEvents()


def test_existing_product_qa_contract_embeds_read_only_accessibility_report() -> None:
    from app.painter_ui_ai_design import audit_ui_design
    from app.painter_ui_document import create_ui_document

    document = create_ui_document()
    before = copy.deepcopy(document)

    report = audit_ui_design(document)

    assert document == before
    assert report["schema"] == "tigerstudio.painter.ui.ai_design_audit.v1"
    assert report["accessibility"]["schema"] == (
        "tigerstudio.painter.ui.accessibility_audit.v1"
    )
