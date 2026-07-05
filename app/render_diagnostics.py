"""Render/export failure diagnostics.

The encoder often returns one long FFmpeg tail. This module turns that into a
stable category, a short user-facing summary, and recovery actions that the UI
can persist in render queue history.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RenderFailureReport:
    category: str
    title: str
    summary: str
    actions: tuple[str, ...] = field(default_factory=tuple)
    raw_tail: str = ""
    context: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "title": self.title,
            "summary": self.summary,
            "actions": list(self.actions),
            "raw_tail": self.raw_tail,
            "context": list(self.context),
        }


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _tail(reason: str, limit: int = 700) -> str:
    cleaned = " ".join(str(reason or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[-limit:]


def _job_context(job: Any | None) -> tuple[str, ...]:
    if job is None:
        return ()
    pieces: list[str] = []
    out_path = str(getattr(job, "out_path", "") or "")
    source_path = str(getattr(job, "source_path", "") or "")
    if out_path:
        pieces.append(f"Output: {Path(out_path).name}")
    if source_path:
        pieces.append(f"Source: {Path(source_path).name}")
    fmt = str(getattr(job, "format_id", "") or "")
    quality = str(getattr(job, "quality_id", "") or "")
    if fmt:
        pieces.append(f"Format: {fmt}")
    if quality:
        pieces.append(f"Quality: {quality}")
    in_ms = int(getattr(job, "in_ms", 0) or 0)
    out_ms = int(getattr(job, "out_ms", 0) or 0)
    if out_ms > in_ms:
        pieces.append(f"Range: {in_ms // 1000}s-{out_ms // 1000}s")
    return tuple(pieces)


def diagnose_render_failure(reason: str, job: Any | None = None) -> RenderFailureReport:
    raw = str(reason or "").strip()
    low = raw.lower()
    context = _job_context(job)
    tail = _tail(raw)

    if "canceled" in low or "cancelled" in low:
        return RenderFailureReport(
            category="canceled",
            title="Render canceled",
            summary="The render was canceled before it completed.",
            actions=("Run the job again when ready.",),
            raw_tail=tail,
            context=context,
        )

    if _contains_any(low, ("could not overwrite", "permission denied", "access is denied", "being used by another process", "another app may be holding")):
        return RenderFailureReport(
            category="output_locked",
            title="Output file is locked",
            summary="The encoder finished or started writing, but the destination file could not be replaced.",
            actions=(
                "Close any media player or file preview using the output file.",
                "Choose a different output filename or folder.",
                "Check write permission for the output folder.",
            ),
            raw_tail=tail,
            context=context,
        )

    if _contains_any(low, ("no space left", "not enough space", "disk full", "insufficient disk")):
        return RenderFailureReport(
            category="disk_space",
            title="Not enough disk space",
            summary="The export could not finish because the destination disk appears to be full.",
            actions=(
                "Free space on the output drive.",
                "Export to another drive.",
                "Use a shorter range or lower quality preset.",
            ),
            raw_tail=tail,
            context=context,
        )

    if _contains_any(low, ("no such file or directory", "error opening input", "failed to open", "cannot find the file")):
        return RenderFailureReport(
            category="missing_media",
            title="Missing or inaccessible media",
            summary="One of the source, overlay, or temporary media files could not be opened.",
            actions=(
                "Open Media Health or Relink and repair missing media.",
                "Avoid moving source files while a render is running.",
                "Retry after confirming the source and output folders still exist.",
            ),
            raw_tail=tail,
            context=context,
        )

    if _contains_any(low, ("invalid data found", "moov atom not found", "could not find codec parameters", "unsupported codec")):
        return RenderFailureReport(
            category="unsupported_media",
            title="Unsupported or damaged media",
            summary="FFmpeg could not decode one of the inputs reliably.",
            actions=(
                "Transcode the source clip to H.264/AAC MP4 and relink it.",
                "Try generating a proxy for the clip.",
                "Remove the last added clip/effect to isolate the bad input.",
            ),
            raw_tail=tail,
            context=context,
        )

    if _contains_any(low, ("unknown encoder", "encoder not found", "unknown decoder", "library configuration mismatch")):
        return RenderFailureReport(
            category="encoder_unavailable",
            title="Encoder is unavailable",
            summary="The selected output codec is not available in the current FFmpeg build.",
            actions=(
                "Switch export format to MP4/H.264.",
                "Install or bundle an FFmpeg build with the requested encoder.",
                "Retry with the Standard or High quality preset.",
            ),
            raw_tail=tail,
            context=context,
        )

    if _contains_any(low, ("error initializing complex filters", "no such filter", "filter not found", "invalid argument", "cannot configure filter graph")):
        return RenderFailureReport(
            category="filter_graph",
            title="Effect/filter graph failed",
            summary="The export filter graph could not be built or initialized.",
            actions=(
                "Disable the most recent effect, LUT, transition, or nested sequence and retry.",
                "Check whether a LUT file path still exists.",
                "Try rendering a shorter range around the failing area.",
            ),
            raw_tail=tail,
            context=context,
        )

    if _contains_any(low, ("spine", "live2d", "actor overlay", "actor encode")):
        return RenderFailureReport(
            category="actor_bake",
            title="Actor baking failed",
            summary="A Spine or Live2D overlay failed while being pre-rendered for export.",
            actions=(
                "Open the actor editor and confirm the model renders in preview.",
                "Try disabling that actor track and export again.",
                "Check missing texture/atlas/model paths.",
            ),
            raw_tail=tail,
            context=context,
        )

    if _contains_any(low, ("cannot allocate memory", "out of memory", "memory allocation")):
        return RenderFailureReport(
            category="memory",
            title="Render ran out of memory",
            summary="The export needed more memory than the process could allocate.",
            actions=(
                "Use proxy media or lower export resolution.",
                "Close other heavy applications.",
                "Render a shorter range and combine the segments later.",
            ),
            raw_tail=tail,
            context=context,
        )

    if "output file not written" in low:
        return RenderFailureReport(
            category="empty_output",
            title="Output was not written",
            summary="The encoder finished without producing a valid output file.",
            actions=(
                "Check that the render range contains visible video.",
                "Choose a different output folder.",
                "Retry with MP4/H.264 to rule out container-specific failure.",
            ),
            raw_tail=tail,
            context=context,
        )

    return RenderFailureReport(
        category="unknown",
        title="Render failed",
        summary="The encoder stopped before the export could complete.",
        actions=(
            "Retry a short range around the failure point.",
            "Try MP4/H.264 with the Standard quality preset.",
            "Check Media Health for missing or damaged inputs.",
        ),
        raw_tail=tail,
        context=context,
    )


def format_render_failure_diagnostics(reason: str, job: Any | None = None) -> str:
    report = diagnose_render_failure(reason, job)
    pieces = [f"{report.title}: {report.summary}"]
    if report.context:
        pieces.append("Context: " + " | ".join(report.context))
    if report.actions:
        pieces.append("Try: " + " / ".join(report.actions))
    if report.raw_tail:
        pieces.append("Raw: " + report.raw_tail)
    return " | ".join(pieces)


def format_render_failure_message(reason: str, job: Any | None = None) -> str:
    report = diagnose_render_failure(reason, job)
    lines = [report.title, "", report.summary]
    if report.context:
        lines.extend(["", "Context:", *[f"- {item}" for item in report.context]])
    if report.actions:
        lines.extend(["", "Try:", *[f"- {item}" for item in report.actions]])
    if report.raw_tail:
        lines.extend(["", "Raw encoder message:", report.raw_tail])
    return "\n".join(lines)
