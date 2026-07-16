"""Unreal Engine bridge entry points for the editor shell."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from app.unreal_link_reference_paths import format_unreal_link_reference_report


def open_unreal_engine_link(self) -> None:
    QMessageBox.information(
        self,
        "언리얼 엔진 링크",
        "언리얼 엔진 링크는 크리에이터 도구 진입점으로 준비되어 있습니다.\n\n"
        "다음 단계: Unreal 프로젝트/에디터 감지, 캡처 세션, 에셋 브리지 워크플로우를 연결합니다.\n\n"
        f"{format_unreal_link_reference_report()}",
    )


__all__ = ["open_unreal_engine_link"]
