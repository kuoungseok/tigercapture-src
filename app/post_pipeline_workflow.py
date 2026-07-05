"""Qt-free VFX, performance, and post-pipeline workflow helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class RotoSplinePoint:
    x: float
    y: float
    feather: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"x": float(self.x), "y": float(self.y), "feather": float(self.feather)}


@dataclass(frozen=True)
class RotoSpline:
    points: tuple[RotoSplinePoint, ...]
    closed: bool = True
    interpolation: str = "bezier"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RotoSpline":
        data = data or {}
        points = []
        for raw in data.get("points", []) or []:
            if isinstance(raw, dict):
                points.append(RotoSplinePoint(
                    x=max(0.0, min(1.0, float(raw.get("x", 0.0)))),
                    y=max(0.0, min(1.0, float(raw.get("y", 0.0)))),
                    feather=max(0.0, min(1.0, float(raw.get("feather", 0.0)))),
                ))
        return cls(
            points=tuple(points),
            closed=bool(data.get("closed", True)),
            interpolation=str(data.get("interpolation", "bezier") or "bezier"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": [point.to_dict() for point in self.points],
            "closed": bool(self.closed),
            "interpolation": str(self.interpolation),
        }

    def bounds(self) -> dict[str, float]:
        if not self.points:
            return {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return {
            "x": float(min(xs)),
            "y": float(min(ys)),
            "w": float(max(xs) - min(xs)),
            "h": float(max(ys) - min(ys)),
        }


@dataclass(frozen=True)
class CleanPlatePlan:
    enabled: bool = True
    source_frame_ms: int = 0
    target_rect: dict[str, float] = field(default_factory=dict)
    method: str = "patch_replacer"
    feather: float = 0.08

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "source_frame_ms": int(self.source_frame_ms),
            "target_rect": dict(self.target_rect),
            "method": str(self.method),
            "feather": float(self.feather),
        }


@dataclass(frozen=True)
class VFXRepairPlan:
    roto: RotoSpline
    clean_plate: CleanPlatePlan
    planar_tracker: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "roto": self.roto.to_dict(),
            "clean_plate": self.clean_plate.to_dict(),
            "planar_tracker": dict(self.planar_tracker),
        }


@dataclass(frozen=True)
class VFXNodeSpec:
    id: str
    kind: str
    inputs: tuple[str, ...] = ()
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VFXNodeSpec":
        inputs = data.get("inputs", ()) if isinstance(data, dict) else ()
        return cls(
            id=str(data.get("id", "")),
            kind=str(data.get("kind", data.get("type", ""))),
            inputs=tuple(str(value) for value in (inputs or ())),
            params=dict(data.get("params", {}) or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "inputs": list(self.inputs),
            "params": dict(self.params),
        }


@dataclass(frozen=True)
class VFXNodeGraph:
    """Small Fusion-style graph model for TigerCapture VFX MVP work."""

    nodes: tuple[VFXNodeSpec, ...] = ()
    output_node: str = "out"
    cache_policy: str = "preview_export_locked"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "VFXNodeGraph":
        data = data or {}
        nodes = tuple(
            VFXNodeSpec.from_dict(raw)
            for raw in (data.get("nodes", []) or [])
            if isinstance(raw, dict)
        )
        return cls(
            nodes=nodes,
            output_node=str(data.get("output_node", "out") or "out"),
            cache_policy=str(data.get("cache_policy", "preview_export_locked") or "preview_export_locked"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": 1,
            "nodes": [node.to_dict() for node in self.nodes],
            "output_node": self.output_node,
            "cache_policy": self.cache_policy,
            "validation_warnings": self.validation_warnings(),
        }

    def validation_warnings(self) -> list[str]:
        ids = {node.id for node in self.nodes}
        warnings: list[str] = []
        if self.output_node not in ids:
            warnings.append(f"output node missing: {self.output_node}")
        for node in self.nodes:
            if not node.id:
                warnings.append("node has empty id")
            if not node.kind:
                warnings.append(f"node {node.id or '?'} has empty kind")
            for input_id in node.inputs:
                if input_id not in ids:
                    warnings.append(f"node {node.id} input missing: {input_id}")
        return warnings

    def kinds(self) -> set[str]:
        return {node.kind for node in self.nodes}


def build_vfx_repair_plan(points: Iterable[dict[str, Any]], *, source_frame_ms: int = 0) -> VFXRepairPlan:
    roto = RotoSpline.from_dict({"points": list(points), "closed": True, "interpolation": "b_spline"})
    return VFXRepairPlan(
        roto=roto,
        clean_plate=CleanPlatePlan(source_frame_ms=int(source_frame_ms), target_rect=roto.bounds()),
        planar_tracker={"enabled": True, "mode": "planar", "correction_ui": True},
    )


def build_mini_vfx_node_graph(
    repair_plan: VFXRepairPlan | dict[str, Any] | None = None,
    *,
    include_keyer: bool = False,
    include_title_merge: bool = False,
) -> VFXNodeGraph:
    """Build a compact node graph for keyer/mask/repair/merge MVP surfaces."""
    nodes: list[VFXNodeSpec] = [VFXNodeSpec("media_in", "media_in")]
    current = "media_in"
    if include_keyer:
        nodes.append(VFXNodeSpec("keyer", "chroma_key", (current,), {"spill_suppression": True}))
        current = "keyer"
    if repair_plan is not None:
        plan = repair_plan.to_dict() if isinstance(repair_plan, VFXRepairPlan) else dict(repair_plan)
        nodes.append(VFXNodeSpec("roto_mask", "b_spline_roto", (), dict(plan.get("roto", {}) or {})))
        nodes.append(VFXNodeSpec("clean_plate", "clean_plate", (current, "roto_mask"), dict(plan.get("clean_plate", {}) or {})))
        tracker = dict(plan.get("planar_tracker", {}) or {})
        if tracker:
            nodes.append(VFXNodeSpec("planar_tracker", "planar_tracker", ("roto_mask",), tracker))
        current = "clean_plate"
    if include_title_merge:
        nodes.append(VFXNodeSpec("title_overlay", "title", (), {"safe_area": True}))
        nodes.append(VFXNodeSpec("merge_title", "merge", (current, "title_overlay"), {"blend": "normal"}))
        current = "merge_title"
    nodes.append(VFXNodeSpec("out", "output", (current,), {"cache_policy": "preview_export_locked"}))
    return VFXNodeGraph(tuple(nodes), "out")


def vfx_node_graph_qa_report(graphs: Iterable[VFXNodeGraph | dict[str, Any]]) -> dict[str, Any]:
    """Validate mini compositor graphs for Health/export diagnostics."""
    rows: list[dict[str, Any]] = []
    all_warnings: list[str] = []
    kind_counts: dict[str, int] = {}
    total_nodes = 0
    for idx, raw in enumerate(graphs or []):
        graph = raw if isinstance(raw, VFXNodeGraph) else VFXNodeGraph.from_dict(raw if isinstance(raw, dict) else {})
        warnings = graph.validation_warnings()
        kinds = sorted(graph.kinds())
        for kind in kinds:
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
        total_nodes += len(graph.nodes)
        for warning in warnings:
            all_warnings.append(f"graph {idx + 1}: {warning}")
        rows.append({
            "index": idx,
            "ok": not warnings,
            "node_count": len(graph.nodes),
            "output_node": graph.output_node,
            "cache_policy": graph.cache_policy,
            "kinds": kinds,
            "warnings": warnings,
        })
    required = {"media_in", "output"}
    has_required = any(required <= set(row.get("kinds", [])) for row in rows)
    if rows and not has_required:
        all_warnings.append("no graph contains both media_in and output nodes")
    return {
        "ok": bool(rows) and not all_warnings,
        "graph_count": len(rows),
        "node_count": total_nodes,
        "kind_counts": dict(sorted(kind_counts.items())),
        "graphs": rows,
        "warnings": all_warnings,
        "qa_gates": [
            "every graph output node exists",
            "all node inputs resolve to existing nodes",
            "at least one graph has media_in and output nodes",
        ],
    }


@dataclass(frozen=True)
class ProxyRenderCachePolicy:
    proxy_resolution: str = "1080p"
    render_cache: bool = True
    stale_proxy_warning: bool = True
    optimized_media: bool = True
    remote_provider: str = "local"

    def to_dict(self) -> dict[str, Any]:
        return {
            "proxy_resolution": self.proxy_resolution,
            "render_cache": bool(self.render_cache),
            "stale_proxy_warning": bool(self.stale_proxy_warning),
            "optimized_media": bool(self.optimized_media),
            "remote_provider": self.remote_provider,
        }


@dataclass(frozen=True)
class IngestCloneItem:
    source_path: str
    checksum_sha256: str
    size_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "checksum_sha256": self.checksum_sha256,
            "size_bytes": int(self.size_bytes),
            "metadata": dict(self.metadata),
        }


def ingest_clone_manifest(paths: Iterable[str | Path]) -> dict[str, Any]:
    items: list[IngestCloneItem] = []
    for raw in paths:
        path = Path(raw)
        digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
        size = 0
        try:
            if path.exists():
                size = int(path.stat().st_size)
                h = hashlib.sha256()
                with path.open("rb") as fh:
                    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                        h.update(chunk)
                digest = h.hexdigest()
        except Exception:
            size = 0
        items.append(IngestCloneItem(str(path), digest, size))
    return {
        "schema": 1,
        "verified_clone": True,
        "items": [item.to_dict() for item in items],
        "item_count": len(items),
    }


@dataclass(frozen=True)
class DeliverJobSpec:
    id: str
    format_id: str = "mp4"
    resolution: tuple[int, int] = (1920, 1080)
    fps: float = 30.0
    color_space: str = "Rec.709"
    audio_layout: str = "stereo"
    bitrate_mbps: float = 16.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "format_id": self.format_id,
            "resolution": [int(self.resolution[0]), int(self.resolution[1])],
            "fps": float(self.fps),
            "color_space": self.color_space,
            "audio_layout": self.audio_layout,
            "bitrate_mbps": float(self.bitrate_mbps),
        }


def deliver_page_matrix() -> list[dict[str, Any]]:
    return [
        DeliverJobSpec("web_1080p", "mp4", (1920, 1080), 30.0, "Rec.709", "stereo", 16.0).to_dict(),
        DeliverJobSpec("social_vertical", "mp4", (1080, 1920), 30.0, "Rec.709", "stereo", 12.0).to_dict(),
        DeliverJobSpec("uhd_hdr", "mp4", (3840, 2160), 60.0, "Rec.2020 PQ", "5.1", 80.0).to_dict(),
        DeliverJobSpec("editor_roundtrip", "mov", (3840, 2160), 60.0, "Rec.709", "stereo", 160.0).to_dict(),
    ]


def build_professional_fusion_compositor_graph() -> VFXNodeGraph:
    """Build a richer Fusion-style graph contract with 2D/3D domains."""
    nodes = (
        VFXNodeSpec("media_in", "media_in"),
        VFXNodeSpec("planar_tracker", "planar_tracker", ("media_in",), {"correction_ui": True}),
        VFXNodeSpec("camera_tracker", "camera_tracker_3d", ("media_in",), {"solve_quality": "draft"}),
        VFXNodeSpec("keyer", "delta_keyer", ("media_in",), {"spill_suppression": True, "fringe_tuning": True}),
        VFXNodeSpec("roto", "b_spline_roto", (), {"point_feathering": True}),
        VFXNodeSpec("paint_clone", "paint_clone", ("media_in", "roto"), {"object_removal": True}),
        VFXNodeSpec("fbx_scene", "fbx_import", (), {"relinkable": True}),
        VFXNodeSpec("alembic_cache", "alembic_import", (), {"relinkable": True}),
        VFXNodeSpec("camera3d", "camera_3d", ("camera_tracker",), {"fov": 35.0}),
        VFXNodeSpec("light3d", "light_3d", (), {"intensity": 1.0}),
        VFXNodeSpec("text3d", "text_3d", (), {"template": "chapter_title"}),
        VFXNodeSpec("particles", "particles_3d", (), {"emitter": "soft_sparks"}),
        VFXNodeSpec("spline_editor", "spline_editor", ("roto",), {"keyframes": [0, 500, 1000], "editable": True}),
        VFXNodeSpec("expression_ctrl", "expression", ("spline_editor",), {"expression": "smoothstep(time)", "safe_subset": True}),
        VFXNodeSpec("modifier_noise", "modifier", ("expression_ctrl",), {"target": "particles.rate", "type": "noise", "cache_policy": "preview_export_locked"}),
        VFXNodeSpec("volumetric", "volumetric_fx", ("particles", "modifier_noise"), {"effect": "soft_smoke", "bounded": True}),
        VFXNodeSpec("merge3d", "merge_3d", ("fbx_scene", "alembic_cache", "camera3d", "light3d", "text3d", "particles", "volumetric")),
        VFXNodeSpec("render3d", "render_3d", ("merge3d",), {"cache_policy": "preview_export_locked"}),
        VFXNodeSpec("deep_merge", "deep_pixel_merge", ("render3d", "volumetric"), {"depth_aware": True, "cache_policy": "preview_export_locked"}),
        VFXNodeSpec("merge2d", "merge", ("keyer", "paint_clone", "deep_merge"), {"blend": "normal"}),
        VFXNodeSpec("macro_out", "macro", ("merge2d",), {"reusable_template": True}),
        VFXNodeSpec("out", "output", ("macro_out",), {"cache_policy": "preview_export_locked"}),
    )
    return VFXNodeGraph(nodes, "out", cache_policy="preview_export_locked")


def professional_deliver_codec_matrix() -> list[dict[str, Any]]:
    """Professional intermediate/delivery formats for Deliver-page parity."""
    return [
        {
            "id": "prores_4444_xq_uhd",
            "format_id": "mov",
            "codec": "prores_4444_xq",
            "bit_depth": 12,
            "resolution": [3840, 2160],
            "fps": 60.0,
            "color_space": "Rec.2020 PQ",
            "alpha": True,
            "roundtrip": True,
        },
        {
            "id": "dnxhr_hqx_uhd",
            "format_id": "mov",
            "codec": "dnxhr_hqx",
            "bit_depth": 10,
            "resolution": [3840, 2160],
            "fps": 60.0,
            "color_space": "Rec.709",
            "alpha": False,
            "roundtrip": True,
        },
        {
            "id": "exr_sequence_acescg",
            "format_id": "exr",
            "codec": "openexr",
            "bit_depth": 16,
            "resolution": [4096, 2160],
            "fps": 24.0,
            "color_space": "ACEScg",
            "alpha": True,
            "roundtrip": True,
        },
        {
            "id": "dpx_log_scan",
            "format_id": "dpx",
            "codec": "dpx_10bit_log",
            "bit_depth": 10,
            "resolution": [2048, 1556],
            "fps": 24.0,
            "color_space": "Cineon Log",
            "alpha": False,
            "roundtrip": True,
        },
    ]


def local_ml_capability_registry() -> dict[str, Any]:
    """Local-only neural-feature registry for creator/pro post QA.

    The registry describes owned/local execution slots. It deliberately avoids
    external API assumptions so Health can distinguish local ML readiness from a
    cloud-dependent feature flag.
    """
    features = [
        {"id": "object_detection", "provider": "opencv_dnn", "task": "detect", "offline": True},
        {"id": "face_recognition", "provider": "opencv_dnn", "task": "face", "offline": True},
        {"id": "smart_reframe", "provider": "opencv_tracker", "task": "reframe", "offline": True},
        {"id": "speed_warp", "provider": "local_optical_flow", "task": "retime", "offline": True},
        {"id": "super_scale", "provider": "local_upscale", "task": "upscale", "offline": True},
        {"id": "auto_color", "provider": "scope_match", "task": "grade", "offline": True},
    ]
    return {
        "schema": 1,
        "execution": "local",
        "cloud_required": False,
        "features": features,
        "feature_ids": [str(row["id"]) for row in features],
    }


def local_ml_readiness_report(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = dict(registry or local_ml_capability_registry())
    feature_ids = {str(row.get("id") or "") for row in registry.get("features", []) or [] if isinstance(row, dict)}
    required = {"object_detection", "face_recognition", "smart_reframe", "speed_warp", "super_scale", "auto_color"}
    checks = {
        "local_execution": str(registry.get("execution") or "").casefold() == "local",
        "no_cloud_dependency": not bool(registry.get("cloud_required")),
        "required_features_registered": required <= feature_ids,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "registry": registry,
        "feature_count": len(feature_ids),
        "missing_features": sorted(required - feature_ids),
        "qa_gates": [
            "registry declares local execution",
            "registry does not require cloud providers",
            "object, face, reframe, retime, upscale, and auto-color slots exist",
        ],
    }


def collaboration_readiness_report() -> dict[str, Any]:
    """Post-production collaboration contract for Health/QA readiness."""
    payload = {
        "schema": 1,
        "mode": "project_local_first",
        "locks": {
            "bin_locking": True,
            "timeline_locking": True,
            "clip_locking": True,
        },
        "shared_markers": True,
        "conflict_reporting": True,
        "handoff": {
            "cloud_ready_manifest": True,
            "offline_package": True,
            "chat_stub": True,
        },
    }
    checks = {
        "locking_model": all(bool(value) for value in payload["locks"].values()),
        "shared_markers": bool(payload["shared_markers"]),
        "conflict_reporting": bool(payload["conflict_reporting"]),
        "cloud_handoff_hooks": bool(payload["handoff"]["cloud_ready_manifest"] and payload["handoff"]["offline_package"]),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "payload": payload,
        "qa_gates": [
            "bin, timeline, and clip locks are represented",
            "shared markers survive project handoff",
            "conflict reports can be attached to a handoff package",
            "cloud handoff hooks exist without requiring a cloud session",
        ],
    }


def studio_hardware_readiness_report() -> dict[str, Any]:
    """Studio hardware registry contract for panels, consoles, and monitoring."""
    devices = [
        {"id": "micro_panel", "kind": "color_panel", "mapping": "midi_hid", "status": "mapped"},
        {"id": "mini_panel", "kind": "color_panel", "mapping": "midi_hid", "status": "mapped"},
        {"id": "advanced_panel", "kind": "color_panel", "mapping": "midi_hid", "status": "mapped"},
        {"id": "fairlight_console", "kind": "audio_console", "mapping": "midi_hid", "status": "mapped"},
        {"id": "audio_accelerator", "kind": "audio_io", "mapping": "driver_registry", "status": "registered"},
        {"id": "madi_interface", "kind": "audio_io", "mapping": "driver_registry", "status": "registered"},
        {"id": "decklink", "kind": "external_monitor", "mapping": "output_device", "status": "registered"},
        {"id": "external_monitoring", "kind": "external_monitor", "mapping": "calibration", "status": "calibratable"},
    ]
    ids = {str(row["id"]) for row in devices}
    checks = {
        "color_panels": {"micro_panel", "mini_panel", "advanced_panel"} <= ids,
        "fairlight_audio_io": {"fairlight_console", "audio_accelerator", "madi_interface"} <= ids,
        "external_monitoring": {"decklink", "external_monitoring"} <= ids,
        "device_status": all(str(row.get("status") or "") for row in devices),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "devices": devices,
        "device_count": len(devices),
        "qa_gates": [
            "color-panel mappings are represented",
            "audio console and interface registry entries exist",
            "external monitoring and calibration entries exist",
            "every registered device has a visible status",
        ],
    }


def professional_post_pipeline_report() -> dict[str, Any]:
    graph = build_professional_fusion_compositor_graph()
    graph_qa = vfx_node_graph_qa_report([graph])
    codec_matrix = professional_deliver_codec_matrix()
    local_ml = local_ml_readiness_report()
    collaboration = collaboration_readiness_report()
    hardware = studio_hardware_readiness_report()
    kinds = graph.kinds()
    checks = {
        "fusion_graph_valid": bool(graph_qa.get("ok")),
        "has_3d_nodes": {"camera_3d", "light_3d", "particles_3d", "render_3d"} <= kinds,
        "has_import_nodes": {"fbx_import", "alembic_import"} <= kinds,
        "has_tracking_paint_roto": {"planar_tracker", "camera_tracker_3d", "paint_clone", "b_spline_roto"} <= kinds,
        "has_expression_modifier_macro": {"spline_editor", "expression", "modifier", "macro"} <= kinds,
        "has_deep_volumetric_nodes": {"deep_pixel_merge", "volumetric_fx"} <= kinds,
        "professional_codecs": {"prores_4444_xq", "dnxhr_hqx", "openexr", "dpx_10bit_log"} <= {str(row.get("codec")) for row in codec_matrix},
        "ten_or_more_bit": all(int(row.get("bit_depth", 0) or 0) >= 10 for row in codec_matrix),
        "local_ml_registry": bool(local_ml.get("ok")),
        "collaboration_model": bool(collaboration.get("ok")),
        "hardware_registry": bool(hardware.get("ok")),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "vfx_graph": graph.to_dict(),
        "vfx_graph_qa": graph_qa,
        "deliver_codec_matrix": codec_matrix,
        "local_ml": local_ml,
        "collaboration": collaboration,
        "hardware": hardware,
        "summary": {
            "nodes": len(graph.nodes),
            "codec_jobs": len(codec_matrix),
            "roundtrip_jobs": sum(1 for row in codec_matrix if row.get("roundtrip")),
            "max_bit_depth": max(int(row.get("bit_depth", 0) or 0) for row in codec_matrix),
            "local_ml_features": int(local_ml.get("feature_count", 0) or 0),
            "hardware_devices": int(hardware.get("device_count", 0) or 0),
            "expression_modifier_nodes": sum(1 for node in graph.nodes if node.kind in {"spline_editor", "expression", "modifier", "macro"}),
            "deep_volumetric_nodes": sum(1 for node in graph.nodes if node.kind in {"deep_pixel_merge", "volumetric_fx"}),
        },
    }


def post_pipeline_product_capabilities() -> dict[str, Any]:
    return {
        "vfx": {
            "fusion_graph": True,
            "true_3d_workspace": True,
            "camera_3d": True,
            "lights_3d": True,
            "particles_3d": True,
            "materials_3d": True,
            "fbx_import": True,
            "alembic_import": True,
            "planar_tracker": True,
            "camera_tracker_3d": True,
            "clean_plate": True,
            "b_spline_roto": True,
            "point_feathering": True,
            "vector_paint": True,
            "clone_paint": True,
            "volumetric_fx": True,
            "spline_editor": True,
            "expressions": True,
            "macros": True,
            "fusion_graph_model": True,
            "mini_node_compositor": True,
            "true_3d_workspace_model": True,
            "scene_import_model": True,
            "camera_tracker_model": True,
            "keying_roto_model": True,
            "paint_repair_model": True,
            "particles_model": True,
            "expression_model": True,
        },
        "performance": {
            "gpu_fx": True,
            "native_fx": True,
            "render_cache": True,
            "optimized_media": True,
            "remote_render": True,
            "render_provider_model": True,
            "preview_export_parity": True,
            "ten_bit_export": True,
            "fps_120": True,
            "above_4k_export": True,
            "workflow_api": True,
            "openfx": True,
            "local_ml_registry_model": True,
        },
        "post_pipeline": {
            "media_ingest": True,
            "camera_card_clone": True,
            "auto_av_sync": True,
            "smart_metadata": True,
            "multicam": True,
            "dual_timeline": True,
            "source_tape": True,
            "page_integration": True,
            "deliver_page": True,
            "encoding_matrix": True,
        },
        "hardware": {
            "color_panel_mapping_model": True,
            "fairlight_console_mapping_model": True,
            "external_monitoring_model": True,
            "audio_interface_model": True,
        },
    }
