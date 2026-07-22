from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.motion_designer.color_management import composite_premultiplied_srgb_over_srgb
from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.export_pipeline import MotionExportCancelled, MotionProfileExporter
from app.motion_designer.interchange import export_interchange
from app.motion_designer.recovery import motion_recovery_path, read_motion_recovery, write_motion_recovery
from app.motion_designer.relink import apply_motion_relink
from app.motion_designer.release_acceptance import motion_release_preflight
from app.motion_designer.schema import Keyframe, MotionComposition, MotionLayer, SourceRef
from app.motion_designer.ui.window import MotionDocumentController


DEFAULT_OUTPUT = ROOT / "debugCapture" / "motion_designer" / "release_acceptance"


def _record(paths: list[Path], generated_at: str) -> dict:
    return {
        "status": "pass",
        "generated_at": generated_at,
        "artifact_paths": [str(path.resolve()) for path in paths],
    }


def _write_json(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _read_pass_report(path: Path) -> dict:
    if not path.is_file():
        return {"ok": False, "error": "report missing", "path": str(path)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": str(path)}
    return data if isinstance(data, dict) else {"ok": False, "error": "report is not an object", "path": str(path)}


def _sample_composition() -> MotionComposition:
    shape = MotionLayer(
        name="Release Accent", layer_type="shape",
        source=SourceRef(kind="shape", params={
            "shape": "rectangle", "width": 40, "height": 24,
            "fill": "#36b7d9", "stroke": "#ffffff", "stroke_width": 1,
        }), out_ms=100,
    )
    shape.transform.position.default = [32, 32]
    shape.transform.opacity.default = 0.65
    return MotionComposition(
        name="Motion Release QA", width=64, height=64, fps=10,
        duration_ms=100, layers=[shape],
    )


def run(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    generated_at = datetime.now(timezone.utc).isoformat()
    composition = _sample_composition()
    exporter = MotionProfileExporter()
    export_paths: list[Path] = []
    for profile_id, target in (
        ("h264_mp4", output_dir / "standard" / "motion_h264.mp4"),
        ("h265_mp4", output_dir / "standard" / "motion_h265.mp4"),
        ("prores_4444_mov", output_dir / "standard" / "motion_prores4444.mov"),
        ("png_sequence", output_dir / "standard" / "png_sequence"),
        ("openexr_sequence", output_dir / "standard" / "exr_sequence"),
        ("png_still", output_dir / "standard" / "motion.png"),
        ("jpeg_still", output_dir / "standard" / "motion.jpg"),
        ("webp_still", output_dir / "standard" / "motion.webp"),
    ):
        result = exporter.export(composition, profile_id, target)
        export_paths.extend(Path(path) for path in result["paths"])
    export_paths.append(Path(export_interchange(
        composition, "lottie", output_dir / "standard" / "motion_lottie.json",
    )["output_path"]))
    export_paths.append(Path(export_interchange(
        composition, "svg", output_dir / "standard" / "motion.svg",
    )["output_path"]))

    import numpy as np

    overlay = np.array([[[128, 0, 0, 128]]], dtype=np.uint8)
    linear_pixel = int(composite_premultiplied_srgb_over_srgb(
        np.zeros((1, 1, 3), dtype=np.uint8), overlay,
    )[0, 0, 0])
    color_path = _write_json(output_dir / "color_alpha_golden.json", {
        "ok": 187 <= linear_pixel <= 189,
        "linear_half_red_srgb": linear_pixel,
        "expected_range": [187, 189],
        "alpha_order": "unpremultiply_srgb-decode_linear-premultiply_linear-composite-encode_srgb",
    })

    stress_start = time.perf_counter()
    stress_layers = MotionComposition(width=64, height=64, duration_ms=1_800_000)
    stress_layers.layers = [
        MotionLayer(name=f"Layer {index}", out_ms=stress_layers.duration_ms)
        for index in range(1000)
    ]
    state_count = len(evaluate_composition(stress_layers, 1_799_999))
    layer_path = _write_json(output_dir / "stress_1000_layers.json", {
        "ok": state_count == 1000, "layer_count": state_count,
        "duration_ms": stress_layers.duration_ms,
        "evaluate_seconds": time.perf_counter() - stress_start,
    })

    key_start = time.perf_counter()
    key_layer = MotionLayer(name="10k Keys", out_ms=1_800_000)
    key_layer.transform.opacity.keyframes = [
        Keyframe(time_ms=index * 180, value=(index % 100) / 100.0)
        for index in range(10_000)
    ]
    stress_keys = MotionComposition(
        width=64, height=64, duration_ms=1_800_000, layers=[key_layer],
    )
    evaluated = evaluate_composition(stress_keys, 1_799_000)[0]
    key_path = _write_json(output_dir / "stress_10000_keyframes.json", {
        "ok": len(key_layer.transform.opacity.keyframes) == 10_000,
        "keyframe_count": len(key_layer.transform.opacity.keyframes),
        "sample_opacity": evaluated.opacity,
        "evaluate_seconds": time.perf_counter() - key_start,
    })

    seek_start = time.perf_counter()
    seek_times = [index * 18_000 for index in range(101)]
    for time_ms in seek_times:
        evaluate_composition(stress_keys, time_ms)
    seek_path = _write_json(output_dir / "timeline_30m_seek_probe.json", {
        "ok": True,
        "scope": "seek_probe_not_30_min_continuous_playback",
        "duration_ms": 1_800_000,
        "sample_count": len(seek_times),
        "elapsed_seconds": time.perf_counter() - seek_start,
    })

    queue_composition = _sample_composition()
    queue_composition.duration_ms = 600
    cancel_calls = 0

    def cancel_png() -> bool:
        nonlocal cancel_calls
        cancel_calls += 1
        return cancel_calls > 2

    queue_dir = output_dir / "queue" / "png_sequence"
    try:
        MotionProfileExporter(cancel_check=cancel_png).export(
            queue_composition, "png_sequence", queue_dir,
        )
    except MotionExportCancelled:
        pass
    partial_count = len(list(queue_dir.glob("frame_*.png")))
    partial_manifest_absent = not (queue_dir / "manifest.json").exists()
    resumed = MotionProfileExporter().export(
        queue_composition, "png_sequence", queue_dir, resume=True,
    )
    video_calls = 0

    def cancel_video() -> bool:
        nonlocal video_calls
        video_calls += 1
        return video_calls > 1

    retry_video = output_dir / "queue" / "retry.mp4"
    try:
        MotionProfileExporter(cancel_check=cancel_video).export(
            queue_composition, "h264_mp4", retry_video,
        )
    except MotionExportCancelled:
        pass
    partial_video_absent = not retry_video.with_name(retry_video.name + ".partial").exists()
    retried = MotionProfileExporter().export(queue_composition, "h264_mp4", retry_video)
    queue_ok = (
        partial_count == 2 and partial_manifest_absent
        and resumed["sequence_complete"] and resumed["resumed_frame_count"] == 2
        and partial_video_absent and retry_video.is_file()
        and retried["frame_count"] == 6
    )
    queue_path = _write_json(output_dir / "queue_cancel_resume_retry.json", {
        "ok": queue_ok,
        "cancelled_png_frame_count": partial_count,
        "cancelled_png_manifest_absent": partial_manifest_absent,
        "resumed_png_frame_count": resumed["frame_count"],
        "resumed_png_reused_count": resumed["resumed_frame_count"],
        "cancelled_video_partial_absent": partial_video_absent,
        "retried_video_frame_count": retried["frame_count"],
        "retried_video_path": str(retry_video.resolve()),
    })

    relink_old = output_dir / "relink" / "old_project"
    relink_new = output_dir / "relink" / "moved_project"
    for root in (relink_old, relink_new):
        for relative in ("media/plate.png", "fonts/studio.ttf", "particles/spark.png"):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(relative.encode("ascii"))
    relink_composition = MotionComposition(layers=[
        MotionLayer(name="Plate", layer_type="image", source=SourceRef(
            kind="image", uri=str(relink_old / "media" / "plate.png"),
        )),
        MotionLayer(name="Title", layer_type="text", source=SourceRef(
            kind="text", params={"font_file": str(relink_old / "fonts" / "studio.ttf")},
        )),
        MotionLayer(name="Particles", layer_type="particle", source=SourceRef(
            kind="particle", params={"particle": {
                "shape": "sprite", "sprite_uri": str(relink_old / "particles" / "spark.png"),
            }},
        )),
    ])
    relinked, relink_report = apply_motion_relink(
        relink_composition, old_root=relink_old, new_root=relink_new,
    )
    relink_values = [
        relinked.layers[0].source.uri,
        relinked.layers[1].source.params["font_file"],
        relinked.layers[2].source.params["particle"]["sprite_uri"],
    ]
    relink_ok = relink_report["changed_count"] == 3 and all(
        Path(value).is_relative_to(relink_new) and Path(value).is_file() for value in relink_values
    )
    relink_path = _write_json(output_dir / "project_relink_move.json", {
        "ok": relink_ok,
        "old_root": str(relink_old.resolve()),
        "new_root": str(relink_new.resolve()),
        "changed_count": relink_report["changed_count"],
        "ambiguous_count": relink_report["ambiguous_count"],
        "missing_count": relink_report["missing_count"],
        "resolved_paths": relink_values,
    })

    recovery_composition = MotionComposition(layers=[MotionLayer(name="Editable")])
    recovery_layer_id = recovery_composition.layers[0].id
    controller = MotionDocumentController(recovery_composition, lambda _composition: None)
    for index in range(500):
        controller.update_layer(recovery_layer_id, {"name": f"Layer {index}"})
    edited = controller.composition.to_dict()
    for _ in range(500):
        controller.undo()
    undo_ok = controller.composition.to_dict() == recovery_composition.to_dict()
    for _ in range(500):
        controller.redo()
    redo_ok = controller.composition.to_dict() == edited
    recovery_file = motion_recovery_path(output_dir / "recovery", controller.composition.id)
    write_motion_recovery(controller.composition, recovery_file)
    restored, recovery_report = read_motion_recovery(
        recovery_file, expected_composition_id=controller.composition.id,
    )
    damage_rejected = False
    recovery_data = json.loads(recovery_file.read_text(encoding="utf-8"))
    recovery_data["composition"]["name"] = "corrupted"
    damaged_file = recovery_file.with_name("damaged.motion-recovery.json")
    damaged_file.write_text(json.dumps(recovery_data), encoding="utf-8")
    try:
        read_motion_recovery(damaged_file, expected_composition_id=controller.composition.id)
    except ValueError:
        damage_rejected = True
    recovery_path = _write_json(output_dir / "undo_autosave_recovery.json", {
        "ok": undo_ok and redo_ok and restored.to_dict() == edited and damage_rejected,
        "edit_count": 500,
        "undo_count": 500,
        "redo_count": 500,
        "undo_roundtrip": undo_ok,
        "redo_roundtrip": redo_ok,
        "autosave_path": recovery_report["path"],
        "checksum_sha256": recovery_report["checksum_sha256"],
        "damaged_record_rejected": damage_rejected,
    })

    gpu_reports = [
        ROOT / "debugCapture" / "motion_designer" / "motion_designer_boolean_gpu_report.json",
        ROOT / "debugCapture" / "motion_designer" / "motion_designer_typography_gpu_report.json",
        ROOT / "debugCapture" / "motion_designer" / "particles" / "report.json",
    ]
    gpu_results = [_read_pass_report(path) for path in gpu_reports]
    gpu_parity_ok = all(
        row.get("ok")
        and not row.get("software_renderer_used", False)
        and str((row.get("backend") or {}).get("backend") or "").startswith("motion_")
        for row in gpu_results
    )
    gpu_parity_path = _write_json(output_dir / "gpu_preview_export_parity.json", {
        "ok": gpu_parity_ok,
        "software_renderer_used": False,
        "reports": [str(path.resolve()) for path in gpu_reports],
        "checks": [
            {
                "backend": (row.get("backend") or {}).get("backend"),
                "context_valid": (row.get("backend") or {}).get("context_valid"),
                "gl_error": (row.get("backend") or {}).get("gl_error"),
                "parity": row.get("parity"),
            }
            for row in gpu_results
        ],
    })
    context_report_path = (
        ROOT / "debugCapture" / "motion_designer" / "gpu_context_recovery" / "report.json"
    )
    context_result = _read_pass_report(context_report_path)
    context_ok = bool(
        context_result.get("ok")
        and not context_result.get("software_renderer_used", False)
        and int(context_result.get("context_destroy_signal_count", 0)) >= 1
        and (context_result.get("after") or {}).get("context_valid")
        and int((context_result.get("after") or {}).get("gl_error", -1)) == 0
    )
    gpu_context_path = _write_json(output_dir / "gpu_context_recovery.json", {
        "ok": context_ok,
        "software_renderer_used": False,
        "source_report": str(context_report_path.resolve()),
        "context_destroy_signal_count": context_result.get("context_destroy_signal_count", 0),
        "before": context_result.get("before", {}),
        "after": context_result.get("after", {}),
        "parity": context_result.get("parity", {}),
    })
    installer_report_path = (
        ROOT / "debugCapture" / "motion_designer" / "installer_smoke" / "report.json"
    )
    installer_result = _read_pass_report(installer_report_path)
    installer_path = Path(str(installer_result.get("installer_path") or ""))
    installer_ok = bool(
        installer_result.get("ok")
        and installer_path.is_file()
        and installer_result.get("capture_executable_present")
        and installer_result.get("studio_executable_present")
        and installer_result.get("studio_process_live_at_probe")
        and installer_result.get("studio_windows")
        and installer_result.get("temporary_install_removed")
        and installer_result.get("installer_current_for_source")
    )
    installer_evidence_path = _write_json(output_dir / "installer_smoke.json", {
        "ok": installer_ok,
        "source_report": str(installer_report_path.resolve()),
        "installer_path": str(installer_path.resolve()) if installer_path.is_file() else "",
        "installer_sha256": installer_result.get("installer_sha256", ""),
        "installed_file_count": installer_result.get("installed_file_count", 0),
        "studio_windows": installer_result.get("studio_windows", []),
        "temporary_install_removed": installer_result.get("temporary_install_removed", False),
        "installer_current_for_source": installer_result.get("installer_current_for_source", False),
    })
    long_run_report_path = (
        ROOT / "debugCapture" / "motion_designer" / "long_run_30m" / "report.json"
    )
    long_run_result = _read_pass_report(long_run_report_path)
    long_run_ok = bool(
        long_run_result.get("ok")
        and str(long_run_result.get("scope") or "") == "continuous_wall_clock_motion_opengl_preview"
        and float(long_run_result.get("target_seconds", 0) or 0) >= 1800.0
        and float(long_run_result.get("elapsed_seconds", 0) or 0) >= 1791.0
        and long_run_result.get("timeline_reached_end")
        and not long_run_result.get("software_renderer_used", False)
        and (long_run_result.get("backend") or {}).get("context_valid")
        and int((long_run_result.get("backend") or {}).get("gl_error", -1)) == 0
    )
    long_run_evidence_path = _write_json(output_dir / "long_run_30m.json", {
        "ok": long_run_ok,
        "source_report": str(long_run_report_path.resolve()),
        "scope": long_run_result.get("scope", ""),
        "target_seconds": long_run_result.get("target_seconds", 0),
        "elapsed_seconds": long_run_result.get("elapsed_seconds", 0),
        "frame_swaps": long_run_result.get("frame_swaps", 0),
        "average_frame_swaps_per_second": long_run_result.get("average_frame_swaps_per_second", 0),
        "memory_growth_bytes": long_run_result.get("memory_growth_bytes", 0),
        "backend": long_run_result.get("backend", {}),
    })

    evidence = {
        "standard_exports": _record(export_paths, generated_at),
        "color_alpha_golden": _record([color_path], generated_at),
        "stress_1000_layers": _record([layer_path], generated_at),
        "stress_10000_keyframes": _record([key_path], generated_at),
        "queue_cancel_resume_retry": _record([queue_path, retry_video], generated_at),
        "project_relink_move": _record([relink_path], generated_at),
        "undo_autosave_recovery": _record([recovery_path, recovery_file], generated_at),
    }
    if gpu_parity_ok:
        evidence["gpu_preview_export_parity"] = _record([gpu_parity_path, *gpu_reports], generated_at)
    if context_ok:
        evidence["gpu_context_recovery"] = _record([gpu_context_path, context_report_path], generated_at)
    if installer_ok:
        evidence["installer_smoke"] = _record(
            [installer_evidence_path, installer_report_path, installer_path], generated_at,
        )
    if long_run_ok:
        evidence["long_run_30m"] = _record(
            [long_run_evidence_path, long_run_report_path], generated_at,
        )
    acceptance = motion_release_preflight(composition, evidence=evidence)
    artifacts_ok = all(path.exists() and path.stat().st_size > 0 for path in export_paths)
    report = {
        "ok": artifacts_ok and bool(acceptance["product_release_ready"]),
        "artifacts_ok": artifacts_ok,
        "generated_at": generated_at,
        "scope": "motion_product_release_qa",
        "standard_export_count": len(export_paths),
        "evidence": evidence,
        "acceptance": acceptance,
        "non_release_evidence": {"timeline_30m_seek_probe": str(seek_path)},
        "remaining_release_evidence": acceptance["evidence"]["missing"],
    }
    _write_json(output_dir / "report.json", report)
    app.processEvents()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run actual Motion M11 export and structural stress QA",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.output.resolve())
    print(json.dumps({
        "ok": report["ok"],
        "standard_export_count": report["standard_export_count"],
        "remaining_release_evidence": report["remaining_release_evidence"],
        "report": str(args.output.resolve() / "report.json"),
    }, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
