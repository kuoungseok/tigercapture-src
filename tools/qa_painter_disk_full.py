"""Prove Painter recovery behavior on an actually full isolated NTFS VHD.

The VHD is created under debugCapture, assigned an unused drive letter, and is
the only disk selected/formatted by the generated DiskPart script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _is_disk_full_exception(exc: BaseException) -> bool:
    rows: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in rows:
        rows.append(current)
        current = current.__cause__ or current.__context__
    return any(
        getattr(row, "winerror", None) in (39, 112)
        or getattr(row, "errno", None) == 28
        or "disk full" in str(row).casefold()
        or "no space left" in str(row).casefold()
        for row in rows
    )


def _is_disk_full_detail(detail: object) -> bool:
    row = detail if isinstance(detail, dict) else {}
    return row.get("winerror") in (39, 112) or row.get("errno") == 28


def _free_drive_letter() -> str:
    for letter in "RSTUVWXYZ":
        if not Path(f"{letter}:\\").exists():
            return letter
    raise RuntimeError("No free isolated QA drive letter is available")


def _run_diskpart(lines: list[str], script_path: Path) -> dict[str, Any]:
    script_path.write_text("\n".join(lines) + "\n", encoding="ascii")
    try:
        completed = subprocess.run(
            ["diskpart.exe", "/s", str(script_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=120,
        )
    except OSError as exc:
        return {
            "command": ["diskpart.exe", "/s", str(script_path.resolve())],
            "returncode": -1,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "winerror": getattr(exc, "winerror", None),
            "requires_elevation": getattr(exc, "winerror", None) == 740,
        }
    return {
        "command": ["diskpart.exe", "/s", str(script_path.resolve())],
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fill_until_full(path: Path) -> dict[str, Any]:
    written = 0
    error: OSError | None = None
    block = os.urandom(1024 * 1024)
    try:
        with path.open("wb", buffering=0) as handle:
            while True:
                try:
                    handle.write(block)
                    written += len(block)
                    os.fsync(handle.fileno())
                except OSError as exc:
                    error = exc
                    break
    except OSError as exc:
        error = exc
    return {
        "path": str(path),
        "bytes_written": written,
        "error_type": type(error).__name__ if error else "",
        "error": str(error or ""),
        "errno": getattr(error, "errno", None),
        "winerror": getattr(error, "winerror", None),
        "actual_disk_full": bool(error and _is_disk_full_exception(error)),
    }


def _probe_mounted_volume(volume_root: Path, output: Path) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap
    from app.painter_autosave import inspect_recovery_archive
    from app.painter_evidence_contract import evidence_record
    from app.painter_native_environment import environment_overrides, is_native_qt_environment

    output.mkdir(parents=True, exist_ok=True)
    data_root = volume_root / "runtime_data"
    data_root.mkdir(parents=True, exist_ok=True)
    os.environ["TIGERCAPTURE_DATA_DIR"] = str(data_root)
    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 180, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    dialog._painter_recovery_timer.stop()
    dialog._fill_document("solid", color1="#254F78")
    dialog._painter_document_dirty = True
    first_schedule = dialog._schedule_painter_recovery_snapshot(force=True)
    initial = dialog._painter_recovery_future.result(timeout=30)
    initial_path = Path(initial["recovery_path"])
    initial_manifest = Path(initial["manifest_path"])
    initial_archive_hash = _sha256(initial_path)
    initial_content_hash = str(initial["content_sha256"])
    original_copy = output / "original_snapshot.tspaint"
    shutil.copy2(initial_path, original_copy)
    usage_before_fill = shutil.disk_usage(volume_root)

    filler = volume_root / "painter_disk_full_filler.bin"
    fill = _fill_until_full(filler)
    usage_full = shutil.disk_usage(volume_root)
    dialog.canvas.add_stroke_direct(Stroke(
        points=[(0.1, 0.2), (0.5, 0.8), (0.9, 0.25)],
        color=(245, 184, 65), opacity=240, width_px=16.0,
    ))
    dialog._painter_document_dirty = True
    failed_schedule = dialog._schedule_painter_recovery_snapshot(force=True)
    writer_exception: BaseException | None = None
    try:
        dialog._painter_recovery_future.result(timeout=30)
    except BaseException as exc:
        writer_exception = exc
    failed_state = dialog.painter_action_state()["recovery"]
    old_integrity = inspect_recovery_archive(initial_path)
    old_manifest = json.loads(initial_manifest.read_text(encoding="utf-8"))
    old_snapshot_preserved = bool(
        old_integrity["valid"]
        and _sha256(initial_path) == initial_archive_hash
        and old_manifest.get("content_sha256") == initial_content_hash
    )

    filler.unlink(missing_ok=True)
    usage_after_release = shutil.disk_usage(volume_root)
    retry_schedule = dialog._schedule_painter_recovery_snapshot(force=True)
    retry = dialog._painter_recovery_future.result(timeout=30)
    retry_state = dialog.painter_action_state()["recovery"]
    retry_path = Path(retry["recovery_path"])
    retry_integrity = inspect_recovery_archive(retry_path)
    retry_copy = output / "retry_snapshot.tspaint"
    shutil.copy2(retry_path, retry_copy)

    overrides = environment_overrides()
    native = is_native_qt_environment(app.platformName(), overrides)
    actual_error = bool(writer_exception and _is_disk_full_exception(writer_exception))
    error_exposed = _is_disk_full_detail(failed_state.get("last_error_detail"))
    retry_passed = bool(
        retry_schedule.get("scheduled")
        and retry_schedule.get("previous_writer_error")
        and retry_integrity["valid"]
        and retry_state.get("last_error") == ""
        and retry.get("content_sha256") != initial_content_hash
    )
    passed = bool(
        native and fill["actual_disk_full"] and actual_error and error_exposed
        and old_snapshot_preserved and retry_passed
    )
    provenance = evidence_record(
        "native-ntfs-disk-full-recovery",
        "native_runtime",
        passed=passed,
        producer="tools/qa_painter_disk_full.py",
        claims=("disk_full_recovery",),
        command="python tools/qa_painter_disk_full.py",
        environment={"qt_platform": app.platformName(), "overrides": overrides, "filesystem": "NTFS VHD"},
        artifacts=(original_copy, retry_copy),
        limitations=(
            "This proves one isolated NTFS VHD and Painter recovery workload on the measured Windows host.",
            "It does not certify every network, removable, cloud-synced, or non-NTFS filesystem failure mode.",
        ),
    )
    report = {
        "schema": "tigerstudio.painter.native-disk-full-qa.v1",
        "classification": "native_runtime",
        "volume": {
            "root": str(volume_root),
            "before_fill": usage_before_fill._asdict(),
            "at_full": usage_full._asdict(),
            "after_release": usage_after_release._asdict(),
        },
        "initial": {"schedule": first_schedule, "content_sha256": initial_content_hash, "archive_sha256": initial_archive_hash},
        "fill": fill,
        "failed_write": {
            "schedule": failed_schedule,
            "exception_type": type(writer_exception).__name__ if writer_exception else "",
            "exception": str(writer_exception or ""),
            "errno": getattr(writer_exception, "errno", None),
            "winerror": getattr(writer_exception, "winerror", None),
            "actual_disk_full": actual_error,
            "state": failed_state,
        },
        "preservation": {"old_snapshot_preserved": old_snapshot_preserved, "integrity": old_integrity},
        "retry": {"schedule": retry_schedule, "state": retry_state, "integrity": retry_integrity, "passed": retry_passed},
        "provenance": [provenance],
        "passed": passed,
    }
    dialog.close()
    app.processEvents()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Painter against an actually full isolated NTFS VHD")
    parser.add_argument("--vhd-size-mb", type=int, default=96)
    args = parser.parse_args()
    if sys.platform != "win32":
        print(json.dumps({"passed": False, "reason": "Windows NTFS VHD evidence requires Windows"}))
        return 2
    size_mb = max(64, min(512, int(args.vhd_size_mb)))
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    output = ROOT / "debugCapture" / "painter" / "disk_full" / run_id
    output.mkdir(parents=True, exist_ok=True)
    resolved_output = output.resolve()
    expected_parent = (ROOT / "debugCapture" / "painter" / "disk_full").resolve()
    if expected_parent not in resolved_output.parents:
        raise RuntimeError("Refusing to create a VHD outside the Painter disk-full QA root")
    vhd = output / "isolated_disk_full.vhd"
    letter = _free_drive_letter()
    volume_root = Path(f"{letter}:\\")
    create = _run_diskpart([
        f'create vdisk file="{vhd.resolve()}" maximum={size_mb} type=expandable',
        f'select vdisk file="{vhd.resolve()}"',
        "attach vdisk",
        "create partition primary",
        "format fs=ntfs quick label=PAINTER_QA",
        f"assign letter={letter}",
        "exit",
    ], output / "diskpart_create.txt")
    report: dict[str, Any]
    try:
        if create["returncode"] != 0 or not volume_root.exists():
            raise RuntimeError("DiskPart did not create and mount the isolated VHD")
        report = _probe_mounted_volume(volume_root, output)
    except Exception as exc:
        report = {
            "schema": "tigerstudio.painter.native-disk-full-qa.v1",
            "classification": "setup_or_probe_failure",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "provenance": [],
        }
    finally:
        detach = _run_diskpart([
            f'select vdisk file="{vhd.resolve()}"',
            "detach vdisk",
            "exit",
        ], output / "diskpart_detach.txt")
    report.update({
        "run_id": run_id,
        "vhd": {"path": str(vhd.resolve()), "configured_size_mb": size_mb, "drive_letter": letter},
        "diskpart": {"create": create, "detach": detach},
    })
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"report": str(report_path.resolve()), "passed": report.get("passed"), "error": report.get("error", "")}, ensure_ascii=False))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
