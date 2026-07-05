import json


def test_vseeface_bridge_action_tool_writes_primary_action_preview(tmp_path):
    from tools.vseeface_bridge_action import main

    status = {
        "actions": [
            {
                "id": "register_vseeface_camera",
                "label": "Register VSeeFaceCamera",
                "kind": "manual_setup",
                "primary": True,
                "auto_run": False,
                "plan": {
                    "auto_run": False,
                    "requires_user_initiation": True,
                    "requires_admin": True,
                    "steps": [
                        {"id": "prepare_registration_batch", "kind": "tool", "program": ".\\.venv\\Scripts\\python.exe", "args": ["tools\\register_vseeface_camera.py"], "auto_run": False},
                        {"id": "launch_admin_registration", "kind": "tool", "program": ".\\.venv\\Scripts\\python.exe", "args": ["tools\\register_vseeface_camera.py", "--launch"], "requires_admin": True, "auto_run": False},
                    ],
                },
            }
        ]
    }
    status_path = tmp_path / "status.json"
    out = tmp_path / "preview.json"
    status_path.write_text(json.dumps(status), encoding="utf-8")

    rc = main(["--status-report", str(status_path), "--out", str(out)])

    preview = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0
    assert preview["action_id"] == "register_vseeface_camera"
    assert preview["requires_admin"] is True
    assert preview["execute_allowed"] is False
    assert preview["steps"][1]["state"] == "requires_admin_confirmation"


def test_vseeface_bridge_action_tool_allows_admin_in_preview_only(tmp_path):
    from tools.vseeface_bridge_action import main

    status = {
        "actions": [
            {
                "id": "register_vseeface_camera",
                "label": "Register VSeeFaceCamera",
                "primary": True,
                "auto_run": False,
                "plan": {
                    "auto_run": False,
                    "requires_admin": True,
                    "steps": [
                        {"id": "launch_admin_registration", "kind": "tool", "program": "python", "args": ["tool.py"], "requires_admin": True, "auto_run": False},
                    ],
                },
            }
        ]
    }
    status_path = tmp_path / "status.json"
    out = tmp_path / "preview.json"
    status_path.write_text(json.dumps(status), encoding="utf-8")

    rc = main(["--status-report", str(status_path), "--allow-admin", "--out", str(out)])

    preview = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0
    assert preview["execute_allowed"] is True
    assert preview["steps"][0]["state"] == "ready"


def test_vseeface_execution_gate_tool_writes_gate_without_executing(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_sidecar_apply_plan
    from tools.vseeface_execution_gate import main

    avatar = tmp_path / "avatar.vrm"
    settings = tmp_path / "settings.ini"
    plan_path = tmp_path / "plan.json"
    out = tmp_path / "gate.json"
    avatar.write_bytes(b"VRM")
    plan = build_vseeface_sidecar_apply_plan(
        VSeeFaceBridgeConfig.from_mapping({"avatar_vrm": str(avatar)}),
        settings_path=settings,
    )
    plan_path.write_text(json.dumps({"plan": plan}), encoding="utf-8")

    rc = main(["--plan", str(plan_path), "--out", str(out)])

    gate = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0
    assert gate["ok"] is True
    assert gate["execute_allowed"] is False
    assert gate["steps"][0]["state"] == "requires_user_confirmation"
    assert not settings.exists()


def test_vseeface_execution_gate_tool_allows_confirmed_plan_preview(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_sidecar_apply_plan
    from tools.vseeface_execution_gate import main

    avatar = tmp_path / "avatar.vrm"
    settings = tmp_path / "settings.ini"
    plan_path = tmp_path / "plan.json"
    out = tmp_path / "gate.json"
    avatar.write_bytes(b"VRM")
    plan = build_vseeface_sidecar_apply_plan(
        VSeeFaceBridgeConfig.from_mapping({"avatar_vrm": str(avatar)}),
        settings_path=settings,
    )
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    rc = main(["--plan", str(plan_path), "--confirm", "--out", str(out)])

    gate = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0
    assert gate["execute_allowed"] is True
    assert gate["steps"][0]["state"] == "ready"
    assert not settings.exists()


def test_vseeface_plan_executor_tool_defaults_to_dry_run(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_sidecar_apply_plan
    from tools.vseeface_plan_executor import main

    avatar = tmp_path / "avatar.vrm"
    settings = tmp_path / "settings.ini"
    plan_path = tmp_path / "plan.json"
    out = tmp_path / "executor.json"
    avatar.write_bytes(b"VRM")
    plan = build_vseeface_sidecar_apply_plan(
        VSeeFaceBridgeConfig.from_mapping({"avatar_vrm": str(avatar)}),
        settings_path=settings,
    )
    plan_path.write_text(json.dumps({"plan": plan}), encoding="utf-8")

    rc = main(["--plan", str(plan_path), "--confirm", "--out", str(out)])

    result = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0
    assert result["dry_run"] is True
    assert result["executed"] is False
    assert result["steps"][0]["would_run"] is True
    assert not settings.exists()


def test_vseeface_plan_executor_tool_blocks_execute_without_confirm(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_sidecar_apply_plan
    from tools.vseeface_plan_executor import main

    avatar = tmp_path / "avatar.vrm"
    settings = tmp_path / "settings.ini"
    plan_path = tmp_path / "plan.json"
    out = tmp_path / "executor.json"
    avatar.write_bytes(b"VRM")
    plan = build_vseeface_sidecar_apply_plan(
        VSeeFaceBridgeConfig.from_mapping({"avatar_vrm": str(avatar)}),
        settings_path=settings,
    )
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    rc = main(["--plan", str(plan_path), "--execute", "--out", str(out)])

    result = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 2
    assert result["ok"] is False
    assert result["executed"] is False
    assert result["errors"] == ["execution_gate_blocked"]
    assert not settings.exists()


def test_vseeface_sidecar_workflow_tool_writes_read_only_report(tmp_path):
    from tools.vseeface_sidecar_workflow import main

    avatar = tmp_path / "avatar.vrm"
    settings = tmp_path / "settings.ini"
    config_path = tmp_path / "config.json"
    out = tmp_path / "workflow.json"
    avatar.write_bytes(b"VRM")
    config_path.write_text(
        json.dumps({
            "avatar_vrm": str(avatar),
            "capture": {"method": "virtual_camera"},
            "input": {"openseeface_port": 39542},
        }),
        encoding="utf-8",
    )

    rc = main([
        "--config",
        str(config_path),
        "--settings",
        str(settings),
        "--out",
        str(out),
    ])

    workflow = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0
    assert workflow["read_only"] is True
    assert workflow["state"] == "confirmation_required"
    assert workflow["view"]["openseeface_endpoint"] == {"host": "127.0.0.1", "port": "39542"}
    assert workflow["view"]["progress"] == 0.75
    assert workflow["view"]["steps"][2]["state"] == "current"
    assert workflow["view"]["next_action"]["registry_action"] == "vtuber.vseeface_sidecar_workflow"
    assert not settings.exists()


def test_vseeface_sidecar_workflow_tool_confirm_changes_state_without_writing(tmp_path):
    from tools.vseeface_sidecar_workflow import main

    avatar = tmp_path / "avatar.vrm"
    settings = tmp_path / "settings.ini"
    config_path = tmp_path / "config.json"
    out = tmp_path / "workflow.json"
    avatar.write_bytes(b"VRM")
    config_path.write_text(json.dumps({"avatar_vrm": str(avatar)}), encoding="utf-8")

    rc = main(["--config", str(config_path), "--settings", str(settings), "--confirm", "--out", str(out)])

    workflow = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0
    assert workflow["state"] == "ready_to_execute"
    assert workflow["executor_dry_run"]["executed"] is False
    assert workflow["view"]["progress"] == 1.0
    assert workflow["view"]["steps"][3]["state"] == "done"
    assert not settings.exists()
