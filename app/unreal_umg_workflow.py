"""Tiger-controlled Unreal UMG generation orchestration."""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from threading import Event
from typing import Any

from app.unreal_umg_plugin import install_project_plugin, plugin_status


DEFAULT_UNREAL_ENGINE_ROOT = Path(r"D:\UE_5.8\Engine")


def preflight_umg_project(project_path: str | Path) -> dict[str, Any]:
    project = Path(project_path).expanduser().resolve()
    status = plugin_status(project)
    editor = DEFAULT_UNREAL_ENGINE_ROOT / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
    blockers: list[str] = []
    if not editor.is_file():
        blockers.append(f"missing_unreal_editor:{editor}")
    return {
        "ok": not blockers,
        "project_path": str(project),
        "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
        "editor_path": str(editor),
        "plugin": status.to_dict(),
        "blockers": blockers,
    }


def _runner_script(
    document_path: Path,
    report_path: Path,
    destination_root: str,
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

subsystem = unreal.get_editor_subsystem(unreal.TigerStudioUMGImportSubsystem)
result = subsystem.generate_document_file(
    {str(document_path)!r},
    {destination_root!r},
)
asset_path = str(read_property(result, "generated_asset_path") or "")
asset = unreal.load_asset(asset_path) if asset_path else None
payload = {{
    "ok": bool(read_property(result, "success", "b_success")),
    "message": str(read_property(result, "message") or ""),
    "generated_asset_path": asset_path,
    "generated_asset_loaded": asset is not None,
    "generated_asset_class": asset.get_class().get_name() if asset is not None else "",
    "generated_widget_count": int(read_property(result, "generated_widget_count") or 0),
    "generated_animation_count": int(read_property(result, "generated_animation_count") or 0),
    "imported_asset_paths": [
        str(item) for item in (read_property(result, "imported_asset_paths") or [])
    ],
    "generated_material_paths": [
        str(item) for item in (read_property(result, "generated_material_paths") or [])
    ],
    "generated_widget_classes": {{
        str(key): str(value)
        for key, value in dict(
            read_property(result, "generated_widget_classes") or {{}}
        ).items()
    }},
    "warnings": [str(item) for item in (read_property(result, "warnings") or [])],
    "errors": [str(item) for item in (read_property(result, "errors") or [])],
}}
Path({str(report_path)!r}).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
""".strip()


def run_unreal_umg_generation(
    project_path: str | Path,
    document_path: str | Path,
    *,
    destination_root: str = "/Game/TigerStudio/Generated",
    timeout_seconds: int = 300,
    cancel_event: Event | None = None,
) -> dict[str, Any]:
    project = Path(project_path).expanduser().resolve()
    document = Path(document_path).expanduser().resolve()
    if not document.is_file():
        raise FileNotFoundError(f"Tiger UMG document is missing: {document}")
    preflight = preflight_umg_project(project)
    if not preflight["ok"]:
        return preflight
    installed = install_project_plugin(project)
    editor = Path(preflight["editor_path"])

    with tempfile.TemporaryDirectory(prefix="tigerstudio_umg_run_") as temporary:
        temporary_root = Path(temporary)
        report_path = temporary_root / "report.json"
        script_path = temporary_root / "generate_umg.py"
        script_path.write_text(
            _runner_script(document, report_path, destination_root),
            encoding="utf-8",
        )
        process = subprocess.Popen(
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )
        deadline = time.monotonic() + max(30, int(timeout_seconds))
        while process.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                return {
                    "ok": False,
                    "cancelled": True,
                    "project_path": str(project),
                    "document_path": str(document),
                    "plugin": installed.to_dict(),
                    "returncode": process.returncode,
                    "errors": ["Unreal UMG generation was cancelled."],
                    "stdout_tail": stdout[-4000:],
                    "stderr_tail": stderr[-4000:],
                }
            if time.monotonic() >= deadline:
                process.kill()
                stdout, stderr = process.communicate()
                return {
                    "ok": False,
                    "project_path": str(project),
                    "document_path": str(document),
                    "plugin": installed.to_dict(),
                    "returncode": process.returncode,
                    "errors": ["Unreal UMG generation timed out."],
                    "stdout_tail": stdout[-4000:],
                    "stderr_tail": stderr[-4000:],
                }
            time.sleep(0.1)
        stdout, stderr = process.communicate()
        if not report_path.is_file():
            return {
                "ok": False,
                "project_path": str(project),
                "document_path": str(document),
                "plugin": installed.to_dict(),
                "returncode": process.returncode,
                "errors": ["Unreal did not produce a Tiger UMG generation report."],
                "stdout_tail": stdout[-8000:],
                "stderr_tail": stderr[-8000:],
            }
        result = json.loads(report_path.read_text(encoding="utf-8"))
        result.update(
            {
                "project_path": str(project),
                "document_path": str(document),
                "plugin": installed.to_dict(),
                "returncode": process.returncode,
                "stdout_tail": stdout[-4000:],
                "stderr_tail": stderr[-4000:],
            }
        )
        result["ok"] = bool(result.get("ok")) and process.returncode == 0
        return result


__all__ = [
    "DEFAULT_UNREAL_ENGINE_ROOT",
    "preflight_umg_project",
    "run_unreal_umg_generation",
]
