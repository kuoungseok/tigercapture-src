from __future__ import annotations

import json
import zipfile


def test_update_manifest_detects_available_update() -> None:
    from app.update.manifest import build_manifest, evaluate_manifest, manifest_from_json, manifest_to_json

    manifest = build_manifest(
        version="1.4.3",
        artifact_url="https://updates.example/TigerCapture-Setup-1.4.3.exe",
        sha256="a" * 64,
        size=123,
        filename="TigerCapture-Setup-1.4.3.exe",
    )

    parsed = manifest_from_json(manifest_to_json(manifest))
    check = evaluate_manifest(parsed, current_version="1.4.2", channel="stable")

    assert check.available is True
    assert check.reason == "update_available"
    assert check.artifact is not None
    assert check.artifact.sha256 == "a" * 64


def test_update_manifest_blocks_too_old_auto_updater() -> None:
    from app.update.manifest import build_manifest, evaluate_manifest

    manifest = build_manifest(
        version="2.0.0",
        minimum_app_version="1.9.0",
        artifact_url="TigerCapture-Setup-2.0.0.exe",
        sha256="b" * 64,
    )

    check = evaluate_manifest(manifest, current_version="1.4.2", channel="stable")

    assert check.available is False
    assert check.blocked is True
    assert check.reason == "current_version_below_minimum_full_installer_required"


def test_update_sha_download_and_apply_plan_roundtrip(tmp_path, monkeypatch) -> None:
    from app.update.apply_plan import build_apply_plan, read_apply_plan, write_apply_plan
    from app.update.downloader import download_artifact
    from app.update.manifest import build_manifest
    from app.update.verifier import sha256_file, verify_artifact_file

    monkeypatch.setenv("TIGERCAPTURE_DATA_DIR", str(tmp_path / "data"))
    artifact_path = tmp_path / "TigerCapture-1.4.3.zip"
    artifact_path.write_bytes(b"update payload")
    digest = sha256_file(artifact_path)
    manifest = build_manifest(
        version="1.4.3",
        artifact_url=str(artifact_path),
        sha256=digest,
        kind="portable_zip",
        filename=artifact_path.name,
    )
    artifact = manifest.artifacts[0]

    downloaded = download_artifact(artifact, cache_dir=tmp_path / "cache")
    integrity = verify_artifact_file(downloaded.path, artifact)
    plan = build_apply_plan(
        artifact_path=downloaded.path,
        manifest=manifest,
        artifact=artifact,
        install_dir=tmp_path / "install",
        current_version="1.4.2",
    )
    plan_path = write_apply_plan(plan, tmp_path / "apply-plan.json")
    loaded = read_apply_plan(plan_path)

    assert integrity["ok"] is True
    assert downloaded.bytes_written == len(b"update payload")
    assert loaded.target_version == "1.4.3"
    assert loaded.artifact_kind == "portable_zip"


def test_update_checker_reads_local_manifest_uri(tmp_path) -> None:
    from app.update.checker import check_for_update
    from app.update.manifest import build_manifest, manifest_to_json

    manifest_path = tmp_path / "latest.json"
    manifest = build_manifest(
        version="1.4.3",
        artifact_url="TigerCapture-Setup-1.4.3.exe",
        sha256="c" * 64,
    )
    manifest_path.write_text(manifest_to_json(manifest), encoding="utf-8")

    check = check_for_update(manifest_path.as_uri(), current_version="1.4.2")

    assert check.available is True
    assert check.latest_version == "1.4.3"


def test_tigercapture_updater_applies_portable_zip_to_temp_install(tmp_path) -> None:
    from app.update.apply_plan import UpdateApplyPlan, write_apply_plan
    from app.update.verifier import sha256_file
    from tools.tigercapture_updater import apply_plan

    install_dir = tmp_path / "install"
    install_dir.mkdir()
    (install_dir / "TigerCapture.exe").write_text("old", encoding="utf-8")
    package = tmp_path / "package.zip"
    payload_root = tmp_path / "payload"
    payload_root.mkdir()
    (payload_root / "TigerCapture.exe").write_text("new", encoding="utf-8")
    (payload_root / "resources.txt").write_text("resource", encoding="utf-8")
    with zipfile.ZipFile(package, "w") as zf:
        zf.write(payload_root / "TigerCapture.exe", "TigerCapture/TigerCapture.exe")
        zf.write(payload_root / "resources.txt", "TigerCapture/resources.txt")
    plan = UpdateApplyPlan(
        artifact_path=str(package),
        artifact_sha256=sha256_file(package),
        artifact_kind="portable_zip",
        install_dir=str(install_dir),
        app_exe="TigerCaptureMissing.exe",
        target_version="1.4.3",
        backup_dir=str(tmp_path / "backup"),
    )

    dry = apply_plan(plan, dry_run=True)
    actual = apply_plan(plan, dry_run=False)

    assert dry["ok"] is True
    assert actual["ok"] is True
    assert (install_dir / "TigerCapture.exe").read_text(encoding="utf-8") == "new"
    assert (install_dir / "resources.txt").read_text(encoding="utf-8") == "resource"
    assert (tmp_path / "backup" / "TigerCapture.exe").read_text(encoding="utf-8") == "old"


def test_tigercapture_updater_rejects_zip_path_traversal(tmp_path) -> None:
    from app.update.apply_plan import UpdateApplyPlan
    from app.update.verifier import sha256_file
    from tools.tigercapture_updater import apply_plan

    install_dir = tmp_path / "install"
    install_dir.mkdir()
    package = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(package, "w") as zf:
        zf.writestr("../escape.txt", "bad")
    plan = UpdateApplyPlan(
        artifact_path=str(package),
        artifact_sha256=sha256_file(package),
        artifact_kind="portable_zip",
        install_dir=str(install_dir),
        app_exe="TigerCaptureMissing.exe",
        target_version="1.4.3",
        backup_dir=str(tmp_path / "backup"),
    )

    report = apply_plan(plan, dry_run=False)

    assert report["ok"] is False
    assert "unsafe zip member path" in str(report["reason"])


def test_build_update_manifest_cli_writes_manifest(tmp_path) -> None:
    from tools.build_update_manifest import main

    artifact = tmp_path / "TigerCapture-Setup-1.4.3.exe"
    output = tmp_path / "latest.json"
    artifact.write_bytes(b"installer")

    import sys

    old_argv = sys.argv
    try:
        sys.argv = [
            "build_update_manifest.py",
            "--artifact",
            str(artifact),
            "--version",
            "1.4.3",
            "--artifact-url",
            "https://updates.example/TigerCapture-Setup-1.4.3.exe",
            "--output",
            str(output),
        ]
        assert main() == 0
    finally:
        sys.argv = old_argv

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["version"] == "1.4.3"
    assert data["artifacts"][0]["sha256"]


def test_prepare_update_workflow_writes_apply_plan(tmp_path, monkeypatch) -> None:
    from app.update.manifest import build_manifest, manifest_to_json
    from app.update.verifier import sha256_file
    from app.update.workflow import prepare_update_from_manifest

    monkeypatch.setenv("TIGERCAPTURE_DATA_DIR", str(tmp_path / "data"))
    artifact = tmp_path / "TigerCapture-1.4.3.zip"
    manifest_path = tmp_path / "latest.json"
    artifact.write_bytes(b"payload")
    manifest = build_manifest(
        version="1.4.3",
        artifact_url=str(artifact),
        sha256=sha256_file(artifact),
        kind="portable_zip",
        filename=artifact.name,
    )
    manifest_path.write_text(manifest_to_json(manifest), encoding="utf-8")

    report = prepare_update_from_manifest(
        manifest_path,
        current_version="1.4.2",
        install_dir=tmp_path / "install",
        cache_dir=tmp_path / "cache",
        plan_path=tmp_path / "plan.json",
        updater_exe=tmp_path / "TigerCaptureUpdater.exe",
    )

    assert report["ok"] is True
    assert report["stage"] == "prepared"
    assert report["check"]["available"] is True
    assert report["integrity"]["ok"] is True
    assert report["updater_command"][0].endswith("TigerCaptureUpdater.exe")
    assert (tmp_path / "plan.json").exists()


def test_prepare_update_workflow_uses_default_source_updater_command(tmp_path, monkeypatch) -> None:
    from app.update.manifest import build_manifest, manifest_to_json
    from app.update.verifier import sha256_file
    from app.update.workflow import prepare_update_from_manifest

    monkeypatch.setenv("TIGERCAPTURE_DATA_DIR", str(tmp_path / "data"))
    artifact = tmp_path / "TigerCapture-1.4.4.zip"
    manifest_path = tmp_path / "latest.json"
    artifact.write_bytes(b"payload")
    manifest = build_manifest(
        version="1.4.4",
        artifact_url=str(artifact),
        sha256=sha256_file(artifact),
        kind="portable_zip",
        filename=artifact.name,
    )
    manifest_path.write_text(manifest_to_json(manifest), encoding="utf-8")

    report = prepare_update_from_manifest(
        manifest_path,
        current_version="1.4.2",
        install_dir=tmp_path / "install",
        cache_dir=tmp_path / "cache",
        plan_path=tmp_path / "plan.json",
        kind="portable_zip",
    )

    command = report["updater_command"]
    assert report["ok"] is True
    assert command
    assert any("tigercapture_updater.py" in part or "TigerCaptureUpdater.exe" in part for part in command)
    assert "--wait-pid" in command


def test_build_portable_update_package_cli_writes_zip_and_manifest(tmp_path) -> None:
    from tools.build_portable_update_package import main

    dist = tmp_path / "dist" / "TigerCapture"
    dist.mkdir(parents=True)
    (dist / "TigerCapture.exe").write_text("app", encoding="utf-8")
    (dist / "TigerStudio.exe").write_text("studio", encoding="utf-8")
    (dist / "TigerCaptureUpdater.exe").write_text("updater", encoding="utf-8")
    (dist / "resources.dat").write_text("resource", encoding="utf-8")
    output = tmp_path / "TigerCapture-Portable-1.4.4.zip"
    manifest = tmp_path / "latest.json"

    import sys

    old_argv = sys.argv
    try:
        sys.argv = [
            "build_portable_update_package.py",
            "--dist-dir",
            str(dist),
            "--version",
            "1.4.4",
            "--output",
            str(output),
            "--manifest-output",
            str(manifest),
            "--artifact-url",
            "https://example.test/TigerCapture-Portable-1.4.4.zip",
        ]
        assert main() == 0
    finally:
        sys.argv = old_argv

    with zipfile.ZipFile(output, "r") as zf:
        names = set(zf.namelist())
    data = json.loads(manifest.read_text(encoding="utf-8"))

    assert "TigerCapture/TigerCapture.exe" in names
    assert "TigerCapture/TigerCaptureUpdater.exe" in names
    assert data["artifacts"][0]["kind"] == "portable_zip"
    assert data["artifacts"][0]["sha256"]
