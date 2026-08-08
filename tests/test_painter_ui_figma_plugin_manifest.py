from __future__ import annotations

import json
from pathlib import Path

from app.painter_ui_figma_plugin_manifest import validate_figma_plugin_manifest


def _write_plugin(
    root: Path,
    *,
    plugin_id: str = "1234567890123456789",
    extra: dict | None = None,
) -> Path:
    root.mkdir(parents=True)
    (root / "code.js").write_text(
        "throw new Error('FP1 must never execute this file');\n",
        encoding="utf-8",
    )
    (root / "ui.html").write_text("<p>QA</p>\n", encoding="utf-8")
    manifest = {
        "name": "Painter FP1 QA",
        "id": plugin_id,
        "api": "1.0.0",
        "editorType": ["figma"],
        "main": "code.js",
        "ui": "ui.html",
        "documentAccess": "dynamic-page",
        "networkAccess": {"allowedDomains": ["none"]},
    }
    manifest.update(extra or {})
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_figma_plugin_manifest_is_metadata_only_and_never_runtime_ready(tmp_path: Path) -> None:
    report = validate_figma_plugin_manifest(_write_plugin(tmp_path / "plugin"))

    assert report["ok"] is True
    assert report["installable"] is True
    assert report["runtime_ready"] is False
    assert report["runtime_policy"] == "metadata_only_no_code_execution"
    assert report["plugin"]["capabilities"] == ["manifest", "main", "ui"]
    assert any("FP2" in item for item in report["warnings"])


def test_figma_plugin_manifest_rejects_path_escape_and_missing_entry(tmp_path: Path) -> None:
    outside = tmp_path / "outside.js"
    outside.write_text("", encoding="utf-8")
    path = _write_plugin(tmp_path / "plugin", extra={"main": "../outside.js"})

    report = validate_figma_plugin_manifest(path)

    assert report["ok"] is False
    assert report["installable"] is False
    assert any("unsafe" in item for item in report["errors"])


def test_figma_plugin_manifest_reports_unsupported_host_capabilities(tmp_path: Path) -> None:
    path = _write_plugin(
        tmp_path / "plugin",
        extra={
            "enablePrivatePluginApi": True,
            "enableProposedApi": True,
            "permissions": ["teamlibrary"],
            "networkAccess": {"allowedDomains": ["https://example.com"]},
        },
    )

    report = validate_figma_plugin_manifest(path)

    assert report["ok"] is True
    assert report["compatibility"] == "blocked"
    assert "network" in report["plugin"]["capabilities"]
    assert "permissions" in report["plugin"]["capabilities"]
    assert any("Private" in item for item in report["blockers"])
    assert any("Proposed" in item for item in report["blockers"])
    assert report["plugin"]["network_approval_required"] is True
    assert report["plugin"]["allowed_domains"] == ["https://example.com"]
    assert any("explicit approval" in item for item in report["warnings"])


def test_figma_plugin_manifest_validates_network_reasoning_and_none(tmp_path: Path) -> None:
    wildcard = _write_plugin(
        tmp_path / "wildcard",
        extra={"networkAccess": {"allowedDomains": ["*"]}},
    )
    wildcard_report = validate_figma_plugin_manifest(wildcard)
    assert wildcard_report["ok"] is False
    assert any("reasoning" in item for item in wildcard_report["errors"])

    mixed = _write_plugin(
        tmp_path / "mixed",
        extra={"networkAccess": {"allowedDomains": ["none", "example.com"]}},
    )
    mixed_report = validate_figma_plugin_manifest(mixed)
    assert mixed_report["ok"] is False
    assert any("used alone" in item for item in mixed_report["errors"])
