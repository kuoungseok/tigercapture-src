from __future__ import annotations

from app.actions.registry import ActionRegistry
from app.motion_designer.trend_capability_audit import (
    TREND_CAPABILITY_AUDIT_SCHEMA,
    audit_trend_capabilities,
)


class Owner:
    pass


def test_trend_capability_audit_verifies_registered_actions_and_evidence() -> None:
    registry = ActionRegistry(Owner())
    action_ids = {row["id"] for row in registry.list_actions()}

    report = audit_trend_capabilities(
        registered_action_ids=action_ids,
        repository_root=".",
    )

    assert report["schema"] == TREND_CAPABILITY_AUDIT_SCHEMA
    assert report["ok"] is True
    assert report["summary"] == {
        "trend_count": 10,
        "supported_v1": 8,
        "limited_v1": 2,
        "unavailable": 0,
    }
    assert report["missing_actions"] == []
    assert report["missing_evidence"] == []
    assert all(
        row["action_registration"] == "verified"
        and row["evidence_files"] == "verified"
        for row in report["trends"]
    )


def test_trend_capability_action_is_non_mutating_and_discloses_limits() -> None:
    registry = ActionRegistry(Owner())

    result = registry.execute("motion.trend.capabilities.inspect", {})

    assert result.ok
    assert result.changed is False
    assert result.result["summary"]["trend_count"] == 10
    limited = {
        row["id"]: row["limitations"]
        for row in result.result["trends"]
        if row["status"] == "limited_v1"
    }
    assert set(limited) == {
        "hybrid_2d_3d_painterly",
        "stop_motion_cgi",
    }
    assert result.result["new_milestones_required"] == []


def test_trend_capability_audit_fails_closed_for_missing_registration() -> None:
    report = audit_trend_capabilities(
        registered_action_ids=(),
        repository_root=".",
    )

    assert report["ok"] is False
    assert "motion.ai.style.plan" in report["missing_actions"]
    assert all(
        row["action_registration"] == "missing"
        for row in report["trends"]
    )
