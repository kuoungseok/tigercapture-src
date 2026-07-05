from __future__ import annotations


def test_ar_pbr_gl_painter_reuses_pbr_batches_for_static_packet() -> None:
    from app.opengl_preview import _ARPBRDirectGLPainter

    painter = _ARPBRDirectGLPainter()
    vertices = [0.0] * (23 * 3)
    item = {
        "packet_cache_id": "static_packet",
        "pbr_triangle_count": 1,
        "pbr_triangles": [
            {
                "texture": "base.png",
                "maps": {"base": "base.png"},
                "vertices": vertices,
            }
        ],
    }

    first = painter._pbr_batches_for_item(item)
    second = painter._pbr_batches_for_item(item)

    assert first is second
    assert len(first) == 1
    assert first[0]["vertices"] == vertices
    assert painter.vbo_diagnostics()["ar_pbr_pbr_batch_cache_size"] == 1
    assert painter._vbo_cache_key("pbr", item, first[0]["batch_key"], len(vertices), 23) is not None


def test_ar_pbr_gl_painter_keeps_uncached_packets_transient() -> None:
    from app.opengl_preview import _ARPBRDirectGLPainter

    painter = _ARPBRDirectGLPainter()
    item = {
        "pbr_triangle_count": 1,
        "pbr_triangles": [
            {
                "texture": "base.png",
                "maps": {"base": "base.png"},
                "vertices": [0.0] * (23 * 3),
            }
        ],
    }

    first = painter._pbr_batches_for_item(item)
    second = painter._pbr_batches_for_item(item)

    assert first is not second
    assert painter.vbo_diagnostics()["ar_pbr_pbr_batch_cache_size"] == 0
    assert painter._vbo_cache_key("pbr", item, first[0]["batch_key"], 23 * 3, 23) is None
