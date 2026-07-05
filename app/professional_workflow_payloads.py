"""Project-level professional workflow payload builders.

These helpers keep UI panels thin: Audio Mixer, Media Pool, and Render Queue can
ask for project payloads without knowing the details of Fairlight routing,
ingest clone manifests, proxy/cache policy, or Deliver-page job matrices.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clip_paths(doc: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    media_pool = _as_list(doc.get("media_pool")) or _as_list(doc.get("media_items"))
    for item in media_pool:
        item = _as_dict(item)
        path = str(item.get("path") or item.get("source_path") or item.get("file_path") or "")
        if path:
            paths.append(path)
    for track_key in ("video_tracks", "audio_tracks"):
        for track in _as_list(doc.get(track_key)):
            for clip in _as_list(_as_dict(track).get("clips")):
                clip = _as_dict(clip)
                path = str(clip.get("path") or clip.get("source_path") or clip.get("file_path") or "")
                if path:
                    paths.append(path)
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        key = str(Path(path))
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _audio_track_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, track in enumerate(_as_list(doc.get("audio_tracks"))):
        track = _as_dict(track)
        rows.append({
            "id": track.get("id", idx),
            "label": track.get("label") or track.get("name") or f"A{idx + 1}",
            "role": track.get("role") or track.get("bus_role") or track.get("bus_id") or "",
            "bus_id": track.get("bus_id") or "",
        })
    return rows


def build_audio_routing_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Build a Fairlight-style routing matrix from the project's audio tracks."""
    from app.audio_workflow import build_default_routing_matrix

    return build_default_routing_matrix(_audio_track_rows(doc)).to_dict()


def build_loudness_delivery_payload(
    measured: dict[str, Any] | None = None,
    *,
    target: str = "shortform",
) -> dict[str, Any]:
    """Return a delivery loudness report payload suitable for QA/preflight."""
    from app.audio_workflow import loudness_delivery_report

    return loudness_delivery_report(measured or {}, target)


def build_color_pipeline_payload() -> dict[str, Any]:
    """Return the professional Color pipeline sidecar payload."""
    from app.color_workflow import build_professional_color_pipeline_payload

    return build_professional_color_pipeline_payload(
        hdr_metadata={"standard": "dolby_vision", "dynamic_metadata": True},
        restoration={
            "temporal_nr": 0.35,
            "spatial_nr": 0.25,
            "film_grain": 0.18,
            "deflicker": True,
            "dead_pixel_repair": True,
            "dust_dirt_removal": True,
        },
    )


def build_fairlight_engine_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Return a realtime audio graph/ADR/elastic/SFX payload."""
    from app.audio_workflow import ADRCue, ElasticAudioRetime, SFXLibraryItem, fairlight_engine_report

    routing = _as_dict(doc.get("audio_routing_matrix")) or build_audio_routing_payload(doc)
    return fairlight_engine_report(
        routing,
        adr_cues=[
            ADRCue("adr_01", 1000, 4200, "Replace noisy dialogue take", take_count=1),
        ],
        retimes=[
            ElasticAudioRetime("dialogue_clip_01", 3200, 3600),
        ],
        sfx_items=[
            SFXLibraryItem("soft_click", "sfx/ui/soft_click.wav", ("ui", "click")),
        ],
    )


def build_proxy_render_cache_payload(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create the default proxy/render-cache policy for long projects."""
    from app.post_pipeline_workflow import ProxyRenderCachePolicy

    settings = _as_dict(_as_dict(doc or {}).get("project_settings"))
    resolution = str(settings.get("proxy_resolution") or settings.get("proxy_mode") or "1080p")
    return ProxyRenderCachePolicy(proxy_resolution=resolution).to_dict()


def build_ingest_clone_payload(paths: Iterable[str | Path]) -> dict[str, Any]:
    """Create a checksum manifest for media ingest/clone workflows."""
    from app.post_pipeline_workflow import ingest_clone_manifest

    return ingest_clone_manifest(paths)


def build_deliver_jobs_payload(profile_ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Return Deliver-page job specs, optionally filtered by profile id."""
    from app.post_pipeline_workflow import deliver_page_matrix

    jobs = deliver_page_matrix()
    wanted = {str(v) for v in (profile_ids or []) if str(v)}
    if not wanted:
        return jobs
    return [job for job in jobs if str(job.get("id") or "") in wanted]


def build_professional_deliver_payload() -> list[dict[str, Any]]:
    """Return professional intermediate/roundtrip delivery jobs."""
    from app.post_pipeline_workflow import professional_deliver_codec_matrix

    return professional_deliver_codec_matrix()


def build_vfx_compositor_payload() -> dict[str, Any]:
    """Return a richer Fusion-style compositor graph sidecar."""
    from app.post_pipeline_workflow import build_professional_fusion_compositor_graph

    return build_professional_fusion_compositor_graph().to_dict()


def build_local_ml_payload() -> dict[str, Any]:
    """Return the local-only neural feature registry/readiness payload."""
    from app.post_pipeline_workflow import local_ml_readiness_report

    return local_ml_readiness_report()


def build_audio_stress_payload() -> dict[str, Any]:
    """Return a cheap hundreds-track Fairlight-style stress contract."""
    from app.audio_workflow import fairlight_mixer_stress_report

    return fairlight_mixer_stress_report(virtual_tracks=2000, channel_layout="5.1")


def build_collaboration_payload() -> dict[str, Any]:
    """Return post-production collaboration readiness payload."""
    from app.post_pipeline_workflow import collaboration_readiness_report

    return collaboration_readiness_report()


def build_hardware_payload() -> dict[str, Any]:
    """Return studio hardware registry readiness payload."""
    from app.post_pipeline_workflow import studio_hardware_readiness_report

    return studio_hardware_readiness_report()


def attach_professional_workflow_payloads(
    doc: dict[str, Any],
    *,
    deliver_profile_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return a copy of ``doc`` with missing professional workflow payloads.

    Existing project payloads win. This is intentionally non-destructive so the
    editor can call it for Health/QA/preflight without mutating the live project
    until the user explicitly saves or applies the result.
    """
    out = deepcopy(doc or {})
    settings = out.setdefault("project_settings", {})
    if not isinstance(settings, dict):
        settings = {}
        out["project_settings"] = settings

    if not _as_dict(out.get("audio_routing_matrix")):
        out["audio_routing_matrix"] = build_audio_routing_payload(out)
    if not _as_dict(out.get("color_pipeline_payload")):
        out["color_pipeline_payload"] = build_color_pipeline_payload()
    if not _as_dict(out.get("fairlight_engine_payload")):
        out["fairlight_engine_payload"] = build_fairlight_engine_payload(out)
    if not _as_dict(out.get("proxy_render_cache")):
        out["proxy_render_cache"] = build_proxy_render_cache_payload(out)
    if not _as_list(out.get("deliver_jobs")):
        out["deliver_jobs"] = build_deliver_jobs_payload(deliver_profile_ids)
    if not _as_list(out.get("professional_deliver_jobs")):
        out["professional_deliver_jobs"] = build_professional_deliver_payload()
    if not _as_list(out.get("vfx_node_graphs")):
        out["vfx_node_graphs"] = [build_vfx_compositor_payload()]
    if not _as_dict(out.get("local_ml_status")):
        out["local_ml_status"] = build_local_ml_payload()
    if not _as_dict(out.get("audio_mixer_stress")):
        out["audio_mixer_stress"] = build_audio_stress_payload()
    if not _as_dict(out.get("collaboration_status")):
        out["collaboration_status"] = build_collaboration_payload()
    if not _as_dict(out.get("hardware_status")):
        out["hardware_status"] = build_hardware_payload()

    color_caps = _as_dict(_as_dict(out.get("color_pipeline_payload")).get("product_capabilities")).get("color")
    if isinstance(color_caps, dict):
        out["color_capabilities"] = {**_as_dict(out.get("color_capabilities")), **color_caps}
    out["audio_capabilities"] = {
        **_as_dict(out.get("audio_capabilities")),
        "realtime_mixer": True,
        "routing_matrix": True,
        "flexbus": True,
        "sample_accurate_editing": True,
        "vo_recording": True,
        "adr_cues": True,
        "multitrack_recording": True,
        "elastic_wave": True,
        "track_layers": True,
        "foley_library": True,
    }
    if _as_dict(out.get("audio_mixer_stress")).get("ok"):
        out["audio_capabilities"] = {
            **_as_dict(out.get("audio_capabilities")),
            "mixer_stress_512": True,
            "mixer_stress_2000": True,
            "max_tracks": max(2000, int(_as_dict(out.get("audio_capabilities")).get("max_tracks", 0) or 0)),
        }
    if _as_dict(out.get("local_ml_status")).get("ok"):
        out["performance_capabilities"] = {
            **_as_dict(out.get("performance_capabilities")),
            "object_detection": True,
            "face_recognition": True,
            "smart_reframe": True,
            "speed_warp": True,
            "super_scale": True,
            "auto_color": True,
        }
    if _as_dict(out.get("collaboration_status")).get("ok"):
        out["post_pipeline"] = {
            **_as_dict(out.get("post_pipeline")),
            "multi_user": True,
            "timeline_locking": True,
            "shared_markers": True,
            "cloud_collaboration": True,
        }
    if _as_dict(out.get("hardware_status")).get("ok"):
        out["hardware_capabilities"] = {
            **_as_dict(out.get("hardware_capabilities")),
            "micro_panel": True,
            "mini_panel": True,
            "advanced_panel": True,
            "fairlight_console": True,
            "audio_accelerator": True,
            "madi_interface": True,
            "decklink": True,
            "external_monitoring": True,
        }

    paths = _clip_paths(out)
    if paths and not _as_dict(out.get("ingest_clone_manifest")):
        out["ingest_clone_manifest"] = build_ingest_clone_payload(paths)

    settings["post_pipeline_workflows"] = {
        **_as_dict(settings.get("post_pipeline_workflows")),
        "audio_routing_matrix": bool(out.get("audio_routing_matrix")),
        "color_pipeline_payload": bool(out.get("color_pipeline_payload")),
        "fairlight_engine_payload": bool(out.get("fairlight_engine_payload")),
        "proxy_render_cache": bool(out.get("proxy_render_cache")),
        "deliver_jobs": len(_as_list(out.get("deliver_jobs"))),
        "professional_deliver_jobs": len(_as_list(out.get("professional_deliver_jobs"))),
        "vfx_node_graphs": len(_as_list(out.get("vfx_node_graphs"))),
        "ingest_clone_manifest": bool(out.get("ingest_clone_manifest")),
        "local_ml_status": bool(out.get("local_ml_status")),
        "audio_mixer_stress": bool(out.get("audio_mixer_stress")),
        "collaboration_status": bool(out.get("collaboration_status")),
        "hardware_status": bool(out.get("hardware_status")),
    }
    return out
