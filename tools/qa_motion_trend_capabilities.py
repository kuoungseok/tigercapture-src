"""Write machine-readable evidence for the 2026 Motion trend capability audit."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.actions.registry import ActionRegistry
from app.motion_designer.trend_capability_audit import audit_trend_capabilities


class Owner:
    pass


def main() -> int:
    registry = ActionRegistry(Owner())
    report = audit_trend_capabilities(
        registered_action_ids={
            row["id"] for row in registry.list_actions()
        },
        repository_root=ROOT,
    )
    output_dir = ROOT / "debugCapture" / "motion_trend_capability_audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "report.json"
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({
        "ok": report["ok"],
        "summary": report["summary"],
        "missing_actions": report["missing_actions"],
        "missing_evidence": report["missing_evidence"],
        "output": str(output_path),
    }, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
