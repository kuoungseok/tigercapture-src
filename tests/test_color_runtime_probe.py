from __future__ import annotations

import json

from app.color_runtime_probe import (
    build_color_runtime_probe_report,
    write_color_runtime_probe_report,
)


def test_color_runtime_probe_executes_real_builtin_ocio(tmp_path) -> None:
    output = tmp_path / "probe.json"
    report = write_color_runtime_probe_report(output)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert report["ok"]
    assert saved["ok"]
    assert saved["ocio_version"] == "2.5.2"
    assert saved["builtin_config_count"] >= 2
    assert saved["plan"]["enabled"]
    assert saved["transform"]["engine"] == "ocio"
    assert saved["lut"]["exists"]
    assert saved["source_pixels"] != saved["output_pixels"]


def test_studio_entrypoint_has_headless_color_runtime_probe() -> None:
    import studio_main

    assert studio_main._consume_option_path(
        ["TigerStudio.exe", "--color-runtime-probe", "report.json"],
        "--color-runtime-probe",
    ).name == "report.json"
