"""Local reference roots for Unreal Engine Link development.

These paths are intentionally references only. Do not copy or vendor these
external directories into the Tiger Studio repository.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


UASSET_INSPECTOR_ENV = "TIGERSTUDIO_UASSET_INSPECTOR_ROOT"
UE_ENGINE_ENV = "TIGERSTUDIO_UE_ENGINE_ROOT"

DEFAULT_UASSET_INSPECTOR_ROOT = Path("D:/Pupg_workspace/ToolsStandalone/UAssetInspector")
DEFAULT_UE_ENGINE_ROOT = Path("D:/UE_5.8")


@dataclass(frozen=True)
class UnrealLinkReferenceRoot:
    key: str
    label: str
    path: Path
    required_children: tuple[str, ...] = ()

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def missing_children(self) -> list[str]:
        return [child for child in self.required_children if not (self.path / child).exists()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "path": self.path.as_posix(),
            "exists": self.exists,
            "required_children": list(self.required_children),
            "missing_children": self.missing_children,
        }


def _configured_path(env_name: str, default: Path) -> Path:
    value = os.environ.get(env_name, "").strip()
    if value:
        return Path(value)
    return default


def unreal_link_reference_roots() -> dict[str, UnrealLinkReferenceRoot]:
    uasset_root = _configured_path(UASSET_INSPECTOR_ENV, DEFAULT_UASSET_INSPECTOR_ROOT)
    ue_root = _configured_path(UE_ENGINE_ENV, DEFAULT_UE_ENGINE_ROOT)
    return {
        "uasset_inspector": UnrealLinkReferenceRoot(
            key="uasset_inspector",
            label="UAssetInspector reference source/tool",
            path=uasset_root,
            required_children=(
                "UAssetInspector.sln",
                "src/UAssetInspector.App",
                "src/UAssetInspector.Core",
                "src/UAssetInspector.Rendering",
            ),
        ),
        "ue_58": UnrealLinkReferenceRoot(
            key="ue_58",
            label="Unreal Engine 5.8 reference install",
            path=ue_root,
            required_children=(
                "Engine",
                "Engine/Binaries/Win64/UnrealEditor.exe",
            ),
        ),
    }


def unreal_link_reference_report() -> dict[str, Any]:
    roots = unreal_link_reference_roots()
    return {
        "note": (
            "Use these as local read-only references for Unreal Engine Link "
            "development. Do not copy the external tool or engine into this repo."
        ),
        "env_overrides": {
            "uasset_inspector": UASSET_INSPECTOR_ENV,
            "ue_58": UE_ENGINE_ENV,
        },
        "roots": {key: root.to_dict() for key, root in roots.items()},
    }


def format_unreal_link_reference_report() -> str:
    report = unreal_link_reference_report()
    lines = [str(report["note"]), "", "Reference roots:"]
    for root in report["roots"].values():
        status = "found" if root["exists"] and not root["missing_children"] else "missing/incomplete"
        lines.append(f"- {root['label']}: {root['path']} ({status})")
        if root["missing_children"]:
            lines.append(f"  missing: {', '.join(root['missing_children'])}")
    lines.extend([
        "",
        "Env overrides:",
        f"- {UASSET_INSPECTOR_ENV}",
        f"- {UE_ENGINE_ENV}",
    ])
    return "\n".join(lines)


__all__ = [
    "DEFAULT_UASSET_INSPECTOR_ROOT",
    "DEFAULT_UE_ENGINE_ROOT",
    "UASSET_INSPECTOR_ENV",
    "UE_ENGINE_ENV",
    "UnrealLinkReferenceRoot",
    "format_unreal_link_reference_report",
    "unreal_link_reference_report",
    "unreal_link_reference_roots",
]
