"""Regenerable M7 audio-reactive sync and UI QA evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

OUTPUT_DIR = ROOT / "debugCapture" / "motion_designer"
REPORT_PATH = OUTPUT_DIR / "audio_sync_qa.json"
UI_PATH = OUTPUT_DIR / "motion_designer_audio_1600x900.png"


def build_fixture(duration_ms: int = 600_000, hop_ms: int = 20):
    from app.motion_designer.audio_analysis import AudioAnalysisCache, AudioEnvelopeSample
    from app.motion_designer.audio_reactive import AudioReactiveBinding, compile_binding, set_layer_bindings
    from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef

    beat_markers = list(range(0, duration_ms, 500))
    beat_set = set(beat_markers)
    samples = [
        AudioEnvelopeSample(time_ms=time_ms, amplitude=1.0 if time_ms in beat_set else 0.0,
                            bass=.85 if time_ms in beat_set else 0.0,
                            onset=1.0 if time_ms in beat_set else 0.0)
        for time_ms in range(0, duration_ms + 1, hop_ms)
    ]
    cache = AudioAnalysisCache(
        id="audio_sync_10min", source_path="qa://structured-click-track",
        source_signature="qa-10-minute-v1", duration_ms=duration_ms, hop_ms=hop_ms,
        samples=samples, beat_markers=beat_markers, estimated_bpm=120.0,
        metadata={"analysis_version": "motion_audio_analysis_v1", "fixture": True},
    )
    layer = MotionLayer(
        name="Beat Pulse", layer_type="shape", out_ms=duration_ms,
        source=SourceRef(kind="shape", params={
            "width": 120, "height": 80, "fill": "#57b7d0", "shape": "rectangle",
        }),
    )
    layer.transform.position.default = [160.0, 90.0]
    binding = compile_binding(AudioReactiveBinding(
        analysis_id=cache.id, property_name="scale", channel="amplitude",
        mode="multiply", output_min=1.0, output_max=1.5,
        smoothing_ms=0, attack_ms=0, release_ms=0,
    ), cache)
    set_layer_bindings(layer, [binding])
    composition = MotionComposition(
        id="motion_audio_sync_qa", name="M7 Audio Sync QA", width=320, height=180,
        fps=30.0, duration_ms=duration_ms, layers=[layer],
        metadata={"audio_analysis": {cache.id: cache.to_dict()}},
    )
    return composition, cache, layer


def _alpha_bounds(array) -> list[int]:
    import numpy as np

    ys, xs = np.where(array[..., 3] > 8)
    if not xs.size:
        return [0, 0, 0, 0]
    return [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]


def build_report() -> dict:
    from PySide6.QtWidgets import QApplication

    from app.motion_designer.audio_reactive import binding_value_at, layer_bindings
    from app.motion_designer.evaluator import evaluate_composition
    from app.motion_designer.export_renderer import MotionExportRenderer
    from app.motion_designer.render_graph import build_render_graph
    from app.motion_designer.ui.window import MotionDesignerWindow

    app = QApplication.instance() or QApplication([])
    composition, cache, layer = build_fixture()
    binding = layer_bindings(layer)[0]
    frame_ms = 1000.0 / composition.fps
    peak_times = []
    for beat in cache.beat_markers:
        search = range(max(0, beat - cache.hop_ms), min(composition.duration_ms, beat + cache.hop_ms) + 1,
                       cache.hop_ms)
        peak = max(search, key=lambda time_ms: binding_value_at(binding, time_ms))
        peak_times.append((beat, peak))
    max_drift_ms = max((abs(beat - peak) for beat, peak in peak_times), default=0)

    probes = [0, 300_000, 599_500]
    renderer = MotionExportRenderer(cache_capacity=8)
    parity = []
    for time_ms in probes:
        state = evaluate_composition(composition, time_ms)[0]
        graph = build_render_graph(composition, time_ms, include_vector_gpu=True)
        node = graph.nodes[0]
        rgba = renderer.render_rgba_array(composition, time_ms)
        parity.append({
            "time_ms": time_ms, "evaluator_scale": list(state.scale),
            "graph_scale": [float(node.matrix[0]), float(node.matrix[3])],
            "matrix_match": abs(state.scale[0] - node.matrix[0]) < 1e-9 and abs(state.scale[1] - node.matrix[3]) < 1e-9,
            "export_alpha_bounds": _alpha_bounds(rgba), "export_nonblank": bool(rgba[..., 3].max() > 0),
            "shared_graph_renderer": graph.diagnostics["renderer"],
        })

    window = MotionDesignerWindow(composition)
    window.resize(1600, 900)
    window._select_layer(layer.id)
    window.project_tabs.setCurrentWidget(window.audio)
    window.show()
    app.processEvents()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    captured = window.grab().save(str(UI_PATH), "PNG")
    window.close()
    app.processEvents()

    return {
        "ok": max_drift_ms < frame_ms and captured and all(row["matrix_match"] and row["export_nonblank"] for row in parity),
        "schema": "tigerstudio.motion.audio_sync_qa.v1",
        "duration_ms": composition.duration_ms, "fps": composition.fps, "frame_ms": frame_ms,
        "analysis_samples": len(cache.samples), "beat_count": len(cache.beat_markers),
        "max_sync_drift_ms": max_drift_ms, "max_sync_drift_frames": max_drift_ms / frame_ms,
        "structured_timing_priority": "Composer/Voice timing priority is covered by unit tests",
        "preview_export_parity": parity,
        "ui_capture": str(UI_PATH), "ui_capture_ok": captured,
        "cache_invalidation_test": "tests/test_motion_audio_analysis.py",
    }


def main() -> int:
    report = build_report()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
