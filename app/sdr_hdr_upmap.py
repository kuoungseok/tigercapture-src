from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from app.subprocess_utils import hidden_subprocess_kwargs


@dataclass(frozen=True)
class SDRHDRUpmapProfile:
    """Settings for the local SDR -> HDR/EXR upmap foundation.

    This is not a neural LTX model. It creates a deterministic HDR-capable
    float EXR sequence and exposes provider hooks so a future LTX/ComfyUI
    worker can replace the local filter without changing callers.
    """

    mode: str = "local_inverse_tone_map"
    target: str = "scene_linear_exr"
    peak_nits: int = 1000
    exposure_stops: float = 0.0
    highlight_boost: float = 1.35
    saturation_boost: float = 1.08
    curve_gamma: float = 0.85
    fps: float = 0.0
    max_frames: int = 0
    output_pattern: str = "frame_%06d.exr"
    compression: str = "zip1"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "SDRHDRUpmapProfile":
        data = dict(data or {})
        return cls(
            mode=str(data.get("mode", "local_inverse_tone_map") or "local_inverse_tone_map"),
            target=str(data.get("target", "scene_linear_exr") or "scene_linear_exr"),
            peak_nits=max(100, int(data.get("peak_nits", 1000) or 1000)),
            exposure_stops=float(data.get("exposure_stops", 0.0) or 0.0),
            highlight_boost=max(0.25, min(8.0, float(data.get("highlight_boost", 1.35) or 1.35))),
            saturation_boost=max(0.0, min(3.0, float(data.get("saturation_boost", 1.08) or 1.08))),
            curve_gamma=max(0.2, min(3.0, float(data.get("curve_gamma", 0.85) or 0.85))),
            fps=max(0.0, float(data.get("fps", 0.0) or 0.0)),
            max_frames=max(0, int(data.get("max_frames", 0) or 0)),
            output_pattern=str(data.get("output_pattern", "frame_%06d.exr") or "frame_%06d.exr"),
            compression=str(data.get("compression", "zip1") or "zip1"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ltx_hdr_provider_state(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return whether an external LTX/ComfyUI HDR worker is configured.

    Supported integration points:
    - TIGERCAPTURE_LTX_HDR_ENDPOINT: HTTP endpoint for a local ComfyUI/LTX job.
    - TIGERCAPTURE_LTX_HDR_COMMAND: command-line worker for batch conversion.
    - TIGERCAPTURE_LTX_HDR_WORKFLOW: optional ComfyUI workflow JSON path.
    """

    env = env or os.environ
    endpoint = str(env.get("TIGERCAPTURE_LTX_HDR_ENDPOINT", "") or "").strip()
    command = str(env.get("TIGERCAPTURE_LTX_HDR_COMMAND", "") or "").strip()
    workflow = str(env.get("TIGERCAPTURE_LTX_HDR_WORKFLOW", "") or "").strip()
    configured = bool(endpoint or command)
    if endpoint:
        provider = "ltx_http_endpoint"
    elif command:
        provider = "ltx_command_worker"
    else:
        provider = "local_inverse_tone_map"
    warnings: list[str] = []
    if not configured:
        warnings.append("No LTX provider configured; using deterministic local EXR upmap.")
    if workflow and not Path(workflow).exists():
        warnings.append("TIGERCAPTURE_LTX_HDR_WORKFLOW is set but the file does not exist.")
    return {
        "configured": configured,
        "provider": provider,
        "endpoint": endpoint,
        "command": command,
        "workflow": workflow,
        "workflow_exists": bool(workflow and Path(workflow).exists()),
        "mode": "external_ltx" if configured else "local_inverse_tone_map",
        "warnings": warnings,
    }


def sdr_hdr_upmap_preset_gallery() -> dict[str, Any]:
    """Return UI-ready SDR->HDR presets for the node/property panel."""

    presets = [
        {
            "id": "soft_hdr_600",
            "label": "Soft HDR 600",
            "summary": "Gentle highlight lift for screen recordings and SDR tutorials.",
            "accent": "#6EA8FF",
            "profile": SDRHDRUpmapProfile(peak_nits=600, highlight_boost=1.18, saturation_boost=1.04, curve_gamma=0.92).to_dict(),
            "use_case": "screen_recording",
        },
        {
            "id": "social_hdr_1000",
            "label": "Social HDR 1000",
            "summary": "Brighter creator look for shorts, reels, and gameplay clips.",
            "accent": "#FF6F61",
            "profile": SDRHDRUpmapProfile(peak_nits=1000, highlight_boost=1.35, saturation_boost=1.10, curve_gamma=0.85).to_dict(),
            "use_case": "social_video",
        },
        {
            "id": "cinematic_probe_1500",
            "label": "Cinematic Probe 1500",
            "summary": "Stronger highlight expansion intended for probe-lit look development.",
            "accent": "#FFB84D",
            "profile": SDRHDRUpmapProfile(peak_nits=1500, exposure_stops=0.15, highlight_boost=1.65, saturation_boost=1.06, curve_gamma=0.78).to_dict(),
            "use_case": "lookdev",
        },
        {
            "id": "exr_linear_archive",
            "label": "EXR Linear Archive",
            "summary": "Conservative scene-linear EXR sequence for downstream grading/compositing.",
            "accent": "#5BE7C4",
            "profile": SDRHDRUpmapProfile(peak_nits=1000, highlight_boost=1.0, saturation_boost=1.0, curve_gamma=1.0, compression="zip1").to_dict(),
            "use_case": "archive",
        },
    ]
    return {
        "ok": True,
        "ready": True,
        "kind": "sdr_hdr_upmap_preset_gallery",
        "preset_count": len(presets),
        "presets": presets,
        "claim_level": "ltx_style_hdr_exr_foundation_not_neural_ltx_parity",
    }


def _match_sdr_hdr_preset(profile: SDRHDRUpmapProfile) -> str:
    best_id = ""
    best_score = float("inf")
    for preset in sdr_hdr_upmap_preset_gallery()["presets"]:
        candidate = SDRHDRUpmapProfile.from_dict(_as_profile_dict(preset.get("profile")))
        score = (
            abs(candidate.peak_nits - profile.peak_nits) / 1000.0
            + abs(candidate.highlight_boost - profile.highlight_boost)
            + abs(candidate.saturation_boost - profile.saturation_boost)
            + abs(candidate.curve_gamma - profile.curve_gamma)
        )
        if score < best_score:
            best_score = score
            best_id = str(preset.get("id") or "")
    return best_id


def _as_profile_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def sdr_hdr_upmap_review_model(profile_or_report: SDRHDRUpmapProfile | Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a compact, product-facing review model for SDR->HDR jobs."""

    data = dict(profile_or_report or {}) if isinstance(profile_or_report, Mapping) else {}
    profile_data = _as_profile_dict(data.get("profile")) if "profile" in data else data
    profile = profile_or_report if isinstance(profile_or_report, SDRHDRUpmapProfile) else SDRHDRUpmapProfile.from_dict(profile_data)
    provider = _as_profile_dict(data.get("provider")) or ltx_hdr_provider_state()
    warnings = list(data.get("warnings") or [])
    if provider.get("warnings"):
        warnings.extend(str(item) for item in provider.get("warnings") or [])
    preset_id = _match_sdr_hdr_preset(profile)
    controls = [
        {"id": "peak_nits", "label": "Peak nits", "value": profile.peak_nits, "min": 100, "max": 4000, "step": 50},
        {"id": "exposure_stops", "label": "Exposure", "value": profile.exposure_stops, "min": -3.0, "max": 3.0, "step": 0.05},
        {"id": "highlight_boost", "label": "Highlights", "value": profile.highlight_boost, "min": 0.25, "max": 8.0, "step": 0.05},
        {"id": "saturation_boost", "label": "Saturation", "value": profile.saturation_boost, "min": 0.0, "max": 3.0, "step": 0.02},
        {"id": "curve_gamma", "label": "Curve", "value": profile.curve_gamma, "min": 0.2, "max": 3.0, "step": 0.02},
    ]
    cards = [
        {
            "id": "preset",
            "label": "Preset",
            "ready": True,
            "summary": preset_id or "custom",
            "accent": "#8A7CFF",
        },
        {
            "id": "provider",
            "label": "Engine",
            "ready": True,
            "summary": "External LTX provider" if provider.get("configured") else "Local deterministic EXR upmap",
            "accent": "#5BE7C4" if provider.get("configured") else "#FFB84D",
        },
        {
            "id": "output",
            "label": "Output",
            "ready": True,
            "summary": f"{profile.target}, {profile.peak_nits} nits, {profile.output_pattern}",
            "accent": "#6EA8FF",
        },
    ]
    actions = [
        {"id": "dry_run_sdr_hdr", "label": "Preview command", "enabled": True},
        {"id": "create_exr_frames", "label": "Create EXR frames", "enabled": True},
        {"id": "open_provider_setup", "label": "Connect LTX provider", "enabled": not bool(provider.get("configured"))},
    ]
    return {
        "ok": True,
        "ready": True,
        "kind": "sdr_hdr_upmap_review_model",
        "preset_id": preset_id,
        "profile": profile.to_dict(),
        "provider": provider,
        "controls": controls,
        "cards": cards,
        "actions": actions,
        "warnings": list(dict.fromkeys(str(item) for item in warnings if str(item).strip())),
        "claim_level": "ltx_style_hdr_exr_foundation_not_neural_ltx_parity",
    }


def _ffmpeg_exe() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return str(get_ffmpeg_exe())
    except Exception:
        return "ffmpeg"


def build_sdr_to_hdr_exr_filter(profile: SDRHDRUpmapProfile | Mapping[str, Any] | None = None) -> str:
    """Build the FFmpeg filter used by the local fallback path.

    The filter lifts SDR into a high-bit-depth RGB path, expands highlights,
    then writes float EXR values. It is intentionally deterministic and modest:
    it gives the editor an HDR-capable intermediate with a scene-linear target
    contract while an actual LTX model remains an optional provider.
    """

    p = profile if isinstance(profile, SDRHDRUpmapProfile) else SDRHDRUpmapProfile.from_dict(profile)
    gain = (2.0 ** float(p.exposure_stops)) * float(p.highlight_boost)
    gamma = float(p.curve_gamma)
    sat = float(p.saturation_boost)
    # FFmpeg filtergraph commas inside expressions must be escaped.
    curve = (
        "lutrgb="
        f"r='pow(val/maxval\\,{gamma:.6f})*maxval*{gain:.6f}':"
        f"g='pow(val/maxval\\,{gamma:.6f})*maxval*{gain:.6f}':"
        f"b='pow(val/maxval\\,{gamma:.6f})*maxval*{gain:.6f}'"
    )
    return (
        f"eq=saturation={sat:.6f},"
        "format=rgb48le,"
        f"{curve},"
        "format=gbrpf32le"
    )


def build_sdr_to_hdr_exr_command(
    input_path: str | Path,
    output_dir: str | Path,
    profile: SDRHDRUpmapProfile | Mapping[str, Any] | None = None,
    *,
    ffmpeg: str | None = None,
) -> list[str]:
    p = profile if isinstance(profile, SDRHDRUpmapProfile) else SDRHDRUpmapProfile.from_dict(profile)
    out_dir = Path(output_dir)
    pattern = out_dir / p.output_pattern
    cmd = [
        ffmpeg or _ffmpeg_exe(),
        "-y",
        "-hide_banner",
        "-i",
        str(input_path),
        "-an",
        "-vf",
        build_sdr_to_hdr_exr_filter(p),
    ]
    if p.fps > 0.0:
        cmd.extend(["-r", f"{p.fps:g}"])
    if p.max_frames > 0:
        cmd.extend(["-frames:v", str(p.max_frames)])
    cmd.extend([
        "-c:v",
        "exr",
        "-pix_fmt",
        "gbrpf32le",
        "-compression",
        p.compression,
        str(pattern),
    ])
    return cmd


def sdr_to_hdr_upmap_report(
    input_path: str | Path,
    output_dir: str | Path,
    profile: SDRHDRUpmapProfile | Mapping[str, Any] | None = None,
    *,
    run: bool = False,
    timeout_s: int = 300,
) -> dict[str, Any]:
    """Create or dry-run an SDR -> HDR/EXR conversion report."""

    p = profile if isinstance(profile, SDRHDRUpmapProfile) else SDRHDRUpmapProfile.from_dict(profile)
    input_p = Path(input_path)
    out_dir = Path(output_dir)
    provider = ltx_hdr_provider_state()
    command = build_sdr_to_hdr_exr_command(input_p, out_dir, p)
    warnings = list(provider.get("warnings") or [])
    if not input_p.exists():
        warnings.append("Input file does not exist; dry-run command is still valid.")
    report: dict[str, Any] = {
        "ok": True,
        "run": bool(run),
        "engine": "external_ltx_provider" if provider.get("configured") else "local_inverse_tone_map",
        "claim_level": "ltx_style_hdr_exr_foundation_not_neural_ltx_parity",
        "real_ltx_model": bool(provider.get("configured")),
        "profile": p.to_dict(),
        "provider": provider,
        "input": str(input_p),
        "output_dir": str(out_dir),
        "output_pattern": str(out_dir / p.output_pattern),
        "ffmpeg_filter": build_sdr_to_hdr_exr_filter(p),
        "command": command,
        "preset_gallery": sdr_hdr_upmap_preset_gallery(),
        "review_model": sdr_hdr_upmap_review_model({"profile": p.to_dict(), "provider": provider, "warnings": warnings}),
        "warnings": warnings,
        "generated_frames": 0,
        "stderr_tail": "",
    }
    if not run:
        report["dry_run"] = True
        return report
    if not input_p.exists():
        report["ok"] = False
        report["dry_run"] = False
        return report
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        cp = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            **hidden_subprocess_kwargs(),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        report["ok"] = False
        report["dry_run"] = False
        report["error"] = str(exc)
        return report
    report["dry_run"] = False
    report["returncode"] = int(cp.returncode)
    report["ok"] = cp.returncode == 0
    report["stderr_tail"] = "\n".join((cp.stderr or "").splitlines()[-20:])
    report["generated_frames"] = len(list(out_dir.glob("*.exr")))
    return report


def write_sdr_to_hdr_upmap_report(path: str | Path, report: Mapping[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(report), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
