"""FP1 local Figma plugin manager; package metadata only, no code execution."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.painter_ui_figma_plugin_registry import PainterFigmaPluginRegistry


def map_plugin_drop_to_active_artboard(
    owner: QWidget,
    payload: Mapping[str, Any],
    *,
    global_position=None,
) -> dict[str, Any] | None:
    """Map a UI drag only when it lands on the active Painter artboard."""
    overlay = getattr(owner, "_painter_ui_overlay", None)
    if overlay is None or not hasattr(overlay, "artboard_point_at"):
        return dict(payload)
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QCursor

    screen_point = global_position if global_position is not None else QCursor.pos()
    local = overlay.mapFromGlobal(screen_point)
    hit = overlay.artboard_point_at(QPointF(local))
    if hit is None:
        return None
    artboard_id, point = hit
    document = getattr(owner, "_painter_ui_document", {})
    if str(artboard_id) != str(document.get("active_artboard_id") or ""):
        return None
    return {
        **dict(payload),
        "absoluteX": float(point.x()),
        "absoluteY": float(point.y()),
    }


class PainterFigmaPluginManagerDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, registry=None) -> None:
        super().__init__(parent)
        self.registry = registry or PainterFigmaPluginRegistry()
        self.setObjectName("PainterFigmaPluginManagerDialog")
        self.setWindowTitle("로컬 Figma 플러그인")
        self.resize(720, 470)

        layout = QVBoxLayout(self)
        title = QLabel("로컬 Figma 플러그인")
        title.setStyleSheet("font-size: 18px; font-weight: 650;")
        layout.addWidget(title)
        policy = QLabel(
            "FP2 headless 또는 FP3 제한 UI를 별도 프로세스에서 실행합니다. "
            "원격 도메인은 실행할 때마다 명시적으로 승인해야 합니다."
        )
        policy.setObjectName("PainterFigmaPluginRuntimePolicy")
        policy.setWordWrap(True)
        layout.addWidget(policy)
        self.runtime_status = QLabel("실행할 플러그인을 선택하세요.")
        self.runtime_status.setObjectName("PainterFigmaPluginRuntimeStatus")
        self.runtime_status.setWordWrap(True)
        self.runtime_status.setAccessibleName("Figma 플러그인 실행 상태")
        layout.addWidget(self.runtime_status)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.plugin_list = QListWidget()
        self.plugin_list.setObjectName("PainterFigmaPluginList")
        self.details = QTextBrowser()
        self.details.setObjectName("PainterFigmaPluginDetails")
        splitter.addWidget(self.plugin_list)
        splitter.addWidget(self.details)
        splitter.setSizes([250, 450])
        layout.addWidget(splitter, 1)

        buttons = QHBoxLayout()
        self.install_button = QPushButton("manifest에서 설치...")
        self.run_button = QPushButton("실행")
        self.run_button.setObjectName("PainterFigmaPluginRunButton")
        self.run_button.setEnabled(False)
        self.run_ui_button = QPushButton("UI 실행")
        self.run_ui_button.setObjectName("PainterFigmaPluginUIRunButton")
        self.run_ui_button.setEnabled(False)
        self.remove_button = QPushButton("제거")
        self.remove_button.setEnabled(False)
        close_button = QPushButton("닫기")
        buttons.addWidget(self.install_button)
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.run_ui_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self.plugin_list.currentItemChanged.connect(self._show_current)
        self.install_button.clicked.connect(self._choose_install)
        self.run_button.clicked.connect(self._run_current)
        self.run_ui_button.clicked.connect(self._run_current_ui)
        self.remove_button.clicked.connect(self._remove_current)
        close_button.clicked.connect(self.accept)
        self.refresh()

    def refresh(self) -> None:
        selected = self.current_plugin_id()
        report = self.registry.list()
        self.plugin_list.clear()
        for row in report["plugins"]:
            label = row["name"] or row["id"] or "손상된 플러그인"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, row)
            if not row["valid"]:
                item.setText(f"⚠ {label}")
            self.plugin_list.addItem(item)
            if selected and row["id"] == selected:
                self.plugin_list.setCurrentItem(item)
        if self.plugin_list.currentItem() is None and self.plugin_list.count():
            self.plugin_list.setCurrentRow(0)
        if not self.plugin_list.count():
            self.details.setPlainText(
                "설치된 로컬 Figma 플러그인이 없습니다.\n\n"
                "manifest.json을 선택하면 안전성 및 호환성 검사를 거친 뒤 복사합니다."
            )
            self.remove_button.setEnabled(False)
            self.run_button.setEnabled(False)
            self.run_ui_button.setEnabled(False)

    def current_plugin_id(self) -> str:
        item = self.plugin_list.currentItem()
        row = item.data(Qt.ItemDataRole.UserRole) if item is not None else {}
        return str((row or {}).get("id") or "")

    def _show_current(self, current, _previous) -> None:
        row = current.data(Qt.ItemDataRole.UserRole) if current is not None else {}
        row = dict(row or {})
        blockers = "\n".join(f"• {item}" for item in row.get("blockers", [])) or "• 없음"
        errors = "\n".join(f"• {item}" for item in row.get("errors", [])) or "• 없음"
        domains = list(row.get("allowed_domains") or [])
        network = "차단" if not domains or domains == ["none"] else ", ".join(domains)
        self.details.setPlainText(
            f"{row.get('name') or '-'}\n"
            f"ID: {row.get('id') or '-'}\n"
            f"API: {row.get('api') or '-'}\n"
            f"상태: {'manifest 정상' if row.get('valid') else '설치 손상'}\n"
            f"실행: {'FP3 제한 UI 브리지' if row.get('ui_runtime_ready') else 'FP2 기본 API 샌드박스'}\n"
            f"네트워크: {network}\n"
            f"경로: {row.get('plugin_root') or '-'}\n\n"
            f"preflight 참고\n{blockers}\n\n오류\n{errors}"
        )
        root = Path(str(row.get("plugin_root") or "")).resolve(strict=False)
        self.remove_button.setEnabled(bool(row) and root.parent == self.registry.install_root)
        self.run_button.setEnabled(bool(row.get("runtime_ready")))
        self.run_ui_button.setEnabled(bool(row.get("ui_runtime_ready")))
        if row:
            self._set_runtime_status(
                "ready" if row.get("runtime_ready") or row.get("ui_runtime_ready") else "blocked",
                (
                    "UI 실행 준비됨" if row.get("ui_runtime_ready") else
                    "실행 준비됨" if row.get("runtime_ready") else
                    "preflight 차단됨"
                ),
            )

    def _set_runtime_status(self, state: str, message: str) -> None:
        palette = {
            "ready": ("#E8F3FF", "#0969DA"),
            "success": ("#E9F7EF", "#137333"),
            "error": ("#FDECEC", "#B3261E"),
            "blocked": ("#FFF4E5", "#8A4B08"),
        }
        background, foreground = palette.get(state, ("#F2F2F2", "#444444"))
        self.runtime_status.setProperty("runtimeState", state)
        self.runtime_status.setText(str(message))
        self.runtime_status.setStyleSheet(
            f"padding: 7px 9px; border-radius: 6px; "
            f"background: {background}; color: {foreground}; font-weight: 600;"
        )

    def _choose_install(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Figma plugin manifest 선택", "", "Figma manifest (manifest.json);;JSON (*.json)"
        )
        if not path:
            return
        try:
            self.registry.install(path)
        except Exception as exc:
            QMessageBox.warning(self, "설치할 수 없음", str(exc))
            return
        self.refresh()

    def _remove_current(self) -> None:
        plugin_id = self.current_plugin_id()
        if not plugin_id:
            return
        if QMessageBox.question(
            self,
            "플러그인 제거",
            f"{plugin_id}의 로컬 복사본을 제거할까요?",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.registry.remove(plugin_id)
        except Exception as exc:
            QMessageBox.warning(self, "제거할 수 없음", str(exc))
            return
        self.refresh()

    def _run_current(self) -> bool:
        plugin_id = self.current_plugin_id()
        owner = self.parentWidget()
        if not plugin_id or owner is None or not hasattr(owner, "_painter_ui_document"):
            self._set_runtime_status("error", "실행 실패 · Painter UI 문서를 찾을 수 없습니다.")
            return False
        self._set_runtime_status("ready", "실행 중…")
        try:
            from app.painter_ui_figma_plugin_runtime import run_installed_figma_plugin

            document, report = run_installed_figma_plugin(
                self.registry, plugin_id, owner._painter_ui_document
            )
        except Exception as exc:
            self._set_runtime_status("error", f"실행 실패 · {exc}")
            QMessageBox.warning(self, "플러그인 실행 실패", str(exc))
            return False
        owner._push_undo_state("Run Figma plugin")
        owner._painter_ui_document = document
        owner._painter_document_dirty = True
        refresh = getattr(owner, "_refresh_painter_ui_overlay", None)
        if callable(refresh):
            refresh()
        self.details.append(
            f"\n실행 완료 · 생성 {len(report['created_object_ids'])}개"
        )
        self._set_runtime_status(
            "success", f"실행 완료 · 생성 {len(report['created_object_ids'])}개 · Undo 가능"
        )
        return True

    def _run_current_ui(self) -> bool:
        plugin_id = self.current_plugin_id()
        owner = self.parentWidget()
        if not plugin_id or owner is None or not hasattr(owner, "_painter_ui_document"):
            self._set_runtime_status("error", "UI 실행 실패 · Painter UI 문서를 찾을 수 없습니다.")
            return False
        try:
            inspected = self.registry.inspect(plugin_id)
            if not inspected.get("ui_runtime_ready"):
                raise ValueError("Plugin UI preflight did not pass")
            validation = dict(inspected["validation"])
            plugin = dict(validation["plugin"])
            allowed_domains = self._approve_network_domains(plugin)
            if allowed_domains is None:
                self._set_runtime_status("blocked", "Plugin UI 실행 취소 · 네트워크 승인 안 함")
                return False
            root = Path(validation["plugin_root"])
            ui_entries = dict(plugin.get("ui") or {})
            default_name = ui_entries.get("default") or next(iter(ui_entries.values()))
            ui_files = {
                key: (root / value).read_text(encoding="utf-8")
                for key, value in ui_entries.items()
            }
            from app.painter_ui_figma_plugin_ui_dialog import PainterFigmaPluginUIDialog
            from app.painter_ui_figma_plugin_ui_session import PainterFigmaPluginUISession

            session = PainterFigmaPluginUISession(
                (root / plugin["main"]).read_text(encoding="utf-8"),
                (root / default_name).read_text(encoding="utf-8"),
                plugin_name=str(plugin.get("name") or plugin_id),
                ui_files=ui_files,
                document=owner._painter_ui_document,
            )
            undo_pushed = [False]

            def apply_document_event(event) -> None:
                document, report = session.apply_event(owner._painter_ui_document, event)
                changed = (
                    document.get("objects") != owner._painter_ui_document.get("objects")
                    or document.get("selection") != owner._painter_ui_document.get("selection")
                )
                if not changed:
                    return
                if not undo_pushed[0]:
                    owner._push_undo_state("Run Figma UI plugin")
                    undo_pushed[0] = True
                owner._painter_ui_document = document
                owner._painter_document_dirty = True
                refresh = getattr(owner, "_refresh_painter_ui_overlay", None)
                if callable(refresh):
                    refresh()
                created = len(report.get("created_object_ids") or [])
                if created:
                    self.details.append(f"\nUI 문서 반영 · 생성 {created}개")

            def map_plugin_drop(payload):
                mapped = map_plugin_drop_to_active_artboard(owner, payload)
                if mapped is None:
                    self._set_runtime_status(
                        "blocked", "Plugin drop 무시 · 활성 Painter 아트보드 위에 놓으세요."
                    )
                return mapped

            dialog = PainterFigmaPluginUIDialog(
                session,
                self,
                document_callback=apply_document_event,
                allowed_domains=allowed_domains,
                drop_position_callback=map_plugin_drop,
            )
            dialog.runtimeFailed.connect(
                lambda message: self._set_runtime_status(
                    "error", f"Plugin UI 실행 실패 · {message}"
                )
            )
            dialogs = getattr(self, "_plugin_ui_dialogs", [])
            dialogs.append(dialog)
            self._plugin_ui_dialogs = dialogs
            dialog.destroyed.connect(
                lambda *_args, target=dialog: self._plugin_ui_dialogs.remove(target)
                if target in self._plugin_ui_dialogs else None
            )
            dialog.show()
        except Exception as exc:
            self._set_runtime_status("error", f"UI 실행 실패 · {exc}")
            QMessageBox.warning(self, "플러그인 UI 실행 실패", str(exc))
            return False
        network_status = (
            f"승인 도메인 {len(allowed_domains)}개" if allowed_domains else "외부 네트워크 차단"
        )
        self._set_runtime_status("success", f"Plugin UI 실행 중 · {network_status}")
        return True

    def _approve_network_domains(self, plugin: dict) -> tuple[str, ...] | None:
        domains = tuple(str(item) for item in plugin.get("allowed_domains") or ())
        if not domains or domains == ("none",):
            return ()
        reasoning = str(plugin.get("network_reasoning") or "").strip() or "제공된 사유 없음"
        domain_lines = "\n".join(f"• {domain}" for domain in domains)
        wildcard_warning = (
            "\n\n주의: 모든 외부 도메인(*) 접근을 요청합니다." if "*" in domains else ""
        )
        answer = QMessageBox.question(
            self,
            "Plugin UI 네트워크 승인",
            "이 실행에서만 다음 원격 접근을 허용할까요?\n\n"
            f"{domain_lines}\n\n요청 사유: {reasoning}{wildcard_warning}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return domains if answer == QMessageBox.StandardButton.Yes else None


def show_painter_figma_plugin_manager(parent: QWidget) -> int:
    dialog = PainterFigmaPluginManagerDialog(parent)
    return dialog.exec()


__all__ = [
    "PainterFigmaPluginManagerDialog",
    "map_plugin_drop_to_active_artboard",
    "show_painter_figma_plugin_manager",
]
