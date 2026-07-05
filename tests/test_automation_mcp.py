from __future__ import annotations

import json
import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


SRT_SAMPLE = """1
00:00:01,000 --> 00:00:03,000
Um today we explain materials.

2
00:00:04,000 --> 00:00:06,000
어 이제 base color를 연결합니다.
"""


class _McpOwner:
    def __init__(self) -> None:
        from app.audio_tracks import AudioClip, AudioTrack
        from app.timeline_model import VideoClip, VideoTrack

        self._tracks = [
            VideoTrack(
                id=1,
                clips=[
                    VideoClip(
                        id=10,
                        source_duration_ms=10000,
                        timeline_in_ms=0,
                        source_in_ms=0,
                        source_out_ms=10000,
                    )
                ],
            )
        ]
        self._audio_tracks = [
            AudioTrack(
                id=2,
                clips=[
                    AudioClip(
                        id=20,
                        duration_ms=5000,
                        trim_end_ms=5000,
                    )
                ],
            )
        ]
        self._timeline_markers = []
        self._selected_clips = [(1, 10)]
        self._project_settings = {}
        self.marker_sync_count = 0

    def _sync_markers_to_ruler(self) -> None:
        self.marker_sync_count += 1

    def _register_change(self, label: str = "") -> None:
        self._last_change = label


def _tool_payload(response: dict) -> dict:
    text = response["result"]["content"][0]["text"]
    return json.loads(text)


def test_automation_mcp_initialize_and_tools_list():
    from app.automation_mcp import AutomationMCPServer

    server = AutomationMCPServer(_McpOwner())
    init = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    tools = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    assert init["result"]["serverInfo"]["name"] == "tigercapture-automation"
    names = {row["name"] for row in tools["result"]["tools"]}
    assert {
        "tigercapture_ping",
        "tigercapture_schema",
        "tigercapture_list_commands",
        "tigercapture_execute_command",
        "tigercapture_list_actions",
        "tigercapture_execute_action",
        "tigercapture_execute_sequence",
    } <= names


def test_automation_mcp_tool_calls_are_safe_and_registered():
    from app.automation_mcp import AutomationMCPServer

    owner = _McpOwner()
    server = AutomationMCPServer(owner)
    unknown = server.handle_message(
        {"jsonrpc": "2.0", "id": "bad", "method": "tools/call", "params": {"name": "python_exec"}}
    )
    dry = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "dry",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_execute_command",
                "arguments": {"command": "add_marker", "params": {"ms": 333, "label": "Dry"}, "dry_run": True},
            },
        }
    )
    assert unknown["error"]["code"] == -32602
    assert _tool_payload(dry)["result"]["dry_run"] is True
    assert owner._timeline_markers == []

    added = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "add",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_execute_command",
                "arguments": {"command": "add_marker", "params": {"ms": 444, "label": "MCP marker"}},
            },
        }
    )
    payload = _tool_payload(added)
    assert added["result"]["isError"] is False
    assert payload["result"]["ok"] is True
    assert owner._timeline_markers[0]["label"] == "MCP marker"
    assert owner.marker_sync_count == 1


def test_automation_mcp_can_generate_edit_plan_through_generic_tool():
    from app.automation_mcp import AutomationMCPServer

    server = AutomationMCPServer(_McpOwner())
    response = server.handle_message(
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
    )
    payload = _tool_payload(response)
    assert response["result"]["isError"] is False
    assert payload["result"]["ok"] is True
    assert payload["result"]["result"]["plan"]["provider"] == "rule_based"
    assert payload["result"]["result"]["payload_counts"]["subtitle_rows"] == 2


def test_automation_mcp_action_tools_reach_python_action_registry():
    from app.automation_mcp import AutomationMCPServer

    owner = _McpOwner()
    server = AutomationMCPServer(owner)
    actions = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "actions",
            "method": "tools/call",
            "params": {"name": "tigercapture_list_actions"},
        }
    )
    schema = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "schema",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_get_action_schema",
                "arguments": {"action": "timeline.marker.add"},
            },
        }
    )
    preview = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "preview",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_preview_action",
                "arguments": {"action": "timeline.marker.add", "params": {"ms": 555, "label": "Preview"}},
            },
        }
    )
    applied = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "apply",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_execute_action",
                "arguments": {"action": "timeline.marker.add", "params": {"ms": 666, "label": "Action MCP"}},
            },
        }
    )
    audio_ai = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "audio-ai",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_execute_action",
                "arguments": {
                    "action": "audio.sound_editor.apply_ai_preset",
                    "params": {"track_id": 2, "clip_id": 20, "preset": "Suno v4", "focus_workbench": False},
                },
            },
        }
    )
    sequence = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": "sequence",
            "method": "tools/call",
            "params": {
                "name": "tigercapture_execute_sequence",
                "arguments": {
                    "steps": [
                        {"action": "app.status"},
                        {"action": "timeline.marker.add", "params": {"ms": 777, "label": "Sequence MCP"}},
                    ]
                },
            },
        }
    )

    actions_payload = _tool_payload(actions)
    schema_payload = _tool_payload(schema)
    preview_payload = _tool_payload(preview)
    applied_payload = _tool_payload(applied)
    audio_ai_payload = _tool_payload(audio_ai)
    sequence_payload = _tool_payload(sequence)

    assert {row["id"] for row in actions_payload["actions"]} >= {
        "app.status",
        "timeline.marker.add",
        "audio.sound_editor.apply_effects",
        "audio.sound_editor.apply_ai_preset",
        "mmd.summary",
        "mmd.diagnostics",
        "mmd.actor.add",
        "mmd.actor.duplicate",
        "mmd.track.move",
    }
    assert schema_payload["schema"]["id"] == "timeline.marker.add"
    assert preview_payload["ok"] is True
    assert preview_payload["dry_run"] is True
    assert applied_payload["ok"] is True
    assert applied_payload["changed"] is True
    assert audio_ai_payload["ok"] is True
    assert owner._audio_tracks[0].clips[0].effects["ai_master"]["preset"] == "Suno v4"
    assert sequence_payload["ok"] is True
    assert [row["label"] for row in owner._timeline_markers] == ["Action MCP", "Sequence MCP"]


def test_automation_mcp_json_lines_server():
    from io import StringIO

    from app.automation_mcp import AutomationMCPServer

    server = AutomationMCPServer(_McpOwner())
    src = StringIO(
        '{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'
        '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
    )
    dst = StringIO()
    assert server.serve_json_lines(src, dst) == 0
    out = dst.getvalue()
    assert "tigercapture_execute_command" in out
    assert out.count('"jsonrpc": "2.0"') == 2
