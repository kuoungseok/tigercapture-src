"""Real-UE acceptance QA for schema-19 RoundedCard geometry binding.

The fixture is authored through Painter's normal document/component services
and covers the four layout cases that can otherwise regress independently:

* a Canvas child stretched horizontally with asymmetric paint padding;
* an Overlay Fill child whose allocation follows its stretched parent;
* an Overlay non-Fill child that must keep the fixed-size contract; and
* a reusable component whose RoundedCard definition root fills the instance.

The same generated Widget Blueprint is rendered once at the authored size and
once at a larger size.  Geometry is accepted only from the plugin's
``RoundedCardSizeAudit`` and ``RoundedCardVisualSlotAudit`` maps produced by
that single FWidgetRenderer paint pass; the PNGs are evidence, not synthetic
geometry stand-ins.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_ui_components import (
    convert_ui_object_to_component,
    instantiate_ui_component,
)
from app.painter_ui_constraints import capture_ui_constraints
from app.painter_ui_document import (
    add_ui_artboard,
    add_ui_object,
    create_ui_document,
    set_active_ui_artboard,
    update_ui_component,
    update_ui_object,
    validate_ui_document,
)
from app.painter_ui_umg_adapter import (
    generate_painter_umg,
    painter_ui_to_umg_document,
    preflight_painter_umg,
)
from app.unreal_umg_workflow import DEFAULT_UNREAL_ENGINE_ROOT
from tools.qa_painter_ui_unreal_umg import (
    _capture_generated_asset,
    _ensure_project,
    _render_generated_asset,
    _reopen_generated_asset,
)


DYNAMIC_SIZE_QA_SCHEMA = (
    "tigerstudio.painter.ui.unreal_umg_rounded_card_dynamic_size_qa.v1"
)
DYNAMIC_SIZE_DOCUMENT_SCHEMA_VERSION = 19
DYNAMIC_SIZE_DESTINATION_ROOT = "/Game/TigerStudio/GeneratedDynamicSizeQA"
DEFAULT_WORKSPACE = (
    ROOT
    / "debugCapture"
    / "painter_ui_designer"
    / "unreal_umg_rounded_card_dynamic_size_schema19"
)
REFERENCE_DRAW_SIZE = (640, 420)
ENLARGED_DRAW_SIZE = (960, 600)
KNOWN_QA_GAPS = [
    "same_instance_zero_collapse_restore_not_exercised",
    "draw_widget_dpi_scale_1_5_2_not_exercised",
    "second_same_class_instance_mid_isolation_not_exercised",
]

_SIZE_AUDIT_RE = re.compile(
    r"^binding=(?P<binding>[^;]+);"
    r"fixed=(?P<fixed_x>-?[0-9.]+)x(?P<fixed_y>-?[0-9.]+);"
    r"geometry=(?P<geometry_x>-?[0-9.]+)x(?P<geometry_y>-?[0-9.]+);"
    r"live=(?P<live_x>-?[0-9.]+)x(?P<live_y>-?[0-9.]+);"
    r"mid=(?:(?P<mid_x>-?[0-9.]+)x(?P<mid_y>-?[0-9.]+)|(?P<mid_unavailable>unavailable))$"
)
_VISUAL_SLOT_AUDIT_RE = re.compile(
    r"^position=(?P<position_x>-?[0-9.]+),(?P<position_y>-?[0-9.]+);"
    r"size=(?P<size_x>-?[0-9.]+)x(?P<size_y>-?[0-9.]+);"
    r"padding=(?P<left>-?[0-9.]+),(?P<top>-?[0-9.]+),"
    r"(?P<right>-?[0-9.]+),(?P<bottom>-?[0-9.]+)$"
)


def _flat_style(fill: str = "#00000000") -> dict[str, Any]:
    return {
        "fill": fill,
        "fills": [
            {
                "type": "solid",
                "visible": True,
                "opacity": 1.0,
                "color": fill,
                "blend_mode": "normal",
            }
        ],
        "radius": 0.0,
        "corner_radii": {
            "top_left": 0.0,
            "top_right": 0.0,
            "bottom_right": 0.0,
            "bottom_left": 0.0,
        },
    }


def _rounded_card_style(
    fill: str,
    *,
    radius: float,
    stroke_width: float = 0.0,
    stroke_align: str = "inside",
    shadow: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    style: dict[str, Any] = {
        "fill": fill,
        "fills": [
            {
                "type": "solid",
                "visible": True,
                "opacity": 1.0,
                "color": fill,
                "blend_mode": "normal",
            }
        ],
        "radius": radius,
        "corner_radii": {
            "top_left": radius,
            "top_right": radius * 0.75,
            "bottom_right": radius * 0.5,
            "bottom_left": radius * 0.625,
        },
        "corner_smoothing": 0.25,
        "stroke_width": stroke_width,
        "stroke_align": stroke_align,
        "strokes": [],
        "effects": [],
    }
    if stroke_width > 0.0:
        style["strokes"] = [
            {
                "type": "solid",
                "visible": True,
                "opacity": 1.0,
                "color": "#F8FAFCFF",
                "blend_mode": "normal",
                "width": stroke_width,
                "align": stroke_align,
            }
        ]
    if shadow is not None:
        style["effects"] = [
            {
                "type": "drop_shadow",
                "color": "#020617A8",
                "x": float(shadow["x"]),
                "y": float(shadow["y"]),
                "blur": float(shadow["blur"]),
                "spread": float(shadow["spread"]),
                "blend_mode": "normal",
            }
        ]
    return style


def _object_by_id(document: Mapping[str, Any], object_id: str) -> dict[str, Any]:
    return copy.deepcopy(
        next(
            row
            for row in document.get("objects", [])
            if str(row.get("id") or "") == str(object_id)
        )
    )


def _set_constraints(
    document: Mapping[str, Any],
    object_id: str,
    parent: Mapping[str, float],
    *,
    horizontal: str,
    vertical: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    row = _object_by_id(document, object_id)
    return update_ui_object(
        document,
        object_id,
        {
            "constraints": capture_ui_constraints(
                row,
                parent,
                {
                    "horizontal": horizontal,
                    "vertical": vertical,
                    "pivot_x": 0.5,
                    "pivot_y": 0.5,
                },
            )
        },
    )


def build_dynamic_size_qa_fixture() -> dict[str, Any]:
    """Build one normal Painter document covering every size-binding path."""

    width, height = REFERENCE_DRAW_SIZE
    document = create_ui_document(width, height, name="RoundedCard Dynamic Size QA")
    document["document_id"] = "painter-rounded-card-dynamic-size-schema19-qa"
    document["interactions"] = []
    document["artboards"][0]["background"] = "#0B1020FF"
    artboard_rect = {
        "x": 0.0,
        "y": 0.0,
        "width": float(width),
        "height": float(height),
    }
    screen_artboard_id = str(document["active_artboard_id"])

    # Outside stroke = 4.  Shadow extent = blur 12 + spread 3 = 15.
    # With offset (8, -4), expected padding is L11/T23/R27/B15.
    document, canvas_dynamic = add_ui_object(
        document,
        kind="rectangle",
        name="Canvas Stretch Dynamic Card",
        x=32,
        y=24,
        width=576,
        height=104,
        style=_rounded_card_style(
            "#2563EBFF",
            radius=24.0,
            stroke_width=4.0,
            stroke_align="outside",
            shadow={"x": 8.0, "y": -4.0, "blur": 12.0, "spread": 3.0},
        ),
    )
    document, canvas_dynamic = _set_constraints(
        document,
        canvas_dynamic["id"],
        artboard_rect,
        horizontal="stretch",
        vertical="top",
    )

    document, overlay_parent = add_ui_object(
        document,
        kind="frame",
        name="Overlay Dynamic Size Parent",
        x=40,
        y=168,
        width=560,
        height=166,
        style=_flat_style("#172033FF"),
    )
    document, overlay_parent = update_ui_object(
        document,
        overlay_parent["id"],
        {
            "layout": {
                "mode": "overlay",
                "umg_spacing_strategy": "padding",
            }
        },
    )
    document, overlay_parent = _set_constraints(
        document,
        overlay_parent["id"],
        artboard_rect,
        horizontal="stretch",
        vertical="top",
    )
    overlay_rect = {
        "x": float(overlay_parent["x"]),
        "y": float(overlay_parent["y"]),
        "width": float(overlay_parent["width"]),
        "height": float(overlay_parent["height"]),
    }

    document, overlay_dynamic = add_ui_object(
        document,
        kind="rectangle",
        name="Overlay Fill Dynamic Card",
        parent_id=overlay_parent["id"],
        x=56,
        y=184,
        width=528,
        height=76,
        style=_rounded_card_style("#0EA5E9FF", radius=18.0),
    )
    document, overlay_dynamic = _set_constraints(
        document,
        overlay_dynamic["id"],
        overlay_rect,
        horizontal="stretch",
        vertical="stretch",
    )

    document, overlay_fixed = add_ui_object(
        document,
        kind="rectangle",
        name="Overlay Non Fill Fixed Card",
        parent_id=overlay_parent["id"],
        x=408,
        y=276,
        width=160,
        height=42,
        style=_rounded_card_style("#F97316FF", radius=12.0),
    )
    document, overlay_fixed = _set_constraints(
        document,
        overlay_fixed["id"],
        overlay_rect,
        horizontal="right",
        vertical="bottom",
    )

    # Keep reusable definitions on a separate Painter library artboard.  The
    # definition owns the stretch constraint before cloning, so the visible
    # screen instance inherits dynamic Canvas allocation without producing an
    # unsupported instance-local constraints override.
    document, library_artboard = add_ui_artboard(
        document,
        name="Component Library",
        width=width,
        height=height,
        breakpoint="component-library",
    )
    library_rect = {
        "x": 0.0,
        "y": 0.0,
        "width": float(width),
        "height": float(height),
    }
    document, component_root = add_ui_object(
        document,
        kind="rectangle",
        name="Reusable Dynamic Rounded Card Definition",
        artboard_id=library_artboard["id"],
        x=80,
        y=344,
        width=220,
        height=56,
        style=_rounded_card_style(
            "#8B5CF6FF",
            radius=16.0,
            stroke_width=2.0,
            stroke_align="center",
        ),
    )
    document, component_root = _set_constraints(
        document,
        component_root["id"],
        library_rect,
        horizontal="stretch",
        vertical="bottom",
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=component_root["id"],
        name="Reusable Dynamic Rounded Card",
    )
    # This QA exercises geometry only; remove the service's default interactive
    # state property so schema-19 generation stays entirely static.
    document, component = update_ui_component(
        document,
        component["id"],
        {"property_definitions": {}},
    )
    document, instance = instantiate_ui_component(
        document,
        component_id=component["id"],
        artboard_id=screen_artboard_id,
        x=80,
        y=350,
    )
    instance_root_id = str(instance["root_object_id"])
    document = set_active_ui_artboard(document, screen_artboard_id)

    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise RuntimeError(
            "Dynamic-size QA fixture is invalid: "
            + ", ".join(str(row) for row in validation["errors"])
        )
    return {
        "document": document,
        "reference_draw_size": list(REFERENCE_DRAW_SIZE),
        "enlarged_draw_size": list(ENLARGED_DRAW_SIZE),
        "canvas_dynamic_id": str(canvas_dynamic["id"]),
        "overlay_parent_id": str(overlay_parent["id"]),
        "overlay_dynamic_id": str(overlay_dynamic["id"]),
        "overlay_fixed_id": str(overlay_fixed["id"]),
        "component_id": str(component["id"]),
        "component_definition_root_id": str(component_root["id"]),
        "component_instance_root_id": instance_root_id,
        "reference_geometry": {
            "canvas_dynamic": [576.0, 104.0],
            "overlay_dynamic": [528.0, 76.0],
            "overlay_fixed": [160.0, 42.0],
            "component_dynamic": [220.0, 56.0],
        },
        "enlarged_geometry": {
            "canvas_dynamic": [896.0, 104.0],
            "overlay_dynamic": [848.0, 76.0],
            "overlay_fixed": [160.0, 42.0],
            "component_dynamic": [540.0, 56.0],
        },
    }


def _layer_by_id(document: Mapping[str, Any], layer_id: str) -> dict[str, Any]:
    for layer in document.get("Layers", []):
        if str(layer.get("Id") or "") == layer_id:
            return copy.deepcopy(dict(layer))
    for component in document.get("Components", []):
        for layer in component.get("Layers", []):
            if str(layer.get("Id") or "") == layer_id:
                return copy.deepcopy(dict(layer))
    return {}


def build_dynamic_size_contract_evidence() -> dict[str, Any]:
    fixture = build_dynamic_size_qa_fixture()
    document = fixture["document"]
    exported = painter_ui_to_umg_document(document)
    preflight = preflight_painter_umg(document)
    ids = {
        "canvas_dynamic": fixture["canvas_dynamic_id"],
        "overlay_dynamic": fixture["overlay_dynamic_id"],
        "overlay_fixed": fixture["overlay_fixed_id"],
        "component_dynamic": fixture["component_definition_root_id"],
    }
    layers = {
        role: _layer_by_id(exported, layer_id)
        for role, layer_id in ids.items()
    }
    component_rows = [
        row
        for row in exported.get("Components", [])
        if str(row.get("Id") or "") == fixture["component_id"]
    ]
    instance_rows = [
        row
        for row in exported.get("ComponentInstances", [])
        if str(row.get("LayerId") or "")
        == fixture["component_instance_root_id"]
    ]
    instance_layer = next(
        (
            row
            for row in exported.get("Layers", [])
            if str(row.get("Id") or "")
            == fixture["component_instance_root_id"]
        ),
        {},
    )
    expected_bindings = {
        "canvas_dynamic": "WidgetGeometry",
        "overlay_dynamic": "WidgetGeometry",
        "overlay_fixed": "FixedSize",
        "component_dynamic": "WidgetGeometry",
    }
    expected_canvas_anchors = {
        "AnchorMinimum": {"X": 0.0, "Y": 0.0},
        "AnchorMaximum": {"X": 1.0, "Y": 0.0},
    }
    overlay_flow = layers["overlay_dynamic"].get("FlowSlot") or {}
    fixed_flow = layers["overlay_fixed"].get("FlowSlot") or {}
    checks = {
        "schema_19": int(exported.get("SchemaVersion") or 0)
        == DYNAMIC_SIZE_DOCUMENT_SCHEMA_VERSION,
        "preflight_ready": bool(preflight.get("ok")),
        "all_layers_present": all(bool(row) for row in layers.values()),
        "all_material": all(
            row.get("Disposition") == "Material" for row in layers.values()
        ),
        "rounded_card_materials": all(
            (row.get("Material") or {}).get("Kind") == "RoundedCard"
            for row in layers.values()
        ),
        "size_bindings": all(
            (layers[role].get("Material") or {}).get("SizeBinding") == binding
            for role, binding in expected_bindings.items()
        ),
        "canvas_stretch_anchors": all(
            (layers["canvas_dynamic"].get("CanvasSlot") or {}).get(key)
            == value
            for key, value in expected_canvas_anchors.items()
        ),
        "overlay_fill_slot": (
            overlay_flow.get("HorizontalAlignment") == "Fill"
            and overlay_flow.get("VerticalAlignment") == "Fill"
        ),
        "overlay_non_fill_slot": (
            fixed_flow.get("HorizontalAlignment") == "Right"
            and fixed_flow.get("VerticalAlignment") == "Bottom"
        ),
        "asymmetric_visual_padding": (
            (layers["canvas_dynamic"].get("Material") or {}).get(
                "VisualPadding"
            )
            == {"Left": 11.0, "Top": 23.0, "Right": 27.0, "Bottom": 15.0}
        ),
        "component_definition_present": len(component_rows) == 1,
        "component_instance_present": len(instance_rows) == 1,
        "component_instance_canvas_stretch": (
            (instance_layer.get("CanvasSlot") or {}).get("AnchorMinimum")
            == {"X": 0.0, "Y": 1.0}
            and (instance_layer.get("CanvasSlot") or {}).get(
                "AnchorMaximum"
            )
            == {"X": 1.0, "Y": 1.0}
        ),
    }
    return {
        "schema": "tigerstudio.painter.ui.unreal_umg_rounded_card_dynamic_size_contract.v1",
        "ok": all(checks.values()),
        "checks": checks,
        "fixture": fixture,
        "umg_document": exported,
        "preflight": preflight,
        "layers": layers,
        "component_instance_layer": copy.deepcopy(dict(instance_layer)),
        "expected_bindings": expected_bindings,
        "expected_audit_suffixes": {
            "canvas_dynamic": fixture["canvas_dynamic_id"],
            "overlay_dynamic": fixture["overlay_dynamic_id"],
            "overlay_fixed": fixture["overlay_fixed_id"],
            "component_dynamic": (
                fixture["component_instance_root_id"]
                + "/"
                + fixture["component_definition_root_id"]
            ),
        },
        "known_gaps": list(KNOWN_QA_GAPS),
    }


def _parse_size_audit(value: object) -> dict[str, Any]:
    match = _SIZE_AUDIT_RE.fullmatch(str(value or ""))
    if match is None:
        return {}
    groups = match.groupdict()
    mid = (
        None
        if groups.get("mid_unavailable")
        else [float(groups["mid_x"]), float(groups["mid_y"])]
    )
    return {
        "binding": groups["binding"],
        "fixed": [float(groups["fixed_x"]), float(groups["fixed_y"])],
        "geometry": [
            float(groups["geometry_x"]),
            float(groups["geometry_y"]),
        ],
        "live": [float(groups["live_x"]), float(groups["live_y"])],
        "mid": mid,
    }


def _parse_visual_slot_audit(value: object) -> dict[str, Any]:
    match = _VISUAL_SLOT_AUDIT_RE.fullmatch(str(value or ""))
    if match is None:
        return {}
    groups = match.groupdict()
    return {
        "position": [
            float(groups["position_x"]),
            float(groups["position_y"]),
        ],
        "size": [float(groups["size_x"]), float(groups["size_y"])],
        "padding": [
            float(groups["left"]),
            float(groups["top"]),
            float(groups["right"]),
            float(groups["bottom"]),
        ],
    }


def _audit_value_by_suffix(
    audit: Mapping[str, Any],
    suffix: str,
) -> tuple[str, Any]:
    if suffix in audit:
        return suffix, audit[suffix]
    matches = [
        (str(key), value)
        for key, value in audit.items()
        if str(key).endswith("/" + suffix)
    ]
    return matches[0] if len(matches) == 1 else ("", "")


def _near_pair(
    actual: object,
    expected: object,
    *,
    tolerance: float = 0.6,
) -> bool:
    if not isinstance(actual, (list, tuple)) or not isinstance(
        expected, (list, tuple)
    ):
        return False
    return len(actual) == len(expected) and all(
        math.isclose(float(left), float(right), abs_tol=tolerance)
        for left, right in zip(actual, expected, strict=True)
    )


def _normalized_render_audits(
    render: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    raw_sizes = render.get("rounded_card_size_audit")
    raw_sizes = dict(raw_sizes) if isinstance(raw_sizes, Mapping) else {}
    raw_slots = render.get("rounded_card_visual_slot_audit")
    raw_slots = dict(raw_slots) if isinstance(raw_slots, Mapping) else {}
    rows: dict[str, Any] = {}
    for role, suffix in contract["expected_audit_suffixes"].items():
        size_key, size_value = _audit_value_by_suffix(raw_sizes, suffix)
        slot_key, slot_value = _audit_value_by_suffix(raw_slots, suffix)
        rows[role] = {
            "size_key": size_key,
            "slot_key": slot_key,
            "size": _parse_size_audit(size_value),
            "visual_slot": _parse_visual_slot_audit(slot_value),
            "raw_size": str(size_value or ""),
            "raw_visual_slot": str(slot_value or ""),
        }
    return rows


def validate_dynamic_size_render_pair(
    reference_render: Mapping[str, Any],
    enlarged_render: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate first-pass live geometry, MID size, and padded visual slots."""

    reference = _normalized_render_audits(reference_render, contract)
    enlarged = _normalized_render_audits(enlarged_render, contract)
    reference_geometry = contract["fixture"]["reference_geometry"]
    enlarged_geometry = contract["fixture"]["enlarged_geometry"]
    dynamic_roles = {
        "canvas_dynamic",
        "overlay_dynamic",
        "component_dynamic",
    }
    per_role: dict[str, Any] = {}
    for role in contract["expected_bindings"]:
        reference_row = reference[role]
        enlarged_row = enlarged[role]
        reference_size = reference_row["size"]
        enlarged_size = enlarged_row["size"]
        reference_slot = reference_row["visual_slot"]
        enlarged_slot = enlarged_row["visual_slot"]
        binding = contract["expected_bindings"][role]
        expected_reference = reference_geometry[role]
        expected_enlarged = enlarged_geometry[role]
        dynamic = role in dynamic_roles
        checks = {
            "audit_paths_present": bool(reference_row["size_key"])
            and bool(reference_row["slot_key"])
            and bool(enlarged_row["size_key"])
            and bool(enlarged_row["slot_key"]),
            "binding": reference_size.get("binding") == binding
            and enlarged_size.get("binding") == binding,
            "fixed_size": _near_pair(
                reference_size.get("fixed"), expected_reference
            )
            and _near_pair(enlarged_size.get("fixed"), expected_reference),
            "host_geometry": _near_pair(
                reference_size.get("geometry"), expected_reference
            )
            and _near_pair(
                enlarged_size.get("geometry"),
                expected_enlarged if dynamic else expected_reference,
            ),
            "reference_live_size": (
                _near_pair(reference_size.get("live"), expected_reference)
                if dynamic
                else _near_pair(reference_size.get("live"), [0.0, 0.0])
            ),
            "enlarged_live_size": (
                _near_pair(enlarged_size.get("live"), expected_enlarged)
                if dynamic
                else _near_pair(enlarged_size.get("live"), [0.0, 0.0])
            ),
            "first_pass_mid_matches_live": (
                _near_pair(reference_size.get("mid"), expected_reference)
                and _near_pair(enlarged_size.get("mid"), expected_enlarged)
                if dynamic
                else reference_size.get("mid") is None
                and enlarged_size.get("mid") is None
            ),
            "padding_stable": reference_slot.get("padding")
            == enlarged_slot.get("padding")
            and bool(reference_slot.get("padding") is not None),
        }
        padding = reference_slot.get("padding") or []
        if len(padding) == 4:
            left, top, right, bottom = padding
            expected_reference_surface = [
                expected_reference[0] + left + right,
                expected_reference[1] + top + bottom,
            ]
            expected_enlarged_surface = [
                expected_enlarged[0] + left + right,
                expected_enlarged[1] + top + bottom,
            ]
            checks["reference_visual_surface"] = _near_pair(
                reference_slot.get("position"), [-left, -top]
            ) and _near_pair(
                reference_slot.get("size"), expected_reference_surface
            )
            checks["enlarged_visual_surface"] = _near_pair(
                enlarged_slot.get("position"), [-left, -top]
            ) and _near_pair(
                enlarged_slot.get("size"), expected_enlarged_surface
            )
        else:
            checks["reference_visual_surface"] = False
            checks["enlarged_visual_surface"] = False
        if role == "overlay_fixed":
            checks["fixed_slot_unchanged"] = (
                reference_row["raw_visual_slot"]
                == enlarged_row["raw_visual_slot"]
            )
        per_role[role] = {
            "ok": all(checks.values()),
            "checks": checks,
            "reference": reference_row,
            "enlarged": enlarged_row,
            "expected_reference_size": expected_reference,
            "expected_enlarged_size": expected_enlarged,
        }
    render_checks = {
        "reference_render_ok": bool(reference_render.get("ok")),
        "enlarged_render_ok": bool(enlarged_render.get("ok")),
        "reference_dimensions": [
            int(reference_render.get("width") or 0),
            int(reference_render.get("height") or 0),
        ]
        == list(REFERENCE_DRAW_SIZE),
        "enlarged_dimensions": [
            int(enlarged_render.get("width") or 0),
            int(enlarged_render.get("height") or 0),
        ]
        == list(ENLARGED_DRAW_SIZE),
        "all_roles": all(row["ok"] for row in per_role.values()),
    }
    return {
        "schema": "tigerstudio.painter.ui.unreal_umg_rounded_card_dynamic_size_render_contract.v1",
        "ok": all(render_checks.values()),
        "checks": render_checks,
        "roles": per_role,
    }


def _component_class_name(class_path: object) -> str:
    value = str(class_path or "").strip().strip("'\"")
    return value.rsplit(".", 1)[-1].rsplit("/", 1)[-1]


def run_dynamic_size_qa(
    workspace: Path,
    *,
    timeout_seconds: int = 300,
    capture_ui: bool = False,
) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    contract = build_dynamic_size_contract_evidence()
    fixture_path = workspace / "rounded_card_dynamic_size_fixture.json"
    umg_path = workspace / "rounded_card_dynamic_size_umg.json"
    fixture_path.write_text(
        json.dumps(contract["fixture"]["document"], ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    umg_path.write_text(
        json.dumps(contract["umg_document"], ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    paths: dict[str, Any] = {
        "fixture_document": str(fixture_path),
        "umg_document": str(umg_path),
    }
    if not contract["ok"]:
        return {
            "schema": DYNAMIC_SIZE_QA_SCHEMA,
            "ok": False,
            "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
            "paths": paths,
            "contract": contract,
            "generation": {
                "ok": False,
                "reason": "dynamic_size_contract_preflight_failed",
            },
        }

    project = _ensure_project(workspace)
    generation = generate_painter_umg(
        contract["fixture"]["document"],
        project_path=project,
        output_dir=workspace / "rounded_card_dynamic_size_packet",
        destination_root=DYNAMIC_SIZE_DESTINATION_ROOT,
        timeout_seconds=timeout_seconds,
    )
    main_asset_path = str(generation.get("generated_asset_path") or "")
    component_id = str(contract["fixture"]["component_id"])
    component_assets = dict(
        generation.get("generated_component_asset_paths") or {}
    )
    component_classes = dict(
        generation.get("generated_component_class_paths") or {}
    )
    expected_main_classes = {
        contract["fixture"]["canvas_dynamic_id"]: "TigerStudioRoundedCardHost",
        contract["fixture"]["overlay_dynamic_id"]: "TigerStudioRoundedCardHost",
        contract["fixture"]["overlay_fixed_id"]: "TigerStudioRoundedCardHost",
        contract["fixture"]["component_instance_root_id"]: _component_class_name(
            component_classes.get(component_id)
        ),
    }
    actual_widget_classes = dict(generation.get("generated_widget_classes") or {})
    generation_checks = {
        "generation_ok": bool(generation.get("ok")),
        "main_asset_loaded": bool(generation.get("generated_asset_loaded")),
        "main_asset_class": generation.get("generated_asset_class")
        == "WidgetBlueprint",
        "component_generated": int(generation.get("generated_component_count") or 0)
        == 1,
        "component_asset_present": bool(component_assets.get(component_id)),
        "component_class_present": bool(component_classes.get(component_id)),
        "main_widget_classes": all(
            class_name and actual_widget_classes.get(layer_id) == class_name
            for layer_id, class_name in expected_main_classes.items()
        ),
        "component_root_class": actual_widget_classes.get(
            f"component:{component_id}/"
            + contract["fixture"]["component_definition_root_id"]
        )
        == "TigerStudioRoundedCardHost",
    }
    generation_contract = {
        "ok": all(generation_checks.values()),
        "checks": generation_checks,
        "expected_main_widget_classes": expected_main_classes,
        "actual_widget_classes": actual_widget_classes,
    }

    reopened = (
        _reopen_generated_asset(
            project,
            main_asset_path,
            expected_widget_classes=expected_main_classes,
            timeout_seconds=timeout_seconds,
        )
        if generation_contract["ok"] and main_asset_path
        else {"ok": False, "reason": "generation_failed_before_reopen"}
    )
    component_asset_path = str(component_assets.get(component_id) or "")
    component_reopened = (
        _reopen_generated_asset(
            project,
            component_asset_path,
            expected_widget_classes={
                contract["fixture"]["component_definition_root_id"]:
                    "TigerStudioRoundedCardHost"
            },
            timeout_seconds=timeout_seconds,
        )
        if reopened.get("ok") and component_asset_path
        else {"ok": False, "reason": "main_reopen_failed_before_component_reopen"}
    )

    reference_path = workspace / "rounded_card_dynamic_size_reference.png"
    enlarged_path = workspace / "rounded_card_dynamic_size_enlarged.png"
    reference_render = (
        _render_generated_asset(
            project,
            main_asset_path,
            reference_path,
            width=REFERENCE_DRAW_SIZE[0],
            height=REFERENCE_DRAW_SIZE[1],
            timeout_seconds=timeout_seconds,
        )
        if component_reopened.get("ok")
        else {"ok": False, "reason": "asset_reopen_failed_before_render"}
    )
    enlarged_render = (
        _render_generated_asset(
            project,
            main_asset_path,
            enlarged_path,
            width=ENLARGED_DRAW_SIZE[0],
            height=ENLARGED_DRAW_SIZE[1],
            timeout_seconds=timeout_seconds,
        )
        if reference_render.get("ok")
        else {"ok": False, "reason": "reference_render_failed"}
    )
    render_contract = validate_dynamic_size_render_pair(
        reference_render,
        enlarged_render,
        contract,
    )
    editor_capture_path = workspace / "rounded_card_dynamic_size_editor.png"
    editor_capture = (
        _capture_generated_asset(
            project,
            main_asset_path,
            editor_capture_path,
            material_asset_names=[
                Path(str(row)).stem
                for row in generation.get("generated_material_paths", [])
            ],
            timeout_seconds=timeout_seconds,
        )
        if capture_ui and render_contract["ok"]
        else {
            "ok": not capture_ui,
            "status": "not_requested" if not capture_ui else "blocked",
        }
    )
    paths.update(
        {
            "project": str(project),
            "generated_asset": main_asset_path,
            "generated_component_asset": component_asset_path,
            "reference_render": str(reference_path),
            "enlarged_render": str(enlarged_path),
            "editor_capture": (
                str(editor_capture_path) if capture_ui else ""
            ),
        }
    )
    return {
        "schema": DYNAMIC_SIZE_QA_SCHEMA,
        "ok": (
            contract["ok"]
            and generation_contract["ok"]
            and bool(reopened.get("ok"))
            and bool(component_reopened.get("ok"))
            and render_contract["ok"]
            and bool(editor_capture.get("ok"))
        ),
        "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
        "project_path": str(project),
        "paths": paths,
        "contract": contract,
        "generation": generation,
        "generation_contract": generation_contract,
        "reopen": reopened,
        "component_reopen": component_reopened,
        "reference_render": reference_render,
        "enlarged_render": enlarged_render,
        "render_contract": render_contract,
        "editor_capture": editor_capture,
        "known_gaps": list(KNOWN_QA_GAPS),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--capture-ui", action="store_true")
    args = parser.parse_args()
    report = run_dynamic_size_qa(
        args.workspace,
        timeout_seconds=args.timeout,
        capture_ui=args.capture_ui,
    )
    report_path = args.workspace.expanduser().resolve() / "qa_report.json"
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
