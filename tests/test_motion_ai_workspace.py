from pathlib import Path

import pytest

from app.motion_designer.ai_workspace import (
    MotionAIReference,
    MotionAIRequest,
    apply_motion_ai_proposal,
    build_motion_ai_proposal,
    references_from_paths,
)
from app.motion_designer.schema import MotionComposition


def test_motion_ai_request_round_trip_keeps_text_and_image_references() -> None:
    request = MotionAIRequest(
        composition_id="composition_1",
        prompt="Create a fade collage",
        references=[
            MotionAIReference(kind="image", name="look.png", uri="C:/look.png", mime_type="image/png"),
            MotionAIReference(kind="text", name="copy.md", text="Launch night", mime_type="text/markdown"),
        ],
    )
    restored = MotionAIRequest.from_dict(request.to_dict())
    assert restored.prompt == request.prompt
    assert [item.kind for item in restored.references] == ["image", "text"]
    assert restored.references[1].text == "Launch night"


def test_motion_ai_local_proposal_is_reviewable_and_applies_as_one_revision() -> None:
    composition = MotionComposition(width=1280, height=720, duration_ms=4000)
    references = [
        MotionAIReference(kind="image", name="scene.png", uri="C:/scene.png"),
        MotionAIReference(kind="text", name="headline.txt", text="TIGER MOTION"),
    ]
    proposal = build_motion_ai_proposal(
        composition, "배경 이미지를 페이드로 보여주고 제목을 배치", references,
    )
    assert len(proposal.layers) == 2
    image, text = proposal.layers
    assert image.layer_type == "image"
    assert image.source.params["fit"] == "cover"
    assert image.behaviors[0].kind == "fade"
    assert text.layer_type == "text"
    assert text.source.params["text"] == "TIGER MOTION"

    applied = apply_motion_ai_proposal(composition, proposal)
    assert applied.id == composition.id
    assert applied.revision == composition.revision + 1
    assert len(applied.layers) == 2
    assert composition.layers == []


def test_motion_ai_reference_files_accept_images_and_text_and_report_unsupported(tmp_path: Path) -> None:
    image = tmp_path / "reference.png"
    image.write_bytes(b"not-decoded-by-core")
    text = tmp_path / "notes.md"
    text.write_text("Typography notes", encoding="utf-8")
    unsupported = tmp_path / "archive.bin"
    unsupported.write_bytes(b"data")
    references, warnings = references_from_paths([image, text, unsupported])
    assert [item.kind for item in references] == ["image", "text"]
    assert references[1].text == "Typography notes"
    assert len(warnings) == 1


def test_motion_ai_proposal_rejects_cross_composition_apply() -> None:
    first = MotionComposition()
    second = MotionComposition()
    proposal = build_motion_ai_proposal(
        first, references=[MotionAIReference(kind="text", text="Title")],
    )
    with pytest.raises(ValueError, match="different composition"):
        apply_motion_ai_proposal(second, proposal)
