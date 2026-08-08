"""Real UE 5.8 proof for the schema-v12 Tiger UMG flipbook material.

The fixture is generated, not checked in: a 2x2 atlas contains red, green,
blue, and yellow frames. Four UImage layers select frame overrides 0..3, then
the generated Widget Blueprint is reopened and rendered by FWidgetRenderer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping

from PIL import Image, ImageStat


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.unreal_umg_flipbook import normalize_umg_flipbook
from app.unreal_umg_workflow import (
    DEFAULT_UNREAL_ENGINE_ROOT,
    run_unreal_umg_generation,
)
from tools.qa_painter_ui_unreal_umg import (
    _capture_pixel_evidence,
    _ensure_project,
    _render_widget_script,
    _reopen_generated_asset,
)


DEFAULT_WORKSPACE = (
    Path(__file__).resolve().parents[1]
    / "debugCapture"
    / "painter_ui_designer"
    / "unreal_umg_flipbook_m4a"
)
FRAME_COLORS = (
    (255, 32, 32, 255),
    (32, 255, 32, 255),
    (32, 32, 255, 255),
    (255, 255, 32, 255),
)
CAPTURE_SIZE = (256, 256)
CELL_INTERIOR_INSET_PX = 4
RGB_ABS_ERROR_MAX = 2
EXPECTED_ALPHA = 255
RENDER_CONTRACT = {
    "schema": "tigerstudio.painter.ui.unreal_umg_flipbook_render_contract.v1",
    "platform_path": "windows_d3d12",
    "launch_pins": {
        "rhi": "D3D12",
        "display_gamma": 2.2,
        "slate_contrast": 1.0,
    },
    "source_backed_requirements": {
        "widget_renderer_use_gamma_correction": False,
        "widget_renderer_clear_target": True,
        "render_target_pixel_format": "PF_B8G8R8A8",
        "render_target_srgb": True,
        "atlas_texture_srgb": True,
        "material_sampler_type": "SAMPLERTYPE_Color",
        "readback_linear_to_gamma": False,
    },
    "stored_rgb_transform": (
        "sRGB texture decode to linear, gamma-disabled Slate shading, then "
        "one hardware sRGB render-target encode; opaque source bytes are "
        "preserved within the two-byte channel tolerance"
    ),
    "runtime_probe_scope": {
        "probed": ["atlas_texture_srgb", "material_sampler_type"],
        "launch_pinned_not_probed": [
            "rhi",
            "display_gamma",
            "slate_contrast",
        ],
        "engine_source_contract_not_probed": [
            "render_target_pixel_format",
            "render_target_srgb",
            "readback_linear_to_gamma",
        ],
    },
}


def _write_atlas(path: Path, *, cell_size: int = 128) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (cell_size * 2, cell_size * 2))
    for frame, color in enumerate(FRAME_COLORS):
        column = frame % 2
        row = frame // 2
        tile = Image.new("RGBA", (cell_size, cell_size), color)
        image.paste(tile, (column * cell_size, row * cell_size))
    image.save(path)
    return path


def _canvas_slot(x: int, y: int, width: int, height: int) -> dict[str, Any]:
    return {
        "AnchorMinimum": {"X": 0.0, "Y": 0.0},
        "AnchorMaximum": {"X": 0.0, "Y": 0.0},
        "Offsets": {
            "Left": float(x),
            "Top": float(y),
            "Right": float(width),
            "Bottom": float(height),
        },
        "Alignment": {"X": 0.0, "Y": 0.0},
    }


def _flow_slot() -> dict[str, Any]:
    return {
        "Padding": {"Left": 0.0, "Top": 0.0, "Right": 0.0, "Bottom": 0.0},
        "HorizontalAlignment": "Fill",
        "VerticalAlignment": "Fill",
        "SizeRule": "Auto",
        "FillCoefficient": 1.0,
        "Row": 0,
        "Column": 0,
        "RowSpan": 1,
        "ColumnSpan": 1,
    }


def _flipbook_document(atlas_path: Path) -> dict[str, Any]:
    atlas_hash = hashlib.sha256(atlas_path.read_bytes()).hexdigest()
    asset_id = "texture_flipbook_m4a_2x2"
    layers: list[dict[str, Any]] = []
    for frame in range(4):
        x = (frame % 2) * 128
        y = (frame // 2) * 128
        flipbook = normalize_umg_flipbook(
            {
                "asset_id": asset_id,
                "columns": 2,
                "rows": 2,
                "frame_count": 4,
                "fps": 8.0,
                "start_frame": 0,
                "loop": True,
                "phase": 0.0,
                "static_frame_override": frame,
            }
        )
        layers.append(
            {
                "Id": f"Frame{frame}",
                "ParentId": "",
                "Name": f"Static frame {frame}",
                "Kind": "Image",
                "Disposition": "Material",
                "BlockReasons": [],
                "Position": {"X": float(x), "Y": float(y)},
                "Size": {"X": 128.0, "Y": 128.0},
                "Scale": {"X": 1.0, "Y": 1.0},
                "Anchor": {"X": 0.0, "Y": 0.0},
                "CanvasSlot": _canvas_slot(x, y, 128, 128),
                "PanelKind": "None",
                "FlowSlot": _flow_slot(),
                "ScrollOverflow": "None",
                "ScrollPosition": "Scroll",
                "RenderTransformPivot": {"X": 0.5, "Y": 0.5},
                "RotationDegrees": 0.0,
                "Opacity": 1.0,
                "AssetId": "",
                "ImageFill": {},
                "Material": {},
                "Flipbook": flipbook,
                "PayloadJson": json.dumps(
                    {
                        "source_kind": "image",
                        "painter_conversion": "flipbook_ui_material",
                    },
                    separators=(",", ":"),
                ),
            }
        )
    return {
        "SchemaVersion": 12,
        "Provider": "painter",
        "DocumentId": "painter-flipbook-m4a-2x2",
        "Revision": 1,
        "Width": 256,
        "Height": 256,
        "FrameRate": 30.0,
        "DurationMilliseconds": 1000,
        "Resources": [
            {
                "Id": asset_id,
                "Kind": "texture",
                "SourcePath": str(atlas_path.resolve()),
                "DestinationName": "TS_Flipbook_M4A_Atlas",
                "ContentHash": atlas_hash,
                "SettingsJson": json.dumps(
                    {
                        "Usage": "FlipbookAtlas",
                        "SRGB": True,
                        "AddressX": "Clamp",
                        "AddressY": "Clamp",
                    },
                    separators=(",", ":"),
                ),
            }
        ],
        "Layers": layers,
        "Animations": [],
        "Interactions": [],
    }


def _inspection_script(
    material_paths: list[str],
    texture_path: str,
    report_path: Path,
) -> str:
    expected_overrides = {
        path: index for index, path in enumerate(material_paths)
    }
    return f"""
import json
from pathlib import Path
import unreal

material_paths = {material_paths!r}
texture_path = {texture_path!r}
expected_overrides = {expected_overrides!r}

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

rows = []
for material_path in material_paths:
    material = unreal.load_asset(material_path)
    row = {{
        "path": material_path,
        "loaded": material is not None,
        "domain": "",
        "expression_classes": [],
        "scalar_defaults": {{}},
        "custom_code": "",
        "custom_output_type": "",
        "atlas_texture_path": "",
        "sampler_type": "",
        "errors": [],
    }}
    if material is None:
        row["errors"].append("material_missing")
        rows.append(row)
        continue
    try:
        row["domain"] = str(read_property(material, "material_domain"))
        expressions = unreal.MaterialEditingLibrary.get_material_expressions(
            material
        )
        row["expression_classes"] = [
            expression.get_class().get_name() for expression in expressions
        ]
        for expression in expressions:
            class_name = expression.get_class().get_name()
            if class_name == "MaterialExpressionScalarParameter":
                name = str(read_property(expression, "parameter_name") or "")
                row["scalar_defaults"][name] = float(
                    read_property(expression, "default_value") or 0.0
                )
            elif class_name == "MaterialExpressionCustom":
                row["custom_code"] = str(read_property(expression, "code") or "")
                row["custom_output_type"] = str(
                    read_property(expression, "output_type") or ""
                )
            elif class_name == "MaterialExpressionTextureSampleParameter2D":
                texture = read_property(expression, "texture")
                row["atlas_texture_path"] = (
                    texture.get_path_name() if texture is not None else ""
                )
                row["sampler_type"] = str(
                    read_property(expression, "sampler_type") or ""
                )
    except Exception as exc:
        row["errors"].append("material_graph_inspection_failed:" + str(exc))
    expected_parameters = {{
        "Columns": 2.0,
        "Rows": 2.0,
        "FrameCount": 4.0,
        "FramesPerSecond": 8.0,
        "StartFrame": 0.0,
        "Loop": 1.0,
        "Phase": 0.0,
        "StaticFrameOverride": float(expected_overrides[material_path]),
    }}
    row["expected_parameters"] = expected_parameters
    row["parameters_match"] = (
        set(row["scalar_defaults"]) == set(expected_parameters)
        and all(
            abs(row["scalar_defaults"][name] - value) <= 0.0001
            for name, value in expected_parameters.items()
        )
    )
    classes = row["expression_classes"]
    row["ok"] = (
        row["loaded"]
        and "MD_UI" in row["domain"]
        and len(classes) == 12
        and classes.count("MaterialExpressionTextureCoordinate") == 1
        and classes.count("MaterialExpressionTime") == 1
        and classes.count("MaterialExpressionScalarParameter") == 8
        and classes.count("MaterialExpressionCustom") == 1
        and classes.count("MaterialExpressionTextureSampleParameter2D") == 1
        and classes.count("MaterialExpressionComponentMask") == 0
        and row["parameters_match"]
        and "Tiger Flipbook Atlas / validated fixed Custom HLSL" in row["custom_code"]
        and "StaticFrameOverride" in row["custom_code"]
        and "return (CellUV + float2(Column, Row))" in row["custom_code"]
        and "Texture2DSample" not in row["custom_code"]
        and row["atlas_texture_path"] == texture_path
        and "SAMPLERTYPE_COLOR" in row["sampler_type"].upper()
        and not row["errors"]
    )
    rows.append(row)

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
    referencer_error = str(exc)
expected_material_packages = [path.split(".", 1)[0] for path in material_paths]
texture_row = {{
    "path": texture_path,
    "loaded": texture is not None,
    "class": texture.get_class().get_name() if texture is not None else "",
    "referencers": referencers,
    "expected_material_packages": expected_material_packages,
    "error": referencer_error,
    "srgb": bool(read_property(texture, "srgb")) if texture is not None else False,
}}
texture_row["ok"] = (
    texture_row["loaded"]
    and texture_row["class"] == "Texture2D"
    and texture_row["srgb"]
    and set(expected_material_packages).issubset(set(referencers))
    and not referencer_error
)
payload = {{
    "ok": len(rows) == 4 and all(row["ok"] for row in rows) and texture_row["ok"],
    "materials": rows,
    "texture": texture_row,
}}
Path({str(report_path)!r}).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
""".strip()


def _inspect_materials(
    project: Path,
    material_paths: list[str],
    texture_path: str,
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    editor = (
        DEFAULT_UNREAL_ENGINE_ROOT
        / "Binaries"
        / "Win64"
        / "UnrealEditor-Cmd.exe"
    )
    with tempfile.TemporaryDirectory(
        prefix="tigerstudio_flipbook_inspect_"
    ) as temporary:
        temporary_root = Path(temporary)
        script_path = temporary_root / "inspect_flipbook.py"
        report_path = temporary_root / "report.json"
        script_path.write_text(
            _inspection_script(material_paths, texture_path, report_path),
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
                "errors": ["Unreal did not produce a flipbook graph report."],
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-8000:],
                "stderr_tail": completed.stderr[-8000:],
            }
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report.update(
            {
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-4000:],
                "stderr_tail": completed.stderr[-4000:],
            }
        )
        report["ok"] = bool(report.get("ok")) and completed.returncode == 0
        return report


def _material_compile_failures(text: str) -> list[str]:
    lines = text.splitlines()
    failures: list[str] = []
    for index, line in enumerate(lines):
        if "Failed to compile Material" not in line:
            continue
        detail = ""
        for candidate in lines[index + 1 : index + 4]:
            candidate = candidate.strip()
            if candidate:
                detail = candidate
                break
        message = line.strip()
        if detail:
            message += " | " + detail
        if message not in failures:
            failures.append(message)
    return failures


def _render_flipbook_asset(
    project: Path,
    asset_path: str,
    output_path: Path,
    *,
    width: int,
    height: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Render with FWidgetRenderer and fail on any real material compile error."""

    editor = (
        DEFAULT_UNREAL_ENGINE_ROOT
        / "Binaries"
        / "Win64"
        / "UnrealEditor-Cmd.exe"
    )
    log_root = project.parent / "Saved" / "Logs"
    before_logs = {
        path: path.stat().st_mtime_ns
        for path in log_root.glob("*.log")
        if path.is_file()
    }
    with tempfile.TemporaryDirectory(
        prefix="tigerstudio_flipbook_render_"
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
        started_ns = time.time_ns()
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
                "-d3d12",
                "-ExecCmds=Gamma 2.2,Slate.Contrast 1",
            ],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=max(30, int(timeout_seconds)),
            check=False,
        )
        changed_logs: list[Path] = []
        for path in log_root.glob("*.log"):
            if not path.is_file():
                continue
            modified_ns = path.stat().st_mtime_ns
            if (
                path not in before_logs
                or modified_ns != before_logs[path]
                or modified_ns >= started_ns
            ):
                changed_logs.append(path)
        diagnostic_texts = [completed.stdout, completed.stderr]
        for path in changed_logs:
            diagnostic_texts.append(
                path.read_text(encoding="utf-8", errors="replace")
            )
        compile_failures = _material_compile_failures(
            "\n".join(diagnostic_texts)
        )
        common = {
            "backend": "unreal_fwidget_renderer",
            "render_contract": RENDER_CONTRACT,
            "returncode": completed.returncode,
            "material_compile_failure_count": len(compile_failures),
            "material_compile_failures": compile_failures,
            "diagnostic_logs": [str(path) for path in changed_logs],
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
        if not report_path.is_file():
            return {
                "ok": False,
                "message": "Unreal did not produce an internal render report.",
                **common,
            }
        result = json.loads(report_path.read_text(encoding="utf-8"))
        rendered_path = Path(str(result.get("output_path") or output_path))
        result["pixel_evidence"] = _capture_pixel_evidence(rendered_path)
        result.update(common)
        result["ok"] = (
            bool(result.get("ok"))
            and bool(result["pixel_evidence"].get("visible_content"))
            and completed.returncode == 0
            and not compile_failures
        )
        return result


def _write_expected_grid(path: Path, *, size: int = 256) -> Path:
    """Write opaque sRGB bytes expected after exactly one output transfer."""

    image = Image.new("RGBA", (size, size))
    half = size // 2
    for frame, color in enumerate(FRAME_COLORS):
        tile = Image.new("RGBA", (half, half), color)
        image.paste(tile, ((frame % 2) * half, (frame // 2) * half))
    image.save(path)
    return path


def _compare_frame_grid(
    actual_path: Path,
    expected_path: Path,
    *,
    inset: int = CELL_INTERIOR_INSET_PX,
) -> dict[str, Any]:
    actual = Image.open(actual_path).convert("RGBA")
    expected = Image.open(expected_path).convert("RGBA")
    width, height = actual.size
    required_width, required_height = CAPTURE_SIZE
    size_matches = actual.size == CAPTURE_SIZE
    expected_size_matches = expected.size == CAPTURE_SIZE
    if not size_matches or not expected_size_matches:
        return {
            "ok": False,
            "actual_path": str(actual_path),
            "expected_path": str(expected_path),
            "size": [width, height],
            "required_size": [required_width, required_height],
            "size_matches": size_matches,
            "expected_size_matches": expected_size_matches,
            "positional_match": False,
            "pairwise_distinct": False,
            "frames": [],
            "thresholds": {
                "rgb_channel_abs_error_max": RGB_ABS_ERROR_MAX,
                "alpha_exact": EXPECTED_ALPHA,
                "interior_inset_px": inset,
                "rgb_mae_role": "diagnostic_only",
                "expected_color_space": (
                    "single-transfer FWidgetRenderer sRGB render-target bytes"
                ),
            },
        }

    rows: list[dict[str, Any]] = []
    for frame, _expected_color in enumerate(FRAME_COLORS):
        column = frame % 2
        row = frame // 2
        left = column * width // 2 + inset
        top = row * height // 2 + inset
        right = (column + 1) * width // 2 - inset
        bottom = (row + 1) * height // 2 - inset
        actual_crop = actual.crop((left, top, right, bottom))
        expected_crop = expected.crop((left, top, right, bottom))
        actual_bytes = actual_crop.tobytes()
        expected_bytes = expected_crop.tobytes()
        pixel_count = len(actual_bytes) // 4
        channel_error_sums = [0, 0, 0]
        channel_error_max = [0, 0, 0]
        rgb_error_pixel_count = 0
        alpha_error_pixel_count = 0
        for offset in range(0, len(actual_bytes), 4):
            errors = [
                abs(
                    actual_bytes[offset + channel]
                    - expected_bytes[offset + channel]
                )
                for channel in range(3)
            ]
            for channel, error in enumerate(errors):
                channel_error_sums[channel] += error
                channel_error_max[channel] = max(
                    channel_error_max[channel], error
                )
            if any(error > RGB_ABS_ERROR_MAX for error in errors):
                rgb_error_pixel_count += 1
            if actual_bytes[offset + 3] != EXPECTED_ALPHA:
                alpha_error_pixel_count += 1

        actual_mean = ImageStat.Stat(actual_crop).mean
        expected_mean = ImageStat.Stat(expected_crop).mean
        rgb_mae = (
            sum(channel_error_sums) / (pixel_count * 3.0)
            if pixel_count
            else float("inf")
        )
        signature = [int(round(actual_mean[channel])) for channel in range(3)]
        pixel_contract_ok = (
            pixel_count > 0
            and rgb_error_pixel_count == 0
            and alpha_error_pixel_count == 0
        )
        rows.append(
            {
                "frame": frame,
                "box": [left, top, right, bottom],
                "actual_mean_rgba": [float(value) for value in actual_mean],
                "expected_mean_rgba": [float(value) for value in expected_mean],
                "rgb_mae": float(rgb_mae),
                "rgb_channel_abs_error_max": channel_error_max,
                "rgb_error_pixel_count": rgb_error_pixel_count,
                "alpha_error_pixel_count": alpha_error_pixel_count,
                "interior_pixel_count": pixel_count,
                "cell_signature_rgb": signature,
                "pixel_contract_ok": pixel_contract_ok,
                "ok": pixel_contract_ok,
            }
        )
    signatures = {
        tuple(row["cell_signature_rgb"])
        for row in rows
    }
    positional_match = len(rows) == 4 and all(
        row["pixel_contract_ok"] for row in rows
    )
    pairwise_distinct = len(signatures) == 4
    return {
        "ok": positional_match and pairwise_distinct,
        "actual_path": str(actual_path),
        "expected_path": str(expected_path),
        "size": [width, height],
        "required_size": list(CAPTURE_SIZE),
        "size_matches": size_matches,
        "expected_size_matches": expected_size_matches,
        "positional_match": positional_match,
        "pairwise_distinct": pairwise_distinct,
        "frames": rows,
        "thresholds": {
            "rgb_channel_abs_error_max": RGB_ABS_ERROR_MAX,
            "alpha_exact": EXPECTED_ALPHA,
            "interior_inset_px": inset,
            "rgb_mae_role": "diagnostic_only",
            "expected_color_space": (
                "single-transfer FWidgetRenderer sRGB render-target bytes"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    atlas_path = _write_atlas(workspace / "fixture" / "atlas_2x2.png")
    expected_path = _write_expected_grid(workspace / "expected_frames.png")
    document = _flipbook_document(atlas_path)
    document_path = workspace / "tiger_umg_flipbook_document.json"
    document_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    project = _ensure_project(workspace)
    generation = run_unreal_umg_generation(
        project,
        document_path,
        destination_root="/Game/TigerStudio/GeneratedM4A",
        timeout_seconds=args.timeout,
    )
    asset_path = str(generation.get("generated_asset_path") or "")
    material_paths = [
        str(path)
        for path in generation.get("generated_material_paths", [])
        if str(path)
    ]
    texture_paths = [
        str(path)
        for path in generation.get("imported_asset_paths", [])
        if str(path)
    ]
    expected_widgets = {f"Frame{index}": "Image" for index in range(4)}
    reopened = (
        _reopen_generated_asset(
            project,
            asset_path,
            material_paths=material_paths,
            material_widget_names=list(expected_widgets),
            expected_widget_classes=expected_widgets,
            timeout_seconds=args.timeout,
        )
        if generation.get("ok")
        and asset_path
        and len(material_paths) == 4
        else {"ok": False, "errors": ["generation_failed_before_reopen"]}
    )
    reopened_materials = list(reopened.get("materials") or [])
    if reopened_materials:
        for material in reopened_materials:
            material["expected_expression_count"] = 12
            material["ok"] = bool(material.get("ok")) and len(
                material.get("expression_classes") or []
            ) == 12
        reopened["ok"] = bool(reopened.get("ok")) and (
            len(reopened_materials) == 4
            and all(material["ok"] for material in reopened_materials)
        )
    inspection = (
        _inspect_materials(
            project,
            material_paths,
            texture_paths[0],
            timeout_seconds=args.timeout,
        )
        if reopened.get("ok") and len(texture_paths) == 1
        else {"ok": False, "errors": ["reopen_failed_before_graph_inspection"]}
    )
    actual_path = workspace / "flipbook_unreal.png"
    rendering = (
        _render_flipbook_asset(
            project,
            asset_path,
            actual_path,
            width=256,
            height=256,
            timeout_seconds=args.timeout,
        )
        if inspection.get("ok")
        else {"ok": False, "message": "inspection_failed_before_render"}
    )
    comparison = (
        _compare_frame_grid(actual_path, expected_path)
        if rendering.get("ok") and actual_path.is_file()
        else {"ok": False, "frames": []}
    )
    report = {
        "schema": "tigerstudio.painter.ui.unreal_umg_flipbook_qa.v1",
        "ok": bool(generation.get("ok"))
        and int(generation.get("generated_widget_count") or 0) == 4
        and len(material_paths) == 4
        and len(texture_paths) == 1
        and bool(reopened.get("ok"))
        and bool(inspection.get("ok"))
        and bool(rendering.get("ok"))
        and bool(comparison.get("ok")),
        "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
        "project_path": str(project),
        "fixture": {
            "atlas_path": str(atlas_path),
            "document_path": str(document_path),
            "expected_path": str(expected_path),
            "frame_colors": [list(color) for color in FRAME_COLORS],
        },
        "generation": generation,
        "reopen": reopened,
        "material_graph": inspection,
        "render": rendering,
        "pixel_comparison": comparison,
        "render_contract": RENDER_CONTRACT,
        "environment": {
            "platform": sys.platform,
            "python": sys.version,
        },
    }
    report_path = workspace / "qa_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
