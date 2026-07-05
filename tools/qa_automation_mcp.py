"""QA report for the TigerCapture automation MCP wrapper."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _Owner:
    def __init__(self) -> None:
        from app.timeline_model import VideoClip, VideoTrack

        self._tracks = [
            VideoTrack(
                id=1,
                clips=[
                    VideoClip(
                        id=10,
                        source_duration_ms=6000,
                        timeline_in_ms=0,
                        source_in_ms=0,
                        source_out_ms=6000,
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


SRT_SAMPLE = """1
00:00:01,000 --> 00:00:03,000
Um today we explain materials.

2
00:00:04,000 --> 00:00:06,000
어 이제 base color를 연결합니다.
"""


def _tool_payload(response: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(response.get("result", {}).get("content", [{}])[0].get("text", "{}"))
    except Exception:
        return {}


def build_automation_mcp_report() -> dict[str, Any]:
    from io import StringIO

    from app.automation_mcp import AutomationMCPServer

    owner = _Owner()
    server = AutomationMCPServer(owner)
    init = server.handle_message({"jsonrpc": "2.0", "id": "init", "method": "initialize"}) or {}
    tools = server.handle_message({"jsonrpc": "2.0", "id": "tools", "method": "tools/list"}) or {}
    schema = server.handle_message(
        {"jsonrpc": "2.0", "id": "schema", "method": "tools/call", "params": {"name": "tigercapture_schema"}}
    ) or {}
    status = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "status",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_execute_command",
                "arguments": {"command": "get_app_status"},
            },
        }
    ) or {}
    generated = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "generate",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_execute_command",
                "arguments": {
                    "command": "generate_edit_plan",
                    "params": {
                        "transcript_text": SRT_SAMPLE,
                        "source_format": "srt",
                        "prompt": "튜토리얼을 보기 좋게 정리하고 자막도 만들어줘",
                        "silence_intervals": [{"start_ms": 3000, "end_ms": 4200}],
                    },
                },
            },
        }
    ) or {}
    rejected = server.handle_message(
        {"jsonrpc": "2.0", "id": "bad", "method": "tools/call", "params": {"name": "python_exec"}}
    ) or {}
    dry = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "dry",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_execute_command",
                "arguments": {"command": "add_marker", "params": {"ms": 100, "label": "Dry"}, "dry_run": True},
            },
        }
    ) or {}
    action_list = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "action_list",
            "method": "tools/call",
            "params": {"name": "tigercapture_list_actions"},
        }
    ) or {}
    action_preview = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "action_preview",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_preview_action",
                "arguments": {
                    "action": "timeline.marker.add",
                    "params": {"ms": 250, "label": "Action Preview"},
                },
            },
        }
    ) or {}
    marker_before = len(owner._timeline_markers)
    marker = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "marker",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_execute_command",
                "arguments": {"command": "add_marker", "params": {"ms": 1500, "label": "MCP QA"}},
            },
        }
    ) or {}
    action_sequence = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "action_sequence",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_execute_sequence",
                "arguments": {
                    "steps": [
                        {"action": "app.status"},
                        {
                            "action": "timeline.marker.add",
                            "params": {"ms": 1800, "label": "Action Sequence QA"},
                        },
                    ]
                },
            },
        }
    ) or {}
    src = StringIO(
        '{"jsonrpc":"2.0","id":"one","method":"initialize"}\n'
        '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
        '{"jsonrpc":"2.0","id":"two","method":"tools/list"}\n'
    )
    dst = StringIO()
    jsonl_code = server.serve_json_lines(src, dst)

    tool_names = {row.get("name") for row in tools.get("result", {}).get("tools", [])}
    schema_payload = _tool_payload(schema)
    status_payload = _tool_payload(status)
    generated_payload = _tool_payload(generated)
    dry_payload = _tool_payload(dry)
    marker_payload = _tool_payload(marker)
    action_list_payload = _tool_payload(action_list)
    action_preview_payload = _tool_payload(action_preview)
    action_sequence_payload = _tool_payload(action_sequence)
    checks = {
        "initialize": init.get("result", {}).get("serverInfo", {}).get("name") == "tigercapture-automation",
        "tools_list": {
            "tigercapture_schema",
            "tigercapture_execute_command",
            "tigercapture_list_actions",
            "tigercapture_execute_action",
            "tigercapture_execute_sequence",
        } <= tool_names,
        "schema_safe": schema_payload.get("result", {}).get("security", {}).get("arbitrary_python") is False,
        "status_exec": status_payload.get("result", {}).get("ok") is True,
        "generate_plan_exec": generated_payload.get("result", {}).get("ok") is True
        and generated_payload.get("result", {}).get("result", {}).get("payload_counts", {}).get("subtitle_rows") == 2,
        "unknown_tool_rejected": rejected.get("error", {}).get("code") == -32602,
        "dry_run_no_mutation": dry_payload.get("result", {}).get("dry_run") is True and marker_before == 0,
        "marker_apply": marker_payload.get("result", {}).get("ok") is True
        and owner._timeline_markers
        and owner._timeline_markers[0].get("label") == "MCP QA",
        "action_list": any(row.get("id") == "timeline.marker.add" for row in action_list_payload.get("actions", [])),
        "action_preview": action_preview_payload.get("ok") is True
        and action_preview_payload.get("dry_run") is True,
        "action_sequence": action_sequence_payload.get("ok") is True
        and any(row.get("label") == "Action Sequence QA" for row in owner._timeline_markers),
        "json_lines": jsonl_code == 0 and "tigercapture_execute_command" in dst.getvalue(),
    }
    failures = [name for name, ok in checks.items() if not ok]
    return {
        "ok": not failures,
        "score": int(round(100 * (len(checks) - len(failures)) / max(1, len(checks)))),
        "checks": checks,
        "failures": failures,
        "summary": {
            "tool_count": len(tool_names),
            "generated_operations": len(generated_payload.get("result", {}).get("result", {}).get("plan", {}).get("operations", []) or []),
            "marker_count": len(owner._timeline_markers),
            "marker_sync_count": owner.marker_sync_count,
            "json_lines_bytes": len(dst.getvalue().encode("utf-8")),
            "action_count": len(action_list_payload.get("actions", []) or []),
        },
        "initialize": init,
        "tools": tools,
        "schema": schema_payload,
        "status": status_payload,
        "generated": generated_payload,
        "marker": marker_payload,
        "actions": action_list_payload,
        "action_sequence": action_sequence_payload,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build TigerCapture automation MCP QA report.")
    parser.add_argument("--out", default="debugCapture/automation_mcp_qa.json")
    args = parser.parse_args()
    report = build_automation_mcp_report()
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
