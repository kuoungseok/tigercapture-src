"""Shared presentation control for Painter container-to-UMG panel policy."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from app.painter_ui_auto_layout import normalize_ui_auto_layout


_PANEL_MODES = {"auto", "overlay", "canvas"}
_LAYOUT_PANEL_KINDS = {
    "horizontal": "Horizontal",
    "vertical": "Vertical",
    "grid": "Grid",
    "overlay": "Overlay",
}


def _normalized_panel_mode(value: Any) -> str:
    mode = str(value or "auto").strip().casefold()
    return mode if mode in _PANEL_MODES else "auto"


def _classification(
    document: Mapping[str, Any] | None,
    row: Mapping[str, Any] | None,
    *,
    normalize: bool = True,
) -> dict[str, Any]:
    """Read the adapter-owned panel decision without duplicating its policy."""

    source = row if isinstance(row, Mapping) else {}
    object_id = str(source.get("id") or "")
    child_count = sum(
        1
        for item in (
            document.get("objects", [])
            if isinstance(document, Mapping)
            else []
        )
        if isinstance(item, Mapping)
        and str(item.get("parent_id") or "") == object_id
    )
    layout = normalize_ui_auto_layout(source.get("layout"))
    requested = _normalized_panel_mode(layout.get("umg_panel_mode"))
    decision: Mapping[str, Any] = {}
    if object_id and isinstance(document, Mapping):
        from app.painter_ui_umg_auto_layout import (
            painter_umg_auto_layout_contract,
        )

        contract = painter_umg_auto_layout_contract(document, normalize=normalize)
        rows = contract.get("classification_by_id")
        if isinstance(rows, Mapping):
            candidate = rows.get(object_id)
            if isinstance(candidate, Mapping):
                decision = candidate

    layout_mode = str(layout.get("mode") or "none")
    effective = str(
        decision.get("effective")
        or _LAYOUT_PANEL_KINDS.get(layout_mode)
        or (requested.title() if requested != "auto" else "Canvas")
    ).title()
    policy = str(
        decision.get("policy")
        or ("layout" if layout_mode in _LAYOUT_PANEL_KINDS else requested)
    )
    reasons_value = decision.get("reasons")
    if isinstance(reasons_value, (list, tuple)):
        reasons = [str(value) for value in reasons_value if str(value)]
    elif reasons_value:
        reasons = [str(reasons_value)]
    else:
        reasons = []
    result = {
        "requested": _normalized_panel_mode(
            decision.get("requested") or requested
        ),
        "effective": effective,
        "policy": policy,
        "reasons": reasons,
        "layout_mode": layout_mode,
        "child_count": child_count,
    }
    if not child_count:
        # A PanelWidget only matters as a host for child slots.  Painted leaf
        # frames are promoted to Image/Material by the adapter, so presenting
        # the policy candidate as a live Overlay here would be misleading.
        result.update(
            {
                "effective": "None",
                "policy": "not_applicable",
                "reasons": ["container_has_no_children"],
            }
        )
    return result


def _decision_text(decision: Mapping[str, Any]) -> tuple[str, str]:
    requested = str(decision.get("requested") or "auto")
    effective = str(decision.get("effective") or "Canvas")
    layout_mode = str(decision.get("layout_mode") or "none")
    if int(decision.get("child_count") or 0) == 0:
        status = "자식 없음 · 패널 미사용"
        hint = (
            "직계 자식이 없어 PanelKind를 사용하지 않습니다. 자식을 추가하면 "
            "Auto/Overlay/Canvas 분류와 선택이 활성화됩니다."
        )
    elif layout_mode in _LAYOUT_PANEL_KINDS:
        status = f"레이아웃 → {effective}"
        hint = (
            f"{layout_mode.title()} 레이아웃이 UMG {effective} 패널을 "
            "고정합니다. 자유 배치로 바꾸면 Auto/Overlay/Canvas를 "
            "직접 선택할 수 있습니다."
        )
    elif requested == "auto" and effective == "Overlay":
        status = "Auto → Overlay"
        hint = (
            "직계 자식 앵커를 UOverlaySlot 정렬과 Padding으로 손실 없이 "
            "표현할 수 있어 Overlay로 자동 분류했습니다."
        )
    elif requested == "auto":
        status = f"Auto → {effective}"
        hint = (
            "Scale/Custom 앵커 또는 자유 좌표 배치가 있어 CanvasPanel로 "
            "자동 분류했습니다."
            if effective == "Canvas"
            else f"자식 레이아웃을 분석해 {effective} 패널로 자동 분류했습니다."
        )
    else:
        status = f"수동 → {effective}"
        incompatible_overlay = bool(
            requested == "overlay"
            and any(
                "requires_canvas" in str(reason)
                for reason in decision.get("reasons", [])
            )
        )
        hint = (
            "Overlay 선택은 유지되지만 Scale/Custom 자식 앵커를 "
            "UOverlaySlot으로 표현할 수 없어 UMG 변환이 차단됩니다. "
            "Canvas를 선택하거나 자식 앵커를 바꾸세요."
            if incompatible_overlay
            else f"사용자가 {effective} 패널로 고정했습니다. Auto로 바꾸면 "
            "직계 자식 앵커를 다시 판정합니다."
        )
    return status, hint


class PainterUIUMGPanelSelector(QFrame):
    """Auto/manual PanelKind selector shared by Inspector and UMG View."""

    mode_changed = Signal(str)

    def __init__(
        self,
        parent=None,
        *,
        show_title: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIUMGPanelSelector")
        self._syncing = False
        self._decision: dict[str, Any] = {}
        self._row: dict[str, Any] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(3)
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)
        self.title_label = QLabel("UMG 패널", self)
        self.title_label.setObjectName("PainterUIUMGPanelTitle")
        self.title_label.setVisible(bool(show_title))
        row_layout.addWidget(self.title_label)
        self.mode_combo = QComboBox(self)
        self.mode_combo.setObjectName("PainterUIUMGPanelModeCombo")
        for label, value in (
            ("Auto (권장)", "auto"),
            ("Overlay", "overlay"),
            ("Canvas", "canvas"),
        ):
            self.mode_combo.addItem(label, value)
        self.mode_combo.setToolTip(
            "Auto는 자식 앵커를 분석합니다. Overlay/Canvas는 이 컨테이너의 "
            "UMG PanelKind를 수동으로 고정합니다."
        )
        self.mode_combo.currentIndexChanged.connect(self._emit_mode)
        row_layout.addWidget(self.mode_combo)
        self.effective_label = QLabel("Auto → Canvas", self)
        self.effective_label.setObjectName("PainterUIUMGPanelEffective")
        row_layout.addWidget(self.effective_label, 1)
        root.addLayout(row_layout)
        self.reason_label = QLabel(self)
        self.reason_label.setObjectName("PainterUIUMGPanelReason")
        self.reason_label.setWordWrap(True)
        root.addWidget(self.reason_label)
        # Stay out of the layout until a structural container is selected.
        self.hide()

    def set_context(
        self,
        document: Mapping[str, Any] | None,
        row: Mapping[str, Any] | None,
        *,
        editable: bool = True,
        normalize: bool = True,
    ) -> None:
        self._row = copy.deepcopy(dict(row or {}))
        is_container = str(self._row.get("kind") or "") in {
            "frame",
            "group",
        }
        self._decision = _classification(document, row, normalize=normalize)
        requested = str(self._decision["requested"])
        layout_mode = str(self._decision["layout_mode"])
        self._syncing = True
        previous = self.mode_combo.blockSignals(True)
        try:
            index = self.mode_combo.findData(requested)
            self.mode_combo.setCurrentIndex(max(0, index))
        finally:
            self.mode_combo.blockSignals(previous)
            self._syncing = False
        priority_layout = layout_mode in _LAYOUT_PANEL_KINDS
        self.mode_combo.setEnabled(
            bool(
                is_container
                and editable
                and not priority_layout
                and int(self._decision.get("child_count") or 0) > 0
            )
        )
        status, hint = _decision_text(self._decision)
        diagnostic = hint
        reasons = [str(value) for value in self._decision.get("reasons", [])]
        if reasons:
            diagnostic += "\n진단 코드: " + ", ".join(reasons)
        self.effective_label.setText(status)
        self.effective_label.setToolTip(diagnostic)
        self.reason_label.setText(hint)
        self.reason_label.setToolTip(diagnostic)
        self.setVisible(is_container)

    def _emit_mode(self, _index: int) -> None:
        if self._syncing or not self.mode_combo.isEnabled():
            return
        self.mode_changed.emit(
            _normalized_panel_mode(self.mode_combo.currentData())
        )

    def state(self) -> dict[str, Any]:
        return {
            **copy.deepcopy(self._decision),
            "enabled": self.mode_combo.isEnabled(),
            "visible": not self.isHidden(),
            "status": self.effective_label.text(),
            "reason_text": self.reason_label.text(),
        }


__all__ = ["PainterUIUMGPanelSelector"]
