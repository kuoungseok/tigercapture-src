"""Refresh readiness artifacts after broadcast evidence changes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def refresh_broadcast_evidence_readiness_artifacts(
    root: str | Path = ".",
    *,
    broadcast_out: str | Path = "debugCapture/broadcast_release_readiness_qa.json",
    final_out: str | Path = "debugCapture/final_product_readiness_qa.json",
) -> dict[str, Any]:
    """Regenerate broadcast and final-readiness artifacts after evidence updates."""
    root_path = Path(root).resolve()
    broadcast_path = root_path / Path(broadcast_out)
    final_path = root_path / Path(final_out)

    from app.broadcast_release_readiness import build_broadcast_release_readiness_report
    from app.final_product_readiness import build_final_product_readiness_report

    broadcast_report = build_broadcast_release_readiness_report(root_path)
    final_report = build_final_product_readiness_report(root_path)

    broadcast_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    broadcast_path.write_text(json.dumps(broadcast_report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    final_path.write_text(json.dumps(final_report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    return {
        "schema": "tigerstudio.broadcast.evidence_readiness_refresh.v1",
        "ok": True,
        "broadcast_artifact": str(broadcast_path),
        "final_artifact": str(final_path),
        "broadcast_commercial_ready": bool(broadcast_report.get("commercial_ready")),
        "broadcast_sale_ready": bool(broadcast_report.get("sale_ready")),
        "final_release_ready": bool(final_report.get("release_ready")),
        "final_commercial_claims_ready": bool(final_report.get("commercial_claims_ready")),
        "broadcast_score": int(broadcast_report.get("score", 0) or 0),
        "final_score": int(final_report.get("score", 0) or 0),
        "broadcast_next_actions": list(broadcast_report.get("next_actions") or [])[:8],
        "final_next_actions": list(final_report.get("next_actions") or [])[:8],
    }
