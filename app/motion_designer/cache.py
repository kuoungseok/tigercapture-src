from __future__ import annotations

from collections import OrderedDict
from typing import Hashable


class MotionFrameCache:
    def __init__(self, capacity: int = 120) -> None:
        self.capacity = max(1, int(capacity))
        self._items: OrderedDict[Hashable, object] = OrderedDict()

    def get(self, key):
        value = self._items.get(key)
        if value is not None:
            self._items.move_to_end(key)
        return value

    def put(self, key, value) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)

    def invalidate_composition(self, composition_id: str) -> None:
        self._items = OrderedDict((key, value) for key, value in self._items.items()
                                  if not (isinstance(key, tuple) and key and key[0] == composition_id))

    def clear(self) -> None:
        self._items.clear()
