from __future__ import annotations


def test_media_pool_empty_state_distinguishes_empty_and_filtered():
    from app.ux_feedback import media_pool_empty_state

    empty = media_pool_empty_state(total=0, visible=0)
    filtered = media_pool_empty_state(total=3, visible=0, query="intro", kind_label="Video")
    visible = media_pool_empty_state(total=3, visible=2, kind_label="Audio")

    assert empty.tone == "active"
    assert "Drop media" in empty.title
    assert filtered.tone == "warning"
    assert "intro" in filtered.body
    assert visible.tone == "neutral"
    assert visible.title == "2 of 3 media visible"


def test_scope_status_state_promotes_numeric_scope_summary():
    from app.ux_feedback import scope_status_state

    ok = scope_status_state({
        "warnings": [],
        "luma_ire_p01": 4.0,
        "luma_ire_p99": 96.0,
        "saturation_p95": 0.42,
    })
    warning = scope_status_state({
        "warnings": ["highlight clipping"],
        "luma_ire_p01": 0.0,
        "luma_ire_p99": 100.0,
        "saturation_p95": 0.9,
    })

    assert ok.tone == "success"
    assert "Luma 4.0-96.0 IRE" in ok.body
    assert warning.tone == "warning"
    assert "highlight clipping" in warning.action


def test_failure_state_trims_long_messages():
    from app.ux_feedback import failure_state

    state = failure_state("Export", "x" * 300)

    assert state.tone == "error"
    assert state.title == "Export failed"
    assert len(state.body) <= 180
