from pathlib import Path

from app.painter_interop_evidence import sha256_file, validate_external_interop_report


def test_external_report_requires_photoshop_identity_and_real_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "roundtrip.psd"
    artifact.write_bytes(b"8BPS external fixture")
    report = {
        "producer": "Adobe Photoshop",
        "producer_version": "27.0",
        "execution": "windows_com",
        "artifacts": [{
            "path": str(artifact),
            "sha256": sha256_file(artifact),
            "opened_by_external_app": True,
        }],
    }
    assert validate_external_interop_report(report)["valid"] is True


def test_internal_reader_cannot_claim_external_proof(tmp_path: Path) -> None:
    artifact = tmp_path / "internal.psd"
    artifact.write_bytes(b"8BPS internal fixture")
    report = {
        "producer": "psd-tools",
        "producer_version": "1",
        "execution": "internal_reader",
        "artifacts": [{
            "path": str(artifact),
            "sha256": sha256_file(artifact),
            "opened_by_external_app": False,
        }],
    }
    result = validate_external_interop_report(report)
    assert result["valid"] is False
    assert any("producer" in message for message in result["errors"])
