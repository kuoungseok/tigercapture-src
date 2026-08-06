"""Headless real-UE proof for the Mobile Onboarding schema-16 fixture.

The checked fixture intentionally separates two claims:

* The unmodified Mobile Onboarding sample remains preflight-blocked because
  its Figma ``navigate`` reaction still needs a UMG screen router.
* A runtime fixture keeps every active-artboard source layer that the exact
  adapter classifies as Native, Material, or Baked.  It removes only source
  layers explicitly classified Blocked and changes the unsupported CTA
  navigation to the already supported ``emit_event`` action.  The fixture
  therefore proves the complete native-visible screen (background, text,
  layout, and CTA), not a button-only reconstruction.
* That fixture must generate, compile, reopen, and render as a real Widget
  Blueprint without opening an editor UI.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageStat


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_ui_templates import instantiate_ui_template
from app.painter_ui_umg_adapter import (
    PAINTER_UMG_FONT_SIZE_UNIT,
    generate_painter_umg,
    painter_ui_to_umg_document,
    preflight_painter_umg,
)
from app.unreal_umg_workflow import DEFAULT_UNREAL_ENGINE_ROOT
from tools.qa_painter_ui_unreal_umg import (
    _ensure_project,
    _render_generated_asset,
    _reopen_generated_asset,
)


DEFAULT_WORKSPACE = (
    ROOT
    / "debugCapture"
    / "painter_ui_designer"
    / "unreal_umg_button_schema16"
)
BUTTON_ID = "ui-object-1-button"
BACKGROUND_ID = "__tiger_artboard_background"
NAVIGATION_BLOCK_REASON = "figma_navigation_requires_umg_screen_router"
RENDERABLE_DISPOSITIONS = frozenset({"Native", "Material", "Baked"})
EXPECTED_SOURCE_LAYER_IDS = (
    "ui-object-1-nav",
    "ui-object-1-brand",
    "ui-object-1-headline",
    "ui-object-1-body",
    BUTTON_ID,
)
EXPECTED_BLOCKED_SOURCE_IDS = (
    "ui-object-1-media",
    "ui-object-1-card-a",
    "ui-object-1-card-b",
)
EXPECTED_LAYER_IDS = (BACKGROUND_ID, *EXPECTED_SOURCE_LAYER_IDS)
EXPECTED_TEXT_LAYERS = {
    "ui-object-1-brand": {
        "name": "Brand",
        "text": "Mobile Onboarding Flow",
        "font_size": 14.0,
    },
    "ui-object-1-headline": {
        "name": "Hero Headline",
        "text": "Make every idea visible",
        "font_size": 38.0,
    },
    "ui-object-1-body": {
        "name": "Supporting Copy",
        "text": (
            "A complete editable starting point with sensible structure "
            "and reusable foundations."
        ),
        "font_size": 31.0,
    },
}
EXPECTED_WIDGET_CLASSES = {
    BACKGROUND_ID: "Image",
    "ui-object-1-nav": "CanvasPanel",
    "ui-object-1-brand": "TextBlock",
    "ui-object-1-headline": "TextBlock",
    "ui-object-1-body": "TextBlock",
    BUTTON_ID: "TigerStudioButton",
}
EXPECTED_BACKGROUND_VISIBILITY = "HitTestInvisible"
EXPECTED_BUTTON_VISIBILITY = "Visible"
EXPECTED_WIDGET_VISIBILITY = {
    layer_id: (
        EXPECTED_BACKGROUND_VISIBILITY
        if layer_id == BACKGROUND_ID
        else EXPECTED_BUTTON_VISIBILITY
    )
    for layer_id in EXPECTED_LAYER_IDS
}
EXPECTED_BUTTON_FILL = "#5B6CFFFF"
EXPECTED_BUTTON_TEXT = "#111827FF"
EXPECTED_ARTBOARD_FILL = "#F7F8FCFF"
EXPECTED_BUTTON_FONT_SIZE = 19.0
EXPECTED_BUTTON_RADII = [8.0, 8.0, 8.0, 8.0]
PIXEL_CHANNEL_ERROR_MAX = 12.0
EXPECTED_FONT_SIZE_UNIT = PAINTER_UMG_FONT_SIZE_UNIT
CSS_PIXELS_PER_SLATE_POINT_96_DPI = 96.0 / 72.0


def build_mobile_onboarding_native_fixture(
    artboard_id: str | None = None,
) -> dict[str, Any]:
    """Build a classification-driven, full active-artboard runtime fixture.

    The exact unmodified template is classified first.  Source objects enter
    the fixture only when their corresponding UMG layer is Native, Material,
    or Baked; source objects whose layer is Blocked are the only active-board
    objects omitted.  This keeps the selection policy reusable when the
    adapter gains support for another layer in the sample.
    """

    original, template_report = instantiate_ui_template(
        "mobile_onboarding"
    )
    available_artboard_ids = [
        str(row.get("id") or "") for row in original.get("artboards", [])
    ]
    target_artboard_id = str(
        artboard_id or original.get("active_artboard_id") or ""
    )
    if target_artboard_id not in available_artboard_ids:
        raise ValueError(
            "Unknown Mobile Onboarding artboard: "
            f"{target_artboard_id!r}"
        )
    original_umg = painter_ui_to_umg_document(
        original,
        artboard_id=target_artboard_id,
    )
    original_layers = {
        str(row.get("Id") or ""): row
        for row in original_umg.get("Layers", [])
        if str(row.get("Id") or "") != BACKGROUND_ID
    }
    active_source_ids = [
        str(row.get("id") or "")
        for row in original.get("objects", [])
        if str(row.get("artboard_id") or "") == target_artboard_id
    ]
    renderable_source_ids = [
        source_id
        for source_id in active_source_ids
        if str(
            original_layers.get(source_id, {}).get("Disposition") or ""
        )
        in RENDERABLE_DISPOSITIONS
    ]
    blocked_source_ids = [
        source_id
        for source_id in active_source_ids
        if str(
            original_layers.get(source_id, {}).get("Disposition") or ""
        )
        == "Blocked"
    ]
    unclassified_source_ids = [
        source_id
        for source_id in active_source_ids
        if source_id not in original_layers
    ]

    fixture = copy.deepcopy(original)
    fixture["active_artboard_id"] = target_artboard_id
    fixture["document_id"] = (
        f"{fixture['document_id']}-{target_artboard_id}"
        "-umg-full-native-schema16-qa"
    )
    fixture["artboards"] = [
        row
        for row in fixture["artboards"]
        if str(row.get("id") or "") == target_artboard_id
    ]
    fixture["objects"] = [
        row
        for row in fixture["objects"]
        if str(row.get("artboard_id") or "") == target_artboard_id
        and str(row.get("id") or "") in renderable_source_ids
    ]
    retained_source_ids = {
        str(row.get("id") or "") for row in fixture["objects"]
    }
    fixture_interactions: list[dict[str, Any]] = []
    replaced_navigation_ids: list[str] = []
    for source_interaction in fixture.get("interactions", []):
        if (
            str(source_interaction.get("source_object_id") or "")
            not in retained_source_ids
        ):
            continue
        interaction = copy.deepcopy(source_interaction)
        if str(interaction.get("action") or "") == "navigate":
            replaced_navigation_ids.append(str(interaction.get("id") or ""))
            interaction.update(
                {
                    "name": "Mobile Onboarding CTA event",
                    "action": "emit_event",
                    "target_artboard_id": "",
                    "target_object_id": "",
                    "component_id": "",
                    "motion_clip_id": "",
                    "parameters": {
                        "event": "mobile_onboarding_primary_cta_clicked"
                    },
                }
            )
        fixture_interactions.append(interaction)
    fixture["interactions"] = fixture_interactions
    return {
        "original_document": original,
        "fixture_document": fixture,
        "template_report": template_report,
        "original_umg_document": original_umg,
        "active_artboard_id": target_artboard_id,
        "available_artboard_ids": available_artboard_ids,
        "active_source_ids": active_source_ids,
        "renderable_source_ids": renderable_source_ids,
        "blocked_source_ids": blocked_source_ids,
        "unclassified_source_ids": unclassified_source_ids,
        "replaced_navigation_interaction_ids": replaced_navigation_ids,
    }


def build_mobile_onboarding_native_fixtures() -> dict[str, dict[str, Any]]:
    """Return one independently generatable fixture per source artboard."""

    source, _report = instantiate_ui_template("mobile_onboarding")
    return {
        str(row.get("id") or ""): build_mobile_onboarding_native_fixture(
            str(row.get("id") or "")
        )
        for row in source.get("artboards", [])
    }


def _mobile_onboarding_button_documents() -> tuple[dict, dict, dict]:
    """Compatibility wrapper returning the full native-visible fixture."""

    bundle = build_mobile_onboarding_native_fixture()
    return (
        bundle["original_document"],
        bundle["fixture_document"],
        bundle["template_report"],
    )


def _layer_by_id(document: Mapping[str, Any], layer_id: str) -> dict:
    return copy.deepcopy(
        next(
            row
            for row in document.get("Layers", [])
            if str(row.get("Id") or "") == layer_id
        )
    )


def _button_visual_contract(layer: Mapping[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(str(layer.get("PayloadJson") or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}
    return {
        "name": str(layer.get("Name") or ""),
        "kind": str(layer.get("Kind") or ""),
        "position": copy.deepcopy(layer.get("Position")),
        "size": copy.deepcopy(layer.get("Size")),
        "canvas_slot": copy.deepcopy(layer.get("CanvasSlot")),
        "opacity": layer.get("Opacity"),
        "text": str(payload.get("text") or ""),
        "font_size": float(payload.get("font_size") or 0.0),
        "font_size_unit": str(payload.get("font_size_unit") or ""),
        "button_style": copy.deepcopy(layer.get("ButtonStyle")),
    }


def _payload(layer: Mapping[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(str(layer.get("PayloadJson") or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _source_canvas_slot_contract(
    source: Mapping[str, Any],
    layer: Mapping[str, Any],
) -> dict[str, Any]:
    """Prove a top-level source rect is recoverable from its CanvasSlot."""

    canvas_slot = layer.get("CanvasSlot")
    size = layer.get("Size")
    if not isinstance(canvas_slot, Mapping) or not isinstance(size, Mapping):
        return {
            "ok": False,
            "canvas_slot": copy.deepcopy(canvas_slot),
            "reason": "canvas_slot_or_size_missing",
        }
    anchors_min = canvas_slot.get("AnchorMinimum")
    anchors_max = canvas_slot.get("AnchorMaximum")
    offsets = canvas_slot.get("Offsets")
    alignment = canvas_slot.get("Alignment")
    if not all(
        isinstance(row, Mapping)
        for row in (anchors_min, anchors_max, offsets, alignment)
    ):
        return {
            "ok": False,
            "canvas_slot": copy.deepcopy(canvas_slot),
            "reason": "canvas_slot_fields_missing",
        }

    def number(row: Mapping[str, Any], key: str) -> float:
        return float(row.get(key) or 0.0)

    source_rect = {
        "x": float(source.get("x") or 0.0),
        "y": float(source.get("y") or 0.0),
        "width": float(source.get("width") or 0.0),
        "height": float(source.get("height") or 0.0),
    }
    reconstructed_rect = {
        "x": (
            number(offsets, "Left")
            - number(size, "X") * number(alignment, "X")
        ),
        "y": (
            number(offsets, "Top")
            - number(size, "Y") * number(alignment, "Y")
        ),
        "width": number(size, "X"),
        "height": number(size, "Y"),
    }
    fixed_top_left_anchors = all(
        abs(number(row, axis)) <= 1e-6
        for row in (anchors_min, anchors_max)
        for axis in ("X", "Y")
    )
    rect_matches = all(
        abs(source_rect[key] - reconstructed_rect[key]) <= 1e-6
        for key in source_rect
    )
    return {
        "ok": fixed_top_left_anchors and rect_matches,
        "canvas_slot": copy.deepcopy(dict(canvas_slot)),
        "source_rect": source_rect,
        "reconstructed_rect": reconstructed_rect,
        "fixed_top_left_anchors": fixed_top_left_anchors,
        "rect_matches_source": rect_matches,
    }


def _artboard_background_canvas_slot_ok(layer: Mapping[str, Any]) -> bool:
    slot = layer.get("CanvasSlot")
    if not isinstance(slot, Mapping):
        return False
    return slot == {
        "AnchorMinimum": {"X": 0.0, "Y": 0.0},
        "AnchorMaximum": {"X": 1.0, "Y": 1.0},
        "Offsets": {
            "Left": 0.0,
            "Top": 0.0,
            "Right": 0.0,
            "Bottom": 0.0,
        },
        "Alignment": {"X": 0.0, "Y": 0.0},
    }


def _navigation_reason_present(preflight: Mapping[str, Any]) -> bool:
    return any(
        NAVIGATION_BLOCK_REASON
        in [str(reason) for reason in blocker.get("reasons", [])]
        for blocker in preflight.get("blockers", [])
        if isinstance(blocker, Mapping)
    )


def build_button_contract_evidence() -> dict[str, Any]:
    """Build the full active-artboard, non-Unreal acceptance report."""

    fixture_bundle = build_mobile_onboarding_native_fixture()
    original = fixture_bundle["original_document"]
    fixture = fixture_bundle["fixture_document"]
    template_report = fixture_bundle["template_report"]
    original_umg = fixture_bundle["original_umg_document"]
    fixture_umg = painter_ui_to_umg_document(fixture)
    original_preflight = preflight_painter_umg(original)
    fixture_preflight = preflight_painter_umg(fixture)
    original_button = _layer_by_id(original_umg, BUTTON_ID)
    fixture_button = _layer_by_id(fixture_umg, BUTTON_ID)
    background = _layer_by_id(fixture_umg, BACKGROUND_ID)
    background_payload = json.loads(background["PayloadJson"])
    original_visual = _button_visual_contract(original_button)
    fixture_visual = _button_visual_contract(fixture_button)
    interaction = fixture_umg["Interactions"][0]
    action = interaction["Actions"][0]
    style = fixture_button["ButtonStyle"]
    normal = style.get("Normal", {})
    radii = normal.get("CornerRadii", {})
    fixture_layer_ids = [
        str(row.get("Id") or "") for row in fixture_umg["Layers"]
    ]
    fixture_object_ids = [
        str(row.get("id") or "") for row in fixture.get("objects", [])
    ]
    source_by_id = {
        str(row.get("id") or ""): row
        for row in fixture.get("objects", [])
    }
    fixture_layers_by_id = {
        str(row.get("Id") or ""): row
        for row in fixture_umg.get("Layers", [])
    }
    original_layers_by_id = {
        str(row.get("Id") or ""): row
        for row in original_umg.get("Layers", [])
    }
    source_layout = {
        layer_id: _source_canvas_slot_contract(
            source_by_id[layer_id],
            fixture_layers_by_id[layer_id],
        )
        for layer_id in fixture_object_ids
        if layer_id in fixture_layers_by_id
    }
    text_layers = {
        layer_id: {
            "name": str(fixture_layers_by_id[layer_id].get("Name") or ""),
            "text": str(_payload(fixture_layers_by_id[layer_id]).get("text") or ""),
            "font_size": float(
                _payload(fixture_layers_by_id[layer_id]).get("font_size")
                or 0.0
            ),
            "font_size_unit": str(
                _payload(fixture_layers_by_id[layer_id]).get(
                    "font_size_unit"
                )
                or ""
            ),
            "position": copy.deepcopy(
                fixture_layers_by_id[layer_id].get("Position")
            ),
            "size": copy.deepcopy(fixture_layers_by_id[layer_id].get("Size")),
            "canvas_slot": copy.deepcopy(
                fixture_layers_by_id[layer_id].get("CanvasSlot")
            ),
            "layout": source_layout.get(layer_id),
        }
        for layer_id in EXPECTED_TEXT_LAYERS
        if layer_id in fixture_layers_by_id
    }
    text_contract_ok = (
        set(text_layers) == set(EXPECTED_TEXT_LAYERS)
        and all(
            row["name"] == EXPECTED_TEXT_LAYERS[layer_id]["name"]
            and row["text"] == EXPECTED_TEXT_LAYERS[layer_id]["text"]
            and row["font_size"]
            == EXPECTED_TEXT_LAYERS[layer_id]["font_size"]
            and row["font_size_unit"] == EXPECTED_FONT_SIZE_UNIT
            and bool((row.get("layout") or {}).get("ok"))
            for layer_id, row in text_layers.items()
        )
    )
    retained_layers_preserved = (
        set(EXPECTED_LAYER_IDS).issubset(original_layers_by_id)
        and set(EXPECTED_LAYER_IDS).issubset(fixture_layers_by_id)
        and all(
            original_layers_by_id[layer_id]
            == fixture_layers_by_id[layer_id]
            for layer_id in EXPECTED_LAYER_IDS
        )
    )
    classification_ok = (
        fixture_bundle["renderable_source_ids"]
        == list(EXPECTED_SOURCE_LAYER_IDS)
        and fixture_bundle["blocked_source_ids"]
        == list(EXPECTED_BLOCKED_SOURCE_IDS)
        and not fixture_bundle["unclassified_source_ids"]
        and fixture_object_ids == list(EXPECTED_SOURCE_LAYER_IDS)
        and set(fixture_bundle["active_source_ids"])
        - set(fixture_object_ids)
        == set(fixture_bundle["blocked_source_ids"])
        and fixture_bundle["replaced_navigation_interaction_ids"]
        == ["ui-interaction-primary"]
    )

    original_routing = {
        "ok": (
            not bool(original_preflight.get("ok"))
            and _navigation_reason_present(original_preflight)
        ),
        "routing_supported": False,
        "expected_block_reason": NAVIGATION_BLOCK_REASON,
        "expected_block_reason_present": _navigation_reason_present(
            original_preflight
        ),
        "preflight": original_preflight,
    }
    fixture_contract = {
        "ok": (
            fixture_umg.get("SchemaVersion") == 16
            and fixture_layer_ids == list(EXPECTED_LAYER_IDS)
            and bool(fixture_preflight.get("ok"))
            and classification_ok
            and retained_layers_preserved
            and text_contract_ok
            and len(source_layout) == len(EXPECTED_SOURCE_LAYER_IDS)
            and all(row["ok"] for row in source_layout.values())
            and background.get("Kind") == "Image"
            and background.get("Disposition") == "Native"
            and background.get("Visibility")
            == EXPECTED_BACKGROUND_VISIBILITY
            and _artboard_background_canvas_slot_ok(background)
            and background_payload.get("artboard_background") is True
            and background_payload.get("fill")
            == EXPECTED_ARTBOARD_FILL
            and interaction.get("ComponentId") == BUTTON_ID
            and interaction.get("Trigger") == "clicked"
            and action.get("Type") == "emit_event"
            and normal.get("Fill") == EXPECTED_BUTTON_FILL
            and normal.get("TextColor") == EXPECTED_BUTTON_TEXT
            and float(normal.get("FontSize") or 0.0)
            == EXPECTED_BUTTON_FONT_SIZE
            and fixture_visual.get("font_size_unit")
            == EXPECTED_FONT_SIZE_UNIT
            and [
                float(radii.get(axis) or 0.0)
                for axis in ("X", "Y", "Z", "W")
            ]
            == EXPECTED_BUTTON_RADII
        ),
        "schema_version": fixture_umg.get("SchemaVersion"),
        "layer_ids": fixture_layer_ids,
        "preflight": fixture_preflight,
        "source_visual_preserved_exactly": retained_layers_preserved,
        "button_visual_preserved_exactly": original_visual == fixture_visual,
        "source_classification": {
            "ok": classification_ok,
            "active_source_ids": fixture_bundle["active_source_ids"],
            "renderable_source_ids": fixture_bundle[
                "renderable_source_ids"
            ],
            "blocked_source_ids": fixture_bundle["blocked_source_ids"],
            "unclassified_source_ids": fixture_bundle[
                "unclassified_source_ids"
            ],
            "fixture_object_ids": fixture_object_ids,
            "replaced_navigation_interaction_ids": fixture_bundle[
                "replaced_navigation_interaction_ids"
            ],
        },
        "source_layout": source_layout,
        "text_layers": text_layers,
        "text_contract_ok": text_contract_ok,
        "original_button_visual": original_visual,
        "fixture_button_visual": fixture_visual,
        "artboard_background": {
            "layer": background,
            "metadata": fixture_umg.get("PainterSource", {}).get(
                "ArtboardBackground"
            ),
        },
        "runtime_interaction": interaction,
    }
    return {
        "ok": original_routing["ok"] and fixture_contract["ok"],
        "template": {
            "id": "mobile_onboarding",
            "report": template_report,
            "active_artboard_id": fixture["active_artboard_id"],
            "button_id": BUTTON_ID,
            "retained_source_layer_ids": list(EXPECTED_SOURCE_LAYER_IDS),
        },
        "original_routing": original_routing,
        "fixture_contract": fixture_contract,
        "original_document": original,
        "fixture_document": fixture,
        "fixture_umg_document": fixture_umg,
    }


def _expected_button_audit(
    style: Mapping[str, Any],
    *,
    font_size_unit: str = EXPECTED_FONT_SIZE_UNIT,
) -> dict[str, Any]:
    def audit_number(value: float) -> float:
        # C++ emits the audit through FString::Printf("%.6g").
        return float(f"{float(value):.6g}")

    def state(name: str) -> dict[str, Any]:
        row = style[name]
        radii = row["CornerRadii"]
        return {
            "fill": row["Fill"],
            "stroke": row["Stroke"],
            "stroke_width": float(row["StrokeWidth"]),
            "radii": [
                float(radii[axis]) for axis in ("X", "Y", "Z", "W")
            ],
            "text": row["TextColor"],
            "font_size": float(row["FontSize"]),
            "font_weight": int(row["FontWeight"]),
            "opacity": float(row["Opacity"]),
        }

    authored_font_size = float(style["Normal"]["FontSize"])
    applied_slate_points = (
        authored_font_size / CSS_PIXELS_PER_SLATE_POINT_96_DPI
        if font_size_unit == "css_px_96dpi"
        else authored_font_size
    )
    return {
        "schema": style["Schema"],
        "enabled": bool(style["Enabled"]),
        "image_fill_background": False,
        "label_font": {
            "authored_size": audit_number(authored_font_size),
            "authored_unit": font_size_unit or "legacy_slate_points",
            "applied_slate_points": audit_number(applied_slate_points),
            "display_css_px_96dpi": audit_number(
                applied_slate_points * CSS_PIXELS_PER_SLATE_POINT_96_DPI
            ),
        },
        "normal": state("Normal"),
        "hovered": state("Hovered"),
        "pressed": state("Pressed"),
        "disabled": state("Disabled"),
    }


def compare_button_style_audit(
    raw_audit: object,
    expected_style: Mapping[str, Any],
    *,
    font_size_unit: str = EXPECTED_FONT_SIZE_UNIT,
) -> dict[str, Any]:
    """Compare the C++ post-construction FButtonStyle audit to the record."""

    expected = _expected_button_audit(
        expected_style,
        font_size_unit=font_size_unit,
    )
    try:
        actual = (
            json.loads(raw_audit)
            if isinstance(raw_audit, str)
            else copy.deepcopy(dict(raw_audit))
            if isinstance(raw_audit, Mapping)
            else {}
        )
        parse_error = ""
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        actual = {}
        parse_error = str(exc)
    return {
        "ok": not parse_error and actual == expected,
        "actual": actual,
        "expected": expected,
        "parse_error": parse_error,
    }


def _hex_rgb(value: str) -> tuple[int, int, int]:
    source = str(value or "").removeprefix("#")
    if len(source) not in {6, 8}:
        raise ValueError(f"Expected RGB/RGBA hex color, got {value!r}")
    return tuple(int(source[index : index + 2], 16) for index in (0, 2, 4))


def _rgb_error(
    actual: tuple[float, float, float],
    expected: tuple[int, int, int],
) -> list[float]:
    return [abs(float(actual[index]) - expected[index]) for index in range(3)]


def compare_mobile_button_render(
    actual_path: Path,
    *,
    artboard_fill: str,
    button_fill: str,
    button_rect: Mapping[str, Any],
    text_rects: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify background, CTA, rounding, and optional authored text ink."""

    expected_size = (390, 844)
    try:
        source = Image.open(actual_path).convert("RGBA")
    except Exception as exc:
        return {
            "ok": False,
            "actual_path": str(actual_path),
            "error": str(exc),
        }
    image = Image.new("RGBA", source.size, (0, 0, 0, 255))
    image.alpha_composite(source)
    rgb = image.convert("RGB")
    x = round(float(button_rect["x"]))
    y = round(float(button_rect["y"]))
    width = round(float(button_rect["width"]))
    height = round(float(button_rect["height"]))
    bounds_ok = (
        0 <= x < x + width <= rgb.width
        and 0 <= y < y + height <= rgb.height
    )
    if not bounds_ok:
        return {
            "ok": False,
            "actual_path": str(actual_path),
            "size": list(rgb.size),
            "expected_size": list(expected_size),
            "button_rect": [x, y, width, height],
            "error": "button_rect_outside_render",
        }

    background_patch = rgb.crop((4, 4, 20, 20))
    # The CTA label is centered; this left-side patch contains only its brush.
    button_patch = rgb.crop(
        (
            x + 20,
            y + max(12, height // 3),
            x + min(80, width // 3),
            y + min(height - 12, height * 2 // 3),
        )
    )
    background_mean = tuple(ImageStat.Stat(background_patch).mean[:3])
    button_mean = tuple(ImageStat.Stat(button_patch).mean[:3])
    expected_background = _hex_rgb(artboard_fill)
    expected_button = _hex_rgb(button_fill)
    background_error = _rgb_error(background_mean, expected_background)
    button_error = _rgb_error(button_mean, expected_button)
    corner_rgb = rgb.getpixel((x, y))
    interior_rgb = rgb.getpixel((x + 12, y + height // 2))
    corner_error = _rgb_error(corner_rgb, expected_background)
    interior_error = _rgb_error(interior_rgb, expected_button)
    alpha_extrema = source.getchannel("A").getextrema()
    text_ink: dict[str, dict[str, Any]] = {}
    for layer_id, rect in (text_rects or {}).items():
        text_x = round(float(rect["x"]))
        text_y = round(float(rect["y"]))
        text_width = round(float(rect["width"]))
        text_height = round(float(rect["height"]))
        text_bounds = (
            text_x,
            text_y,
            text_x + text_width,
            text_y + text_height,
        )
        bounds_valid = (
            0 <= text_bounds[0] < text_bounds[2] <= rgb.width
            and 0 <= text_bounds[1] < text_bounds[3] <= rgb.height
        )
        ink_pixels = 0
        if bounds_valid:
            patch = rgb.crop(text_bounds)
            color_counts = patch.getcolors(
                maxcolors=max(1, patch.width * patch.height)
            ) or []
            for count, pixel in color_counts:
                if max(_rgb_error(pixel, expected_background)) >= 36.0:
                    ink_pixels += int(count)
        text_ink[layer_id] = {
            "ok": bounds_valid and ink_pixels >= 4,
            "bounds": list(text_bounds),
            "bounds_valid": bounds_valid,
            "ink_pixels": ink_pixels,
            "minimum_ink_pixels": 4,
        }
    text_overflow_guard = {
        "ok": True,
        "bounds": [],
        "ink_pixels": 0,
        "maximum_ink_pixels": 0,
    }
    if text_rects:
        trailing_rect = max(
            text_rects.values(),
            key=lambda rect: float(rect["y"]) + float(rect["height"]),
        )
        guard_left = max(0, round(float(trailing_rect["x"])))
        guard_top = max(
            0,
            round(
                float(trailing_rect["y"])
                + float(trailing_rect["height"])
                + 2.0
            ),
        )
        guard_right = min(
            rgb.width,
            round(float(trailing_rect["x"]) + float(trailing_rect["width"])),
        )
        guard_bottom = min(rgb.height, max(guard_top, y - 2))
        overflow_ink_pixels = 0
        if guard_right > guard_left and guard_bottom > guard_top:
            guard_patch = rgb.crop(
                (guard_left, guard_top, guard_right, guard_bottom)
            )
            color_counts = guard_patch.getcolors(
                maxcolors=max(1, guard_patch.width * guard_patch.height)
            ) or []
            overflow_ink_pixels = sum(
                int(count)
                for count, pixel in color_counts
                if max(_rgb_error(pixel, expected_background)) >= 36.0
            )
        text_overflow_guard = {
            "ok": overflow_ink_pixels == 0,
            "bounds": [guard_left, guard_top, guard_right, guard_bottom],
            "ink_pixels": overflow_ink_pixels,
            "maximum_ink_pixels": 0,
        }
    # The Painter source's 31 CSS-pixel body copy exposes two authored lines
    # in its fixed 342x90 rectangle: ``A complete editable`` and
    # ``starting point with``.  Before the px->point conversion, Unreal's
    # accidental 41.3px display size wrapped the first line after
    # ``complete``.  Probe the right-hand ink of the expected first line plus
    # the trailing half of the second line so real-render QA catches that
    # regression without pretending to OCR the entire clipped paragraph.
    source_visible_body_text = {
        "ok": True,
        "line_1_tail": {"bounds": [], "ink_pixels": 0},
        "line_2_tail": {"bounds": [], "ink_pixels": 0},
        "minimum_ink_pixels": 4,
    }
    body_rect = (text_rects or {}).get("ui-object-1-body")
    if isinstance(body_rect, Mapping):
        body_x = round(float(body_rect["x"]))
        body_y = round(float(body_rect["y"]))
        body_width = round(float(body_rect["width"]))
        body_height = round(float(body_rect["height"]))
        parity_bounds = {
            "line_1_tail": (
                body_x + round(body_width * 0.64),
                body_y,
                body_x + round(body_width * 0.90),
                body_y + round(body_height * 0.46),
            ),
            "line_2_tail": (
                body_x + round(body_width * 0.46),
                body_y + round(body_height * 0.42),
                body_x + round(body_width * 0.86),
                body_y + round(body_height * 0.88),
            ),
        }
        parity_ok = True
        for name, bounds in parity_bounds.items():
            left = max(0, bounds[0])
            top = max(0, bounds[1])
            right = min(rgb.width, bounds[2])
            bottom = min(rgb.height, bounds[3])
            ink_pixels = 0
            if right > left and bottom > top:
                patch = rgb.crop((left, top, right, bottom))
                ink_pixels = sum(
                    int(count)
                    for count, pixel in (
                        patch.getcolors(
                            maxcolors=max(1, patch.width * patch.height)
                        )
                        or []
                    )
                    if max(_rgb_error(pixel, expected_background)) >= 36.0
                )
            row_ok = ink_pixels >= 4
            parity_ok = parity_ok and row_ok
            source_visible_body_text[name] = {
                "ok": row_ok,
                "bounds": [left, top, right, bottom],
                "ink_pixels": ink_pixels,
            }
        source_visible_body_text["ok"] = parity_ok
    checks = {
        "size": rgb.size == expected_size,
        "opaque": bool(alpha_extrema and alpha_extrema[0] >= 250),
        "background_patch": max(background_error) <= PIXEL_CHANNEL_ERROR_MAX,
        "button_patch": max(button_error) <= PIXEL_CHANNEL_ERROR_MAX,
        "rounded_corner_exposes_background": (
            max(corner_error) <= PIXEL_CHANNEL_ERROR_MAX
        ),
        "button_interior": max(interior_error) <= PIXEL_CHANNEL_ERROR_MAX,
        "authored_text_visible": all(
            row["ok"] for row in text_ink.values()
        ),
        "source_visible_body_two_line_parity": source_visible_body_text[
            "ok"
        ],
        "wrapped_text_clipped": text_overflow_guard["ok"],
    }
    return {
        "ok": all(checks.values()),
        "actual_path": str(actual_path),
        "size": list(rgb.size),
        "expected_size": list(expected_size),
        "button_rect": [x, y, width, height],
        "checks": checks,
        "background": {
            "actual_mean_rgb": list(background_mean),
            "expected_rgb": list(expected_background),
            "channel_error": background_error,
        },
        "button": {
            "actual_mean_rgb": list(button_mean),
            "expected_rgb": list(expected_button),
            "channel_error": button_error,
        },
        "rounded_corner": {
            "actual_rgb": list(corner_rgb),
            "expected_background_rgb": list(expected_background),
            "channel_error": corner_error,
        },
        "interior": {
            "actual_rgb": list(interior_rgb),
            "expected_button_rgb": list(expected_button),
            "channel_error": interior_error,
        },
        "alpha_extrema": list(alpha_extrema or ()),
        "text_ink": text_ink,
        "source_visible_body_text": source_visible_body_text,
        "text_overflow_guard": text_overflow_guard,
        "thresholds": {
            "maximum_channel_error": PIXEL_CHANNEL_ERROR_MAX,
            "minimum_alpha": 250,
        },
    }


def _button_source_rect(document: Mapping[str, Any]) -> dict[str, float]:
    row = next(
        item
        for item in document.get("objects", [])
        if str(item.get("id") or "") == BUTTON_ID
    )
    return {
        "x": float(row["x"]),
        "y": float(row["y"]),
        "width": float(row["width"]),
        "height": float(row["height"]),
    }


def _text_source_rects(
    document: Mapping[str, Any],
) -> dict[str, dict[str, float]]:
    expected_ids = set(EXPECTED_TEXT_LAYERS)
    return {
        str(row.get("id") or ""): {
            "x": float(row.get("x") or 0.0),
            "y": float(row.get("y") or 0.0),
            "width": float(row.get("width") or 0.0),
            "height": float(row.get("height") or 0.0),
        }
        for row in document.get("objects", [])
        if str(row.get("id") or "") in expected_ids
    }


def run_button_qa(
    workspace: Path,
    *,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    contract = build_button_contract_evidence()
    original_path = workspace / "mobile_onboarding_original.json"
    fixture_path = workspace / "mobile_onboarding_button_fixture.json"
    fixture_umg_path = workspace / "mobile_onboarding_button_umg.json"
    original_path.write_text(
        json.dumps(
            contract["original_document"],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    fixture_path.write_text(
        json.dumps(
            contract["fixture_document"],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    fixture_umg_path.write_text(
        json.dumps(
            contract["fixture_umg_document"],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    common_paths = {
        "original_document": str(original_path),
        "runtime_fixture_document": str(fixture_path),
        "runtime_fixture_umg_document": str(fixture_umg_path),
    }
    if not contract["ok"]:
        return {
            "schema": "tigerstudio.painter.ui.unreal_umg_button_qa.v1",
            "ok": False,
            "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
            "paths": common_paths,
            "contract": contract,
            "generation": {
                "ok": False,
                "reason": "button_contract_preflight_failed",
            },
        }

    project = _ensure_project(workspace)
    generation = generate_painter_umg(
        contract["fixture_document"],
        project_path=project,
        output_dir=workspace / "button_packet",
        destination_root="/Game/TigerStudio/GeneratedButtonQA",
        timeout_seconds=timeout_seconds,
    )
    asset_path = str(generation.get("generated_asset_path") or "")
    style = contract["fixture_contract"]["fixture_button_visual"][
        "button_style"
    ]
    style_audit = compare_button_style_audit(
        generation.get("generated_button_style_audit", {}).get(BUTTON_ID),
        style,
    )
    generated_classes = generation.get("generated_widget_classes") or {}
    visibility_audit = (
        generation.get("generated_widget_visibility_audit") or {}
    )
    generation_contract = {
        "ok": (
            bool(generation.get("ok"))
            and bool(generation.get("generated_asset_loaded"))
            and generation.get("generated_asset_class")
            == "WidgetBlueprint"
            and int(generation.get("generated_widget_count") or 0)
            == len(EXPECTED_LAYER_IDS)
            and all(
                generated_classes.get(layer_id) == class_name
                for layer_id, class_name in EXPECTED_WIDGET_CLASSES.items()
            )
            and all(
                visibility_audit.get(layer_id) == visibility
                for layer_id, visibility in EXPECTED_WIDGET_VISIBILITY.items()
            )
            and style_audit["ok"]
        ),
        "expected_widget_classes": EXPECTED_WIDGET_CLASSES,
        "actual_widget_classes": generated_classes,
        "expected_visibility": EXPECTED_WIDGET_VISIBILITY,
        "actual_visibility": visibility_audit,
        "button_style_audit": style_audit,
    }
    reopened = (
        _reopen_generated_asset(
            project,
            asset_path,
            expected_widget_classes=EXPECTED_WIDGET_CLASSES,
            timeout_seconds=timeout_seconds,
        )
        if generation_contract["ok"] and asset_path
        else {
            "ok": False,
            "reason": "generation_contract_failed_before_reopen",
        }
    )
    output_path = workspace / "mobile_onboarding_button_unreal.png"
    rendered = (
        _render_generated_asset(
            project,
            asset_path,
            output_path,
            width=390,
            height=844,
            timeout_seconds=timeout_seconds,
        )
        if reopened.get("ok") and asset_path
        else {
            "ok": False,
            "reason": "reopen_failed_before_render",
        }
    )
    render_comparison = (
        compare_mobile_button_render(
            output_path,
            artboard_fill=EXPECTED_ARTBOARD_FILL,
            button_fill=EXPECTED_BUTTON_FILL,
            button_rect=_button_source_rect(contract["fixture_document"]),
            text_rects=_text_source_rects(contract["fixture_document"]),
        )
        if rendered.get("ok") and output_path.is_file()
        else {
            "ok": False,
            "reason": "unreal_render_failed_before_pixel_comparison",
        }
    )
    report = {
        "schema": "tigerstudio.painter.ui.unreal_umg_button_qa.v1",
        "ok": (
            contract["ok"]
            and generation_contract["ok"]
            and bool(reopened.get("ok"))
            and bool(rendered.get("ok"))
            and bool(render_comparison.get("ok"))
        ),
        "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
        "project_path": str(project),
        "paths": {
            **common_paths,
            "render": str(output_path),
        },
        "contract": contract,
        "generation": generation,
        "generation_contract": generation_contract,
        "reopen": reopened,
        "render": rendered,
        "render_comparison": render_comparison,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    report = run_button_qa(
        workspace,
        timeout_seconds=args.timeout,
    )
    report_path = workspace / "qa_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"ok": report["ok"], "report": str(report_path)},
            ensure_ascii=False,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
