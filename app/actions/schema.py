"""Action schema declarations for the Tiger Studio Python Action System."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


ACTION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ActionSpec:
    id: str
    title: str
    namespace: str
    params_schema: Mapping[str, Any] = field(default_factory=dict)
    result_schema: Mapping[str, Any] = field(default_factory=dict)
    mutating: bool = False
    destructive: bool = False
    requires_owner: bool = False
    requires_review: bool = False
    supports_dry_run: bool = True
    undo_label: str = ""
    async_kind: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ACTION_SCHEMA_VERSION,
            "id": self.id,
            "title": self.title,
            "namespace": self.namespace,
            "params_schema": dict(self.params_schema or {}),
            "result_schema": dict(self.result_schema or {}),
            "mutating": bool(self.mutating),
            "mutates": bool(self.mutating),
            "destructive": bool(self.destructive),
            "requires_owner": bool(self.requires_owner),
            "requires_review": bool(self.requires_review),
            "supports_dry_run": bool(self.supports_dry_run),
            "undo_label": self.undo_label,
            "async_kind": self.async_kind,
        }


def namespace_from_action_id(action_id: str) -> str:
    text = str(action_id or "").strip()
    return text.split(".", 1)[0] if "." in text else text


def schema_object(
    properties: Mapping[str, Any] | None = None,
    *,
    required: list[str] | tuple[str, ...] = (),
    additional_properties: bool = False,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties or {}),
        "required": list(required or ()),
        "additionalProperties": bool(additional_properties),
    }
