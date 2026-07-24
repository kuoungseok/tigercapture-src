from __future__ import annotations


from pathlib import Path


def test_painter_reference_board_crud_and_contract(tmp_path: Path) -> None:
    from app.painter_reference_board import (
        add_reference_image,
        default_reference_board,
        delete_reference_image,
        duplicate_reference_image,
        extract_reference_palette,
        reference_board_from_dict,
        sample_reference_color,
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
        rotation_deg=725,
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
    assert ref["rotation_deg"] == 5.0

    board = update_reference_image(
        board,
        "reference:key",
        x_norm=0.25,
        opacity=0.4,
        rotation_deg=-35,
        visible=False,
        locked=True,
    )
    ref = board.to_dict()["references"][0]
    assert ref["x_norm"] == 0.25
    assert ref["opacity"] == 0.4
    assert ref["rotation_deg"] == -35.0
    assert ref["visible"] is False
    assert ref["locked"] is True

    board = duplicate_reference_image(board, "reference:key", offset_x=0.1, offset_y=0.2)
    rows = board.to_dict()["references"]
    assert len(rows) == 2
    assert rows[1]["path"] == rows[0]["path"]
    assert rows[1]["name"].endswith("Copy")
    assert rows[1]["rotation_deg"] == rows[0]["rotation_deg"]

    from PySide6.QtGui import QColor, QImage

    image_path = tmp_path / "reference_palette.png"
    image = QImage(4, 4, QImage.Format.Format_ARGB32)
    image.fill(QColor("#224466"))
    image.setPixelColor(2, 2, QColor("#CC8844"))
    assert image.save(str(image_path), "PNG")
    sample = sample_reference_color(str(image_path), x_norm=0.66, y_norm=0.66)
    assert sample["hex"] == "#CC8844"
    palette = extract_reference_palette(str(image_path), max_colors=3)
    assert palette["color_count"] >= 1
    assert palette["colors"][0]["hex"] in {"#184860", "#C09048"}

    restored = reference_board_from_dict(board.to_dict())
    assert restored.to_dict()["reference_count"] == 2

    board = delete_reference_image(restored, "reference:key")
    assert board.to_dict()["reference_count"] == 1
