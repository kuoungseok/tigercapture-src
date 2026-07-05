"""Write the read-only VSeeFace sidecar settings workflow report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vseeface_bridge import (  # noqa: E402
    VSeeFaceBridgeConfig,
    build_vseeface_sidecar_workflow,
    default_vseeface_bridge_config,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a read-only VSeeFace sidecar workflow JSON report.")
    parser.add_argument("--config", default="", help="Optional bridge config JSON.")
    parser.add_argument("--settings", default="", help="Optional VSeeFace settings.ini path.")
    parser.add_argument("--report-out", default="debugCapture\\vseeface_sidecar_config_report.json")
    parser.add_argument("--confirm", action="store_true", help="Mark user confirmation as present for workflow evaluation only.")
    parser.add_argument("--allow-admin", action="store_true", help="Mark administrator approval as present for workflow evaluation only.")
    parser.add_argument("--out", default="", help="Optional workflow output JSON path.")
    args = parser.parse_args(argv)

    config = _load_config(args.config)
    workflow = build_vseeface_sidecar_workflow(
        config,
        settings_path=str(args.settings or "") or None,
        out_path=str(args.report_out or "") or "debugCapture\\vseeface_sidecar_config_report.json",
        confirm=bool(args.confirm),
        allow_admin=bool(args.allow_admin),
    )
    text = json.dumps(workflow, ensure_ascii=False, indent=2, default=str)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(json.dumps({
            "ok": workflow["ok"],
            "state": workflow["state"],
            "read_only": workflow["read_only"],
            "out": str(out),
        }, ensure_ascii=False))
    else:
        print(text)
    return 0 if workflow["ok"] else 2


def _load_config(path_text: str) -> VSeeFaceBridgeConfig:
    if not path_text:
        return default_vseeface_bridge_config(ROOT)
    path = Path(path_text)
    return VSeeFaceBridgeConfig.from_mapping(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    raise SystemExit(main())
