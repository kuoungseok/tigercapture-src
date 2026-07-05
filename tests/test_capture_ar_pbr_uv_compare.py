from pathlib import Path

from PIL import Image

from tools.capture_ar_pbr_uv_compare import (
    _diff_bbox,
    _image_diff_metrics,
    _make_diff_sheet,
    _make_focus_sheet,
    _parse_crop,
    _write_report,
)


def test_parse_crop_validates_bounds():
    assert _parse_crop("1,2,30,40") == (1, 2, 30, 40)


def test_image_diff_metrics_reports_identical_and_different_images(tmp_path: Path):
    left = tmp_path / "left.png"
    same = tmp_path / "same.png"
    different = tmp_path / "different.png"
    Image.new("RGB", (2, 2), (10, 20, 30)).save(left)
    Image.new("RGB", (2, 2), (10, 20, 30)).save(same)
    Image.new("RGB", (2, 2), (11, 20, 30)).save(different)

    identical = _image_diff_metrics(left, same)
    changed = _image_diff_metrics(left, different)

    assert identical["same_size"] is True
    assert identical["identical"] is True
    assert identical["max_abs_channel_diff"] == 0
    assert changed["same_size"] is True
    assert changed["identical"] is False
    assert changed["max_abs_channel_diff"] == 1


def test_write_report_marks_auto_on_match_and_off_difference(tmp_path: Path):
    auto = tmp_path / "auto.png"
    on = tmp_path / "on.png"
    off = tmp_path / "off.png"
    sheet = tmp_path / "sheet.png"
    report = tmp_path / "report.json"
    Image.new("RGB", (2, 2), (10, 20, 30)).save(auto)
    Image.new("RGB", (2, 2), (10, 20, 30)).save(on)
    Image.new("RGB", (2, 2), (30, 20, 10)).save(off)
    sheet.write_bytes(b"sheet")

    data = _write_report(
        {
            "OFF (old)": off,
            "AUTO (fixed)": auto,
            "ON (forced)": on,
        },
        sheet=sheet,
        report=report,
        asset=tmp_path / "scene.gltf",
        crop_box=(0, 0, 2, 2),
    )

    assert report.exists()
    assert data["verdict"]["auto_matches_forced_on"] is True
    assert data["verdict"]["auto_differs_from_old_off"] is True
    assert data["verdict"]["uv_v_flip_auto_active"] is True


def test_make_diff_sheet_writes_visual_diff_artifact(tmp_path: Path):
    auto = tmp_path / "auto.png"
    on = tmp_path / "on.png"
    off = tmp_path / "off.png"
    diff = tmp_path / "diff.png"
    Image.new("RGB", (2, 2), (10, 20, 30)).save(auto)
    Image.new("RGB", (2, 2), (10, 20, 30)).save(on)
    Image.new("RGB", (2, 2), (30, 20, 10)).save(off)

    _make_diff_sheet(
        {
            "OFF (old)": off,
            "AUTO (fixed)": auto,
            "ON (forced)": on,
        },
        output=diff,
    )

    assert diff.exists()
    assert Image.open(diff).size == (1482, 471)


def test_make_focus_sheet_uses_auto_off_difference_bbox(tmp_path: Path):
    auto = tmp_path / "auto.png"
    on = tmp_path / "on.png"
    off = tmp_path / "off.png"
    focus = tmp_path / "focus.png"
    auto_image = Image.new("RGB", (32, 24), (10, 10, 10))
    on_image = Image.new("RGB", (32, 24), (10, 10, 10))
    off_image = Image.new("RGB", (32, 24), (10, 10, 10))
    for x in range(12, 16):
        for y in range(8, 12):
            off_image.putpixel((x, y), (220, 20, 20))
    auto_image.save(auto)
    on_image.save(on)
    off_image.save(off)

    bbox = _diff_bbox(auto, off, threshold=8, padding=2)
    clamped_bbox = _diff_bbox(auto, off, threshold=-1, padding=-5)
    focus_box = _make_focus_sheet(
        {
            "OFF (old)": off,
            "AUTO (fixed)": auto,
            "ON (forced)": on,
        },
        output=focus,
        threshold=8,
        padding=2,
    )

    assert bbox == (10, 6, 18, 14)
    assert clamped_bbox == (12, 8, 16, 12)
    assert focus_box == bbox
    assert focus.exists()
    assert Image.open(focus).size == (882, 610)
