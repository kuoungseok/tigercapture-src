def test_virtual_camera_plan_falls_back_to_program_window_share():
    from app.broadcast_virtual_camera import virtual_camera_output_plan

    plan = virtual_camera_output_plan({})

    assert plan["selected_backend"] == "program_output_window_share"
    assert plan["manual_fallback"] is True
    assert plan["install_policy"] == "user_approved_only"
    assert plan["output_contract"]["mode"] == "window_share"
    assert "Program Output" in plan["operator_steps"][1]


def test_virtual_camera_plan_prefers_available_obs_backend():
    from app.broadcast_virtual_camera import virtual_camera_output_plan

    plan = virtual_camera_output_plan(
        {"preferred_backend": "obs_virtual_camera"},
        installed_backends={"obs_virtual_camera": True},
    )

    assert plan["selected_backend"] == "obs_virtual_camera"
    assert plan["manual_fallback"] is False
    assert plan["output_contract"]["mode"] == "obs_virtual_camera"
    assert plan["output_contract"]["program_output_input"] == "window_capture"
    assert plan["selected"]["can_create_device"] is True


def test_virtual_camera_plan_keeps_obs_free_default_even_when_obs_is_installed():
    from app.broadcast_virtual_camera import virtual_camera_output_plan

    plan = virtual_camera_output_plan(
        {},
        installed_backends={"obs_virtual_camera": {"available": True, "executable": "C:/OBS/obs64.exe"}},
    )

    assert plan["selected_backend"] == "program_output_window_share"
    assert plan["manual_fallback"] is True
    assert plan["default_backend_policy"] == "obs_free_first"
    assert plan["obs_optional"] is True


def test_virtual_camera_plan_can_auto_select_installed_backend_when_requested():
    from app.broadcast_virtual_camera import virtual_camera_output_plan

    plan = virtual_camera_output_plan(
        {"auto_select_installed_backend": True},
        installed_backends={"obs_virtual_camera": {"available": True, "executable": "C:/OBS/obs64.exe"}},
    )

    assert plan["selected_backend"] == "obs_virtual_camera"
    assert plan["manual_fallback"] is False


def test_virtual_camera_plan_selects_installed_device_backend():
    from app.broadcast_virtual_camera import virtual_camera_output_plan

    plan = virtual_camera_output_plan(
        {"preferred_backend": "pyvirtualcam_device"},
        installed_backends={
            "pyvirtualcam_device": {
                "available": True,
                "module": "pyvirtualcam",
                "device_name": "Tiger Virtual Camera",
            }
        },
    )

    assert plan["selected_backend"] == "pyvirtualcam_device"
    assert plan["manual_fallback"] is False
    assert plan["selected"]["can_create_device"] is True
    assert plan["output_contract"]["mode"] == "virtual_camera_device"
    assert plan["output_contract"]["program_output_input"] == "rgb_frame_stream"
    assert plan["output_contract"]["direct_driver_install"] is False


def test_virtual_camera_discovery_reports_pyvirtualcam_when_available():
    from app.broadcast_virtual_camera import discover_installed_virtual_camera_backends

    plan = discover_installed_virtual_camera_backends({"pyvirtualcam_available": True, "virtual_camera_device": "TigerCam"})

    backend = plan["installed_backends"]["pyvirtualcam_device"]
    assert backend["available"] is True
    assert backend["module"] == "pyvirtualcam"
    assert backend["device_name"] == "TigerCam"
    assert backend["detection"] == "explicit_payload"


def test_virtual_camera_discovery_uses_injected_obs_path():
    from app.broadcast_virtual_camera import discover_installed_virtual_camera_backends

    plan = discover_installed_virtual_camera_backends(
        {"obs_executable": "C:/OBS/bin/64bit/obs64.exe"},
        env={},
        path_exists=lambda path: path == "C:/OBS/bin/64bit/obs64.exe",
    )

    obs = plan["installed_backends"]["obs_virtual_camera"]
    assert plan["schema"] == "tigerstudio.broadcast.virtual_camera_discovery.v1"
    assert obs["available"] is True
    assert obs["executable"] == "C:/OBS/bin/64bit/obs64.exe"
    assert plan["install_policy"] == "user_approved_only"


def test_virtual_camera_plan_includes_obs_bridge_when_selected():
    from app.broadcast_virtual_camera import virtual_camera_output_plan

    plan = virtual_camera_output_plan(
        {
            "preferred_backend": "obs_virtual_camera",
            "program_window_title": "Tiger Studio Program Output",
            "scene_name": "Tiger Scene",
            "source_name": "Tiger Window",
        },
        installed_backends={
            "obs_virtual_camera": {
                "available": True,
                "executable": "C:/OBS/obs64.exe",
            }
        },
    )

    bridge = plan["obs_bridge"]
    assert bridge["schema"] == "tigerstudio.broadcast.obs_virtual_camera_bridge.v1"
    assert bridge["available"] is True
    assert bridge["obs_scene"]["scene_name"] == "Tiger Scene"
    assert bridge["obs_scene"]["source_kind"] == "window_capture"
    assert bridge["program_output"]["must_exclude_performance_source"] is True
    assert bridge["automation"]["direct_driver_install"] is False


def test_obs_virtual_camera_bridge_plan_keeps_setup_manual_without_websocket():
    from app.broadcast_virtual_camera import obs_virtual_camera_bridge_plan

    plan = obs_virtual_camera_bridge_plan(
        {"program_window_title": "Tiger Studio Program Output"},
        installed_backends={"obs_virtual_camera": {"available": True, "executable": "C:/OBS/obs64.exe"}},
    )

    assert plan["available"] is True
    assert plan["websocket"]["enabled"] is False
    assert plan["websocket"]["can_control"] is False
    assert plan["obs"]["auto_launch_policy"] == "user_confirmed_only"
    assert any("Window Capture" in step for step in plan["operator_steps"])


def test_obs_bridge_execution_gate_requires_confirm_and_websocket_dependency():
    from app.broadcast_virtual_camera import obs_virtual_camera_bridge_execution_gate

    gate = obs_virtual_camera_bridge_execution_gate(
        {
            "confirm": False,
            "websocket_enabled": True,
            "obsws_available": True,
        },
        installed_backends={"obs_virtual_camera": {"available": True, "executable": "C:/OBS/obs64.exe"}},
    )

    assert gate["ready"] is True
    assert gate["can_execute"] is False
    assert gate["confirm_required"] is True
    assert any("confirmation" in blocker for blocker in gate["execute_blockers"])


def test_obs_bridge_dry_run_lists_scene_source_and_virtual_camera_operations():
    from app.broadcast_virtual_camera import obs_virtual_camera_bridge_executor_dry_run

    dry = obs_virtual_camera_bridge_executor_dry_run(
        {
            "confirm": True,
            "websocket_enabled": True,
            "obsws_available": True,
            "scene_name": "Tiger Scene",
            "source_name": "Tiger Output",
        },
        installed_backends={"obs_virtual_camera": {"available": True, "executable": "C:/OBS/obs64.exe"}},
    )

    operation_ids = [row["id"] for row in dry["operations"]]
    assert dry["would_execute"] is True
    assert dry["can_execute_now"] is True
    assert operation_ids == [
        "connect_obs_websocket",
        "ensure_scene",
        "ensure_window_capture_source",
        "start_virtual_camera",
    ]


def test_execute_obs_bridge_can_apply_with_injected_client():
    from app.broadcast_virtual_camera import execute_obs_virtual_camera_bridge

    class FakeObsClient:
        def __init__(self, *, host, port, password):
            self.host = host
            self.port = port
            self.password = password
            self.calls = []

        def get_scene_list(self):
            self.calls.append(("get_scene_list",))
            return {"scenes": []}

        def create_scene(self, **kwargs):
            self.calls.append(("create_scene", kwargs))

        def get_input_list(self):
            self.calls.append(("get_input_list",))
            return {"inputs": []}

        def create_input(self, **kwargs):
            self.calls.append(("create_input", kwargs))

        def start_virtual_cam(self):
            self.calls.append(("start_virtual_cam",))

    clients = []

    def factory(**kwargs):
        client = FakeObsClient(**kwargs)
        clients.append(client)
        return client

    result = execute_obs_virtual_camera_bridge(
        {
            "confirm": True,
            "websocket_enabled": True,
            "obsws_available": True,
            "scene_name": "Tiger Scene",
            "source_name": "Tiger Output",
            "program_window_title": "Tiger Studio Program Output",
            "websocket_password": "secret",
        },
        installed_backends={"obs_virtual_camera": {"available": True, "executable": "C:/OBS/obs64.exe"}},
        client_factory=factory,
    )

    assert result["executed"] is True
    assert [row["status"] for row in result["operations"][1:]] == ["created", "created", "started"]
    assert clients[0].password == "secret"
    assert clients[0].calls[1][0] == "create_scene"
    assert clients[0].calls[3][0] == "create_input"


def test_virtual_camera_device_session_writes_frames_with_injected_camera():
    import numpy as np

    from app.broadcast_virtual_camera_session import BroadcastVirtualCameraDeviceSession

    class FakeCamera:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.frames = []
            self.closed = False
            cameras.append(self)

        def send(self, frame):
            self.frames.append(np.asarray(frame).copy())

        def sleep_until_next_frame(self):
            pass

        def close(self):
            self.closed = True

    cameras = []
    session = BroadcastVirtualCameraDeviceSession(
        {"device": "TigerCam"},
        {"width": 4, "height": 2, "fps": 30},
        camera_factory=FakeCamera,
    )

    preflight = session.preflight()
    started = session.start()
    written = session.write_frame(np.zeros((2, 4, 3), dtype=np.uint8))
    stopped = session.stop()

    assert preflight["ok"] is True
    assert started["state"] == "running"
    assert written["frames_written"] == 1
    assert written["bytes_written"] == 4 * 2 * 3
    assert cameras[0].kwargs["device"] == "TigerCam"
    assert cameras[0].frames[0].shape == (2, 4, 3)
    assert stopped["state"] == "stopped"
    assert cameras[0].closed is True
