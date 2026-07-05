from __future__ import annotations

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _BridgeOwner:
    def __init__(self) -> None:
        from app.audio_tracks import AudioClip, AudioTrack
        from app.timeline_model import VideoClip, VideoTrack

        self._tracks = [
            VideoTrack(
                id=1,
                clips=[
                    VideoClip(
                        id=10,
                        source_duration_ms=5000,
                        timeline_in_ms=0,
                        source_in_ms=0,
                        source_out_ms=5000,
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
        self.changes: list[str] = []

    def _sync_markers_to_ruler(self) -> None:
        self.marker_sync_count += 1

    def _register_change(self, label: str = "") -> None:
        self.changes.append(label)


def test_automation_bridge_schema_and_list_commands():
    from app.automation_bridge import AutomationBridge

    bridge = AutomationBridge(_BridgeOwner())
    ping = bridge.handle_request({"id": 1, "method": "automation.ping"})
    schema = bridge.handle_request({"id": 2, "method": "automation.schema"})
    commands = bridge.handle_request({"id": 3, "method": "automation.list_commands"})
    actions = bridge.handle_request({"id": 4, "method": "automation.list_actions"})

    assert ping["ok"] is True
    assert ping["result"]["pong"] is True
    assert schema["result"]["security"]["arbitrary_python"] is False
    assert schema["result"]["security"]["arbitrary_shell"] is False
    assert schema["result"]["security"]["registered_actions_only"] is True
    assert "automation.execute_action" in schema["result"]["methods"]
    assert {row["name"] for row in commands["result"]["commands"]} >= {"get_app_status", "add_marker"}
    assert {row["id"] for row in actions["result"]["actions"]} >= {
        "app.status",
        "timeline.marker.add",
        "audio.sound_editor.apply_effects",
        "audio.sound_editor.apply_ai_preset",
        "mmd.summary",
        "mmd.diagnostics",
        "mmd.actor.add",
        "mmd.actor.duplicate",
        "mmd.track.move",
        "ar_pbr.gizmo.state",
        "ar_pbr.gizmo.show",
        "ar_pbr.gizmo.hide",
    }


def test_automation_bridge_executes_registered_command_only():
    from app.automation_bridge import AutomationBridge

    owner = _BridgeOwner()
    bridge = AutomationBridge(owner)
    unknown = bridge.handle_request({"id": "bad", "method": "automation.execute", "params": {"command": "shell"}})
    dry = bridge.handle_request(
        {
            "id": "dry",
            "method": "automation.execute",
            "params": {"command": "add_marker", "params": {"ms": 111, "label": "Dry"}, "dry_run": True},
        }
    )

    assert unknown["ok"] is True
    assert unknown["result"]["ok"] is False
    assert unknown["result"]["error"] == "unknown command: shell"
    assert dry["result"]["dry_run"] is True
    assert owner._timeline_markers == []

    added = bridge.handle_request(
        {
            "id": "add",
            "method": "automation.execute",
            "params": {"command": "add_marker", "params": {"ms": 222, "label": "Bridge marker"}},
        }
    )
    assert added["result"]["ok"] is True
    assert owner._timeline_markers[0]["label"] == "Bridge marker"
    assert owner.marker_sync_count == 1


def test_automation_bridge_executes_registered_actions():
    from app.automation_bridge import AutomationBridge

    owner = _BridgeOwner()
    bridge = AutomationBridge(owner)
    schema = bridge.handle_request(
        {"id": "schema", "method": "automation.get_action_schema", "params": {"action": "timeline.marker.add"}}
    )
    preview = bridge.handle_request(
        {
            "id": "preview",
            "method": "automation.preview_action",
            "params": {"action": "timeline.marker.add", "params": {"ms": 111, "label": "Preview"}},
        }
    )
    applied = bridge.handle_request(
        {
            "id": "apply",
            "method": "automation.execute_action",
            "params": {"action": "timeline.marker.add", "params": {"ms": 222, "label": "Action marker"}},
        }
    )
    audio_ai = bridge.handle_request(
        {
            "id": "audio-ai",
            "method": "automation.execute_action",
            "params": {
                "action": "audio.sound_editor.apply_ai_preset",
                "params": {"track_id": 2, "clip_id": 20, "preset": "Udio", "focus_workbench": False},
            },
        }
    )
    sequence = bridge.handle_request(
        {
            "id": "sequence",
            "method": "automation.execute_sequence",
            "params": {
                "steps": [
                    {"action": "app.status"},
                    {"action": "timeline.marker.add", "params": {"ms": 333, "label": "Sequence marker"}},
                ]
            },
        }
    )

    assert schema["result"]["ok"] is True
    assert schema["result"]["schema"]["id"] == "timeline.marker.add"
    assert preview["result"]["ok"] is True
    assert preview["result"]["dry_run"] is True
    assert [row["label"] for row in owner._timeline_markers] == ["Action marker", "Sequence marker"]
    assert applied["result"]["ok"] is True
    assert audio_ai["result"]["ok"] is True
    assert owner._audio_tracks[0].clips[0].effects["ai_master"]["preset"] == "Udio"
    assert applied["result"]["changed"] is True
    assert sequence["result"]["ok"] is True
    assert sequence["result"]["failed_index"] == -1


def test_automation_bridge_json_lines_and_request_limits():
    from io import StringIO

    from app.automation_bridge import AutomationBridge

    bridge = AutomationBridge(_BridgeOwner(), max_request_bytes=64)
    invalid = bridge.handle_json("{")
    too_large = bridge.handle_json('{"method":"automation.ping","padding":"' + ("x" * 2048) + '"}')

    assert invalid["ok"] is False
    assert invalid["error"].startswith("invalid_json:")
    assert too_large["ok"] is False
    assert too_large["error"] == "request_too_large"

    bridge = AutomationBridge(_BridgeOwner())
    src = StringIO('{"id":1,"method":"automation.ping"}\n{"id":2,"method":"automation.list_commands"}\n')
    dst = StringIO()
    assert bridge.serve_json_lines(src, dst) == 0
    assert '"pong": true' in dst.getvalue()
    assert "add_marker" in dst.getvalue()
