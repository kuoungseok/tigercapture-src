"""Package a Painter template and generate it into the real Unreal project."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

QApplication([])

from app.painter_ui_templates import instantiate_ui_template
from app.painter_ui_umg_adapter import package_painter_umg
from app.unreal_umg_workflow import run_unreal_umg_generation

TEMPLATE = sys.argv[1] if len(sys.argv) > 1 else "game_hud"
PROJECT = (
    ROOT / "debugCapture" / "component_schema18_buildcheck" / "HostProject"
    / "HostProject.uproject"
)
OUT = ROOT / "debugCapture" / f"umg_{TEMPLATE}_package"

start = time.monotonic()
def step(message: str) -> None:
    print(f"[{time.monotonic() - start:7.1f}s] {message}", flush=True)

document, report = instantiate_ui_template(TEMPLATE)
step(f"template {TEMPLATE!r}: {len(document['objects'])} objects")

package = package_painter_umg(document, OUT)
pf = package["packaged_preflight"]
step(f"packaged ok={package['ok']} counts={pf['counts']} blockers={len(pf['blockers'])}")

result = run_unreal_umg_generation(
    PROJECT,
    package["document_path"],
    destination_root=f"/Game/TigerStudio/{TEMPLATE}",
    timeout_seconds=1800,
)
step(f"generation ok={result.get('ok')}")
print(json.dumps({
    k: result.get(k) for k in (
        "ok", "message", "generated_asset_path", "generated_asset_loaded",
        "generated_asset_class", "generated_widget_count",
        "generated_component_count", "errors", "warnings",
    )
}, ensure_ascii=False, indent=2)[:3000], flush=True)
