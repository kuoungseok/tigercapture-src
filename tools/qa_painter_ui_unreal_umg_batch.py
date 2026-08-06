"""Sequential real-UE QA for every built-in Painter UI template.

Each case is delegated to ``qa_painter_ui_unreal_umg.py`` so the batch uses
the same packaging, generation, reopen, FWidgetRenderer, and optional visible
Unreal Editor capture path as the focused QA.  Unreal runs are deliberately
sequential: sharing a project/editor process across cases makes failures much
harder to attribute and can introduce asset-editor capture races.
"""
from __future__ import annotations

import argparse
import inspect
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_ui_templates import instantiate_ui_template, list_ui_templates
from app.unreal_umg_workflow import DEFAULT_UNREAL_ENGINE_ROOT


BATCH_QA_SCHEMA = "tigerstudio.painter.ui.unreal_umg_batch_qa.v1"
DEFAULT_WORKSPACE = (
    ROOT
    / "debugCapture"
    / "painter_ui_designer"
    / "unreal_umg_builtin_batch"
)
SINGLE_QA_TOOL = ROOT / "tools" / "qa_painter_ui_unreal_umg.py"


SampleRunner = Callable[..., Mapping[str, Any]]


def _safe_directory_name(value: object) -> str:
    result = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in str(value or "")
    ).strip("_")
    return result or "sample"


def discover_builtin_samples(
    template_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Return built-ins in their user-facing catalog order."""

    catalog = [dict(row) for row in list_ui_templates()]
    if template_ids is None:
        return catalog
    requested = [str(value) for value in template_ids]
    by_id = {str(row.get("id") or ""): row for row in catalog}
    unknown = [template_id for template_id in requested if template_id not in by_id]
    if unknown:
        raise ValueError(
            "Unknown Painter UI built-in template(s): " + ", ".join(unknown)
        )
    # CLI order is useful for focused reruns; duplicate ids are intentionally
    # collapsed because they target the same deterministic output directory.
    seen: set[str] = set()
    selected: list[dict[str, Any]] = []
    for template_id in requested:
        if template_id not in seen:
            selected.append(dict(by_id[template_id]))
            seen.add(template_id)
    return selected


def discover_builtin_sample_targets(
    template_ids: Sequence[str] | None = None,
    *,
    all_artboards: bool = False,
) -> list[dict[str, Any]]:
    """Expand templates into stable template/artboard QA targets."""

    targets: list[dict[str, Any]] = []
    for template_index, template in enumerate(
        discover_builtin_samples(template_ids),
        start=1,
    ):
        document, _report = instantiate_ui_template(str(template["id"]))
        active_id = str(document.get("active_artboard_id") or "")
        artboards = list(document.get("artboards") or [])
        selected = (
            artboards
            if all_artboards
            else [
                row
                for row in artboards
                if str(row.get("id") or "") == active_id
            ]
        )
        if not selected:
            raise ValueError(
                f"Painter UI built-in has no active artboard: {template['id']}"
            )
        index_by_id = {
            str(row.get("id") or ""): index
            for index, row in enumerate(artboards)
        }
        for artboard in selected:
            artboard_id = str(artboard.get("id") or "")
            targets.append(
                {
                    "template": dict(template),
                    "template_index": template_index,
                    "artboard": {
                        "id": artboard_id,
                        "name": str(artboard.get("name") or artboard_id),
                        "index": int(index_by_id[artboard_id]),
                        "width": float(artboard.get("width") or 0.0),
                        "height": float(artboard.get("height") or 0.0),
                        "is_default": artboard_id == active_id,
                    },
                }
            )
    return targets


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "ok": False,
            "schema": "invalid_report",
            "errors": [f"report_read_failed:{exc}"],
        }
    if not isinstance(value, dict):
        return {
            "ok": False,
            "schema": "invalid_report",
            "errors": ["report_root_not_object"],
        }
    return value


def _execute_sample(
    template: Mapping[str, Any],
    sample_dir: Path,
    timeout_seconds: int,
    capture_ui: bool,
    artboard_id: str = "",
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(SINGLE_QA_TOOL),
        "--workspace",
        str(sample_dir),
        "--timeout",
        str(max(30, int(timeout_seconds))),
        "--template",
        str(template.get("id") or ""),
    ]
    if artboard_id:
        command.extend(["--artboard-id", str(artboard_id)])
    if capture_ui:
        command.append("--capture-ui")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=max(300, int(timeout_seconds) * 5),
            check=False,
        )
        returncode = int(completed.returncode)
        stdout_tail = completed.stdout[-8000:]
        stderr_tail = completed.stderr[-8000:]
        execution_error = ""
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout_tail = str(exc.stdout or "")[-8000:]
        stderr_tail = str(exc.stderr or "")[-8000:]
        execution_error = "batch_sample_timeout"
    report_path = sample_dir / "qa_report.json"
    report = (
        _read_json(report_path)
        if report_path.is_file()
        else {
            "ok": False,
            "schema": "missing_report",
            "errors": [execution_error or "single_qa_report_missing"],
        }
    )
    return {
        "returncode": returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "command": command,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "report_path": str(report_path),
        "report": report,
        "resumed": False,
    }


def _resume_sample(
    sample_dir: Path,
    *,
    template_id: str = "",
    artboard_id: str = "",
    capture_ui: bool = False,
) -> dict[str, Any] | None:
    report_path = sample_dir / "qa_report.json"
    renderer_path = sample_dir / "painter_umg_fwidget_renderer.png"
    if (
        not report_path.is_file()
        or not renderer_path.is_file()
        or not _image_readable(renderer_path)
    ):
        return None
    report = _read_json(report_path)
    if not bool(report.get("ok")):
        return None
    template_report = report.get("template")
    template_report = (
        dict(template_report) if isinstance(template_report, Mapping) else {}
    )
    if template_id and str(template_report.get("id") or "") != template_id:
        return None
    if (
        artboard_id
        and str(template_report.get("active_artboard_id") or "")
        != artboard_id
    ):
        return None
    if capture_ui:
        visual_capture = report.get("visual_capture")
        visual_capture = (
            dict(visual_capture)
            if isinstance(visual_capture, Mapping)
            else {}
        )
        editor_path = Path(str(visual_capture.get("path") or ""))
        if (
            not bool(visual_capture.get("ok"))
            or not editor_path.is_file()
            or not _image_readable(editor_path)
        ):
            return None
    return {
        "returncode": 0,
        "duration_seconds": 0.0,
        "command": [],
        "stdout_tail": "",
        "stderr_tail": "",
        "report_path": str(report_path),
        "report": report,
        "resumed": True,
    }


def _invoke_sample_runner(
    runner: SampleRunner,
    template: Mapping[str, Any],
    sample_dir: Path,
    timeout_seconds: int,
    capture_ui: bool,
    artboard_id: str,
) -> Mapping[str, Any]:
    """Pass artboard ids while retaining compatibility with four-arg runners."""

    try:
        signature = inspect.signature(runner)
        signature.bind(
            template,
            sample_dir,
            timeout_seconds,
            capture_ui,
            artboard_id,
        )
    except (TypeError, ValueError):
        return runner(template, sample_dir, timeout_seconds, capture_ui)
    return runner(
        template,
        sample_dir,
        timeout_seconds,
        capture_ui,
        artboard_id,
    )


def _artifact_path(
    value: object,
    *,
    sample_dir: Path,
    fallback_name: str,
) -> Path:
    path = Path(str(value or fallback_name)).expanduser()
    return path if path.is_absolute() else sample_dir / path


def _image_readable(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except Exception:
        return False


def _sample_result(
    template: Mapping[str, Any],
    artboard: Mapping[str, Any],
    sample_dir: Path,
    execution: Mapping[str, Any],
    *,
    capture_ui: bool,
) -> dict[str, Any]:
    raw_report = execution.get("report")
    report = dict(raw_report) if isinstance(raw_report, Mapping) else {}
    widget_render = report.get("widget_render")
    widget_render = (
        dict(widget_render) if isinstance(widget_render, Mapping) else {}
    )
    visual_capture = report.get("visual_capture")
    visual_capture = (
        dict(visual_capture) if isinstance(visual_capture, Mapping) else {}
    )
    summary = report.get("summary")
    summary = dict(summary) if isinstance(summary, Mapping) else {}
    renderer_path = _artifact_path(
        widget_render.get("output_path"),
        sample_dir=sample_dir,
        fallback_name="painter_umg_fwidget_renderer.png",
    )
    editor_path = _artifact_path(
        visual_capture.get("path"),
        sample_dir=sample_dir,
        fallback_name="painter_umg_unreal_editor.png",
    )
    # A file left by an earlier attempt is not evidence for the current run.
    # Count it only when the per-sample report explicitly says that stage
    # succeeded and names the artifact produced by that stage.
    renderer_exists = (
        bool(widget_render.get("ok"))
        and bool(widget_render.get("output_path"))
        and renderer_path.is_file()
        and _image_readable(renderer_path)
    )
    editor_exists = (
        bool(visual_capture.get("ok"))
        and bool(visual_capture.get("path"))
        and editor_path.is_file()
        and _image_readable(editor_path)
    )
    returncode = int(execution.get("returncode") or 0)
    sample_ok = bool(report.get("ok")) and returncode == 0 and renderer_exists
    if capture_ui:
        sample_ok = sample_ok and bool(visual_capture.get("ok")) and editor_exists
    artboard_id = str(artboard.get("id") or "")
    artboard_name = str(artboard.get("name") or artboard_id)
    return {
        "id": str(template.get("id") or ""),
        "screen_id": f"{template.get('id')}:{artboard_id}",
        "name": str(template.get("name") or ""),
        "category": str(template.get("category") or ""),
        "artboard_id": artboard_id,
        "artboard_name": artboard_name,
        "artboard": dict(artboard),
        "ok": sample_ok,
        "sample_dir": str(sample_dir),
        "report": str(execution.get("report_path") or sample_dir / "qa_report.json"),
        "renderer": {
            "ok": bool(widget_render.get("ok")) and renderer_exists,
            "path": str(renderer_path),
            "exists": renderer_exists,
            "width": int(widget_render.get("width") or 0),
            "height": int(widget_render.get("height") or 0),
            "pixel_evidence": widget_render.get("pixel_evidence") or {},
        },
        "editor_screenshot": {
            "requested": capture_ui,
            "ok": bool(visual_capture.get("ok")) and editor_exists,
            "path": str(editor_path),
            "exists": editor_exists,
            "status": str(visual_capture.get("status") or "not_run"),
            "reason": str(visual_capture.get("reason") or ""),
            "backend": str(visual_capture.get("backend") or ""),
        },
        "stages": {
            "generation": str(summary.get("generation_status") or "unknown"),
            "reopen": str(summary.get("reopen_status") or "unknown"),
            "renderer": str(
                summary.get("fwidget_renderer_status") or "unknown"
            ),
        },
        "counts": {
            "expected_layers": int(summary.get("expected_layer_count") or 0),
            "expected_widgets": int(summary.get("expected_widget_count") or 0),
            "generated_widgets": int(
                summary.get("actual_generated_widget_count") or 0
            ),
            "blocked_layers": len(summary.get("blocked_layers") or []),
        },
        "execution": {
            "returncode": returncode,
            "duration_seconds": float(
                execution.get("duration_seconds") or 0.0
            ),
            "resumed": bool(execution.get("resumed")),
            "command": list(execution.get("command") or []),
            "stdout_tail": str(execution.get("stdout_tail") or ""),
            "stderr_tail": str(execution.get("stderr_tail") or ""),
        },
    }


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return ImageFont.truetype(str(candidate), size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def write_contact_sheet(
    samples: Sequence[Mapping[str, Any]],
    output_path: Path,
    *,
    include_editor: bool,
) -> dict[str, Any]:
    """Write renderer/editor evidence, retaining placeholders for failures."""

    entries: list[tuple[Mapping[str, Any], str, Path, bool]] = []
    for sample in samples:
        renderer = sample.get("renderer") or {}
        entries.append(
            (
                sample,
                "FWidgetRenderer",
                Path(str(renderer.get("path") or "")),
                bool(renderer.get("ok")),
            )
        )
        if include_editor:
            editor = sample.get("editor_screenshot") or {}
            entries.append(
                (
                    sample,
                    "Unreal Editor",
                    Path(str(editor.get("path") or "")),
                    bool(editor.get("ok")),
                )
            )
    if not entries:
        return {"ok": False, "reason": "no_samples", "path": str(output_path)}

    columns = 2
    cell_width, cell_height = 480, 310
    image_width, image_height = 444, 238
    rows = (len(entries) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (columns * cell_width, rows * cell_height),
        (8, 12, 20),
    )
    draw = ImageDraw.Draw(sheet)
    title_font = _font(17, bold=True)
    detail_font = _font(12)
    source_image_count = 0
    placeholders = 0
    for index, (sample, kind, path, artifact_ok) in enumerate(entries):
        column = index % columns
        row = index // columns
        left = column * cell_width + 12
        top = row * cell_height + 12
        right = left + cell_width - 24
        bottom = top + cell_height - 24
        border = (45, 190, 120) if artifact_ok else (225, 145, 55)
        draw.rounded_rectangle(
            (left, top, right, bottom),
            radius=12,
            fill=(18, 26, 39),
            outline=border,
            width=2,
        )
        image_box = (
            left + 6,
            top + 6,
            left + 6 + image_width,
            top + 6 + image_height,
        )
        if artifact_ok and path.is_file() and _image_readable(path):
            try:
                with Image.open(path) as source:
                    thumb = ImageOps.contain(
                        source.convert("RGB"),
                        (image_width, image_height),
                        Image.Resampling.LANCZOS,
                    )
                paste_x = image_box[0] + (image_width - thumb.width) // 2
                paste_y = image_box[1] + (image_height - thumb.height) // 2
                sheet.paste(thumb, (paste_x, paste_y))
                source_image_count += 1
            except Exception:
                placeholders += 1
                draw.rectangle(image_box, fill=(32, 39, 52))
        else:
            placeholders += 1
            draw.rectangle(image_box, fill=(32, 39, 52))
            draw.text(
                (image_box[0] + 14, image_box[1] + 104),
                "capture unavailable",
                font=title_font,
                fill=(175, 183, 197),
            )
        artboard_name = str(
            sample.get("artboard_name") or sample.get("artboard_id") or ""
        )
        label = f"{sample.get('id')} / {artboard_name} · {kind}"
        draw.text(
            (left + 10, top + image_height + 14),
            label,
            font=title_font,
            fill=(238, 243, 249),
        )
        status = "PASS" if artifact_ok else "CHECK"
        draw.text(
            (left + 10, top + image_height + 40),
            f"{status}  {sample.get('category') or ''}",
            font=detail_font,
            fill=border,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG")
    return {
        "ok": output_path.is_file() and source_image_count > 0,
        "path": str(output_path),
        "width": sheet.width,
        "height": sheet.height,
        "screen_count": len(samples),
        "cell_count": len(entries),
        "source_image_count": source_image_count,
        "placeholder_count": placeholders,
        "includes_editor": include_editor,
    }


def _relative_link(path: object, workspace: Path) -> str:
    candidate = Path(str(path or ""))
    try:
        return candidate.resolve().relative_to(workspace.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def write_markdown_index(report: Mapping[str, Any], output_path: Path) -> None:
    workspace = output_path.parent
    summary = report.get("summary") or {}
    contact = report.get("contact_sheet") or {}
    lines = [
        "# Painter UI built-in Unreal UMG batch QA",
        "",
        f"- Result: **{'PASS' if report.get('ok') else 'CHECK'}**",
        f"- Templates: {summary.get('template_count', 0)}",
        f"- Screens: {summary.get('passed', 0)}/{summary.get('screen_count', summary.get('total', 0))} passed",
        f"- All artboards: {bool(report.get('all_artboards'))}",
        f"- Renderer captures: {summary.get('renderer_captures', 0)}",
        f"- Editor screenshots: {summary.get('editor_screenshots', 0)}",
        f"- Contact sheet: [{Path(str(contact.get('path') or '')).name}]({_relative_link(contact.get('path'), workspace)})",
        "",
        "| # | Template | Artboard | Result | Generation | Reopen | Renderer | Editor | Artifacts |",
        "|---:|---|---|---|---|---|---|---|---|",
    ]
    for index, sample in enumerate(report.get("samples") or [], start=1):
        renderer = sample.get("renderer") or {}
        editor = sample.get("editor_screenshot") or {}
        stages = sample.get("stages") or {}
        report_link = _relative_link(sample.get("report"), workspace)
        renderer_link = _relative_link(renderer.get("path"), workspace)
        editor_link = _relative_link(editor.get("path"), workspace)
        artifacts = [f"[report]({report_link})"]
        if renderer.get("exists"):
            artifacts.append(f"[render]({renderer_link})")
        if editor.get("exists"):
            artifacts.append(f"[editor]({editor_link})")
        editor_status = (
            "passed"
            if editor.get("ok")
            else ("not requested" if not editor.get("requested") else "failed")
        )
        name = str(sample.get("name") or "").replace("|", "\\|")
        artboard_name = str(sample.get("artboard_name") or "").replace(
            "|", "\\|"
        )
        artboard_id = str(sample.get("artboard_id") or "").replace(
            "|", "\\|"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    f"`{sample.get('id')}`<br>{name}",
                    f"`{artboard_id}`<br>{artboard_name}",
                    "PASS" if sample.get("ok") else "CHECK",
                    str(stages.get("generation") or "unknown"),
                    str(stages.get("reopen") or "unknown"),
                    str(stages.get("renderer") or "unknown"),
                    editor_status,
                    " · ".join(artifacts),
                ]
            )
            + " |"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _target_sample_directory(
    samples_root: Path,
    target: Mapping[str, Any],
) -> Path:
    template = target.get("template") or {}
    artboard = target.get("artboard") or {}
    base_name = (
        f"{int(target.get('template_index') or 0):02d}_"
        f"{_safe_directory_name(template.get('id'))}"
    )
    if bool(artboard.get("is_default")):
        return samples_root / base_name
    suffix = _safe_directory_name(artboard.get("id"))
    return samples_root / f"{base_name}__{suffix}"


def run_batch_qa(
    workspace: Path,
    *,
    timeout_seconds: int = 300,
    capture_ui: bool = True,
    template_ids: Sequence[str] | None = None,
    all_artboards: bool = False,
    resume: bool = False,
    runner: SampleRunner | None = None,
) -> dict[str, Any]:
    """Run every selected built-in through the focused real-UE QA tool."""

    workspace = workspace.expanduser().resolve()
    samples_root = workspace / "samples"
    samples_root.mkdir(parents=True, exist_ok=True)
    templates = discover_builtin_samples(template_ids)
    targets = discover_builtin_sample_targets(
        template_ids,
        all_artboards=all_artboards,
    )
    execute = runner or _execute_sample
    sample_results: list[dict[str, Any]] = []
    started = time.monotonic()
    for target in targets:
        template = target["template"]
        artboard = target["artboard"]
        template_id = str(template.get("id") or "")
        artboard_id = str(artboard.get("id") or "")
        sample_dir = _target_sample_directory(samples_root, target)
        sample_dir.mkdir(parents=True, exist_ok=True)
        execution = (
            _resume_sample(
                sample_dir,
                template_id=template_id,
                artboard_id=artboard_id,
                capture_ui=capture_ui,
            )
            if resume
            else None
        )
        if execution is None:
            execution = dict(
                _invoke_sample_runner(
                    execute,
                    template,
                    sample_dir,
                    max(30, int(timeout_seconds)),
                    capture_ui,
                    artboard_id,
                )
            )
        sample = _sample_result(
            template,
            artboard,
            sample_dir,
            execution,
            capture_ui=capture_ui,
        )
        (sample_dir / "batch_sample.json").write_text(
            json.dumps(sample, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        sample_results.append(sample)

    contact_path = workspace / "painter_ui_umg_batch_contact_sheet.png"
    contact_sheet = write_contact_sheet(
        sample_results,
        contact_path,
        include_editor=capture_ui,
    )
    passed = sum(bool(row.get("ok")) for row in sample_results)
    renderer_captures = sum(
        bool((row.get("renderer") or {}).get("exists"))
        for row in sample_results
    )
    editor_screenshots = sum(
        bool((row.get("editor_screenshot") or {}).get("exists"))
        for row in sample_results
    )
    report_path = workspace / "batch_report.json"
    index_path = workspace / "index.md"
    report = {
        "schema": BATCH_QA_SCHEMA,
        "ok": bool(sample_results)
        and passed == len(sample_results)
        and bool(contact_sheet.get("ok")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
        "single_qa_tool": str(SINGLE_QA_TOOL),
        "workspace": str(workspace),
        "capture_ui_requested": capture_ui,
        "all_artboards": bool(all_artboards),
        "summary": {
            "total": len(sample_results),
            "template_count": len(templates),
            "screen_count": len(sample_results),
            "passed": passed,
            "failed": len(sample_results) - passed,
            "renderer_captures": renderer_captures,
            "editor_screenshots": editor_screenshots,
            "duration_seconds": round(time.monotonic() - started, 3),
        },
        "paths": {
            "report": str(report_path),
            "index": str(index_path),
            "contact_sheet": str(contact_path),
            "samples": str(samples_root),
        },
        "contact_sheet": contact_sheet,
        "samples": sample_results,
    }
    write_markdown_index(report, index_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sequentially QA Painter UI built-ins in real UE 5.8."
    )
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--template",
        action="append",
        choices=[row["id"] for row in list_ui_templates()],
        dest="templates",
        help="Run only this built-in; repeat to select multiple.",
    )
    parser.add_argument(
        "--all-artboards",
        action="store_true",
        help=(
            "Run every artboard in each selected template. Default active "
            "artboards retain the legacy sample directories for --resume."
        ),
    )
    capture = parser.add_mutually_exclusive_group()
    capture.add_argument(
        "--capture-ui",
        action="store_true",
        dest="capture_ui",
        help="Capture the visible Unreal Widget Blueprint editor (default).",
    )
    capture.add_argument(
        "--no-capture-ui",
        action="store_false",
        dest="capture_ui",
        help="Skip visible editor screenshots; FWidgetRenderer PNGs remain required.",
    )
    parser.set_defaults(capture_ui=True)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse a passing sample report when its renderer PNG still exists.",
    )
    return parser


def main() -> int:
    args = _argument_parser().parse_args()
    report = run_batch_qa(
        args.workspace,
        timeout_seconds=args.timeout,
        capture_ui=bool(args.capture_ui),
        template_ids=args.templates,
        all_artboards=bool(args.all_artboards),
        resume=bool(args.resume),
    )
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "report": report["paths"]["report"],
                "index": report["paths"]["index"],
                "contact_sheet": report["paths"]["contact_sheet"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
