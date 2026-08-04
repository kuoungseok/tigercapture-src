from app.painter_ui_creation_hierarchy import creation_parent_frame_id
from app.painter_ui_document import add_ui_object, create_ui_document


def test_creation_chooses_deepest_frame_under_new_shape() -> None:
    document = create_ui_document(1440, 900)
    document, outer = add_ui_object(
        document,
        kind="frame",
        name="Desktop",
        x=100,
        y=100,
        width=900,
        height=600,
    )
    document, inner = add_ui_object(
        document,
        kind="frame",
        name="Card",
        parent_id=outer["id"],
        x=240,
        y=220,
        width=360,
        height=260,
    )

    assert creation_parent_frame_id(
        document,
        x=300,
        y=280,
        width=120,
        height=80,
    ) == inner["id"]


def test_creation_outside_frames_stays_at_canvas_root() -> None:
    document = create_ui_document(1440, 900)
    document, _frame = add_ui_object(
        document,
        kind="frame",
        name="Phone",
        x=100,
        y=100,
        width=300,
        height=600,
    )

    assert creation_parent_frame_id(
        document,
        x=700,
        y=150,
        width=100,
        height=100,
    ) == ""
