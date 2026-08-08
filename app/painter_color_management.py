"""ICC validation, conversion, and soft-proof operations for Painter output."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageCms


def _profile_bytes(value: bytes | bytearray | str | Path | None) -> bytes:
    if value is None:
        return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return Path(value).read_bytes()


def inspect_icc_profile(
    value: bytes | bytearray | str | Path,
    *,
    require_v4: bool = False,
) -> dict[str, Any]:
    data = _profile_bytes(value)
    errors: list[str] = []
    declared_size = int.from_bytes(data[:4], "big") if len(data) >= 4 else 0
    signature = data[36:40] if len(data) >= 40 else b""
    version_major = data[8] if len(data) >= 9 else 0
    if len(data) < 128:
        errors.append("ICC header is shorter than 128 bytes")
    if declared_size != len(data):
        errors.append("ICC declared profile size does not match payload size")
    if signature != b"acsp":
        errors.append("ICC profile signature is not acsp")
    if version_major not in {2, 4}:
        errors.append(f"Unsupported ICC major version: {version_major}")
    if require_v4 and version_major != 4:
        errors.append("ICC v4 profile required")
    pillow_valid = False
    description = ""
    try:
        profile = ImageCms.ImageCmsProfile(io.BytesIO(data))
        description = str(ImageCms.getProfileDescription(profile) or "").strip()
        pillow_valid = True
    except Exception as exc:
        errors.append(f"LittleCMS rejected profile: {type(exc).__name__}")
    return {
        "schema": "tigerstudio.painter.icc-inspection.v1",
        "valid": not errors,
        "require_v4": bool(require_v4),
        "version_major": int(version_major),
        "declared_size": int(declared_size),
        "actual_size": len(data),
        "device_class": data[12:16].decode("latin-1", "replace") if len(data) >= 16 else "",
        "color_space": data[16:20].decode("latin-1", "replace") if len(data) >= 20 else "",
        "pcs": data[20:24].decode("latin-1", "replace") if len(data) >= 24 else "",
        "description": description,
        "littlecms_valid": pillow_valid,
        "sha256": hashlib.sha256(data).hexdigest(),
        "errors": errors,
    }


def transform_rgba_profile(
    image: Image.Image,
    *,
    source_profile: bytes | bytearray | str | Path | None = None,
    output_profile: bytes | bytearray | str | Path | None = None,
    rendering_intent: int = 1,
) -> tuple[Image.Image, dict[str, Any]]:
    source_bytes = _profile_bytes(source_profile)
    output_bytes = _profile_bytes(output_profile)
    source_info = inspect_icc_profile(source_bytes)
    output_info = inspect_icc_profile(output_bytes)
    if not source_info["valid"] or not output_info["valid"]:
        raise ValueError("ICC transform requires valid source and output profiles")
    source = ImageCms.ImageCmsProfile(io.BytesIO(source_bytes))
    output = ImageCms.ImageCmsProfile(io.BytesIO(output_bytes))
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB")
    converted = ImageCms.profileToProfile(
        rgb,
        source,
        output,
        renderingIntent=max(0, min(3, int(rendering_intent))),
        outputMode="RGB",
    )
    converted.putalpha(alpha)
    return converted, {
        "schema": "tigerstudio.painter.icc-transform.v1",
        "applied": True,
        "identity_profiles": source_info["sha256"] == output_info["sha256"],
        "pixel_changed": converted.tobytes() != rgba.tobytes(),
        "alpha_preserved": converted.getchannel("A").tobytes() == alpha.tobytes(),
        "rendering_intent": int(rendering_intent),
        "source": source_info,
        "output": output_info,
    }


def soft_proof_rgba(
    image: Image.Image,
    *,
    source_profile: bytes | bytearray | str | Path | None = None,
    proof_profile: bytes | bytearray | str | Path,
    display_profile: bytes | bytearray | str | Path | None = None,
    rendering_intent: int = 1,
    proof_intent: int = 1,
) -> tuple[Image.Image, dict[str, Any]]:
    source_bytes = _profile_bytes(source_profile)
    proof_bytes = _profile_bytes(proof_profile)
    display_bytes = _profile_bytes(display_profile)
    profiles = {
        "source": inspect_icc_profile(source_bytes),
        "proof": inspect_icc_profile(proof_bytes),
        "display": inspect_icc_profile(display_bytes),
    }
    if not all(row["valid"] for row in profiles.values()):
        raise ValueError("Soft proof requires valid source, proof, and display profiles")
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    transform = ImageCms.buildProofTransform(
        ImageCms.ImageCmsProfile(io.BytesIO(source_bytes)),
        ImageCms.ImageCmsProfile(io.BytesIO(display_bytes)),
        ImageCms.ImageCmsProfile(io.BytesIO(proof_bytes)),
        "RGB",
        "RGB",
        renderingIntent=max(0, min(3, int(rendering_intent))),
        proofRenderingIntent=max(0, min(3, int(proof_intent))),
        flags=ImageCms.Flags.SOFTPROOFING,
    )
    proofed = ImageCms.applyTransform(rgba.convert("RGB"), transform)
    proofed.putalpha(alpha)
    return proofed, {
        "schema": "tigerstudio.painter.soft-proof.v1",
        "applied": True,
        "pixel_changed": proofed.tobytes() != rgba.tobytes(),
        "alpha_preserved": proofed.getchannel("A").tobytes() == alpha.tobytes(),
        "rendering_intent": int(rendering_intent),
        "proof_intent": int(proof_intent),
        "profiles": profiles,
    }


__all__ = ["inspect_icc_profile", "soft_proof_rgba", "transform_rgba_profile"]
