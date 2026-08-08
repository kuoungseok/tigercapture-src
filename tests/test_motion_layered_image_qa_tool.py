from pathlib import Path

from tools.qa_motion_layered_images import DEFAULT_OUTPUT, ROOT, default_samples


def test_layered_image_qa_defaults_respect_durable_asset_boundary() -> None:
    assert "debugCapture" in DEFAULT_OUTPUT.parts
    samples = default_samples()
    assert len(samples) == 3
    assert {(item.width, item.height) for item in samples} == {
        (640, 360),
        (360, 640),
        (480, 480),
    }
    for item in samples:
        assert item.source.is_file()
        relative = item.source.relative_to(ROOT)
        assert relative.parts[0] in {"resources", "qa_corpus", "sample_assets", "external"}
        assert "debugCapture" not in relative.parts
