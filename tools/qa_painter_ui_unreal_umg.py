"""Generate and reopen a real Painter-authored Widget Blueprint in UE 5.8."""
from __future__ import annotations

import argparse
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
from app.painter_ui_umg_adapter import generate_painter_umg
from app.unreal_umg_workflow import DEFAULT_UNREAL_ENGINE_ROOT
from app.window_capture import list_capture_windows, save_window_screenshot


DEFAULT_WORKSPACE = (
    ROOT / "debugCapture" / "painter_ui_designer" / "unreal_umg"
)


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


def _reopen_script(asset_path: str, report_path: Path) -> str:
    return f"""
import json
from pathlib import Path
import unreal

asset_path = {asset_path!r}
asset = unreal.load_asset(asset_path)
generated_class = None
widget_tree = None
widget_count = 0
widget_names = []
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
        except Exception as exc:
            warnings.append(
                "widget_tree_not_exposed_to_python_after_reopen:" + str(exc)
            )

payload = {{
    "ok": asset is not None and generated_class is not None,
    "asset_path": asset_path,
    "asset_loaded": asset is not None,
    "asset_class": asset.get_class().get_name() if asset is not None else "",
    "generated_class_loaded": generated_class is not None,
    "generated_class_name": generated_class.get_name() if generated_class is not None else "",
    "widget_tree_loaded": widget_tree is not None or widget_count > 0,
    "widget_count": widget_count,
    "widget_names": widget_names,
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
            _reopen_script(asset_path, report_path),
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
            return {
                "ok": Path(capture["path"]).is_file(),
                "status": "captured",
                "path": capture["path"],
                "backend": capture["backend"],
                "window": capture["window"],
                "candidate_windows": windows,
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
    reopened = (
        _reopen_generated_asset(
            project,
            generated_asset_path,
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
        and (not args.capture_ui or bool(visual_capture.get("ok"))),
        "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
        "project_path": str(project),
        "template": {
            "id": "mobile_onboarding",
            "report": template_report,
            "active_artboard_id": active_artboard,
            "expected_widget_count": expected_widget_count,
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
