from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QMenu

from app import tier
from app.i18n import tr
from app.style import (
    COLOR_ACCENT_BLUE,
    COLOR_BG_L3,
    COLOR_BG_L5,
    COLOR_BORDER_DEFAULT,
    COLOR_TEXT_PRIMARY,
)
from app.video_exporter import EXPORT_FORMATS, QUALITY_PRESETS, get_export_format, get_quality_preset


RESOLUTION_PRESETS: tuple[tuple[tuple[int, int] | None, str], ...] = (
    (None, "Original"),
    ((3840, 2160), "4K  3840x2160"),
    ((1920, 1080), "1080p  1920x1080"),
    ((1280, 720), "720p  1280x720"),
    ((854, 480), "480p  854x480"),
    ((1080, 1920), "9:16  1080x1920"),
    ((1080, 1080), "1:1  1080x1080"),
)

FPS_PRESETS: tuple[tuple[float | None, str], ...] = (
    (None, "Original"),
    (60.0, "60 fps"),
    (30.0, "30 fps"),
    (25.0, "25 fps"),
    (24.0, "24 fps"),
)


def _refresh_export_control_dependents(owner: Any) -> None:
    refresh_tooltip = getattr(owner, "_refresh_export_button_tooltip", None)
    if callable(refresh_tooltip):
        refresh_tooltip()
    refresh_bar = getattr(owner, "_refresh_command_bar_responsive", None)
    if callable(refresh_bar):
        refresh_bar()


def _menu_qss(object_name: str) -> str:
    return (
        f"QMenu#{object_name} {{ "
        f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
        f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
        f"border-radius: 6px; padding: 6px; font-size: 12px; }}"
        f"QMenu#{object_name}::item {{ "
        f"padding: 8px 18px 8px 36px; border-radius: 4px; "
        f"margin: 1px 0px; }}"
        f"QMenu#{object_name}::item:selected {{ "
        f"background-color: {COLOR_BG_L5}; }}"
        f"QMenu#{object_name}::item:checked {{ "
        f"background-color: {COLOR_ACCENT_BLUE}; "
        f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; }}"
        f"QMenu#{object_name}::indicator {{ "
        f"width: 16px; height: 16px; left: 10px; }}"
    )


def refresh_export_quality_btn_label(owner: Any) -> None:
    q = get_quality_preset(getattr(owner, "_export_quality_id", ""))
    label = tr(q.name_key)
    if tier.requires_pro(q.feature_id) and not tier.is_locked(q.feature_id):
        label = f"{label} PRO"
    owner.quality_btn.setText(f"{label}  v")
    _refresh_export_control_dependents(owner)


def build_export_quality_menu(owner: Any) -> None:
    menu = QMenu(owner.quality_btn)
    menu.setObjectName("QualityMenu")
    menu.setStyleSheet(_menu_qss("QualityMenu"))
    for q in QUALITY_PRESETS:
        badge = ""
        if tier.requires_pro(q.feature_id):
            badge = "LOCKED PRO  " if tier.is_locked(q.feature_id) else "PRO  "
        label = f"{badge}{tr(q.name_key)}  -  {tr(q.desc_key)}"
        act = menu.addAction(label)
        act.setCheckable(True)
        act.setChecked(q.id == getattr(owner, "_export_quality_id", ""))
        act.triggered.connect(
            lambda _checked=False, qid=q.id: owner._on_quality_picked(qid)
        )
    owner.quality_btn.setMenu(menu)


def refresh_export_format_btn_label(owner: Any) -> None:
    f = get_export_format(getattr(owner, "_export_format_id", ""))
    label = (f.extension or f.id).lstrip(".").upper()
    if tier.requires_pro(f.feature_id) and not tier.is_locked(f.feature_id):
        label = f"{label} PRO"
    owner.format_btn.setText(f"{label}  v")
    _refresh_export_control_dependents(owner)


def build_export_format_menu(owner: Any) -> None:
    menu = QMenu(owner.format_btn)
    menu.setObjectName("FormatMenu")
    menu.setStyleSheet(_menu_qss("FormatMenu"))
    for f in EXPORT_FORMATS:
        badge = ""
        if tier.requires_pro(f.feature_id):
            badge = "LOCKED PRO  " if tier.is_locked(f.feature_id) else "PRO  "
        label = f"{badge}{tr(f.name_key)}  -  {tr(f.desc_key)}"
        act = menu.addAction(label)
        act.setCheckable(True)
        act.setChecked(f.id == getattr(owner, "_export_format_id", ""))
        act.triggered.connect(
            lambda _checked=False, fid=f.id: owner._on_format_picked(fid)
        )
    owner.format_btn.setMenu(menu)


def refresh_export_resolution_btn_label(owner: Any) -> None:
    res = getattr(owner, "_export_resolution", None)
    if res is None:
        owner.resolution_btn.setText("Original  v")
    else:
        owner.resolution_btn.setText(f"{res[0]}x{res[1]}  v")
    _refresh_export_control_dependents(owner)


def build_export_resolution_menu(owner: Any) -> None:
    menu = QMenu(owner.resolution_btn)
    menu.setObjectName("ResolutionMenu")
    menu.setStyleSheet(_menu_qss("ResolutionMenu"))
    for res, name in RESOLUTION_PRESETS:
        act = menu.addAction(name)
        act.setCheckable(True)
        act.setChecked(getattr(owner, "_export_resolution", None) == res)
        act.triggered.connect(
            lambda _checked=False, r=res: owner._on_resolution_picked(r)
        )
    owner.resolution_btn.setMenu(menu)


def refresh_export_fps_btn_label(owner: Any) -> None:
    fps = getattr(owner, "_export_fps", None)
    if fps is None:
        owner.fps_btn.setText("FPS Auto  v")
    else:
        owner.fps_btn.setText(f"{int(fps) if fps == int(fps) else fps} fps  v")
    _refresh_export_control_dependents(owner)


def build_export_fps_menu(owner: Any) -> None:
    menu = QMenu(owner.fps_btn)
    menu.setObjectName("FpsMenu")
    menu.setStyleSheet(_menu_qss("FpsMenu"))
    for fps, name in FPS_PRESETS:
        act = menu.addAction(name)
        act.setCheckable(True)
        act.setChecked(getattr(owner, "_export_fps", None) == fps)
        act.triggered.connect(
            lambda _checked=False, f=fps: owner._on_fps_picked(f)
        )
    owner.fps_btn.setMenu(menu)
