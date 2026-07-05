from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import paths
from app.timeline_thumbnail_cache import (
    load_timeline_thumb_cache,
    prepare_timeline_thumb_cache,
    store_timeline_thumb_cache,
    timeline_thumb_cache_dir,
    timeline_thumb_cache_root,
)


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_timeline_thumb_cache_root_uses_default_save_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "default_save_dir", lambda: tmp_path)

    root = timeline_thumb_cache_root()

    assert root == tmp_path / ".cache" / "timeline_thumbs"
    assert root.exists()


def test_timeline_thumb_cache_same_file_metadata_and_height_reuses_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "default_save_dir", lambda: tmp_path / "save")
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"abc")

    first = timeline_thumb_cache_dir(source, thumb_h=48)
    second = timeline_thumb_cache_dir(source, thumb_h=48)

    assert first is not None
    assert second is not None
    assert first == second


def test_timeline_thumb_cache_key_changes_with_thumb_height(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "default_save_dir", lambda: tmp_path / "save")
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"abc")

    small = timeline_thumb_cache_dir(source, thumb_h=48)
    large = timeline_thumb_cache_dir(source, thumb_h=96)

    assert small is not None
    assert large is not None
    assert small != large
    assert small.parent == timeline_thumb_cache_root()


def test_prepare_cache_writes_count_and_load_returns_none_without_frames(tmp_path, monkeypatch):
    _ensure_qapp()
    monkeypatch.setattr(paths, "default_save_dir", lambda: tmp_path / "save")
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"abc")

    prepare_timeline_thumb_cache(source, count=3, thumb_h=48)

    cache_dir = timeline_thumb_cache_dir(source, thumb_h=48)
    assert cache_dir is not None
    assert (cache_dir / "count.txt").read_text(encoding="utf-8") == "3"
    assert load_timeline_thumb_cache(source, thumb_h=48) is None


def test_store_qimage_can_be_loaded_from_timeline_thumb_cache(tmp_path, monkeypatch):
    _ensure_qapp()
    from PySide6.QtGui import QColor, QImage

    monkeypatch.setattr(paths, "default_save_dir", lambda: tmp_path / "save")
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"abc")

    prepare_timeline_thumb_cache(source, count=1, thumb_h=48)
    image = QImage(3, 2, QImage.Format.Format_RGB32)
    image.fill(QColor(20, 40, 60))

    store_timeline_thumb_cache(source, 0, image, thumb_h=48)
    loaded = load_timeline_thumb_cache(source, thumb_h=48)

    assert loaded is not None
    assert len(loaded) == 1
    loaded_image = loaded[0].toImage()
    assert loaded_image.width() == 3
    assert loaded_image.height() == 2
    assert loaded_image.pixelColor(1, 1) == QColor(20, 40, 60)


def test_load_timeline_thumb_cache_returns_none_for_missing_source(tmp_path, monkeypatch):
    _ensure_qapp()
    monkeypatch.setattr(paths, "default_save_dir", lambda: tmp_path / "save")

    assert load_timeline_thumb_cache(tmp_path / "missing.mp4") is None


def test_load_timeline_thumb_cache_returns_none_for_broken_cache(tmp_path, monkeypatch):
    _ensure_qapp()
    monkeypatch.setattr(paths, "default_save_dir", lambda: tmp_path / "save")
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"abc")

    prepare_timeline_thumb_cache(source, count=1, thumb_h=48)
    cache_dir = timeline_thumb_cache_dir(source, thumb_h=48)
    assert cache_dir is not None
    (cache_dir / "0000.png").write_text("not a png", encoding="utf-8")

    assert load_timeline_thumb_cache(source, thumb_h=48) is None


def test_timeline_thumb_cache_returns_none_for_missing_source(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "default_save_dir", lambda: tmp_path / "save")

    assert timeline_thumb_cache_dir(tmp_path / "missing.mp4") is None


def test_timeline_thumb_cache_key_changes_with_file_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "default_save_dir", lambda: tmp_path / "save")
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"abc")
    first = timeline_thumb_cache_dir(source, thumb_h=48)

    source.write_bytes(b"abcdef")
    os.utime(source, None)
    second = timeline_thumb_cache_dir(source, thumb_h=48)

    assert first is not None
    assert second is not None
    assert first != second
