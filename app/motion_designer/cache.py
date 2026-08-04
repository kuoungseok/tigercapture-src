from __future__ import annotations

from collections import OrderedDict
from typing import Hashable


class MotionFrameCache:
    def __init__(self, capacity: int = 120, *, max_bytes: int = 256 * 1024 * 1024) -> None:
        self.capacity = max(1, int(capacity))
        self.max_bytes = max(1, int(max_bytes))
        self._items: OrderedDict[Hashable, tuple[object, int]] = OrderedDict()
        self._current_bytes = 0
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @staticmethod
    def _estimate_bytes(value: object) -> int:
        size_in_bytes = getattr(value, "sizeInBytes", None)
        if callable(size_in_bytes):
            try:
                return max(0, int(size_in_bytes()))
            except (TypeError, ValueError, RuntimeError):
                pass
        bytes_per_line = getattr(value, "bytesPerLine", None)
        height = getattr(value, "height", None)
        if callable(bytes_per_line) and callable(height):
            try:
                return max(0, int(bytes_per_line()) * int(height()))
            except (TypeError, ValueError, RuntimeError):
                pass
        try:
            return max(0, int(value.__sizeof__()))
        except (AttributeError, TypeError, ValueError):
            return 0

    def get(self, key):
        item = self._items.get(key)
        if item is None:
            self._misses += 1
            return None
        self._hits += 1
        self._items.move_to_end(key)
        return item[0]

    def put(self, key, value) -> None:
        previous = self._items.pop(key, None)
        if previous is not None:
            self._current_bytes -= previous[1]
        estimated_bytes = self._estimate_bytes(value)
        self._items[key] = (value, estimated_bytes)
        self._current_bytes += estimated_bytes
        self._items.move_to_end(key)
        while len(self._items) > self.capacity or self._current_bytes > self.max_bytes:
            _, (_, removed_bytes) = self._items.popitem(last=False)
            self._current_bytes -= removed_bytes
            self._evictions += 1

    def invalidate_composition(self, composition_id: str) -> None:
        retained = OrderedDict(
            (key, item) for key, item in self._items.items()
            if not (isinstance(key, tuple) and key and key[0] == composition_id)
        )
        removed_count = len(self._items) - len(retained)
        self._items = retained
        self._current_bytes = sum(item[1] for item in retained.values())
        self._evictions += removed_count

    def clear(self) -> None:
        self._items.clear()
        self._current_bytes = 0

    def __len__(self) -> int:
        return len(self._items)

    def diagnostics(self) -> dict[str, int]:
        return {
            "size": len(self._items),
            "capacity": self.capacity,
            "current_bytes": self._current_bytes,
            "max_bytes": self.max_bytes,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
        }
