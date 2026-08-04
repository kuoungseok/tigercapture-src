"""Generate and reopen a real Painter-authored Widget Blueprint in UE 5.8."""
from __future__ import annotations

import argparse
import copy
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_ui_templates import instantiate_ui_template
from app.painter_ui_constraints import capture_ui_constraints
from app.painter_ui_document import add_ui_object, update_ui_object
from app.painter_ui_umg_adapter import (
    generate_painter_umg,
    painter_ui_to_umg_document,
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


def _anchor_qa_document(value: dict) -> tuple[dict, list[dict]]:
    """Author anchors, Image Fill, Rounded Card, and native layout panels."""
    document = copy.deepcopy(value)
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
                "image_fit": "fill",
                "focal_x": 0.62,
                "focal_y": 0.48,
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
    texture_paths: list[str] | tuple[str, ...] = (),
    texture_widget_names: list[str] | tuple[str, ...] = (),
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
texture_paths = {list(texture_paths)!r}
texture_widget_names = {list(texture_widget_names)!r}
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
            "referencers": referencers,
            "errors": [error_text] if error_text else [],
            "ok": widget_package in referencers and not error_text,
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
        "referencers": referencers,
        "errors": [referencer_error] if referencer_error else [],
    }}
    texture_row["ok"] = (
        texture_row["loaded"]
        and texture_row["class"] == "Texture2D"
        and widget_package in referencers
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
    texture_paths: list[str] | tuple[str, ...] = (),
    texture_widget_names: list[str] | tuple[str, ...] = (),
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
                texture_paths=texture_paths,
                texture_widget_names=texture_widget_names,
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


def _open_asset_script(asset_path: str, ready_path: Path) -> str:
    return f"""
from pathlib import Path
import unreal

asset = unreal.load_asset({asset_path!r})
if asset is None:
    raise RuntimeError("Painter UMG asset could not be loaded for visual QA.")
subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
opened = subsystem.open_editor_for_assets([asset])
Path({str(ready_path)!r}).write_text(
    "opened=" + str(bool(opened)),
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
        selected_pid = 0
        try:
            while time.monotonic() < deadline:
                report = list_capture_windows(
                    process_contains="UnrealEditor",
                    limit=50,
                )
                project_name = project.stem.lower()
                asset_name = asset_path.rsplit(".", 1)[-1].lower()
                windows = [
                    row
                    for row in report.get("windows") or []
                    if project_name
                    in str(row.get("title") or "").lower()
                    or asset_name
                    in str(row.get("title") or "").lower()
                ]
                if ready_path.is_file() and windows:
                    break
                time.sleep(0.5)
            if not ready_path.is_file():
                return {
                    "ok": False,
                    "status": "failed",
                    "reason": "unreal_asset_editor_did_not_signal_ready",
                    "pid": process.pid,
                    "window_count": len(windows),
                }
            time.sleep(3.0)
            report = list_capture_windows(
                process_contains="UnrealEditor",
                limit=50,
            )
            project_name = project.stem.lower()
            asset_name = asset_path.rsplit(".", 1)[-1].lower()
            windows = [
                row
                for row in report.get("windows") or []
                if project_name in str(row.get("title") or "").lower()
                or asset_name in str(row.get("title") or "").lower()
            ]
            if not windows:
                return {
                    "ok": False,
                    "status": "failed",
                    "reason": "unreal_window_not_found",
                    "pid": process.pid,
                    "window_count": 0,
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
            capture = save_window_screenshot(
                path=output_path,
                hwnd=int(selected["hwnd"]),
                backend="auto",
                activate=True,
            )
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
                "shader_compile_errors": shader_compile_errors,
            }
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            if selected_pid and selected_pid != process.pid:
                try:
                    os.kill(selected_pid, signal.SIGTERM)
                except OSError:
                    pass
            script_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--capture-ui", action="store_true")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    project = _ensure_project(workspace)
    document, template_report = instantiate_ui_template("mobile_onboarding")
    document, anchor_expectations = _anchor_qa_document(document)
    active_artboard = str(document["active_artboard_id"])
    expected_widget_count = sum(
        1
        for row in document["objects"]
        if row["artboard_id"] == active_artboard
    )
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
        str(row["id"])
        for row in anchor_expectations
        if row.get("disposition") == "Material"
    ]
    material_stop_counts = [
        (
            len(list((row.get("material") or {}).get("Stops") or []))
            if str((row.get("material") or {}).get("Generator") or "")
            == "tiger_ui_gradient_custom_hlsl_v1"
            else 0
        )
        for row in anchor_expectations
        if row.get("disposition") == "Material"
    ]
    imported_texture_paths = [
        str(path)
        for path in generation.get("imported_asset_paths", [])
        if str(path)
    ]
    image_fill_rows = [
        row
        for row in anchor_expectations
        if str((row.get("image_fill") or {}).get("AssetId") or "")
    ]
    image_fill_asset_ids = {
        str((row.get("image_fill") or {}).get("AssetId") or "")
        for row in image_fill_rows
    }
    expected_widget_classes = {
        str(row["id"]): (
            "HorizontalBox"
            if row.get("panel_kind") == "Horizontal"
            else "GridPanel"
        )
        for row in anchor_expectations
        if row.get("panel_kind") in {"Horizontal", "Grid"}
    }
    for row in anchor_expectations:
        if row.get("scroll_overflow") != "None":
            expected_widget_classes[str(row["id"])] = "Overlay"
            expected_widget_classes[str(row["id"]) + "#scroll"] = "ScrollBox"
            expected_widget_classes[str(row["id"]) + "#fixed"] = "CanvasPanel"
            if row.get("scroll_overflow") == "Both":
                expected_widget_classes[
                    str(row["id"]) + "#scroll_horizontal"
                ] = "ScrollBox"
    reopened = (
        _reopen_generated_asset(
            project,
            generated_asset_path,
            material_paths=generated_material_paths,
            material_widget_names=material_widget_names,
            material_stop_counts=material_stop_counts,
            texture_paths=imported_texture_paths,
            texture_widget_names=[str(row["id"]) for row in image_fill_rows],
            expected_widget_classes=expected_widget_classes,
            timeout_seconds=args.timeout,
        )
        if generation.get("ok") and generated_asset_path
        else {
            "ok": False,
            "errors": ["generation_failed_before_reopen"],
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
    report = {
        "schema": "tigerstudio.painter.ui.unreal_umg_qa.v1",
        "ok": bool(generation.get("ok"))
        and bool(reopened.get("ok"))
        and int(generation.get("generated_widget_count") or 0)
        == expected_widget_count
        and len(generated_material_paths) == len(material_widget_names)
        and len(material_widget_names) > 0
        and len(imported_texture_paths) == len(image_fill_asset_ids)
        and len(image_fill_asset_ids) > 0
        and all(
            generation.get("generated_widget_classes", {}).get(name)
            == class_name
            for name, class_name in expected_widget_classes.items()
        )
        and (not args.capture_ui or bool(visual_capture.get("ok"))),
        "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
        "project_path": str(project),
        "template": {
            "id": "mobile_onboarding",
            "report": template_report,
            "active_artboard_id": active_artboard,
            "expected_widget_count": expected_widget_count,
            "anchor_expectations": anchor_expectations,
            "expected_widget_classes": expected_widget_classes,
        },
        "generation": generation,
        "reopen": reopened,
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
