"""Shared painter render graph for GPU preview and file export."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter, QTransform

from .adapters import render_source
from .boolean_layers import consumed_boolean_operand_ids, resolve_boolean_layer
from .effect_adapter import apply_effects
from .evaluator import evaluate_composition
from .schema import MotionComposition, MotionEffectRef, MotionLayer
from .source_frame import transparent_image
from .typography_gpu import TypographyGpuPacket, build_typography_gpu_packet
from .vector_gpu import VectorGpuPacket, build_vector_gpu_packet


@dataclass(slots=True)
class RenderNode:
    layer_id: str
    image: QImage | None
    matrix: tuple[float, float, float, float, float, float]
    opacity: float
    blend_mode: str
    anchor: tuple[float, float]
    layer_type: str = "shape"
    effects: list[MotionEffectRef] | None = None
    local_time_ms: float = 0.0
    matte_layer_id: str = ""
    matte_mode: str = "alpha"
    matte_inverted: bool = False
    vector_gpu_packet: VectorGpuPacket | None = None
    vector_gpu_reason: str = ""
    typography_gpu_packet: TypographyGpuPacket | None = None
    typography_gpu_reason: str = ""
    source_layer: MotionLayer | None = None
    source_composition: MotionComposition | None = None
    composition_time_ms: float = 0.0
    render_quality: str = "preview"
    source_viewport_size: tuple[int, int] | None = None


@dataclass(slots=True)
class RenderGraph:
    width: int
    height: int
    nodes: list[RenderNode]
    diagnostics: dict[str, Any]


BLEND_MODES = {
    "normal": QPainter.CompositionMode_SourceOver,
    "add": QPainter.CompositionMode_Plus,
    "screen": QPainter.CompositionMode_Screen,
    "multiply": QPainter.CompositionMode_Multiply,
}


def build_render_graph(
    composition: MotionComposition,
    time_ms: float,
    *,
    include_vector_gpu: bool = False,
    render_quality: str = "preview",
    output_size: tuple[int, int] | None = None,
) -> RenderGraph:
    states = {state.id: state for state in evaluate_composition(composition, time_ms)}
    consumed_operand_ids = consumed_boolean_operand_ids(composition, states)
    nodes: list[RenderNode] = []
    vector_gpu_packet_count = 0
    vector_gpu_fallback_count = 0
    typography_gpu_packet_count = 0
    typography_gpu_fallback_count = 0
    for layer in composition.layers:
        state = states[layer.id]
        if not state.active or layer.layer_type in {"group", "null", "camera", "light"} or layer.id in consumed_operand_ids:
            continue
        render_layer = resolve_boolean_layer(composition, layer, states)
        if include_vector_gpu and render_layer.layer_type == "shape":
            vector_gpu_packet, vector_gpu_reason = build_vector_gpu_packet(render_layer, state.local_time_ms)
        elif include_vector_gpu and render_layer.layer_type == "particle":
            from .particle_gpu import build_particle_gpu_packet

            vector_gpu_packet, vector_gpu_reason = build_particle_gpu_packet(render_layer, state.local_time_ms)
        else:
            vector_gpu_packet = None
            vector_gpu_reason = "not_requested" if not include_vector_gpu else "non_vector_node"
        if include_vector_gpu and render_layer.layer_type == "text":
            typography_gpu_packet, typography_gpu_reason = build_typography_gpu_packet(
                render_layer, state.local_time_ms,
            )
        else:
            typography_gpu_packet = None
            typography_gpu_reason = "not_requested" if not include_vector_gpu else "non_typography_node"
        image = None
        if (
            layer.layer_type != "adjustment"
            and vector_gpu_packet is None
            and typography_gpu_packet is None
        ):
            image = render_source(
                render_layer,
                state.local_time_ms,
                composition=composition,
                composition_time_ms=float(time_ms),
                quality=render_quality,
                viewport_size=output_size or (composition.width, composition.height),
            )
        if vector_gpu_packet is not None:
            vector_gpu_packet_count += 1
        elif include_vector_gpu and layer.layer_type != "adjustment":
            if render_layer.layer_type in {"shape", "particle"}:
                vector_gpu_fallback_count += 1
        if typography_gpu_packet is not None:
            typography_gpu_packet_count += 1
        elif include_vector_gpu and render_layer.layer_type == "text":
            typography_gpu_fallback_count += 1
        nodes.append(RenderNode(
            layer.id, image, state.matrix, state.opacity, state.blend_mode,
            (float(state.anchor[0]), float(state.anchor[1])), layer_type=layer.layer_type,
            effects=list(layer.effects), local_time_ms=state.local_time_ms,
            matte_layer_id=str(layer.metadata.get("matte_layer_id") or ""),
            matte_mode=str(layer.metadata.get("matte_mode") or "alpha"),
            matte_inverted=bool(layer.metadata.get("matte_inverted", False)),
            vector_gpu_packet=vector_gpu_packet,
            vector_gpu_reason=vector_gpu_reason,
            typography_gpu_packet=typography_gpu_packet,
            typography_gpu_reason=typography_gpu_reason,
            source_layer=render_layer,
            source_composition=composition,
            composition_time_ms=float(time_ms),
            render_quality=str(render_quality),
            source_viewport_size=output_size or (composition.width, composition.height),
        ))
    return RenderGraph(composition.width, composition.height, nodes, {
        "renderer": "qt_painter_render_graph", "premultiplied_alpha": True,
        "node_count": len(nodes), "composition_revision": composition.revision,
        "boolean_operand_count": len(consumed_operand_ids),
        "vector_gpu_packet_count": vector_gpu_packet_count,
        "vector_gpu_fallback_count": vector_gpu_fallback_count,
        "vector_gpu_requested": include_vector_gpu,
        "typography_gpu_packet_count": typography_gpu_packet_count,
        "typography_gpu_fallback_count": typography_gpu_fallback_count,
        "typography_gpu_requested": include_vector_gpu,
        "render_quality": str(render_quality),
        "output_size": list(output_size or (composition.width, composition.height)),
    })


def _node_image(node: RenderNode) -> QImage | None:
    if node.image is None and node.layer_type != "adjustment" and node.source_layer is not None:
        node.image = render_source(
            node.source_layer,
            node.local_time_ms,
            composition=node.source_composition,
            composition_time_ms=node.composition_time_ms,
            quality=node.render_quality,
            viewport_size=node.source_viewport_size,
        )
    return node.image


def _node_surface(graph: RenderGraph, node: RenderNode) -> QImage:
    surface = transparent_image(graph.width, graph.height)
    image = _node_image(node)
    if image is None:
        return surface
    layer_painter = QPainter(surface)
    layer_painter.setRenderHint(QPainter.Antialiasing)
    layer_painter.setRenderHint(QPainter.SmoothPixmapTransform)
    layer_painter.setOpacity(node.opacity)
    a, b, c, d, tx, ty = node.matrix
    layer_painter.setTransform(QTransform(a, b, 0.0, c, d, 0.0, tx, ty, 1.0))
    layer_painter.drawImage(
        -image.width() * node.anchor[0],
        -image.height() * node.anchor[1],
        image,
    )
    layer_painter.end()
    return surface


def _paint_node(painter: QPainter, node: RenderNode) -> None:
    image = _node_image(node)
    if image is None:
        return
    painter.save()
    painter.setCompositionMode(BLEND_MODES.get(node.blend_mode, QPainter.CompositionMode_SourceOver))
    painter.setOpacity(node.opacity)
    a, b, c, d, tx, ty = node.matrix
    painter.setTransform(QTransform(a, b, 0.0, c, d, 0.0, tx, ty, 1.0), combine=True)
    painter.drawImage(
        -image.width() * node.anchor[0],
        -image.height() * node.anchor[1],
        image,
    )
    painter.restore()


def _luma_matte(image: QImage) -> QImage:
    import numpy as np

    straight = image.convertToFormat(QImage.Format_RGBA8888)
    array = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(straight.height(), straight.bytesPerLine())
    rgba = array[:, : straight.width() * 4].reshape(straight.height(), straight.width(), 4).copy()
    luma = np.clip(rgba[..., 0] * .2126 + rgba[..., 1] * .7152 + rgba[..., 2] * .0722, 0, 255).astype(np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = luma
    output = QImage(rgba.data, straight.width(), straight.height(), rgba.strides[0], QImage.Format_RGBA8888).copy()
    return output.convertToFormat(QImage.Format_RGBA8888_Premultiplied)


def render_graph_image(graph: RenderGraph) -> QImage:
    canvas = transparent_image(graph.width, graph.height)
    node_by_id = {node.layer_id: node for node in graph.nodes}
    matte_ids = {node.matte_layer_id for node in graph.nodes if node.matte_layer_id}
    surface_cache: dict[str, QImage] = {}

    def surface(node: RenderNode) -> QImage:
        cached = surface_cache.get(node.layer_id)
        if cached is None:
            cached = _node_surface(graph, node)
            surface_cache[node.layer_id] = cached
        return cached.copy()

    for node in graph.nodes:
        if node.layer_type == "adjustment":
            canvas = apply_effects(canvas, node.effects or [], node.local_time_ms)
            continue
        if node.layer_id in matte_ids:
            continue
        matte_node = node_by_id.get(node.matte_layer_id)
        if matte_node is None:
            canvas_painter = QPainter(canvas)
            _paint_node(canvas_painter, node)
            canvas_painter.end()
            continue
        layer_surface = surface(node)
        if matte_node is not None:
            matte = surface(matte_node)
            if node.matte_mode.lower().startswith("luma"):
                matte = _luma_matte(matte)
            mask_painter = QPainter(layer_surface)
            inverted = node.matte_inverted or node.matte_mode.lower().endswith("_inverted")
            mask_painter.setCompositionMode(
                QPainter.CompositionMode_DestinationOut if inverted else QPainter.CompositionMode_DestinationIn
            )
            mask_painter.drawImage(0, 0, matte)
            mask_painter.end()
        canvas_painter = QPainter(canvas)
        canvas_painter.setCompositionMode(BLEND_MODES.get(node.blend_mode, QPainter.CompositionMode_SourceOver))
        canvas_painter.drawImage(0, 0, layer_surface)
        canvas_painter.end()
    return canvas


def paint_render_graph(painter: QPainter, graph: RenderGraph, target: QRectF) -> None:
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.drawImage(target, render_graph_image(graph))
    painter.restore()
