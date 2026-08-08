"""Registry-to-UI surface coverage audit for Painter UI Design."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


SCHEMA = "tigerstudio.painter.ui.action_parity.v1"

# Longest/specific prefixes are evaluated first. Each family identifies the
# contextual UI surface that owns discovery; it does not imply that every
# low-level automation action needs its own visible button.
_FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "id": "productivity",
        "label": "Productivity",
        "surface": "UI menu / Quick Actions",
        "prefixes": (
            "paint.ui.find_replace.",
            "paint.ui.batch_rename.",
            "paint.ui.shortcut.",
            "paint.ui.action_parity.",
            "paint.ui.locale_audit.",
            "paint.ui.focus_audit.",
            "paint.ui.release_corpus.",
            "paint.ui.performance_budget.",
            "paint.ui.runtime_performance.",
            "paint.ui.recovery.",
            "paint.ui.selection.similar.",
        ),
        "required": (
            "paint.ui.find_replace.inspect",
            "paint.ui.find_replace.apply",
            "paint.ui.batch_rename.inspect",
            "paint.ui.batch_rename.apply",
            "paint.ui.shortcut.inspect",
        ),
    },
    {
        "id": "shell",
        "label": "Workspace and view",
        "surface": "Canvas shell / panel controls / zoom menu",
        "prefixes": (
            "paint.ui.document.",
            "paint.ui.workspace.",
            "paint.ui.inspector.",
            "paint.ui.navigator.",
            "paint.ui.view.",
            "paint.ui.quick_action.",
        ),
        "required": ("paint.ui.document.inspect", "paint.ui.view.fit"),
    },
    {
        "id": "resources",
        "label": "Templates and assets",
        "surface": "Resources / Assets",
        "prefixes": (
            "paint.ui.template.",
            "paint.ui.library.",
            "paint.ui.component.library.",
            "paint.ui.token.library.",
            "paint.ui.image.",
        ),
        "required": (
            "paint.ui.template.catalog.inspect",
            "paint.ui.template.apply",
        ),
    },
    {
        "id": "pages",
        "label": "Pages, artboards, rulers and guides",
        "surface": "Navigator / View options / Artboard inspector",
        "prefixes": (
            "paint.ui.page.",
            "paint.ui.artboard.",
            "paint.ui.layout_grid.",
            "paint.ui.guide.",
            "paint.ui.ruler.",
            "paint.ui.section.",
        ),
        "required": (
            "paint.ui.artboard.add",
            "paint.ui.artboard.remove",
            "paint.ui.guide.create",
        ),
    },
    {
        "id": "objects",
        "label": "Objects and selection",
        "surface": "Canvas / Layers / contextual Design",
        "prefixes": (
            "paint.ui.object.",
            "paint.ui.selection.",
            "paint.ui.property.",
            "paint.ui.clip.",
            "paint.ui.mask.",
            "paint.ui.smart_guide.",
        ),
        "required": (
            "paint.ui.object.add",
            "paint.ui.object.update",
            "paint.ui.object.remove",
        ),
    },
    {
        "id": "vector",
        "label": "Vector editing",
        "surface": "Canvas vector mode / contextual toolbar",
        "prefixes": ("paint.ui.vector.",),
        "required": ("paint.ui.vector.node.add",),
    },
    {
        "id": "appearance",
        "label": "Appearance and effects",
        "surface": "Design > Appearance",
        "prefixes": ("paint.ui.appearance.",),
        "required": ("paint.ui.appearance.inspect",),
    },
    {
        "id": "typography",
        "label": "Typography",
        "surface": "Design > Typography / inline text editor",
        "prefixes": ("paint.ui.text.", "paint.ui.typography."),
        "required": ("paint.ui.text.content.set",),
    },
    {
        "id": "responsive",
        "label": "Layout and responsive design",
        "surface": "Design > Layout / responsive preview",
        "prefixes": (
            "paint.ui.layout.",
            "paint.ui.responsive.",
            "paint.ui.theme.",
        ),
        "required": ("paint.ui.layout.set",),
    },
    {
        "id": "design_system",
        "label": "Components, variables and styles",
        "surface": "Assets / Design component and token sections",
        "prefixes": (
            "paint.ui.component.",
            "paint.ui.token.",
            "paint.ui.style.",
            "paint.ui.variable.",
        ),
        "required": (
            "paint.ui.component.create",
            "paint.ui.component.instantiate",
            "paint.ui.token.add",
        ),
    },
    {
        "id": "prototype",
        "label": "Prototype",
        "surface": "Prototype tab / canvas connections",
        "prefixes": ("paint.ui.interaction.", "paint.ui.prototype."),
        "required": ("paint.ui.interaction.add",),
    },
    {
        "id": "motion",
        "label": "Motion",
        "surface": "Prototype > Motion / Motion dialogs",
        "prefixes": ("paint.ui.motion.", "paint.ui.motion_actor."),
        "required": ("paint.ui.motion.open", "paint.ui.motion.inspect"),
    },
    {
        "id": "delivery",
        "label": "Delivery and Unreal UMG",
        "surface": "Inspect > Delivery / Export",
        "prefixes": (
            "paint.ui.delivery.",
            "paint.ui.handoff.",
            "paint.ui.assets.",
            "paint.ui.umg.",
            "paint.ui.advanced_delivery.",
            "paint.ui.web.",
            "paint.ui.ppt.",
            "paint.ui.convert.",
        ),
        "required": (
            "paint.ui.delivery.preflight",
            "paint.ui.advanced_delivery.inspect",
            "paint.ui.web.preflight",
            "paint.ui.web.package",
            "paint.ui.ppt.inspect",
            "paint.ui.ppt.send",
            "paint.ui.convert.to_paint",
            "paint.ui.convert.to_vector",
        ),
    },
    {
        "id": "dev_review",
        "label": "Developer handoff and review",
        "surface": "Inspect / Review Prototype",
        "prefixes": (
            "paint.ui.review.",
            "paint.ui.developer.",
            "paint.ui.dev.",
        ),
        "required": ("paint.ui.developer.inspect",),
    },
    {
        "id": "exchange_ai",
        "label": "Figma exchange and AI",
        "surface": "File exchange / AI Design",
        "prefixes": ("paint.ui.figma.", "paint.ui.ai."),
        "required": (
            "paint.ui.figma.import",
            "paint.ui.figma.export",
            "paint.ui.ai.plan",
            "paint.ui.ai.prototype.plan",
        ),
    },
)


def inspect_painter_ui_action_parity(
    actions: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Classify the live Registry and report missing or orphan candidates."""

    action_rows = [
        dict(row)
        for row in actions
        if str(row.get("id") or "").startswith("paint.ui.")
    ]
    action_ids = {str(row["id"]) for row in action_rows}
    assigned: set[str] = set()
    families: list[dict[str, Any]] = []
    missing_all: list[str] = []
    for family in _FAMILIES:
        matched = sorted(
            action_id
            for action_id in action_ids
            if any(
                action_id.startswith(prefix)
                for prefix in family["prefixes"]
            )
        )
        assigned.update(matched)
        missing = sorted(set(family["required"]) - action_ids)
        missing_all.extend(missing)
        families.append(
            {
                "id": family["id"],
                "label": family["label"],
                "surface": family["surface"],
                "action_count": len(matched),
                "missing_count": len(missing),
                "missing_action_ids": missing,
                "status": "missing" if missing else "covered",
            }
        )
    orphan_candidates = sorted(action_ids - assigned)
    return {
        "schema": SCHEMA,
        "status": (
            "blocked"
            if missing_all
            else "review"
            if orphan_candidates
            else "covered"
        ),
        "action_count": len(action_rows),
        "family_count": len(families),
        "covered_family_count": sum(
            1 for row in families if row["status"] == "covered"
        ),
        "missing_action_ids": sorted(set(missing_all)),
        "orphan_candidate_ids": orphan_candidates,
        "families": families,
    }


__all__ = ["SCHEMA", "inspect_painter_ui_action_parity"]
