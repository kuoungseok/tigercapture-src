from __future__ import annotations

import json

from app.actor_loading_cache import record_actor_load
from app.loading_performance import (
    LoadingTimer,
    loading_performance_report,
    record_loading_event,
)
from app.preview_acceleration import (
    configure_preview_acceleration_defaults,
    prewarm_ar_pbr_asset_descriptor,
)


def test_loading_performance_report_reads_recent_jsonl(tmp_path, monkeypatch):
    log_path = tmp_path / "loading.jsonl"
    monkeypatch.setenv("TIGERCAPTURE_LOADING_PERF_LOG", str(log_path))

    record_loading_event("decoder.open", "ready", status="ready", elapsed_ms=12.5, detail="cv2")
    timer = LoadingTimer("ar_pbr.preview", tmp_path / "asset.fbx")
    timer.mark("import", metadata={"cached": False})

    report = loading_performance_report(path=log_path)

    assert report["ok"] is True
    assert report["event_count"] == 2
    assert report["by_area"]["decoder.open"] == 1
    assert report["by_area"]["ar_pbr.preview"] == 1
    assert report["by_status"]["ready"] == 1


def test_actor_loading_cache_records_loading_event(tmp_path, monkeypatch):
    log_path = tmp_path / "loading.jsonl"
    monkeypatch.setenv("TIGERCAPTURE_LOADING_PERF_LOG", str(log_path))

    record_actor_load(
        "live2d",
        str(tmp_path / "sample.model3.json"),
        status="loading",
        stage="parse",
        message="parse model",
        elapsed_ms=33,
        cache_path=tmp_path / "actor_cache.json",
    )

    report = loading_performance_report(path=log_path)

    assert report["by_area"]["actor.live2d"] == 1
    assert report["area_summary"]["actor.live2d"]["max_ms"] == 33


def test_preview_acceleration_defaults_are_conservative(monkeypatch):
    keys = [
        "TIGERCAPTURE_PREVIEW_DECODER_AUTO",
        "TIGERCAPTURE_PREVIEW_FRAME_SERVER",
        "TIGERCAPTURE_CV2_FORWARD_SEEK_WINDOW",
        "TIGERCAPTURE_FRAME_CACHE_LIMIT",
        "TIGERCAPTURE_SPINE_PREVIEW_RENDERER",
        "TIGERCAPTURE_SPINE_ZERO_READBACK",
        "TIGERCAPTURE_AR_PBR_GPU_PREVIEW",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)

    defaults = configure_preview_acceleration_defaults()

    assert defaults["TIGERCAPTURE_PREVIEW_DECODER_AUTO"] == "1"
    assert defaults["TIGERCAPTURE_PREVIEW_FRAME_SERVER"] == "auto"
    assert int(defaults["TIGERCAPTURE_CV2_FORWARD_SEEK_WINDOW"]) >= 24
    assert int(defaults["TIGERCAPTURE_FRAME_CACHE_LIMIT"]) >= 36
    assert defaults["TIGERCAPTURE_SPINE_PREVIEW_RENDERER"] == "gl"
    assert defaults["TIGERCAPTURE_SPINE_ZERO_READBACK"] == "1"
    assert defaults["TIGERCAPTURE_AR_PBR_GPU_PREVIEW"] == "1"


def test_ar_pbr_prewarm_reuses_persistent_descriptor_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("TIGERCAPTURE_DISABLE_AR_PBR_DESCRIPTOR_CACHE", raising=False)
    log_path = tmp_path / "loading.jsonl"
    monkeypatch.setenv("TIGERCAPTURE_LOADING_PERF_LOG", str(log_path))
    from app.ar_pbr.importer import import_asset
    from app.ar_pbr.sample_scene import write_pbr_fbx_scene

    asset = write_pbr_fbx_scene(tmp_path / "pbr_scene.fbx")
    first = prewarm_ar_pbr_asset_descriptor(asset, max_triangles=800)
    second_descriptor, second_diag = import_asset(
        asset,
        settings={"max_triangles_per_geometry": 800},
    )

    assert first["ok"] is True
    assert second_descriptor["id"] == first["descriptor"]["id"]
    assert second_diag["cached"] is True
    assert second_diag["imported"] is True
    assert "descriptor_cache" in (first["diagnostics"] or {})
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert any(row["area"] == "ar_pbr.prewarm" for row in rows)
