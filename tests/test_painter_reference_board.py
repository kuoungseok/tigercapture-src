from __future__ import annotations


def test_painter_reference_board_crud_and_contract() -> None:
    from app.painter_reference_board import (
        add_reference_image,
        default_reference_board,
        delete_reference_image,
        duplicate_reference_image,
        reference_board_from_dict,
        update_reference_image,
    )

    board = add_reference_image(
        default_reference_board(),
        reference_id="reference:key",
        path="E:/refs/key.png",
        name="Key Art",
        x_norm=-1,
        y_norm=2,
        width_norm=9,
        height_norm=0.001,
        opacity=4,
    )
    payload = board.to_dict()
    assert payload["schema"] == "tigerstudio.painter.reference_board.v1"
    assert payload["reference_count"] == 1
    assert payload["non_destructive"] is True
    assert payload["exported_by_default"] is False
    ref = payload["references"][0]
    assert ref["x_norm"] == 0.0
    assert ref["y_norm"] == 1.0
    assert ref["width_norm"] == 1.0
    assert ref["height_norm"] == 0.02
    assert ref["opacity"] == 1.0

    board = update_reference_image(board, "reference:key", x_norm=0.25, opacity=0.4, visible=False)
    ref = board.to_dict()["references"][0]
    assert ref["x_norm"] == 0.25
    assert ref["opacity"] == 0.4
    assert ref["visible"] is False

    board = duplicate_reference_image(board, "reference:key", offset_x=0.1, offset_y=0.2)
    rows = board.to_dict()["references"]
    assert len(rows) == 2
    assert rows[1]["path"] == rows[0]["path"]
    assert rows[1]["name"].endswith("Copy")

    restored = reference_board_from_dict(board.to_dict())
    assert restored.to_dict()["reference_count"] == 2

    board = delete_reference_image(restored, "reference:key")
    assert board.to_dict()["reference_count"] == 1
