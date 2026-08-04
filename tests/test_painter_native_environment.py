from __future__ import annotations


def test_offscreen_and_scale_overrides_are_not_native_evidence() -> None:
    from app.painter_native_environment import is_native_qt_environment

    assert not is_native_qt_environment("offscreen", {})
    assert not is_native_qt_environment("windows", {"QT_SCALE_FACTOR": "1.5"})
    assert not is_native_qt_environment("windows", {"QT_SCREEN_SCALE_FACTORS": "2"})
    assert is_native_qt_environment("windows", {})


def test_forced_offscreen_is_rejected_even_if_reported_platform_differs() -> None:
    from app.painter_native_environment import is_native_qt_environment

    assert not is_native_qt_environment("windows", {"QT_QPA_PLATFORM": "offscreen"})
