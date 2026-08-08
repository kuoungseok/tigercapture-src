from __future__ import annotations

import copy
import json
from pathlib import Path


def test_mobile_onboarding_native_fixture_is_classification_driven() -> None:
    from tools.qa_painter_ui_unreal_umg_button import (
        EXPECTED_BLOCKED_SOURCE_IDS,
        EXPECTED_SOURCE_LAYER_IDS,
        build_mobile_onboarding_native_fixture,
    )

    fixture = build_mobile_onboarding_native_fixture()
    source = fixture["original_document"]
    runtime = fixture["fixture_document"]

    assert len(runtime["artboards"]) == 1
    assert runtime["artboards"][0]["id"] == source["active_artboard_id"]
    assert fixture["renderable_source_ids"] == list(
        EXPECTED_SOURCE_LAYER_IDS
    )
    assert fixture["blocked_source_ids"] == list(
        EXPECTED_BLOCKED_SOURCE_IDS
    )
    assert fixture["unclassified_source_ids"] == []
    assert [row["id"] for row in runtime["objects"]] == list(
        EXPECTED_SOURCE_LAYER_IDS
    )
    assert runtime["interactions"][0]["action"] == "emit_event"
    assert runtime["interactions"][0]["target_artboard_id"] == ""
    assert runtime["interactions"][0]["parameters"] == {
        "event": "mobile_onboarding_primary_cta_clicked"
    }
    assert fixture["replaced_navigation_interaction_ids"] == [
        "ui-interaction-primary"
    ]


def test_mobile_onboarding_each_artboard_has_a_clean_full_fixture() -> None:
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )
    from tools.qa_painter_ui_unreal_umg_button import (
        BACKGROUND_ID,
        build_mobile_onboarding_native_fixtures,
    )

    fixtures = build_mobile_onboarding_native_fixtures()

    assert list(fixtures) == ["artboard-1", "artboard-2", "artboard-3"]
    generated_document_ids = set()
    for index, (artboard_id, fixture) in enumerate(fixtures.items(), start=1):
        document = fixture["fixture_document"]
        expected_source_ids = [
            f"ui-object-{index}-nav",
            f"ui-object-{index}-brand",
            f"ui-object-{index}-headline",
            f"ui-object-{index}-body",
            f"ui-object-{index}-button",
        ]
        expected_blocked_ids = [
            f"ui-object-{index}-media",
            f"ui-object-{index}-card-a",
            f"ui-object-{index}-card-b",
        ]

        assert document["active_artboard_id"] == artboard_id
        assert len(document["artboards"]) == 1
        assert [row["id"] for row in document["objects"]] == (
            expected_source_ids
        )
        assert fixture["renderable_source_ids"] == expected_source_ids
        assert fixture["blocked_source_ids"] == expected_blocked_ids
        assert fixture["unclassified_source_ids"] == []
        preflight = preflight_painter_umg(document)
        assert preflight["ok"] is True
        assert preflight["counts"] == {
            "Native": 6,
            "Material": 0,
            "Baked": 0,
            "Blocked": 0,
        }
        exported = painter_ui_to_umg_document(document)
        generated_document_ids.add(exported["DocumentId"])
        assert artboard_id in exported["DocumentId"]
        assert [row["Id"] for row in exported["Layers"]] == [
            BACKGROUND_ID,
            *expected_source_ids,
        ]
        for layer in exported["Layers"]:
            assert layer["CanvasSlot"]
            assert layer["CanvasSlot"]["AnchorMinimum"] is not None
            assert layer["CanvasSlot"]["AnchorMaximum"] is not None
    assert len(generated_document_ids) == 3


def test_button_qa_keeps_original_navigation_block_separate() -> None:
    from tools.qa_painter_ui_unreal_umg_button import (
        BACKGROUND_ID,
        BUTTON_ID,
        EXPECTED_ARTBOARD_FILL,
        EXPECTED_BACKGROUND_VISIBILITY,
        EXPECTED_BLOCKED_SOURCE_IDS,
        EXPECTED_BUTTON_FILL,
        EXPECTED_BUTTON_TEXT,
        EXPECTED_LAYER_IDS,
        EXPECTED_SOURCE_LAYER_IDS,
        EXPECTED_TEXT_LAYERS,
        NAVIGATION_BLOCK_REASON,
        build_button_contract_evidence,
    )

    evidence = build_button_contract_evidence()

    assert evidence["ok"] is True
    original = evidence["original_routing"]
    assert original["ok"] is True
    assert original["routing_supported"] is False
    assert original["expected_block_reason"] == NAVIGATION_BLOCK_REASON
    assert original["expected_block_reason_present"] is True
    assert any(
        NAVIGATION_BLOCK_REASON in blocker["reasons"]
        for blocker in original["preflight"]["blockers"]
    )

    fixture = evidence["fixture_contract"]
    assert fixture["ok"] is True
    assert fixture["schema_version"] == 16
    assert fixture["preflight"]["ok"] is True
    assert fixture["layer_ids"] == list(EXPECTED_LAYER_IDS)
    assert fixture["source_visual_preserved_exactly"] is True
    assert fixture["button_visual_preserved_exactly"] is True
    classification = fixture["source_classification"]
    assert classification["ok"] is True
    assert classification["renderable_source_ids"] == list(
        EXPECTED_SOURCE_LAYER_IDS
    )
    assert classification["fixture_object_ids"] == list(
        EXPECTED_SOURCE_LAYER_IDS
    )
    assert classification["blocked_source_ids"] == list(
        EXPECTED_BLOCKED_SOURCE_IDS
    )
    assert classification["unclassified_source_ids"] == []
    assert set(classification["active_source_ids"]) - set(
        classification["fixture_object_ids"]
    ) == set(EXPECTED_BLOCKED_SOURCE_IDS)
    assert classification["replaced_navigation_interaction_ids"] == [
        "ui-interaction-primary"
    ]

    assert fixture["text_contract_ok"] is True
    assert set(fixture["text_layers"]) == set(EXPECTED_TEXT_LAYERS)
    for layer_id, expected in EXPECTED_TEXT_LAYERS.items():
        actual = fixture["text_layers"][layer_id]
        assert actual["name"] == expected["name"]
        assert actual["text"] == expected["text"]
        assert actual["font_size"] == expected["font_size"]
        assert actual["font_size_unit"] == "css_px_96dpi"
        assert actual["position"]
        assert actual["size"]
        assert actual["canvas_slot"]
        assert actual["layout"]["ok"] is True
        assert actual["layout"]["rect_matches_source"] is True

    assert set(fixture["source_layout"]) == set(
        EXPECTED_SOURCE_LAYER_IDS
    )
    assert all(row["ok"] for row in fixture["source_layout"].values())
    normal = fixture["fixture_button_visual"]["button_style"]["Normal"]
    assert normal["Fill"] == EXPECTED_BUTTON_FILL
    assert normal["TextColor"] == EXPECTED_BUTTON_TEXT
    assert normal["FontSize"] == 19.0
    assert list(normal["CornerRadii"].values()) == [8.0, 8.0, 8.0, 8.0]

    background = fixture["artboard_background"]
    assert background["metadata"] == {
        "mode": "included",
        "color": EXPECTED_ARTBOARD_FILL,
        "layer_id": BACKGROUND_ID,
    }
    assert background["layer"]["Kind"] == "Image"
    assert background["layer"]["Disposition"] == "Native"
    assert (
        background["layer"]["Visibility"]
        == EXPECTED_BACKGROUND_VISIBILITY
    )
    assert json.loads(background["layer"]["PayloadJson"])[
        "artboard_background"
    ] is True

    interaction = fixture["runtime_interaction"]
    assert interaction["ComponentId"] == BUTTON_ID
    assert interaction["Trigger"] == "clicked"
    assert interaction["Actions"][0]["Type"] == "emit_event"
    assert interaction["Actions"][0]["TargetId"] == ""


def test_button_qa_audit_matches_all_four_real_slate_states() -> None:
    from tools.qa_painter_ui_unreal_umg_button import (
        _expected_button_audit,
        build_button_contract_evidence,
        compare_button_style_audit,
    )

    evidence = build_button_contract_evidence()
    style = evidence["fixture_contract"]["fixture_button_visual"][
        "button_style"
    ]
    expected = _expected_button_audit(style)
    report = compare_button_style_audit(json.dumps(expected), style)

    assert report["ok"] is True
    assert set(report["actual"]) == {
        "schema",
        "enabled",
        "image_fill_background",
        "label_font",
        "normal",
        "hovered",
        "pressed",
        "disabled",
    }
    assert report["actual"]["normal"]["font_size"] == 19.0
    assert report["actual"]["label_font"] == {
        "authored_size": 19.0,
        "authored_unit": "css_px_96dpi",
        "applied_slate_points": 14.25,
        "display_css_px_96dpi": 19.0,
    }
    assert report["actual"]["normal"]["radii"] == [8.0] * 4
    assert report["actual"]["normal"]["fill"] == "#5B6CFFFF"
    assert report["actual"]["hovered"]["fill"] != ""
    assert report["actual"]["pressed"]["fill"] != ""
    assert report["actual"]["disabled"]["opacity"] == 0.45

    mismatched = copy.deepcopy(expected)
    mismatched["normal"]["font_size"] = 18.0
    rejected = compare_button_style_audit(mismatched, style)
    assert rejected["ok"] is False
    assert rejected["actual"]["normal"]["font_size"] == 18.0
    assert rejected["expected"]["normal"]["font_size"] == 19.0

    legacy_expected = _expected_button_audit(style, font_size_unit="")
    assert legacy_expected["label_font"] == {
        "authored_size": 19.0,
        "authored_unit": "legacy_slate_points",
        "applied_slate_points": 19.0,
        "display_css_px_96dpi": 25.3333,
    }
    legacy_report = compare_button_style_audit(
        json.dumps(legacy_expected),
        style,
        font_size_unit="",
    )
    assert legacy_report["ok"] is True


def test_button_qa_pixel_contract_sees_background_fill_and_rounding(
    tmp_path: Path,
) -> None:
    from PIL import Image, ImageDraw

    from tools.qa_painter_ui_unreal_umg_button import (
        EXPECTED_ARTBOARD_FILL,
        EXPECTED_BUTTON_FILL,
        compare_mobile_button_render,
    )

    artboard_rgb = (247, 248, 252, 255)
    button_rgb = (91, 108, 255, 255)
    actual = tmp_path / "button.png"
    image = Image.new("RGBA", (390, 844), artboard_rgb)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (24, 332, 283, 387),
        radius=8,
        fill=button_rgb,
    )
    text_rects = {
        "ui-object-1-brand": {
            "x": 24.0,
            "y": 12.0,
            "width": 195.0,
            "height": 40.0,
        },
        "ui-object-1-headline": {
            "x": 24.0,
            "y": 88.0,
            "width": 342.0,
            "height": 110.0,
        },
        "ui-object-1-body": {
            "x": 24.0,
            "y": 212.0,
            "width": 342.0,
            "height": 90.0,
        },
    }
    for rect in text_rects.values():
        draw.rectangle(
            (
                int(rect["x"]) + 4,
                int(rect["y"]) + 4,
                int(rect["x"]) + 16,
                int(rect["y"]) + 8,
            ),
            fill=(17, 24, 39, 255),
        )
    body_rect = text_rects["ui-object-1-body"]
    draw.rectangle(
        (250, int(body_rect["y"]) + 12, 268, int(body_rect["y"]) + 20),
        fill=(17, 24, 39, 255),
    )
    draw.rectangle(
        (205, int(body_rect["y"]) + 48, 225, int(body_rect["y"]) + 57),
        fill=(17, 24, 39, 255),
    )
    image.save(actual)

    report = compare_mobile_button_render(
        actual,
        artboard_fill=EXPECTED_ARTBOARD_FILL,
        button_fill=EXPECTED_BUTTON_FILL,
        button_rect={
            "x": 24.0,
            "y": 332.0,
            "width": 260.0,
            "height": 56.0,
        },
        text_rects=text_rects,
    )

    assert report["ok"] is True
    assert all(report["checks"].values())
    assert report["rounded_corner"]["actual_rgb"] == [247, 248, 252]
    assert report["interior"]["actual_rgb"] == [91, 108, 255]
    assert report["checks"]["authored_text_visible"] is True
    assert report["checks"]["source_visible_body_two_line_parity"] is True
    assert report["checks"]["wrapped_text_clipped"] is True
    assert report["source_visible_body_text"]["line_1_tail"]["ink_pixels"] > 0
    assert report["source_visible_body_text"]["line_2_tail"]["ink_pixels"] > 0
    assert all(row["ok"] for row in report["text_ink"].values())
    assert report["text_overflow_guard"]["ink_pixels"] == 0

    oversized_wrap = tmp_path / "oversized_wrap.png"
    oversized_wrap_image = image.copy()
    ImageDraw.Draw(oversized_wrap_image).rectangle(
        (243, 212, 332, 253),
        fill=artboard_rgb,
    )
    oversized_wrap_image.save(oversized_wrap)
    oversized_wrap_report = compare_mobile_button_render(
        oversized_wrap,
        artboard_fill=EXPECTED_ARTBOARD_FILL,
        button_fill=EXPECTED_BUTTON_FILL,
        button_rect={
            "x": 24.0,
            "y": 332.0,
            "width": 260.0,
            "height": 56.0,
        },
        text_rects=text_rects,
    )
    assert oversized_wrap_report["ok"] is False
    assert (
        oversized_wrap_report["checks"][
            "source_visible_body_two_line_parity"
        ]
        is False
    )
    assert (
        oversized_wrap_report["source_visible_body_text"]["line_1_tail"][
            "ink_pixels"
        ]
        == 0
    )

    overflow = tmp_path / "overflow.png"
    overflow_image = image.copy()
    ImageDraw.Draw(overflow_image).rectangle(
        (28, 306, 120, 316),
        fill=(17, 24, 39, 255),
    )
    overflow_image.save(overflow)
    overflow_report = compare_mobile_button_render(
        overflow,
        artboard_fill=EXPECTED_ARTBOARD_FILL,
        button_fill=EXPECTED_BUTTON_FILL,
        button_rect={
            "x": 24.0,
            "y": 332.0,
            "width": 260.0,
            "height": 56.0,
        },
        text_rects=text_rects,
    )
    assert overflow_report["ok"] is False
    assert overflow_report["checks"]["wrapped_text_clipped"] is False
    assert overflow_report["text_overflow_guard"]["ink_pixels"] > 0

    broken = tmp_path / "transparent.png"
    Image.new("RGBA", (390, 844), (0, 0, 0, 0)).save(broken)
    rejected = compare_mobile_button_render(
        broken,
        artboard_fill=EXPECTED_ARTBOARD_FILL,
        button_fill=EXPECTED_BUTTON_FILL,
        button_rect={
            "x": 24.0,
            "y": 332.0,
            "width": 260.0,
            "height": 56.0,
        },
    )
    assert rejected["ok"] is False
    assert rejected["checks"]["opaque"] is False
    assert rejected["checks"]["background_patch"] is False
    assert rejected["checks"]["button_patch"] is False


def test_unreal_runner_serializes_button_and_visibility_audits(
    tmp_path: Path,
) -> None:
    from app.unreal_umg_workflow import _runner_script

    script = _runner_script(
        tmp_path / "document.json",
        tmp_path / "report.json",
        "/Game/TigerStudio/GeneratedButtonQA",
    )

    assert 'read_property(result, "generated_button_style_audit")' in script
    assert '"generated_button_style_audit"' in script
    assert (
        'read_property(result, "generated_widget_visibility_audit")'
        in script
    )
    assert '"generated_widget_visibility_audit"' in script


def test_button_qa_runtime_contract_requires_typed_unreal_results() -> None:
    from tools.qa_painter_ui_unreal_umg_button import (
        BACKGROUND_ID,
        BUTTON_ID,
        EXPECTED_BACKGROUND_VISIBILITY,
        EXPECTED_BUTTON_VISIBILITY,
        EXPECTED_WIDGET_VISIBILITY,
        EXPECTED_WIDGET_CLASSES,
    )

    assert EXPECTED_WIDGET_CLASSES == {
        BACKGROUND_ID: "Image",
        "ui-object-1-nav": "CanvasPanel",
        "ui-object-1-brand": "TextBlock",
        "ui-object-1-headline": "TextBlock",
        "ui-object-1-body": "TextBlock",
        BUTTON_ID: "TigerStudioButton",
    }
    assert EXPECTED_BACKGROUND_VISIBILITY == "HitTestInvisible"
    assert EXPECTED_BUTTON_VISIBILITY == "Visible"
    assert EXPECTED_WIDGET_VISIBILITY == {
        BACKGROUND_ID: "HitTestInvisible",
        "ui-object-1-nav": "Visible",
        "ui-object-1-brand": "Visible",
        "ui-object-1-headline": "Visible",
        "ui-object-1-body": "Visible",
        BUTTON_ID: "Visible",
    }
