"""Generate and reopen a real Painter-authored Widget Blueprint in UE 5.8."""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_ui_templates import instantiate_ui_template, list_ui_templates
from app.painter_ui_constraints import capture_ui_constraints
from app.painter_ui_document import (
    add_ui_object,
    create_ui_document,
    update_ui_object,
)
from app.painter_ui_umg_adapter import (
    generate_painter_umg,
    painter_ui_to_umg_document,
    preflight_painter_umg,
)
from app.unreal_umg_workflow import DEFAULT_UNREAL_ENGINE_ROOT
from app.window_capture import list_capture_windows, save_window_screenshot


DEFAULT_WORKSPACE = (
    ROOT / "debugCapture" / "painter_ui_designer" / "unreal_umg"
)
IMAGE_FILL_QA_SOURCE = (
    ROOT
    / "sample_assets"
    / "motion_ai_showcase"
    / "wall_street_trump"
    / "financial_broadsheet_plate.png"
)


def _capture_has_visible_content(path: Path) -> bool:
    """Reject compositor captures that contain only a flat/black frame."""
    try:
        with Image.open(path) as captured:
            rgba = captured.convert("RGBA")
            alpha_extrema = rgba.getchannel("A").getextrema()
            composited = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
            composited.alpha_composite(rgba)
            extrema = composited.convert("L").getextrema()
    except Exception:
        return False
    return bool(
        alpha_extrema
        and alpha_extrema[1] > 8
        and extrema
        and extrema[1] > 8
        and extrema[1] - extrema[0] > 4
    )


def _capture_pixel_evidence(path: Path) -> dict:
    try:
        with Image.open(path) as captured:
            rgba = captured.convert("RGBA")
            composited = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
            composited.alpha_composite(rgba)
            return {
                "width": rgba.width,
                "height": rgba.height,
                "rgba_extrema": [list(row) for row in rgba.getextrema()],
                "luminance_extrema": list(
                    composited.convert("L").getextrema()
                ),
                "alpha_bbox": list(rgba.getchannel("A").getbbox() or ()),
                "visible_content": _capture_has_visible_content(path),
            }
    except Exception as exc:
        return {
            "visible_content": False,
            "error": str(exc),
        }


def _capture_render_color_evidence(
    path: Path,
    samples: list[dict],
    *,
    tolerance: int = 16,
) -> dict:
    """Verify authored opaque colors at deterministic render coordinates."""
    rows: list[dict] = []
    try:
        with Image.open(path) as captured:
            rgba = captured.convert("RGBA")
            for sample in samples:
                x = int(sample["x"])
                y = int(sample["y"])
                expected = tuple(int(value) for value in sample["rgba"])
                if not (0 <= x < rgba.width and 0 <= y < rgba.height):
                    rows.append(
                        {
                            **sample,
                            "actual": [],
                            "max_channel_error": None,
                            "ok": False,
                            "reason": "sample_out_of_bounds",
                        }
                    )
                    continue
                actual = tuple(int(value) for value in rgba.getpixel((x, y)))
                max_error = max(
                    abs(actual[index] - expected[index])
                    for index in range(4)
                )
                rows.append(
                    {
                        **sample,
                        "actual": list(actual),
                        "max_channel_error": max_error,
                        "ok": max_error <= tolerance,
                    }
                )
    except Exception as exc:
        return {
            "ok": False,
            "tolerance": tolerance,
            "samples": rows,
            "error": str(exc),
        }
    return {
        "ok": bool(rows) and all(row["ok"] for row in rows),
        "tolerance": tolerance,
        "samples": rows,
    }


def _compare_normalized_crop_render(
    actual_path: Path,
    source_path: Path,
    expected_path: Path,
    *,
    crop_x: float,
    crop_y: float,
    crop_width: float,
    crop_height: float,
) -> dict:
    with Image.open(actual_path) as actual_source:
        actual = actual_source.convert("RGB")
    with Image.open(source_path) as source:
        source_rgb = source.convert("RGB")
        source_width, source_height = source_rgb.size
        crop_box = (
            round(crop_x * source_width),
            round(crop_y * source_height),
            round((crop_x + crop_width) * source_width),
            round((crop_y + crop_height) * source_height),
        )
        expected = source_rgb.crop(crop_box).resize(
            actual.size,
            Image.Resampling.BILINEAR,
        )
    expected_path.parent.mkdir(parents=True, exist_ok=True)
    expected.save(expected_path)

    actual_pixels = np.asarray(actual, dtype=np.float64)
    expected_pixels = np.asarray(expected, dtype=np.float64)
    if actual.width > 4 and actual.height > 4:
        actual_pixels = actual_pixels[2:-2, 2:-2]
        expected_pixels = expected_pixels[2:-2, 2:-2]
    actual_luma = (
        actual_pixels[..., 0] * 0.2126
        + actual_pixels[..., 1] * 0.7152
        + actual_pixels[..., 2] * 0.0722
    )
    expected_luma = (
        expected_pixels[..., 0] * 0.2126
        + expected_pixels[..., 1] * 0.7152
        + expected_pixels[..., 2] * 0.0722
    )
    correlation = float(
        np.corrcoef(actual_luma.ravel(), expected_luma.ravel())[0, 1]
    )
    rgb_mae = float(np.mean(np.abs(actual_pixels - expected_pixels)))
    luminance_mae = float(np.mean(np.abs(actual_luma - expected_luma)))
    return {
        "ok": bool(
            np.isfinite(correlation)
            and correlation >= 0.85
            and rgb_mae <= 30.0
        ),
        "actual_path": str(actual_path),
        "expected_path": str(expected_path),
        "source_path": str(source_path),
        "source_crop_pixels": list(crop_box),
        "normalized_crop": {
            "x": crop_x,
            "y": crop_y,
            "width": crop_width,
            "height": crop_height,
        },
        "edge_inset_pixels": 2,
        "luminance_correlation": correlation,
        "rgb_mae": rgb_mae,
        "luminance_mae": luminance_mae,
        "thresholds": {
            "minimum_luminance_correlation": 0.85,
            "maximum_rgb_mae": 30.0,
        },
    }


def _anchor_qa_document(value: dict) -> tuple[dict, list[dict]]:
    """Author anchors, Image Fill, Rounded Card, and native layout panels."""
    document = copy.deepcopy(value)
    # The built-in onboarding template carries a navigation prototype action.
    # This fixture measures layout/material/image generation, while screen
    # routing is intentionally and independently Blocked by UMG preflight.
    # Remove the unrelated action explicitly instead of allowing a blocker to
    # abort the real Widget Blueprint acceptance path.
    document["interactions"] = []
    artboard = next(
        row
        for row in document["artboards"]
        if row["id"] == document["active_artboard_id"]
    )
    parent = {
        "x": 0.0,
        "y": 0.0,
        "width": float(artboard["width"]),
        "height": float(artboard["height"]),
    }
    authored_modes = {
        "Primary CTA": {
            "horizontal": "right",
            "vertical": "bottom",
            "pivot_x": 0.25,
            "pivot_y": 0.75,
        },
        "Feature Card A": {
            "horizontal": "stretch",
            "vertical": "top",
            "pivot_x": 0.5,
            "pivot_y": 0.5,
        },
        "Feature Card B": {
            "horizontal": "scale",
            "vertical": "scale",
            "pivot_x": 0.5,
            "pivot_y": 0.5,
        },
        "Hero Media": {
            "horizontal": "custom",
            "vertical": "custom",
            "anchor_min_x": 0.2,
            "anchor_max_x": 0.2,
            "anchor_min_y": 0.3,
            "anchor_max_y": 0.3,
            "pivot_x": 0.4,
            "pivot_y": 0.6,
        },
    }
    for row in document["objects"]:
        active_row = (
            str(row.get("artboard_id") or "")
            == str(document["active_artboard_id"])
        )
        image_fill_button = (
            active_row and str(row.get("name") or "") == "Primary CTA"
        )
        if str(row.get("kind") or "").casefold() in {
            "button",
            "frame",
            "image",
        } and not image_fill_button:
            # This acceptance fixture isolates the supported leaf-rectangle
            # material path. Rounded Button/Frame/Image backgrounds are
            # intentionally blocked until they have their own native or
            # material-backed conversion instead of being silently dropped.
            compatible_style = dict(row.get("style") or {})
            compatible_style["radius"] = 0.0
            compatible_style["corner_radii"] = {
                "top_left": 0.0,
                "top_right": 0.0,
                "bottom_right": 0.0,
                "bottom_left": 0.0,
            }
            row["style"] = compatible_style
        if image_fill_button:
            image_style = dict(row.get("style") or {})
            image_style["radius"] = 8.0
            image_style["corner_radii"] = {
                "top_left": 8.0,
                "top_right": 8.0,
                "bottom_right": 8.0,
                "bottom_left": 8.0,
            }
            row["style"] = image_style
            row["content"] = {
                **dict(row.get("content") or {}),
                "source_path": str(IMAGE_FILL_QA_SOURCE.resolve()),
                # Exercise the Figma REST STRETCH/imageTransform mapping
                # through the existing provider-neutral native Crop record.
                "image_fit": "stretch",
                "figma_image_transform": [
                    [0.6, 0.0, 0.2],
                    [0.0, 0.7, 0.15],
                ],
                "tile_scale": 1.0,
                "original_width": 1280,
                "original_height": 720,
                "nine_slice_enabled": False,
            }
        if (
            str(row.get("artboard_id") or "")
            == str(document["active_artboard_id"])
            and str(row.get("name") or "") == "Hero Media"
        ):
            # Exercise Painter -> shared v2 contract -> fixed Rounded Card SDF
            # Custom HLSL without adding an artificial QA-only object.
            row["kind"] = "rectangle"
            row["style"] = {
                "fill": "#FFFFFFFF",
                "text_color": "#111111FF",
                "radius": 24.0,
                "stroke_width": 3.0,
                "blend_mode": "normal",
                "corner_smoothing": 0.35,
                "fills": [
                    {
                        "type": "radial",
                        "visible": True,
                        "opacity": 0.92,
                        "gradient": {
                            "type": "radial",
                            "start": {"x": 0.38, "y": 0.38},
                            "end": {"x": 0.92, "y": 0.25},
                            "width": {"x": 0.22, "y": 0.94},
                            "stops": [
                                {"position": 0.0, "color": "#7C3AEDFF"},
                                {"position": 0.48, "color": "#2563EBFF"},
                                {"position": 1.0, "color": "#06B6D4FF"},
                            ],
                        },
                    }
                ],
                "strokes": [
                    {
                        "type": "solid",
                        "visible": True,
                        "opacity": 0.9,
                        "color": "#D9F2FFFF",
                        "blend_mode": "normal",
                        "width": 3.0,
                        "align": "inside",
                    }
                ],
                "corner_radii": {
                    "top_left": 32.0,
                    "top_right": 20.0,
                    "bottom_right": 28.0,
                    "bottom_left": 16.0,
                },
                "stroke_align": "inside",
                "effects": [
                    {
                        "type": "drop_shadow",
                        "color": "#07142699",
                        "x": 14.0,
                        "y": 18.0,
                        "blur": 28.0,
                        "spread": 3.0,
                        "blend_mode": "normal",
                    },
                    {
                        "type": "inner_shadow",
                        "color": "#FFFFFF42",
                        "x": -3.0,
                        "y": -3.0,
                        "blur": 8.0,
                        "spread": 0.0,
                        "blend_mode": "normal",
                    },
                ],
            }
            row["content"] = {
                "text_ranges": [],
                "boolean": {
                    "enabled": False,
                    "operation": "union",
                    "group": False,
                    "operand_ids": [],
                },
            }
            row["token_bindings"] = {}
        updates = authored_modes.get(str(row.get("name") or ""))
        if updates is not None:
            row["constraints"] = capture_ui_constraints(row, parent, updates)

    flat_native_style = {
        "radius": 0.0,
        "corner_radii": {
            "top_left": 0.0,
            "top_right": 0.0,
            "bottom_right": 0.0,
            "bottom_left": 0.0,
        },
    }
    document, auto_frame = add_ui_object(
        document,
        kind="frame",
        name="UMG Auto Row",
        x=24,
        y=float(artboard["height"]) - 104,
        width=float(artboard["width"]) - 48,
        height=72,
        style=flat_native_style,
    )
    document, auto_frame = update_ui_object(
        document,
        auto_frame["id"],
        {
            "layout": {
                "mode": "horizontal",
                "umg_spacing_strategy": "spacer",
                "umg_spacer_size_rule": "fill",
                "umg_spacer_fill_coefficient": 1.0,
                "padding": {
                    "left": 12,
                    "top": 10,
                    "right": 12,
                    "bottom": 10,
                },
                "gap": 8,
                "main_alignment": "start",
                "cross_alignment": "center",
            }
        },
    )
    document, _auto_first = add_ui_object(
        document,
        kind="button",
        name="UMG Auto First",
        parent_id=auto_frame["id"],
        width=96,
        height=44,
        style=flat_native_style,
    )
    document, _auto_second = add_ui_object(
        document,
        kind="button",
        name="UMG Auto Second",
        parent_id=auto_frame["id"],
        width=112,
        height=44,
        style=flat_native_style,
    )
    document, overlay_frame = add_ui_object(
        document,
        kind="frame",
        name="UMG Overlay Stack",
        x=24,
        y=520,
        width=163,
        height=48,
        style=flat_native_style,
    )
    document, overlay_frame = update_ui_object(
        document,
        overlay_frame["id"],
        {
            "layout": {
                "mode": "overlay",
                "umg_spacing_strategy": "padding",
            }
        },
    )
    document, _overlay_bottom = add_ui_object(
        document,
        kind="rectangle",
        name="UMG Overlay Bottom",
        parent_id=overlay_frame["id"],
        x=24,
        y=520,
        width=163,
        height=48,
        style={
            **flat_native_style,
            "fill": "#D946EFFF",
        },
    )
    document, _overlay_top = add_ui_object(
        document,
        kind="rectangle",
        name="UMG Overlay Top",
        parent_id=overlay_frame["id"],
        x=80,
        y=532,
        width=72,
        height=24,
        style={
            **flat_native_style,
            "fill": "#22C55EFF",
        },
    )
    document, grid_frame = add_ui_object(
        document,
        kind="frame",
        name="UMG Auto Grid",
        x=24,
        y=float(artboard["height"]) - 190,
        width=float(artboard["width"]) - 48,
        height=70,
        style=flat_native_style,
    )
    document, grid_frame = update_ui_object(
        document,
        grid_frame["id"],
        {
            "layout": {
                "mode": "grid",
                "grid_columns": 3,
                "padding": 8,
                "gap": 6,
                "cross_gap": 6,
            }
        },
    )
    document, grid_first = add_ui_object(
        document,
        kind="button",
        name="UMG Grid Span",
        parent_id=grid_frame["id"],
        width=120,
        height=44,
        style=flat_native_style,
    )
    document, _grid_first = update_ui_object(
        document,
        grid_first["id"],
        {
            "layout": {
                "grid_column_span": 2,
                "cell_horizontal_alignment": "stretch",
                "cell_vertical_alignment": "stretch",
            }
        },
    )
    document, _grid_second = add_ui_object(
        document,
        kind="button",
        name="UMG Grid Last",
        parent_id=grid_frame["id"],
        width=80,
        height=44,
        style=flat_native_style,
    )
    document, scroll_frame = add_ui_object(
        document,
        kind="frame",
        name="UMG Scroll Frame",
        x=float(artboard["width"]) - 170,
        y=470,
        width=140,
        height=110,
        style=flat_native_style,
    )
    document, scroll_frame = update_ui_object(
        document,
        scroll_frame["id"],
        {
            "clip_content": True,
            "scroll": {"overflow": "both"},
        },
    )
    document, _scroll_content = add_ui_object(
        document,
        kind="button",
        name="UMG Scroll Content",
        parent_id=scroll_frame["id"],
        x=float(artboard["width"]) - 160,
        y=560,
        width=110,
        height=80,
        style=flat_native_style,
    )
    document, scroll_fixed = add_ui_object(
        document,
        kind="button",
        name="UMG Scroll Fixed",
        parent_id=scroll_frame["id"],
        x=float(artboard["width"]) - 160,
        y=480,
        width=110,
        height=28,
        style=flat_native_style,
    )
    document, _scroll_fixed = update_ui_object(
        document,
        scroll_fixed["id"],
        {
            "layout": {"positioning": "absolute"},
            "scroll": {"position": "fixed"},
        },
    )

    exported = painter_ui_to_umg_document(document)
    target_names = {
        *authored_modes,
        "UMG Auto Row",
        "UMG Auto First",
        "UMG Auto Second",
        "UMG Overlay Stack",
        "UMG Overlay Bottom",
        "UMG Overlay Top",
        "UMG Auto Grid",
        "UMG Grid Span",
        "UMG Grid Last",
        "UMG Scroll Frame",
        "UMG Scroll Content",
        "UMG Scroll Fixed",
    }
    expectations = [
        {
            "id": str(layer["Id"]),
            "name": str(layer["Name"]),
            "canvas_slot": copy.deepcopy(layer["CanvasSlot"]),
            "render_transform_pivot": copy.deepcopy(
                layer["RenderTransformPivot"]
            ),
            "disposition": str(layer["Disposition"]),
            "material": copy.deepcopy(layer.get("Material") or {}),
            "image_fill": copy.deepcopy(layer.get("ImageFill") or {}),
            "asset_id": str(layer.get("AssetId") or ""),
            "panel_kind": str(layer.get("PanelKind") or "None"),
            "spacing_strategy": str(
                layer.get("SpacingStrategy") or "Padding"
            ),
            "spacer_size_rule": str(
                layer.get("SpacerSizeRule") or "Auto"
            ),
            "spacer_fill_coefficient": float(
                layer.get("SpacerFillCoefficient") or 1.0
            ),
            "flow_slot": copy.deepcopy(layer.get("FlowSlot") or {}),
            "scroll_overflow": str(layer.get("ScrollOverflow") or "None"),
            "scroll_position": str(layer.get("ScrollPosition") or "Scroll"),
        }
        for layer in exported["Layers"]
        if str(layer.get("Name") or "") in target_names
    ]
    return document, expectations


def _ensure_project(workspace: Path) -> Path:
    project_root = workspace / "UnrealProject"
    project_root.mkdir(parents=True, exist_ok=True)
    project = project_root / "TigerPainterUMGQA.uproject"
    if not project.is_file():
        project.write_text(
            json.dumps(
                {
                    "FileVersion": 3,
                    "EngineAssociation": "5.8",
                    "Category": "",
                    "Description": "Tiger Studio Painter UMG QA",
                    "Plugins": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return project


def _reopen_script(
    asset_path: str,
    report_path: Path,
    material_paths: list[str] | tuple[str, ...] = (),
    material_widget_names: list[str] | tuple[str, ...] = (),
    material_stop_counts: list[int] | tuple[int, ...] = (),
    material_owner_asset_paths: list[str] | tuple[str, ...] = (),
    texture_paths: list[str] | tuple[str, ...] = (),
    texture_widget_names: list[str] | tuple[str, ...] = (),
    texture_owner_asset_paths: list[str] | tuple[str, ...] = (),
    expected_widget_classes: dict[str, str] | None = None,
) -> str:
    return f"""
import json
from pathlib import Path
import unreal

asset_path = {asset_path!r}
material_paths = {list(material_paths)!r}
material_widget_name_list = {list(material_widget_names)!r}
material_widget_names = set(material_widget_name_list)
material_stop_counts = {list(material_stop_counts)!r}
material_owner_asset_paths = {list(material_owner_asset_paths)!r}
texture_paths = {list(texture_paths)!r}
texture_widget_names = {list(texture_widget_names)!r}
texture_owner_asset_paths = {list(texture_owner_asset_paths)!r}
expected_widget_classes = {dict(expected_widget_classes or {})!r}
asset = unreal.load_asset(asset_path)
generated_class = None
widget_tree = None
widgets = []
widget_count = 0
widget_names = []
widget_classes = {{}}
errors = []
warnings = []
if asset is None:
    errors.append("generated_asset_missing_after_reopen")
else:
    try:
        generated_class = asset.generated_class()
    except Exception:
        try:
            generated_class = asset.get_editor_property("generated_class")
        except Exception as exc:
            errors.append("generated_class_unavailable:" + str(exc))
    try:
        widget_tree = asset.get_editor_property("widget_tree")
        widgets = widget_tree.get_all_widgets() if widget_tree is not None else []
        widget_count = len(widgets)
        widget_names = [widget.get_name() for widget in widgets]
        widget_classes = {{
            widget.get_name(): widget.get_class().get_name()
            for widget in widgets
        }}
    except Exception:
        try:
            default_widget = unreal.get_default_object(generated_class)
            widget_tree = default_widget.get_editor_property("widget_tree")
            widgets = (
                widget_tree.get_all_widgets()
                if widget_tree is not None
                else []
            )
            widget_count = len(widgets)
            widget_names = [widget.get_name() for widget in widgets]
            widget_classes = {{
                widget.get_name(): widget.get_class().get_name()
                for widget in widgets
            }}
        except Exception as exc:
            warnings.append(
                "widget_tree_not_exposed_to_python_after_reopen:" + str(exc)
            )

materials = []
for material_index, material_path in enumerate(material_paths):
    stop_count = (
        int(material_stop_counts[material_index])
        if material_index < len(material_stop_counts)
        else 0
    )
    material = unreal.load_asset(material_path)
    material_row = {{
        "path": material_path,
        "loaded": material is not None,
        "class": material.get_class().get_name() if material is not None else "",
        "domain": "",
        "expression_classes": [],
        "expected_expression_count": 7 + stop_count if stop_count else 0,
        "custom_hlsl_present": False,
        "errors": [],
    }}
    if material is None:
        material_row["errors"].append("generated_material_missing_after_reopen")
    else:
        try:
            material_row["domain"] = str(
                material.get_editor_property("material_domain")
            )
        except Exception as exc:
            material_row["errors"].append("material_domain_unavailable:" + str(exc))
        try:
            expressions = unreal.MaterialEditingLibrary.get_material_expressions(
                material
            )
            material_row["expression_classes"] = [
                expression.get_class().get_name() for expression in expressions
            ]
            material_row["custom_hlsl_present"] = (
                "MaterialExpressionCustom"
                in material_row["expression_classes"]
            )
        except Exception as exc:
            material_row["errors"].append("material_graph_unavailable:" + str(exc))
    material_row["ok"] = (
        material_row["loaded"]
        and material_row["class"] == "Material"
        and "MD_UI" in material_row["domain"]
        and material_row["custom_hlsl_present"]
        and material_row["expression_classes"].count(
            "MaterialExpressionCustom"
        ) == 1
        and (
            not material_row["expected_expression_count"]
            or len(material_row["expression_classes"])
            == material_row["expected_expression_count"]
        )
        and not material_row["errors"]
    )
    materials.append(material_row)

material_brushes = []
widgets_by_name = {{widget.get_name(): widget for widget in widgets}}
for logical_widget_name in material_widget_name_list:
    # Rounded Card materials use a stable layout wrapper named after the layer
    # and an expanded visual child so shadows can draw outside that layout box.
    # Legacy gradient materials still put the brush on the logical widget.
    visual_widget_name = logical_widget_name + "_Visual"
    widget = widgets_by_name.get(visual_widget_name)
    if widget is None:
        visual_widget_name = logical_widget_name
        widget = widgets_by_name.get(visual_widget_name)
    if widget is None:
        continue
    brush_row = {{
        "widget_name": logical_widget_name,
        "visual_widget_name": visual_widget_name,
        "resource_path": "",
        "resource_class": "",
        "errors": [],
    }}
    try:
        brush = widget.get_editor_property("brush")
        resource = brush.get_editor_property("resource_object")
        if resource is not None:
            brush_row["resource_path"] = resource.get_path_name()
            brush_row["resource_class"] = resource.get_class().get_name()
    except Exception as exc:
        brush_row["errors"].append("material_brush_unavailable:" + str(exc))
    brush_row["ok"] = (
        brush_row["resource_class"] in {{"Material", "MaterialInstanceConstant"}}
        and brush_row["resource_path"] in material_paths
        and not brush_row["errors"]
    )
    material_brushes.append(brush_row)

if not material_brushes and material_paths:
    # WidgetBlueprint.WidgetTree is not exposed in all UE Python builds. The
    # asset registry still proves that the reopened Widget Blueprint package
    # serialized the generated Material reference.
    widget_package = asset_path.split(".", 1)[0]
    for material_index, material_path in enumerate(material_paths):
        widget_name = (
            material_widget_name_list[material_index]
            if material_index < len(material_widget_name_list)
            else ""
        )
        owner_asset_path = (
            material_owner_asset_paths[material_index]
            if material_index < len(material_owner_asset_paths)
            and material_owner_asset_paths[material_index]
            else asset_path
        )
        expected_owner_package = owner_asset_path.split(".", 1)[0]
        try:
            referencers = [
                str(value)
                for value in unreal.EditorAssetLibrary.find_package_referencers_for_asset(
                    material_path,
                    False,
                )
            ]
            error_text = ""
        except Exception as exc:
            referencers = []
            error_text = "material_referencers_unavailable:" + str(exc)
        material_brushes.append({{
            "widget_name": widget_name,
            "resource_path": material_path,
            "resource_class": "Material",
            "verification": "serialized_package_reference",
            "expected_owner_package": expected_owner_package,
            "referencers": referencers,
            "errors": [error_text] if error_text else [],
            "ok": expected_owner_package in referencers and not error_text,
        }})

textures = []
widget_package = asset_path.split(".", 1)[0]
for texture_index, texture_path in enumerate(texture_paths):
    texture = unreal.load_asset(texture_path)
    try:
        referencers = [
            str(value)
            for value in unreal.EditorAssetLibrary.find_package_referencers_for_asset(
                texture_path,
                False,
            )
        ]
        referencer_error = ""
    except Exception as exc:
        referencers = []
        referencer_error = "texture_referencers_unavailable:" + str(exc)
    texture_row = {{
        "path": texture_path,
        "widget_name": (
            texture_widget_names[texture_index]
            if texture_index < len(texture_widget_names)
            else ""
        ),
        "loaded": texture is not None,
        "class": texture.get_class().get_name() if texture is not None else "",
        "expected_owner_package": (
            texture_owner_asset_paths[texture_index].split(".", 1)[0]
            if texture_index < len(texture_owner_asset_paths)
            and texture_owner_asset_paths[texture_index]
            else widget_package
        ),
        "referencers": referencers,
        "errors": [referencer_error] if referencer_error else [],
    }}
    texture_row["ok"] = (
        texture_row["loaded"]
        and texture_row["class"] == "Texture2D"
        and texture_row["expected_owner_package"] in referencers
        and not texture_row["errors"]
    )
    textures.append(texture_row)

payload = {{
    "ok": (
        asset is not None
        and generated_class is not None
        and all(row["ok"] for row in materials)
        and len(material_brushes) == len(material_widget_names)
        and all(row["ok"] for row in material_brushes)
        and len(textures) == len(texture_paths)
        and all(row["ok"] for row in textures)
        and (
            not widget_classes
            or all(
                widget_classes.get(name) == class_name
                for name, class_name in expected_widget_classes.items()
            )
        )
    ),
    "asset_path": asset_path,
    "asset_loaded": asset is not None,
    "asset_class": asset.get_class().get_name() if asset is not None else "",
    "generated_class_loaded": generated_class is not None,
    "generated_class_name": generated_class.get_name() if generated_class is not None else "",
    "widget_tree_loaded": widget_tree is not None or widget_count > 0,
    "widget_count": widget_count,
    "widget_names": widget_names,
    "widget_classes": widget_classes,
    "expected_widget_classes": expected_widget_classes,
    "materials": materials,
    "material_brushes": material_brushes,
    "textures": textures,
    "errors": errors,
    "warnings": warnings,
}}
Path({str(report_path)!r}).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
""".strip()


def _reopen_generated_asset(
    project: Path,
    asset_path: str,
    *,
    material_paths: list[str] | tuple[str, ...] = (),
    material_widget_names: list[str] | tuple[str, ...] = (),
    material_stop_counts: list[int] | tuple[int, ...] = (),
    material_owner_asset_paths: list[str] | tuple[str, ...] = (),
    texture_paths: list[str] | tuple[str, ...] = (),
    texture_widget_names: list[str] | tuple[str, ...] = (),
    texture_owner_asset_paths: list[str] | tuple[str, ...] = (),
    expected_widget_classes: dict[str, str] | None = None,
    timeout_seconds: int,
) -> dict:
    editor = (
        DEFAULT_UNREAL_ENGINE_ROOT
        / "Binaries"
        / "Win64"
        / "UnrealEditor-Cmd.exe"
    )
    with tempfile.TemporaryDirectory(
        prefix="tigerstudio_painter_umg_reopen_"
    ) as temporary:
        temporary_root = Path(temporary)
        report_path = temporary_root / "reopen_report.json"
        script_path = temporary_root / "reopen_umg.py"
        script_path.write_text(
            _reopen_script(
                asset_path,
                report_path,
                material_paths=material_paths,
                material_widget_names=material_widget_names,
                material_stop_counts=material_stop_counts,
                material_owner_asset_paths=material_owner_asset_paths,
                texture_paths=texture_paths,
                texture_widget_names=texture_widget_names,
                texture_owner_asset_paths=texture_owner_asset_paths,
                expected_widget_classes=expected_widget_classes,
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                str(editor),
                str(project),
                f"-ExecutePythonScript={script_path.as_posix()}",
                "-ScriptErrorsAreFatal",
                "-unattended",
                "-nop4",
                "-nosplash",
                "-nullrhi",
            ],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=max(30, int(timeout_seconds)),
            check=False,
        )
        if not report_path.is_file():
            return {
                "ok": False,
                "returncode": completed.returncode,
                "errors": ["Unreal did not produce a reopen report."],
                "stdout_tail": completed.stdout[-8000:],
                "stderr_tail": completed.stderr[-8000:],
            }
        result = json.loads(report_path.read_text(encoding="utf-8"))
        result.update(
            {
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-4000:],
                "stderr_tail": completed.stderr[-4000:],
            }
        )
        result["ok"] = bool(result.get("ok")) and completed.returncode == 0
        return result


def _reopen_owner_asset_paths(
    generated_asset_path: str,
    generated_component_asset_paths: dict | None,
    expectation_rows: list[dict] | tuple[dict, ...],
) -> list[str]:
    """Resolve the Widget Blueprint package that serializes each resource.

    Component-definition layers are authored into their generated component
    Widget Blueprint, while ordinary layers are authored into the document's
    root Widget Blueprint.  Reopen QA must therefore check resource
    referencers against the corresponding owner rather than always expecting
    the root package.
    """
    root_asset_path = str(generated_asset_path or "")
    component_asset_paths = {
        str(component_id): str(asset_path)
        for component_id, asset_path in (
            generated_component_asset_paths or {}
        ).items()
        if str(component_id) and str(asset_path)
    }
    return [
        component_asset_paths.get(
            str(row.get("component_id") or ""),
            root_asset_path,
        )
        or root_asset_path
        for row in expectation_rows
    ]


def _render_widget_script(
    asset_path: str,
    output_path: Path,
    report_path: Path,
    *,
    width: int,
    height: int,
) -> str:
    return f"""
import json
from pathlib import Path
import unreal

def read_property(value, *names):
    for name in names:
        try:
            return value.get_editor_property(name)
        except Exception:
            pass
        try:
            return getattr(value, name)
        except Exception:
            pass
    return None

def string_map(value):
    try:
        return {{str(key): str(item) for key, item in value.items()}}
    except Exception:
        return {{}}

subsystem = unreal.get_editor_subsystem(unreal.TigerStudioUMGImportSubsystem)
result = subsystem.render_widget_blueprint_to_png(
    {asset_path!r},
    {str(output_path)!r},
    unreal.Vector2D({int(width)}, {int(height)}),
)
payload = {{
    "ok": bool(read_property(result, "success", "b_success")),
    "message": str(read_property(result, "message") or ""),
    "output_path": str(read_property(result, "output_path") or ""),
    "width": int(read_property(result, "width") or 0),
    "height": int(read_property(result, "height") or 0),
    "widget_text_audit": string_map(
        read_property(result, "widget_text_audit", "WidgetTextAudit")
    ),
    "widget_visibility_audit": string_map(
        read_property(
            result,
            "widget_visibility_audit",
            "WidgetVisibilityAudit",
        )
    ),
    "component_instance_audit": string_map(
        read_property(
            result,
            "component_instance_audit",
            "ComponentInstanceAudit",
        )
    ),
    "rounded_card_size_audit": string_map(
        read_property(
            result,
            "rounded_card_size_audit",
            "RoundedCardSizeAudit",
        )
    ),
    "rounded_card_visual_slot_audit": string_map(
        read_property(
            result,
            "rounded_card_visual_slot_audit",
            "RoundedCardVisualSlotAudit",
        )
    ),
}}
Path({str(report_path)!r}).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
""".strip()


def _render_generated_asset(
    project: Path,
    asset_path: str,
    output_path: Path,
    *,
    width: int,
    height: int,
    timeout_seconds: int,
) -> dict:
    editor = (
        DEFAULT_UNREAL_ENGINE_ROOT
        / "Binaries"
        / "Win64"
        / "UnrealEditor-Cmd.exe"
    )
    with tempfile.TemporaryDirectory(
        prefix="tigerstudio_painter_umg_render_"
    ) as temporary:
        temporary_root = Path(temporary)
        report_path = temporary_root / "render_report.json"
        script_path = temporary_root / "render_umg.py"
        script_path.write_text(
            _render_widget_script(
                asset_path,
                output_path,
                report_path,
                width=width,
                height=height,
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                str(editor),
                str(project),
                f"-ExecutePythonScript={script_path.as_posix()}",
                "-ScriptErrorsAreFatal",
                "-unattended",
                "-nop4",
                "-nosplash",
                "-RenderOffscreen",
                "-AllowCommandletRendering",
            ],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=max(30, int(timeout_seconds)),
            check=False,
        )
        if not report_path.is_file():
            return {
                "ok": False,
                "message": "Unreal did not produce an internal render report.",
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-8000:],
                "stderr_tail": completed.stderr[-8000:],
            }
        result = json.loads(report_path.read_text(encoding="utf-8"))
        rendered_path = Path(str(result.get("output_path") or output_path))
        result["pixel_evidence"] = _capture_pixel_evidence(rendered_path)
        result.update(
            {
                "backend": "unreal_fwidget_renderer",
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-4000:],
                "stderr_tail": completed.stderr[-4000:],
            }
        )
        result["ok"] = bool(result.get("ok")) and bool(
            result["pixel_evidence"].get("visible_content")
        ) and completed.returncode == 0
        return result


def _run_isolated_image_crop_qa(
    project: Path,
    workspace: Path,
    *,
    timeout_seconds: int,
) -> dict:
    width, height = 260, 140
    crop_x, crop_y, crop_width, crop_height = 0.2, 0.15, 0.6, 0.7
    with Image.open(IMAGE_FILL_QA_SOURCE) as source:
        source_width, source_height = source.size
    document = create_ui_document(width, height, name="Image Crop QA")
    document["document_id"] = "ui-image-crop-qa"
    document, image_row = add_ui_object(
        document,
        kind="image",
        name="Isolated Figma REST Crop",
        x=0.0,
        y=0.0,
        width=width,
        height=height,
        style={
            "radius": 0.0,
            "corner_radii": {
                "top_left": 0.0,
                "top_right": 0.0,
                "bottom_right": 0.0,
                "bottom_left": 0.0,
            },
        },
        content={
            "source_path": str(IMAGE_FILL_QA_SOURCE.resolve()),
            "image_fit": "stretch",
            "figma_image_transform": [
                [crop_width, 0.0, crop_x],
                [0.0, crop_height, crop_y],
            ],
            "original_width": source_width,
            "original_height": source_height,
        },
    )
    umg_document = painter_ui_to_umg_document(document)
    layer = next(
        row
        for row in umg_document["Layers"]
        if row["Id"] == image_row["id"]
    )
    generation = generate_painter_umg(
        document,
        project_path=project,
        output_dir=workspace / "isolated_crop_packet",
        timeout_seconds=timeout_seconds,
    )
    asset_path = str(generation.get("generated_asset_path") or "")
    texture_paths = [
        str(path)
        for path in generation.get("imported_asset_paths", [])
        if str(path)
    ]
    reopened = (
        _reopen_generated_asset(
            project,
            asset_path,
            texture_paths=texture_paths,
            texture_widget_names=[str(image_row["id"])],
            expected_widget_classes={str(image_row["id"]): "Image"},
            timeout_seconds=timeout_seconds,
        )
        if generation.get("ok") and asset_path
        else {"ok": False, "errors": ["isolated_crop_generation_failed"]}
    )
    output_path = workspace / "isolated_crop_unreal.png"
    rendered = (
        _render_generated_asset(
            project,
            asset_path,
            output_path,
            width=width,
            height=height,
            timeout_seconds=timeout_seconds,
        )
        if reopened.get("ok") and asset_path
        else {"ok": False, "message": "isolated_crop_reopen_failed"}
    )
    comparison = (
        _compare_normalized_crop_render(
            output_path,
            IMAGE_FILL_QA_SOURCE,
            workspace / "isolated_crop_expected.png",
            crop_x=crop_x,
            crop_y=crop_y,
            crop_width=crop_width,
            crop_height=crop_height,
        )
        if rendered.get("ok") and output_path.is_file()
        else {"ok": False, "reason": "isolated_crop_render_failed"}
    )
    return {
        "ok": bool(generation.get("ok"))
        and bool(reopened.get("ok"))
        and bool(rendered.get("ok"))
        and bool(comparison.get("ok"))
        and layer.get("Disposition") == "Native"
        and (layer.get("ImageFill") or {}).get("Mode") == "Crop"
        and generation.get("generated_widget_classes", {}).get(
            str(image_row["id"])
        )
        == "Image",
        "document_id": document["document_id"],
        "object_id": image_row["id"],
        "umg_disposition": layer.get("Disposition"),
        "umg_image_fill": layer.get("ImageFill"),
        "generation": generation,
        "reopen": reopened,
        "render": rendered,
        "comparison": comparison,
    }


def _open_asset_script(asset_path: str, ready_path: Path) -> str:
    return f"""
from pathlib import Path
import json
import unreal

asset = unreal.load_asset({asset_path!r})
if asset is None:
    raise RuntimeError("Painter UMG asset could not be loaded for visual QA.")
subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
opened = subsystem.open_editor_for_assets([asset])
Path({str(ready_path)!r}).write_text(
    json.dumps(
        {{
            "opened": bool(opened),
            "asset_path": {asset_path!r},
            "asset_class": asset.get_class().get_name(),
        }},
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
""".strip()


def _capture_generated_asset(
    project: Path,
    asset_path: str,
    output_path: Path,
    *,
    material_asset_names: list[str] | tuple[str, ...] = (),
    timeout_seconds: int,
) -> dict:
    # Never let a screenshot from a previous attempt masquerade as evidence
    # for the editor process launched below.  This matters when an Unreal
    # startup is interrupted or its ready handshake times out.
    output_path.unlink(missing_ok=True)
    editor = (
        DEFAULT_UNREAL_ENGINE_ROOT
        / "Binaries"
        / "Win64"
        / "UnrealEditor.exe"
    )
    with tempfile.TemporaryDirectory(
        prefix="tigerstudio_painter_umg_capture_"
    ) as temporary:
        temporary_root = Path(temporary)
        ready_path = temporary_root / "ready.txt"
        python_root = project.parent / "Content" / "Python"
        python_root.mkdir(parents=True, exist_ok=True)
        script_path = python_root / "init_unreal.py"
        script_path.write_text(
            _open_asset_script(asset_path, ready_path),
            encoding="utf-8",
        )
        process = subprocess.Popen(
            [
                str(editor),
                str(project),
                "-nop4",
                "-nosplash",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + max(30, int(timeout_seconds))
        windows: list[dict] = []
        ready_payload: dict = {}
        try:
            while time.monotonic() < deadline:
                report = list_capture_windows(
                    process_contains="UnrealEditor",
                    limit=50,
                )
                windows = [
                    row
                    for row in report.get("windows") or []
                    if int(row.get("pid") or 0) == int(process.pid)
                ]
                if ready_path.is_file():
                    try:
                        value = json.loads(
                            ready_path.read_text(encoding="utf-8")
                        )
                        ready_payload = value if isinstance(value, dict) else {}
                    except (OSError, json.JSONDecodeError):
                        ready_payload = {}
                if ready_payload.get("opened") is True and windows:
                    break
                time.sleep(0.5)
            if ready_payload.get("opened") is not True:
                return {
                    "ok": False,
                    "status": "failed",
                    "reason": (
                        "unreal_asset_editor_open_failed"
                        if ready_path.is_file()
                        else "unreal_asset_editor_did_not_signal_ready"
                    ),
                    "pid": process.pid,
                    "window_count": len(windows),
                    "ready": ready_payload,
                }
            time.sleep(3.0)
            report = list_capture_windows(
                process_contains="UnrealEditor",
                limit=50,
            )
            windows = [
                row
                for row in report.get("windows") or []
                if int(row.get("pid") or 0) == int(process.pid)
            ]
            if not windows:
                return {
                    "ok": False,
                    "status": "failed",
                    "reason": "unreal_window_not_found",
                    "pid": process.pid,
                    "window_count": 0,
                    "ready": ready_payload,
                }
            asset_name = asset_path.rsplit(".", 1)[-1].lower()
            windows.sort(
                key=lambda row: (
                    asset_name in str(row.get("title") or "").lower(),
                    int(row.get("width") or 0) * int(row.get("height") or 0),
                ),
                reverse=True,
            )
            selected = windows[0]
            selected_pid = int(selected.get("pid") or 0)
            if selected_pid != int(process.pid):
                return {
                    "ok": False,
                    "status": "failed",
                    "reason": "unreal_window_pid_mismatch",
                    "pid": process.pid,
                    "selected_pid": selected_pid,
                    "ready": ready_payload,
                    "candidate_windows": windows,
                }
            capture: dict = {}
            capture_attempts: list[dict] = []
            for backend in ("wgc_window", "visible", "mss", "printwindow"):
                try:
                    candidate = save_window_screenshot(
                        path=output_path,
                        hwnd=int(selected["hwnd"]),
                        backend=backend,
                        activate=True,
                    )
                    has_visible_content = _capture_has_visible_content(
                        Path(candidate["path"])
                    )
                    capture_attempts.append(
                        {
                            "backend": backend,
                            "ok": has_visible_content,
                            "reason": (
                                ""
                                if has_visible_content
                                else "flat_or_black_capture"
                            ),
                        }
                    )
                    if has_visible_content:
                        capture = candidate
                        break
                except Exception as exc:
                    capture_attempts.append(
                        {
                            "backend": backend,
                            "ok": False,
                            "reason": str(exc),
                        }
                    )
            if not capture:
                return {
                    "ok": False,
                    "status": "failed",
                    "reason": "no_visible_unreal_capture",
                    "capture_attempts": capture_attempts,
                    "window": selected,
                    "candidate_windows": windows,
                }
            log_path = (
                project.parent
                / "Saved"
                / "Logs"
                / f"{project.stem}.log"
            )
            log_text = (
                log_path.read_text(encoding="utf-8", errors="replace")
                if log_path.is_file()
                else ""
            )
            shader_compile_errors = [
                line.strip()
                for line in log_text.splitlines()
                if "Failed to compile Material" in line
                and any(
                    name in line
                    for name in material_asset_names
                    if name
                )
            ]
            return {
                "ok": (
                    Path(capture["path"]).is_file()
                    and not shader_compile_errors
                ),
                "status": "captured",
                "path": capture["path"],
                "backend": capture["backend"],
                "window": capture["window"],
                "candidate_windows": windows,
                "capture_attempts": capture_attempts,
                "shader_compile_errors": shader_compile_errors,
                "ready": ready_payload,
                "pid_matches_launched_editor": True,
                "pixel_evidence": _capture_pixel_evidence(
                    Path(capture["path"])
                ),
            }
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            script_path.unlink(missing_ok=True)


def _blocked_layer_rows(exported_document: dict) -> list[dict]:
    """Return stable, human-readable blockers from the layer contract."""
    return [
        {
            "id": str(layer.get("Id") or ""),
            "name": str(layer.get("Name") or ""),
            "kind": str(layer.get("Kind") or ""),
            "reasons": [
                str(reason) for reason in layer.get("BlockReasons", [])
            ],
        }
        for layer in exported_document.get("Layers", [])
        if str(layer.get("Disposition") or "") == "Blocked"
    ]


def _inspect_builtin_template_compatibility(document: dict) -> dict:
    exported = painter_ui_to_umg_document(document)
    preflight = preflight_painter_umg(document)
    return {
        "schema": "tigerstudio.painter.ui.unreal_umg_template_source.v1",
        "preflight_ok": bool(preflight.get("ok")),
        "disposition_counts": copy.deepcopy(preflight.get("counts") or {}),
        "blocked_layers": _blocked_layer_rows(exported),
        "preflight_blockers": copy.deepcopy(preflight.get("blockers") or []),
        "interaction_count": int(preflight.get("interaction_count") or 0),
    }


def _activate_template_artboard(
    value: dict,
    artboard_id: str = "",
) -> tuple[dict, dict]:
    """Return a copy with the requested built-in artboard made active."""

    document = copy.deepcopy(value)
    artboards = list(document.get("artboards") or [])
    requested_id = str(artboard_id or document.get("active_artboard_id") or "")
    selected_index = next(
        (
            index
            for index, row in enumerate(artboards)
            if str(row.get("id") or "") == requested_id
        ),
        -1,
    )
    if selected_index < 0:
        available = ", ".join(
            str(row.get("id") or "") for row in artboards
        )
        raise ValueError(
            f"Painter UI template artboard not found: {requested_id!r}. "
            f"Available artboards: {available or '(none)'}"
        )
    selected = artboards[selected_index]
    document["active_artboard_id"] = requested_id
    return document, {
        "id": requested_id,
        "name": str(selected.get("name") or requested_id),
        "index": selected_index,
        "width": float(selected.get("width") or 0.0),
        "height": float(selected.get("height") or 0.0),
        "is_default": requested_id == str(value.get("active_artboard_id") or ""),
    }


def _prepare_builtin_template_qa_document(
    value: dict,
) -> tuple[dict, dict]:
    """Prepare an appearance-identical copy of a built-in Painter template.

    Runtime prototype routing is outside this visual conversion acceptance
    test, so interactions are reported and excluded. Object kinds, styles,
    geometry, hierarchy, and appearance are deliberately left untouched: the
    adapter itself must prove that the original template is UMG compatible.
    """
    document = copy.deepcopy(value)
    source = _inspect_builtin_template_compatibility(document)
    excluded_interactions = [
        {
            "id": str(row.get("id") or ""),
            "name": str(row.get("name") or ""),
            "source_object_id": str(row.get("source_object_id") or ""),
            "action": str(row.get("action") or ""),
            "reason": "prototype_routing_outside_visual_umg_qa",
        }
        for row in document.get("interactions", [])
    ]
    document["interactions"] = []
    prepared_export = painter_ui_to_umg_document(document)
    prepared_preflight = preflight_painter_umg(document)
    return document, {
        "schema": "tigerstudio.painter.ui.unreal_umg_template_prepare.v1",
        "mode": "builtin_template_visual_compatibility",
        "source": source,
        "substitutions": [],
        "excluded_interactions": excluded_interactions,
        "prepared": {
            "preflight_ok": bool(prepared_preflight.get("ok")),
            "disposition_counts": copy.deepcopy(
                prepared_preflight.get("counts") or {}
            ),
            "blocked_layers": _blocked_layer_rows(prepared_export),
            "preflight_blockers": copy.deepcopy(
                prepared_preflight.get("blockers") or []
            ),
        },
    }


def _umg_document_expectations(
    document: dict,
    *,
    layout_expectations: list[dict] | tuple[dict, ...] = (),
) -> tuple[dict, dict]:
    exported = painter_ui_to_umg_document(document)
    layers = list(exported.get("Layers") or [])
    component_layers = [
        (str(component.get("Id") or ""), layer)
        for component in exported.get("Components") or []
        if isinstance(component, dict)
        for layer in component.get("Layers") or []
        if isinstance(layer, dict)
    ]
    visual_resource_layers = [
        ("", layer) for layer in layers if isinstance(layer, dict)
    ] + component_layers
    disposition_counts = {
        disposition: sum(
            str(layer.get("Disposition") or "") == disposition
            for layer in layers
        )
        for disposition in ("Native", "Material", "Baked", "Blocked")
    }
    material_layers_by_id = {
        str(layer.get("Id") or ""): {
            "id": str(layer.get("Id") or ""),
            "name": str(layer.get("Name") or ""),
            "component_id": component_id,
            "generator": str(
                (layer.get("Material") or {}).get("Generator") or ""
            ),
            "stop_count": len(
                list((layer.get("Material") or {}).get("Stops") or [])
            ),
        }
        for component_id, layer in visual_resource_layers
        if str(layer.get("Id") or "")
        and str(layer.get("Disposition") or "") == "Material"
    }
    material_layers = list(material_layers_by_id.values())
    image_fill_layers = [
        {
            "id": str(layer.get("Id") or ""),
            "name": str(layer.get("Name") or ""),
            "component_id": component_id,
            "asset_id": str(
                (layer.get("ImageFill") or {}).get("AssetId") or ""
            ),
        }
        for component_id, layer in visual_resource_layers
        if str((layer.get("ImageFill") or {}).get("AssetId") or "")
    ]
    panel_classes = {
        "Horizontal": "HorizontalBox",
        "Vertical": "VerticalBox",
        "Grid": "GridPanel",
        "Overlay": "Overlay",
    }
    expected_widget_classes = {
        str(layer.get("Id") or ""): panel_classes[
            str(layer.get("PanelKind") or "")
        ]
        for layer in layers
        if str(layer.get("PanelKind") or "") in panel_classes
    }
    for layer in layers:
        layer_id = str(layer.get("Id") or "")
        scroll_overflow = str(layer.get("ScrollOverflow") or "None")
        if scroll_overflow == "None":
            continue
        expected_widget_classes[layer_id] = "Overlay"
        expected_widget_classes[layer_id + "#scroll"] = "ScrollBox"
        expected_widget_classes[layer_id + "#fixed"] = "CanvasPanel"
        if scroll_overflow == "Both":
            expected_widget_classes[
                layer_id + "#scroll_horizontal"
            ] = "ScrollBox"

    spacer_audit_suffixes = {
        "UMG Auto First": ("spacer_before",),
        "UMG Auto Second": ("spacer_before", "spacer_after"),
    }
    for row in layout_expectations:
        suffixes = spacer_audit_suffixes.get(
            str(row.get("name") or ""),
            (),
        )
        for suffix in suffixes:
            expected_widget_classes[
                f"{row['id']}#{suffix}"
            ] = "Spacer"

    active_artboard_id = str(document.get("active_artboard_id") or "")
    authored_object_count = sum(
        str(row.get("artboard_id") or "") == active_artboard_id
        for row in document.get("objects", [])
    )
    return exported, {
        "active_artboard_id": active_artboard_id,
        "authored_object_count": authored_object_count,
        "expected_layer_count": len(layers),
        "expected_widget_count": len(layers),
        "disposition_counts": disposition_counts,
        "blocked_layers": _blocked_layer_rows(exported),
        "material_layers": material_layers,
        "image_fill_layers": image_fill_layers,
        "expected_material_count": len(material_layers),
        "expected_texture_count": len(
            {row["asset_id"] for row in image_fill_layers}
        ),
        "expected_widget_classes": expected_widget_classes,
    }


def _qa_stage_status(result: dict, *, generation: bool = False) -> str:
    if bool(result.get("ok")):
        return "passed"
    if str(result.get("status") or "") == "not_run" or str(
        result.get("reason") or ""
    ).endswith("_not_requested"):
        return "not_run"
    if generation:
        preflight = result.get("preflight") or result.get(
            "packaged_preflight"
        )
        if isinstance(preflight, dict) and preflight.get("blockers"):
            return "blocked"
    if any(
        "failed_before" in str(value)
        for value in (
            result.get("message"),
            result.get("reason"),
            result.get("errors"),
        )
    ):
        return "not_run"
    return "failed"


def _build_qa_summary(
    *,
    preparation: dict,
    expectations: dict,
    generation: dict,
    reopened: dict,
    widget_render: dict,
) -> dict:
    generated_asset_path = str(
        generation.get("generated_asset_path") or ""
    )
    generated_material_paths = [
        str(path)
        for path in generation.get("generated_material_paths", [])
        if str(path)
    ]
    reopened_materials = list(reopened.get("materials") or [])
    material_brushes = list(reopened.get("material_brushes") or [])
    return {
        "generation_status": _qa_stage_status(generation, generation=True),
        "reopen_status": _qa_stage_status(reopened),
        "fwidget_renderer_status": _qa_stage_status(widget_render),
        "expected_layer_count": int(expectations["expected_layer_count"]),
        "expected_widget_count": int(expectations["expected_widget_count"]),
        "actual_generated_widget_count": int(
            generation.get("generated_widget_count") or 0
        ),
        "expected_material_count": int(
            expectations.get("expected_material_count") or 0
        ),
        "actual_generated_material_count": len(generated_material_paths),
        "generated_material_paths": generated_material_paths,
        "reopened_material_count": len(reopened_materials),
        "material_brush_reference_count": len(material_brushes),
        "material_reopen_ok": (
            len(reopened_materials) == len(generated_material_paths)
            and len(material_brushes) == len(generated_material_paths)
            and all(bool(row.get("ok")) for row in reopened_materials)
            and all(bool(row.get("ok")) for row in material_brushes)
        ),
        "blocked_layers": copy.deepcopy(
            (preparation.get("source") or {}).get("blocked_layers") or []
        ),
        "source_preflight_blockers": copy.deepcopy(
            (preparation.get("source") or {}).get("preflight_blockers")
            or []
        ),
        "prepared_blocked_layers": copy.deepcopy(
            expectations.get("blocked_layers") or []
        ),
        "actual_asset_path": generated_asset_path,
        "output_path": str(widget_render.get("output_path") or ""),
    }


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--capture-ui", action="store_true")
    parser.add_argument(
        "--template",
        choices=[row["id"] for row in list_ui_templates()],
        default="mobile_onboarding",
        help="Built-in Painter UI template id (default: mobile_onboarding).",
    )
    parser.add_argument(
        "--artboard-id",
        default="",
        help=(
            "Template artboard id to activate and verify. The template's "
            "default active artboard is used when omitted."
        ),
    )
    parser.add_argument(
        "--umg-layout-qa",
        action="store_true",
        help=(
            "Add the specialized Canvas/Overlay/Spacer/Image/Material QA "
            "fixture. The normal template path does not add synthetic layers."
        ),
    )
    return parser


def main() -> int:
    parser = _argument_parser()
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    project = _ensure_project(workspace)
    source_document, template_report = instantiate_ui_template(args.template)
    try:
        source_document, selected_artboard = _activate_template_artboard(
            source_document,
            args.artboard_id,
        )
    except ValueError as exc:
        parser.error(str(exc))
    source_compatibility = _inspect_builtin_template_compatibility(
        source_document
    )
    if args.umg_layout_qa:
        document, layout_expectations = _anchor_qa_document(source_document)
        prepared_preflight = preflight_painter_umg(document)
        prepared_export = painter_ui_to_umg_document(document)
        preparation = {
            "schema": (
                "tigerstudio.painter.ui.unreal_umg_template_prepare.v1"
            ),
            "mode": "specialized_umg_layout_qa",
            "source": source_compatibility,
            "substitutions": [],
            "excluded_interactions": [
                {
                    "id": str(row.get("id") or ""),
                    "name": str(row.get("name") or ""),
                    "source_object_id": str(
                        row.get("source_object_id") or ""
                    ),
                    "action": str(row.get("action") or ""),
                    "reason": "prototype_routing_outside_visual_umg_qa",
                }
                for row in source_document.get("interactions", [])
            ],
            "prepared": {
                "preflight_ok": bool(prepared_preflight.get("ok")),
                "disposition_counts": copy.deepcopy(
                    prepared_preflight.get("counts") or {}
                ),
                "blocked_layers": _blocked_layer_rows(prepared_export),
                "preflight_blockers": copy.deepcopy(
                    prepared_preflight.get("blockers") or []
                ),
            },
        }
    else:
        document, preparation = _prepare_builtin_template_qa_document(
            source_document
        )
        layout_expectations = []
    _exported_document, expectations = _umg_document_expectations(
        document,
        layout_expectations=layout_expectations,
    )
    active_artboard = str(expectations["active_artboard_id"])
    expected_widget_count = int(expectations["expected_widget_count"])
    generation = generate_painter_umg(
        document,
        project_path=project,
        output_dir=workspace / "packet",
        timeout_seconds=args.timeout,
    )
    generated_asset_path = str(generation.get("generated_asset_path") or "")
    generated_material_paths = [
        str(path)
        for path in generation.get("generated_material_paths", [])
        if str(path)
    ]
    material_widget_names = [
        str(row["id"]) for row in expectations["material_layers"]
    ]
    material_stop_counts = [
        (
            int(row["stop_count"])
            if str(row.get("generator") or "")
            == "tiger_ui_gradient_custom_hlsl_v1"
            else 0
        )
        for row in expectations["material_layers"]
    ]
    generated_component_asset_paths = dict(
        generation.get("generated_component_asset_paths") or {}
    )
    material_owner_asset_paths = _reopen_owner_asset_paths(
        generated_asset_path,
        generated_component_asset_paths,
        expectations["material_layers"],
    )
    imported_texture_paths = [
        str(path)
        for path in generation.get("imported_asset_paths", [])
        if str(path)
    ]
    image_fill_rows = list(expectations["image_fill_layers"])
    texture_owner_asset_paths = _reopen_owner_asset_paths(
        generated_asset_path,
        generated_component_asset_paths,
        image_fill_rows,
    )
    expected_widget_classes = dict(expectations["expected_widget_classes"])
    reopened = (
        _reopen_generated_asset(
            project,
            generated_asset_path,
            material_paths=generated_material_paths,
            material_widget_names=material_widget_names,
            material_stop_counts=material_stop_counts,
            material_owner_asset_paths=material_owner_asset_paths,
            texture_paths=imported_texture_paths,
            texture_widget_names=[str(row["id"]) for row in image_fill_rows],
            texture_owner_asset_paths=texture_owner_asset_paths,
            expected_widget_classes=expected_widget_classes,
            timeout_seconds=args.timeout,
        )
        if generation.get("ok") and generated_asset_path
        else {
            "ok": False,
            "errors": ["generation_failed_before_reopen"],
        }
    )
    active_artboard_row = next(
        row
        for row in document["artboards"]
        if str(row.get("id") or "") == active_artboard
    )
    widget_render = (
        _render_generated_asset(
            project,
            generated_asset_path,
            workspace / "painter_umg_fwidget_renderer.png",
            width=max(1, round(float(active_artboard_row["width"]))),
            height=max(1, round(float(active_artboard_row["height"]))),
            timeout_seconds=args.timeout,
        )
        if reopened.get("ok") and generated_asset_path
        else {
            "ok": False,
            "message": "reopen_failed_before_internal_render",
        }
    )
    overlay_render_evidence = (
        _capture_render_color_evidence(
            Path(str(widget_render["output_path"])),
            [
                {
                    "name": "overlay_bottom_paint",
                    "x": 40,
                    "y": 528,
                    "rgba": [217, 70, 239, 255],
                },
                {
                    "name": "overlay_top_paint",
                    "x": 100,
                    "y": 540,
                    "rgba": [34, 197, 94, 255],
                },
            ],
        )
        if args.umg_layout_qa
        and widget_render.get("ok")
        and widget_render.get("output_path")
        else {
            "ok": False,
            "status": "not_run",
            "samples": [],
            "reason": (
                "umg_layout_qa_not_requested"
                if not args.umg_layout_qa
                else "widget_render_failed_before_overlay_evidence"
            ),
        }
    )
    isolated_crop = (
        _run_isolated_image_crop_qa(
            project,
            workspace,
            timeout_seconds=args.timeout,
        )
        if args.umg_layout_qa
        else {
            "ok": False,
            "status": "not_run",
            "reason": "umg_layout_qa_not_requested",
        }
    )
    visual_capture = (
        _capture_generated_asset(
            project,
            generated_asset_path,
            workspace / "painter_umg_unreal_editor.png",
            material_asset_names=[
                path.rsplit("/", 1)[-1].split(".", 1)[0]
                for path in generated_material_paths
            ],
            timeout_seconds=min(args.timeout, 120),
        )
        if args.capture_ui and reopened.get("ok") and generated_asset_path
        else {
            "ok": False,
            "status": "not_run",
            "reason": (
                "capture_not_requested"
                if not args.capture_ui
                else "reopen_failed_before_capture"
            ),
        }
    )
    layout_qa_ok = (
        bool(overlay_render_evidence.get("ok"))
        and bool(isolated_crop.get("ok"))
        if args.umg_layout_qa
        else True
    )
    prepared_preflight_ok = bool(
        (preparation.get("prepared") or {}).get("preflight_ok")
    ) and not expectations["blocked_layers"]
    report_ok = (
        prepared_preflight_ok
        and bool(generation.get("ok"))
        and bool(reopened.get("ok"))
        and bool(widget_render.get("ok"))
        and layout_qa_ok
        and int(generation.get("generated_widget_count") or 0)
        == expected_widget_count
        and len(generated_material_paths)
        == int(expectations["expected_material_count"])
        and len(imported_texture_paths)
        == int(expectations["expected_texture_count"])
        and all(
            generation.get("generated_widget_classes", {}).get(name)
            == class_name
            for name, class_name in expected_widget_classes.items()
        )
        and (not args.capture_ui or bool(visual_capture.get("ok")))
    )
    summary = _build_qa_summary(
        preparation=preparation,
        expectations=expectations,
        generation=generation,
        reopened=reopened,
        widget_render=widget_render,
    )
    report = {
        "schema": "tigerstudio.painter.ui.unreal_umg_qa.v1",
        "ok": report_ok,
        "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
        "project_path": str(project),
        "summary": summary,
        "template": {
            "id": args.template,
            "report": template_report,
            "active_artboard_id": active_artboard,
            "selected_artboard": selected_artboard,
            "umg_layout_qa": bool(args.umg_layout_qa),
            "source_compatibility": source_compatibility,
            "preparation": preparation,
            "expectations": expectations,
            "expected_layer_count": expectations["expected_layer_count"],
            "expected_widget_count": expected_widget_count,
            "anchor_expectations": layout_expectations,
            "expected_widget_classes": expected_widget_classes,
        },
        "generation": generation,
        "reopen": reopened,
        "widget_render": widget_render,
        "overlay_render_evidence": overlay_render_evidence,
        "isolated_crop": isolated_crop,
        "visual_capture": visual_capture,
        "environment": {
            "platform": sys.platform,
            "python": sys.version,
            "pid": os.getpid(),
        },
    }
    report_path = workspace / "qa_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
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
