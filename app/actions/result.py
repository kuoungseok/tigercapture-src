"""Result objects for the Tiger Studio Python Action System."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    action: str
    result: Mapping[str, Any] = field(default_factory=dict)
    error: str = ""
    warnings: Sequence[str] = field(default_factory=tuple)
    dry_run: bool = False
    preview: bool = False
    changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "action": str(self.action or ""),
            "result": dict(self.result or {}),
            "error": str(self.error or ""),
            "warnings": list(self.warnings or ()),
            "dry_run": bool(self.dry_run),
            "preview": bool(self.preview),
            "changed": bool(self.changed),
        }


def ok_result(
    action: str,
    result: Mapping[str, Any] | None = None,
    *,
    warnings: Sequence[str] = (),
    dry_run: bool = False,
    preview: bool = False,
    changed: bool = False,
) -> ActionResult:
    return ActionResult(
        True,
        action,
        dict(result or {}),
        warnings=tuple(warnings or ()),
        dry_run=bool(dry_run),
        preview=bool(preview),
        changed=bool(changed),
    )


def error_result(
    action: str,
    error: str,
    *,
    result: Mapping[str, Any] | None = None,
    warnings: Sequence[str] = (),
    dry_run: bool = False,
    preview: bool = False,
    changed: bool = False,
) -> ActionResult:
    return ActionResult(
        False,
        action,
        dict(result or {}),
        error=str(error or "action_failed"),
        warnings=tuple(warnings or ()),
        dry_run=bool(dry_run),
        preview=bool(preview),
        changed=bool(changed),
    )
