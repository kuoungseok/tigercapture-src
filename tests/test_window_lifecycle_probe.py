from __future__ import annotations


def _tick(index, *, left: bool, foreground: int, windows: list[dict]):
    return {
        "tick": index,
        "elapsed_ms": index * 33,
        "foreground_hwnd": foreground,
        "cursor": {"x": 100 + index, "y": 200 + index},
        "mouse": {"left": left, "right": False, "middle": False},
        "windows": windows,
    }


def test_window_lifecycle_probe_summary_detects_release_created_window_and_resize():
    from tools.window_lifecycle_probe import summarize_ticks

    old_window = {
        "hwnd": 10,
        "title": "TigerCapture",
        "class_name": "QtWindow",
        "rect": {"left": 0, "top": 0, "right": 100, "bottom": 100, "width": 100, "height": 100},
        "visible": True,
        "minimized": False,
    }
    resized_old_window = {
        **old_window,
        "rect": {"left": 0, "top": 0, "right": 80, "bottom": 80, "width": 80, "height": 80},
    }
    new_window = {
        "hwnd": 20,
        "title": "TigerCapture - New",
        "class_name": "QtWindow",
        "rect": {"left": 10, "top": 10, "right": 300, "bottom": 200, "width": 290, "height": 190},
        "visible": True,
        "minimized": False,
    }

    summary = summarize_ticks(
        [
            _tick(0, left=True, foreground=10, windows=[old_window]),
            _tick(1, left=True, foreground=10, windows=[resized_old_window]),
            _tick(2, left=False, foreground=20, windows=[resized_old_window, new_window]),
        ]
    )

    assert summary["tick_count"] == 3
    assert [row["hwnd"] for row in summary["created_hwnds"]] == [20]
    assert [row["hwnd"] for row in summary["appeared_hwnds"]] == [20]
    assert summary["rect_changes"][0]["hwnd"] == 10
    assert summary["foreground_changes"] == [{"tick": 2, "elapsed_ms": 66, "before": 10, "after": 20}]
    assert summary["left_mouse_transitions"] == [
        {
            "tick": 2,
            "elapsed_ms": 66,
            "button": "left",
            "before": True,
            "after": False,
            "cursor": {"x": 102, "y": 202},
            "foreground_hwnd": 20,
        }
    ]
    assert summary["mouse_release_correlations"] == [
        {
            "release_tick": 2,
            "release_elapsed_ms": 66,
            "cursor": {"x": 102, "y": 202},
            "foreground_hwnd_at_release": 20,
            "appeared_hwnds": [summary["appeared_hwnds"][0]],
            "disappeared_hwnds": [],
            "foreground_changes": [{"tick": 2, "elapsed_ms": 66, "before": 10, "after": 20}],
            "visibility_changes": [],
        }
    ]


def test_window_lifecycle_probe_summary_detects_mid_run_disappeared_window():
    from tools.window_lifecycle_probe import summarize_ticks

    old_window = {
        "hwnd": 10,
        "title": "Tiger Studio",
        "class_name": "Qt6111QWindowIcon",
        "rect": {"left": 0, "top": 0, "right": 100, "bottom": 100, "width": 100, "height": 100},
        "visible": True,
        "minimized": False,
    }
    replacement_window = {
        "hwnd": 20,
        "title": "Tiger Studio",
        "class_name": "Qt6111QWindowOwnDCIcon",
        "rect": {"left": 0, "top": 0, "right": 100, "bottom": 100, "width": 100, "height": 100},
        "visible": True,
        "minimized": False,
    }

    summary = summarize_ticks(
        [
            _tick(0, left=True, foreground=10, windows=[old_window]),
            _tick(1, left=False, foreground=10, windows=[old_window]),
            _tick(2, left=False, foreground=20, windows=[replacement_window]),
            _tick(3, left=False, foreground=20, windows=[replacement_window]),
        ]
    )

    assert [row["hwnd"] for row in summary["appeared_hwnds"]] == [20]
    assert [row["hwnd"] for row in summary["disappeared_hwnds"]] == [10]
    assert summary["mouse_release_correlations"][0]["appeared_hwnds"][0]["hwnd"] == 20
    assert summary["mouse_release_correlations"][0]["disappeared_hwnds"][0]["hwnd"] == 10
