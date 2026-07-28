"""Shared painter render graph for GPU preview and file export."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from typing import Any

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter, QTransform

from .adapters import render_source
from .adjustment_scope import (
    ADJUSTMENT_SCOPE_SELECTED_BELOW,
    adjustment_scope,
)
from .advanced_motion import active_2_5d_light, evaluate_replicator
from .boolean_layers import consumed_boolean_operand_ids, resolve_boolean_layer
from .effect_adapter import apply_effects
from .effect_group import resolved_effect_group_target_ids
from .evaluator import evaluate_composition
from .schema import MotionComposition, MotionEffectRef, MotionLayer
from .source_frame import transparent_image
from .puppet_gpu import PuppetGpuPacket, build_puppet_gpu_packet
from .puppet_mesh import layer_puppet_mesh
from .typography_gpu import TypographyGpuPacket, build_typography_gpu_packet
from .vector_gpu import VectorGpuPacket, build_vector_gpu_packet
from .glass_material import glass_effect
from .glass_runtime import resolve_glass_driver


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
    puppet_gpu_packet: PuppetGpuPacket | None = None
    puppet_gpu_reason: str = ""
    source_layer: MotionLayer | None = None
    source_composition: MotionComposition | None = None
    composition_time_ms: float = 0.0
    render_quality: str = "preview"
    source_viewport_size: tuple[int, int] | None = None
    replicator_instances: list[dict[str, float]] | None = None
    motion_blur_vector: tuple[float, float] = (0.0, 0.0)
    motion_blur_samples: int = 1
    motion_blur_shutter: float = 0.0
    depth_z: float = 0.0
    cast_shadows: bool = False
    receive_shadows: bool = False
    shadow_strength: float = 0.45
    shadow_softness: float = 6.0
    shadow_light_azimuth: float = 45.0
    shadow_light_elevation: float = 45.0
    shadow_light_intensity: float = 0.0
    adjustment_scope_mode: str = "all_below"
    adjustment_target_layer_ids: tuple[str, ...] = ()
    glass_driver_override: tuple[float, float] | None = None


@dataclass(slots=True)
class RenderGraph:
    width: int
    height: int
    nodes: list[RenderNode]
    diagnostics: dict[str, Any]
    effect_groups: list["EffectGroupApplication"] = field(default_factory=list)


@dataclass(slots=True)
class EffectGroupApplication:
    layer_id: str
    target_layer_ids: tuple[str, ...]
    effects: list[MotionEffectRef]
    local_time_ms: float


BLEND_MODES = {
    "normal": QPainter.CompositionMode_SourceOver,
    "add": QPainter.CompositionMode_Plus,
    "screen": QPainter.CompositionMode_Screen,
    "multiply": QPainter.CompositionMode_Multiply,
}


def _render_raster_source(
    render_layer: MotionLayer,
    local_time_ms: float,
    *,
    composition: MotionComposition,
    composition_time_ms: float,
    include_vector_gpu: bool,
    render_quality: str,
    output_size: tuple[int, int] | None,
    runtime_inputs: Mapping[str, tuple[float, float]] | None,
    composition_stack: tuple[str, ...],
) -> tuple[QImage | None, int, int]:
    if render_layer.layer_type != "precomp":
        return render_source(
            render_layer,
            local_time_ms,
            composition=composition,
            composition_time_ms=composition_time_ms,
            quality=render_quality,
            viewport_size=output_size or (composition.width, composition.height),
        ), 0, 0

    from .precomposition import apply_precomp_overrides, embedded_composition

    child = embedded_composition(render_layer)
    if child is None or child.id in (*composition_stack, composition.id):
        return (
            transparent_image(composition.width, composition.height),
            0,
            int(child is not None),
        )
    child = apply_precomp_overrides(render_layer, child, local_time_ms)
    child_graph = build_render_graph(
        child,
        local_time_ms,
        include_vector_gpu=include_vector_gpu,
        render_quality=render_quality,
        output_size=(child.width, child.height),
        runtime_inputs=runtime_inputs,
        _composition_stack=(*composition_stack, composition.id),
    )
    return render_graph_image(child_graph), 1, 0


def build_render_graph(
    composition: MotionComposition,
    time_ms: float,
    *,
    include_vector_gpu: bool = False,
    render_quality: str = "preview",
    output_size: tuple[int, int] | None = None,
    runtime_inputs: Mapping[str, tuple[float, float]] | None = None,
    _composition_stack: tuple[str, ...] = (),
) -> RenderGraph:
    states = {state.id: state for state in evaluate_composition(composition, time_ms)}
    previous_time_ms = max(0.0, float(time_ms) - 1000.0 / max(1.0, float(composition.fps)))
    previous_states = {
        state.id: state for state in evaluate_composition(composition, previous_time_ms)
    }
    consumed_operand_ids = consumed_boolean_operand_ids(composition, states)
    nodes: list[RenderNode] = []
    vector_gpu_packet_count = 0
    vector_gpu_fallback_count = 0
    typography_gpu_packet_count = 0
    typography_gpu_fallback_count = 0
    puppet_gpu_packet_count = 0
    puppet_gpu_fallback_count = 0
    replicated_node_count = 0
    motion_blur_node_count = 0
    nested_composition_count = 0
    nested_cycle_count = 0
    frame_mix_node_count = 0
    optical_flow_fallback_count = 0
    shadow_caster_count = 0
    shadow_receiver_count = 0
    shadow_light = active_2_5d_light(composition, float(time_ms)) or {}
    for layer in composition.layers:
        state = states[layer.id]
        if not state.active or layer.layer_type in {"group", "null", "camera", "light"} or layer.id in consumed_operand_ids:
            continue
        render_layer = resolve_boolean_layer(composition, layer, states)
        from .stop_motion import stop_motion_sample_time

        source_composition_time = stop_motion_sample_time(
            composition,
            render_layer,
            time_ms,
        )
        from .frame_blending import (
            frame_blending_preflight,
            frame_mix_samples,
            layer_frame_blending,
            mix_images,
        )

        frame_blending = frame_blending_preflight(render_layer)
        frame_mix_enabled = frame_blending["effective_mode"] == "frame_mix"
        if frame_blending["requested_mode"] == "optical_flow":
            optical_flow_fallback_count += 1
        active_glass_effect = glass_effect(render_layer.effects)
        has_glass = active_glass_effect is not None
        if (
            include_vector_gpu
            and render_layer.layer_type == "shape"
            and not frame_mix_enabled
            and not has_glass
        ):
            vector_gpu_packet, vector_gpu_reason = build_vector_gpu_packet(render_layer, state.local_time_ms)
        elif include_vector_gpu and render_layer.layer_type == "particle" and not frame_mix_enabled:
            from .particle_gpu import build_particle_gpu_packet

            vector_gpu_packet, vector_gpu_reason = build_particle_gpu_packet(render_layer, state.local_time_ms)
        else:
            vector_gpu_packet = None
            vector_gpu_reason = (
                "backdrop_glass_requires_raster"
                if include_vector_gpu and has_glass
                else "frame_blending_requires_raster"
                if include_vector_gpu and frame_mix_enabled
                else "not_requested" if not include_vector_gpu else "non_vector_node"
            )
        if include_vector_gpu and render_layer.layer_type == "text" and not frame_mix_enabled:
            typography_gpu_packet, typography_gpu_reason = build_typography_gpu_packet(
                render_layer, state.local_time_ms,
            )
        else:
            typography_gpu_packet = None
            typography_gpu_reason = (
                "frame_blending_requires_raster"
                if include_vector_gpu and frame_mix_enabled
                else "not_requested" if not include_vector_gpu else "non_typography_node"
            )
        puppet_gpu_packet = None
        puppet_gpu_reason = "not_requested" if not include_vector_gpu else "non_puppet_node"
        if include_vector_gpu and render_layer.layer_type == "image" and not frame_mix_enabled:
            puppet_mesh = layer_puppet_mesh(render_layer)
            if puppet_mesh is not None:
                puppet_source = render_source(
                    render_layer,
                    state.local_time_ms,
                    composition=composition,
                    composition_time_ms=source_composition_time,
                    quality=render_quality,
                    viewport_size=output_size or (composition.width, composition.height),
                )
                puppet_gpu_packet, puppet_gpu_reason = build_puppet_gpu_packet(
                    render_layer,
                    puppet_mesh,
                    puppet_source,
                    state.local_time_ms,
                    composition=composition,
                )
        image = None
        if (
            layer.layer_type != "adjustment"
            and vector_gpu_packet is None
            and typography_gpu_packet is None
            and puppet_gpu_packet is None
        ):
            if frame_mix_enabled:
                source_fps = float(
                    layer_frame_blending(render_layer).get("source_fps", 0.0)
                    or composition.fps
                )
                left_time, right_time, weight = frame_mix_samples(
                    state.local_time_ms,
                    source_fps,
                )
                left, left_nested, left_cycles = _render_raster_source(
                    render_layer,
                    left_time,
                    composition=composition,
                    composition_time_ms=source_composition_time,
                    include_vector_gpu=include_vector_gpu,
                    render_quality=render_quality,
                    output_size=output_size,
                    runtime_inputs=runtime_inputs,
                    composition_stack=_composition_stack,
                )
                right, right_nested, right_cycles = _render_raster_source(
                    render_layer,
                    right_time,
                    composition=composition,
                    composition_time_ms=source_composition_time,
                    include_vector_gpu=include_vector_gpu,
                    render_quality=render_quality,
                    output_size=output_size,
                    runtime_inputs=runtime_inputs,
                    composition_stack=_composition_stack,
                )
                nested_composition_count += left_nested + right_nested
                nested_cycle_count += left_cycles + right_cycles
                if left is not None and right is not None:
                    image = mix_images(left, right, weight)
                else:
                    image = left if left is not None else right
                frame_mix_node_count += 1
            else:
                image, nested_count, cycle_count = _render_raster_source(
                    render_layer,
                    state.local_time_ms,
                    composition=composition,
                    composition_time_ms=source_composition_time,
                    include_vector_gpu=include_vector_gpu,
                    render_quality=render_quality,
                    output_size=output_size,
                    runtime_inputs=runtime_inputs,
                    composition_stack=_composition_stack,
                )
                nested_composition_count += nested_count
                nested_cycle_count += cycle_count
            if image is not None:
                from .puppet_mesh import deform_puppet_image

                mesh = layer_puppet_mesh(render_layer)
                if mesh is not None:
                    image = deform_puppet_image(
                        image,
                        mesh,
                        state.local_time_ms,
                        composition=composition,
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
        if puppet_gpu_packet is not None:
            puppet_gpu_packet_count += 1
        elif (
            include_vector_gpu
            and render_layer.layer_type == "image"
            and layer_puppet_mesh(render_layer) is not None
        ):
            puppet_gpu_fallback_count += 1
        replicator = evaluate_replicator(layer.metadata.get("replicator"), state.local_time_ms)
        if len(replicator) > 1:
            replicated_node_count += 1
        motion_blur = layer.metadata.get("motion_blur")
        if not isinstance(motion_blur, dict):
            motion_blur = composition.metadata.get("motion_blur")
        motion_blur = motion_blur if isinstance(motion_blur, dict) else {}
        blur_enabled = bool(motion_blur.get("enabled", False))
        samples = max(1, min(32, int(motion_blur.get("samples", 8) or 8))) if blur_enabled else 1
        shutter = max(0.0, min(2.0, float(motion_blur.get("shutter", 0.65) or 0.0))) if blur_enabled else 0.0
        previous = previous_states.get(layer.id)
        vector = (
            float(state.matrix[4] - previous.matrix[4]) * shutter,
            float(state.matrix[5] - previous.matrix[5]) * shutter,
        ) if previous is not None and blur_enabled else (0.0, 0.0)
        if samples > 1 and (abs(vector[0]) > 0.05 or abs(vector[1]) > 0.05):
            motion_blur_node_count += 1
        three_d = layer.metadata.get("three_d")
        three_d = three_d if isinstance(three_d, dict) else {}
        three_d_enabled = bool(three_d.get("enabled", False))
        cast_shadows = three_d_enabled and bool(three_d.get("cast_shadows", False))
        receive_shadows = three_d_enabled and bool(
            three_d.get("receive_shadows", False)
        )
        shadow_caster_count += int(cast_shadows)
        shadow_receiver_count += int(receive_shadows)
        scope = adjustment_scope(layer)
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
            puppet_gpu_packet=puppet_gpu_packet,
            puppet_gpu_reason=puppet_gpu_reason,
            source_layer=render_layer,
            source_composition=composition,
            composition_time_ms=source_composition_time,
            render_quality=str(render_quality),
            source_viewport_size=output_size or (composition.width, composition.height),
            replicator_instances=replicator,
            motion_blur_vector=vector,
            motion_blur_samples=samples,
            motion_blur_shutter=shutter,
            depth_z=max(
                -8.0,
                min(8.0, float(layer.metadata.get("depth_z", 0.0) or 0.0)),
            ),
            cast_shadows=cast_shadows,
            receive_shadows=receive_shadows,
            shadow_strength=max(
                0.0,
                min(1.0, float(three_d.get("shadow_strength", 0.45) or 0.0)),
            ),
            shadow_softness=max(
                0.0,
                min(32.0, float(three_d.get("shadow_softness", 6.0) or 0.0)),
            ),
            shadow_light_azimuth=float(shadow_light.get("azimuth", 45.0)),
            shadow_light_elevation=float(shadow_light.get("elevation", 45.0)),
            shadow_light_intensity=float(shadow_light.get("intensity", 0.0)),
            adjustment_scope_mode=scope["mode"],
            adjustment_target_layer_ids=tuple(scope["layer_ids"]),
            glass_driver_override=(
                resolve_glass_driver(
                    active_glass_effect,
                    runtime_inputs,
                    time_ms=state.local_time_ms,
                )
                if active_glass_effect is not None
                else None
            ),
        ))
    effect_groups = [
        EffectGroupApplication(
            layer_id=layer.id,
            target_layer_ids=tuple(resolved_effect_group_target_ids(composition, layer)),
            effects=list(layer.effects),
            local_time_ms=states[layer.id].local_time_ms,
        )
        for layer in composition.layers
        if (
            layer.layer_type == "group"
            and states[layer.id].active
            and layer.effects
            and resolved_effect_group_target_ids(composition, layer)
        )
    ]
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
        "puppet_gpu_packet_count": puppet_gpu_packet_count,
        "puppet_gpu_fallback_count": puppet_gpu_fallback_count,
        "puppet_gpu_requested": include_vector_gpu,
        "render_quality": str(render_quality),
        "output_size": list(output_size or (composition.width, composition.height)),
        "replicated_node_count": replicated_node_count,
        "motion_blur_node_count": motion_blur_node_count,
        "nested_composition_count": nested_composition_count,
        "nested_cycle_count": nested_cycle_count,
        "frame_mix_node_count": frame_mix_node_count,
        "optical_flow_fallback_count": optical_flow_fallback_count,
        "card_shadow_caster_count": shadow_caster_count,
        "card_shadow_receiver_count": shadow_receiver_count,
        "card_shadow_light_ready": bool(shadow_light),
        "card_shadow_renderer": "qt_raster_receiver_clipped",
        "scoped_adjustment_count": sum(
            1
            for node in nodes
            if node.layer_type == "adjustment"
            and node.adjustment_scope_mode == ADJUSTMENT_SCOPE_SELECTED_BELOW
        ),
        "effect_group_count": len(effect_groups),
        "effect_group_target_count": sum(
            len(group.target_layer_ids) for group in effect_groups
        ),
    }, effect_groups=effect_groups)


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
        if node.image is not None:
            from .puppet_mesh import deform_puppet_image, layer_puppet_mesh

            mesh = layer_puppet_mesh(node.source_layer)
            if mesh is not None:
                node.image = deform_puppet_image(
                    node.image,
                    mesh,
                    node.local_time_ms,
                    composition=node.source_composition,
                )
    return node.image


def _instance_transform(node: RenderNode, instance: dict[str, float]) -> QTransform:
    a, b, c, d, tx, ty = node.matrix
    base = QTransform(a, b, 0.0, c, d, 0.0, tx, ty, 1.0)
    local = QTransform()
    local.translate(float(instance.get("x", 0.0)), float(instance.get("y", 0.0)))
    local.rotate(float(instance.get("rotation", 0.0)))
    local.scale(float(instance.get("scale_x", 1.0)), float(instance.get("scale_y", 1.0)))
    return local * base


def _apply_motion_blur(
    surface: QImage,
    node: RenderNode,
    *,
    pixel_scale: tuple[float, float] = (1.0, 1.0),
) -> QImage:
    dx, dy = node.motion_blur_vector
    dx *= float(pixel_scale[0])
    dy *= float(pixel_scale[1])
    samples = max(1, int(node.motion_blur_samples))
    if samples <= 1 or (abs(dx) <= 0.05 and abs(dy) <= 0.05):
        return surface
    import cv2
    import numpy as np

    straight = surface.convertToFormat(QImage.Format_RGBA8888)
    raw = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(
        straight.height(), straight.bytesPerLine(),
    )
    rgba = raw[:, : straight.width() * 4].reshape(straight.height(), straight.width(), 4).astype(np.float32)
    visible_y, visible_x = np.nonzero(rgba[..., 3] > 0.5)
    if visible_x.size == 0:
        return surface
    margin = int(max(abs(dx), abs(dy)) * 0.6) + 3
    left = max(0, int(visible_x.min()) - margin)
    right = min(straight.width(), int(visible_x.max()) + margin + 1)
    top = max(0, int(visible_y.min()) - margin)
    bottom = min(straight.height(), int(visible_y.max()) + margin + 1)
    region = rgba[top:bottom, left:right]
    accumulated = np.zeros_like(region, dtype=np.float32)
    for index in range(samples):
        amount = index / max(1, samples - 1) - 0.5
        matrix = np.array([[1.0, 0.0, -dx * amount], [0.0, 1.0, -dy * amount]], dtype=np.float32)
        accumulated += cv2.warpAffine(
            region,
            matrix,
            (region.shape[1], region.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )
    output = np.zeros_like(rgba, dtype=np.uint8)
    output[top:bottom, left:right] = np.clip(accumulated / samples, 0, 255).astype(np.uint8)
    output = np.ascontiguousarray(output)
    image = QImage(
        output.data, straight.width(), straight.height(), output.strides[0], QImage.Format_RGBA8888,
    ).copy()
    return image.convertToFormat(QImage.Format_RGBA8888_Premultiplied)


def _node_surface(
    graph: RenderGraph,
    node: RenderNode,
    *,
    output_size: tuple[int, int] | None = None,
) -> QImage:
    width, height = output_size or (graph.width, graph.height)
    scale_x = width / max(1.0, float(graph.width))
    scale_y = height / max(1.0, float(graph.height))
    surface = transparent_image(width, height)
    image = _node_image(node)
    if image is None:
        return surface
    layer_painter = QPainter(surface)
    layer_painter.setRenderHint(QPainter.Antialiasing)
    layer_painter.setRenderHint(QPainter.SmoothPixmapTransform)
    layer_painter.scale(scale_x, scale_y)
    for instance in node.replicator_instances or [{"opacity": 1.0}]:
        layer_painter.save()
        layer_painter.setOpacity(node.opacity * float(instance.get("opacity", 1.0)))
        layer_painter.setTransform(
            _instance_transform(node, instance),
            combine=True,
        )
        layer_painter.drawImage(
            -image.width() * node.anchor[0],
            -image.height() * node.anchor[1],
            image,
        )
        layer_painter.restore()
    layer_painter.end()
    return _apply_motion_blur(
        surface,
        node,
        pixel_scale=(scale_x, scale_y),
    )


def _paint_node(painter: QPainter, node: RenderNode) -> None:
    image = _node_image(node)
    if image is None:
        return
    for instance in node.replicator_instances or [{"opacity": 1.0}]:
        painter.save()
        painter.setCompositionMode(BLEND_MODES.get(node.blend_mode, QPainter.CompositionMode_SourceOver))
        painter.setOpacity(node.opacity * float(instance.get("opacity", 1.0)))
        painter.setTransform(_instance_transform(node, instance), combine=True)
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


def _card_shadow_surface(
    caster: QImage,
    receiver: QImage,
    *,
    depth_delta: float,
    azimuth: float,
    elevation: float,
    intensity: float,
    strength: float,
    softness: float,
    pixel_scale: float = 1.0,
) -> QImage | None:
    if depth_delta <= 0.0 or intensity <= 0.0 or strength <= 0.0:
        return None
    import cv2
    import numpy as np

    caster_straight = caster.convertToFormat(QImage.Format_RGBA8888)
    receiver_straight = receiver.convertToFormat(QImage.Format_RGBA8888)
    width = min(caster_straight.width(), receiver_straight.width())
    height = min(caster_straight.height(), receiver_straight.height())
    if width <= 0 or height <= 0:
        return None

    def alpha(image: QImage) -> np.ndarray:
        rows = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
            image.height(),
            image.bytesPerLine(),
        )
        return rows[:height, : width * 4].reshape(height, width, 4)[..., 3]

    caster_alpha = alpha(caster_straight).astype(np.float32)
    receiver_alpha = alpha(receiver_straight).astype(np.float32) / 255.0
    if caster_alpha.max(initial=0.0) <= 0.0 or receiver_alpha.max(initial=0.0) <= 0.0:
        return None
    if softness > 0.01:
        caster_alpha = cv2.GaussianBlur(
            caster_alpha,
            (0, 0),
            sigmaX=max(0.01, float(softness) * pixel_scale),
            sigmaY=max(0.01, float(softness) * pixel_scale),
            borderType=cv2.BORDER_CONSTANT,
        )
    elevation_radians = math.radians(max(5.0, min(89.0, elevation)))
    distance = min(
        float(max(width, height)),
        max(0.0, float(depth_delta)) * 36.0 * pixel_scale
        / max(0.087, math.tan(elevation_radians)),
    )
    azimuth_radians = math.radians(float(azimuth))
    offset_x = -math.cos(azimuth_radians) * distance
    offset_y = math.sin(azimuth_radians) * distance
    shifted = cv2.warpAffine(
        caster_alpha,
        np.asarray(
            [[1.0, 0.0, offset_x], [0.0, 1.0, offset_y]],
            dtype=np.float32,
        ),
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    light_factor = max(0.0, min(1.0, float(intensity) / 0.42))
    shadow_alpha = np.clip(
        shifted * receiver_alpha * float(strength) * light_factor,
        0.0,
        255.0,
    ).astype(np.uint8)
    if shadow_alpha.max(initial=0) == 0:
        return None
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[..., 3] = shadow_alpha
    rgba = np.ascontiguousarray(rgba)
    return QImage(
        rgba.data,
        width,
        height,
        rgba.strides[0],
        QImage.Format_RGBA8888,
    ).copy().convertToFormat(QImage.Format_RGBA8888_Premultiplied)


def render_graph_image(
    graph: RenderGraph,
    *,
    output_size: tuple[int, int] | None = None,
) -> QImage:
    width, height = output_size or (graph.width, graph.height)
    width, height = max(1, int(width)), max(1, int(height))
    scale_x = width / max(1.0, float(graph.width))
    scale_y = height / max(1.0, float(graph.height))
    pixel_scale = min(scale_x, scale_y)
    canvas = transparent_image(width, height)
    node_by_id = {node.layer_id: node for node in graph.nodes}
    matte_ids = {node.matte_layer_id for node in graph.nodes if node.matte_layer_id}
    surface_cache: dict[str, QImage] = {}
    shadow_receivers: list[tuple[RenderNode, QImage]] = []
    scoped_adjustments: dict[str, list[RenderNode]] = {}
    scoped_effect_groups: dict[str, list[EffectGroupApplication]] = {}
    for group in graph.effect_groups:
        for layer_id in group.target_layer_ids:
            scoped_effect_groups.setdefault(layer_id, []).append(group)
    lower_renderable_ids: set[str] = set()
    for node in graph.nodes:
        if node.layer_type == "adjustment":
            if node.adjustment_scope_mode == ADJUSTMENT_SCOPE_SELECTED_BELOW:
                for layer_id in node.adjustment_target_layer_ids:
                    if layer_id in lower_renderable_ids:
                        scoped_adjustments.setdefault(layer_id, []).append(node)
            continue
        lower_renderable_ids.add(node.layer_id)

    def surface(node: RenderNode) -> QImage:
        cached = surface_cache.get(node.layer_id)
        if cached is None:
            cached = _node_surface(
                graph,
                node,
                output_size=(width, height),
            )
            cached = apply_effects(cached, node.effects or [], node.local_time_ms)
            for group in scoped_effect_groups.get(node.layer_id, ()):
                cached = apply_effects(
                    cached,
                    group.effects,
                    group.local_time_ms,
                )
            for adjustment in scoped_adjustments.get(node.layer_id, ()):
                cached = apply_effects(
                    cached,
                    adjustment.effects or [],
                    adjustment.local_time_ms,
                )
            surface_cache[node.layer_id] = cached
        return cached.copy()

    for node in graph.nodes:
        if node.layer_type == "adjustment":
            if node.adjustment_scope_mode != ADJUSTMENT_SCOPE_SELECTED_BELOW:
                canvas = apply_effects(canvas, node.effects or [], node.local_time_ms)
            continue
        if node.layer_id in matte_ids:
            continue
        matte_node = node_by_id.get(node.matte_layer_id)
        requires_surface = (
            matte_node is not None
            or len(node.replicator_instances or ()) > 1
            or node.motion_blur_samples > 1
            or node.cast_shadows
            or node.receive_shadows
            or bool(node.effects)
            or node.layer_id in scoped_effect_groups
            or node.layer_id in scoped_adjustments
        )
        if not requires_surface:
            canvas_painter = QPainter(canvas)
            canvas_painter.scale(scale_x, scale_y)
            _paint_node(canvas_painter, node)
            canvas_painter.end()
            continue
        layer_surface = surface(node)
        glass = glass_effect(node.effects)
        if glass is not None:
            from .glass_renderer import render_glass_surface

            layer_surface = render_glass_surface(
                canvas,
                layer_surface,
                glass,
                node.local_time_ms,
                driver_override=node.glass_driver_override,
                pixel_scale=pixel_scale,
            )
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
        if node.cast_shadows:
            for receiver_node, receiver_surface in shadow_receivers:
                shadow = _card_shadow_surface(
                    layer_surface,
                    receiver_surface,
                    depth_delta=node.depth_z - receiver_node.depth_z,
                    azimuth=node.shadow_light_azimuth,
                    elevation=node.shadow_light_elevation,
                    intensity=node.shadow_light_intensity,
                    strength=node.shadow_strength,
                    softness=node.shadow_softness,
                    pixel_scale=pixel_scale,
                )
                if shadow is not None:
                    shadow_painter = QPainter(canvas)
                    shadow_painter.setCompositionMode(
                        QPainter.CompositionMode_SourceOver
                    )
                    shadow_painter.drawImage(0, 0, shadow)
                    shadow_painter.end()
        canvas_painter = QPainter(canvas)
        canvas_painter.setCompositionMode(BLEND_MODES.get(node.blend_mode, QPainter.CompositionMode_SourceOver))
        canvas_painter.drawImage(0, 0, layer_surface)
        canvas_painter.end()
        if node.receive_shadows:
            shadow_receivers.append((node, layer_surface.copy()))
    return canvas


def paint_render_graph(
    painter: QPainter,
    graph: RenderGraph,
    target: QRectF,
    *,
    raster_size: tuple[int, int] | None = None,
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.drawImage(
        target,
        render_graph_image(graph, output_size=raster_size),
    )
    painter.restore()
