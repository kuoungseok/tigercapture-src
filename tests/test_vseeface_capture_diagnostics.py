def test_graphics_probe_diagnostics_rejects_error_dialog_as_usable_capture():
    from app.vtuber.vseeface_capture_diagnostics import CAPTURE_UNUSABLE, analyze_graphics_probe_report

    report = {
        "variants": [
            {
                "name": "d3d11",
                "flags": ["-force-d3d11"],
                "printwindow": {
                    "content_nonblack": False,
                    "content": {"mean_luma": 1.6, "unique_colors": 2},
                },
                "virtual_camera": {"opened": True, "content_nonblack": False},
                "log_tail": "Adjusted player loop.",
            },
            {
                "name": "vulkan",
                "flags": ["-force-vulkan"],
                "printwindow": {
                    "content_nonblack": True,
                    "size": [598, 343],
                    "content": {"mean_luma": 219.0, "unique_colors": 626},
                },
                "log_tail": "InitializeEngineGraphics failed",
            },
        ],
    }

    diagnostics = analyze_graphics_probe_report(report)

    assert diagnostics["ok"] is False
    assert diagnostics["status"] == CAPTURE_UNUSABLE
    assert diagnostics["usable_variants"] == []
    assert diagnostics["black_variants"][0]["name"] == "d3d11"
    assert diagnostics["virtual_camera_black_variants"][0]["name"] == "d3d11"
    assert diagnostics["graphics_failed_variants"][0]["name"] == "vulkan"
    assert "switch_capture_method_to_spout2_or_virtual_camera" in diagnostics["recommendations"]


def test_graphics_probe_diagnostics_rejects_small_unity_error_dialog_without_full_log():
    from app.vtuber.vseeface_capture_diagnostics import GRAPHICS_FAILED, analyze_graphics_probe_report

    diagnostics = analyze_graphics_probe_report({
        "variants": [
            {
                "name": "glcore_windowed",
                "flags": ["-force-glcore"],
                "printwindow": {
                    "content_nonblack": True,
                    "size": [598, 343],
                    "content": {"mean_luma": 219.0, "unique_colors": 626},
                },
                "virtual_camera": {"opened": True, "content_nonblack": False},
                "log_tail": "s failed",
            }
        ],
    })

    assert diagnostics["ok"] is False
    assert diagnostics["status"] == GRAPHICS_FAILED
    assert diagnostics["graphics_failed_variants"][0]["name"] == "glcore_windowed"


def test_graphics_probe_diagnostics_accepts_nonblack_without_graphics_failure():
    from app.vtuber.vseeface_capture_diagnostics import CAPTURE_READY, analyze_graphics_probe_report

    diagnostics = analyze_graphics_probe_report({
        "variants": [
            {
                "name": "d3d11",
                "flags": [],
                "printwindow": {
                    "content_nonblack": True,
                    "content": {"mean_luma": 80.0, "unique_colors": 4000},
                },
                "virtual_camera": {"opened": True, "content_nonblack": True},
                "log_tail": "Avatar loaded.",
            }
        ]
    })

    assert diagnostics["ok"] is True
    assert diagnostics["status"] == CAPTURE_READY
    assert diagnostics["usable_variants"][0]["name"] == "d3d11"
    assert diagnostics["usable_virtual_camera"] is True


def test_capture_backend_prefers_registered_virtual_camera_when_window_is_blocked():
    from app.vtuber.vseeface_capture_diagnostics import BACKEND_NEEDS_CONFIGURATION, choose_capture_backend

    decision = choose_capture_backend({
        "spout2": {"sender_available": True, "receiver_available": False},
        "virtual_camera": {"registered": True, "requires_admin_registration": False},
    })

    assert decision["preferred_backend"] == "virtual_camera"
    assert decision["status"] == BACKEND_NEEDS_CONFIGURATION


def test_capture_backend_reports_admin_install_when_vseeface_camera_is_bundled_only():
    from app.vtuber.vseeface_capture_diagnostics import BACKEND_NEEDS_INSTALL, choose_capture_backend

    decision = choose_capture_backend({
        "spout2": {"sender_available": True, "receiver_available": False},
        "virtual_camera": {"registered": False, "requires_admin_registration": True},
    })

    assert decision["preferred_backend"] == "virtual_camera"
    assert decision["status"] == BACKEND_NEEDS_INSTALL
    assert decision["next_action"] == "run_vseeface_camera_install_bat_as_admin"


def test_capture_backend_repairs_stale_virtual_camera_registration():
    from app.vtuber.vseeface_capture_diagnostics import BACKEND_NEEDS_INSTALL, choose_capture_backend

    decision = choose_capture_backend({
        "spout2": {"sender_available": True, "receiver_available": False},
        "virtual_camera": {
            "registered": True,
            "registration_usable": False,
            "registration_stale": True,
            "requires_admin_registration": True,
        },
    })

    assert decision["preferred_backend"] == "virtual_camera"
    assert decision["status"] == BACKEND_NEEDS_INSTALL
    assert decision["reason"] == "vseeface_camera_registered_to_stale_path"
    assert decision["next_action"] == "rerun_vseeface_camera_install_bat_as_admin"


def test_capture_backend_prefers_spout_when_sender_and_receiver_exist():
    from app.vtuber.vseeface_capture_diagnostics import BACKEND_NEEDS_CONFIGURATION, choose_capture_backend

    decision = choose_capture_backend({
        "spout2": {"sender_available": True, "receiver_available": True},
        "virtual_camera": {"registered": False, "requires_admin_registration": True},
    })

    assert decision["preferred_backend"] == "spout2"
    assert decision["status"] == BACKEND_NEEDS_CONFIGURATION
