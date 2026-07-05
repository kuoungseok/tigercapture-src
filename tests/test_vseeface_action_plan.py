def test_vseeface_action_preview_blocks_admin_step_until_allowed():
    from app.vtuber.vseeface_action_plan import build_vseeface_action_preview

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
                        {"id": "prepare_registration_batch", "kind": "tool", "program": "python", "args": ["tool.py"], "auto_run": False},
                        {"id": "launch_admin_registration", "kind": "tool", "program": "python", "args": ["tool.py", "--launch"], "requires_admin": True, "auto_run": False},
                    ],
                },
            }
        ]
    }

    preview = build_vseeface_action_preview(status)
    allowed = build_vseeface_action_preview(status, allow_admin=True)

    assert preview["ok"] is True
    assert preview["requires_admin"] is True
    assert preview["execute_allowed"] is False
    assert preview["steps"][1]["state"] == "requires_admin_confirmation"
    assert allowed["execute_allowed"] is True
    assert allowed["steps"][1]["state"] == "ready"


def test_vseeface_action_preview_reports_missing_action():
    from app.vtuber.vseeface_action_plan import build_vseeface_action_preview

    preview = build_vseeface_action_preview({"actions": []}, action_id="missing")

    assert preview["ok"] is False
    assert preview["errors"] == ["action_not_found"]


def test_vseeface_action_preview_accepts_tracking_input_picker_action():
    from app.vtuber.vseeface_bridge import ACTION_SELECT_TRACKING_INPUT, build_vseeface_bridge_action_plan
    from app.vtuber.vseeface_action_plan import build_vseeface_action_preview

    status = {
        "actions": [
            {
                "id": ACTION_SELECT_TRACKING_INPUT,
                "label": "Select tracking input",
                "kind": "ui",
                "primary": False,
                "auto_run": False,
                "plan": build_vseeface_bridge_action_plan(ACTION_SELECT_TRACKING_INPUT),
            }
        ]
    }

    preview = build_vseeface_action_preview(status, action_id=ACTION_SELECT_TRACKING_INPUT)

    assert preview["ok"] is True
    assert preview["execute_allowed"] is True
    assert preview["steps"][0]["kind"] == "ui"
    assert preview["steps"][0]["control"] == "camera_or_project_clip_picker"
    assert preview["steps"][0]["registry_action"] == "vtuber.vseeface_select_input_source"
    assert preview["steps"][0]["form"]["params"][0]["source"] == "status.input_sources.options"


def test_vseeface_action_preview_exposes_file_picker_form_metadata():
    from app.vtuber.vseeface_bridge import ACTION_SELECT_VSEEFACE_EXE, build_vseeface_bridge_action_plan
    from app.vtuber.vseeface_action_plan import build_vseeface_action_preview

    status = {
        "actions": [
            {
                "id": ACTION_SELECT_VSEEFACE_EXE,
                "label": "Select VSeeFace.exe",
                "kind": "ui",
                "primary": True,
                "auto_run": False,
                "plan": build_vseeface_bridge_action_plan(ACTION_SELECT_VSEEFACE_EXE),
            }
        ]
    }

    preview = build_vseeface_action_preview(status)

    assert preview["ok"] is True
    assert preview["steps"][0]["registry_action"] == "vtuber.vseeface_select_exe"
    assert preview["steps"][0]["form"]["params"][0]["name"] == "path"
    assert preview["steps"][0]["form"]["params"][0]["must_exist"] is True


def test_vseeface_action_preview_exposes_capture_backend_picker_form():
    from app.vtuber.vseeface_bridge import ACTION_SELECT_CAPTURE_BACKEND, build_vseeface_bridge_action_plan
    from app.vtuber.vseeface_action_plan import build_vseeface_action_preview

    status = {
        "actions": [
            {
                "id": ACTION_SELECT_CAPTURE_BACKEND,
                "label": "Select capture backend",
                "kind": "ui",
                "primary": False,
                "auto_run": False,
                "plan": build_vseeface_bridge_action_plan(ACTION_SELECT_CAPTURE_BACKEND),
            }
        ]
    }

    preview = build_vseeface_action_preview(status, action_id=ACTION_SELECT_CAPTURE_BACKEND)

    assert preview["ok"] is True
    assert preview["steps"][0]["registry_action"] == "vtuber.vseeface_select_capture_backend"
    assert preview["steps"][0]["form"]["params"][0]["kind"] == "enum"
    assert preview["steps"][0]["form"]["params"][0]["options"][2]["value"] == "spout2"


def test_vseeface_action_preview_exposes_framing_picker_form():
    from app.vtuber.vseeface_bridge import ACTION_SELECT_BROADCAST_FRAMING, build_vseeface_bridge_action_plan
    from app.vtuber.vseeface_action_plan import build_vseeface_action_preview

    status = {
        "actions": [
            {
                "id": ACTION_SELECT_BROADCAST_FRAMING,
                "label": "Select framing",
                "kind": "ui",
                "primary": False,
                "auto_run": False,
                "plan": build_vseeface_bridge_action_plan(ACTION_SELECT_BROADCAST_FRAMING),
            }
        ]
    }

    preview = build_vseeface_action_preview(status, action_id=ACTION_SELECT_BROADCAST_FRAMING)

    assert preview["ok"] is True
    assert preview["steps"][0]["registry_action"] == "vtuber.vseeface_select_framing"
    assert preview["steps"][0]["form"]["params"][0]["options"][1]["value"] == "half_body"


def test_vseeface_execution_gate_requires_confirmation_for_sidecar_write(tmp_path):
    from app.vtuber.vseeface_action_plan import build_vseeface_execution_gate
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_sidecar_apply_plan

    avatar = tmp_path / "avatar.vrm"
    avatar.write_bytes(b"VRM")
    plan = build_vseeface_sidecar_apply_plan(
        VSeeFaceBridgeConfig.from_mapping({"avatar_vrm": str(avatar)}),
        settings_path=tmp_path / "settings.ini",
    )

    gated = build_vseeface_execution_gate(plan)
    confirmed = build_vseeface_execution_gate(plan, confirm=True)

    assert gated["ok"] is True
    assert gated["execute_allowed"] is False
    assert gated["requires_confirmation"] is True
    assert gated["steps"][0]["state"] == "requires_user_confirmation"
    assert "user_confirmation_required" in gated["warnings"]
    assert confirmed["ok"] is True
    assert confirmed["execute_allowed"] is True
    assert confirmed["steps"][0]["state"] == "ready"
    assert not (tmp_path / "settings.ini").exists()


def test_vseeface_execution_gate_blocks_unknown_tool():
    from app.vtuber.vseeface_action_plan import build_vseeface_execution_gate

    plan = {
        "auto_run": False,
        "requires_user_initiation": True,
        "steps": [
            {
                "id": "bad",
                "kind": "tool",
                "program": "powershell.exe",
                "args": ["tools\\unknown.py"],
                "auto_run": False,
            }
        ],
    }

    gated = build_vseeface_execution_gate(plan, confirm=True)

    assert gated["ok"] is False
    assert gated["execute_allowed"] is False
    assert "step_0_program_not_allowed" in gated["errors"]
    assert "step_0_script_not_allowed" in gated["errors"]


def test_vseeface_execution_gate_blocks_admin_without_allow_admin():
    from app.vtuber.vseeface_action_plan import build_vseeface_execution_gate

    plan = {
        "auto_run": False,
        "requires_user_initiation": True,
        "requires_admin": True,
        "steps": [
            {
                "id": "register",
                "kind": "tool",
                "program": ".\\.venv\\Scripts\\python.exe",
                "args": ["tools\\register_vseeface_camera.py", "--launch"],
                "requires_admin": True,
                "auto_run": False,
            }
        ],
    }

    gated = build_vseeface_execution_gate(plan, confirm=True)
    allowed = build_vseeface_execution_gate(plan, confirm=True, allow_admin=True)

    assert gated["ok"] is True
    assert gated["execute_allowed"] is False
    assert gated["steps"][0]["state"] == "requires_admin_confirmation"
    assert allowed["execute_allowed"] is True
    assert allowed["steps"][0]["state"] == "ready"
