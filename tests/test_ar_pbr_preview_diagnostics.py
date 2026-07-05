from __future__ import annotations


def test_ar_pbr_overlay_diagnostics_payload_summarizes_items() -> None:
    from app.ar_pbr.preview_diagnostics import overlay_diagnostics_payload

    payload = overlay_diagnostics_payload(
        items=[
            {
                "track_id": "ar_pbr_001",
                "packet_cache_id": "packet_001",
                "triangle_count": 3,
                "pbr_triangle_count": 2,
                "diagnostics": {"ar_pbr_vbo_cache_hits": 5},
            }
        ],
        painter_diagnostics={"ar_pbr_vbo_cache_hit_rate": 0.75},
        failed=False,
        painter_ready=True,
    )

    assert payload["item_count"] == 1
    assert payload["painter_ready"] is True
    assert payload["vbo"]["ar_pbr_vbo_cache_hit_rate"] == 0.75
    assert payload["items"][0]["packet_cache_id"] == "packet_001"
    assert payload["items"][0]["diagnostics"]["ar_pbr_vbo_cache_hits"] == 5


def test_ar_pbr_preview_diagnostics_payload_prefers_player_packet_id() -> None:
    from app.ar_pbr.preview_diagnostics import preview_diagnostics_payload

    payload = preview_diagnostics_payload(
        tracks=[{"id": "ar_pbr_001"}],
        active_tracks=[{"id": "ar_pbr_001"}],
        player_diagnostics={
            "mode": "gpu_preview",
            "packet_cache_hit": True,
            "packet_cache_id": "player_packet",
            "playback_optimized": True,
        },
        gl_diagnostics={
            "items": [{"packet_cache_id": "gl_packet"}],
        },
        frame_size=(1920, 1080),
        preview_gl_available=True,
    )

    assert payload["track_count"] == 1
    assert payload["active_track_ids"] == ["ar_pbr_001"]
    assert payload["preview_frame_size"] == [1920, 1080]
    assert payload["preview_gl_available"] is True
    assert payload["packet_cache_id"] == "player_packet"
    assert payload["packet_cache_hit"] is True
    assert payload["playback_optimized"] is True
    assert payload["renderer_mode"] == "gpu_preview"


def test_ar_pbr_preview_diagnostics_payload_falls_back_to_gl_packet_id() -> None:
    from app.ar_pbr.preview_diagnostics import preview_diagnostics_payload

    payload = preview_diagnostics_payload(
        tracks=[],
        active_tracks=[],
        player_diagnostics={},
        gl_diagnostics={"items": [{"packet_cache_id": "gl_packet"}]},
        frame_size=None,
        preview_gl_available=False,
    )

    assert payload["packet_cache_id"] == "gl_packet"
    assert payload["preview_frame_size"] == [0, 0]
