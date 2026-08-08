from __future__ import annotations


def test_brush_response_measurement_passes_every_published_invariant() -> None:
    from tools.measure_painter_brush_response import measure_brush_response

    report = measure_brush_response()

    assert report["scope"] == "painting_only_ui_design_excluded"
    assert report["claim_boundary"]["physical_media_parity"] is False
    assert report["claim_boundary"]["external_brush_engine_pixel_parity"] is False
    assert report["official_sources"]["qt_tablet_event_pressure"] == (
        "https://doc.qt.io/qtforpython-6/PySide6/QtGui/QTabletEvent.html"
    )
    assert report["official_sources"]["rfc7693_blake2"] == (
        "https://www.rfc-editor.org/rfc/rfc7693"
    )
    assert report["official_sources"]["qt_qimage_bounds"] == (
        "https://doc.qt.io/qt-6/qimage.html"
    )
    assert report["official_sources"]["krita_brush_texture"] == (
        "https://docs.krita.org/en/reference_manual/brushes/brush_settings/"
        "texture.html"
    )
    assert report["passed"] is True
    assert all(report["checks"].values())
