from __future__ import annotations

import subprocess
import sys


def test_series_orchestrator_routes_acceptance_and_reapproval_to_versioned_dir(
    tmp_path, monkeypatch
) -> None:
    import tools.run_painter_long_soak_series as module

    seed = tmp_path / "raw.json"
    seed.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "series-output"
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_painter_long_soak_series.py",
            str(seed),
            "--additional-runs",
            "0",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert module.main() == 0
    acceptance = commands[0]
    reapproval = commands[1]
    series_report = output_dir.resolve() / "series_acceptance_report.json"
    assert acceptance[-2:] == ["--output", str(series_report)]
    assert reapproval[-4:] == [
        "--soak-series",
        str(series_report),
        "--output",
        str(output_dir.resolve() / "product_reapproval_report.json"),
    ]


def test_watch_orchestrator_routes_single_soak_and_reapproval_to_versioned_dir(
    tmp_path, monkeypatch
) -> None:
    import tools.watch_painter_long_soak as module

    raw = tmp_path / "raw.json"
    raw.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "watch-output"
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "watch_painter_long_soak.py",
            str(raw),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert module.main() == 0
    acceptance_report = output_dir.resolve() / "long_soak_acceptance_report.json"
    assert commands[0][-2:] == ["--output", str(acceptance_report)]
    assert commands[1][-4:] == [
        "--soak",
        str(acceptance_report),
        "--output",
        str(output_dir.resolve() / "product_reapproval_report.json"),
    ]
