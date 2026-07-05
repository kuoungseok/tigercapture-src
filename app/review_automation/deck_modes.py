from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


DECK_MODES: tuple[str, ...] = ("summary", "detailed", "evidence-full")

DECK_MODE_LABELS: dict[str, str] = {
    "summary": "Summary",
    "detailed": "Detailed",
    "evidence-full": "Evidence Full",
}

DECK_MODE_DESCRIPTIONS: dict[str, str] = {
    "summary": "4장 안팎의 빠른 소개용 요약 덱입니다.",
    "detailed": "제품 기능군을 챕터별로 설명하는 30장 안팎의 발표용 상세 덱입니다.",
    "evidence-full": "QA Dashboard 항목을 appendix로 최대한 포함하는 증거 중심 덱입니다.",
}


DECK_MODE_DESCRIPTIONS = {
    "summary": "Fast product-catalog introduction deck.",
    "detailed": "Feature-group presentation with editor-work screenshots.",
    "evidence-full": "Internal appendix deck with QA and evidence rows.",
}


@dataclass(frozen=True)
class DeckTopic:
    id: str
    title: str
    category: str
    bullets: tuple[str, ...]
    qa_keywords: tuple[str, ...] = ()


TOPICS: tuple[DeckTopic, ...] = (
    DeckTopic(
        id="screen_recording",
        title="Screen Recording And Auto Polish",
        category="Creator Capture",
        bullets=(
            "Screenshot, GIF, MP4 capture and Windows Graphics Capture support.",
            "Cursor sidecar metadata drives smoothing, click rings, hotkey badges, drag trails, and auto zoom.",
            "Screen Studio-style export handoff keeps tutorial polish in the local workflow.",
        ),
        qa_keywords=("screenstudio", "editor_e2e_smoke"),
    ),
    DeckTopic(
        id="creator_assist",
        title="Creator Assist And CapCut-Style Workflows",
        category="Creator Workflow",
        bullets=(
            "Creator Assist plans captions, shorts ranges, vertical reframes, publish copy, and render jobs.",
            "CapCut-style quick result, publish, voice, prompt edit, collaboration, and handoff reports track parity gaps.",
            "Local-first workflow avoids requiring a cloud API for the core path.",
        ),
        qa_keywords=("capcut", "creator_asset_packs"),
    ),
    DeckTopic(
        id="multilingual_localization",
        title="Multilingual UI And Localization QA",
        category="Product Foundation",
        bullets=(
            "Runtime language switching covers Korean, English, Japanese, Simplified Chinese, French, and German.",
            "Locale tables are audited for missing keys, placeholder mismatches, and mojibake/tofu-risk tokens.",
            "CJK-safe font fallback is used for review HTML, PNG, and PPT outputs so captured proof remains readable.",
        ),
        qa_keywords=("localization", "locale", "i18n", "language"),
    ),
    DeckTopic(
        id="ai_script_edit",
        title="AI Script Edit And Local LLM",
        category="AI Assistance",
        bullets=(
            "Bottom AI Command dock and Script Edit panel convert text/transcripts into reviewed edit plans.",
            "Provider state is explicit: rule-based, local LLM, Qwen-compatible, or configured external provider.",
            "Safety gates prevent marketing smart-AI claims when corpus quality evidence is missing.",
        ),
        qa_keywords=("ai_edit", "local_ml"),
    ),
    DeckTopic(
        id="timeline_editing",
        title="Timeline, Media Pool, And Workbench",
        category="Editing Core",
        bullets=(
            "Timeline model covers cuts, splits, markers, speed segments, fades, actor tracks, and zoom actors.",
            "Media Pool tracks thumbnails, relink health, proxy state, actor QA badges, and preset browsing.",
            "Workbench connects node graph effects, masks, clip FX stack, metadata, and inspectors.",
        ),
        qa_keywords=("timeline", "preset_application", "node_graph"),
    ),
    DeckTopic(
        id="actors",
        title="Live2D, Spine, And NIKKE Actor Tracks",
        category="Actor Overlay",
        bullets=(
            "Live2D and Spine clips live on dedicated actor tracks and bake into final exports.",
            "Live2D has model3/moc/texture/motion/physics dependency checks.",
            "Spine/NIKKE and VTuber bridge work stay guarded until their visual/runtime evidence is strong enough.",
        ),
        qa_keywords=("actor", "spine", "live2d", "editor_e2e_smoke"),
    ),
    DeckTopic(
        id="color_audio_vfx",
        title="Color, Audio, Masks, And VFX",
        category="Finishing",
        bullets=(
            "Color management covers Rec.709, sRGB, HDR PQ/HLG, P3, ACES intent, LUTs, and scopes.",
            "Audio workflow includes lanes, Sound Editor, AI Master presets, loudness, true peak, and separation fallback.",
            "Masks, rotoscope, chroma key, stabilization, background removal, and tracked effects are preview/export targets.",
        ),
        qa_keywords=("color", "audio", "visual", "micro_interactions"),
    ),
    DeckTopic(
        id="export_parity",
        title="Export, Render Queue, And Preview Parity",
        category="Delivery",
        bullets=(
            "MP4, WebM, MOV, 1080p, 4K, vertical, square, and HDR metadata paths are tracked.",
            "Raw pre-render fallback handles preview-only effects that cannot safely map to FFmpeg.",
            "GPU preview/export parity checks cover node graphs, masks, actors, typography, and color metadata.",
        ),
        qa_keywords=("export", "gpu", "parity", "editor_export"),
    ),
    DeckTopic(
        id="ar_pbr_3d",
        title="AR/PBR 3D Compositor",
        category="3D Compositing",
        bullets=(
            "AR/PBR track schema, depth/camera solve, road-plane placement, and HDR environment preview are documented.",
            "Attachment stability checks whether 3D models stick to video motion.",
            "Camera-scene assets can be reviewed inside the editor with real preview evidence.",
        ),
        qa_keywords=("ar_pbr", "gpu_preview_pixel_collision"),
    ),
    DeckTopic(
        id="performance_health",
        title="Performance, Health, And Native Worker",
        category="Reliability",
        bullets=(
            "Health Center summarizes crash status, QA failures, render failures, media health, and actor risks.",
            "Preview/cache bottlenecks are measured before moving work into OpenCV, OpenGL, FFmpeg, proxy, or Rust.",
            "Native worker remains optional and follows a JSON-lines process boundary.",
        ),
        qa_keywords=("professional", "project_qa", "loading", "crash", "runtime"),
    ),
    DeckTopic(
        id="productization_release",
        title="Productization, Release Evidence, And Positioning",
        category="Release",
        bullets=(
            "Final readiness, productization loop, release gap closure, and release evidence reports gate claims.",
            "Public positioning guardrails stop unfinished parity claims from leaking into marketing material.",
            "Review automation reuses the same evidence graph for docs, screenshots, HTML, and PPT.",
        ),
        qa_keywords=("final_product", "product", "release", "public_positioning", "review_automation"),
    ),
)


def normalize_deck_mode(value: str | None) -> str:
    raw = str(value or "summary").strip().lower().replace("_", "-")
    aliases = {
        "short": "summary",
        "quick": "summary",
        "detail": "detailed",
        "full": "evidence-full",
        "evidence": "evidence-full",
        "evidence_full": "evidence-full",
    }
    mode = aliases.get(raw, raw)
    return mode if mode in DECK_MODES else "summary"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _report_summary(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary")
    if isinstance(summary, Mapping):
        compact = []
        for key, value in list(summary.items())[:6]:
            if isinstance(value, (str, int, float, bool)) or value is None:
                compact.append(f"{key}={value}")
        if compact:
            return ", ".join(compact)
    if payload:
        return "report present"
    return "missing"


def qa_catalog(project_root: str | Path) -> list[dict[str, Any]]:
    from app.qa_dashboard import REPORT_SPECS

    root = Path(project_root)
    rows: list[dict[str, Any]] = []
    for label, raw_path, kind in REPORT_SPECS:
        path = root / raw_path
        payload = _load_json(path) if path.exists() else {}
        rows.append(
            {
                "label": label,
                "kind": kind,
                "path": raw_path,
                "exists": path.exists(),
                "ok": bool(payload.get("ok", True)) if payload else False,
                "summary": _report_summary(payload),
            }
        )
    return rows


def topic_qa_rows(topic: DeckTopic, qa_rows: Iterable[Mapping[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    keywords = tuple(keyword.lower() for keyword in topic.qa_keywords)
    for row in qa_rows:
        haystack = f"{row.get('label', '')} {row.get('kind', '')} {row.get('path', '')}".lower()
        if any(keyword in haystack for keyword in keywords):
            out.append(dict(row))
        if len(out) >= limit:
            break
    return out


def build_deck_plan(
    *,
    mode: str,
    project_root: str | Path,
    review_features: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    deck_mode = normalize_deck_mode(mode)
    qa_rows = qa_catalog(project_root)
    features = [dict(feature) for feature in review_features]
    topics = []
    for topic in TOPICS:
        topics.append(
            {
                "id": topic.id,
                "title": topic.title,
                "category": topic.category,
                "bullets": list(topic.bullets),
                "qa_rows": topic_qa_rows(topic, qa_rows),
            }
        )
    if deck_mode == "summary":
        estimated_slides = 4
    elif deck_mode == "detailed":
        estimated_slides = 3 + len(topics) * 2 + 1
    else:
        estimated_slides = 4 + len(topics) + len(qa_rows)
    return {
        "mode": deck_mode,
        "label": DECK_MODE_LABELS[deck_mode],
        "description": DECK_MODE_DESCRIPTIONS[deck_mode],
        "estimated_slides": estimated_slides,
        "review_features": features,
        "topics": topics,
        "qa_rows": qa_rows,
    }
