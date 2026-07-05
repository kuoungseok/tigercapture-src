def test_spine_gl_append_expanded_vertices_batches_triangles():
    from app.spine_editor.spine_gl_renderer import SpineGLViewport

    verts = [
        -1.0, -1.0, 0.0, 0.0,
        1.0, -1.0, 1.0, 0.0,
        1.0, 1.0, 1.0, 1.0,
        -1.0, 1.0, 0.0, 1.0,
    ]
    out = []

    SpineGLViewport._append_expanded_vertices(out, verts, [0, 1, 2, 0, 2, 3])

    assert out == (
        verts[0:4]
        + verts[4:8]
        + verts[8:12]
        + verts[0:4]
        + verts[8:12]
        + verts[12:16]
    )


def test_spine_gl_append_expanded_vertices_skips_invalid_indices():
    from app.spine_editor.spine_gl_renderer import SpineGLViewport

    verts = [
        -1.0, -1.0, 0.0, 0.0,
        1.0, -1.0, 1.0, 0.0,
    ]
    out = []

    SpineGLViewport._append_expanded_vertices(out, verts, [0, 9, -1, 1])

    assert out == verts[0:4] + verts[4:8]


def test_spine_gl_scissor_constant_is_available_for_preview_reset():
    from app.spine_editor.spine_gl_renderer import _GL_SCISSOR_TEST

    assert _GL_SCISSOR_TEST == 0x0C11
