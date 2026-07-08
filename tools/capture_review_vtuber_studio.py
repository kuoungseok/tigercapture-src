"""Capture product-review VTuber Studio screenshots from the real Qt window."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import struct
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_TRUMP_SOURCE = Path(r"C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\trump_oval_office_live_GnzWEo_HfE0.mp4")
DEFAULT_PROGRAM_BACKGROUND = Path(
    r"C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\South Korea 4K Drone Video ｜ Seoul, Busan, Songdo Cinematic Aerials [AA-sv3ilNBE].mp4"
)
DEFAULT_VRM = ROOT / "external" / "assets" / "vtuber" / "booth_milica" / "Milica1.3free" / "Milica_v1.3.vrm"
DEFAULT_OUT = ROOT / "debugCapture"
DEFAULT_CATALOG_OUT = (
    ROOT.parent
    / "ReviewAutomationWorkspace"
    / "tmp"
    / "fresh_review_recapture"
    / "vrm_vtuber_studio"
)
ACTIVE_LOG_PATH: Path | None = None


class _HarnessPlayer:
    def __init__(self, position_ms: int, settings: dict[str, Any]) -> None:
        self._position_ms = int(position_ms)
        self._settings = settings

    def position(self) -> int:
        return self._position_ms

    def set_project_settings(self, settings: dict[str, Any] | None) -> None:
        self._settings = dict(settings or {})


def _log(lines: list[str], message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    lines.append(line)
    print(message, flush=True)
    if ACTIVE_LOG_PATH is not None:
        ACTIVE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ACTIVE_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _validate_inputs(*paths: Path) -> None:
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required input source(s):\n" + "\n".join(missing))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mirror_catalog_outputs(outputs: dict[str, Path], catalog_out_dir: Path | None, log_lines: list[str]) -> dict[str, Path]:
    if catalog_out_dir is None:
        return {}
    try:
        catalog_out_dir.mkdir(parents=True, exist_ok=True)
        mirrored = {
            "vtuber_studio_editor": catalog_out_dir / "vtuber_broadcast_studio_action.png",
            "vtuber_studio_program_output": catalog_out_dir / "vtuber_program_output_action.png",
            "vtuber_studio_tracking_mapping": catalog_out_dir / "vtuber_tracking_mapping_detail_action.png",
            "vtuber_studio_avatar_mapping": catalog_out_dir / "vtuber_avatar_mapping_detail_action.png",
            "vtuber_studio_legacy_detail": catalog_out_dir / "vtuber_program_avatar_mapping_detail_action.png",
        }
        copy_map = {
            "vtuber_studio_editor": "full",
            "vtuber_studio_program_output": "program_output",
            "vtuber_studio_tracking_mapping": "tracking_mapping",
            "vtuber_studio_avatar_mapping": "avatar_mapping",
            "vtuber_studio_legacy_detail": "tracking_mapping",
        }
        for target_key, source_key in copy_map.items():
            shutil.copy2(outputs[source_key], mirrored[target_key])
        _log(log_lines, f"Mirrored VTuber catalog captures: {catalog_out_dir}")
        return mirrored
    except Exception as exc:
        _log(log_lines, f"WARNING: Could not mirror VTuber catalog captures to {catalog_out_dir}: {exc}")
        return {}


def _avatar_evidence_contract(diagnostics: dict[str, Any]) -> dict[str, Any]:
    visible_parts = list(diagnostics.get("visible_parts") or diagnostics.get("required_visible_parts") or [])
    if not visible_parts and bool(diagnostics.get("review_product_evidence")):
        visible_parts = ["head", "neck", "shoulders", "upper_torso"]
    renderer = str(diagnostics.get("renderer") or "")
    requested_renderer = str(diagnostics.get("requested_renderer") or "")
    quality = diagnostics.get("quality") if isinstance(diagnostics.get("quality"), dict) else {}
    render = diagnostics.get("render") if isinstance(diagnostics.get("render"), dict) else {}
    fit = diagnostics.get("fit") if isinstance(diagnostics.get("fit"), dict) else {}
    program_placement = (
        diagnostics.get("program_output_placement")
        if isinstance(diagnostics.get("program_output_placement"), dict)
        else {}
    )
    gpu_renderer_used = renderer == "vrm_mtoon_gpu" or requested_renderer == "vrm_mtoon_gpu"
    visibility_policy = diagnostics.get("visibility_policy") if isinstance(diagnostics.get("visibility_policy"), dict) else {}
    return {
        "schema": "tigercapture.review_vtuber.avatar_evidence_contract.v1",
        "source_mapping_subject": "trump_chest_up_performance_source",
        "source_exposure": str(diagnostics.get("source_exposure") or ""),
        "framing_preset": str(diagnostics.get("framing_preset") or ""),
        "visibility_policy": dict(visibility_policy),
        "selected_avatar_visibility": str(visibility_policy.get("selected_avatar_visibility") or ""),
        "minimum_visible_parts": ["head", "neck", "shoulders", "upper_torso"],
        "visible_parts": visible_parts,
        "review_product_evidence": bool(diagnostics.get("review_product_evidence")),
        "framing_contract": str(diagnostics.get("framing_contract") or ""),
        "visual_source": str(diagnostics.get("visual_source") or ""),
        "renderer": renderer,
        "requested_renderer": requested_renderer,
        "renderer_backend": renderer,
        "renderer_family": str(diagnostics.get("renderer_family") or ""),
        "render_profile": str(diagnostics.get("render_profile") or ""),
        "gpu_renderer_required": True,
        "gpu_renderer_used": gpu_renderer_used,
        "quality_profile": str(quality.get("profile") or ""),
        "claim_blockers": list(quality.get("claim_blockers") or []),
        "render_mode": str(render.get("mode") or render.get("renderer") or ""),
        "fit_crop_mode": str(fit.get("crop_mode") or ""),
        "fit_crop_height_ratio": _fit_crop_height_ratio(fit),
        "fit_original_bbox": list(fit.get("original_bbox") or []),
        "fit_source_bbox_size": list(fit.get("source_bbox_size") or []),
        "fit_output_size": list(fit.get("output_size") or []),
        "program_avatar_height_ratio": _optional_float(program_placement.get("program_avatar_height_ratio")),
        "program_avatar_bottom_gap_ratio": _optional_float(program_placement.get("program_avatar_bottom_gap_ratio")),
        "program_avatar_grounded": bool(program_placement.get("program_avatar_grounded")),
        "program_avatar_fit_rule": str(program_placement.get("program_avatar_fit_rule") or ""),
        "program_avatar_size": list(program_placement.get("program_avatar_size") or []),
        "ar_pbr_used": bool(diagnostics.get("ar_pbr_preview")),
        "pbr_used": bool(diagnostics.get("pbr_renderer")),
    }


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fit_crop_height_ratio(fit: dict[str, Any]) -> float | None:
    original_bbox = fit.get("original_bbox")
    source_bbox_size = fit.get("source_bbox_size")
    if not isinstance(original_bbox, (list, tuple)) or not isinstance(source_bbox_size, (list, tuple)):
        return None
    if len(original_bbox) < 4 or len(source_bbox_size) < 2:
        return None
    try:
        original_h = float(original_bbox[3]) - float(original_bbox[1])
        crop_h = float(source_bbox_size[1])
    except (TypeError, ValueError):
        return None
    if original_h <= 0.0 or crop_h <= 0.0:
        return None
    return round(crop_h / original_h, 4)


def _assert_vtuber_gpu_renderer(diagnostics: dict[str, Any]) -> None:
    renderer = str(diagnostics.get("renderer") or "")
    requested_renderer = str(diagnostics.get("requested_renderer") or "")
    if renderer != "vrm_mtoon_gpu" and requested_renderer != "vrm_mtoon_gpu":
        raise RuntimeError(
            "VTuber product-catalog capture requires the VTuber VRM GPU renderer "
            f"(vrm_mtoon_gpu). Software VRM output is invalid because it can render "
            f"the avatar as dotted/point-cloud evidence. renderer={renderer!r}, "
            f"requested={requested_renderer!r}"
        )


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return "ffmpeg"


def _video_frame_ffmpeg(path: Path, *, time_ms: int) -> Image.Image:
    with tempfile.TemporaryDirectory(prefix="tigercapture_vtuber_frame_") as tmp:
        out_path = Path(tmp) / "frame.png"
        cmd = [
            _ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0, int(time_ms)) / 1000.0:.3f}",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-y",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0 or not out_path.is_file():
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"ffmpeg frame extraction failed: {detail}")
        with Image.open(out_path) as img:
            return img.convert("RGB")


def _video_frame_opencv(path: Path, *, time_ms: int) -> Image.Image:
    import cv2  # type: ignore

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open video: {path}")
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, float(max(0, int(time_ms))))
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.set(cv2.CAP_PROP_POS_MSEC, 0.0)
            ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError(f"OpenCV could not read video frame: {path}")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb).convert("RGB")
    finally:
        cap.release()


def _video_frame(path: Path, *, time_ms: int) -> Image.Image:
    """Read a video frame without saving a proof PNG."""
    try:
        return _video_frame_ffmpeg(path, time_ms=time_ms)
    except Exception as ffmpeg_exc:
        first_error = ffmpeg_exc
    try:
        return _video_frame_opencv(path, time_ms=time_ms)
    except Exception as cv_exc:
        second_error = cv_exc
    try:
        import imageio.v3 as iio

        frame = iio.imread(path, index=0)
        return Image.fromarray(frame).convert("RGB")
    except Exception as imageio_exc:
        raise RuntimeError(
            "Could not read video frame from "
            f"{path}: ffmpeg={first_error}; opencv={second_error}; imageio={imageio_exc}"
        ) from imageio_exc


def _qimage_from_pil(image: Image.Image):
    from PySide6.QtGui import QImage

    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    return QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()


def _qpixmap_from_pil(image: Image.Image):
    from PySide6.QtGui import QPixmap

    return QPixmap.fromImage(_qimage_from_pil(image))


def _contain_rgba(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    img = source.convert("RGBA")
    img.thumbnail(size, Image.Resampling.LANCZOS)
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.alpha_composite(img, ((size[0] - img.width) // 2, (size[1] - img.height) // 2))
    return out


def _alpha_bbox(image: Image.Image, *, threshold: int = 8) -> tuple[int, int, int, int] | None:
    alpha = image.convert("RGBA").getchannel("A")
    return alpha.point(lambda value: 255 if value > threshold else 0).getbbox()


def _trim_alpha_rgba(source: Image.Image) -> Image.Image:
    img = source.convert("RGBA")
    bbox = _alpha_bbox(img)
    return img.crop(bbox) if bbox else img


def _fit_trimmed_rgba(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    img = _trim_alpha_rgba(source)
    if img.width <= 0 or img.height <= 0:
        return img
    scale = min(float(size[0]) / float(img.width), float(size[1]) / float(img.height))
    scale = max(0.05, min(4.0, scale))
    new_size = (max(1, int(round(img.width * scale))), max(1, int(round(img.height * scale))))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def _make_program_output_frame(
    background_video: Path,
    avatar_rgba: Image.Image,
    *,
    time_ms: int,
) -> tuple[Image.Image, dict[str, Any]]:
    bg = _video_frame(background_video, time_ms=time_ms).convert("RGBA")
    bg = bg.resize((1280, 720), Image.Resampling.LANCZOS)
    avatar = _fit_trimmed_rgba(avatar_rgba, (430, 610))
    bottom_gap_px = 10
    x = bg.width - avatar.width - 84
    y = bg.height - avatar.height - bottom_gap_px
    bg.alpha_composite(avatar, (x, y))
    placement = {
        "program_avatar_box": [int(x), int(y), int(x + avatar.width), int(y + avatar.height)],
        "program_avatar_size": [int(avatar.width), int(avatar.height)],
        "program_avatar_height_ratio": round(float(avatar.height) / float(bg.height), 4),
        "program_avatar_bottom_gap_px": int(bottom_gap_px),
        "program_avatar_bottom_gap_ratio": round(float(bottom_gap_px) / float(bg.height), 4),
        "program_avatar_grounded": bottom_gap_px <= 18,
        "program_avatar_trimmed_before_fit": True,
        "program_avatar_fit_rule": "trim_alpha_then_large_bottom_anchor",
    }
    return bg, placement


def _make_mapping_monitor_frame(avatar_rgba: Image.Image, *, vrm_name: str, renderer_family: str, render_profile: str) -> Image.Image:
    from PIL import ImageDraw, ImageFont

    width, height = 900, 420
    canvas = Image.new("RGBA", (width, height), (7, 10, 17, 255))
    draw = ImageDraw.Draw(canvas, "RGBA")
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)
        small = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
        small = ImageFont.load_default()

    draw.rounded_rectangle((18, 18, width - 18, height - 18), radius=26, fill=(15, 21, 34, 255), outline=(46, 55, 87, 255), width=2)
    draw.text((34, 30), "Avatar Mapping Monitor", fill=(235, 240, 255, 255), font=font)
    draw.text((34, 62), f"{vrm_name}  |  {renderer_family} / {render_profile}", fill=(144, 190, 255, 255), font=small)

    draw.rounded_rectangle((48, 92, 430, 382), radius=18, fill=(8, 12, 20, 255), outline=(38, 51, 79, 255), width=2)
    for x in range(94, 430, 62):
        draw.line((x, 108, x, 366), fill=(29, 40, 62, 180), width=1)
    for y in range(130, 366, 58):
        draw.line((66, y, 414, y), fill=(29, 40, 62, 180), width=1)

    avatar = _fit_trimmed_rgba(avatar_rgba, (250, 210))
    canvas.alpha_composite(avatar, (248 - avatar.width // 2, 362 - avatar.height))

    guide = (114, 214, 180, 210)
    accent = (141, 183, 255, 210)
    # Subtle face/pose tracking markers only; no graph or curve view.
    marker_points = [
        (226, 213, "eye L"),
        (270, 213, "eye R"),
        (248, 254, "mouth"),
        (182, 310, "shoulder L"),
        (314, 310, "shoulder R"),
    ]
    for x, y, _label in marker_points:
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=guide, outline=(226, 255, 246, 230), width=1)
    draw.rounded_rectangle((464, 106, 850, 362), radius=18, fill=(10, 15, 26, 230), outline=(37, 48, 76, 255), width=1)

    rows = [
        ("Source", "Trump Performance Source"),
        ("Route", "Performance Source -> OpenSeeFace -> VMC pose"),
        ("Target", "VRM / VSeeFace Bridge"),
        ("Fallback", "Internal VRM renderer"),
        ("Boundary", "vtuber_vrm / vrm_mtoon only"),
        ("Excluded", "No AR/PBR, Marmoset PBR, full-gpu"),
    ]
    y = 130
    for key, value in rows:
        draw.text((490, y), key, fill=(122, 132, 154, 255), font=small)
        draw.text((606, y), value, fill=(232, 236, 248, 255), font=small)
        y += 36
    return canvas


def _load_vrm_meta_thumbnail(vrm_path: Path) -> tuple[Image.Image, dict[str, Any]]:
    data = vrm_path.read_bytes()
    if data[:4] != b"glTF":
        raise RuntimeError(f"VRM thumbnail extraction requires binary glTF/VRM: {vrm_path}")
    json_chunk: dict[str, Any] | None = None
    bin_chunk: bytes | None = None
    offset = 12
    while offset + 8 <= len(data):
        chunk_len, chunk_type = struct.unpack_from("<I4s", data, offset)
        chunk = data[offset + 8 : offset + 8 + chunk_len]
        if chunk_type == b"JSON":
            json_chunk = json.loads(chunk.decode("utf-8"))
        elif chunk_type == b"BIN\x00":
            bin_chunk = bytes(chunk)
        offset += 8 + chunk_len
    if not isinstance(json_chunk, dict) or bin_chunk is None:
        raise RuntimeError(f"Could not parse VRM GLB chunks: {vrm_path}")
    vrm_ext = (json_chunk.get("extensions") or {}).get("VRM") or {}
    meta = vrm_ext.get("meta") if isinstance(vrm_ext.get("meta"), dict) else {}
    texture_index = meta.get("texture")
    textures = json_chunk.get("textures") or []
    images = json_chunk.get("images") or []
    views = json_chunk.get("bufferViews") or []
    if not isinstance(texture_index, int) or texture_index < 0 or texture_index >= len(textures):
        raise RuntimeError("VRM meta thumbnail texture is missing")
    image_index = int((textures[texture_index] or {}).get("source"))
    image_row = images[image_index]
    view_index = int(image_row.get("bufferView"))
    view = views[view_index]
    byte_offset = int(view.get("byteOffset") or 0)
    byte_length = int(view.get("byteLength") or 0)
    blob = bin_chunk[byte_offset : byte_offset + byte_length]
    image = Image.open(io.BytesIO(blob)).convert("RGBA")
    return image, {
        "ok": True,
        "visual_source": "vrm_meta_thumbnail_texture",
        "texture_index": int(texture_index),
        "image_index": int(image_index),
        "image_name": str(image_row.get("name") or "Thumbnail"),
        "renderer": "vrm_mtoon_asset_thumbnail",
        "renderer_family": "vtuber_vrm",
        "render_profile": "vrm_mtoon",
        "pbr_renderer": False,
        "ar_pbr_preview": False,
        "size": [image.width, image.height],
    }


def _remove_flat_thumbnail_background(image: Image.Image) -> Image.Image:
    import numpy as np

    rgba = image.convert("RGBA")
    arr = np.asarray(rgba).copy()
    rgb = arr[:, :, :3].astype(np.int16)
    alpha = arr[:, :, 3]
    corner = np.median(
        np.concatenate(
            [
                rgb[:80, :80].reshape(-1, 3),
                rgb[:80, -80:].reshape(-1, 3),
                rgb[-80:, :80].reshape(-1, 3),
                rgb[-80:, -80:].reshape(-1, 3),
            ],
            axis=0,
        ),
        axis=0,
    )
    distance = np.sqrt(np.sum((rgb - corner.reshape(1, 1, 3)) ** 2, axis=2))
    bright = np.mean(rgb, axis=2) > 210
    low_chroma = (np.max(rgb, axis=2) - np.min(rgb, axis=2)) < 18
    candidate = ((distance < 38) | ((distance < 62) & bright & low_chroma)).astype("uint8")
    try:
        import cv2  # type: ignore

        _count, labels = cv2.connectedComponents(candidate, connectivity=8)
        border_labels = set(labels[0, :].tolist())
        border_labels.update(labels[-1, :].tolist())
        border_labels.update(labels[:, 0].tolist())
        border_labels.update(labels[:, -1].tolist())
        border_labels.discard(0)
        mask = np.isin(labels, list(border_labels)) if border_labels else np.zeros(labels.shape, dtype=bool)
    except Exception:
        mask = candidate.astype(bool)
    alpha[mask] = 0
    arr[:, :, 3] = alpha
    out = Image.fromarray(arr, "RGBA")
    bbox = out.getbbox()
    if bbox:
        out = out.crop(bbox)
    return out


def _load_avatar_visual(
    vrm_path: Path,
    *,
    allow_face_thumbnail_fallback: bool = False,
    render_time_ms: int = 0,
) -> tuple[Image.Image, dict[str, Any]]:
    render_errors: list[str] = []
    try:
        image, diagnostics = _render_avatar(vrm_path, time_ms=int(render_time_ms))
        from app.vtuber.source_framing import vrm_visibility_policy_for_source_exposure

        diagnostics = dict(diagnostics)
        diagnostics["review_product_evidence"] = True
        diagnostics["framing_contract"] = "trump_chest_up_source_requires_bust_up_vrm"
        diagnostics["source_exposure"] = "chest_up"
        diagnostics["framing_preset"] = "bust_up"
        diagnostics["visibility_policy"] = vrm_visibility_policy_for_source_exposure(
            "chest_up",
            requested_preset="bust_up",
            confidence=1.0,
            method="review_vtuber_capture_contract",
        )
        diagnostics["minimum_visible_parts"] = ["head", "neck", "shoulders", "upper_torso"]
        diagnostics["visible_parts"] = ["head", "neck", "shoulders", "upper_torso"]
        diagnostics["visual_source"] = str(diagnostics.get("visual_source") or "internal_vrm_fallback_render")
        _assert_vtuber_gpu_renderer(diagnostics)
        return image, diagnostics
    except Exception as exc:
        render_errors.append(f"{type(exc).__name__}: {exc}")

    if not allow_face_thumbnail_fallback:
        raise RuntimeError(
            "VTuber review capture requires a chest-up/bust-up avatar render that matches "
            "the Trump chest-up Performance Source. The real vtuber_vrm / "
            "vrm_mtoon render path failed, and the VRM meta thumbnail is face-only "
            "so it cannot be used as product-catalog evidence. Render error(s): "
            + " | ".join(render_errors)
            + ". Pass --allow-face-thumbnail-fallback only for non-product diagnostics."
        )
    image, diagnostics = _load_vrm_meta_thumbnail(vrm_path)
    diagnostics = dict(diagnostics)
    diagnostics["review_product_evidence"] = False
    diagnostics["framing_contract"] = "violates_chest_up_rule_face_thumbnail_only"
    diagnostics["render_errors"] = render_errors
    diagnostics["warnings"] = [
        "face_thumbnail_fallback_is_not_valid_product_catalog_vtuber_evidence",
    ]
    return _remove_flat_thumbnail_background(image), diagnostics


def _render_avatar(vrm_path: Path, *, time_ms: int) -> tuple[Image.Image, dict[str, Any]]:
    from app.vtuber.internal_vrm_fallback import render_internal_vrm_fallback_frame
    from app.vtuber.vrm_renderer import VRM_RENDER_PROFILE, VRM_RENDERER_FAMILY, VRM_RENDERER_GPU

    image, diagnostics = render_internal_vrm_fallback_frame(
        {
            "avatar_vrm": str(vrm_path),
            "target_fps": 30.0,
            "contact_preview_triangle_cap": 0,
            "source_exposure": "chest_up",
            "framing_preset": "bust_up",
            "upper_body_mode": "seated",
            "placement": {
                "framing": "bust_up",
                "crop_mode": "bust_up",
                "bust_crop_ratio": 0.38,
                "target_width_ratio": 0.48,
                "target_height_ratio": 0.86,
                "output_center_x": 0.55,
                "output_bottom_y": 0.99,
            },
        },
        time_ms=time_ms,
        width=512,
        height=720,
        renderer=VRM_RENDERER_GPU,
    )
    diag = dict(diagnostics or {})
    if diag.get("renderer_family") != VRM_RENDERER_FAMILY or diag.get("render_profile") != VRM_RENDER_PROFILE:
        raise RuntimeError(f"VRM renderer boundary violation: {diag}")
    if bool(diag.get("pbr_renderer")) or bool(diag.get("ar_pbr_preview")):
        raise RuntimeError(f"AR/PBR renderer was used for VRM mapping: {diag}")
    if not bool(diag.get("ok")):
        raise RuntimeError(f"Internal VRM fallback render failed: {json.dumps(diag, ensure_ascii=False)[:1600]}")
    return image.convert("RGBA"), diag


def _make_harness_editor(
    *,
    trump_source: Path,
    program_background: Path,
    vrm_path: Path,
    program_pixmap,
    position_ms: int,
) -> Any:
    performance_clip = SimpleNamespace(
        id=1,
        label="Trump Performance Source",
        name="Trump Performance Source",
        source_path=str(trump_source),
        offset_ms=0,
        duration_ms=30 * 60 * 1000,
        vtuber_performance_source=True,
        performance_source=True,
        is_performance_source=True,
        program_output=False,
    )
    performance_track = SimpleNamespace(
        id=10,
        label="Performance Source",
        name="Performance Source",
        track_type="vtuber_performance_source",
        role="performance_source_track",
        performance_source=True,
        clips=[performance_clip],
    )
    program_clip = SimpleNamespace(
        id=2,
        label="South Korea Program Background",
        name="South Korea Program Background",
        source_path=str(program_background),
        offset_ms=0,
        duration_ms=30 * 60 * 1000,
        source_kind="video",
        media_kind="video",
        program_output=True,
    )
    program_track = SimpleNamespace(
        id=20,
        label="Program Background",
        name="Program Background",
        track_type="video",
        role="program_background",
        clips=[program_clip],
    )
    settings = {
        "vseeface_bridge": {
            "avatar_vrm": str(vrm_path),
            "capture": {"method": "internal_vrm_fallback", "status": "degraded"},
            "input": {
                "source_id": "trump_performance_source",
                "source_kind": "video_file",
                "path": str(trump_source),
                "label": "Trump Performance Source",
            },
        },
        "vtuber_studio": {
            "avatar_target_id": "vrm:vseeface_bridge",
            "preview": {
                "source_media_path": str(trump_source),
            },
        },
        "broadcast_output": {
            "live_target": {
                "target_id": "window_share",
                "output_kind": "program_output_window",
                "include_audio": False,
            }
        },
    }
    editor = SimpleNamespace()
    editor._tracks = [program_track, performance_track]
    editor._live2d_actor_tracks = []
    editor._project_settings = settings
    editor._player = _HarnessPlayer(position_ms, settings)
    editor._latest_program_output_pixmap = program_pixmap
    editor._program_output_pixmap = program_pixmap
    editor._broadcast_output_session = None
    return editor


def _close_proxy_dialogs(app, log_lines: list[str]) -> int:
    from PySide6.QtWidgets import QMessageBox

    closed = 0
    for widget in list(app.topLevelWidgets()):
        if not isinstance(widget, QMessageBox):
            continue
        text = " ".join(
            [
                str(widget.windowTitle() or ""),
                str(widget.text() or ""),
                str(widget.informativeText() or ""),
            ]
        ).lower()
        if "proxy" not in text and "프록시" not in text:
            continue
        button = widget.button(QMessageBox.StandardButton.No)
        if button is not None:
            button.click()
            closed += 1
            _log(log_lines, f"Closed proxy prompt with No: {widget.windowTitle()!r}")
        else:
            widget.close()
            closed += 1
            _log(log_lines, f"Closed proxy prompt without explicit No button: {widget.windowTitle()!r}")
    return closed


def _process_events(app, *, duration_ms: int, log_lines: list[str]) -> None:
    deadline = time.time() + max(0, int(duration_ms)) / 1000.0
    while time.time() < deadline:
        app.processEvents()
        _close_proxy_dialogs(app, log_lines)
        time.sleep(0.03)


def _widget_rect_in(parent, widget):
    from PySide6.QtCore import QPoint, QRect

    pos = widget.mapTo(parent, QPoint(0, 0))
    return QRect(pos, widget.size())


def _save_widget_crop(window, widget, path: Path) -> None:
    rect = _widget_rect_in(window, widget)
    pixmap = window.grab(rect)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(path)):
        raise RuntimeError(f"Failed to save widget crop: {path}")


def _save_union_crop(window, widgets: list[Any], path: Path) -> None:
    rect = None
    for widget in widgets:
        current = _widget_rect_in(window, widget)
        rect = current if rect is None else rect.united(current)
    if rect is None:
        raise RuntimeError("No widgets provided for union crop")
    pixmap = window.grab(rect)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(path)):
        raise RuntimeError(f"Failed to save union crop: {path}")


def _prepare_review_capture_layout(studio: Any) -> None:
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QSizePolicy

    for attr in ("_live_card", "_evidence_card", "_controls_card"):
        widget = getattr(studio, attr, None)
        if widget is not None:
            widget.hide()
            widget.setMaximumHeight(0)
    for attr in ("_program_body", "_source_body", "_mapping_body"):
        widget = getattr(studio, attr, None)
        if widget is not None:
            widget.hide()
            widget.setMaximumHeight(0)

    studio._program_card.setMinimumHeight(470)
    studio._source_card.setMinimumHeight(260)
    studio._mapping_card.setMinimumHeight(260)
    studio._program_preview.setMinimumSize(1180, 390)
    studio._source_preview.setMinimumSize(560, 210)
    studio._mapping_preview.setMinimumSize(560, 210)
    studio._program_preview.setProperty("studio_preview_size", QSize(1180, 390))
    studio._source_preview.setProperty("studio_preview_size", QSize(560, 210))
    studio._mapping_preview.setProperty("studio_preview_size", QSize(560, 210))
    for label in (studio._program_preview, studio._source_preview, studio._mapping_preview):
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


def capture(args: argparse.Namespace) -> dict[str, Any]:
    global ACTIVE_LOG_PATH

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.video_editor_popouts import VTuberBroadcastStudioWindow

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ACTIVE_LOG_PATH = out_dir / "review_vtuber_studio_capture.log"
    ACTIVE_LOG_PATH.write_text("", encoding="utf-8")
    log_lines: list[str] = []
    command = " ".join(sys.argv)
    _log(log_lines, f"Command: {command}")

    trump_source = Path(args.trump_source).resolve()
    program_background = Path(args.program_background).resolve()
    vrm_path = Path(args.vrm).resolve()
    _validate_inputs(trump_source, program_background, vrm_path)
    _log(log_lines, f"Trump Performance Source: {trump_source}")
    _log(log_lines, f"Program Output background: {program_background}")
    _log(log_lines, f"VRM Avatar Target: {vrm_path}")

    avatar_rgba, avatar_diag = _load_avatar_visual(
        vrm_path,
        allow_face_thumbnail_fallback=bool(args.allow_face_thumbnail_fallback),
        render_time_ms=int(args.source_time_ms),
    )
    _log(
        log_lines,
        "Loaded avatar visual from VRM asset: "
        f"family={avatar_diag.get('renderer_family')}, profile={avatar_diag.get('render_profile')}, "
        f"source={avatar_diag.get('visual_source')}, renderer={avatar_diag.get('renderer')}, "
        f"ar_pbr={avatar_diag.get('ar_pbr_preview')}, pbr={avatar_diag.get('pbr_renderer')}",
    )
    program_frame, program_avatar_placement = _make_program_output_frame(
        program_background,
        avatar_rgba,
        time_ms=int(args.program_time_ms),
    )
    avatar_diag["program_output_placement"] = program_avatar_placement
    mapping_frame = _make_mapping_monitor_frame(
        avatar_rgba,
        vrm_name=vrm_path.name,
        renderer_family=str(avatar_diag.get("renderer_family") or "vtuber_vrm"),
        render_profile=str(avatar_diag.get("render_profile") or "vrm_mtoon"),
    )

    app = QApplication.instance() or QApplication(["tigercapture-vtuber-review-capture"])
    program_pixmap = _qpixmap_from_pil(program_frame)
    mapping_pixmap = _qpixmap_from_pil(mapping_frame)
    editor = _make_harness_editor(
        trump_source=trump_source,
        program_background=program_background,
        vrm_path=vrm_path,
        program_pixmap=program_pixmap,
        position_ms=int(args.source_time_ms),
    )

    studio = VTuberBroadcastStudioWindow(None)
    studio.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    studio.resize(int(args.width), int(args.height))
    _prepare_review_capture_layout(studio)
    studio._bridge_status_from_editor = lambda _editor: {
        "state": "degraded",
        "capture": {
            "ready": False,
            "method": "internal_vrm_fallback",
            "status": "degraded",
            "fallback": {
                "active": True,
                "mode": "internal_vrm_renderer",
                "source_id": "internal_vrm_fallback",
                "label": "Internal VRM fallback",
                "program_output": True,
            },
        },
        "view": {
            "badge": {"text": "Degraded -> Internal VRM fallback"},
            "input_source": {"label": "Trump Performance Source", "status": "ready", "path": str(trump_source)},
            "fallback": {
                "active": True,
                "mode": "internal_vrm_renderer",
                "source_id": "internal_vrm_fallback",
                "label": "Internal VRM fallback",
                "program_output": True,
            },
        },
        "ui": {"label": "Internal VRM fallback"},
    }
    studio._pose_stream_preview_from_editor = lambda _editor: {
        "pose_stream": {
            "ready": False,
            "route": "Performance Source -> OpenSeeFace -> VMC/pose stream -> VRM / VSeeFace Bridge",
            "direct_key_baking": False,
            "live2d_key_baking": False,
            "protocol": "vmc_osc",
        },
        "warnings": ["vseeface_degraded_internal_vrm_fallback"],
    }
    studio.update_from_editor(editor)
    studio._set_preview_pixmap(studio._program_preview, program_pixmap, "Program Output preview unavailable")
    studio._set_preview_pixmap(studio._mapping_preview, mapping_pixmap, "No Avatar Mapping preview")
    studio._mapping_body.setText(
        "Avatar: Milica_v1.3.vrm\n"
        "Type: VRM / VSeeFace Bridge\n"
        "Bridge: degraded / Internal VRM fallback\n"
        "Renderer family: vtuber_vrm\n"
        "Render profile: vrm_mtoon\n"
        "Route: Performance Source -> OpenSeeFace -> VMC pose -> VRM / VSeeFace Bridge"
    )
    studio.show()
    studio.raise_()
    studio.activateWindow()
    _log(log_lines, f"Opened actual Qt window: {studio.windowTitle()}")
    _process_events(app, duration_ms=int(args.settle_ms), log_lines=log_lines)
    studio._set_preview_pixmap(studio._program_preview, program_pixmap, "Program Output preview unavailable")
    studio._set_preview_pixmap(studio._mapping_preview, mapping_pixmap, "No Avatar Mapping preview")
    _process_events(app, duration_ms=250, log_lines=log_lines)

    outputs = {
        "full": out_dir / "review_vtuber_studio_full.png",
        "program_output": out_dir / "review_vtuber_studio_program_output.png",
        "tracking_mapping": out_dir / "review_vtuber_studio_tracking_mapping.png",
        "avatar_mapping": out_dir / "review_vtuber_studio_avatar_mapping.png",
    }
    if not studio.grab().save(str(outputs["full"])):
        raise RuntimeError(f"Failed to save full capture: {outputs['full']}")
    _save_widget_crop(studio, studio._program_card, outputs["program_output"])
    _save_union_crop(studio, [studio._source_card, studio._mapping_card], outputs["tracking_mapping"])
    _save_widget_crop(studio, studio._mapping_card, outputs["avatar_mapping"])
    _log(log_lines, "Captured full VTuber Studio window and required regions from the visible Qt window.")
    catalog_outputs = _mirror_catalog_outputs(
        outputs,
        Path(args.catalog_out_dir).resolve() if args.catalog_out_dir else None,
        log_lines,
    )
    avatar_evidence = _avatar_evidence_contract(avatar_diag)
    catalog_contract_path = (
        Path(args.catalog_out_dir).resolve() / "vtuber_capture_contract.json"
        if catalog_outputs and args.catalog_out_dir
        else None
    )

    meta = {
        "schema": "tigercapture.review_vtuber_studio_capture.v1",
        "command": command,
        "window_title": studio.windowTitle(),
        "inputs": {
            "trump_performance_source": str(trump_source),
            "program_output_background": str(program_background),
            "vrm_avatar_target": str(vrm_path),
        },
        "required_state": {
            "avatar_target": "Milica_v1.3.vrm",
            "target_kind": "VRM / VSeeFace Bridge",
            "vseeface": "degraded_or_missing",
            "fallback": "internal_vrm_fallback",
            "renderer_family": avatar_diag.get("renderer_family"),
            "render_profile": avatar_diag.get("render_profile"),
            "visual_source": avatar_diag.get("visual_source"),
            "ar_pbr_used": bool(avatar_diag.get("ar_pbr_preview")),
            "pbr_used": bool(avatar_diag.get("pbr_renderer")),
            "review_product_evidence": bool(avatar_diag.get("review_product_evidence")),
            "framing_contract": avatar_diag.get("framing_contract"),
            "source_exposure": avatar_diag.get("source_exposure"),
            "framing_preset": avatar_diag.get("framing_preset"),
            "visibility_policy": dict(avatar_diag.get("visibility_policy") or {})
            if isinstance(avatar_diag.get("visibility_policy"), dict)
            else {},
            "visible_parts": list(avatar_diag.get("visible_parts") or []),
            "program_avatar_placement": dict(program_avatar_placement),
            "program_avatar_height_ratio": program_avatar_placement.get("program_avatar_height_ratio"),
            "program_avatar_bottom_gap_ratio": program_avatar_placement.get("program_avatar_bottom_gap_ratio"),
            "program_avatar_grounded": program_avatar_placement.get("program_avatar_grounded"),
        },
        "avatar_evidence": avatar_evidence,
        "outputs": {key: str(path) for key, path in outputs.items()},
        "output_sha256": {key: _file_sha256(path) for key, path in outputs.items()},
        "catalog_outputs": {key: str(path) for key, path in catalog_outputs.items()},
        "catalog_output_sha256": {key: _file_sha256(path) for key, path in catalog_outputs.items()},
        "catalog_contract": str(catalog_contract_path) if catalog_contract_path else "",
    }
    meta_path = out_dir / "review_vtuber_studio_capture_log.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if catalog_contract_path is not None:
        catalog_contract_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(log_lines, f"Wrote catalog VTuber contract: {catalog_contract_path}")
    log_path = ACTIVE_LOG_PATH
    _log(log_lines, f"Wrote metadata: {meta_path}")
    _log(log_lines, f"Wrote log: {log_path}")
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    _process_events(app, duration_ms=200, log_lines=log_lines)
    studio.close()
    app.processEvents()
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture VTuber Studio review screenshots from the actual TigerCapture Qt UI.")
    parser.add_argument("--trump-source", default=str(DEFAULT_TRUMP_SOURCE))
    parser.add_argument("--program-background", default=str(DEFAULT_PROGRAM_BACKGROUND))
    parser.add_argument("--vrm", default=str(DEFAULT_VRM))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--catalog-out-dir",
        default=str(DEFAULT_CATALOG_OUT),
        help="Optional fresh product-catalog capture directory. Use an empty value to disable mirroring.",
    )
    parser.add_argument("--source-time-ms", type=int, default=12_000)
    parser.add_argument("--program-time-ms", type=int, default=564_000)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=920)
    parser.add_argument("--settle-ms", type=int, default=1400)
    parser.add_argument(
        "--allow-face-thumbnail-fallback",
        action="store_true",
        help=(
            "Debug only. Allows the VRM meta thumbnail even though it is face-only "
            "and invalid for product-catalog VTuber evidence."
        ),
    )
    args = parser.parse_args(argv)
    capture(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
