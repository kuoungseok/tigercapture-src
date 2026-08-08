"""Painter UI to the shared Tiger Studio PPT document bridge."""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document
from app.painter_ui_motion_bridge import resolved_ui_geometry
from app.painter_ui_themes import resolve_ui_theme_document
from app.pptgen.schema import (
    DeckSpec,
    ElementStyle,
    SlideElement,
    SlideSpec,
    ThemeSpec,
)


PPT_PREFLIGHT_SCHEMA = "tigerstudio.painter.ui.ppt_preflight.v1"
PPT_BRIDGE_SCHEMA = "tigerstudio.painter.ui.ppt_bridge.v1"
_NATIVE_KINDS = {"frame", "group", "rectangle", "line", "text", "button"}
_BAKED_KINDS = {
    "ellipse",
    "polygon",
    "star",
    "arc",
    "path",
    "progress",
    "motion_actor",
}


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "")).strip("-")


def _selected_artboards(
    document: Mapping[str, Any],
    scope: str,
) -> list[dict[str, Any]]:
    normalized_scope = str(scope or "active_artboard").strip().casefold()
    if normalized_scope not in {"active_artboard", "all_artboards"}:
        raise ValueError(f"Unsupported Painter PPT scope: {scope}")
    if normalized_scope == "all_artboards":
        return [dict(row) for row in document["artboards"]]
    return [
        dict(row)
        for row in document["artboards"]
        if row["id"] == document["active_artboard_id"]
    ]


def _delivery_for_object(row: Mapping[str, Any]) -> tuple[str, str]:
    kind = str(row["kind"])
    if kind == "image":
        source = str((row.get("content") or {}).get("source_path") or "")
        if source and Path(source).is_file():
            return "Native", "editable PPT image"
        return "Baked", "missing image source is rendered as a visual placeholder"
    if kind in _NATIVE_KINDS:
        return "Native", "editable PPT element"
    if kind in _BAKED_KINDS:
        return "Baked", "exact appearance requires a raster element"
    return "Blocked", f"unsupported Painter object kind: {kind}"


def inspect_painter_ui_ppt(
    value: Mapping[str, Any],
    *,
    scope: str = "active_artboard",
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    artboards = _selected_artboards(document, scope)
    artboard_ids = {row["id"] for row in artboards}
    features = []
    counts = {"Native": 0, "Baked": 0, "Blocked": 0}
    blockers = []
    for row in document["objects"]:
        if row["artboard_id"] not in artboard_ids or not row["visible"]:
            continue
        resolved, reason = _delivery_for_object(row)
        counts[resolved] += 1
        features.append(
            {
                "object_id": row["id"],
                "object_name": row["name"],
                "object_kind": row["kind"],
                "resolved": resolved,
                "reason": reason,
            }
        )
        if resolved == "Blocked":
            blockers.append(f"blocked_object:{row['id']}:{row['kind']}")
    return {
        "schema": PPT_PREFLIGHT_SCHEMA,
        "ok": not blockers,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "scope": str(scope or "active_artboard"),
        "artboard_ids": [row["id"] for row in artboards],
        "slide_count": len(artboards),
        "counts": counts,
        "features": features,
        "blockers": blockers,
        "claim_scope": "editable_ppt_deck_with_explicit_bakes",
    }


def _fit_region(artboard: Mapping[str, Any]) -> tuple[float, float, float, float]:
    target_ratio = 16.0 / 9.0
    source_ratio = float(artboard["width"]) / max(1.0, float(artboard["height"]))
    if source_ratio >= target_ratio:
        height = target_ratio / source_ratio
        return 0.0, (1.0 - height) * 0.5, 1.0, height
    width = source_ratio / target_ratio
    return (1.0 - width) * 0.5, 0.0, width, 1.0


def _element_rect(
    geometry: Mapping[str, Any],
    artboard: Mapping[str, Any],
) -> tuple[float, float, float, float]:
    fit_x, fit_y, fit_w, fit_h = _fit_region(artboard)
    width = max(1.0, float(artboard["width"]))
    height = max(1.0, float(artboard["height"]))
    return (
        fit_x + float(geometry["x"]) / width * fit_w,
        fit_y + float(geometry["y"]) / height * fit_h,
        max(0.001, float(geometry["width"]) / width * fit_w),
        max(0.001, float(geometry["height"]) / height * fit_h),
    )


def _element_style(row: Mapping[str, Any]) -> ElementStyle:
    style = dict(row.get("style") or {})
    return ElementStyle(
        fill=str(style.get("fill") or "") or None,
        stroke=str(style.get("stroke") or "") or None,
        stroke_width=float(style.get("stroke_width") or 0.0),
        color=str(style.get("text_color") or "#182033"),
        font_family=str(style.get("font_family") or "Noto Sans KR"),
        font_size=max(1, int(round(float(style.get("font_size") or 16.0)))),
        bold=float(style.get("font_weight") or 400.0) >= 600.0,
        italic=bool(style.get("italic", False)),
        underline=bool(style.get("underline", False)),
        align=str(style.get("text_align") or "left"),
        line_height=float(style.get("line_height") or 1.2),
        letter_spacing=float(style.get("letter_spacing") or 0.0),
        radius=float(style.get("radius") or 0.0),
    )


def _bake_object(
    document: Mapping[str, Any],
    row: Mapping[str, Any],
    geometry: Mapping[str, Any],
    asset_dir: Path,
) -> Path:
    from app.painter_ui_asset_export import render_ui_artboard

    isolated = copy.deepcopy(dict(document))
    artboard = next(
        item
        for item in isolated["artboards"]
        if item["id"] == row["artboard_id"]
    )
    baked_row = copy.deepcopy(dict(row))
    baked_row.update(
        {
            "x": 0.0,
            "y": 0.0,
            "width": float(geometry["width"]),
            "height": float(geometry["height"]),
            "parent_id": "",
        }
    )
    artboard.update(
        {
            "width": max(1, int(round(float(geometry["width"])))),
            "height": max(1, int(round(float(geometry["height"])))),
            "background": "#00000000",
        }
    )
    isolated["active_artboard_id"] = artboard["id"]
    isolated["objects"] = [baked_row]
    digest = hashlib.sha256(
        f"{document['document_id']}|{document['revision']}|{row['id']}".encode(
            "utf-8"
        )
    ).hexdigest()[:12]
    target = asset_dir / f"{_safe_id(row['id'])}-{digest}.png"
    asset_dir.mkdir(parents=True, exist_ok=True)
    image = render_ui_artboard(isolated, artboard["id"], density=1.0)
    if not image.save(str(target), "PNG"):
        raise RuntimeError(f"Could not bake Painter object for PPT: {row['id']}")
    return target


def painter_ui_to_ppt_deck(
    value: Mapping[str, Any],
    *,
    scope: str = "active_artboard",
    asset_dir: str | Path,
    title: str = "",
) -> tuple[DeckSpec, dict[str, Any]]:
    document = resolve_ui_theme_document(normalize_ui_document(value))
    preflight = inspect_painter_ui_ppt(document, scope=scope)
    if not preflight["ok"]:
        raise ValueError("Painter PPT preflight blocked: " + ", ".join(preflight["blockers"]))
    artboards = _selected_artboards(document, scope)
    geometry = resolved_ui_geometry(document)
    root = Path(asset_dir).expanduser().resolve()
    first = artboards[0]
    theme = ThemeSpec(
        id="painter-ui",
        name="Painter UI",
        background=str(first.get("background") or "#FFFFFF"),
    )
    deck = DeckSpec(
        id=f"ppt-{_safe_id(document['document_id'])}",
        title=str(title or document.get("name") or "Painter UI Presentation"),
        aspect_ratio="16:9",
        theme=theme,
        metadata={
            "source": "painter_ui",
            "painter_ui_document_id": document["document_id"],
            "painter_ui_revision": document["revision"],
        },
    )
    baked_assets = []
    for slide_index, artboard in enumerate(artboards, start=1):
        slide = SlideSpec(
            id=f"slide-{_safe_id(artboard['id'])}",
            title=str(artboard["name"]),
            layout_id="blank",
            background=str(artboard.get("background") or "#FFFFFF"),
            metadata={
                "painter_ui_artboard_id": artboard["id"],
                "painter_ui_breakpoint": artboard.get("breakpoint", "custom"),
            },
        )
        for row in sorted(
            (
                item
                for item in document["objects"]
                if item["artboard_id"] == artboard["id"] and item["visible"]
            ),
            key=lambda item: (int(item["z_index"]), item["id"]),
        ):
            delivery, _reason = _delivery_for_object(row)
            resolved = geometry.get(row["id"], row)
            x, y, width, height = _element_rect(resolved, artboard)
            metadata = {
                "painter_ui_object_id": row["id"],
                "painter_ui_kind": row["kind"],
                "painter_ui_delivery": delivery,
            }
            if delivery == "Baked":
                source = _bake_object(document, row, resolved, root)
                baked_assets.append(str(source))
                element = SlideElement.image(
                    row["id"],
                    source,
                    x=x,
                    y=y,
                    w=width,
                    h=height,
                    name=row["name"],
                )
                element.metadata = metadata
            elif row["kind"] == "image":
                element = SlideElement.image(
                    row["id"],
                    (row.get("content") or {}).get("source_path", ""),
                    x=x,
                    y=y,
                    w=width,
                    h=height,
                    name=row["name"],
                )
                element.metadata = metadata
            else:
                kind = (
                    "text"
                    if row["kind"] in {"text", "button"}
                    else "line"
                    if row["kind"] == "line"
                    else "shape"
                )
                element = SlideElement(
                    id=row["id"],
                    kind=kind,
                    name=row["name"],
                    x=x,
                    y=y,
                    w=width,
                    h=height,
                    rotation=float(row["rotation"]),
                    z_index=int(row["z_index"]),
                    opacity=float(row["opacity"]),
                    text=str((row.get("content") or {}).get("text") or ""),
                    style=_element_style(row),
                    metadata=metadata,
                )
            slide.add_element(element)
        deck.slides.append(slide)
    report = {
        "schema": PPT_BRIDGE_SCHEMA,
        "ok": True,
        "deck_id": deck.id,
        "slide_count": len(deck.slides),
        "element_count": sum(len(slide.elements) for slide in deck.slides),
        "baked_assets": baked_assets,
        "preflight": preflight,
    }
    return deck, report


__all__ = [
    "PPT_BRIDGE_SCHEMA",
    "PPT_PREFLIGHT_SCHEMA",
    "inspect_painter_ui_ppt",
    "painter_ui_to_ppt_deck",
]
