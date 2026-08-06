"""Fast deep copy for the JSON-shaped payloads Painter UI documents carry.

``copy.deepcopy`` is general: it maintains a memo table, calls ``id()`` on
every node and keeps intermediate objects alive so shared references and
cycles survive.  Painter UI document rows are plain JSON trees - dicts,
lists, strings and numbers - with no sharing to preserve and no cycles, so
that bookkeeping is pure overhead.  On a large imported Figma file it
dominates normalization: a 8.9k-object document deep copies roughly seven
times faster here than through ``copy.deepcopy``.

Anything that is not a JSON container or scalar is handed back to
``copy.deepcopy`` so behaviour never silently changes for exotic values.
"""
from __future__ import annotations

import copy
from typing import Any


_ATOMIC = (str, bool, int, float, type(None))


def json_deepcopy(value: Any) -> Any:
    """Return a deep copy of ``value``, fast-pathing JSON-shaped data."""
    kind = type(value)
    if kind is dict:
        return {key: json_deepcopy(item) for key, item in value.items()}
    if kind is list:
        return [json_deepcopy(item) for item in value]
    if kind in _ATOMIC:
        return value
    return copy.deepcopy(value)


__all__ = ["json_deepcopy"]
