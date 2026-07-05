from types import SimpleNamespace


def test_vseeface_plan_executor_defaults_to_dry_run(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_sidecar_apply_plan
    from app.vtuber.vseeface_plan_executor import execute_vseeface_plan

    avatar = tmp_path / "avatar.vrm"
    settings = tmp_path / "settings.ini"
    avatar.write_bytes(b"VRM")
    plan = build_vseeface_sidecar_apply_plan(
        VSeeFaceBridgeConfig.from_mapping({"avatar_vrm": str(avatar)}),
        settings_path=settings,
    )

    result = execute_vseeface_plan(plan, confirm=True)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["executed"] is False
    assert result["steps"][0]["would_run"] is True
    assert not settings.exists()


def test_vseeface_plan_executor_blocks_execution_without_confirmation(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_sidecar_apply_plan
    from app.vtuber.vseeface_plan_executor import execute_vseeface_plan

    calls = []
    avatar = tmp_path / "avatar.vrm"
    settings = tmp_path / "settings.ini"
    avatar.write_bytes(b"VRM")
    plan = build_vseeface_sidecar_apply_plan(
        VSeeFaceBridgeConfig.from_mapping({"avatar_vrm": str(avatar)}),
        settings_path=settings,
    )

    result = execute_vseeface_plan(plan, execute=True, runner=lambda *args, **kwargs: calls.append(args))

    assert result["ok"] is False
    assert result["executed"] is False
    assert result["errors"] == ["execution_gate_blocked"]
    assert calls == []
    assert not settings.exists()


def test_vseeface_plan_executor_runs_only_after_explicit_execute_and_confirm(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_sidecar_apply_plan
    from app.vtuber.vseeface_plan_executor import execute_vseeface_plan

    calls = []
    avatar = tmp_path / "avatar.vrm"
    settings = tmp_path / "settings.ini"
    avatar.write_bytes(b"VRM")
    plan = build_vseeface_sidecar_apply_plan(
        VSeeFaceBridgeConfig.from_mapping({"avatar_vrm": str(avatar)}),
        settings_path=settings,
    )

    def fake_runner(command, **kwargs):
        calls.append({"command": command, "kwargs": kwargs})
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    result = execute_vseeface_plan(plan, confirm=True, execute=True, runner=fake_runner)

    assert result["ok"] is True
    assert result["executed"] is True
    assert result["steps"][0]["ok"] is True
    assert result["steps"][0]["stdout"] == "ok"
    assert calls[0]["command"][1] == "tools\\configure_vseeface_sidecar.py"
    assert calls[0]["kwargs"]["capture_output"] is True
    assert not settings.exists()


def test_vseeface_plan_executor_stops_after_failed_step():
    from app.vtuber.vseeface_plan_executor import execute_vseeface_plan

    calls = []
    plan = {
        "auto_run": False,
        "requires_user_initiation": True,
        "steps": [
            {
                "id": "one",
                "kind": "tool",
                "program": ".\\.venv\\Scripts\\python.exe",
                "args": ["tools\\vseeface_capture_backend_preflight.py"],
                "auto_run": False,
            },
            {
                "id": "two",
                "kind": "tool",
                "program": ".\\.venv\\Scripts\\python.exe",
                "args": ["tools\\verify_vseeface_post_install.py", "--skip-video-send"],
                "auto_run": False,
            },
        ],
    }

    def fake_runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=7, stdout="", stderr="failed")

    result = execute_vseeface_plan(plan, confirm=True, execute=True, runner=fake_runner)

    assert result["ok"] is False
    assert result["errors"] == ["step_failed:one"]
    assert len(calls) == 1
