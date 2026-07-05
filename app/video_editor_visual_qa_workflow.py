from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

def _open_visual_qa_viewer(self) -> None:
        from PySide6.QtWidgets import QListWidget, QListWidgetItem

        root_dir = Path.cwd() / "debugCapture"
        report_files: list[Path] = []
        if root_dir.exists():
            report_files.extend(root_dir.glob("**/visual_regression_report.json"))
            report_files.extend(root_dir.glob("**/layout_report.json"))
        dirs = sorted({path.parent for path in report_files}, key=lambda p: str(p).casefold())

        dlg = QDialog(self)
        dlg.setWindowTitle("Visual QA Viewer")
        dlg.resize(820, 540)
        root = QHBoxLayout(dlg)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        listw = QListWidget()
        root.addWidget(listw, 1)

        right = QVBoxLayout()
        preview = QLabel("No QA capture selected")
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumSize(420, 260)
        preview.setStyleSheet("background:#1B202A;border:1px solid #3A4355;border-radius:12px;color:#A7ADC2;")
        info = QLabel("")
        info.setWordWrap(True)
        info.setStyleSheet("color:#A7ADC2;font-size:10px;")
        right.addWidget(preview, 1)
        right.addWidget(info)
        btns = QHBoxLayout()
        open_btn = QPushButton("Open Folder")
        approve_btn = QPushButton("Approve Baseline")
        refresh_btn = QPushButton("Refresh")
        close_btn = QPushButton("Close")
        for btn in (open_btn, approve_btn, refresh_btn, close_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btns.addWidget(open_btn)
        btns.addWidget(approve_btn)
        btns.addWidget(refresh_btn)
        btns.addStretch(1)
        btns.addWidget(close_btn)
        right.addLayout(btns)
        root.addLayout(right, 2)

        def _load_dirs() -> None:
            listw.clear()
            fresh_files: list[Path] = []
            if root_dir.exists():
                fresh_files.extend(root_dir.glob("**/visual_regression_report.json"))
                fresh_files.extend(root_dir.glob("**/layout_report.json"))
            fresh_dirs = sorted({path.parent for path in fresh_files}, key=lambda p: str(p).casefold())
            if not fresh_dirs:
                listw.addItem("No visual QA reports found")
                return
            for folder in fresh_dirs:
                item = QListWidgetItem(str(folder.relative_to(root_dir)))
                item.setData(Qt.ItemDataRole.UserRole, str(folder))
                listw.addItem(item)
            listw.setCurrentRow(0)

        def _selected_folder() -> Path | None:
            item = listw.currentItem()
            if item is None:
                return None
            value = item.data(Qt.ItemDataRole.UserRole)
            if not value:
                return None
            return Path(str(value))

        def _show_selected() -> None:
            folder = _selected_folder()
            if folder is None:
                return
            images = sorted(folder.glob("*.png"))
            pix = QPixmap(str(images[0])) if images else QPixmap()
            if not pix.isNull():
                preview.setPixmap(pix.scaled(
                    preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
            else:
                preview.setText("No PNG preview in this QA folder")
                preview.setPixmap(QPixmap())
            report_bits: list[str] = []
            for name in ("visual_regression_report.json", "layout_report.json"):
                path = folder / name
                if not path.exists():
                    continue
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    report_bits.append(f"{name}: {json.dumps(raw, ensure_ascii=False, default=str)[:520]}")
                except Exception:
                    report_bits.append(f"{name}: unreadable")
            info.setText("\n".join(report_bits) if report_bits else str(folder))

        def _approve_selected() -> None:
            folder = _selected_folder()
            if folder is None or not folder.exists():
                self._flash_status("Select a QA capture before approving a baseline")
                return
            snapshot = folder / "current_snapshot.json"
            if snapshot.exists():
                try:
                    from tools.qa_visual_baseline_manager import approve_latest_visual_baseline

                    report = approve_latest_visual_baseline(snapshot_path=snapshot)
                    if not report.get("ok"):
                        self._flash_status(f"Baseline approval failed: {report.get('error', 'unknown error')}")
                        return
                    self._flash_status(
                        f"Approved visual baseline: {Path(str(report.get('baseline', 'baseline'))).name} "
                        f"({report.get('screenshot_count', 0)} image(s))"
                    )
                    return
                except Exception as exc:
                    self._flash_status(f"Baseline approval failed: {exc}")
                    return
            try:
                rel = folder.relative_to(root_dir)
            except Exception:
                rel = Path(folder.name)
            target_name = "__".join(part for part in rel.parts if part and part != ".") or folder.name
            target = root_dir / "baselines" / target_name
            try:
                target.mkdir(parents=True, exist_ok=True)
                copied: list[str] = []
                for old in target.glob("*"):
                    if old.is_file() and old.suffix.casefold() in {".png", ".json"}:
                        old.unlink()
                for src in sorted(folder.iterdir()):
                    if src.is_file() and src.suffix.casefold() in {".png", ".json"}:
                        dst = target / src.name
                        shutil.copy2(src, dst)
                        copied.append(src.name)
                manifest = {
                    "approved_at": datetime.now().isoformat(timespec="seconds"),
                    "source": str(folder),
                    "files": copied,
                }
                (target / "baseline_manifest.json").write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self._flash_status(f"Approved visual baseline: {target.name} ({len(copied)} file(s))")
            except Exception as exc:
                self._flash_status(f"Baseline approval failed: {exc}")

        listw.currentItemChanged.connect(lambda *_: _show_selected())
        refresh_btn.clicked.connect(_load_dirs)
        approve_btn.clicked.connect(_approve_selected)
        close_btn.clicked.connect(dlg.reject)
        open_btn.clicked.connect(lambda: os.startfile(str(_selected_folder())) if _selected_folder() is not None and os.name == "nt" else None)
        _load_dirs()
        dlg.exec()
