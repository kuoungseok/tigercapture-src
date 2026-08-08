from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _pixel_hash(dialog) -> str:
    image = dialog._painter_composite_pil(include_background=False).convert("RGBA")
    return hashlib.sha256(image.tobytes()).hexdigest()


def _pixel_probe(dialog, path: Path) -> dict[str, object]:
    from dataclasses import asdict
    from app.painter_raster_layers import raster_png_bytes
    image = dialog._painter_composite_pil(include_background=False).convert("RGBA")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return {
        "pixel_hash": hashlib.sha256(image.tobytes()).hexdigest(),
        "size": list(image.size),
        "artifact": str(path.resolve()),
        "layer_count": len(dialog._paint_layers),
        "stroke_count": len(dialog.canvas.embedded_strokes()),
        "strokes": [
            asdict(stroke)
            for stroke in dialog.canvas.embedded_strokes()
        ],
        "layers": [asdict(layer) for layer in dialog._paint_layers],
        "raster_layer_ids": sorted(dialog._paint_layer_rasters),
        "raster_hashes": {
            layer_id: hashlib.sha256(raster_png_bytes(image)).hexdigest()
            for layer_id, image in dialog._paint_layer_rasters.items()
        },
    }


def _writer_child(expected_path: Path) -> int:
    from PySide6.QtWidgets import QApplication
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 180, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_recovery_timer.stop()
    dialog._fill_document("solid", color1="#254F78")
    dialog.canvas.add_stroke_direct(Stroke(
        points=[(0.1, 0.2), (0.45, 0.72), (0.88, 0.3)],
        color=(248, 185, 65),
        opacity=235,
        width_px=14.0,
        brush_style="round",
        point_pressure=[0.25, 0.9, 0.4],
    ))
    dialog._painter_document_dirty = True
    scheduled = dialog._schedule_painter_recovery_snapshot(force=True)
    saved = dialog._painter_recovery_future.result(timeout=30)
    expected_probe = _pixel_probe(dialog, expected_path.with_name("expected.png"))
    expected = {
        **expected_probe,
        "session_id": dialog._painter_recovery_session_id,
        "scheduled": scheduled,
        "saved": saved,
    }
    expected_path.parent.mkdir(parents=True, exist_ok=True)
    expected_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PAINTER_RECOVERY_READY {expected_path}", flush=True)
    while True:
        app.processEvents()
        time.sleep(0.05)


def _restore_child() -> int:
    from PySide6.QtWidgets import QApplication
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_autosave import list_recovery_snapshots

    app = QApplication.instance() or QApplication([])
    rows = list_recovery_snapshots()
    if not rows:
        print("PAINTER_RESTORE_RESULT " + json.dumps({"restored": False, "reason": "no_snapshot"}))
        return 2
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_recovery_timer.stop()
    restored = dialog._restore_painter_recovery_snapshot(rows[0])
    result = {
        "restored": bool(restored.get("restored")),
        **_pixel_probe(
            dialog,
            Path(os.environ["TIGERCAPTURE_DATA_DIR"]).parent / "restored.png",
        ),
        "row": rows[0],
        "restore_report": restored,
    }
    print("PAINTER_RESTORE_RESULT " + json.dumps(result, ensure_ascii=False, default=str), flush=True)
    dialog.close()
    app.processEvents()
    return 0 if result["restored"] else 3


def _atomic_writer_child(session_id: str) -> int:
    """Start a large replacement so the parent can kill us while .tmp exists."""
    from app.painter_autosave import save_recovery_snapshot

    # Incompressible bounded metadata keeps the ZIP writer active long enough
    # for the parent to observe the real mkstemp file. It stays below the
    # document format's 16 MiB metadata ceiling.
    random_payload = os.urandom(6 * 1024 * 1024).hex()
    print("PAINTER_ATOMIC_WRITE_START", flush=True)
    save_recovery_snapshot(
        session_id,
        {"document": {"width": 64, "height": 64}, "fault_probe": random_payload},
    )
    print("PAINTER_ATOMIC_WRITE_REPLACED", flush=True)
    return 0


def _atomic_replace_crash_probe(root: Path, env: dict[str, str]) -> dict[str, object]:
    from app.painter_autosave import inspect_recovery_archive, list_recovery_snapshots, save_recovery_snapshot

    previous = os.environ.get("TIGERCAPTURE_DATA_DIR")
    os.environ["TIGERCAPTURE_DATA_DIR"] = env["TIGERCAPTURE_DATA_DIR"]
    session_id = "atomic-replace-crash"
    try:
        original = save_recovery_snapshot(
            session_id,
            {"document": {"width": 64, "height": 64}, "generation": "original"},
        )
    finally:
        if previous is None:
            os.environ.pop("TIGERCAPTURE_DATA_DIR", None)
        else:
            os.environ["TIGERCAPTURE_DATA_DIR"] = previous
    original_hash = str(original.get("content_sha256") or "")
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--atomic-writer-child",
        session_id,
    ]
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    recovery_dir = Path(env["TIGERCAPTURE_DATA_DIR"]) / "painter" / "recovery"
    deadline = time.monotonic() + 45.0
    temporary_seen = False
    output: list[str] = []
    while time.monotonic() < deadline and process.poll() is None:
        temporary_seen = any(recovery_dir.glob(".*.tmp"))
        if temporary_seen:
            process.kill()
            break
        time.sleep(0.005)
    if process.poll() is None:
        process.kill()
    returncode = process.wait(timeout=10)
    if process.stdout is not None:
        output.extend(process.stdout.read().splitlines())
    rows = list_recovery_snapshots(root=recovery_dir)
    surviving = next((row for row in rows if row.get("session_id") == session_id), {})
    surviving_hash = str(surviving.get("content_sha256") or "")
    integrity = inspect_recovery_archive(str(original["recovery_path"]))
    passed = bool(
        temporary_seen
        and returncode != 0
        and integrity["valid"]
        and surviving_hash == original_hash
    )
    return {
        "command": command,
        "temporary_seen": temporary_seen,
        "returncode_after_kill": returncode,
        "output": output,
        "original_content_sha256": original_hash,
        "surviving_content_sha256": surviving_hash,
        "surviving_integrity": integrity,
        "orphan_temporary_files": [str(path.resolve()) for path in recovery_dir.glob(".*.tmp")],
        "passed": passed,
    }


def _read_until_ready(process: subprocess.Popen, timeout: float = 30.0) -> tuple[bool, list[str]]:
    deadline = time.monotonic() + timeout
    lines: list[str] = []
    while time.monotonic() < deadline:
        line = process.stdout.readline() if process.stdout is not None else ""
        if line:
            lines.append(line.rstrip())
            if line.startswith("PAINTER_RECOVERY_READY "):
                return True, lines
        elif process.poll() is not None:
            break
        else:
            time.sleep(0.02)
    return False, lines


def _main_parent() -> int:
    from app.painter_evidence_contract import evidence_record
    from app.painter_native_environment import environment_overrides, is_native_qt_environment

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    root = ROOT / "debugCapture" / "painter" / "crash_recovery" / run_id
    data_root = root / "runtime_data"
    expected_path = root / "expected.json"
    root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TIGERCAPTURE_DATA_DIR"] = str(data_root)
    command = [sys.executable, str(Path(__file__).resolve()), "--writer-child", str(expected_path)]
    writer = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    ready, writer_output = _read_until_ready(writer)
    if ready and writer.poll() is None:
        writer.kill()
    writer_returncode = writer.wait(timeout=10)
    expected = json.loads(expected_path.read_text(encoding="utf-8")) if expected_path.is_file() else {}

    restore_command = [sys.executable, str(Path(__file__).resolve()), "--restore-child"]
    restored_process = subprocess.run(
        restore_command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=45,
        check=False,
    )
    restore_result: dict[str, object] = {}
    for line in restored_process.stdout.splitlines():
        if line.startswith("PAINTER_RESTORE_RESULT "):
            restore_result = json.loads(line.partition(" ")[2])
    overrides = environment_overrides()
    platform_name = "windows" if sys.platform == "win32" else sys.platform
    native = is_native_qt_environment(platform_name, overrides)
    parity = bool(expected.get("pixel_hash") and expected.get("pixel_hash") == restore_result.get("pixel_hash"))
    atomic_replace = _atomic_replace_crash_probe(root, env)
    passed = bool(
        native
        and ready
        and writer_returncode != 0
        and restored_process.returncode == 0
        and restore_result.get("restored")
        and parity
        and atomic_replace["passed"]
    )
    report_path = root / "report.json"
    provenance = evidence_record(
        "native-process-crash-recovery",
        "native_runtime",
        passed=passed,
        producer="tools/qa_painter_crash_recovery.py",
        claims=("crash_recovery",),
        command="python tools/qa_painter_crash_recovery.py",
        environment={"platform": platform_name, "overrides": overrides},
        artifacts=tuple(
            path for path in (
                expected_path,
                expected.get("artifact", ""),
                restore_result.get("artifact", ""),
            ) if path
        ),
        limitations=(
            "The process is terminated after an autosave future completes; interruption during ZIP replacement is a separate fault-injection case.",
            "This run proves next-process discovery and pixel parity for one bounded document corpus.",
        ),
    )
    report = {
        "schema": "tigerstudio.painter.native-crash-recovery-qa.v1",
        "run_id": run_id,
        "native_environment": native,
        "writer": {
            "command": command,
            "ready": ready,
            "returncode_after_kill": writer_returncode,
            "output": writer_output,
        },
        "expected": expected,
        "restore": {
            "command": restore_command,
            "returncode": restored_process.returncode,
            "stdout": restored_process.stdout,
            "stderr": restored_process.stderr,
            "result": restore_result,
        },
        "pixel_parity": parity,
        "atomic_replace_crash": atomic_replace,
        "provenance": [provenance],
        "passed": passed,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "report": str(report_path.resolve()),
        "writer_killed": ready and writer_returncode != 0,
        "next_process_restored": bool(restore_result.get("restored")),
        "pixel_parity": parity,
        "atomic_replace_survived": atomic_replace["passed"],
        "passed": passed,
    }, ensure_ascii=False))
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--writer-child", type=Path)
    parser.add_argument("--restore-child", action="store_true")
    parser.add_argument("--atomic-writer-child")
    args = parser.parse_args()
    if args.writer_child:
        return _writer_child(args.writer_child)
    if args.restore_child:
        return _restore_child()
    if args.atomic_writer_child:
        return _atomic_writer_child(args.atomic_writer_child)
    return _main_parent()


if __name__ == "__main__":
    raise SystemExit(main())
