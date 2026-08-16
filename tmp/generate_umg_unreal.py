"""Generate the packaged Auto Layout frame into a real Unreal project."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.unreal_umg_workflow import preflight_umg_project, run_unreal_umg_generation

PROJECT = ROOT / "debugCapture" / "component_schema18_buildcheck" / "HostProject" / "HostProject.uproject"
DOCUMENT = ROOT / "debugCapture" / "umg_auto_layout_package" / "tiger_umg_document.json"

start = time.monotonic()
def step(message: str) -> None:
    print(f"[{time.monotonic() - start:7.1f}s] {message}", flush=True)

step("project preflight")
pre = preflight_umg_project(PROJECT)
step(json.dumps({k: pre[k] for k in ("ok", "engine_root", "blockers")}, ensure_ascii=False))
if not pre["ok"]:
    raise SystemExit(1)

step("running UnrealEditor-Cmd generation")
report = run_unreal_umg_generation(
    PROJECT,
    DOCUMENT,
    destination_root="/Game/TigerStudio/AutoLayout",
    timeout_seconds=1800,
)
step("generation finished")
print(json.dumps(report, ensure_ascii=False, indent=2)[:4000], flush=True)
