from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
)
from app.i18n import tr


def _show_upsell(self, feature_id: str, feature_label: str) -> None:
    QMessageBox.information(
        self,
        tr("upsell.title"),
        tr("upsell.body", feature=feature_label),
    )


def _open_qa_dashboard(self) -> None:
    try:
        from app.qa_dashboard import QADashboardDialog

        dlg = QADashboardDialog(self)
        dlg.exec()
    except Exception as exc:
        self._flash_status(f"QA Dashboard failed: {exc}")


def _open_crash_report(self) -> None:
    try:
        from app.crash_report_dialog import CrashReportDialog
        from app.project_io import load_project, remember_last_project

        def _open_project(path: Path) -> None:
            load_project(self, path)
            self._project_path = path
            remember_last_project(path)
            self._refresh_window_title()
            self._flash_status(f"Opened recovery autosave: {path.name}")

        dlg = CrashReportDialog(self, open_project_callback=_open_project)
        dlg.exec()
    except Exception as exc:
        self._flash_status(f"Crash report failed: {exc}")


def _open_health_center(self) -> None:
    try:
        from app.health_center_dialog import HealthCenterDialog

        dlg = HealthCenterDialog(self)
        dlg.exec()
    except Exception as exc:
        self._flash_status(f"Health Center failed: {exc}")


def _show_productization_loop_report(self) -> None:
    try:
        from tools.qa_productization_loop import build_productization_report

        report = build_productization_report()
        out_dir = Path.cwd() / "debugCapture"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "productization_loop_qa.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except Exception as exc:
        self._flash_status(f"Productization loop failed: {exc}")
        return
    summary = dict(report.get("summary", {}) or {})
    lines = [
        f"Score: {report.get('score', 0)}/100",
        f"Passing: {summary.get('passing', 0)}/{summary.get('areas', 0)}",
        f"Needs attention: {summary.get('attention', 0)}",
        f"Report: {out_path}",
        "",
    ]
    for area in list(report.get("areas", []) or [])[:10]:
        if not isinstance(area, dict):
            continue
        mark = "OK" if area.get("ok") else "ATTN"
        lines.append(f"[{mark}] {area.get('label', area.get('id', 'area'))}: {area.get('summary', '')}")
    actions = list(report.get("next_actions", []) or [])
    if actions:
        lines.append("")
        lines.append("Next actions:")
        lines.extend(f"- {action}" for action in actions[:6])
    QMessageBox.information(self, "Productization Loop", "\n".join(lines))


def _refresh_actor_qa_badges(self) -> None:
    try:
        pool = getattr(self, "_media_pool", None)
        refresh = getattr(pool, "refresh_actor_qa_status", None)
        if callable(refresh):
            refresh()
            self._flash_status("Actor QA badges refreshed")
        else:
            self._flash_status("Media Pool actor QA refresh is unavailable")
    except Exception as exc:
        self._flash_status(f"Actor QA refresh failed: {exc}")


def _open_actor_qa_browser(self) -> None:
    try:
        from app.actor_qa_browser import ActorQABrowserDialog

        dlg = ActorQABrowserDialog(self)
        dlg.exec()
    except Exception as exc:
        self._flash_status(f"Actor QA Browser failed: {exc}")


def _open_actor_loading_manager(self) -> None:
    try:
        from app.actor_loading_manager import ActorLoadingManagerDialog

        dlg = ActorLoadingManagerDialog(self)
        dlg.exec()
    except Exception as exc:
        self._flash_status(f"Actor Loading Manager failed: {exc}")


def _color_audio_export_badge_note(self) -> str:
    path = Path("debugCapture/color_audio_accuracy_qa.json")
    if not path.exists():
        return "Color/Audio QA: no recent report. Run QA Dashboard > Color/Audio Accuracy before final delivery."
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "Color/Audio QA: latest report is unreadable."
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    samples = summary.get("sample_sources", {}) if isinstance(summary, dict) else {}
    sample_count = len(samples.get("video", []) or []) + len(samples.get("audio", []) or []) if isinstance(samples, dict) else 0
    status = "OK" if report.get("ok") else "FAIL"
    return (
        f"Color/Audio QA: {status} | checks={summary.get('checks', 0)} "
        f"failures={summary.get('failures', 0)} samples={sample_count}"
    )


def _audio_delivery_export_note(self) -> str:
    try:
        from app.render_queue_panel import audio_delivery_preflight_text_for_tracks

        measured = None
        mixer = getattr(self, "_audio_mixer_panel", None)
        meter = getattr(mixer, "_lufs_meter", None)
        if meter is not None:
            measured = {
                "integrated_lufs": float(getattr(meter, "_lufs", -14.0)),
                "true_peak_db": -1.0,
                "lra": 8.0,
            }
        return audio_delivery_preflight_text_for_tracks(
            list(getattr(self, "_audio_tracks", []) or []),
            measured=measured,
            target="shortform",
        )
    except Exception:
        return ""


def _show_preset_qa_report(self) -> None:
    from PySide6.QtWidgets import QListWidget, QListWidgetItem

    try:
        from app.preset_library import preset_ecosystem_report

        report = preset_ecosystem_report()
    except Exception as exc:
        self._flash_status(f"Preset QA failed: {exc}")
        return
    dlg = QDialog(self)
    dlg.setWindowTitle("Preset QA Report")
    dlg.resize(620, 460)
    root = QVBoxLayout(dlg)
    root.setContentsMargins(12, 12, 12, 12)
    score = int(report.get("score", 0) or 0)
    summary = QLabel(f"Preset QA score: {score}/100")
    summary.setStyleSheet("font-weight:900;font-size:14px;")
    root.addWidget(summary)
    issues = list(report.get("issues", []) or [])
    listw = QListWidget()
    if not issues:
        listw.addItem("No preset ecosystem issues found.")
    for issue in issues:
        sev = str(issue.get("severity", "info")).upper()
        text = f"[{sev}] {issue.get('message', '')}\n{issue.get('action', '')}"
        item = QListWidgetItem(text)
        item.setToolTip(json.dumps(issue, ensure_ascii=False, indent=2))
        listw.addItem(item)
    root.addWidget(listw, 1)
    close_btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_btns.rejected.connect(dlg.reject)
    root.addWidget(close_btns)
    dlg.exec()


def _show_preset_application_corpus_report(self) -> None:
    try:
        from tools.qa_preset_application_corpus import build_report, discover_project_files

        roots = [Path.cwd() / "qa_corpus" / "preset_application_samples", Path.cwd() / "qa_corpus", Path.cwd()]
        projects: list[Path] = []
        seen: set[Path] = set()
        for root in roots:
            for path in discover_project_files(root, limit=max(1, 5 - len(projects))):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                projects.append(path)
                if len(projects) >= 5:
                    break
            if len(projects) >= 5:
                break
        report = build_report(projects)
        out_dir = Path.cwd() / "debugCapture"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "preset_application_corpus_ui.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except Exception as exc:
        self._flash_status(f"Preset corpus QA failed: {exc}")
        return
    projects = list(report.get("projects", []) or [])
    parity_ok = sum(1 for row in projects if dict(row.get("export_parity", {}) or {}).get("ok"))
    blocked = [
        row for row in projects
        if not dict(row.get("export_parity", {}) or {}).get("ok")
    ]
    lines = [
        f"Projects: {len(projects)}",
        f"Template-first plans: {sum(1 for row in projects if row.get('template_first'))}/{len(projects)}",
        f"Export parity: {parity_ok}/{len(projects)}",
        f"Report: {out_path}",
    ]
    for row in projects[:5]:
        parity = dict(row.get("export_parity", {}) or {})
        lines.append(
            f"- {Path(str(row.get('path', ''))).name}: "
            f"{len(row.get('plan_ids', []) or [])} preset(s), "
            f"bake {', '.join(parity.get('bake_targets', []) or []) or 'none'}"
        )
    for row in blocked[:3]:
        parity = dict(row.get("export_parity", {}) or {})
        lines.append(f"Blocked: {Path(str(row.get('path', ''))).name} -> {', '.join(parity.get('unknown_kinds', []) or [])}")
    QMessageBox.information(self, "Preset Application Corpus", "\n".join(lines))
