from __future__ import annotations

import struct

import pytest

from app.actions.editor_adapter_motion_aep import MotionAepAdapterMixin
from app.actions.motion_aep_namespace import register_motion_aep_actions
from app.motion_designer.aep import (
    AepParseError,
    AepSafetyLimits,
    inspect_aep_document,
    parse_aep_bytes,
)


def _chunk(tag: str, payload: bytes) -> bytes:
    encoded = tag.encode("ascii") + struct.pack(">I", len(payload)) + payload
    return encoded + (b"\x00" if len(payload) & 1 else b"")


def _list(list_type: str, *children: bytes) -> bytes:
    return _chunk("LIST", list_type.encode("ascii") + b"".join(children))


def _aep(*children: bytes, xmp: bytes = b"") -> bytes:
    body = b"Egg!" + b"".join(children)
    return b"RIFX" + struct.pack(">I", len(body)) + body + xmp


def test_parses_nested_lists_padding_opaque_data_and_xmp() -> None:
    data = _aep(
        _list("Fold", _chunk("Utf8", b"Hero"), _chunk("odd!", b"123")),
        _list("btdk", b"not-a-chunk-stream"),
        xmp=b"<x:xmpmeta>sample</x:xmpmeta>",
    )
    document = parse_aep_bytes(data)

    assert document.root.list_type == "Egg!"
    assert document.root.children[0].list_type == "Fold"
    assert document.root.children[0].children[1].size == 3
    assert document.root.children[1].opaque is True
    assert document.xmp_text.startswith("<x:xmpmeta>")


def test_inspection_finds_paths_and_requires_ae_for_expressions() -> None:
    expression_metadata = bytearray(124)
    expression_metadata[120] = 1
    data = _aep(
        _chunk("tdb4", bytes(expression_metadata)),
        _chunk(
            "Utf8",
            b"expression javascript C:\\shots\\hero.png third-party plugin",
        )
    )
    report = inspect_aep_document(parse_aep_bytes(data))

    assert report["schema"] == "tigerstudio.motion.aep.inspect.v1"
    assert report["compatibility"]["disposition"] == "ae_render_required"
    assert "expressions_require_after_effects_evaluation" in report["compatibility"]["blockers"]
    assert report["assets"]["path_candidates"] == ["C:\\shots\\hero.png"]


def test_rejects_non_aep_truncation_alignment_and_limits() -> None:
    with pytest.raises(AepParseError, match="RIFX"):
        parse_aep_bytes(b"NOPE" + b"\x00" * 12)

    valid = _aep(_chunk("data", b"abcd"))
    with pytest.raises(AepParseError, match="beyond"):
        parse_aep_bytes(valid[:-1])

    with pytest.raises(AepParseError, match="chunk count"):
        parse_aep_bytes(
            _aep(_chunk("one!", b""), _chunk("two!", b"")),
            limits=AepSafetyLimits(max_chunks=2),
        )


def test_parses_known_raw_container_children() -> None:
    wrapped = _chunk("fnam", _chunk("Utf8", b"Display Name"))
    document = parse_aep_bytes(_aep(wrapped))

    fnam = document.root.children[0]
    assert fnam.tag == "fnam"
    assert fnam.children[0].tag == "Utf8"


def test_aep_inspection_action_is_read_only_and_ownerless(tmp_path) -> None:
    source = tmp_path / "sample.aep"
    source.write_bytes(_aep(_chunk("Utf8", b"Tiger Studio")))

    class Adapter(MotionAepAdapterMixin):
        pass

    report = Adapter().motion_aep_inspect(path=str(source))
    assert report["ok"] is True

    class Registry:
        def __init__(self) -> None:
            self.calls = []

        def register_adapter_action(self, *args, **kwargs) -> None:
            self.calls.append((args, kwargs))

    registry = Registry()
    register_motion_aep_actions(registry)
    args, kwargs = registry.calls[0]
    assert args[0] == "motion.aep.inspect"
    assert kwargs["mutating"] is False
    assert kwargs["requires_owner"] is False
