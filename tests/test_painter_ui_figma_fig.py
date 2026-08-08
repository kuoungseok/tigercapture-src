"""End-to-end coverage for the native Figma ``.fig`` reader.

No redistributable ``.fig`` sample exists (the format is proprietary and the
public parser projects ship none), so these tests build real binaries with a
Kiwi encoder written against the same reference specification as the decoder.
Encoding independently and decoding back proves the wire format rather than the
decoder agreeing with itself.
"""
from __future__ import annotations

import io
import math
import struct
import zipfile
import zlib

import pytest

from app.painter_ui_figma import PainterUIFigmaError, import_fig_file
from app.painter_ui_figma_fig import (
    PainterUIFigError,
    decode_fig_payload,
    read_fig_archive,
)
from app.painter_ui_figma_fig_rest import fig_archive_to_rest_payload, fig_guid_to_id
from app.painter_ui_figma_fig_vector import (
    VectorNetworkError,
    parse_vector_network,
    vector_network_fill_paths,
)
from app.painter_ui_figma_kiwi import KiwiByteBuffer, KiwiError, decode_binary_schema

# -- Kiwi encoder (mirror of app.painter_ui_figma_kiwi) ------------------

_BUILTINS = ("bool", "byte", "int", "uint", "float", "string", "int64", "uint64")
_KINDS = ("ENUM", "STRUCT", "MESSAGE")


class _Writer:
    def __init__(self) -> None:
        self.data = bytearray()

    def byte(self, value: int) -> None:
        self.data.append(value & 0xFF)

    def var_uint(self, value: int) -> None:
        value &= 0xFFFFFFFF
        while True:
            chunk = value & 127
            value >>= 7
            self.byte(chunk | 128 if value else chunk)
            if not value:
                break

    def var_int(self, value: int) -> None:
        self.var_uint(((value << 1) ^ (value >> 31)) & 0xFFFFFFFF)

    def var_uint64(self, value: int) -> None:
        value &= 0xFFFFFFFFFFFFFFFF
        for _ in range(8):
            if value <= 127:
                break
            self.byte((value & 127) | 128)
            value >>= 7
        self.byte(value & 0xFF)

    def var_int64(self, value: int) -> None:
        self.var_uint64(~(value << 1) if value < 0 else value << 1)

    def var_float(self, value: float) -> None:
        (bits,) = struct.unpack("<I", struct.pack("<f", value))
        bits = ((bits >> 23) | (bits << 9)) & 0xFFFFFFFF
        if (bits & 255) == 0:
            self.byte(0)
            return
        self.data.extend(struct.pack("<I", bits))

    def string(self, value: str) -> None:
        self.data.extend(value.encode("utf-8"))
        self.byte(0)

    def byte_array(self, value: bytes) -> None:
        self.var_uint(len(value))
        self.data.extend(value)


def _encode_schema(definitions: list[dict]) -> bytes:
    index = {definition["name"]: position for position, definition in enumerate(definitions)}
    writer = _Writer()
    writer.var_uint(len(definitions))
    for definition in definitions:
        writer.string(definition["name"])
        writer.byte(_KINDS.index(definition["kind"]))
        fields = definition["fields"]
        writer.var_uint(len(fields))
        for field in fields:
            writer.string(field["name"])
            if definition["kind"] == "ENUM":
                writer.var_int(0)
            elif field["type"] in _BUILTINS:
                writer.var_int(~_BUILTINS.index(field["type"]))
            else:
                writer.var_int(index[field["type"]])
            writer.byte(1 if field.get("array") else 0)
            writer.var_uint(field["value"])
    return bytes(writer.data)


class _MessageEncoder:
    def __init__(self, definitions: list[dict]) -> None:
        self.by_name = {definition["name"]: definition for definition in definitions}

    def encode(self, name: str, value: dict) -> bytes:
        writer = _Writer()
        self._definition(writer, name, value)
        return bytes(writer.data)

    def _definition(self, writer: _Writer, name: str, value: dict) -> None:
        definition = self.by_name[name]
        if definition["kind"] == "MESSAGE":
            for field in definition["fields"]:
                if field["name"] not in value:
                    continue
                writer.var_uint(field["value"])
                self._field(writer, field, value[field["name"]])
            writer.var_uint(0)
            return
        for field in definition["fields"]:
            self._field(writer, field, value.get(field["name"], 0))

    def _field(self, writer: _Writer, field: dict, value) -> None:
        if field.get("array"):
            if field["type"] == "byte":
                writer.byte_array(bytes(value))
                return
            writer.var_uint(len(value))
            for entry in value:
                self._value(writer, field["type"], entry)
            return
        self._value(writer, field["type"], value)

    def _value(self, writer: _Writer, type_: str, value) -> None:
        if type_ == "bool":
            writer.byte(1 if value else 0)
        elif type_ == "byte":
            writer.byte(int(value))
        elif type_ == "int":
            writer.var_int(int(value))
        elif type_ == "uint":
            writer.var_uint(int(value))
        elif type_ == "float":
            writer.var_float(float(value))
        elif type_ == "string":
            writer.string(str(value))
        elif type_ == "int64":
            writer.var_int64(int(value))
        elif type_ == "uint64":
            writer.var_uint64(int(value))
        else:
            definition = self.by_name[type_]
            if definition["kind"] == "ENUM":
                names = {field["name"]: field["value"] for field in definition["fields"]}
                writer.var_uint(names[str(value)])
            else:
                self._definition(writer, type_, value)


# -- A miniature stand-in for Figma's embedded schema --------------------

SCHEMA_DEFINITIONS: list[dict] = [
    {
        "name": "NodeType",
        "kind": "ENUM",
        "fields": [
            {"name": "DOCUMENT", "type": None, "value": 0},
            {"name": "CANVAS", "type": None, "value": 1},
            {"name": "FRAME", "type": None, "value": 2},
            {"name": "ROUNDED_RECTANGLE", "type": None, "value": 3},
            {"name": "TEXT", "type": None, "value": 4},
            {"name": "SYMBOL", "type": None, "value": 5},
            {"name": "STAMP", "type": None, "value": 6},
        ],
    },
    {
        "name": "PaintType",
        "kind": "ENUM",
        "fields": [
            {"name": "SOLID", "type": None, "value": 0},
            {"name": "GRADIENT_LINEAR", "type": None, "value": 1},
            {"name": "IMAGE", "type": None, "value": 2},
        ],
    },
    {
        "name": "GUID",
        "kind": "STRUCT",
        "fields": [
            {"name": "sessionID", "type": "uint", "value": 0},
            {"name": "localID", "type": "uint", "value": 0},
        ],
    },
    {
        "name": "Vector",
        "kind": "STRUCT",
        "fields": [
            {"name": "x", "type": "float", "value": 0},
            {"name": "y", "type": "float", "value": 0},
        ],
    },
    {
        "name": "Matrix",
        "kind": "STRUCT",
        "fields": [
            {"name": "m00", "type": "float", "value": 0},
            {"name": "m01", "type": "float", "value": 0},
            {"name": "m02", "type": "float", "value": 0},
            {"name": "m10", "type": "float", "value": 0},
            {"name": "m11", "type": "float", "value": 0},
            {"name": "m12", "type": "float", "value": 0},
        ],
    },
    {
        "name": "Color",
        "kind": "STRUCT",
        "fields": [
            {"name": "r", "type": "float", "value": 0},
            {"name": "g", "type": "float", "value": 0},
            {"name": "b", "type": "float", "value": 0},
            {"name": "a", "type": "float", "value": 0},
        ],
    },
    {
        "name": "ParentIndex",
        "kind": "STRUCT",
        "fields": [
            {"name": "guid", "type": "GUID", "value": 0},
            {"name": "position", "type": "string", "value": 0},
        ],
    },
    {
        "name": "ColorStop",
        "kind": "STRUCT",
        "fields": [
            {"name": "color", "type": "Color", "value": 0},
            {"name": "position", "type": "float", "value": 0},
        ],
    },
    {
        "name": "Image",
        "kind": "MESSAGE",
        "fields": [{"name": "hash", "type": "byte", "array": True, "value": 1}],
    },
    {
        "name": "Paint",
        "kind": "MESSAGE",
        "fields": [
            {"name": "type", "type": "PaintType", "value": 1},
            {"name": "color", "type": "Color", "value": 2},
            {"name": "opacity", "type": "float", "value": 3},
            {"name": "visible", "type": "bool", "value": 4},
            {"name": "image", "type": "Image", "value": 5},
            {"name": "imageScaleMode", "type": "string", "value": 6},
            {"name": "stops", "type": "ColorStop", "array": True, "value": 7},
            {"name": "transform", "type": "Matrix", "value": 8},
        ],
    },
    {
        "name": "TextData",
        "kind": "MESSAGE",
        "fields": [{"name": "characters", "type": "string", "value": 1}],
    },
    {
        "name": "NodeChange",
        "kind": "MESSAGE",
        "fields": [
            {"name": "guid", "type": "GUID", "value": 1},
            {"name": "parentIndex", "type": "ParentIndex", "value": 2},
            {"name": "type", "type": "NodeType", "value": 3},
            {"name": "name", "type": "string", "value": 4},
            {"name": "visible", "type": "bool", "value": 5},
            {"name": "opacity", "type": "float", "value": 6},
            {"name": "transform", "type": "Matrix", "value": 7},
            {"name": "size", "type": "Vector", "value": 8},
            {"name": "fillPaints", "type": "Paint", "array": True, "value": 9},
            {"name": "cornerRadius", "type": "float", "value": 10},
            {"name": "textData", "type": "TextData", "value": 11},
            {"name": "fontSize", "type": "float", "value": 12},
            {"name": "stackMode", "type": "string", "value": 13},
            {"name": "stackSpacing", "type": "float", "value": 14},
            {"name": "stackPrimarySizing", "type": "string", "value": 15},
            {"name": "stackCounterSizing", "type": "string", "value": 16},
            {"name": "stackPrimaryAlignItems", "type": "string", "value": 17},
            {"name": "vectorData", "type": "VectorData", "value": 18},
        ],
    },
    {
        "name": "Message",
        "kind": "MESSAGE",
        "fields": [
            {"name": "nodeChanges", "type": "NodeChange", "array": True, "value": 1},
            {"name": "fileName", "type": "string", "value": 2},
            {"name": "blobs", "type": "Blob", "array": True, "value": 3},
        ],
    },
]

# Declared after the list so the forward references above stay readable; the
# binary schema binds types by index, so order only has to be self-consistent.
SCHEMA_DEFINITIONS.insert(
    len(SCHEMA_DEFINITIONS) - 1,
    {
        "name": "VectorData",
        "kind": "MESSAGE",
        "fields": [
            {"name": "vectorNetworkBlob", "type": "uint", "value": 1},
            {"name": "normalizedSize", "type": "Vector", "value": 2},
        ],
    },
)
SCHEMA_DEFINITIONS.insert(
    len(SCHEMA_DEFINITIONS) - 1,
    {
        "name": "Blob",
        "kind": "STRUCT",
        "fields": [{"name": "bytes", "type": "byte", "array": True, "value": 0}],
    },
)


def _guid(local: int, session: int = 0) -> dict:
    return {"sessionID": session, "localID": local}


def _matrix(x: float = 0.0, y: float = 0.0) -> dict:
    return {"m00": 1.0, "m01": 0.0, "m02": x, "m10": 0.0, "m11": 1.0, "m12": y}


def _sample_message() -> dict:
    solid = {
        "type": "SOLID",
        "color": {"r": 0.25, "g": 0.5, "b": 1.0, "a": 1.0},
        "opacity": 1.0,
        "visible": True,
    }
    return {
        "fileName": "Fixture File",
        "nodeChanges": [
            {"guid": _guid(0), "type": "DOCUMENT", "name": "Document"},
            {
                "guid": _guid(1),
                "parentIndex": {"guid": _guid(0), "position": "!"},
                "type": "CANVAS",
                "name": "Page 1",
            },
            {
                "guid": _guid(2),
                "parentIndex": {"guid": _guid(1), "position": "!"},
                "type": "FRAME",
                "name": "Card",
                "visible": True,
                "opacity": 1.0,
                "transform": _matrix(100.0, 50.0),
                "size": {"x": 320.0, "y": 200.0},
                "fillPaints": [solid],
                "stackMode": "VERTICAL",
                "stackSpacing": 12.0,
            },
            {
                "guid": _guid(3),
                "parentIndex": {"guid": _guid(2), "position": "!"},
                "type": "ROUNDED_RECTANGLE",
                "name": "Swatch",
                "visible": True,
                "opacity": 1.0,
                "transform": _matrix(10.0, 10.0),
                "size": {"x": 64.0, "y": 64.0},
                "fillPaints": [solid],
                "cornerRadius": 8.0,
            },
            {
                "guid": _guid(4),
                "parentIndex": {"guid": _guid(2), "position": '"'},
                "type": "TEXT",
                "name": "Label",
                "visible": True,
                "opacity": 1.0,
                "transform": _matrix(10.0, 90.0),
                "size": {"x": 200.0, "y": 24.0},
                "textData": {"characters": "안녕 Figma"},
                "fontSize": 18.0,
            },
        ],
    }


def _zstd_compress(raw: bytes) -> bytes:
    """Compress with whichever zstd backend this interpreter offers."""

    try:
        from compression import zstd  # Python 3.14+ standard library
    except ImportError:
        pass
    else:
        return zstd.compress(raw)
    try:
        import zstandard
    except ImportError:
        pytest.skip("no zstd backend available (Python < 3.14 without zstandard)")
    return zstandard.ZstdCompressor().compress(raw)


def _build_payload(
    message: dict | None = None,
    *,
    prelude: bytes = b"fig-kiwi",
    version: int = 24,
    zstd_message: bool = False,
) -> bytes:
    schema_bytes = _encode_schema(SCHEMA_DEFINITIONS)
    encoder = _MessageEncoder(SCHEMA_DEFINITIONS)
    message_bytes = encoder.encode("Message", message if message is not None else _sample_message())

    def deflate(raw: bytes) -> bytes:
        compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
        return compressor.compress(raw) + compressor.flush()

    schema_chunk = deflate(schema_bytes)
    message_chunk = _zstd_compress(message_bytes) if zstd_message else deflate(message_bytes)

    out = bytearray(prelude)
    out.extend(struct.pack("<I", version))
    for chunk in (schema_chunk, message_chunk):
        out.extend(struct.pack("<I", len(chunk)))
        out.extend(chunk)
    return bytes(out)


_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _build_zip(payload: bytes, *, images: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("canvas.fig", payload)
        archive.writestr("meta.json", '{"file_name": "Zipped Fixture"}')
        archive.writestr("thumbnail.png", _PNG)
        for name, blob in (images or {}).items():
            archive.writestr(f"images/{name}", blob)
    return buffer.getvalue()


# -- Kiwi primitives -----------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [0, 1, 127, 128, 300, 65535, 2**31 - 1, 2**32 - 1],
)
def test_var_uint_round_trip(value: int) -> None:
    writer = _Writer()
    writer.var_uint(value)
    assert KiwiByteBuffer(bytes(writer.data)).read_var_uint() == value


@pytest.mark.parametrize("value", [0, 1, -1, 63, -64, 2**31 - 1, -(2**31)])
def test_var_int_round_trip(value: int) -> None:
    writer = _Writer()
    writer.var_int(value)
    assert KiwiByteBuffer(bytes(writer.data)).read_var_int() == value


@pytest.mark.parametrize("value", [0.0, 1.0, -1.0, 0.5, 1234.5, -0.125, 3.4028234663852886e38])
def test_var_float_round_trip(value: float) -> None:
    writer = _Writer()
    writer.var_float(value)
    decoded = KiwiByteBuffer(bytes(writer.data)).read_var_float()
    assert decoded == pytest.approx(value, rel=1e-6, abs=1e-9)


def test_var_float_zero_is_a_single_byte() -> None:
    writer = _Writer()
    writer.var_float(0.0)
    assert len(writer.data) == 1


@pytest.mark.parametrize("value", [0, 1, 2**40, 2**63 - 1, 2**64 - 1])
def test_var_uint64_round_trip(value: int) -> None:
    writer = _Writer()
    writer.var_uint64(value)
    assert KiwiByteBuffer(bytes(writer.data)).read_var_uint64() == value


@pytest.mark.parametrize("value", [0, 1, -1, 2**62, -(2**62)])
def test_var_int64_round_trip(value: int) -> None:
    writer = _Writer()
    writer.var_int64(value)
    assert KiwiByteBuffer(bytes(writer.data)).read_var_int64() == value


def test_string_round_trip_handles_non_ascii() -> None:
    writer = _Writer()
    writer.string("한글 Figma 🎨")
    assert KiwiByteBuffer(bytes(writer.data)).read_string() == "한글 Figma 🎨"


def test_binary_schema_round_trip() -> None:
    schema = decode_binary_schema(_encode_schema(SCHEMA_DEFINITIONS))
    assert [definition["name"] for definition in SCHEMA_DEFINITIONS] == schema.names
    node_change = schema.definition("NodeChange")
    assert node_change is not None
    assert node_change.kind == "MESSAGE"
    fills = next(field for field in node_change.fields if field.name == "fillPaints")
    assert fills.type == "Paint"
    assert fills.is_array is True
    node_type = schema.definition("NodeType")
    assert node_type is not None
    assert node_type.enum_name(3) == "ROUNDED_RECTANGLE"


def test_unknown_message_field_is_rejected() -> None:
    schema = decode_binary_schema(_encode_schema(SCHEMA_DEFINITIONS))
    writer = _Writer()
    writer.var_uint(99)  # no such field id on Message
    with pytest.raises(KiwiError):
        schema.decode(bytes(writer.data))


# -- Container -----------------------------------------------------------


def test_decode_bare_payload() -> None:
    message, schema, version = decode_fig_payload(_build_payload())
    assert version == 24
    assert message["fileName"] == "Fixture File"
    assert len(message["nodeChanges"]) == 5
    assert schema.definition("Message") is not None


def test_decode_zstd_message_chunk() -> None:
    message, _schema, _version = decode_fig_payload(_build_payload(zstd_message=True))
    assert len(message["nodeChanges"]) == 5


def test_figjam_prelude_is_accepted() -> None:
    message, _schema, _version = decode_fig_payload(_build_payload(prelude=b"fig-jam."))
    assert message["fileName"] == "Fixture File"


def test_bad_prelude_is_rejected() -> None:
    payload = bytearray(_build_payload())
    payload[:8] = b"not-fig!"
    with pytest.raises(PainterUIFigError, match="prelude"):
        decode_fig_payload(bytes(payload))


def test_truncated_chunk_is_rejected() -> None:
    payload = _build_payload()
    with pytest.raises(PainterUIFigError, match="exceeds"):
        decode_fig_payload(payload[: len(payload) - 16])


def test_read_zip_container_collects_images_and_meta(tmp_path) -> None:
    target = tmp_path / "sample.fig"
    target.write_bytes(_build_zip(_build_payload(), images={"abc123": _PNG}))
    archive = read_fig_archive(target)
    assert archive.version == 24
    assert archive.meta["file_name"] == "Zipped Fixture"
    assert archive.images == {"abc123": _PNG}
    assert len(archive.node_changes) == 5


def test_read_bare_container(tmp_path) -> None:
    target = tmp_path / "bare.fig"
    target.write_bytes(_build_payload())
    assert len(read_fig_archive(target).node_changes) == 5


def test_zip_without_canvas_entry_is_rejected(tmp_path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("meta.json", "{}")
    target = tmp_path / "broken.fig"
    target.write_bytes(buffer.getvalue())
    with pytest.raises(PainterUIFigError, match="canvas.fig"):
        read_fig_archive(target)


# -- REST translation ----------------------------------------------------


def _rest_payload(tmp_path, message: dict | None = None) -> dict:
    target = tmp_path / "sample.fig"
    target.write_bytes(_build_payload(message))
    payload, _report = fig_archive_to_rest_payload(read_fig_archive(target))
    return payload


def _find(node: dict, name: str) -> dict:
    if node.get("name") == name:
        return node
    for child in node.get("children", []):
        found = _find(child, name)
        if found:
            return found
    return {}


def test_guid_renders_rest_node_id() -> None:
    assert fig_guid_to_id({"sessionID": 3, "localID": 42}) == "3:42"
    assert fig_guid_to_id(None) == ""


def test_tree_is_rebuilt_from_parent_index(tmp_path) -> None:
    payload = _rest_payload(tmp_path)
    document = payload["document"]
    assert document["type"] == "DOCUMENT"
    page = document["children"][0]
    assert page["type"] == "CANVAS"
    assert page["name"] == "Page 1"
    card = page["children"][0]
    assert card["type"] == "FRAME"
    assert [child["name"] for child in card["children"]] == ["Swatch", "Label"]


def test_transforms_compose_into_absolute_bounds(tmp_path) -> None:
    payload = _rest_payload(tmp_path)
    card = _find(payload["document"], "Card")
    swatch = _find(payload["document"], "Swatch")
    assert card["absoluteBoundingBox"] == pytest.approx(
        {"x": 100.0, "y": 50.0, "width": 320.0, "height": 200.0}
    )
    # The child sits at (10, 10) inside a frame translated to (100, 50).
    assert swatch["absoluteBoundingBox"] == pytest.approx(
        {"x": 110.0, "y": 60.0, "width": 64.0, "height": 64.0}
    )
    assert swatch["relativeTransform"] == [[1.0, 0.0, 10.0], [0.0, 1.0, 10.0]]


def test_rotation_is_reported_in_degrees(tmp_path) -> None:
    message = _sample_message()
    angle = math.radians(30.0)
    message["nodeChanges"][3]["transform"] = {
        "m00": math.cos(angle),
        "m01": -math.sin(angle),
        "m02": 10.0,
        "m10": math.sin(angle),
        "m11": math.cos(angle),
        "m12": 10.0,
    }
    payload = _rest_payload(tmp_path, message)
    swatch = _find(payload["document"], "Swatch")
    assert swatch["rotation"] == pytest.approx(30.0, abs=1e-4)
    # A rotated square grows its axis-aligned bounds.
    assert swatch["absoluteBoundingBox"]["width"] == pytest.approx(64.0 * (math.cos(angle) + math.sin(angle)), abs=1e-3)


def test_node_types_and_paints_are_translated(tmp_path) -> None:
    payload = _rest_payload(tmp_path)
    swatch = _find(payload["document"], "Swatch")
    assert swatch["type"] == "RECTANGLE"  # from internal ROUNDED_RECTANGLE
    assert swatch["cornerRadius"] == pytest.approx(8.0)
    fill = swatch["fills"][0]
    assert fill["type"] == "SOLID"
    assert fill["color"] == pytest.approx({"r": 0.25, "g": 0.5, "b": 1.0, "a": 1.0})


def test_text_and_auto_layout_are_translated(tmp_path) -> None:
    payload = _rest_payload(tmp_path)
    label = _find(payload["document"], "Label")
    assert label["type"] == "TEXT"
    assert label["characters"] == "안녕 Figma"
    assert label["style"]["fontSize"] == pytest.approx(18.0)
    card = _find(payload["document"], "Card")
    assert card["layoutMode"] == "VERTICAL"
    assert card["itemSpacing"] == pytest.approx(12.0)


@pytest.mark.parametrize(
    ("internal", "expected"),
    [
        ("RESIZE_TO_FIT", "AUTO"),
        # Figma's StackSize enum has a third member; both hug variants must
        # become AUTO or a hug frame imports as a fixed-size frame.
        ("RESIZE_TO_FIT_WITH_IMPLICIT_SIZE", "AUTO"),
        ("FIXED", "FIXED"),
    ],
)
def test_stack_sizing_covers_both_hug_variants(tmp_path, internal: str, expected: str) -> None:
    message = _sample_message()
    message["nodeChanges"][2]["stackPrimarySizing"] = internal
    message["nodeChanges"][2]["stackCounterSizing"] = internal
    payload = _rest_payload(tmp_path, message)
    card = _find(payload["document"], "Card")
    assert card["primaryAxisSizingMode"] == expected
    assert card["counterAxisSizingMode"] == expected


def test_space_evenly_is_downgraded_and_reported(tmp_path) -> None:
    message = _sample_message()
    # REST primaryAxisAlignItems has no SPACE_EVENLY member.
    message["nodeChanges"][2]["stackPrimaryAlignItems"] = "SPACE_EVENLY"
    target = tmp_path / "evenly.fig"
    target.write_bytes(_build_payload(message))
    payload, report = fig_archive_to_rest_payload(read_fig_archive(target))
    card = _find(payload["document"], "Card")
    assert card["primaryAxisAlignItems"] == "SPACE_BETWEEN"
    assert "fig_stack_justify_downgraded:SPACE_EVENLY" in report["warnings"]


def test_supported_stack_justify_passes_through(tmp_path) -> None:
    message = _sample_message()
    message["nodeChanges"][2]["stackPrimaryAlignItems"] = "SPACE_BETWEEN"
    payload = _rest_payload(tmp_path, message)
    assert _find(payload["document"], "Card")["primaryAxisAlignItems"] == "SPACE_BETWEEN"


def test_gradient_handles_are_recovered_from_the_matrix(tmp_path) -> None:
    message = _sample_message()
    black = {"r": 0.0, "g": 0.0, "b": 0.0, "a": 1.0}
    white = {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0}
    # Figma stores normalized-node-space -> gradient-space; REST publishes the
    # inverse as handles. A half-width gradient starting at x=0.5 inverts to
    # handles at (0.5, 0), (1, 0) and (0.5, 1).
    message["nodeChanges"][3]["fillPaints"] = [
        {
            "type": "GRADIENT_LINEAR",
            "opacity": 1.0,
            "visible": True,
            "stops": [{"color": black, "position": 0.0}, {"color": white, "position": 1.0}],
            "transform": {"m00": 2.0, "m01": 0.0, "m02": -1.0, "m10": 0.0, "m11": 1.0, "m12": 0.0},
        }
    ]
    payload = _rest_payload(tmp_path, message)
    fill = _find(payload["document"], "Swatch")["fills"][0]
    assert fill["type"] == "GRADIENT_LINEAR"
    assert [stop["position"] for stop in fill["gradientStops"]] == pytest.approx([0.0, 1.0])
    handles = fill["gradientHandlePositions"]
    assert handles[0] == pytest.approx({"x": 0.5, "y": 0.0})
    assert handles[1] == pytest.approx({"x": 1.0, "y": 0.0})
    assert handles[2] == pytest.approx({"x": 0.5, "y": 1.0})


def test_singular_gradient_matrix_omits_handles(tmp_path) -> None:
    message = _sample_message()
    message["nodeChanges"][3]["fillPaints"] = [
        {
            "type": "GRADIENT_LINEAR",
            "opacity": 1.0,
            "visible": True,
            "stops": [],
            # A degenerate matrix has no inverse and must not raise.
            "transform": {"m00": 0.0, "m01": 0.0, "m02": 0.0, "m10": 0.0, "m11": 0.0, "m12": 0.0},
        }
    ]
    payload = _rest_payload(tmp_path, message)
    fill = _find(payload["document"], "Swatch")["fills"][0]
    assert "gradientHandlePositions" not in fill


def test_image_paint_carries_a_hex_image_ref(tmp_path) -> None:
    message = _sample_message()
    message["nodeChanges"][3]["fillPaints"] = [
        {
            "type": "IMAGE",
            "opacity": 1.0,
            "visible": True,
            "image": {"hash": bytes.fromhex("abcdef0123")},
            "imageScaleMode": "FILL",
        }
    ]
    payload = _rest_payload(tmp_path, message)
    fill = _find(payload["document"], "Swatch")["fills"][0]
    assert fill["imageRef"] == "abcdef0123"
    assert fill["scaleMode"] == "FILL"


def test_unmapped_node_type_is_reported(tmp_path) -> None:
    message = _sample_message()
    message["nodeChanges"][3]["type"] = "STAMP"
    target = tmp_path / "stamp.fig"
    target.write_bytes(_build_payload(message))
    _payload, report = fig_archive_to_rest_payload(read_fig_archive(target))
    assert report["unmapped_node_types"] == ["STAMP"]


def test_missing_document_root_is_synthesized(tmp_path) -> None:
    message = _sample_message()
    # Drop the DOCUMENT and CANVAS rows, leaving a bare frame fragment.
    message["nodeChanges"] = [
        row for row in message["nodeChanges"] if row["type"] not in {"DOCUMENT", "CANVAS"}
    ]
    message["nodeChanges"][0].pop("parentIndex", None)
    target = tmp_path / "fragment.fig"
    target.write_bytes(_build_payload(message))
    payload, report = fig_archive_to_rest_payload(read_fig_archive(target))
    assert payload["document"]["type"] == "DOCUMENT"
    assert payload["document"]["children"][0]["type"] == "CANVAS"
    assert "fig_synthesized_document_root" in report["warnings"]


def test_empty_node_changes_is_rejected(tmp_path) -> None:
    target = tmp_path / "empty.fig"
    target.write_bytes(_build_payload({"fileName": "Empty", "nodeChanges": []}))
    with pytest.raises(ValueError, match="no node changes"):
        fig_archive_to_rest_payload(read_fig_archive(target))


# -- Vector networks -----------------------------------------------------


def _vector_blob(
    vertices: list[tuple[float, float]],
    segments: list[tuple[int, float, float, int, float, float]],
    regions: list[tuple[int, list[list[int]]]],
) -> bytes:
    out = bytearray(struct.pack("<III", len(vertices), len(segments), len(regions)))
    for x, y in vertices:
        out.extend(struct.pack("<Iff", 0, x, y))
    for start, stx, sty, end, etx, ety in segments:
        out.extend(struct.pack("<IIffIff", 0, start, stx, sty, end, etx, ety))
    for winding, loops in regions:
        out.extend(struct.pack("<II", winding, len(loops)))
        for loop in loops:
            out.extend(struct.pack("<I", len(loop)))
            for index in loop:
                out.extend(struct.pack("<I", index))
    return bytes(out)


_SQUARE = _vector_blob(
    [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
    [
        (0, 0.0, 0.0, 1, 0.0, 0.0),
        (1, 0.0, 0.0, 2, 0.0, 0.0),
        (2, 0.0, 0.0, 3, 0.0, 0.0),
        (3, 0.0, 0.0, 0, 0.0, 0.0),
    ],
    [(0, [[0, 1, 2, 3]])],
)


def test_vector_network_parses_counts() -> None:
    network = parse_vector_network(_SQUARE)
    assert len(network.vertices) == 4
    assert len(network.segments) == 4
    assert network.regions[0][0] == "NONZERO"


def test_straight_segments_emit_line_commands() -> None:
    rows = vector_network_fill_paths(parse_vector_network(_SQUARE))
    assert rows == [{"path": "M0 0L10 0L10 10L0 10L0 0Z", "windingRule": "NONZERO"}]


def test_tangents_emit_cubic_commands() -> None:
    blob = _vector_blob(
        [(0.0, 0.0), (10.0, 0.0)],
        [(0, 2.0, 3.0, 1, -2.0, 3.0)],
        [(1, [[0]])],
    )
    rows = vector_network_fill_paths(parse_vector_network(blob))
    # Control points are the vertex position plus the stored tangent offset.
    assert rows[0]["path"] == "M0 0C2 3 8 3 10 0Z"
    assert rows[0]["windingRule"] == "EVENODD"


def test_reversed_segment_is_chained_forwards() -> None:
    # The second segment is stored end-first; the walker must flip it.
    blob = _vector_blob(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
        [(0, 0.0, 0.0, 1, 0.0, 0.0), (2, 0.0, 0.0, 1, 0.0, 0.0)],
        [(0, [[0, 1]])],
    )
    rows = vector_network_fill_paths(parse_vector_network(blob))
    assert rows[0]["path"] == "M0 0L10 0L10 10Z"


def test_networks_without_regions_stay_open() -> None:
    blob = _vector_blob(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
        [(0, 0.0, 0.0, 1, 0.0, 0.0), (1, 0.0, 0.0, 2, 0.0, 0.0)],
        [],
    )
    rows = vector_network_fill_paths(parse_vector_network(blob))
    assert rows[0]["path"] == "M0 0L10 0L10 10"
    assert "Z" not in rows[0]["path"]


def test_paths_scale_from_normalized_size() -> None:
    rows = vector_network_fill_paths(parse_vector_network(_SQUARE), scale_x=2.0, scale_y=0.5)
    assert rows[0]["path"] == "M0 0L20 0L20 5L0 5L0 0Z"


def test_truncated_vector_blob_is_rejected() -> None:
    with pytest.raises(VectorNetworkError):
        parse_vector_network(_SQUARE[:20])


def test_implausible_vector_counts_are_rejected() -> None:
    with pytest.raises(VectorNetworkError, match="Implausible"):
        parse_vector_network(struct.pack("<III", 2**30, 0, 0))


def _vector_message(blob: bytes = _SQUARE, *, blob_index: int = 0) -> dict:
    message = _sample_message()
    message["blobs"] = [{"bytes": blob}]
    message["nodeChanges"][3]["type"] = "FRAME"  # keep the parent chain intact
    message["nodeChanges"].append(
        {
            "guid": _guid(5),
            "parentIndex": {"guid": _guid(2), "position": "#"},
            "type": "ROUNDED_RECTANGLE",
            "name": "Glyph",
            "visible": True,
            "opacity": 1.0,
            "transform": _matrix(0.0, 0.0),
            "size": {"x": 10.0, "y": 10.0},
            "vectorData": {"vectorNetworkBlob": blob_index, "normalizedSize": {"x": 10.0, "y": 10.0}},
        }
    )
    return message


def test_vector_geometry_reaches_the_rest_payload(tmp_path) -> None:
    payload = _rest_payload(tmp_path, _vector_message())
    glyph = _find(payload["document"], "Glyph")
    assert glyph["fillGeometry"] == [{"path": "M0 0L10 0L10 10L0 10L0 0Z", "windingRule": "NONZERO"}]


def test_missing_vector_blob_is_reported(tmp_path) -> None:
    target = tmp_path / "novector.fig"
    target.write_bytes(_build_payload(_vector_message(blob_index=7)))
    payload, report = fig_archive_to_rest_payload(read_fig_archive(target))
    assert "fillGeometry" not in _find(payload["document"], "Glyph")
    assert "fig_vector_blob_missing:7" in report["warnings"]


def test_corrupt_vector_blob_is_reported_not_raised(tmp_path) -> None:
    target = tmp_path / "corrupt.fig"
    target.write_bytes(_build_payload(_vector_message(b"\x01\x02\x03")))
    payload, report = fig_archive_to_rest_payload(read_fig_archive(target))
    assert "fillGeometry" not in _find(payload["document"], "Glyph")
    assert any(w.startswith("fig_vector_network_unparsed:") for w in report["warnings"])


# -- Full import ---------------------------------------------------------


def test_import_fig_file_produces_a_painter_document(tmp_path) -> None:
    target = tmp_path / "sample.fig"
    target.write_bytes(_build_zip(_build_payload(), images={"abc123": _PNG}))
    document, report = import_fig_file(target, asset_root=tmp_path / "assets")

    assert report["fig_native_import"] is True
    assert report["fig_version"] == 24
    assert report["fig_node_count"] == 5
    assert document["artboards"], "the Card frame should import as an artboard"
    names = {obj.get("name") for obj in document["objects"]}
    assert {"Swatch", "Label"} <= names
    assert report["downloaded_image_count"] == 1
    written = tmp_path / "assets" / "fig-images" / "abc123.png"
    assert written.read_bytes() == _PNG


def test_import_fig_file_reports_a_readable_error(tmp_path) -> None:
    target = tmp_path / "broken.fig"
    target.write_bytes(b"not a fig file at all")
    with pytest.raises(PainterUIFigmaError, match="broken.fig"):
        import_fig_file(target)


# -- instance expansion and mask flags -----------------------------------


def _fig_rows(*rows: dict) -> dict:
    from app.painter_ui_figma_fig_rest import _collect_nodes, _link_tree

    nodes, warnings = _collect_nodes(rows)
    _link_tree(nodes)
    return {"nodes": nodes, "warnings": warnings}


def test_mask_nodes_use_the_rest_spelling(tmp_path) -> None:
    """The importer reads ``isMask``; emitting ``mask`` hid every mask.

    Figma fills mask shapes with a loud colour precisely because they never
    render, so a missed mask paints a bright block over the artwork.
    """

    from app.painter_ui_figma_fig_rest import _convert_node, _collect_nodes, _link_tree

    rows = [
        {"guid": _guid(1), "type": "CANVAS", "name": "Page"},
        {
            "guid": _guid(2),
            "type": "RECTANGLE",
            "name": "mask",
            "parentIndex": {"guid": _guid(1), "position": "!"},
            "transform": _matrix(),
            "size": {"x": 10.0, "y": 10.0},
            "mask": True,
            "maskType": "ALPHA",
        },
    ]
    nodes, warnings = _collect_nodes(rows)
    _link_tree(nodes)
    rest = _convert_node(nodes["0:2"], (1.0, 0.0, 0.0, 0.0, 1.0, 0.0), warnings, [])
    assert rest["isMask"] is True
    assert rest["maskType"] == "ALPHA"
    assert "mask" not in rest


def test_instances_are_expanded_from_their_component() -> None:
    """A ``.fig`` instance stores a reference, not its children."""

    from app.painter_ui_figma_fig_rest import (
        _collect_nodes,
        _expand_instances,
        _link_tree,
    )

    rows = [
        {"guid": _guid(1), "type": "CANVAS", "name": "Page"},
        {
            "guid": _guid(10),
            "type": "SYMBOL",
            "name": "card",
            "parentIndex": {"guid": _guid(1), "position": "!"},
            "transform": _matrix(),
            "size": {"x": 100.0, "y": 40.0},
        },
        {
            "guid": _guid(11),
            "type": "TEXT",
            "name": "label",
            "parentIndex": {"guid": _guid(10), "position": "!"},
            "transform": _matrix(),
            "size": {"x": 80.0, "y": 20.0},
            "textData": {"characters": "component default"},
        },
        {
            "guid": _guid(20),
            "type": "INSTANCE",
            "name": "card instance",
            "parentIndex": {"guid": _guid(1), "position": "\""},
            "transform": _matrix(200.0, 0.0),
            "size": {"x": 100.0, "y": 40.0},
            "symbolData": {
                "symbolID": _guid(10),
                "symbolOverrides": [
                    {
                        "guidPath": {"guids": [_guid(11)]},
                        "textData": {"characters": "overridden"},
                    }
                ],
            },
        },
    ]
    nodes, warnings = _collect_nodes(rows)
    _link_tree(nodes)
    report = _expand_instances(nodes, warnings)

    assert report["instances"] == 1
    assert report["unresolved"] == 0
    instance = nodes["0:20"]
    assert len(instance.children) == 1
    child = instance.children[0]
    # The clone is addressed the way REST addresses instance children.
    assert child.node_id == "I0:20;0:11"
    assert child.raw["textData"]["characters"] == "overridden"
    # The component keeps its own copy untouched.
    assert nodes["0:11"].raw["textData"]["characters"] == "component default"


def test_expansion_refuses_a_component_that_contains_itself() -> None:
    from app.painter_ui_figma_fig_rest import (
        _collect_nodes,
        _expand_instances,
        _link_tree,
    )

    rows = [
        {"guid": _guid(1), "type": "CANVAS", "name": "Page"},
        {
            "guid": _guid(10),
            "type": "SYMBOL",
            "name": "loop",
            "parentIndex": {"guid": _guid(1), "position": "!"},
            "transform": _matrix(),
            "size": {"x": 10.0, "y": 10.0},
        },
        {
            "guid": _guid(11),
            "type": "INSTANCE",
            "name": "self",
            "parentIndex": {"guid": _guid(10), "position": "!"},
            "transform": _matrix(),
            "size": {"x": 10.0, "y": 10.0},
            "symbolData": {"symbolID": _guid(10), "symbolOverrides": []},
        },
    ]
    nodes, warnings = _collect_nodes(rows)
    _link_tree(nodes)
    _expand_instances(nodes, warnings)
    assert any("recursive_component" in warning for warning in warnings)


def test_an_instance_without_its_component_is_reported() -> None:
    from app.painter_ui_figma_fig_rest import (
        _collect_nodes,
        _expand_instances,
        _link_tree,
    )

    rows = [
        {"guid": _guid(1), "type": "CANVAS", "name": "Page"},
        {
            "guid": _guid(20),
            "type": "INSTANCE",
            "name": "orphan",
            "parentIndex": {"guid": _guid(1), "position": "!"},
            "transform": _matrix(),
            "size": {"x": 10.0, "y": 10.0},
            "symbolData": {"symbolID": _guid(99), "symbolOverrides": []},
        },
    ]
    nodes, warnings = _collect_nodes(rows)
    _link_tree(nodes)
    report = _expand_instances(nodes, warnings)
    assert report["unresolved"] == 1
    assert nodes["0:20"].children == []
    assert any("component_missing" in warning for warning in warnings)


def test_a_nested_instance_keeps_its_own_resolved_state() -> None:
    """An outer override must not repaint a nested instance.

    A descendant that is itself an instance already carries the state Figma
    resolved for it; the outer instance's override for that path is a stale
    delta.  Applying it painted resolved nested instances a colour Figma never
    renders, while text overrides on ordinary nodes still have to apply.
    """

    from app.painter_ui_figma_fig_rest import (
        _collect_nodes,
        _expand_instances,
        _link_tree,
    )

    rows = [
        {"guid": _guid(1), "type": "CANVAS", "name": "Page"},
        # The button component, and the button instance the card holds.
        {
            "guid": _guid(30),
            "type": "SYMBOL",
            "name": "button",
            "parentIndex": {"guid": _guid(1), "position": "!"},
            "transform": _matrix(),
            "size": {"x": 80.0, "y": 24.0},
            "fillPaints": [{"type": "SOLID", "color": {"r": 0, "g": 0, "b": 0, "a": 1}}],
        },
        {
            "guid": _guid(10),
            "type": "SYMBOL",
            "name": "card",
            "parentIndex": {"guid": _guid(1), "position": '"'},
            "transform": _matrix(),
            "size": {"x": 200.0, "y": 80.0},
        },
        {
            "guid": _guid(11),
            "type": "TEXT",
            "name": "label",
            "parentIndex": {"guid": _guid(10), "position": "!"},
            "transform": _matrix(),
            "size": {"x": 100.0, "y": 20.0},
            "textData": {"characters": "component default"},
        },
        {
            "guid": _guid(12),
            "type": "INSTANCE",
            "name": "button",
            "parentIndex": {"guid": _guid(10), "position": '"'},
            "transform": _matrix(),
            "size": {"x": 80.0, "y": 24.0},
            # Already resolved to its own colour.
            "fillPaints": [
                {"type": "SOLID", "color": {"r": 0.125, "g": 0.125, "b": 0.125, "a": 1}}
            ],
            "symbolData": {"symbolID": _guid(30), "symbolOverrides": []},
        },
        {
            "guid": _guid(20),
            "type": "INSTANCE",
            "name": "card instance",
            "parentIndex": {"guid": _guid(1), "position": "#"},
            "transform": _matrix(300.0, 0.0),
            "size": {"x": 200.0, "y": 80.0},
            "symbolData": {
                "symbolID": _guid(10),
                "symbolOverrides": [
                    {
                        "guidPath": {"guids": [_guid(11)]},
                        "textData": {"characters": "overridden"},
                    },
                    {
                        "guidPath": {"guids": [_guid(12)]},
                        "fillPaints": [
                            {"type": "SOLID", "color": {"r": 1, "g": 0, "b": 1, "a": 1}}
                        ],
                    },
                ],
            },
        },
    ]
    nodes, warnings = _collect_nodes(rows)
    _link_tree(nodes)
    _expand_instances(nodes, warnings)

    children = {child.raw["name"]: child for child in nodes["0:20"].children}
    # An ordinary node still takes the override.
    assert children["label"].raw["textData"]["characters"] == "overridden"
    # The nested instance keeps what it already resolved to.
    colour = children["button"].raw["fillPaints"][0]["color"]
    assert colour["r"] == pytest.approx(0.125)
    assert colour["g"] == pytest.approx(0.125)


def test_boolean_operations_keep_their_kind(tmp_path) -> None:
    """Every boolean imported as UNION, so cut-outs came through uncut."""

    from app.painter_ui_figma_fig_rest import (
        _collect_nodes,
        _convert_node,
        _link_tree,
    )

    identity = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    for internal, expected in (
        ("SUBTRACT", "SUBTRACT"),
        ("INTERSECT", "INTERSECT"),
        ("UNION", "UNION"),
        ("XOR", "XOR"),
    ):
        rows = [
            {"guid": _guid(1), "type": "CANVAS", "name": "Page"},
            {
                "guid": _guid(2),
                "type": "BOOLEAN_OPERATION",
                "name": "shape",
                "parentIndex": {"guid": _guid(1), "position": "!"},
                "transform": _matrix(),
                "size": {"x": 40.0, "y": 40.0},
                "booleanOperation": internal,
            },
        ]
        nodes, warnings = _collect_nodes(rows)
        _link_tree(nodes)
        rest = _convert_node(nodes["0:2"], identity, warnings, [])
        assert rest["type"] == "BOOLEAN_OPERATION"
        assert rest["booleanOperation"] == expected


def test_a_subtract_boolean_reaches_the_document_as_subtract() -> None:
    """The importer defaults to union, so the mapper has to say otherwise."""

    from app.painter_ui_figma import import_figma_payload

    payload = {
        "name": "Booleans",
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "type": "CANVAS",
                    "name": "Page",
                    "children": [
                        {
                            "id": "1:1",
                            "type": "FRAME",
                            "name": "Frame",
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 200,
                                "height": 200,
                            },
                            "children": [
                                {
                                    "id": "1:2",
                                    "type": "BOOLEAN_OPERATION",
                                    "name": "cut",
                                    "booleanOperation": "SUBTRACT",
                                    "absoluteBoundingBox": {
                                        "x": 10,
                                        "y": 10,
                                        "width": 80,
                                        "height": 80,
                                    },
                                    "children": [
                                        {
                                            "id": "1:3",
                                            "type": "RECTANGLE",
                                            "name": "base",
                                            "absoluteBoundingBox": {
                                                "x": 10,
                                                "y": 10,
                                                "width": 80,
                                                "height": 80,
                                            },
                                        },
                                        {
                                            "id": "1:4",
                                            "type": "ELLIPSE",
                                            "name": "hole",
                                            "absoluteBoundingBox": {
                                                "x": 30,
                                                "y": 30,
                                                "width": 40,
                                                "height": 40,
                                            },
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    }
    document, report = import_figma_payload(payload, source="BooleanSample")
    assert report["ok"] is True
    cut = next(
        row for row in document["objects"] if row["name"] == "cut"
    )
    boolean = (cut.get("content") or {}).get("boolean") or {}
    assert boolean.get("enabled") is True
    assert boolean.get("operation") == "subtract"
    assert len(boolean.get("operand_ids") or []) == 2


def _library_component_rows(*, extra_local_child: bool = False) -> list[dict]:
    """A component published to a library, whose local copy was renumbered.

    Its overrides address descendants by the library's guids (session 41),
    which this file has never heard of; the local copy carries session 0.
    """

    rows = [
        {"guid": _guid(1), "type": "CANVAS", "name": "Page"},
        {
            "guid": _guid(30),
            "type": "SYMBOL",
            "name": "button",
            "parentIndex": {"guid": _guid(1), "position": "!"},
            "transform": _matrix(),
            "size": {"x": 108.0, "y": 48.0},
            "sharedSymbolVersion": "474:281",
        },
        {
            "guid": _guid(31),
            "type": "TEXT",
            "name": "CTA",
            "parentIndex": {"guid": _guid(30), "position": "!"},
            "transform": _matrix(),
            "size": {"x": 101.0, "y": 32.0},
            "textData": {"characters": "Get started"},
        },
        {
            "guid": _guid(32),
            "type": "TEXT",
            "name": "arrow",
            "parentIndex": {"guid": _guid(30), "position": '"'},
            "transform": _matrix(),
            "size": {"x": 23.0, "y": 1.0},
            "textData": {"characters": "->"},
        },
    ]
    if extra_local_child:
        rows.append(
            {
                "guid": _guid(33),
                "type": "RECTANGLE",
                "name": "extra",
                "parentIndex": {"guid": _guid(30), "position": "#"},
                "transform": _matrix(),
                "size": {"x": 8.0, "y": 8.0},
            }
        )
    rows.append(
        {
            "guid": _guid(40),
            "type": "INSTANCE",
            "name": "button instance",
            "parentIndex": {"guid": _guid(1), "position": '"'},
            "transform": _matrix(200.0, 0.0),
            "size": {"x": 108.0, "y": 48.0},
            "symbolData": {
                "symbolID": _guid(30),
                "symbolOverrides": [
                    {"guidPath": {"guids": [_guid(25, 41)]}, "size": {"x": 108.0, "y": 48.0}},
                    {
                        "guidPath": {"guids": [_guid(26, 41)]},
                        "textData": {"characters": "Start"},
                    },
                ],
            },
            "derivedSymbolData": [
                {"guidPath": {"guids": [_guid(25, 41)]}, "size": {"x": 108.0, "y": 48.0}},
                {"guidPath": {"guids": [_guid(26, 41)]}, "size": {"x": 45.0, "y": 32.0}},
                {"guidPath": {"guids": [_guid(27, 41)]}, "size": {"x": 23.0, "y": 0.0}},
            ],
        }
    )
    return rows


def test_library_guids_are_remapped_onto_the_local_copy() -> None:
    from app.painter_ui_figma_fig_rest import (
        _collect_nodes,
        _expand_instances,
        _link_tree,
    )

    nodes, warnings = _collect_nodes(_library_component_rows())
    _link_tree(nodes)
    report = _expand_instances(nodes, warnings)

    assert report["remapped"] == 1
    children = {child.raw["name"]: child for child in nodes["0:40"].children}
    assert children["CTA"].raw["textData"]["characters"] == "Start"
    # The component itself is untouched.
    assert nodes["0:31"].raw["textData"]["characters"] == "Get started"


def test_a_remap_that_does_not_line_up_is_refused() -> None:
    """A misaligned guess would write the text onto the wrong node."""

    from app.painter_ui_figma_fig_rest import (
        _collect_nodes,
        _expand_instances,
        _link_tree,
    )

    nodes, warnings = _collect_nodes(
        _library_component_rows(extra_local_child=True)
    )
    _link_tree(nodes)
    report = _expand_instances(nodes, warnings)

    # 3 unknown guids against a 4-node subtree is neither an exact match nor a
    # root-less one, so nothing is remapped and the default text stands.
    assert report["remapped"] == 0
    children = {child.raw["name"]: child for child in nodes["0:40"].children}
    assert children["CTA"].raw["textData"]["characters"] == "Get started"


def test_text_overrides_never_land_on_a_non_text_node() -> None:
    from app.painter_ui_figma_fig_rest import _guarded_override

    fields = {"textData": {"characters": "x"}, "fillPaints": [], "size": {}}
    assert _guarded_override(fields, "TEXT") == fields
    kept = _guarded_override(fields, "RECTANGLE")
    assert "textData" not in kept
    assert set(kept) == {"fillPaints", "size"}
