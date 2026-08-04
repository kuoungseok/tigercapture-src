from __future__ import annotations

from PySide6.QtGui import QImage

from app.motion_designer.cache import MotionFrameCache


def _image(width: int, height: int) -> QImage:
    return QImage(width, height, QImage.Format_RGBA8888)


def test_frame_cache_enforces_byte_budget_and_lru_order() -> None:
    cache = MotionFrameCache(capacity=8, max_bytes=800)
    cache.put("first", _image(10, 10))
    cache.put("second", _image(10, 10))
    assert cache.get("first") is not None

    cache.put("third", _image(10, 10))

    assert cache.get("second") is None
    assert cache.get("first") is not None
    assert cache.get("third") is not None
    diagnostics = cache.diagnostics()
    assert diagnostics["size"] == 2
    assert diagnostics["current_bytes"] <= diagnostics["max_bytes"]
    assert diagnostics["hits"] == 3
    assert diagnostics["misses"] == 1
    assert diagnostics["evictions"] == 1


def test_frame_cache_drops_single_frame_larger_than_budget() -> None:
    cache = MotionFrameCache(capacity=8, max_bytes=128)
    cache.put("oversized", _image(10, 10))

    assert len(cache) == 0
    assert cache.diagnostics()["evictions"] == 1


def test_frame_cache_invalidation_releases_accounted_bytes() -> None:
    cache = MotionFrameCache(capacity=8, max_bytes=4096)
    cache.put(("composition-a", 0), _image(10, 10))
    cache.put(("composition-b", 0), _image(10, 10))

    cache.invalidate_composition("composition-a")

    diagnostics = cache.diagnostics()
    assert diagnostics["size"] == 1
    assert diagnostics["current_bytes"] == 400
    assert cache.get(("composition-b", 0)) is not None
