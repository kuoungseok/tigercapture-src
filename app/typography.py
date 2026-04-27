"""Typography / text-clip data model (Phase 1).

Spec: ``typo_editor/TYPOGRAPHY_SPEC_PYQT.md``.

Phase 1 goal is the *data + placement* infrastructure. Animations,
the full 3-pane editor, presets, and export integration come in
later phases — this module already carries the fields those phases
will fill in (``style``, ``animation``) so persistence stays
compatible when we add them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Any


# ---------------------------------------------------------------------------
#  ID generator
# ---------------------------------------------------------------------------

# Monotonic integer ids, scoped to the process. We don't need cryptographic
# uniqueness — this is for in-memory tracking only.
_id_counter = count(1)


def _next_id() -> int:
    return next(_id_counter)


# ---------------------------------------------------------------------------
#  Style
# ---------------------------------------------------------------------------


@dataclass
class TextStyle:
    """Visual style of a text clip. All fields have sensible defaults so
    an empty clip renders as centered white sans-serif text."""

    font_family: str = "Noto Sans KR"
    font_size: int = 72
    font_weight: int = 700          # 100..900 (CSS-style)
    color: str = "#FFFFFF"
    alignment: str = "center"       # "left" | "center" | "right"
    letter_spacing: int = 0         # px
    line_height: float = 1.2        # multiplier

    # On-screen position as a fraction of the video rect (0..1). The
    # text's geometric center sits at (position_x, position_y).
    position_x: float = 0.5
    position_y: float = 0.5
    rotation: float = 0.0           # degrees, 0 = upright

    # Optional outline — drawn under the glyph fill.
    outline_color: str | None = None
    outline_width: int = 0

    # Optional drop-shadow — drawn beneath everything.
    shadow_color: str | None = None
    shadow_offset_x: int = 0
    shadow_offset_y: int = 0
    shadow_blur: int = 0

    # Optional background rectangle (news-ticker / label style).
    background_color: str | None = None
    background_padding: int = 0
    background_radius: int = 0


# ---------------------------------------------------------------------------
#  Animation config
# ---------------------------------------------------------------------------


@dataclass
class AnimationConfig:
    """Animation identity + IN/HOLD/OUT timing. Phase 1 stores the
    defaults so future phases can wire real animations by id without a
    data-model migration."""

    preset_id: str = "basic-fade"        # top-level preset label
    in_animation: str = "fade-in"         # IN segment id
    hold_animation: str = "none"          # HOLD segment id (static / loop)
    out_animation: str = "fade-out"       # OUT segment id

    # Extra animations stacked on top of the primary. Composed by the
    # renderer: offsets/rotations add, scale/opacity multiply. Mixing a
    # per-glyph extra with whole-text primary lifts the whole-text
    # transform onto every glyph.
    in_extras: list[str] = field(default_factory=list)
    hold_extras: list[str] = field(default_factory=list)
    out_extras: list[str] = field(default_factory=list)

    in_duration: float = 0.5              # seconds
    out_duration: float = 0.5             # seconds
    # hold_duration is derived from clip.duration - in - out (see TextClip).

    # Animation magnitude per phase (0..200, default 100). Each
    # animation interprets this as a multiplier on its core "deviation
    # from identity" — slide distance, rotation angle, scale extreme,
    # wave amplitude. 0% renders as no effect (identity); 200% doubles
    # the displacement. The extras share the slot's intensity.
    in_intensity: float = 100.0
    out_intensity: float = 100.0
    hold_intensity: float = 100.0

    # When True, ignore any per-glyph color overrides emitted by the
    # animation (e.g. Angle Break's white → red → yellow flash) and
    # render every glyph in the clip's main TextStyle.color. Useful
    # when users want the geometric motion of a fancy preset without
    # the multi-color flicker.
    mono_color: bool = False

    # Free-form parameters that specific animations read during render.
    # Kept open so presets can stash anything (shake amplitude, bounce
    # height, glitch frequency…) without growing this dataclass.
    custom_params: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
#  Text clip
# ---------------------------------------------------------------------------


@dataclass
class TextClip:
    """A single placed text clip on the typography lane.

    Timing is expressed in *milliseconds* to stay consistent with the
    rest of Bitdam's timeline (video tracks, fade segments, etc.). The
    spec uses seconds; we translate on the fly in the UI.
    """

    id: int = field(default_factory=_next_id)
    start_ms: int = 0
    end_ms: int = 2000                          # default = 2-second clip
    text: str = ""
    animation: AnimationConfig = field(default_factory=AnimationConfig)
    style: TextStyle = field(default_factory=TextStyle)

    # --- derived timings ---

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    @property
    def duration_s(self) -> float:
        return self.duration_ms / 1000.0

    @property
    def hold_duration_s(self) -> float:
        total = self.duration_s
        taken = self.animation.in_duration + self.animation.out_duration
        return max(0.0, total - taken)

    def contains(self, project_ms: int) -> bool:
        """True when ``project_ms`` falls inside the clip's window."""
        return int(self.start_ms) <= int(project_ms) < int(self.end_ms)

    def display_text(self) -> str:
        """Whatever to show in the timeline chip / preview. Falls back
        to a placeholder when the user hasn't typed anything yet."""
        return self.text if self.text else "Enter text…"


# ---------------------------------------------------------------------------
#  Text track (container)
# ---------------------------------------------------------------------------


@dataclass
class TextTrack:
    """Owns the ordered list of text clips shown on the dedicated
    typography lane. The editor has exactly one of these (text clips
    are global overlays — they aren't per-video-track)."""

    id: int = field(default_factory=_next_id)
    clips: list[TextClip] = field(default_factory=list)

    def add_clip(self, clip: TextClip) -> None:
        self.clips.append(clip)
        self.clips.sort(key=lambda c: c.start_ms)

    def remove_clip(self, clip_id: int) -> bool:
        before = len(self.clips)
        self.clips = [c for c in self.clips if c.id != clip_id]
        return len(self.clips) != before

    def find(self, clip_id: int) -> TextClip | None:
        for c in self.clips:
            if c.id == clip_id:
                return c
        return None

    def active_clips_at(self, project_ms: int) -> list[TextClip]:
        """Clips whose time window contains ``project_ms``. Multiple
        clips can be active at once — later ones draw on top."""
        return [c for c in self.clips if c.contains(project_ms)]

    def extent_ms(self) -> int:
        return max((c.end_ms for c in self.clips), default=0)


# ---------------------------------------------------------------------------
#  Drag MIME type (shared between TypographyCard source and TextLaneRow
#  target so we can distinguish T-card drops from generic file drops).
# ---------------------------------------------------------------------------

TEXT_CLIP_MIME = "application/x-bitdam-text-clip"
