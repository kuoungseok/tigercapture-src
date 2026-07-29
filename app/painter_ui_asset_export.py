"""Production asset rendering and deterministic Painter UI delivery manifests."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen

from app.painter_ui_document import normalize_ui_document
from app.painter_ui_image_renderer import draw_ui_image
from app.painter_ui_style_renderer import draw_ui_vector_paths


ASSET_EXPORT_SCHEMA = "tigerstudio.painter.ui.asset_export.v1"
_VECTOR_KINDS = {
    "frame",
    "group",
    "rectangle",
    "ellipse",
    "line",
    "polygon",
    "star",
    "arc",
    "path",
    "text",
}


def _slug(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip())
    return result.strip("-").lower() or "asset"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _color(value: Any, fallback: str = "#00000000") -> QColor:
    color = QColor(str(value or fallback))
    return color if color.isValid() else QColor(fallback)


def _objects_for_artboard(
    document: Mapping[str, Any],
    artboard_id: str,
) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in document["objects"]
        if row["artboard_id"] == artboard_id and row["visible"]
    ]
    from app.painter_ui_boolean_geometry import boolean_operand_ids

    hidden_operands = boolean_operand_ids(rows)
    return sorted(
        (row for row in rows if row["id"] not in hidden_operands),
        key=lambda row: (int(row["z_index"]), row["id"]),
    )


def _image_fill_clip_path(
    rect: QRectF,
    kind: str,
    radius: float,
) -> QPainterPath:
    path = QPainterPath()
    if kind == "ellipse":
        path.addEllipse(rect)
    else:
        path.addRoundedRect(rect, radius, radius)
    return path


def _draw_image_fill(
    painter: QPainter,
    rect: QRectF,
    kind: str,
    radius: float,
    content: Mapping[str, Any],
) -> bool:
    if not str(content.get("source_path") or "").strip():
        return False
    painter.save()
    painter.setClipPath(_image_fill_clip_path(rect, kind, radius))
    rendered = draw_ui_image(painter, rect, content)
    painter.restore()
    return rendered


def render_ui_artboard(
    value: Mapping[str, Any],
    artboard_id: str,
    *,
    density: float = 1.0,
) -> QImage:
    document = normalize_ui_document(value)
    artboard = next(
        (
            row
            for row in document["artboards"]
            if row["id"] == str(artboard_id)
        ),
        None,
    )
    if artboard is None:
        raise ValueError(f"Painter UI artboard not found: {artboard_id}")
    scale = max(0.25, min(8.0, float(density)))
    width = max(1, int(round(float(artboard["width"]) * scale)))
    height = max(1, int(round(float(artboard["height"]) * scale)))
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(_color(artboard.get("background"), "#FFFFFFFF"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.scale(scale, scale)
    all_rows = [
        row
        for row in document["objects"]
        if row["artboard_id"] == str(artboard_id)
    ]

    def document_rect(row: Mapping[str, Any]) -> QRectF:
        return QRectF(
            float(row["x"]),
            float(row["y"]),
            float(row["width"]),
            float(row["height"]),
        )

    for row in _objects_for_artboard(document, str(artboard_id)):
        rect = QRectF(
            float(row["x"]),
            float(row["y"]),
            float(row["width"]),
            float(row["height"]),
        )
        style = dict(row.get("style") or {})
        content = dict(row.get("content") or {})
        painter.save()
        painter.setOpacity(float(row["opacity"]))
        pivot_x = rect.left() + rect.width() * float(row.get("pivot_x", 0.5))
        pivot_y = rect.top() + rect.height() * float(row.get("pivot_y", 0.5))
        painter.translate(pivot_x, pivot_y)
        painter.rotate(float(row["rotation"]))
        painter.translate(-pivot_x, -pivot_y)
        fill = _color(style.get("fill"), "#00000000")
        stroke_width = max(0.0, float(style.get("stroke_width", 0.0) or 0.0))
        pen = QPen(_color(style.get("stroke"), "#00000000"))
        pen.setWidthF(stroke_width)
        painter.setPen(pen if stroke_width > 0.0 else Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        radius = max(0.0, float(style.get("radius", 0.0) or 0.0))
        kind = row["kind"]
        from app.painter_ui_boolean_geometry import resolve_ui_boolean_path

        boolean_path = resolve_ui_boolean_path(
            all_rows,
            row,
            document_rect,
        )
        if boolean_path is not None:
            painter.drawPath(boolean_path)
        elif kind == "ellipse":
            painter.drawEllipse(rect)
            _draw_image_fill(
                painter,
                rect,
                kind,
                radius,
                content,
            )
        elif kind == "line":
            painter.drawLine(rect.topLeft(), rect.bottomRight())
        elif kind in {"polygon", "star", "arc"}:
            from app.painter_ui_parametric_shapes import (
                parametric_shape_path,
            )

            painter.drawPath(
                parametric_shape_path(rect, kind, content)
            )
        elif kind == "image":
            if not _draw_image_fill(
                painter,
                rect,
                kind,
                radius,
                content,
            ):
                painter.fillRect(rect, QColor("#323842"))
                painter.setPen(QPen(QColor("#9AA6B2"), 1.0))
                painter.drawLine(rect.topLeft(), rect.bottomRight())
                painter.drawLine(rect.topRight(), rect.bottomLeft())
        elif kind in {"text", "button"}:
            if kind == "button":
                painter.drawRoundedRect(rect, radius, radius)
                _draw_image_fill(
                    painter,
                    rect,
                    kind,
                    radius,
                    content,
                )
            font = QFont(str(style.get("font_family") or "Arial"))
            font.setPixelSize(max(1, int(float(style.get("font_size", 16.0)))))
            font.setWeight(
                max(
                    QFont.Weight.Thin,
                    min(
                        QFont.Weight.Black,
                        int(float(style.get("font_weight", 400))) // 10,
                    ),
                )
            )
            from app.painter_ui_typography import apply_ui_font_axes

            apply_ui_font_axes(font, style.get("font_axes"))
            painter.setFont(font)
            painter.setPen(_color(style.get("text_color"), "#111111"))
            alignment = {
                "center": Qt.AlignmentFlag.AlignCenter,
                "right": Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter,
            }.get(
                str(style.get("text_align") or "left"),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            painter.drawText(
                rect,
                alignment | Qt.TextFlag.TextWordWrap,
                str(content.get("text") or row["name"]),
            )
        elif kind == "path":
            draw_ui_vector_paths(painter, rect, content, style)
        elif kind == "progress":
            painter.drawRoundedRect(rect, radius, radius)
            progress = min(1.0, max(0.0, float(content.get("value", 0.5))))
            painter.fillRect(
                QRectF(rect.x(), rect.y(), rect.width() * progress, rect.height()),
                _color(style.get("progress_fill"), "#4F7CFF"),
            )
        else:
            painter.drawRoundedRect(rect, radius, radius)
            if kind in {"frame", "rectangle"}:
                _draw_image_fill(
                    painter,
                    rect,
                    kind,
                    radius,
                    content,
                )
        painter.restore()
    painter.end()
    return image


def _svg_for_artboard(
    document: Mapping[str, Any],
    artboard: Mapping[str, Any],
) -> tuple[str, list[str]]:
    blocked = [
        row["id"]
        for row in _objects_for_artboard(document, artboard["id"])
        if row["kind"] not in _VECTOR_KINDS
        or row.get("style", {}).get("paint_layer_id")
        or row.get("style", {}).get("mask")
        or row.get("style", {}).get("material")
    ]
    if blocked:
        image = render_ui_artboard(document, artboard["id"], density=1.0)
        encoded = QByteArray()
        buffer = QBuffer(encoded)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        payload = base64.b64encode(bytes(encoded)).decode("ascii")
        return (
            (
                '<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" '
                'viewBox="0 0 %s %s"><image width="100%%" height="100%%" '
                'href="data:image/png;base64,%s"/></svg>'
            )
            % (
                artboard["width"],
                artboard["height"],
                artboard["width"],
                artboard["height"],
                payload,
            ),
            blocked,
        )
    rows = [
        (
            '<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" '
            'viewBox="0 0 %s %s">'
        )
        % (
            artboard["width"],
            artboard["height"],
            artboard["width"],
            artboard["height"],
        ),
        '<rect width="100%%" height="100%%" fill="%s"/>'
        % str(artboard.get("background") or "#ffffff"),
    ]
    for row in _objects_for_artboard(document, artboard["id"]):
        if row["id"] in blocked:
            continue
        style = dict(row.get("style") or {})
        content = dict(row.get("content") or {})
        common = (
            'fill="%s" stroke="%s" stroke-width="%s" opacity="%s" '
            'transform="rotate(%s %s %s)"'
            % (
                style.get("fill") or "none",
                style.get("stroke") or "none",
                style.get("stroke_width", 0),
                row["opacity"],
                row["rotation"],
                row["x"] + row["width"] * row.get("pivot_x", 0.5),
                row["y"] + row["height"] * row.get("pivot_y", 0.5),
            )
        )
        from app.painter_ui_boolean_geometry import (
            qpath_to_svg_path,
            resolve_ui_boolean_path,
        )

        all_rows = [
            item
            for item in document["objects"]
            if item["artboard_id"] == artboard["id"]
        ]
        boolean_path = resolve_ui_boolean_path(
            all_rows,
            row,
            lambda item: QRectF(
                float(item["x"]),
                float(item["y"]),
                float(item["width"]),
                float(item["height"]),
            ),
        )
        if boolean_path is not None:
            rows.append(
                '<path d="%s" fill-rule="evenodd" %s/>'
                % (qpath_to_svg_path(boolean_path), common)
            )
        elif row["kind"] == "ellipse":
            rows.append(
                '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" %s/>'
                % (
                    row["x"] + row["width"] / 2,
                    row["y"] + row["height"] / 2,
                    row["width"] / 2,
                    row["height"] / 2,
                    common,
                )
            )
        elif row["kind"] == "line":
            rows.append(
                '<line x1="%s" y1="%s" x2="%s" y2="%s" %s/>'
                % (
                    row["x"],
                    row["y"],
                    row["x"] + row["width"],
                    row["y"] + row["height"],
                    common,
                )
            )
        elif row["kind"] in {"polygon", "star", "arc"}:
            from app.painter_ui_parametric_shapes import (
                parametric_shape_svg_path,
            )

            rows.append(
                '<path d="%s" fill-rule="evenodd" %s/>'
                % (
                    parametric_shape_svg_path(
                        QRectF(
                            float(row["x"]),
                            float(row["y"]),
                            float(row["width"]),
                            float(row["height"]),
                        ),
                        str(row["kind"]),
                        content,
                    ),
                    common,
                )
            )
        elif row["kind"] == "path":
            from app.painter_ui_vector_network import (
                vector_network_to_svg_path,
            )

            path = vector_network_to_svg_path(
                content.get("vector_network"),
                QRectF(
                    float(row["x"]),
                    float(row["y"]),
                    float(row["width"]),
                    float(row["height"]),
                ),
            )
            if path:
                rows.append('<path d="%s" %s/>' % (path, common))
        elif row["kind"] == "text":
            rows.append(
                '<text x="%s" y="%s" font-size="%s" %s>%s</text>'
                % (
                    row["x"],
                    row["y"] + float(style.get("font_size", 16)),
                    style.get("font_size", 16),
                    common,
                    str(content.get("text") or row["name"])
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"),
                )
            )
        else:
            rows.append(
                '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" %s/>'
                % (
                    row["x"],
                    row["y"],
                    row["width"],
                    row["height"],
                    style.get("radius", 0),
                    common,
                )
            )
    rows.append("</svg>")
    return "\n".join(rows), blocked


def _build_atlas(
    images: list[tuple[str, QImage]],
    output_path: Path,
) -> tuple[QImage, dict[str, Any]]:
    if not images:
        return QImage(), {}
    width = max(image.width() for _, image in images)
    total_area = sum(image.width() * image.height() for _, image in images)
    target_width = max(width, int(math.sqrt(total_area)))
    x = y = row_height = 0
    placements: dict[str, Any] = {}
    packed_width = 0
    for name, image in images:
        if x and x + image.width() > target_width:
            x = 0
            y += row_height
            row_height = 0
        placements[name] = {
            "x": x,
            "y": y,
            "width": image.width(),
            "height": image.height(),
        }
        x += image.width()
        row_height = max(row_height, image.height())
        packed_width = max(packed_width, x)
    packed_height = y + row_height
    atlas = QImage(
        max(1, packed_width),
        max(1, packed_height),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    atlas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(atlas)
    for name, image in images:
        row = placements[name]
        painter.drawImage(row["x"], row["y"], image)
    painter.end()
    atlas.save(str(output_path), "PNG")
    return atlas, placements


def export_ui_assets(
    value: Mapping[str, Any],
    output_dir: str | Path,
    *,
    formats: list[str] | None = None,
    densities: list[float] | None = None,
    create_atlas: bool = False,
    object_ids: list[str] | None = None,
    trim_transparent: bool = False,
    padding: int = 0,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    requested_formats = [
        item
        for item in {
            str(row).strip().lower() for row in (formats or ["png", "webp", "svg"])
        }
        if item in {"png", "webp", "svg"}
    ]
    requested_densities = sorted(
        {
            max(0.25, min(8.0, float(row)))
            for row in (densities or [1.0, 2.0, 3.0])
        }
    )
    artifacts: list[dict[str, Any]] = []
    atlas_images: list[tuple[str, QImage]] = []
    requested_object_ids = {
        str(row) for row in (object_ids or []) if str(row)
    }
    object_rows = {
        row["id"]: row
        for row in document["objects"]
        if not requested_object_ids or row["id"] in requested_object_ids
    }
    for artboard in document["artboards"]:
        base = _slug(artboard["name"])
        for density in requested_densities:
            image = render_ui_artboard(
                document,
                artboard["id"],
                density=density,
            )
            density_label = (
                f"@{int(density)}x"
                if float(density).is_integer()
                else f"@{density:g}x"
            )
            if density == 1.0:
                atlas_images.append((base, image))
            for format_name in requested_formats:
                if format_name == "svg":
                    continue
                path = root / f"{base}{density_label}.{format_name}"
                saved = image.save(str(path), format_name.upper())
                if not saved:
                    artifacts.append(
                        {
                            "kind": format_name,
                            "path": str(path),
                            "status": "blocked",
                            "reason": f"Qt image plugin cannot write {format_name}",
                        }
                    )
                    continue
                artifacts.append(
                    {
                        "kind": format_name,
                        "artboard_id": artboard["id"],
                        "density": density,
                        "width": image.width(),
                        "height": image.height(),
                        "path": str(path),
                        "sha256": _hash_file(path),
                        "status": "native",
                    }
                )
        if "svg" in requested_formats:
            svg, blocked = _svg_for_artboard(document, artboard)
            path = root / f"{base}.svg"
            path.write_text(svg + "\n", encoding="utf-8")
            artifacts.append(
                {
                    "kind": "svg",
                    "artboard_id": artboard["id"],
                    "density": 1.0,
                    "path": str(path),
                    "sha256": _hash_file(path),
                    "status": "baked" if blocked else "native",
                    "blocked_object_ids": blocked,
                    "reason": (
                        "Unsupported objects are embedded as a deterministic PNG bake"
                        if blocked
                        else ""
                    ),
                }
            )
        artboard_image_cache: dict[float, QImage] = {}
        for row in object_rows.values():
            if row["artboard_id"] != artboard["id"]:
                continue
            slice_name = _slug(row["name"])
            for density in requested_densities:
                full = artboard_image_cache.setdefault(
                    density,
                    render_ui_artboard(
                        document,
                        artboard["id"],
                        density=density,
                    ),
                )
                extra = max(0, int(padding))
                rect = QRect(
                    max(0, int(round(row["x"] * density)) - extra),
                    max(0, int(round(row["y"] * density)) - extra),
                    max(
                        1,
                        int(round(row["width"] * density)) + extra * 2,
                    ),
                    max(
                        1,
                        int(round(row["height"] * density)) + extra * 2,
                    ),
                ).intersected(full.rect())
                sliced = full.copy(rect)
                if trim_transparent and sliced.hasAlphaChannel():
                    bounds = sliced.rect()
                    left, top = bounds.right(), bounds.bottom()
                    right = bottom = -1
                    for y in range(sliced.height()):
                        for x in range(sliced.width()):
                            if QColor(sliced.pixel(x, y)).alpha() > 0:
                                left = min(left, x)
                                top = min(top, y)
                                right = max(right, x)
                                bottom = max(bottom, y)
                    if right >= left and bottom >= top:
                        sliced = sliced.copy(
                            QRect(left, top, right - left + 1, bottom - top + 1)
                        )
                if density == 1.0:
                    atlas_images.append((slice_name, sliced))
                density_label = (
                    f"@{int(density)}x"
                    if float(density).is_integer()
                    else f"@{density:g}x"
                )
                for format_name in requested_formats:
                    if format_name == "svg":
                        continue
                    path = (
                        root
                        / f"{base}--{slice_name}{density_label}.{format_name}"
                    )
                    if not sliced.save(str(path), format_name.upper()):
                        continue
                    artifacts.append(
                        {
                            "kind": f"slice_{format_name}",
                            "object_id": row["id"],
                            "artboard_id": artboard["id"],
                            "density": density,
                            "width": sliced.width(),
                            "height": sliced.height(),
                            "padding": extra,
                            "trim_transparent": bool(trim_transparent),
                            "path": str(path),
                            "sha256": _hash_file(path),
                            "status": "native",
                        }
                    )
    atlas_report: dict[str, Any] = {}
    if create_atlas and atlas_images:
        atlas_path = root / "ui-atlas.png"
        atlas, placements = _build_atlas(atlas_images, atlas_path)
        atlas_meta_path = root / "ui-atlas.json"
        atlas_meta_path.write_text(
            json.dumps(placements, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        atlas_report = {
            "image": str(atlas_path),
            "metadata": str(atlas_meta_path),
            "width": atlas.width(),
            "height": atlas.height(),
            "sha256": _hash_file(atlas_path),
        }
    nine_slice = [
        {
            "object_id": row["id"],
            "name": row["name"],
            "source": str(
                row.get("content", {}).get("source_path")
                or row.get("content", {}).get("path")
                or ""
            ),
            "margins": dict(row.get("content", {}).get("nine_slice") or {}),
        }
        for row in document["objects"]
        if row.get("content", {}).get("nine_slice")
    ]
    resources: list[dict[str, Any]] = []
    seen_resources: set[str] = set()
    candidates: list[tuple[str, str]] = []
    for row in document["objects"]:
        content = dict(row.get("content") or {})
        if row["kind"] == "image":
            candidates.append(
                (
                    "image",
                    str(content.get("source_path") or content.get("path") or ""),
                )
            )
        font_path = str(content.get("font_path") or "")
        if font_path:
            candidates.append(("font", font_path))
    for interaction in document["interactions"]:
        parameters = dict(interaction.get("parameters") or {})
        if interaction["action"] == "play_sound":
            candidates.append(("sound", str(parameters.get("uri") or "")))
    for kind, raw_path in candidates:
        path = Path(raw_path).expanduser()
        key = f"{kind}:{path}"
        if key in seen_resources:
            continue
        seen_resources.add(key)
        resources.append(
            {
                "id": f"{kind}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}",
                "kind": kind,
                "path": str(path),
                "exists": path.is_file(),
                "sha256": _hash_file(path) if path.is_file() else "",
                "size_bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    manifest = {
        "schema": ASSET_EXPORT_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "formats": requested_formats,
        "densities": requested_densities,
        "artifacts": artifacts,
        "atlas": atlas_report,
        "nine_slice": nine_slice,
        "resources": resources,
        "color_space": "sRGB",
        "alpha_mode": "straight",
        "trim_transparent": bool(trim_transparent),
        "slice_padding": max(0, int(padding)),
        "blocked_count": sum(
            1 for row in artifacts if row["status"] == "blocked"
        ),
        "baked_count": sum(1 for row in artifacts if row["status"] == "baked"),
    }
    manifest_path = root / "asset-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": manifest["blocked_count"] == 0,
        "root": str(root),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
    }


__all__ = [
    "ASSET_EXPORT_SCHEMA",
    "export_ui_assets",
    "render_ui_artboard",
]
