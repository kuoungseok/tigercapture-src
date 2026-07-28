"""Qt-free Motion Designer actor placement contract for Painter UI Design."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.motion_designer.schema import MotionComposition
from app.painter_ui_document import add_ui_object, normalize_ui_document


MOTION_ACTOR_KIND = "motion_actor"
MOTION_ACTOR_VERSION = 1


def motion_actor_composition_id(row: Mapping[str, Any]) -> str:
    if str(row.get("kind") or "") != MOTION_ACTOR_KIND:
        return ""
    content = row.get("content")
    content = content if isinstance(content, Mapping) else {}
    return str(content.get("motion_composition_id") or "")


def add_motion_actor(
    value: Mapping[str, Any],
    composition: MotionComposition,
    *,
    source_path: str = "",
    name: str = "",
    x: float | None = None,
    y: float | None = None,
    width: float = 0.0,
    height: float = 0.0,
    autoplay: bool = True,
    loop: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    artboard = next(
        row
        for row in document["artboards"]
        if row["id"] == document["active_artboard_id"]
    )
    aspect = max(0.01, float(composition.width) / max(1.0, composition.height))
    target_width = float(width or min(artboard["width"] * 0.62, composition.width))
    target_height = float(height or target_width / aspect)
    if target_height > artboard["height"] * 0.62:
        target_height = artboard["height"] * 0.62
        target_width = target_height * aspect
    target_width = max(32.0, min(float(artboard["width"]), target_width))
    target_height = max(32.0, min(float(artboard["height"]), target_height))
    target_x = (
        float(x)
        if x is not None
        else max(0.0, (float(artboard["width"]) - target_width) * 0.5)
    )
    target_y = (
        float(y)
        if y is not None
        else max(0.0, (float(artboard["height"]) - target_height) * 0.5)
    )
    return add_ui_object(
        document,
        kind=MOTION_ACTOR_KIND,
        name=str(name or composition.name or Path(source_path).stem or "Motion Actor"),
        x=target_x,
        y=target_y,
        width=target_width,
        height=target_height,
        style={
            "fill": "#00000000",
            "stroke": "#6FA0F5",
            "stroke_width": 1.0,
        },
        content={
            "motion_actor_version": MOTION_ACTOR_VERSION,
            "motion_composition_id": composition.id,
            "source_path": str(source_path or ""),
            "autoplay": bool(autoplay),
            "loop": bool(loop),
        },
    )


def motion_actor_rows(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    document = normalize_ui_document(value)
    return [
        dict(row)
        for row in document["objects"]
        if row["kind"] == MOTION_ACTOR_KIND
    ]


__all__ = [
    "MOTION_ACTOR_KIND",
    "MOTION_ACTOR_VERSION",
    "add_motion_actor",
    "motion_actor_composition_id",
    "motion_actor_rows",
]
