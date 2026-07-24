"""Qt-free multimodal request and proposal core for Motion Designer AI."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import mimetypes
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from .schema import MotionBehaviorRef, MotionComposition, MotionLayer, SourceRef, new_motion_id
from .validation import validate_composition


MOTION_AI_REQUEST_SCHEMA = "tigercapture.motion.ai.request.v1"
MOTION_AI_PROPOSAL_SCHEMA = "tigercapture.motion.ai.proposal.v1"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".srt", ".vtt"}
MAX_TEXT_ATTACHMENT_CHARS = 64_000


@dataclass(slots=True)
class MotionAIReference:
    kind: str
    name: str = ""
    uri: str = ""
    text: str = ""
    mime_type: str = ""
    id: str = field(default_factory=lambda: new_motion_id("reference"))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "uri": self.uri,
            "text": self.text,
            "mime_type": self.mime_type,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MotionAIReference":
        kind = str(data.get("kind") or "").strip().lower()
        if kind not in {"image", "text"}:
            raise ValueError(f"unsupported Motion AI reference kind: {kind or 'empty'}")
        return cls(
            id=str(data.get("id") or new_motion_id("reference")),
            kind=kind,
            name=str(data.get("name") or ""),
            uri=str(data.get("uri") or ""),
            text=str(data.get("text") or "")[:MAX_TEXT_ATTACHMENT_CHARS],
            mime_type=str(data.get("mime_type") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class MotionAIRequest:
    composition_id: str
    prompt: str = ""
    references: list[MotionAIReference] = field(default_factory=list)
    provider: str = "local_layout"
    id: str = field(default_factory=lambda: new_motion_id("ai_request"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": MOTION_AI_REQUEST_SCHEMA,
            "id": self.id,
            "composition_id": self.composition_id,
            "prompt": self.prompt,
            "provider": self.provider,
            "references": [item.to_dict() for item in self.references],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MotionAIRequest":
        return cls(
            id=str(data.get("id") or new_motion_id("ai_request")),
            composition_id=str(data.get("composition_id") or ""),
            prompt=str(data.get("prompt") or "").strip(),
            provider=str(data.get("provider") or "local_layout"),
            references=[
                MotionAIReference.from_dict(item)
                for item in data.get("references", [])
                if isinstance(item, Mapping)
            ],
        )


@dataclass(slots=True)
class MotionAIProposal:
    composition_id: str
    request_id: str
    layers: list[MotionLayer] = field(default_factory=list)
    summary: str = ""
    warnings: list[str] = field(default_factory=list)
    analysis: dict[str, Any] = field(default_factory=dict)
    provider: str = "local_layout"
    id: str = field(default_factory=lambda: new_motion_id("ai_proposal"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": MOTION_AI_PROPOSAL_SCHEMA,
            "id": self.id,
            "composition_id": self.composition_id,
            "request_id": self.request_id,
            "provider": self.provider,
            "summary": self.summary,
            "warnings": list(self.warnings),
            "analysis": dict(self.analysis),
            "layers": [item.to_dict() for item in self.layers],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MotionAIProposal":
        return cls(
            id=str(data.get("id") or new_motion_id("ai_proposal")),
            composition_id=str(data.get("composition_id") or ""),
            request_id=str(data.get("request_id") or ""),
            provider=str(data.get("provider") or "local_layout"),
            summary=str(data.get("summary") or ""),
            warnings=[str(item) for item in data.get("warnings", [])],
            analysis=dict(data.get("analysis") or {}),
            layers=[MotionLayer.from_dict(item) for item in data.get("layers", []) if isinstance(item, Mapping)],
        )


def reference_from_path(path: str | Path) -> MotionAIReference:
    source = Path(path).expanduser()
    if not source.is_file():
        raise ValueError(f"reference file not found: {source}")
    suffix = source.suffix.lower()
    mime_type = mimetypes.guess_type(str(source))[0] or "application/octet-stream"
    if suffix in IMAGE_EXTENSIONS:
        return MotionAIReference(kind="image", name=source.name, uri=str(source.resolve()), mime_type=mime_type)
    if suffix in TEXT_EXTENSIONS:
        with source.open("r", encoding="utf-8", errors="replace") as stream:
            text = stream.read(MAX_TEXT_ATTACHMENT_CHARS)
        return MotionAIReference(
            kind="text", name=source.name, uri=str(source.resolve()), text=text, mime_type=mime_type,
        )
    raise ValueError(f"unsupported Motion AI reference type: {source.suffix or source.name}")


def references_from_paths(paths: Iterable[str | Path]) -> tuple[list[MotionAIReference], list[str]]:
    references: list[MotionAIReference] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for value in paths:
        try:
            item = reference_from_path(value)
        except (OSError, ValueError) as exc:
            warnings.append(str(exc))
            continue
        identity = f"{item.kind}:{item.uri.lower()}"
        if identity in seen:
            continue
        seen.add(identity)
        references.append(item)
    return references, warnings


def _prompt_behavior(prompt: str, duration_ms: int) -> MotionBehaviorRef | None:
    normalized = prompt.casefold()
    span = min(max(1, duration_ms), 800)
    if any(token in normalized for token in ("slide", "슬라이드", "밀려", "들어오")):
        return MotionBehaviorRef(
            kind="slide", start_ms=0, end_ms=span,
            params={"direction": "in", "distance": [180.0, 0.0]},
        )
    if any(token in normalized for token in ("pop", "팝", "튀어")):
        return MotionBehaviorRef(kind="pop", start_ms=0, end_ms=span, params={"from": .8, "overshoot": .12})
    if any(token in normalized for token in ("fade", "페이드", "서서히")):
        return MotionBehaviorRef(kind="fade", start_ms=0, end_ms=span, params={"direction": "in"})
    return None


def _quoted_titles(prompt: str) -> list[str]:
    matches = re.findall(r'["“”\'‘’]([^"“”\'‘’]{1,180})["“”\'‘’]', prompt)
    return [" ".join(item.split()) for item in matches if item.strip()]


def _image_layout(count: int, width: int, height: int, prompt: str) -> list[tuple[float, float, float, float, str]]:
    if count <= 0:
        return []
    normalized = prompt.casefold()
    full_bleed = count == 1 and any(
        token in normalized for token in ("background", "backdrop", "full bleed", "배경", "풀블리드", "꽉")
    )
    if full_bleed:
        return [(width / 2, height / 2, width, height, "cover")]
    columns = min(3, count)
    rows = int(math.ceil(count / columns))
    gap = max(16.0, min(width, height) * .025)
    area_width = width * .82
    area_height = height * (.68 if rows == 1 else .72)
    cell_width = max(1.0, (area_width - gap * (columns - 1)) / columns)
    cell_height = max(1.0, (area_height - gap * (rows - 1)) / rows)
    left = (width - area_width) / 2
    top = height * .19
    rows_out: list[tuple[float, float, float, float, str]] = []
    for index in range(count):
        row, column = divmod(index, columns)
        x = left + column * (cell_width + gap) + cell_width / 2
        y = top + row * (cell_height + gap) + cell_height / 2
        rows_out.append((x, y, cell_width, cell_height, "contain"))
    return rows_out


def build_motion_ai_proposal(
    composition: MotionComposition,
    prompt: str = "",
    references: Iterable[MotionAIReference | Mapping[str, Any]] = (),
    *,
    provider: str = "local_layout",
) -> MotionAIProposal:
    normalized_refs = [
        item if isinstance(item, MotionAIReference) else MotionAIReference.from_dict(item)
        for item in references
    ]
    request = MotionAIRequest(
        composition_id=composition.id,
        prompt=str(prompt or "").strip(),
        references=normalized_refs,
        provider=provider,
    )
    images = [item for item in normalized_refs if item.kind == "image"]
    texts = [item for item in normalized_refs if item.kind == "text" and item.text.strip()]
    warnings: list[str] = []
    layers: list[MotionLayer] = []
    behavior = _prompt_behavior(request.prompt, composition.duration_ms)

    for index, (reference, layout) in enumerate(zip(images, _image_layout(
        len(images), composition.width, composition.height, request.prompt,
    ))):
        x, y, layer_width, layer_height, fit = layout
        if reference.uri.startswith(("http://", "https://")):
            warnings.append(f"Remote image is context-only until downloaded: {reference.name or reference.uri}")
            continue
        if reference.uri and not Path(reference.uri).is_file():
            warnings.append(f"Image needs relink before rendering: {reference.name or reference.uri}")
        layer = MotionLayer(
            name=reference.name or f"AI Image {index + 1}",
            layer_type="image",
            source=SourceRef(kind="image", uri=reference.uri, params={
                "width": int(round(layer_width)), "height": int(round(layer_height)), "fit": fit,
            }),
            out_ms=composition.duration_ms,
            metadata={"ai_request_id": request.id, "ai_reference_id": reference.id},
        )
        layer.transform.position.default = [float(x), float(y)]
        if behavior is not None:
            layer.behaviors = [MotionBehaviorRef.from_dict(behavior.to_dict())]
        layers.append(layer)

    text_values = [item.text.strip() for item in texts]
    text_values.extend(_quoted_titles(request.prompt))
    for index, text in enumerate(text_values[:8]):
        font_size = max(24, int(composition.height * (.07 if index == 0 else .045)))
        layer = MotionLayer(
            name=(texts[index].name if index < len(texts) else "AI Title") or f"AI Text {index + 1}",
            layer_type="text",
            source=SourceRef(kind="typography", params={
                "text": text[:1200], "font_family": "Segoe UI", "font_size": font_size,
                "font_weight": 700 if index == 0 else 500, "fill": "#f4f6f8",
                "stroke": "#111317cc", "stroke_width": 1.5,
                "alignment": "center", "width": int(composition.width * .82),
                "height": int(composition.height * .2), "line_height": 1.15,
            }),
            out_ms=composition.duration_ms,
            metadata={"ai_request_id": request.id},
        )
        layer.transform.position.default = [composition.width / 2, composition.height * (.1 + index * .11)]
        if behavior is not None:
            layer.behaviors = [MotionBehaviorRef.from_dict(behavior.to_dict())]
        layers.append(layer)

    if not layers:
        warnings.append("No layer-ready image or quoted/text reference was supplied; the request remains context-only.")
    summary = (
        f"Prepared {len(layers)} layer(s) from {len(images)} image and {len(texts)} text reference(s)."
    )
    from .ai_planner import analyze_motion_ai_layers

    analysis = analyze_motion_ai_layers(composition, layers)
    warnings.extend(str(item) for item in analysis.get("warnings", []))
    warnings = list(dict.fromkeys(warnings))
    return MotionAIProposal(
        composition_id=composition.id,
        request_id=request.id,
        layers=layers,
        summary=summary,
        warnings=warnings,
        analysis=analysis,
        provider=provider,
    )


def apply_motion_ai_proposal(
    composition: MotionComposition,
    proposal: MotionAIProposal | Mapping[str, Any],
) -> MotionComposition:
    normalized = proposal if isinstance(proposal, MotionAIProposal) else MotionAIProposal.from_dict(proposal)
    if normalized.composition_id and normalized.composition_id != composition.id:
        raise ValueError("Motion AI proposal targets a different composition")
    generation = normalized.analysis.get("generation_plan") if isinstance(normalized.analysis, Mapping) else None
    if isinstance(generation, Mapping):
        base_revision = int(generation.get("base_revision", composition.revision) or composition.revision)
        if base_revision != composition.revision:
            raise ValueError("Motion AI proposal was created for a stale composition revision")
    candidate = MotionComposition.from_dict(composition.to_dict())
    if not normalized.layers:
        return candidate
    existing_ids = {item.id for item in candidate.layers}
    for item in normalized.layers:
        layer = MotionLayer.from_dict(item.to_dict())
        if layer.id in existing_ids:
            layer.id = new_motion_id("layer")
        existing_ids.add(layer.id)
        layer.out_ms = max(layer.in_ms + 1, min(composition.duration_ms, layer.out_ms))
        candidate.layers.append(layer)
    candidate.revision += 1
    report = validate_composition(candidate)
    if not report.ok:
        raise ValueError(report.issues[0].message)
    return candidate
