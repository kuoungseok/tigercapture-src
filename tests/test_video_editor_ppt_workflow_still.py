from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


class _Player:
    def position(self) -> int:
        return 2500


class _Timeline:
    selected_slide_id = "slide-001"

    def select_slide(self, _slide_id: str) -> None:
        return None


class _Window:
    def __init__(self) -> None:
        self.timeline = _Timeline()
        self.deck = SimpleNamespace(slides=[SimpleNamespace(id="slide-001")])
        self.added_path = ""
        self.selected_element_id = ""

    def add_image_file_to_slide(self, path, **kwargs):
        self.added_path = str(path)
        return SimpleNamespace(id="still-1", kind="image", name="", metadata={})

    def _refresh_selected(self) -> None:
        return None

    def show(self) -> None:
        return None

    def raise_(self) -> None:
        return None

    def activateWindow(self) -> None:
        return None


def test_add_timeline_clip_still_uses_playhead_inside_selected_clip(monkeypatch, tmp_path):
    from app import video_editor_ppt_workflow as workflow
    from app.pptgen import frame_extract

    source = tmp_path / "source.mp4"
    still = tmp_path / "source_still.png"
    owner = SimpleNamespace(
        _player=_Player(),
        _selected_clips=[(1, 10)],
        _ppt_generator_window=_Window(),
        _tracks=[
            SimpleNamespace(
                id=1,
                clips=[
                    SimpleNamespace(
                        id=10,
                        source_path=source,
                        timeline_in_ms=1000,
                        source_in_ms=500,
                        source_out_ms=4500,
                        source_duration_ms=6000,
                    )
                ],
            )
        ],
    )
    captured: dict[str, object] = {}

    def fake_extract_video_still(path: str | Path, *, source_ms: int = 0, output_dir=None) -> Path:
        captured["path"] = str(path)
        captured["source_ms"] = source_ms
        return still

    monkeypatch.setattr(frame_extract, "extract_video_still", fake_extract_video_still)

    result = workflow.add_timeline_clip_still_to_ppt(owner)

    assert result["kind"] == "image"
    assert result["source_path"] == str(still)
    assert captured == {"path": str(source), "source_ms": 2000}
    assert result["source_ms"] == 2000
    assert result["track_id"] == 1
    assert result["clip_id"] == 10
