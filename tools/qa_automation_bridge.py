"""QA report for the JSON automation bridge."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _BridgeOwner:
    def __init__(self) -> None:
        from app.timeline_model import VideoClip, VideoTrack

        self._tracks = [
            VideoTrack(
                id=1,
                clips=[
                    VideoClip(
                        id=10,
                        source_duration_ms=8000,
                        timeline_in_ms=0,
                        source_in_ms=0,
                        source_out_ms=8000,
                    )
                ],
            )
        ]
        self._audio_tracks = []
        self._timeline_markers: list[dict[str, Any]] = []
        self._selected_clips = [(1, 10)]
        self._project_settings = {}
        self.marker_sync_count = 0
        self.change_count = 0

    def _sync_markers_to_ruler(self) -> None:
        self.marker_sync_count += 1

    def _register_change(self, label: str = "") -> None:
        self.change_count += 1


def build_automation_bridge_report() -> dict[str, Any]:
    from io import StringIO

    from app.automation_bridge import AutomationBridge

    owner = _BridgeOwner()
    bridge = AutomationBridge(owner)
    ping = bridge.handle_request({"id": "ping", "method": "automation.ping"})
    schema = bridge.handle_request({"id": "schema", "method": "automation.schema"})
    commands = bridge.handle_request({"id": "commands", "method": "automation.list_commands"})
    status = bridge.handle_request(
        {"id": "status", "method": "automation.execute", "params": {"command": "get_app_status"}}
    )
    rejected = bridge.handle_request(
        {"id": "bad", "method": "automation.execute", "params": {"command": "shell"}}
    )
    dry = bridge.handle_request(
        {
            "id": "dry",
            "method": "automation.execute",
            "params": {"command": "add_marker", "params": {"ms": 500, "label": "Dry"}, "dry_run": True},
        }
    )
    marker_before_apply = len(owner._timeline_markers)
    marker = bridge.handle_request(
        {
            "id": "marker",
            "method": "automation.execute",
            "params": {"command": "add_marker", "params": {"ms": 1200, "label": "Bridge QA"}},
        }
    )
    src = StringIO('{"id":"one","method":"automation.ping"}\n{"id":"two","method":"automation.list_commands"}\n')
    dst = StringIO()
    jsonl_code = bridge.serve_json_lines(src, dst)
    invalid = bridge.handle_json("{")

    command_names = {row.get("name") for row in commands.get("result", {}).get("commands", [])}
    checks = {
        "ping": ping.get("ok") is True and ping.get("result", {}).get("pong") is True,
        "schema_safe": schema.get("result", {}).get("security", {}).get("arbitrary_python") is False
        and schema.get("result", {}).get("security", {}).get("registered_commands_only") is True,
        "lists_commands": {"get_app_status", "add_marker"} <= command_names,
        "status_exec": status.get("result", {}).get("ok") is True
        and status.get("result", {}).get("result", {}).get("automation", {}).get("arbitrary_shell") is False,
        "rejects_unknown": rejected.get("result", {}).get("ok") is False
        and "unknown command" in rejected.get("result", {}).get("error", ""),
        "dry_run_no_mutation": dry.get("result", {}).get("dry_run") is True and marker_before_apply == 0,
        "marker_apply": marker.get("result", {}).get("ok") is True
        and owner._timeline_markers
        and owner._timeline_markers[0].get("label") == "Bridge QA",
        "json_lines": jsonl_code == 0 and "automation.list_commands" not in dst.getvalue() and "add_marker" in dst.getvalue(),
        "invalid_json_blocked": invalid.get("ok") is False and invalid.get("error", "").startswith("invalid_json:"),
    }
    failures = [name for name, ok in checks.items() if not ok]
    return {
        "ok": not failures,
        "score": int(round(100 * (len(checks) - len(failures)) / max(1, len(checks)))),
        "checks": checks,
        "failures": failures,
        "summary": {
            "command_count": len(command_names),
            "marker_count": len(owner._timeline_markers),
            "marker_sync_count": owner.marker_sync_count,
            "json_lines_bytes": len(dst.getvalue().encode("utf-8")),
        },
        "schema": schema,
        "commands": commands,
        "status": status,
        "rejected": rejected,
        "marker": marker,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build TigerCapture automation bridge QA report.")
    parser.add_argument("--out", default="debugCapture/automation_bridge_qa.json")
    args = parser.parse_args()
    report = build_automation_bridge_report()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
