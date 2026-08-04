from __future__ import annotations


def test_empty_or_partial_tablet_event_corpus_cannot_pass() -> None:
    from app.painter_tablet_capture import summarize_tablet_events

    assert summarize_tablet_events([])["required_sequence_captured"] is False
    partial = [
        {"event_type": "TabletPress", "pressure": 0.4, "device": {"name": "pen", "system_id": 1}},
        {"event_type": "TabletMove", "pressure": 0.8, "device": {"name": "pen", "system_id": 1}},
    ]
    assert summarize_tablet_events(partial)["required_sequence_captured"] is False


def test_complete_real_event_shape_is_summarized_without_axis_assumptions() -> None:
    from app.painter_tablet_capture import summarize_tablet_events

    base = {
        "pressure": 0.0,
        "x_tilt_degrees": 0.0,
        "y_tilt_degrees": 0.0,
        "rotation_degrees": 0.0,
        "tangential_pressure": 0.0,
        "device": {"name": "pen", "system_id": 4, "pointer_type": "Pen"},
    }
    report = summarize_tablet_events([
        {**base, "event_type": "TabletPress"},
        {**base, "event_type": "TabletMove", "pressure": 0.75},
        {**base, "event_type": "TabletRelease"},
    ])
    assert report["required_sequence_captured"] is True
    assert report["pressure_range"] == [0.0, 0.75]
    assert report["tilt_observed"] is False
