"""Tiger Studio AEP structural parsing and compatibility inspection."""

from .inspect import REPORT_SCHEMA, inspect_aep_document, inspect_aep_file
from .model import AepChunk, AepDocument, AepParseError, AepSafetyLimits
from .rifx import parse_aep_bytes, parse_aep_file

__all__ = [
    "REPORT_SCHEMA",
    "AepChunk",
    "AepDocument",
    "AepParseError",
    "AepSafetyLimits",
    "inspect_aep_document",
    "inspect_aep_file",
    "parse_aep_bytes",
    "parse_aep_file",
]
