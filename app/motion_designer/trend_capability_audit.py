"""Evidence-bound capability audit for the 2026 Motion trend roadmap."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any


TREND_CAPABILITY_AUDIT_SCHEMA = "tigerstudio.motion.trend_capability_audit.v1"

_ROWS: tuple[dict[str, Any], ...] = (
    {
        "id": "ai_hybrid_workflow",
        "name": "AI hybrid workflow",
        "status": "supported_v1",
        "contracts": [
            "tigerstudio.motion.ai_semantic_style_direction.v1",
            "tigerstudio.motion.ai_platform_copy_plan.v1",
        ],
        "actions": [
            "motion.ai.style.plan",
            "motion.ai.story.plan",
            "motion.ai.platform_copy.plan",
        ],
        "evidence_tools": [
            "tools/qa_motion_style_director.py",
            "tools/qa_motion_platform_copy_ui.py",
        ],
        "limitations": [
            "Provider output remains a reviewable proposal and requires explicit human approval."
        ],
    },
    {
        "id": "authentic_imperfection",
        "name": "Authentic imperfection",
        "status": "supported_v1",
        "contracts": ["tigerstudio.motion.craft_style.v1"],
        "actions": [
            "motion.craft.apply",
            "motion.craft.seed.lock",
            "motion.craft.preflight",
        ],
        "evidence_tools": ["tools/qa_motion_craft_style.py"],
        "limitations": [],
    },
    {
        "id": "craft_as_luxury",
        "name": "Craft as luxury",
        "status": "supported_v1",
        "contracts": [
            "tigerstudio.motion.craft_style.v1",
            "tigerstudio.motion.collage.v1",
        ],
        "actions": [
            "motion.craft.texture.attach",
            "motion.collage.asset.catalog",
            "motion.collage.create",
        ],
        "evidence_tools": [
            "tools/qa_motion_craft_style.py",
            "tools/qa_motion_collage_asset_pack.py",
        ],
        "limitations": [],
    },
    {
        "id": "hybrid_2d_3d_painterly",
        "name": "Hybrid 2D and painterly 3D",
        "status": "limited_v1",
        "contracts": ["tigerstudio.motion.painterly_look.v1"],
        "actions": [
            "motion.lookdev.set",
            "motion.lookdev.texture.project",
            "motion.lookdev.preflight",
        ],
        "evidence_tools": [
            "tools/qa_motion_painterly_look.py",
            "tools/qa_motion_painterly_ui.py",
        ],
        "limitations": [
            "Per-material painterly overrides require a material-ID pass that is not implemented."
        ],
    },
    {
        "id": "liquid_glass",
        "name": "Liquid glass and glossy motion",
        "status": "supported_v1",
        "contracts": ["tigerstudio.motion.glass_material.v1"],
        "actions": [
            "motion.material.glass.create",
            "motion.material.glass.driver.bind",
            "motion.material.glass.preflight",
        ],
        "evidence_tools": ["tools/qa_motion_glass.py"],
        "limitations": [
            "This is Tiger Glass, not a claim of pixel-identical Apple rendering."
        ],
    },
    {
        "id": "kinetic_typography",
        "name": "Expressive kinetic typography",
        "status": "supported_v1",
        "contracts": ["tigerstudio.motion.typography.v1"],
        "actions": [
            "motion.typography.style.set",
            "motion.typography.animation.set",
            "motion.typography.preflight",
        ],
        "evidence_tools": ["tools/qa_motion_gpu_typography.py"],
        "limitations": [],
    },
    {
        "id": "mixed_media_collage",
        "name": "Mixed media and collage",
        "status": "supported_v1",
        "contracts": ["tigerstudio.motion.collage.v1"],
        "actions": [
            "motion.collage.item.add",
            "motion.collage.edge.set",
            "motion.collage.preflight",
        ],
        "evidence_tools": ["tools/qa_motion_collage.py"],
        "limitations": [],
    },
    {
        "id": "stop_motion_cgi",
        "name": "Stop-motion inspired CGI",
        "status": "limited_v1",
        "contracts": ["tigerstudio.motion.stop_motion.v1"],
        "actions": [
            "motion.stop_motion.set",
            "motion.stop_motion.pose.capture",
            "motion.stop_motion.preflight",
        ],
        "evidence_tools": ["tools/qa_motion_stop_motion.py"],
        "limitations": [
            "Physical clay deformation, volumetric miniature lighting, and automatic frame sculpting are not implemented."
        ],
    },
    {
        "id": "story_led_brand_film",
        "name": "Story-led brand film",
        "status": "supported_v1",
        "contracts": [
            "tigerstudio.motion.story.v1",
            "tigerstudio.motion.ai_platform_copy_plan.v1",
        ],
        "actions": [
            "motion.story.beat.add",
            "motion.story.audio.bind",
            "motion.ai.story.plan",
        ],
        "evidence_tools": [
            "tools/qa_motion_story_platform.py",
            "tools/qa_motion_story_audio_ui.py",
        ],
        "limitations": [],
    },
    {
        "id": "platform_character_realtime",
        "name": "Character, platform-aware, and realtime graphics",
        "status": "supported_v1",
        "contracts": ["tigerstudio.motion.platform_variant_plan.v1"],
        "actions": [
            "motion.actor.update",
            "motion.platform.variant.plan",
            "motion.template.trend.preflight",
        ],
        "evidence_tools": ["tools/qa_motion_story_platform.py"],
        "limitations": [
            "Platform variants remain reviewable derivatives rather than autonomous publishing."
        ],
    },
)


def audit_trend_capabilities(
    *,
    registered_action_ids: Iterable[str] | None = None,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    known_actions = (
        {str(item) for item in registered_action_ids}
        if registered_action_ids is not None
        else None
    )
    root = Path(repository_root) if repository_root is not None else None
    rows: list[dict[str, Any]] = []
    missing_actions: list[str] = []
    missing_evidence: list[str] = []
    for source in _ROWS:
        row = {
            key: list(value) if isinstance(value, list) else value
            for key, value in source.items()
        }
        if known_actions is None:
            row["action_registration"] = "declared"
        else:
            row_missing_actions = [
                action_id
                for action_id in row["actions"]
                if action_id not in known_actions
            ]
            row["action_registration"] = (
                "verified" if not row_missing_actions else "missing"
            )
            row["missing_actions"] = row_missing_actions
            missing_actions.extend(row_missing_actions)
        if root is None:
            row["evidence_files"] = "declared"
        else:
            row_missing_evidence = [
                relative
                for relative in row["evidence_tools"]
                if not (root / relative).is_file()
            ]
            row["evidence_files"] = (
                "verified" if not row_missing_evidence else "missing"
            )
            row["missing_evidence"] = row_missing_evidence
            missing_evidence.extend(row_missing_evidence)
        rows.append(row)

    supported = sum(row["status"] == "supported_v1" for row in rows)
    limited = sum(row["status"] == "limited_v1" for row in rows)
    return {
        "schema": TREND_CAPABILITY_AUDIT_SCHEMA,
        "ok": not missing_actions and not missing_evidence,
        "summary": {
            "trend_count": len(rows),
            "supported_v1": supported,
            "limited_v1": limited,
            "unavailable": len(rows) - supported - limited,
        },
        "trends": rows,
        "missing_actions": sorted(set(missing_actions)),
        "missing_evidence": sorted(set(missing_evidence)),
        "new_milestones_required": [],
        "existing_follow_up_scopes": [
            "M24 material-ID painterly overrides",
            "M25 physical clay deformation and miniature volumetric lighting",
        ],
        "claim_boundary": (
            "supported_v1 means the editable contract, registered action surface, "
            "and named QA path exist; limited_v1 must retain its limitations."
        ),
    }


__all__ = ["TREND_CAPABILITY_AUDIT_SCHEMA", "audit_trend_capabilities"]
