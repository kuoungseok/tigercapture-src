"""VSeeFace sidecar settings writer.

This module only prepares VSeeFace's own `settings.ini` for external sidecar
use. It does not embed, link, or import VSeeFace internals.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.vtuber.vmc_protocol import VMC_DEFAULT_HOST, VMC_VSEEFACE_SENDER_PORT


OPENSEEDEMO_SECTION = "OpenSeeDemo"
OPENSEEFACE_TRACKING_CAMERA_NAME = "[OpenSeeFace tracking]"
VSEEFACE_KEEP_VIRTUAL_CAMERA_ENABLED_KEY = "KeepVirtualCamEnabled"


@dataclass(frozen=True)
class VSeeFaceSettingsWriteResult:
    path: str
    backup_path: str
    encoding: str
    section: str
    duplicate_sections_removed: int
    keys_written: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "backup_path": self.backup_path,
            "encoding": self.encoding,
            "section": self.section,
            "duplicate_sections_removed": self.duplicate_sections_removed,
            "keys_written": list(self.keys_written),
        }


def default_vseeface_settings_path(home: str | Path | None = None) -> Path:
    root = Path(home) if home is not None else Path.home()
    return root / "AppData" / "LocalLow" / "Emiliana_vt" / "VSeeFace" / "settings.ini"


def build_sidecar_settings_values(
    *,
    avatar_vrm: str | Path,
    openseeface_host: str = VMC_DEFAULT_HOST,
    openseeface_port: int = VMC_VSEEFACE_SENDER_PORT,
    camera_name: str = OPENSEEFACE_TRACKING_CAMERA_NAME,
    disable_leap_motion: bool = True,
    enable_virtual_camera: bool = True,
) -> dict[str, str]:
    """Return VSeeFace settings keys for a video-driven sidecar setup.

    `IP` and `Port` are VSeeFace's OpenSeeFace tracking input settings, not the
    VMC receiver settings. The VMC receiver is enabled from VSeeFace's runtime
    UI and does not appear to be a stable `settings.ini` key in v1.13.38c.

    `KeepVirtualCamEnabled` is present in VSeeFace v1.13.38c and keeps the
    bundled UnityCapture output available across launches.
    """
    avatar_path = Path(avatar_vrm)
    values = {
        "AvatarDirectory": str(avatar_path.parent),
        "AvatarFile": str(avatar_path),
        "CameraName": str(camera_name or OPENSEEFACE_TRACKING_CAMERA_NAME),
        "Camera": "0",
        "IP": str(openseeface_host or VMC_DEFAULT_HOST),
        "Port": str(max(1, min(65535, int(openseeface_port or VMC_VSEEFACE_SENDER_PORT)))),
        "AutoBlink": "0",
        "SmoothAutoBlink": "1",
        "GazeStrength": "1",
    }
    if enable_virtual_camera:
        values[VSEEFACE_KEEP_VIRTUAL_CAMERA_ENABLED_KEY] = "1"
    if disable_leap_motion:
        values.update({
            "TrackLeapMotion": "0",
            "LeapMotionOrionV4Compat": "0",
        })
    return values


def write_vseeface_sidecar_settings(
    settings_path: str | Path,
    values: Mapping[str, Any],
    *,
    backup: bool = True,
    backup_suffix: str = ".codex_backup",
) -> VSeeFaceSettingsWriteResult:
    path = Path(settings_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.read_bytes() if path.is_file() else b""
    text = _decode_settings(original)
    merged, duplicate_count = _merge_openseedemo_section(text, {str(k): str(v) for k, v in values.items()})
    encoded, encoding = _encode_settings(merged)

    backup_path = ""
    if backup and path.is_file():
        backup_target = _next_backup_path(path, backup_suffix)
        backup_target.write_bytes(original)
        backup_path = str(backup_target)
    path.write_bytes(encoded)
    return VSeeFaceSettingsWriteResult(
        path=str(path),
        backup_path=backup_path,
        encoding=encoding,
        section=OPENSEEDEMO_SECTION,
        duplicate_sections_removed=max(0, duplicate_count - 1),
        keys_written=list(values.keys()),
    )


def read_openseedemo_settings(settings_path: str | Path) -> dict[str, str]:
    path = Path(settings_path)
    if not path.is_file():
        return {}
    text = _decode_settings(path.read_bytes())
    values: dict[str, str] = {}
    in_section = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            in_section = line[1:-1].strip() == OPENSEEDEMO_SECTION
            continue
        if in_section and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _decode_settings(data: bytes) -> str:
    if not data:
        return ""
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace")
    return data.decode("utf-8", errors="replace")


def _encode_settings(text: str) -> tuple[bytes, str]:
    try:
        return text.encode("ascii"), "ascii"
    except UnicodeEncodeError:
        return text.encode("utf-16"), "utf-16"


def _merge_openseedemo_section(text: str, updates: dict[str, str]) -> tuple[str, int]:
    existing: dict[str, str] = {}
    other_sections: list[str] = []
    current_other: list[str] = []
    in_openseedemo = False
    in_other = False
    duplicate_count = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            if current_other:
                other_sections.extend(current_other)
                current_other = []
            section = line[1:-1].strip()
            in_openseedemo = section == OPENSEEDEMO_SECTION
            in_other = not in_openseedemo
            if in_openseedemo:
                duplicate_count += 1
            else:
                current_other.append(raw_line)
            continue
        if in_openseedemo and "=" in line:
            key, value = line.split("=", 1)
            existing[key.strip()] = value.strip()
        elif in_other:
            current_other.append(raw_line)
    if current_other:
        other_sections.extend(current_other)

    existing.update(updates)
    lines = [f"[{OPENSEEDEMO_SECTION}]"]
    lines.extend(f"{key}={value}" for key, value in existing.items())
    if other_sections:
        lines.append("")
        lines.extend(other_sections)
    return "\n".join(lines).rstrip() + "\n", duplicate_count


def _next_backup_path(path: Path, suffix: str) -> Path:
    candidate = path.with_name(path.name + suffix)
    if not candidate.exists():
        return candidate
    index = 1
    while True:
        numbered = path.with_name(f"{path.name}{suffix}.{index}")
        if not numbered.exists():
            return numbered
        index += 1
