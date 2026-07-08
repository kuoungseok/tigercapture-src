"""User-facing PPT generation package.

The core modules in this package are intentionally Qt-free. UI code lives under
``app.pptgen.ui`` and editor integration should go through focused workflow
modules instead of the main video editor facade.
"""
from __future__ import annotations

from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec
from app.pptgen.timeline import PptTimeline, SlideClip
from app.pptgen.validation import ValidationIssue, validate_deck, validation_report

__all__ = [
    "DeckSpec",
    "PptTimeline",
    "SlideClip",
    "SlideElement",
    "SlideSpec",
    "ValidationIssue",
    "validate_deck",
    "validation_report",
]
