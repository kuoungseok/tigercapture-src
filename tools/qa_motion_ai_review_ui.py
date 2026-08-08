"""Render real Motion Designer AI candidate and revision review UI evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.motion_designer.ai_generation import (
    generate_motion_ai_candidates,
    generate_motion_ai_patch,
)
from app.motion_designer.ai_patch_diff import build_motion_ai_patch_diff
from app.motion_designer.ai_workspace import apply_motion_ai_proposal
from app.motion_designer.candidate_preview import render_candidate_preview_set
from app.motion_designer.schema import MotionComposition
from app.motion_designer.ui.window import MotionDesignerWindow


OUTPUT = ROOT / "debugCapture" / "motion_designer" / "ai_review_ui"


def main() -> int:
    app = QApplication.instance() or QApplication([])
    base = MotionComposition(
        name="AI Review UI",
        width=1280,
        height=720,
        duration_ms=5000,
    )
    candidates = [
        item.to_dict()
        for item in generate_motion_ai_candidates(
            base,
            'dynamic fade "NIGHT SHIFT"',
            [],
            provider_id="rule_based",
        )
    ]
    preview = render_candidate_preview_set(
        base,
        candidates,
        cache_root=OUTPUT / "cache",
    )
    window = MotionDesignerWindow(base)
    window.resize(1520, 900)
    window.show()
    window.ai_dock.show()
    window.ai.set_candidate_set({
        "schema": "tigerstudio.motion.ai.candidate_set.v1",
        "selected_index": 1,
        "candidates": candidates,
    })
    window.ai.set_candidate_previews(preview)
    applied = apply_motion_ai_proposal(base, candidates[1])
    added_ids = [item.id for item in applied.layers]
    window.controller.replace(applied)
    window.ai.set_applied(len(added_ids), added_ids)
    patch = generate_motion_ai_patch(
        applied,
        'make it bigger and fade "NIGHT SHIFT / AFTER DARK"',
        added_ids,
        provider_id="rule_based",
    )
    diff = build_motion_ai_patch_diff(applied, patch)
    window.ai.set_patch({"patch": patch, "diff": diff})
    app.processEvents()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    screenshot = OUTPUT / "motion_ai_candidate_patch_review.png"
    window.grab().save(str(screenshot), "PNG")
    report = {
        "ok": screenshot.is_file() and screenshot.stat().st_size > 0,
        "screenshot": str(screenshot.resolve()),
        "candidate_count": len(candidates),
        "preview_count": len(preview["previews"]),
        "patch_operation_count": diff["operation_count"],
        "patch_affected_layer_count": diff["affected_layer_count"],
    }
    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    window.close()
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
