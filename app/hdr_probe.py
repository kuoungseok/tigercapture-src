"""HDR Phase 0: probe a video file for HDR metadata.

We run ``ffmpeg -i FILE`` (using the bundled ``imageio_ffmpeg`` binary)
and parse its stderr — that's the cheapest way to learn the colour
transfer / primaries / pixel format without shelling out to ffprobe
(which isn't shipped by imageio_ffmpeg on Windows). The probe is run
once per file when the Media Pool ingests it; the result is cached on
the pool item so repeated reads (workbench, paint) are free.

Detected formats (by transfer characteristic):
- ``smpte2084``  — PQ (HDR10, HDR10+, Dolby Vision IPT)
- ``arib-std-b67`` — HLG (BBC/NHK Hybrid Log-Gamma)

Anything else (typically ``bt709`` for normal Rec.709 SDR or
``bt2020-10`` for wide-gamut SDR) is reported as SDR.

The decoded preview path still goes through ``cv2.VideoCapture`` and
strips HDR — this module is *detection only*. Phase 1 will move the
decode to ffmpeg pipe + SDR tonemap; Phase 2 will preserve HDR
through the export filter chain.
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# Transfer characteristics that indicate HDR content. Matched against
# the value ffmpeg prints in its ``Stream #0:0(...) Video: ...`` line.
_HDR_TRANSFERS: frozenset[str] = frozenset(
    {"smpte2084", "arib-std-b67"}
)


# Regex for the colour-space triple that appears inside parens after
# the pixel format on the Video stream line. Examples:
#   yuv420p10le(tv, bt2020nc/bt2020/smpte2084)
#   yuv420p(progressive)
#   yuv420p(tv, bt709, progressive)
# We tolerate optional 'tv'/'pc' prefix, optional 'progressive', and
# capture the matrix/primaries/transfer triple when it's present.
_COLOR_TRIPLE_RX = re.compile(
    r"\(\s*"
    r"(?:tv|pc)?\s*,?\s*"
    r"(?P<matrix>[\w\-]+)"
    r"(?:/(?P<primaries>[\w\-]+)/(?P<transfer>[\w\-]+))?"
    r"(?:\s*,\s*\w+)?"
    r"\s*\)",
)

_PIXFMT_RX = re.compile(r"Video:\s*[^,]+,\s*(?P<pixfmt>\w+)")


@dataclass(frozen=True)
class HDRInfo:
    """What we learned about a file's colour pipeline.

    ``is_hdr`` is the load-bearing field; everything else is for
    UI tooltips and Phase 1/2 decode/export decisions.
    """

    is_hdr: bool
    transfer: str = ""        # e.g. "smpte2084", "arib-std-b67", "bt709"
    primaries: str = ""       # e.g. "bt2020", "bt709"
    matrix: str = ""          # e.g. "bt2020nc", "bt709"
    pix_fmt: str = ""         # e.g. "yuv420p10le"
    raw_line: str = ""        # the full Video: line from ffmpeg, for diagnostics

    @property
    def standard_label(self) -> str:
        """Human-readable HDR variant, or "SDR"."""
        if not self.is_hdr:
            return "SDR"
        if self.transfer == "smpte2084":
            return "HDR10"
        if self.transfer == "arib-std-b67":
            return "HLG"
        return "HDR"


_FFMPEG_PROBE_TIMEOUT_S = 10


def probe_hdr(path: Path | str) -> HDRInfo:
    """Run ffmpeg on ``path`` long enough to print stream metadata,
    then return an ``HDRInfo``. Falls back to ``HDRInfo(is_hdr=False)``
    on any error (missing binary, unreadable file, parse mismatch) —
    failure to detect must never block a video from loading."""
    p = Path(path)
    if not p.is_file():
        return HDRInfo(is_hdr=False)
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        ffmpeg = get_ffmpeg_exe()
    except Exception:
        return HDRInfo(is_hdr=False)
    # ``-hide_banner -i FILE`` makes ffmpeg print metadata then bail
    # with a "At least one output file must be specified" error code.
    # We capture stderr (where the Stream line lives) and ignore
    # stdout / exit code.
    try:
        cp = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(p)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_FFMPEG_PROBE_TIMEOUT_S,
            creationflags=(
                subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            ),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return HDRInfo(is_hdr=False)
    text = (cp.stderr or "") + "\n" + (cp.stdout or "")
    return _parse_hdr_from_ffmpeg_text(text)


def _parse_hdr_from_ffmpeg_text(text: str) -> HDRInfo:
    """Pull the first ``Stream #...: Video:`` line out of ffmpeg's
    output and parse it. Public-ish for unit-testing without spawning
    ffmpeg."""
    line = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if "Video:" in stripped and "Stream " in stripped:
            line = stripped
            break
    if not line:
        return HDRInfo(is_hdr=False)
    pix_fmt = ""
    m_pix = _PIXFMT_RX.search(line)
    if m_pix:
        pix_fmt = m_pix.group("pixfmt")
    matrix = primaries = transfer = ""
    for m in _COLOR_TRIPLE_RX.finditer(line):
        # Several parens appear on the line (resolution, colour, etc.).
        # The triple we want is the one with primaries+transfer; the
        # plain ``(progressive)`` / ``(tv)`` matches don't carry a
        # primaries group. Skip those.
        if m.group("transfer") is None:
            continue
        matrix = m.group("matrix") or ""
        primaries = m.group("primaries") or ""
        transfer = m.group("transfer") or ""
        break
    is_hdr = transfer in _HDR_TRANSFERS
    return HDRInfo(
        is_hdr=is_hdr,
        transfer=transfer,
        primaries=primaries,
        matrix=matrix,
        pix_fmt=pix_fmt,
        raw_line=line,
    )
