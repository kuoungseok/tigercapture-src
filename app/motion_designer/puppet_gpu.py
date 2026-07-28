"""GPU preview packet construction for textured puppet meshes."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from PySide6.QtGui import QImage

from .puppet_mesh import (
    PuppetMesh,
    evaluate_puppet_depths,
    evaluate_puppet_render_vertices,
)
from .schema import MotionComposition, MotionLayer


@dataclass(frozen=True, slots=True)
class PuppetGpuPacket:
    key: str
    texture_key: str
    image: QImage
    width: int
    height: int
    vertices: tuple[float, ...]
    triangle_count: int
    repair: dict[str, Any]


def _texture_key(layer: MotionLayer, image: QImage) -> str:
    path = Path(str(layer.source.uri or ""))
    signature = ""
    try:
        stat = path.stat()
        signature = f"{stat.st_size}:{stat.st_mtime_ns}"
    except OSError:
        pass
    params = json.dumps(layer.source.params, sort_keys=True, default=str)
    return f"{path.resolve() if path.exists() else path}|{signature}|{image.width()}x{image.height()}|{params}"


def build_puppet_gpu_packet(
    layer: MotionLayer,
    mesh: PuppetMesh,
    image: QImage,
    time_ms: float,
    *,
    composition: MotionComposition | None = None,
) -> tuple[PuppetGpuPacket | None, str]:
    if not mesh.enabled:
        return None, "puppet_mesh_disabled"
    if not mesh.pins:
        return None, "puppet_mesh_has_no_pins"
    if image is None or image.isNull():
        return None, "puppet_source_image_unavailable"
    width, height = max(1, image.width()), max(1, image.height())
    points, repair = evaluate_puppet_render_vertices(
        mesh,
        time_ms,
        width=width,
        height=height,
        composition=composition,
    )
    depths = evaluate_puppet_depths(mesh)
    triangles = sorted(
        mesh.triangles,
        key=lambda indices: sum(depths[index] for index in indices) / 3.0
        if min(indices) >= 0 and max(indices) < len(depths)
        else 0.0,
    )
    vertices: list[float] = []
    triangle_count = 0
    for triangle in triangles:
        if min(triangle) < 0 or max(triangle) >= len(points):
            continue
        for index in triangle:
            x, y = points[index]
            u, v = mesh.vertices[index].uv
            vertices.extend((
                x * (width - 1),
                y * (height - 1),
                float(u),
                float(v),
            ))
        triangle_count += 1
    if not vertices:
        return None, "puppet_mesh_has_no_renderable_triangles"
    texture_key = _texture_key(layer, image)
    return PuppetGpuPacket(
        key=f"{mesh.id}:{layer.id}",
        texture_key=texture_key,
        image=image.convertToFormat(QImage.Format_RGBA8888_Premultiplied),
        width=width,
        height=height,
        vertices=tuple(vertices),
        triangle_count=triangle_count,
        repair=repair,
    ), ""


__all__ = ["PuppetGpuPacket", "build_puppet_gpu_packet"]
