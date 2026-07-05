from __future__ import annotations

import json
import os
from pathlib import Path


def test_sdr_hdr_upmap_command_declares_float_exr(tmp_path):
    from app.sdr_hdr_upmap import SDRHDRUpmapProfile, build_sdr_to_hdr_exr_command

    cmd = build_sdr_to_hdr_exr_command(
        tmp_path / "input.mp4",
        tmp_path / "exr",
        SDRHDRUpmapProfile(max_frames=3, highlight_boost=1.5),
        ffmpeg="ffmpeg",
    )
    text = " ".join(str(part) for part in cmd)

    assert "-c:v exr" in text
    assert "-pix_fmt gbrpf32le" in text
    assert "format=rgb48le" in text
    assert "frame_%06d.exr" in text
    assert "-frames:v 3" in text


def test_sdr_hdr_upmap_report_is_honest_without_ltx_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("TIGERCAPTURE_LTX_HDR_ENDPOINT", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_LTX_HDR_COMMAND", raising=False)

    from app.sdr_hdr_upmap import sdr_to_hdr_upmap_report

    report = sdr_to_hdr_upmap_report(tmp_path / "missing.mp4", tmp_path / "frames", run=False)

    assert report["ok"] is True
    assert report["dry_run"] is True
    assert report["engine"] == "local_inverse_tone_map"
    assert report["real_ltx_model"] is False
    assert report["claim_level"] == "ltx_style_hdr_exr_foundation_not_neural_ltx_parity"
    assert report["provider"]["configured"] is False
    assert report["preset_gallery"]["preset_count"] >= 4
    assert report["review_model"]["ready"] is True


def test_sdr_hdr_upmap_preset_gallery_and_review_model_are_ui_ready():
    from app.sdr_hdr_upmap import SDRHDRUpmapProfile, sdr_hdr_upmap_preset_gallery, sdr_hdr_upmap_review_model

    gallery = sdr_hdr_upmap_preset_gallery()
    review = sdr_hdr_upmap_review_model(SDRHDRUpmapProfile(peak_nits=1500, highlight_boost=1.65, curve_gamma=0.78))

    assert gallery["ready"] is True
    assert gallery["preset_count"] >= 4
    assert all(row["profile"]["target"] == "scene_linear_exr" for row in gallery["presets"])
    assert review["ready"] is True
    assert review["preset_id"] == "cinematic_probe_1500"
    assert any(row["id"] == "create_exr_frames" for row in review["actions"])
    assert any(row["id"] == "peak_nits" for row in review["controls"])


def test_convert_sdr_to_hdr_exr_cli_writes_dry_run_report(tmp_path):
    from tools.convert_sdr_to_hdr_exr import main

    report_path = tmp_path / "report.json"
    code = main([
        "--input", str(tmp_path / "source.mp4"),
        "--out-dir", str(tmp_path / "frames"),
        "--out", str(report_path),
        "--max-frames", "2",
    ])
    data = json.loads(report_path.read_text(encoding="utf-8"))

    assert code == 0
    assert data["dry_run"] is True
    assert data["profile"]["max_frames"] == 2
    assert data["output_pattern"].endswith("frame_%06d.exr")


def test_qa_sdr_hdr_upmap_contract_passes(tmp_path):
    from tools.qa_sdr_hdr_upmap import run_sdr_hdr_upmap_qa

    out = tmp_path / "qa.json"
    report = run_sdr_hdr_upmap_qa(out=out)

    assert report["ok"] is True
    assert report["checks"]["scene_linear_float_filter"] is True
    assert report["checks"]["honest_claim"] is True
    assert out.exists()


def test_workbench_has_persistent_sdr_hdr_upmap_node():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication

    from app.effect_node_params import SDRHDRUpmapParams
    from app.project_player import _apply_node_effect_player
    from app.workbench.node_graph.scene import NodeGraphScene

    QApplication.instance() or QApplication([])

    scene = NodeGraphScene()
    node = scene.add_effect_node("sdr_hdr_upmap", pos=QPointF(0, 0), auto_connect=True)
    node.effect_params.peak_nits = 1200
    node.effect_params.max_frames = 12
    saved = scene.to_data()

    restored = NodeGraphScene()
    restored.load_from_data(saved)
    restored_node = restored._serial_nodes[0]

    assert restored_node.NODE_KIND == "sdr_hdr_upmap"
    assert isinstance(restored_node.effect_params, SDRHDRUpmapParams)
    assert restored_node.effect_params.peak_nits == 1200
    assert restored_node.effect_params.max_frames == 12
    payload = restored_node.effect_params.to_node_payload()
    assert payload["execution"] == "tools/convert_sdr_to_hdr_exr.py"

    import numpy as np

    rgb = np.full((4, 4, 3), 128, dtype=np.uint8)
    assert (_apply_node_effect_player(restored_node, rgb.copy(), [], 0) == rgb).all()
