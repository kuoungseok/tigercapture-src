from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.review_automation.dev_gate import require_review_automation_dev
from app.review_automation.paths import DEFAULT_REVIEW_ROOT, review_paths


def _options_namespace(
    *,
    deck_mode: str,
    build_html: bool,
    build_ppt: bool,
    run_qa: bool,
    run_review_qa: bool,
    force: bool,
    review_root: Path = DEFAULT_REVIEW_ROOT,
) -> SimpleNamespace:
    paths = review_paths(review_root)
    return SimpleNamespace(
        review_root=paths["root"],
        out_dir=paths["outputs"],
        report=paths["report"],
        sample_root=paths["samples"],
        sample_report=paths["sample_report"],
        run_qa=bool(run_qa),
        skip_html=not bool(build_html),
        skip_ppt=not bool(build_ppt),
        deck_mode=deck_mode,
        run_review_qa=bool(run_review_qa),
        manifest_only=False,
        force=bool(force),
    )


def _run_generation(options: SimpleNamespace) -> dict:
    from tools.generate_review_assets import generate_review_assets

    report = generate_review_assets(options)
    if options.run_review_qa:
        from app.review_automation.qa import validate_review_automation_report

        qa = validate_review_automation_report(options.report, project_root=ROOT)
        qa_path = review_paths(options.review_root)["qa_report"]
        qa_path.parent.mkdir(parents=True, exist_ok=True)
        qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def launch_dialog() -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLabel,
        QMessageBox,
        QVBoxLayout,
    )

    from app.review_automation.deck_modes import DECK_MODE_DESCRIPTIONS, DECK_MODE_LABELS

    app = QApplication.instance() or QApplication(sys.argv)
    dialog = QDialog()
    dialog.setWindowTitle("TigerCapture Review Automation")
    dialog.setMinimumWidth(520)

    layout = QVBoxLayout(dialog)
    title = QLabel("생성할 리뷰/PPT 버전을 선택하세요.")
    title.setStyleSheet("font-size: 18px; font-weight: 700;")
    layout.addWidget(title)

    desc = QLabel("요약, 상세, 증거 전체 모드를 같은 자동화 파이프라인에서 생성합니다.")
    desc.setWordWrap(True)
    layout.addWidget(desc)

    mode_combo = QComboBox()
    for mode in ("summary", "detailed", "evidence-full"):
        mode_combo.addItem(f"{DECK_MODE_LABELS[mode]} - {DECK_MODE_DESCRIPTIONS[mode]}", mode)
    mode_combo.setCurrentIndex(1)

    html_check = QCheckBox("HTML 사이트 생성")
    html_check.setChecked(True)
    ppt_check = QCheckBox("PPTX 덱 생성")
    ppt_check.setChecked(True)
    qa_check = QCheckBox("생성 후 리뷰 자동화 QA 실행")
    qa_check.setChecked(True)
    run_editor_qa_check = QCheckBox("먼저 Editor E2E Smoke QA 재실행")
    run_editor_qa_check.setChecked(False)
    force_check = QCheckBox("샘플/캡처 산출물 강제 재생성")
    force_check.setChecked(False)

    form = QFormLayout()
    form.addRow("Deck mode", mode_combo)
    form.addRow("", html_check)
    form.addRow("", ppt_check)
    form.addRow("", qa_check)
    form.addRow("", run_editor_qa_check)
    form.addRow("", force_check)
    layout.addLayout(form)

    hint = QLabel(
        f"출력 위치: {review_paths(DEFAULT_REVIEW_ROOT)['outputs']}\n"
        "상세/증거 전체 모드는 PPTX 파일명이 모드별로 분리됩니다."
    )
    hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    hint.setWordWrap(True)
    layout.addWidget(hint)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText("생성")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return 1

    options = _options_namespace(
        deck_mode=str(mode_combo.currentData()),
        build_html=html_check.isChecked(),
        build_ppt=ppt_check.isChecked(),
        run_qa=run_editor_qa_check.isChecked(),
        run_review_qa=qa_check.isChecked(),
        force=force_check.isChecked(),
    )

    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        report = _run_generation(options)
    except Exception as exc:
        QApplication.restoreOverrideCursor()
        QMessageBox.critical(dialog, "생성 실패", repr(exc))
        return 2
    finally:
        try:
            QApplication.restoreOverrideCursor()
        except Exception:
            pass

    outputs = report.get("outputs", {}) if isinstance(report, dict) else {}
    qa_text = f"\nQA: {review_paths(options.review_root)['qa_report']}" if qa_check.isChecked() else ""
    QMessageBox.information(
        dialog,
        "생성 완료",
        "리뷰 자동화 산출물을 생성했습니다.\n\n"
        f"Mode: {options.deck_mode}\n"
        f"HTML: {outputs.get('html', '-')}\n"
        f"PPTX: {outputs.get('pptx', '-')}\n"
        f"Report: {options.report}"
        f"{qa_text}",
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Open the TigerCapture review automation selection dialog.")
    parser.add_argument("--no-gui", action="store_true", help="Print a short help message instead of opening the dialog.")
    args = parser.parse_args()
    try:
        require_review_automation_dev(ROOT)
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.no_gui:
        print(
            "Use tools/generate_review_assets.py --deck-mode summary|detailed|evidence-full "
            f"for CLI generation. Review root: {DEFAULT_REVIEW_ROOT}"
        )
        return 0
    return launch_dialog()


if __name__ == "__main__":
    raise SystemExit(main())
