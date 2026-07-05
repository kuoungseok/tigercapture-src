from pathlib import Path

from app.youtube_import import (
    is_youtube_url,
    youtube_format_selector,
    youtube_import_output_dir,
    youtube_output_template,
    youtube_quality_choices,
    youtube_quality_label,
)


def test_is_youtube_url_accepts_standard_and_short_hosts():
    assert is_youtube_url("https://www.youtube.com/watch?v=abc123")
    assert is_youtube_url("https://youtu.be/abc123")
    assert is_youtube_url("https://m.youtube.com/shorts/abc123")


def test_is_youtube_url_rejects_non_youtube_urls():
    assert not is_youtube_url("https://example.com/watch?v=abc123")
    assert not is_youtube_url("file:///C:/tmp/video.mp4")
    assert not is_youtube_url("")


def test_youtube_output_dir_and_template(tmp_path: Path):
    out_dir = youtube_import_output_dir(tmp_path)
    template = youtube_output_template(out_dir)

    assert out_dir.is_dir()
    assert out_dir.name == "YouTube Imports"
    assert "%(title).120B" in template
    assert "%(id)s" in template
    assert template.endswith("%(ext)s")


def test_youtube_quality_choices_include_common_resolutions():
    choices = youtube_quality_choices()
    ids = [preset_id for preset_id, _label in choices]

    assert ids[0] == "auto"
    assert "2160p" in ids
    assert "1080p" in ids
    assert "720p" in ids
    assert youtube_quality_label("2160p") == "4K / 2160p max"


def test_youtube_format_selector_caps_height_when_quality_selected():
    auto_selector = youtube_format_selector("auto")
    capped_selector = youtube_format_selector("1080p")

    assert "height<=1080" in capped_selector
    assert "height<=1080" not in auto_selector
    assert "ba[ext=m4a]" in capped_selector
    assert capped_selector.endswith("/best")
