"""Project color-management core.

The UI can stay lightweight, but preview/export need one authoritative model
for input, working, display, LUT, and output color decisions.  This module is
Qt-free so project I/O, QA scripts, render queue diagnostics, and tests can all
validate the same pipeline.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.subprocess_utils import hidden_subprocess_kwargs


COLOR_SPACE_ALIASES = {
    "rec.709": "rec709",
    "bt.709": "rec709",
    "bt709": "rec709",
    "709": "rec709",
    "srgb": "srgb",
    "s-rgb": "srgb",
    "rec.2020": "rec2020",
    "bt.2020": "rec2020",
    "bt2020": "rec2020",
    "rec2020": "rec2020",
    "p3": "p3-d65",
    "p3d65": "p3-d65",
    "p3-d65": "p3-d65",
    "display-p3": "p3-d65",
    "aces": "acescg",
    "acescg": "acescg",
    "aces-cg": "acescg",
    "acescct": "acescct",
    "aces-cct": "acescct",
}

TRANSFER_ALIASES = {
    "bt709": "bt709",
    "rec709": "bt709",
    "rec.709": "bt709",
    "srgb": "srgb",
    "s-rgb": "srgb",
    "pq": "pq",
    "smpte2084": "pq",
    "st2084": "pq",
    "hlg": "hlg",
    "arib-std-b67": "hlg",
    "linear": "linear",
    "acescct": "acescct",
    "aces-cct": "acescct",
}

SUPPORTED_COLOR_SPACES = frozenset(COLOR_SPACE_ALIASES.values())
SUPPORTED_TRANSFERS = frozenset(TRANSFER_ALIASES.values())
SUPPORTED_VIEW_TRANSFORMS = frozenset(
    {"none", "rec709", "srgb", "aces-1.3", "hdr-pq", "hdr-hlg"}
)

_FFMPEG_COLOR_MAP = {
    ("rec709", "bt709"): {
        "colorspace": "bt709",
        "color_primaries": "bt709",
        "color_trc": "bt709",
        "pix_fmt": "yuv420p",
    },
    ("srgb", "srgb"): {
        "colorspace": "bt709",
        "color_primaries": "bt709",
        "color_trc": "iec61966-2-1",
        "pix_fmt": "yuv420p",
    },
    ("rec2020", "pq"): {
        "colorspace": "bt2020nc",
        "color_primaries": "bt2020",
        "color_trc": "smpte2084",
        "pix_fmt": "yuv420p10le",
    },
    ("rec2020", "hlg"): {
        "colorspace": "bt2020nc",
        "color_primaries": "bt2020",
        "color_trc": "arib-std-b67",
        "pix_fmt": "yuv420p10le",
    },
    ("p3-d65", "bt709"): {
        "colorspace": "bt709",
        "color_primaries": "smpte432",
        "color_trc": "bt709",
        "pix_fmt": "yuv420p",
    },
}


def _norm_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "-").replace(" ", "")


def normalize_color_space(value: Any, default: str = "rec709") -> str:
    key = _norm_key(value)
    if not key:
        return default
    return COLOR_SPACE_ALIASES.get(key, default)


def normalize_transfer(value: Any, default: str = "bt709") -> str:
    key = _norm_key(value)
    if not key:
        return default
    return TRANSFER_ALIASES.get(key, default)


def normalize_view_transform(value: Any, default: str = "rec709") -> str:
    key = _norm_key(value)
    if key in {"aces", "aces13", "aces1.3"}:
        return "aces-1.3"
    if key in {"hdrpq", "pq"}:
        return "hdr-pq"
    if key in {"hdrhlg", "hlg"}:
        return "hdr-hlg"
    if key in SUPPORTED_VIEW_TRANSFORMS:
        return key
    return default


def _clamp01(value: Any, default: float = 1.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default


@dataclass(frozen=True)
class LutSlot:
    """One project-level LUT slot with a blend strength."""

    path: str = ""
    strength: float = 1.0
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LutSlot":
        if not isinstance(data, dict):
            return cls()
        return cls(
            path=str(data.get("path", "") or ""),
            strength=_clamp01(data.get("strength", 1.0), 1.0),
            enabled=bool(data.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "strength": float(self.strength),
            "enabled": bool(self.enabled),
        }

    def is_active(self) -> bool:
        return bool(self.enabled and self.path and self.strength > 0.0)


@dataclass(frozen=True)
class ColorManagementSettings:
    """Project color pipeline settings.

    `working_space` may be ACEScg/ACEScct even when display/output is Rec.709.
    OCIO is optional; when absent, the app still validates/persists the intent
    and emits stable FFmpeg metadata for the final encode.
    """

    input_space: str = "rec709"
    input_transfer: str = "bt709"
    working_space: str = "rec709"
    output_space: str = "rec709"
    output_transfer: str = "bt709"
    view_transform: str = "rec709"
    hdr_mode: bool = False
    ocio_config_path: str = ""
    input_lut: LutSlot = LutSlot()
    creative_lut: LutSlot = LutSlot()
    output_lut: LutSlot = LutSlot()
    preview_transform_enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ColorManagementSettings":
        if not isinstance(data, dict):
            return cls()
        output_transfer = normalize_transfer(
            data.get("output_transfer", data.get("transfer", "bt709")),
            "bt709",
        )
        output_space = normalize_color_space(data.get("output_space", "rec709"), "rec709")
        hdr_mode = bool(data.get("hdr_mode", False)) or output_transfer in {"pq", "hlg"}
        return cls(
            input_space=normalize_color_space(data.get("input_space", "rec709"), "rec709"),
            input_transfer=normalize_transfer(data.get("input_transfer", data.get("transfer", "bt709")), "bt709"),
            working_space=normalize_color_space(data.get("working_space", "rec709"), "rec709"),
            output_space=output_space,
            output_transfer=output_transfer,
            view_transform=normalize_view_transform(data.get("view_transform", "rec709"), "rec709"),
            hdr_mode=hdr_mode,
            ocio_config_path=str(data.get("ocio_config_path", "") or ""),
            input_lut=LutSlot.from_dict(data.get("input_lut")),
            creative_lut=LutSlot.from_dict(data.get("creative_lut")),
            output_lut=LutSlot.from_dict(data.get("output_lut")),
            preview_transform_enabled=bool(data.get("preview_transform_enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_space": self.input_space,
            "input_transfer": self.input_transfer,
            "working_space": self.working_space,
            "output_space": self.output_space,
            "output_transfer": self.output_transfer,
            "view_transform": self.view_transform,
            "hdr_mode": bool(self.hdr_mode),
            "ocio_config_path": self.ocio_config_path,
            "input_lut": self.input_lut.to_dict(),
            "creative_lut": self.creative_lut.to_dict(),
            "output_lut": self.output_lut.to_dict(),
            "preview_transform_enabled": bool(self.preview_transform_enabled),
        }

    def is_hdr(self) -> bool:
        return bool(
            self.hdr_mode
            or self.output_space == "rec2020"
            or self.output_transfer in {"pq", "hlg"}
        )

    def active_luts(self) -> list[tuple[str, LutSlot]]:
        slots = [
            ("input", self.input_lut),
            ("creative", self.creative_lut),
            ("output", self.output_lut),
        ]
        return [(name, slot) for name, slot in slots if slot.is_active()]


def default_color_management() -> ColorManagementSettings:
    return ColorManagementSettings()


def export_color_metadata(settings: ColorManagementSettings | dict[str, Any] | None) -> dict[str, str]:
    s = ColorManagementSettings.from_dict(settings) if isinstance(settings, dict) or settings is None else settings
    metadata = _FFMPEG_COLOR_MAP.get((s.output_space, s.output_transfer))
    if metadata is None:
        if s.output_space == "rec2020":
            metadata = _FFMPEG_COLOR_MAP[("rec2020", "pq" if s.is_hdr() else "hlg")]
        elif s.output_space == "srgb":
            metadata = _FFMPEG_COLOR_MAP[("srgb", "srgb")]
        elif s.output_space == "p3-d65":
            metadata = _FFMPEG_COLOR_MAP[("p3-d65", "bt709")]
        else:
            metadata = _FFMPEG_COLOR_MAP[("rec709", "bt709")]
    return dict(metadata)


def ffmpeg_color_args(settings: ColorManagementSettings | dict[str, Any] | None) -> list[str]:
    metadata = export_color_metadata(settings)
    return [
        "-colorspace", metadata["colorspace"],
        "-color_primaries", metadata["color_primaries"],
        "-color_trc", metadata["color_trc"],
        "-pix_fmt", metadata["pix_fmt"],
    ]


def ffmpeg_filter_path(path: str) -> str:
    """Escape a filesystem path for use inside an FFmpeg filter option."""
    p = str(path or "").replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        p = p[0] + "\\:" + p[2:]
    return p.replace("'", "\\'")


def append_lut_filter_graph(
    graph: str,
    input_label: str,
    settings: ColorManagementSettings | dict[str, Any] | None,
    *,
    output_prefix: str = "outv_lut",
) -> tuple[str, str]:
    """Append project LUT slots to a filter graph.

    Returns `(graph, output_label)`.  Strength below 1.0 is implemented with a
    split + blend branch so preview/export can share the same intensity concept.
    """
    s = ColorManagementSettings.from_dict(settings) if isinstance(settings, dict) or settings is None else settings
    active = s.active_luts()
    if not active:
        return graph, input_label
    parts = [graph] if graph else []
    current = input_label
    for idx, (name, slot) in enumerate(active):
        out_label = f"{output_prefix}{idx}"
        lut_path = ffmpeg_filter_path(slot.path)
        strength = max(0.0, min(1.0, float(slot.strength)))
        if strength >= 0.999:
            parts.append(
                f"[{current}]lut3d=file='{lut_path}':interp=tetrahedral[{out_label}]"
            )
        else:
            src_label = f"{output_prefix}{idx}_src"
            lut_in_label = f"{output_prefix}{idx}_in"
            lut_label = f"{output_prefix}{idx}_applied"
            parts.append(
                f"[{current}]split=2[{src_label}][{lut_in_label}];"
                f"[{lut_in_label}]lut3d=file='{lut_path}':interp=tetrahedral[{lut_label}];"
                f"[{src_label}][{lut_label}]blend=all_mode=normal:all_opacity={strength:.4f}[{out_label}]"
            )
        current = out_label
    return ";".join(parts), current


def validate_color_management(
    settings: ColorManagementSettings | dict[str, Any] | None,
    *,
    require_existing_luts: bool = False,
) -> dict[str, Any]:
    s = ColorManagementSettings.from_dict(settings) if isinstance(settings, dict) or settings is None else settings
    warnings: list[str] = []
    errors: list[str] = []

    if s.input_space not in SUPPORTED_COLOR_SPACES:
        errors.append(f"Unsupported input color space: {s.input_space}")
    if s.working_space not in SUPPORTED_COLOR_SPACES:
        errors.append(f"Unsupported working color space: {s.working_space}")
    if s.output_space not in SUPPORTED_COLOR_SPACES:
        errors.append(f"Unsupported output color space: {s.output_space}")
    if s.input_transfer not in SUPPORTED_TRANSFERS:
        errors.append(f"Unsupported input transfer: {s.input_transfer}")
    if s.output_transfer not in SUPPORTED_TRANSFERS:
        errors.append(f"Unsupported output transfer: {s.output_transfer}")
    if s.view_transform not in SUPPORTED_VIEW_TRANSFORMS:
        errors.append(f"Unsupported view transform: {s.view_transform}")

    if s.is_hdr() and s.output_space != "rec2020":
        warnings.append("HDR output should normally use Rec.2020 primaries.")
    if not s.is_hdr() and s.output_transfer in {"pq", "hlg"}:
        warnings.append("PQ/HLG transfer implies HDR output.")
    if s.working_space in {"acescg", "acescct"} and not s.ocio_config_path:
        warnings.append("ACES working space is selected without an OCIO config path.")
    if s.ocio_config_path:
        try:
            from app.color_ocio import build_ocio_plan, ocio_config_exists

            if not ocio_config_exists(s.ocio_config_path):
                warnings.append("OCIO config is unavailable.")
            else:
                ocio_plan = build_ocio_plan(s)
                if not ocio_plan.enabled:
                    warnings.extend(
                        f"OCIO runtime: {warning}"
                        for warning in ocio_plan.warnings
                    )
        except Exception as exc:
            warnings.append(f"OCIO runtime validation failed: {exc}")

    for name, slot in s.active_luts():
        if not slot.path.lower().endswith((".cube", ".3dl")):
            warnings.append(f"{name} LUT does not look like a .cube/.3dl file.")
        if require_existing_luts and not Path(slot.path).is_file():
            errors.append(f"{name} LUT file is missing: {slot.path}")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "metadata": export_color_metadata(s),
        "active_luts": [name for name, _slot in s.active_luts()],
        "summary": color_pipeline_summary(s),
    }


def color_pipeline_summary(settings: ColorManagementSettings | dict[str, Any] | None) -> list[str]:
    s = ColorManagementSettings.from_dict(settings) if isinstance(settings, dict) or settings is None else settings
    steps = [
        f"Input: {s.input_space}/{s.input_transfer}",
        f"Working: {s.working_space}",
    ]
    if s.input_lut.is_active():
        steps.append(f"Input LUT: {Path(s.input_lut.path).name} @ {s.input_lut.strength:.2f}")
    if s.creative_lut.is_active():
        steps.append(f"Creative LUT: {Path(s.creative_lut.path).name} @ {s.creative_lut.strength:.2f}")
    steps.append(f"View: {s.view_transform}" if s.preview_transform_enabled else "View: bypass")
    if s.output_lut.is_active():
        steps.append(f"Output LUT: {Path(s.output_lut.path).name} @ {s.output_lut.strength:.2f}")
    steps.append(f"Output: {s.output_space}/{s.output_transfer}")
    return steps


def validate_export_color_consistency(
    project_settings: dict[str, Any] | None,
    export_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate that project and export color intent agree.

    `project_settings` is the editor's existing `_project_settings` payload.  A
    future UI can pass `export_settings["color_management"]` to override output
    per render preset, but mismatches are surfaced instead of silently changing
    the render.
    """

    project_settings = project_settings or {}
    export_settings = export_settings or {}
    project_cm = ColorManagementSettings.from_dict(project_settings.get("color_management"))
    export_cm = ColorManagementSettings.from_dict(
        export_settings.get("color_management", project_cm.to_dict())
    )
    report = validate_color_management(export_cm)
    warnings = list(report["warnings"])
    if project_cm.output_space != export_cm.output_space:
        warnings.append(
            f"Export output space {export_cm.output_space} differs from project {project_cm.output_space}."
        )
    if project_cm.output_transfer != export_cm.output_transfer:
        warnings.append(
            f"Export output transfer {export_cm.output_transfer} differs from project {project_cm.output_transfer}."
        )
    metadata = export_color_metadata(export_cm)
    return {
        "ok": bool(report["ok"]),
        "errors": report["errors"],
        "warnings": warnings,
        "metadata": metadata,
        "ffmpeg_args": ffmpeg_color_args(export_cm),
        "summary": color_pipeline_summary(export_cm),
    }


def compare_ffprobe_color_metadata(
    project_settings: dict[str, Any] | None,
    ffprobe_stream: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare expected project color metadata with an ffprobe video stream.

    Use this after export in render-queue diagnostics.  It accepts one parsed
    `ffprobe -show_streams -print_format json` video stream dict, so callers can
    unit-test it without invoking FFmpeg.
    """
    expected = validate_export_color_consistency(project_settings).get("metadata", {})
    stream = ffprobe_stream or {}
    actual = {
        "colorspace": str(stream.get("color_space", stream.get("colorspace", "")) or ""),
        "color_primaries": str(stream.get("color_primaries", "") or ""),
        "color_trc": str(stream.get("color_transfer", stream.get("color_trc", "")) or ""),
    }
    mismatches: list[str] = []
    for key in ("colorspace", "color_primaries", "color_trc"):
        exp = str(expected.get(key, "") or "")
        got = str(actual.get(key, "") or "")
        if exp and got and exp != got:
            mismatches.append(f"{key}: expected {exp}, got {got}")
        elif exp and not got:
            mismatches.append(f"{key}: expected {exp}, got missing")
    return {
        "ok": not mismatches,
        "expected": expected,
        "actual": actual,
        "mismatches": mismatches,
    }


_FFMPEG_VIDEO_LINE_RX = re.compile(r"Video:\s*[^,]+,\s*(?P<pix_fmt>[\w\d_]+)")
_FFMPEG_COLOR_TRIPLE_RX = re.compile(
    r"\(\s*"
    r"(?:tv|pc)?\s*,?\s*"
    r"(?P<matrix>[\w\-]+)"
    r"(?:/(?P<primaries>[\w\-]+)/(?P<transfer>[\w\-]+))?"
    r"(?:\s*,\s*\w+)?"
    r"\s*\)",
)


def parse_ffmpeg_color_stream_text(text: str) -> dict[str, Any]:
    """Parse ffmpeg stderr into an ffprobe-like first video stream dict."""
    line = ""
    for raw in str(text or "").splitlines():
        stripped = raw.strip()
        if "Stream " in stripped and "Video:" in stripped:
            line = stripped
            break
    if not line:
        return {}
    pix_fmt = ""
    m_pix = _FFMPEG_VIDEO_LINE_RX.search(line)
    if m_pix:
        pix_fmt = m_pix.group("pix_fmt") or ""
    matrix = primaries = transfer = ""
    fallback_matrix = ""
    for m in _FFMPEG_COLOR_TRIPLE_RX.finditer(line):
        token = m.group("matrix") or ""
        if m.group("transfer") is None:
            if token and token not in {"tv", "pc", "progressive"} and not fallback_matrix:
                fallback_matrix = token
            continue
        matrix = token
        primaries = m.group("primaries") or ""
        transfer = m.group("transfer") or ""
        break
    if not matrix and fallback_matrix:
        matrix = fallback_matrix
        if fallback_matrix == "bt709":
            primaries = "bt709"
            transfer = "bt709"
        elif fallback_matrix == "bt2020nc":
            primaries = "bt2020"
    return {
        "pix_fmt": pix_fmt,
        "color_space": matrix,
        "color_primaries": primaries,
        "color_transfer": transfer,
        "raw_line": line,
    }


def _ffprobe_candidates() -> list[str]:
    candidates: list[str] = []
    found = shutil.which("ffprobe")
    if found:
        candidates.append(found)
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        ffmpeg = Path(get_ffmpeg_exe())
        for name in ("ffprobe.exe", "ffprobe"):
            sibling = ffmpeg.with_name(name)
            if sibling.exists():
                candidates.append(str(sibling))
    except Exception:
        pass
    unique: list[str] = []
    for item in candidates:
        if item and item not in unique:
            unique.append(item)
    return unique


def _probe_color_with_ffprobe(path: Path, timeout_s: float) -> tuple[dict[str, Any], str]:
    for ffprobe in _ffprobe_candidates():
        try:
            proc = subprocess.run(
                [
                    ffprobe,
                    "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries",
                    "stream=pix_fmt,color_space,color_primaries,color_transfer",
                    "-of", "json",
                    str(path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                **hidden_subprocess_kwargs(),
            )
            if proc.returncode != 0:
                continue
            payload = json.loads(proc.stdout or "{}")
            streams = payload.get("streams") or []
            if streams and isinstance(streams[0], dict):
                return dict(streams[0]), "ffprobe"
        except Exception:
            continue
    return {}, ""


def _probe_color_with_ffmpeg(path: Path, timeout_s: float) -> tuple[dict[str, Any], str]:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        ffmpeg = get_ffmpeg_exe()
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {}, ""
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            **hidden_subprocess_kwargs(),
        )
    except Exception:
        return {}, ""
    stream = parse_ffmpeg_color_stream_text((proc.stderr or "") + "\n" + (proc.stdout or ""))
    return stream, "ffmpeg" if stream else ""


def probe_export_color_metadata(
    output_path: Path | str,
    project_settings: dict[str, Any] | None,
    *,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    """Probe an exported file and compare its color tags to project intent."""
    path = Path(output_path)
    if not path.is_file():
        return {
            "ok": False,
            "probed": False,
            "tool": "",
            "diagnostics": "Color QA: output file missing",
            "comparison": compare_ffprobe_color_metadata(project_settings, {}),
        }
    stream, tool = _probe_color_with_ffprobe(path, timeout_s)
    if not stream:
        stream, tool = _probe_color_with_ffmpeg(path, timeout_s)
    comparison = compare_ffprobe_color_metadata(project_settings, stream)
    if not stream:
        return {
            "ok": False,
            "probed": False,
            "tool": "",
            "diagnostics": "Color QA: probe unavailable",
            "comparison": comparison,
        }
    if comparison["ok"]:
        actual = comparison.get("actual", {})
        summary = "/".join(
            str(actual.get(k, "") or "?")
            for k in ("colorspace", "color_primaries", "color_trc")
        )
        diagnostics = f"Color QA: OK ({summary}, {tool})"
    else:
        diagnostics = "Color QA: mismatch - " + "; ".join(comparison["mismatches"])
    return {
        "ok": bool(comparison["ok"]),
        "probed": True,
        "tool": tool,
        "diagnostics": diagnostics,
        "stream": stream,
        "comparison": comparison,
    }
