"""Small delegate binding helpers for VideoEditorWindow compatibility methods."""
from __future__ import annotations

from importlib import import_module
from typing import Iterable


Binding = tuple[str, str, str, bool]


def bind_imported_delegate_methods(owner_cls: type, bindings: Iterable[Binding]) -> None:
    """Bind legacy VideoEditorWindow method names to focused implementation modules."""
    for owner_attr, module_name, attr_name, as_static in bindings:
        value = getattr(import_module(module_name), attr_name)
        if as_static:
            value = staticmethod(value)
        setattr(owner_cls, owner_attr, value)
