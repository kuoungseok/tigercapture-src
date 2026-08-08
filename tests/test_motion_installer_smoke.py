from __future__ import annotations

import json

from tools.qa_motion_installer_smoke import _load_frozen_runtime_identity


def test_installer_smoke_loads_frozen_runtime_identity(tmp_path) -> None:
    report_path = tmp_path / "runtime.json"
    identity = {
        "frozen": True,
        "executable": "TigerStudio.exe",
        "executable_size_bytes": 123,
        "executable_sha256": "a" * 64,
    }
    report_path.write_text(
        json.dumps({"runtime_identity": identity}),
        encoding="utf-8",
    )

    loaded, modified = _load_frozen_runtime_identity(report_path)

    assert loaded == identity
    assert modified == report_path.stat().st_mtime


def test_installer_smoke_rejects_missing_runtime_identity(tmp_path) -> None:
    report_path = tmp_path / "runtime.json"
    report_path.write_text("{}", encoding="utf-8")

    loaded, modified = _load_frozen_runtime_identity(report_path)

    assert loaded == {}
    assert modified == report_path.stat().st_mtime
