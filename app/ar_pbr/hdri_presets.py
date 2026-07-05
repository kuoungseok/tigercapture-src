"""HDRI preset discovery for AR/PBR model preview lighting."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESOURCE_ROOT = PROJECT_ROOT / "resources" / "ar_pbr"
MANIFEST_PATH = RESOURCE_ROOT / "manifest.json"
HDRI_DIR = RESOURCE_ROOT / "hdri"


@dataclass(frozen=True)
class HdriPreset:
    id: str
    label: str
    path: Path
    source_url: str = ""
    license: str = "CC0"
    purpose: str = ""

    @property
    def available(self) -> bool:
        return self.path.exists()

    def to_combo_label(self) -> str:
        suffix = "" if self.available else " (missing)"
        return f"{self.label}{suffix}"


_FALLBACK_IDS = (
    "wide_street_01",
    "studio_small_09",
    "wooden_studio_17",
    "abandoned_parking",
    "cayley_interior",
    "autumn_forest_01",
    "belfast_sunset",
    "cobblestone_street_night",
    "brown_photostudio_03",
)


def _label_from_id(value: str) -> str:
    return str(value or "HDRI").replace("_", " ").title()


def _resolve_path(value: Any) -> Path:
    path = Path(str(value or ""))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _preset_from_manifest_row(row: Mapping[str, Any]) -> HdriPreset | None:
    preset_id = str(row.get("id") or "").strip()
    path_value = row.get("path")
    if not preset_id or not path_value:
        return None
    return HdriPreset(
        id=preset_id,
        label=str(row.get("label") or _label_from_id(preset_id)),
        path=_resolve_path(path_value),
        source_url=str(row.get("source_url") or ""),
        license=str(row.get("license") or "CC0"),
        purpose=str(row.get("purpose") or ""),
    )


def hdri_presets() -> list[HdriPreset]:
    rows: list[HdriPreset] = []
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        for item in data.get("hdri", []) or []:
            if isinstance(item, Mapping):
                preset = _preset_from_manifest_row(item)
                if preset is not None:
                    rows.append(preset)
    except Exception:
        rows = []
    seen = {row.id for row in rows}
    for preset_id in _FALLBACK_IDS:
        if preset_id in seen:
            continue
        rows.append(HdriPreset(
            id=preset_id,
            label=_label_from_id(preset_id),
            path=HDRI_DIR / f"{preset_id}_1k.hdr",
            source_url=f"https://polyhaven.com/a/{preset_id}",
        ))
    return rows


def default_hdri_preset() -> HdriPreset | None:
    rows = hdri_presets()
    for preferred in ("wide_street_01", "studio_small_09"):
        for row in rows:
            if row.id == preferred and row.available:
                return row
    return next((row for row in rows if row.available), rows[0] if rows else None)


def default_hdri_path() -> Path:
    preset = default_hdri_preset()
    return preset.path if preset is not None else HDRI_DIR / "wide_street_01_1k.hdr"


def resolve_hdri_preset(value: str | None) -> HdriPreset | None:
    key = str(value or "").strip()
    if not key:
        return default_hdri_preset()
    for row in hdri_presets():
        if row.id == key or str(row.path) == key:
            return row
    raw_path = _resolve_path(key)
    if raw_path.exists():
        return HdriPreset(id=raw_path.stem, label=_label_from_id(raw_path.stem), path=raw_path)
    return default_hdri_preset()
