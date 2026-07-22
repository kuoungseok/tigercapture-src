from __future__ import annotations

from app.actions.registry import ActionRegistry
from app.motion_designer.release_acceptance import (
    REQUIRED_RELEASE_EVIDENCE, motion_release_preflight, validate_release_evidence,
)
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef


def _composition() -> MotionComposition:
    layer = MotionLayer(
        name="Shape", layer_type="shape",
        source=SourceRef(kind="shape", params={"width": 100, "height": 80, "fill": "#24677f"}),
        out_ms=1000,
    )
    return MotionComposition(width=1280, height=720, duration_ms=1000, layers=[layer])


def test_render_readiness_does_not_fake_product_release_evidence() -> None:
    report = motion_release_preflight(_composition())
    assert report["render_ready"] is True
    assert report["product_release_ready"] is False
    assert report["status"] == "render_ready_evidence_pending"
    assert set(report["evidence"]["missing"]) == set(REQUIRED_RELEASE_EVIDENCE)


def test_complete_evidence_matrix_allows_release_ready_state(tmp_path) -> None:
    evidence = {}
    for name in REQUIRED_RELEASE_EVIDENCE:
        artifact = tmp_path / f"{name}.json"
        artifact.write_text("{}", encoding="utf-8")
        evidence[name] = {
            "status": "pass", "generated_at": "2026-07-22T00:00:00Z",
            "artifact_path": str(artifact),
        }
    assert validate_release_evidence(evidence)["ok"] is True
    report = motion_release_preflight(_composition(), evidence=evidence)
    assert report["product_release_ready"] is True
    assert report["status"] == "release_ready"


def test_empty_artifact_does_not_satisfy_release_evidence(tmp_path) -> None:
    artifact = tmp_path / "empty.json"
    artifact.touch()
    report = validate_release_evidence({
        "standard_exports": {
            "status": "pass",
            "generated_at": "2026-07-22T00:00:00Z",
            "artifact_path": str(artifact),
        },
    })
    detail = report["details"]["standard_exports"]
    assert detail["ok"] is False
    assert detail["empty_artifact_paths"] == [str(artifact.resolve())]


def test_missing_asset_unknown_layer_and_gpu_proof_are_blockers(tmp_path) -> None:
    image = MotionLayer(name="Missing", layer_type="image", source=SourceRef(kind="image", uri=str(tmp_path / "missing.png")))
    unknown = MotionLayer(name="Unknown", layer_type="future_renderer", source=SourceRef(kind="future_renderer"))
    vrm = MotionLayer(name="VRM", layer_type="vrm_actor", source=SourceRef(kind="vrm_actor", uri=str(tmp_path / "missing.vrm")))
    composition = MotionComposition(layers=[image, unknown, vrm])
    report = motion_release_preflight(composition)
    assert report["render_ready"] is False
    assert report["renderer_coverage"]["unsupported"][0]["layer_id"] == unknown.id
    assert len(report["assets"]["missing"]) == 2
    assert report["gpu"]["missing_diagnostics"] == [vrm.id]


class _Owner:
    def __init__(self, composition: MotionComposition) -> None:
        self._motion_compositions = {composition.id: composition}


def test_release_actions_keep_render_and_product_claims_separate() -> None:
    composition = _composition()
    registry = ActionRegistry(_Owner(composition))
    result = registry.execute("motion.release.preflight", {"composition_id": composition.id})
    assert result.ok
    assert result.result["render_ready"] is True
    assert result.result["product_release_ready"] is False
