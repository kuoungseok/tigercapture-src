"""Kiwi binary format decoder used by the Figma ``.fig`` reader.

Kiwi is the compact schema-driven binary format created by Evan Wallace and used
as the wire format inside Figma ``.fig`` archives. A ``.fig`` payload embeds its
own schema, so this module only needs the generic decoder: parse the binary
schema, then walk the message with the resulting definitions. No code generation
and no third-party dependency is required.

Reference implementation: https://github.com/evanw/kiwi (MIT).
"""
from __future__ import annotations

import struct
from typing import Any, Mapping, Sequence

__all__ = [
    "KIWI_BUILTIN_TYPES",
    "KiwiByteBuffer",
    "KiwiDefinition",
    "KiwiError",
    "KiwiField",
    "KiwiSchema",
    "decode_binary_schema",
    "schema_summary",
]


class KiwiError(ValueError):
    pass


# Builtin type ids are stored negated in the binary schema: ``~type`` indexes
# this table, so -1 is ``bool``, -2 is ``byte`` and so on.
KIWI_BUILTIN_TYPES: tuple[str, ...] = (
    "bool",
    "byte",
    "int",
    "uint",
    "float",
    "string",
    "int64",
    "uint64",
)

_KIWI_KINDS: tuple[str, ...] = ("ENUM", "STRUCT", "MESSAGE")

_UINT32 = struct.Struct("<I")
_FLOAT32 = struct.Struct("<f")


class KiwiByteBuffer:
    """Sequential reader matching ``ByteBuffer`` from the reference decoder."""

    __slots__ = ("_data", "_index")

    def __init__(self, data: bytes | bytearray | memoryview) -> None:
        self._data = bytes(data)
        self._index = 0

    @property
    def index(self) -> int:
        return self._index

    @property
    def remaining(self) -> int:
        return len(self._data) - self._index

    def read_byte(self) -> int:
        index = self._index
        if index >= len(self._data):
            raise KiwiError("Index out of bounds")
        self._index = index + 1
        return self._data[index]

    def read_bool(self) -> bool:
        return bool(self.read_byte())

    def read_byte_array(self) -> bytes:
        length = self.read_var_uint()
        start = self._index
        end = start + length
        if end > len(self._data):
            raise KiwiError("Read array out of bounds")
        self._index = end
        return self._data[start:end]

    def read_var_uint(self) -> int:
        value = 0
        shift = 0
        while True:
            byte = self.read_byte()
            value |= (byte & 127) << shift
            shift += 7
            if not (byte & 128) or shift >= 35:
                break
        # The reference decoder truncates to 32 bits via ``value >>> 0``.
        return value & 0xFFFFFFFF

    def read_var_int(self) -> int:
        value = self.read_var_uint()
        # Zigzag: odd values are negative.
        if value & 1:
            return ~(value >> 1)
        return value >> 1

    def read_var_uint64(self) -> int:
        value = 0
        shift = 0
        while True:
            byte = self.read_byte()
            if not (byte & 128) or shift >= 56:
                value |= byte << shift
                break
            value |= (byte & 127) << shift
            shift += 7
        return value & 0xFFFFFFFFFFFFFFFF

    def read_var_int64(self) -> int:
        value = self.read_var_uint64()
        sign = value & 1
        value >>= 1
        return ~value if sign else value

    def read_var_float(self) -> float:
        index = self._index
        data = self._data
        if index >= len(data):
            raise KiwiError("Index out of bounds")
        # Zero and denormals collapse to a single zero byte.
        first = data[index]
        if first == 0:
            self._index = index + 1
            return 0.0
        if index + 4 > len(data):
            raise KiwiError("Index out of bounds")
        bits = first | (data[index + 1] << 8) | (data[index + 2] << 16) | (data[index + 3] << 24)
        self._index = index + 4
        # The writer rotates the exponent into the low byte; undo that here.
        bits = ((bits << 23) | (bits >> 9)) & 0xFFFFFFFF
        return _FLOAT32.unpack(_UINT32.pack(bits))[0]

    def read_string(self) -> str:
        # Kiwi stores null-terminated UTF-8 and re-encodes surrogate pairs, so
        # decode the raw run with surrogatepass to keep lone surrogates intact.
        data = self._data
        start = self._index
        end = data.find(b"\x00", start)
        if end < 0:
            raise KiwiError("Unterminated string")
        self._index = end + 1
        raw = data[start:end]
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("utf-8", "replace")


class KiwiField:
    __slots__ = ("name", "type", "is_array", "value")

    def __init__(self, name: str, type_: str | None, is_array: bool, value: int) -> None:
        self.name = name
        self.type = type_
        self.is_array = is_array
        self.value = value

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        suffix = "[]" if self.is_array else ""
        return f"KiwiField({self.name}: {self.type}{suffix} = {self.value})"


class KiwiDefinition:
    __slots__ = ("name", "kind", "fields", "_by_value", "_enum_names")

    def __init__(self, name: str, kind: str, fields: list[KiwiField]) -> None:
        self.name = name
        self.kind = kind
        self.fields = fields
        self._by_value: dict[int, KiwiField] = {}
        self._enum_names: dict[int, str] = {}

    def finalize(self) -> None:
        if self.kind == "MESSAGE":
            self._by_value = {field.value: field for field in self.fields}
        elif self.kind == "ENUM":
            self._enum_names = {field.value: field.name for field in self.fields}

    def field_for(self, value: int) -> KiwiField | None:
        return self._by_value.get(value)

    def enum_name(self, value: int) -> str | int:
        return self._enum_names.get(value, value)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"KiwiDefinition({self.kind} {self.name}, {len(self.fields)} fields)"


class KiwiSchema:
    """Decoded Kiwi schema able to decode messages that follow it."""

    __slots__ = ("definitions", "_by_name")

    def __init__(self, definitions: Sequence[KiwiDefinition]) -> None:
        self.definitions = list(definitions)
        self._by_name = {definition.name: definition for definition in self.definitions}

    def definition(self, name: str) -> KiwiDefinition | None:
        return self._by_name.get(name)

    @property
    def names(self) -> list[str]:
        return [definition.name for definition in self.definitions]

    def decode(self, data: bytes | bytearray | memoryview, root: str = "Message") -> dict[str, Any]:
        definition = self._by_name.get(root)
        if definition is None:
            raise KiwiError(f"Schema does not define a {root!r} root")
        return self._decode_definition(definition, KiwiByteBuffer(data))

    # -- internals -------------------------------------------------------

    def _decode_definition(self, definition: KiwiDefinition, bb: KiwiByteBuffer) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if definition.kind == "MESSAGE":
            while True:
                field_value = bb.read_var_uint()
                if field_value == 0:
                    return result
                field = definition.field_for(field_value)
                if field is None:
                    # An unknown field id means the stream and schema disagree;
                    # there is no length prefix to skip past, so stop cleanly
                    # rather than emit garbage for the remaining fields.
                    raise KiwiError(
                        f"Unknown field id {field_value} in message {definition.name!r}"
                    )
                result[field.name] = self._decode_field(field, bb)
        for field in definition.fields:
            result[field.name] = self._decode_field(field, bb)
        return result

    def _decode_field(self, field: KiwiField, bb: KiwiByteBuffer) -> Any:
        if field.is_array:
            if field.type == "byte":
                return bb.read_byte_array()
            length = bb.read_var_uint()
            return [self._decode_value(field.type, bb) for _ in range(length)]
        return self._decode_value(field.type, bb)

    def _decode_value(self, type_: str | None, bb: KiwiByteBuffer) -> Any:
        if type_ == "bool":
            return bb.read_bool()
        if type_ == "byte":
            return bb.read_byte()
        if type_ == "int":
            return bb.read_var_int()
        if type_ == "uint":
            return bb.read_var_uint()
        if type_ == "float":
            return bb.read_var_float()
        if type_ == "string":
            return bb.read_string()
        if type_ == "int64":
            return bb.read_var_int64()
        if type_ == "uint64":
            return bb.read_var_uint64()
        definition = self._by_name.get(type_ or "")
        if definition is None:
            raise KiwiError(f"Invalid type {type_!r}")
        if definition.kind == "ENUM":
            return definition.enum_name(bb.read_var_uint())
        return self._decode_definition(definition, bb)


def decode_binary_schema(data: bytes | bytearray | memoryview) -> KiwiSchema:
    """Parse the binary schema chunk embedded in a ``.fig`` payload."""

    bb = KiwiByteBuffer(data)
    definition_count = bb.read_var_uint()
    definitions: list[KiwiDefinition] = []
    raw_types: list[list[int | None]] = []

    for _ in range(definition_count):
        name = bb.read_string()
        kind_index = bb.read_byte()
        if kind_index >= len(_KIWI_KINDS):
            raise KiwiError(f"Invalid definition kind {kind_index}")
        kind = _KIWI_KINDS[kind_index]
        field_count = bb.read_var_uint()
        fields: list[KiwiField] = []
        types: list[int | None] = []
        for _ in range(field_count):
            field_name = bb.read_string()
            field_type = bb.read_var_int()
            is_array = bool(bb.read_byte() & 1)
            value = bb.read_var_uint()
            # ENUM members carry no type; their payload is the varuint value.
            types.append(None if kind == "ENUM" else field_type)
            fields.append(KiwiField(field_name, None, is_array, value))
        definitions.append(KiwiDefinition(name, kind, fields))
        raw_types.append(types)

    # Type ids reference definitions by index, so bind names only once every
    # definition exists.
    for definition, types in zip(definitions, raw_types):
        for field, type_id in zip(definition.fields, types):
            if type_id is None:
                field.type = None
            elif type_id < 0:
                builtin = ~type_id
                if builtin >= len(KIWI_BUILTIN_TYPES):
                    raise KiwiError(f"Invalid type {type_id}")
                field.type = KIWI_BUILTIN_TYPES[builtin]
            else:
                if type_id >= len(definitions):
                    raise KiwiError(f"Invalid type {type_id}")
                field.type = definitions[type_id].name
        definition.finalize()

    return KiwiSchema(definitions)


def schema_summary(schema: KiwiSchema) -> Mapping[str, int]:
    """Count definitions per kind; used by diagnostics and tests."""

    counts: dict[str, int] = {"ENUM": 0, "STRUCT": 0, "MESSAGE": 0}
    for definition in schema.definitions:
        counts[definition.kind] = counts.get(definition.kind, 0) + 1
    return counts
