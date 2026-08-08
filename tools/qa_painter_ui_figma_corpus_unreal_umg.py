"""Gate the release Figma corpus and run real UE QA only for clean cases.

The full selected manifest is imported and every artboard is preflighted again
on each run.  Cases with any UMG blocker are recorded as skipped; they are not
silently dropped and are never represented as Unreal evidence.  Clean cases
use the same generation, reopen, FWidgetRenderer, and visible editor capture
helpers as ``qa_painter_ui_unreal_umg.py``.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_ui_figma import import_figma_payload
from app.painter_ui_umg_adapter import (
    PainterUMGConversionSession,
    generate_painter_umg,
)
from app.unreal_umg_workflow import DEFAULT_UNREAL_ENGINE_ROOT
from tools.fetch_painter_ui_figma_document_corpus import (
    DEFAULT_OUTPUT_ROOT,
    FigmaCorpusError,
    _safe_relative_path,
)
from tools.qa_painter_ui_figma_document_corpus import (
    _load_case_source,
    _load_manifest,
    _load_selector_case_source,
    _verify_case_artifact,
)
from tools.qa_painter_ui_unreal_umg import (
    _capture_generated_asset,
    _ensure_project,
    _render_generated_asset,
    _reopen_generated_asset,
    _reopen_owner_asset_paths,
    _umg_document_expectations,
)


FIGMA_CORPUS_UE_QA_SCHEMA = (
    "tigerstudio.painter.ui.figma_corpus_unreal_umg_qa.v1"
)
DEFAULT_MANIFEST = (
    ROOT
    / "qa_corpus"
    / "painter_ui_figma_documents"
    / "release_manifest.json"
)
DEFAULT_WORKSPACE = (
    ROOT
    / "debugCapture"
    / "painter_ui_designer"
    / "figma_corpus_unreal_umg"
)


UnrealCaseRunner = Callable[
    [Mapping[str, Any], Mapping[str, Any], Path, int, bool],
    Mapping[str, Any],
]


def _safe_name(value: object) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in str(value or "")
    ).strip("_")
    return cleaned or "case"


def load_release_cases(
    manifest_path: str | Path = DEFAULT_MANIFEST,
    *,
    case_ids: Sequence[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = dict(_load_manifest(Path(manifest_path).expanduser().resolve()))
    rows = [dict(row) for row in manifest.get("cases") or []]
    requested = [str(value) for value in (case_ids or [])]
    if requested:
        by_id = {str(row.get("id") or ""): row for row in rows}
        unknown = [case_id for case_id in requested if case_id not in by_id]
        if unknown:
            raise FigmaCorpusError(
                "Unknown corpus case ids: " + ", ".join(unknown)
            )
        seen: set[str] = set()
        selected: list[dict[str, Any]] = []
        for case_id in requested:
            if case_id not in seen:
                selected.append(dict(by_id[case_id]))
                seen.add(case_id)
        rows = selected
    return manifest, rows


def _load_imported_case(
    item: Mapping[str, Any],
    assets_root: Path,
    selector_cache: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    artifact = item.get("artifact")
    artifact = artifact if isinstance(artifact, Mapping) else {}
    source_path = (
        assets_root / _safe_relative_path(str(artifact["relative_path"]))
    ).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Figma corpus artifact missing: {source_path}")
    selector = item.get("selector")
    if isinstance(selector, Mapping):
        payload, image_paths, source_details, selector_load = (
            _load_selector_case_source(
                source_path,
                artifact,
                selector,
                selector_cache,
            )
        )
        artifact_evidence = dict(selector_load.get("artifact") or {})
        selector_evidence = dict(selector_load.get("selector") or {})
    else:
        artifact_evidence = _verify_case_artifact(source_path, artifact)
        payload, image_paths, source_details = _load_case_source(source_path)
        selector_evidence = {}
    document, import_report = import_figma_payload(
        payload,
        source=str(source_path),
        image_paths=image_paths,
    )
    return {
        "document": document,
        "import_report": import_report,
        "source_path": str(source_path),
        "source_details": source_details,
        "artifact": artifact_evidence,
        "selector": selector_evidence,
    }


def _preflight_document(document: Mapping[str, Any]) -> dict[str, Any]:
    session = PainterUMGConversionSession(document)
    artboards: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    blocker_reasons: Counter[str] = Counter()
    errors: list[str] = []
    source_artboards = [
        row
        for row in document.get("artboards", [])
        if isinstance(row, Mapping)
    ]
    for artboard in source_artboards:
        artboard_id = str(artboard.get("id") or "")
        try:
            result = session.preflight(artboard_id=artboard_id)
            blockers = list(result.get("blockers") or [])
            artboard_errors = [str(row) for row in result.get("errors") or []]
            counts.update(result.get("counts") or {})
            reasons: Counter[str] = Counter()
            for blocker in blockers:
                if isinstance(blocker, Mapping):
                    values = blocker.get("reasons") or ["blocked"]
                else:
                    values = [str(blocker)]
                reasons.update(str(reason) for reason in values)
            blocker_reasons.update(reasons)
            errors.extend(
                f"{artboard_id}:{message}" for message in artboard_errors
            )
            artboards.append(
                {
                    "id": artboard_id,
                    "name": str(artboard.get("name") or artboard_id),
                    "ok": bool(result.get("ok"))
                    and not blockers
                    and not artboard_errors,
                    "counts": dict(result.get("counts") or {}),
                    "blocker_count": len(blockers),
                    "blocker_reasons": dict(sorted(reasons.items())),
                    "blockers": blockers,
                    "errors": artboard_errors,
                }
            )
        except Exception as exc:
            message = f"{artboard_id}:{type(exc).__name__}:{exc}"
            errors.append(message)
            artboards.append(
                {
                    "id": artboard_id,
                    "name": str(artboard.get("name") or artboard_id),
                    "ok": False,
                    "counts": {},
                    "blocker_count": 0,
                    "blocker_reasons": {},
                    "blockers": [],
                    "errors": [message],
                }
            )
    clean = bool(artboards) and all(row["ok"] for row in artboards)
    return {
        "clean": clean,
        "artboard_count": len(artboards),
        "clean_artboard_count": sum(row["ok"] for row in artboards),
        "counts": dict(sorted(counts.items())),
        "blocker_reasons": dict(sorted(blocker_reasons.items())),
        "errors": errors,
        "artboards": artboards,
    }


def _class_name(class_path: object) -> str:
    value = str(class_path or "").strip().strip("'\"")
    return value.rsplit(".", 1)[-1].rsplit("/", 1)[-1] if value else ""


def _component_path_map(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(path) for key, path in value.items()}


def _effective_widget_classes(
    exported: Mapping[str, Any],
    expectations: Mapping[str, Any],
    generation: Mapping[str, Any],
) -> dict[str, str]:
    expected = dict(expectations.get("expected_widget_classes") or {})
    class_paths = _component_path_map(
        generation.get("generated_component_class_paths")
    )
    for instance in exported.get("ComponentInstances") or []:
        if not isinstance(instance, Mapping):
            continue
        layer_id = str(instance.get("LayerId") or "")
        component_id = str(instance.get("ComponentId") or "")
        class_name = _class_name(class_paths.get(component_id))
        if layer_id and class_name:
            expected[layer_id] = class_name
    return expected


def _generation_contract(
    generation: Mapping[str, Any],
    exported: Mapping[str, Any],
    expectations: Mapping[str, Any],
) -> dict[str, Any]:
    generated_classes = generation.get("generated_widget_classes")
    generated_classes = (
        dict(generated_classes)
        if isinstance(generated_classes, Mapping)
        else {}
    )
    expected_classes = _effective_widget_classes(
        exported,
        expectations,
        generation,
    )
    components = [
        row
        for row in exported.get("Components") or []
        if isinstance(row, Mapping)
    ]
    component_ids = {str(row.get("Id") or "") for row in components}
    component_assets = _component_path_map(
        generation.get("generated_component_asset_paths")
    )
    component_classes = _component_path_map(
        generation.get("generated_component_class_paths")
    )
    material_paths = [
        str(path)
        for path in generation.get("generated_material_paths") or []
        if str(path)
    ]
    texture_paths = [
        str(path)
        for path in generation.get("imported_asset_paths") or []
        if str(path)
    ]
    checks = {
        "generation_ok": bool(generation.get("ok")),
        "asset_loaded": bool(generation.get("generated_asset_loaded")),
        "asset_class": generation.get("generated_asset_class")
        == "WidgetBlueprint",
        "widget_count": int(generation.get("generated_widget_count") or 0)
        == int(expectations.get("expected_widget_count") or 0),
        "material_count": len(material_paths)
        == int(expectations.get("expected_material_count") or 0),
        "texture_count": len(texture_paths)
        == int(expectations.get("expected_texture_count") or 0),
        "component_count": int(
            generation.get("generated_component_count") or 0
        )
        == len(component_ids),
        "component_asset_ids": set(component_assets) == component_ids,
        "component_class_ids": set(component_classes) == component_ids,
        "widget_classes": all(
            generated_classes.get(name) == class_name
            for name, class_name in expected_classes.items()
        ),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "expected_widget_classes": expected_classes,
        "actual_widget_classes": generated_classes,
        "expected_component_ids": sorted(component_ids),
        "component_asset_paths": component_assets,
        "component_class_paths": component_classes,
        "generated_material_paths": material_paths,
        "imported_texture_paths": texture_paths,
    }


def _run_unreal_case(
    item: Mapping[str, Any],
    document: Mapping[str, Any],
    sample_dir: Path,
    timeout_seconds: int,
    capture_ui: bool,
) -> dict[str, Any]:
    sample_dir.mkdir(parents=True, exist_ok=True)
    document_path = sample_dir / "imported_painter_document.json"
    document_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    exported, expectations = _umg_document_expectations(
        document,
        layout_expectations=[],
    )
    exported_path = sample_dir / "tiger_umg_document.json"
    exported_path.write_text(
        json.dumps(exported, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    project = _ensure_project(sample_dir)
    generation = generate_painter_umg(
        document,
        project_path=project,
        output_dir=sample_dir / "packet",
        destination_root="/Game/TigerStudio/FigmaCorpusQA",
        timeout_seconds=timeout_seconds,
    )
    generation_contract = _generation_contract(
        generation,
        exported,
        expectations,
    )
    asset_path = str(generation.get("generated_asset_path") or "")
    material_rows = list(expectations.get("material_layers") or [])
    image_rows = list(expectations.get("image_fill_layers") or [])
    component_asset_paths = generation_contract["component_asset_paths"]
    reopened = (
        _reopen_generated_asset(
            project,
            asset_path,
            material_paths=generation_contract["generated_material_paths"],
            material_widget_names=[str(row["id"]) for row in material_rows],
            material_stop_counts=[
                (
                    int(row.get("stop_count") or 0)
                    if str(row.get("generator") or "")
                    == "tiger_ui_gradient_custom_hlsl_v1"
                    else 0
                )
                for row in material_rows
            ],
            material_owner_asset_paths=_reopen_owner_asset_paths(
                asset_path,
                component_asset_paths,
                material_rows,
            ),
            texture_paths=generation_contract["imported_texture_paths"],
            texture_widget_names=[str(row["id"]) for row in image_rows],
            texture_owner_asset_paths=_reopen_owner_asset_paths(
                asset_path,
                component_asset_paths,
                image_rows,
            ),
            expected_widget_classes=generation_contract[
                "expected_widget_classes"
            ],
            timeout_seconds=timeout_seconds,
        )
        if generation_contract["ok"] and asset_path
        else {
            "ok": False,
            "reason": "generation_contract_failed_before_reopen",
        }
    )
    active_artboard_id = str(expectations.get("active_artboard_id") or "")
    active_artboard = next(
        (
            row
            for row in document.get("artboards") or []
            if str(row.get("id") or "") == active_artboard_id
        ),
        {},
    )
    width = max(1, round(float(active_artboard.get("width") or 1)))
    height = max(1, round(float(active_artboard.get("height") or 1)))
    renderer_path = sample_dir / "painter_umg_fwidget_renderer.png"
    rendered = (
        _render_generated_asset(
            project,
            asset_path,
            renderer_path,
            width=width,
            height=height,
            timeout_seconds=timeout_seconds,
        )
        if reopened.get("ok") and asset_path
        else {"ok": False, "reason": "reopen_failed_before_render"}
    )
    editor_path = sample_dir / "painter_umg_unreal_editor.png"
    editor_capture = (
        _capture_generated_asset(
            project,
            asset_path,
            editor_path,
            material_asset_names=[
                path.rsplit("/", 1)[-1].split(".", 1)[0]
                for path in generation_contract["generated_material_paths"]
            ],
            timeout_seconds=min(timeout_seconds, 120),
        )
        if capture_ui and reopened.get("ok") and asset_path
        else {
            "ok": False,
            "status": "not_run",
            "reason": (
                "capture_not_requested"
                if not capture_ui
                else "reopen_failed_before_capture"
            ),
        }
    )
    ok = (
        generation_contract["ok"]
        and bool(reopened.get("ok"))
        and bool(rendered.get("ok"))
        and (not capture_ui or bool(editor_capture.get("ok")))
    )
    result = {
        "ok": ok,
        "case_id": str(item.get("id") or ""),
        "project_path": str(project),
        "active_artboard_id": active_artboard_id,
        "render_size": [width, height],
        "paths": {
            "painter_document": str(document_path),
            "umg_document": str(exported_path),
            "renderer": str(renderer_path),
            "editor_screenshot": str(editor_path),
        },
        "expectations": expectations,
        "generation": generation,
        "generation_contract": generation_contract,
        "reopen": reopened,
        "renderer": rendered,
        "editor_capture": editor_capture,
    }
    result_path = sample_dir / "unreal_qa_report.json"
    result["paths"]["report"] = str(result_path)
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def _load_optional_report(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    resolved = Path(path).expanduser().resolve()
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Painter corpus report root must be an object")
    value["_report_path"] = str(resolved)
    return value


def _rebased_painter_path(
    raw_path: object,
    *,
    renders_root: Path | None,
    case_id: str,
) -> Path | None:
    source = Path(str(raw_path or ""))
    candidates: list[Path] = []
    if str(raw_path or ""):
        candidates.append(source)
    if renders_root is not None:
        parts = list(source.parts)
        lowered = [part.casefold() for part in parts]
        if "renders" in lowered:
            index = len(lowered) - 1 - lowered[::-1].index("renders")
            candidates.append(renders_root.joinpath(*parts[index + 1 :]))
        if source.name:
            candidates.extend(
                [
                    renders_root / source.name,
                    renders_root / f"{case_id}.artboards" / source.name,
                ]
            )
        candidates.append(renders_root / f"{case_id}.png")
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return candidates[0] if candidates else None


def _painter_evidence(
    case_id: str,
    active_artboard_id: str,
    painter_case: Mapping[str, Any] | None,
    *,
    report_path: str,
    renders_root: Path | None,
) -> dict[str, Any]:
    if not isinstance(painter_case, Mapping):
        return {
            "status": "not_provided",
            "path": "",
            "exists": False,
            "is_unreal_evidence": False,
        }
    render = painter_case.get("render_smoke")
    render = dict(render) if isinstance(render, Mapping) else {}
    selected: Mapping[str, Any] | None = None
    kind = ""
    for row in render.get("artboards") or []:
        if (
            isinstance(row, Mapping)
            and str(row.get("artboard_id") or "") == active_artboard_id
            and row.get("png_path")
        ):
            selected = row
            kind = "active_artboard"
            break
    if selected is None and render.get("png_path"):
        selected = render
        kind = "whole_document"
    raw_path = selected.get("png_path") if selected else ""
    path = _rebased_painter_path(
        raw_path,
        renders_root=renders_root,
        case_id=case_id,
    )
    exists = path is not None and path.is_file()
    return {
        "status": "available" if exists else "missing",
        "path": str(path) if path is not None else "",
        "exists": exists,
        "render_kind": kind,
        "render_passed": bool(selected and selected.get("passed")),
        "source_report": report_path,
        "is_unreal_evidence": False,
        "label": "Painter render (UMG blocked; not Unreal)",
    }


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    for path in (
        Path(
            "C:/Windows/Fonts/seguisb.ttf"
            if bold
            else "C:/Windows/Fonts/segoeui.ttf"
        ),
        Path(
            "C:/Windows/Fonts/arialbd.ttf"
            if bold
            else "C:/Windows/Fonts/arial.ttf"
        ),
    ):
        try:
            if path.is_file():
                return ImageFont.truetype(str(path), size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def _image_readable(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except Exception:
        return False


def write_contact_sheet(
    cases: Sequence[Mapping[str, Any]],
    output_path: Path,
) -> dict[str, Any]:
    if not cases:
        return {"ok": False, "reason": "no_cases", "path": str(output_path)}
    columns = 4
    cell_width, cell_height = 310, 230
    image_width, image_height = 282, 154
    rows = (len(cases) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (columns * cell_width, rows * cell_height),
        (7, 11, 19),
    )
    draw = ImageDraw.Draw(sheet)
    title_font = _font(13, bold=True)
    small_font = _font(10)
    unreal_cells = 0
    painter_cells = 0
    placeholders = 0
    for index, case in enumerate(cases):
        left = (index % columns) * cell_width + 8
        top = (index // columns) * cell_height + 8
        status = str(case.get("status") or "")
        if status in {"passed", "failed"}:
            unreal = case.get("unreal") or {}
            renderer = unreal.get("renderer") or {}
            path = Path(
                str(
                    renderer.get("output_path")
                    or (unreal.get("paths") or {}).get("renderer")
                    or ""
                )
            )
            evidence_label = "UNREAL · FWidgetRenderer"
            color = (48, 190, 122) if status == "passed" else (225, 94, 94)
            unreal_cells += 1
        elif status == "skipped_blocked":
            painter = case.get("painter_evidence") or {}
            path = Path(str(painter.get("path") or ""))
            evidence_label = "PAINTER · UMG BLOCKED"
            color = (226, 153, 62)
            painter_cells += 1
        else:
            painter = case.get("painter_evidence") or {}
            path = Path(str(painter.get("path") or ""))
            evidence_label = "PAINTER · PREFLIGHT ERROR"
            color = (225, 94, 94)
            painter_cells += 1
        draw.rounded_rectangle(
            (left, top, left + cell_width - 16, top + cell_height - 16),
            radius=9,
            fill=(18, 26, 39),
            outline=color,
            width=2,
        )
        image_box = (
            left + 6,
            top + 6,
            left + 6 + image_width,
            top + 6 + image_height,
        )
        if path.is_file() and _image_readable(path):
            with Image.open(path) as source:
                thumb = ImageOps.contain(
                    source.convert("RGB"),
                    (image_width, image_height),
                    Image.Resampling.LANCZOS,
                )
            sheet.paste(
                thumb,
                (
                    image_box[0] + (image_width - thumb.width) // 2,
                    image_box[1] + (image_height - thumb.height) // 2,
                ),
            )
        else:
            placeholders += 1
            draw.rectangle(image_box, fill=(34, 42, 55))
            draw.text(
                (image_box[0] + 12, image_box[1] + 66),
                "evidence unavailable",
                font=title_font,
                fill=(172, 182, 197),
            )
        case_id = str(case.get("id") or "")
        draw.text(
            (left + 8, top + image_height + 14),
            case_id[:42],
            font=title_font,
            fill=(238, 243, 249),
        )
        reasons = ", ".join(
            list((case.get("preflight") or {}).get("blocker_reasons") or {})[:2]
        )
        detail = evidence_label if status in {"passed", "failed"} else (
            evidence_label + (f" · {reasons}" if reasons else "")
        )
        draw.text(
            (left + 8, top + image_height + 38),
            detail[:58],
            font=small_font,
            fill=color,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG")
    return {
        "ok": output_path.is_file(),
        "path": str(output_path),
        "width": sheet.width,
        "height": sheet.height,
        "cell_count": len(cases),
        "unreal_fwidget_renderer_cells": unreal_cells,
        "painter_blocked_cells": painter_cells,
        "placeholder_count": placeholders,
        "painter_cells_are_not_unreal_evidence": True,
    }


def _relative(path: object, root: Path) -> str:
    candidate = Path(str(path or ""))
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def write_markdown_index(report: Mapping[str, Any], path: Path) -> None:
    root = path.parent
    summary = report.get("summary") or {}
    contact = report.get("contact_sheet") or {}
    lines = [
        "# Figma release corpus → Unreal UMG QA",
        "",
        f"- Result: **{'PASS' if report.get('ok') else 'CHECK'}**",
        f"- Selected: {summary.get('selected_cases', 0)} / manifest {summary.get('manifest_cases', 0)}",
        f"- UMG-clean and executed: {summary.get('clean_cases', 0)}",
        f"- UMG-blocked and skipped: {summary.get('blocked_cases', 0)}",
        f"- Unreal passed: {summary.get('unreal_passed', 0)}",
        f"- Unreal failed: {summary.get('unreal_failed', 0)}",
        f"- Contact sheet: [open]({_relative(contact.get('path'), root)})",
        "",
        "> Painter images on blocked rows are source-side previews only. They are explicitly not Unreal or UMG renders.",
        "",
        "| # | Case | Decision | Blocker reasons | UE stages | Evidence |",
        "|---:|---|---|---|---|---|",
    ]
    for index, case in enumerate(report.get("cases") or [], start=1):
        preflight = case.get("preflight") or {}
        blockers = ", ".join(
            f"{key}×{value}"
            for key, value in (preflight.get("blocker_reasons") or {}).items()
        ) or "—"
        status = str(case.get("status") or "")
        unreal = case.get("unreal") or {}
        stages = (
            "generation / reopen / renderer / editor"
            if status in {"passed", "failed"}
            else "not run"
        )
        if status in {"passed", "failed"}:
            evidence_path = (unreal.get("paths") or {}).get("renderer") or ""
            evidence = f"[Unreal FWidgetRenderer]({_relative(evidence_path, root)})"
            editor_path = (unreal.get("paths") or {}).get("editor_screenshot") or ""
            if Path(str(editor_path)).is_file():
                evidence += f" · [Editor]({_relative(editor_path, root)})"
        else:
            painter = case.get("painter_evidence") or {}
            if painter.get("exists"):
                evidence = (
                    f"[Painter preview]({_relative(painter.get('path'), root)}) "
                    "(not Unreal)"
                )
            else:
                evidence = "Painter preview unavailable (not Unreal)"
        title = str(case.get("title") or "").replace("|", "\\|")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    f"`{case.get('id')}`<br>{title}",
                    status,
                    blockers.replace("|", "\\|"),
                    stages,
                    evidence,
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_figma_corpus_unreal_umg_qa(
    manifest_path: str | Path,
    workspace: str | Path,
    *,
    assets_root: str | Path | None = None,
    case_ids: Sequence[str] | None = None,
    timeout_seconds: int = 300,
    capture_ui: bool = True,
    painter_report_path: str | Path | None = None,
    painter_renders_root: str | Path | None = None,
    unreal_runner: UnrealCaseRunner | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    manifest, selected = load_release_cases(
        manifest_path,
        case_ids=case_ids,
    )
    manifest_root = Path(str(manifest.get("storage_root") or DEFAULT_OUTPUT_ROOT))
    if not manifest_root.is_absolute():
        manifest_root = ROOT / manifest_root
    resolved_assets = (
        Path(assets_root).expanduser().resolve()
        if assets_root is not None
        else manifest_root.resolve()
    )
    painter_report = _load_optional_report(painter_report_path)
    painter_by_id = {
        str(row.get("id") or ""): row
        for row in painter_report.get("cases") or []
        if isinstance(row, Mapping)
    }
    renders_root = (
        Path(painter_renders_root).expanduser().resolve()
        if painter_renders_root is not None
        else None
    )
    execute_unreal = unreal_runner or _run_unreal_case
    selector_cache: dict[tuple[str, str], dict[str, Any]] = {}
    case_rows: list[dict[str, Any]] = []
    started = time.monotonic()
    for index, item in enumerate(selected, start=1):
        case_id = str(item.get("id") or "")
        case_dir = workspace / "cases" / f"{index:03d}_{_safe_name(case_id)}"
        case_dir.mkdir(parents=True, exist_ok=True)
        row: dict[str, Any] = {
            "id": case_id,
            "title": str(item.get("title") or case_id),
            "format": str(item.get("format") or ""),
            "case_dir": str(case_dir),
            "status": "preflight_error",
            "ok": False,
        }
        try:
            loaded = _load_imported_case(item, resolved_assets, selector_cache)
            document = loaded["document"]
            preflight = _preflight_document(document)
            row.update(
                {
                    "source_path": loaded["source_path"],
                    "source_details": loaded["source_details"],
                    "artifact": loaded["artifact"],
                    "selector": loaded["selector"],
                    "import": loaded["import_report"],
                    "active_artboard_id": str(
                        document.get("active_artboard_id") or ""
                    ),
                    "preflight": preflight,
                }
            )
            row["painter_evidence"] = _painter_evidence(
                case_id,
                row["active_artboard_id"],
                painter_by_id.get(case_id),
                report_path=str(painter_report.get("_report_path") or ""),
                renders_root=renders_root,
            )
            if preflight["clean"]:
                try:
                    unreal = dict(
                        execute_unreal(
                            item,
                            document,
                            case_dir,
                            max(30, int(timeout_seconds)),
                            capture_ui,
                        )
                    )
                except Exception as exc:
                    unreal = {
                        "ok": False,
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "reason": "unreal_case_execution_failed",
                    }
                row["unreal"] = unreal
                row["status"] = "passed" if unreal.get("ok") else "failed"
                row["ok"] = bool(unreal.get("ok"))
            else:
                row["status"] = "skipped_blocked"
                row["ok"] = True
                row["unreal"] = {
                    "ok": False,
                    "status": "not_run",
                    "reason": "all_artboards_must_be_umg_clean",
                }
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            row.setdefault(
                "preflight",
                {
                    "clean": False,
                    "artboard_count": 0,
                    "clean_artboard_count": 0,
                    "counts": {},
                    "blocker_reasons": {},
                    "errors": [row["error"]],
                    "artboards": [],
                },
            )
            row["painter_evidence"] = _painter_evidence(
                case_id,
                "",
                painter_by_id.get(case_id),
                report_path=str(painter_report.get("_report_path") or ""),
                renders_root=renders_root,
            )
            row["unreal"] = {
                "ok": False,
                "status": "not_run",
                "reason": "case_load_or_preflight_failed",
            }
        (case_dir / "case_report.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        case_rows.append(row)

    contact_path = workspace / "figma_corpus_umg_contact_sheet.png"
    contact_sheet = write_contact_sheet(case_rows, contact_path)
    status_counts = Counter(str(row.get("status") or "") for row in case_rows)
    blocker_reason_totals: Counter[str] = Counter()
    for row in case_rows:
        blocker_reason_totals.update(
            {
                str(reason): int(count)
                for reason, count in (
                    (row.get("preflight") or {}).get("blocker_reasons") or {}
                ).items()
            }
        )
    clean_case_ids = [
        str(row["id"])
        for row in case_rows
        if bool((row.get("preflight") or {}).get("clean"))
    ]
    report_path = workspace / "report.json"
    index_path = workspace / "index.md"
    error_count = status_counts["preflight_error"]
    unreal_failed = status_counts["failed"]
    report = {
        "schema": FIGMA_CORPUS_UE_QA_SCHEMA,
        "ok": error_count == 0
        and unreal_failed == 0
        and bool(contact_sheet.get("ok")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(Path(manifest_path).expanduser().resolve()),
        "assets_root": str(resolved_assets),
        "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
        "capture_ui_requested": capture_ui,
        "painter_report": str(painter_report.get("_report_path") or ""),
        "painter_renders_root": str(renders_root or ""),
        "summary": {
            "manifest_cases": len(manifest.get("cases") or []),
            "selected_cases": len(case_rows),
            "clean_cases": len(clean_case_ids),
            "blocked_cases": status_counts["skipped_blocked"],
            "preflight_errors": error_count,
            "unreal_executed": status_counts["passed"] + unreal_failed,
            "unreal_passed": status_counts["passed"],
            "unreal_failed": unreal_failed,
            "blocker_reason_totals": dict(
                sorted(blocker_reason_totals.items())
            ),
            "duration_seconds": round(time.monotonic() - started, 3),
        },
        "clean_case_ids": clean_case_ids,
        "paths": {
            "report": str(report_path),
            "index": str(index_path),
            "contact_sheet": str(contact_path),
            "cases": str(workspace / "cases"),
        },
        "contact_sheet": contact_sheet,
        "cases": case_rows,
    }
    write_markdown_index(report, index_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight the release Figma corpus and run real UE QA only for "
            "cases whose every artboard is UMG-clean."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--assets-root", type=Path, default=None)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--painter-report", type=Path, default=None)
    parser.add_argument("--painter-renders-root", type=Path, default=None)
    capture = parser.add_mutually_exclusive_group()
    capture.add_argument(
        "--capture-ui",
        action="store_true",
        dest="capture_ui",
        help="Capture each clean Widget Blueprint editor (default).",
    )
    capture.add_argument(
        "--no-capture-ui",
        action="store_false",
        dest="capture_ui",
        help="Skip visible Editor screenshots; FWidgetRenderer remains required.",
    )
    parser.set_defaults(capture_ui=True)
    return parser


def main() -> int:
    args = _argument_parser().parse_args()
    try:
        report = run_figma_corpus_unreal_umg_qa(
            args.manifest,
            args.workspace,
            assets_root=args.assets_root,
            case_ids=args.case,
            timeout_seconds=args.timeout,
            capture_ui=bool(args.capture_ui),
            painter_report_path=args.painter_report,
            painter_renders_root=args.painter_renders_root,
        )
    except (FigmaCorpusError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "report": report["paths"]["report"],
                "index": report["paths"]["index"],
                "contact_sheet": report["paths"]["contact_sheet"],
                "clean_case_ids": report["clean_case_ids"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
