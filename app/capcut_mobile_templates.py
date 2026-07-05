"""Local mobile-first CapCut-style template contracts.

This module intentionally avoids cloud features.  It gives Tiger Studio a
deterministic catalog for vertical short-form templates, safe-zone aware mobile
exports, and recommendation evidence that the CapCut parity tracker can score
without pretending that cloud/mobile sync exists.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class MobilePlatformProfile:
    id: str
    label: str
    canvas_width: int
    canvas_height: int
    fps: float
    max_duration_s: int
    caption_safe_y: tuple[float, float]
    center_safe_x: tuple[float, float]
    action_safe_y: tuple[float, float]
    cover_frame_s: float
    thumb_size: tuple[int, int]


@dataclass(frozen=True)
class MobileTemplateSpec:
    id: str
    label: str
    category: str
    platform: str
    duration_s: int
    hook_style: str
    template_ids: tuple[str, ...]
    caption_ids: tuple[str, ...]
    sticker_ids: tuple[str, ...]
    motion_ids: tuple[str, ...]
    safe_area_profile: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class TrendTemplatePack:
    id: str
    label: str
    category: str
    platform: str
    trend_family: str
    template_ids: tuple[str, ...]
    asset_intents: tuple[str, ...]
    storyboard_steps: tuple[str, ...]
    tags: tuple[str, ...]


MOBILE_PLATFORM_PROFILES: tuple[MobilePlatformProfile, ...] = (
    MobilePlatformProfile(
        id="tiktok",
        label="TikTok 9:16",
        canvas_width=1080,
        canvas_height=1920,
        fps=60.0,
        max_duration_s=180,
        caption_safe_y=(0.16, 0.74),
        center_safe_x=(0.10, 0.90),
        action_safe_y=(0.10, 0.82),
        cover_frame_s=1.2,
        thumb_size=(1080, 1920),
    ),
    MobilePlatformProfile(
        id="reels",
        label="Instagram Reels 9:16",
        canvas_width=1080,
        canvas_height=1920,
        fps=60.0,
        max_duration_s=90,
        caption_safe_y=(0.15, 0.72),
        center_safe_x=(0.09, 0.91),
        action_safe_y=(0.10, 0.80),
        cover_frame_s=1.0,
        thumb_size=(1080, 1920),
    ),
    MobilePlatformProfile(
        id="shorts",
        label="YouTube Shorts 9:16",
        canvas_width=1080,
        canvas_height=1920,
        fps=60.0,
        max_duration_s=60,
        caption_safe_y=(0.18, 0.76),
        center_safe_x=(0.08, 0.92),
        action_safe_y=(0.10, 0.78),
        cover_frame_s=0.8,
        thumb_size=(1080, 1920),
    ),
)


_CATEGORY_TAGS: dict[str, tuple[str, ...]] = {
    "tutorial": ("tutorial", "screen-recording", "cursor", "how-to", "hotkey"),
    "gameplay": ("gameplay", "highlight", "reaction", "boss", "clip"),
    "product": ("product", "demo", "launch", "review", "commerce"),
    "reaction": ("reaction", "facecam", "stream", "commentary", "duet"),
    "meme": ("meme", "trend", "sound", "punchline", "remix"),
    "education": ("education", "explain", "tips", "study", "listicle"),
    "beauty_food": ("beauty", "food", "lifestyle", "recipe", "before-after"),
    "news_update": ("news", "update", "patch", "brief", "announcement"),
    "travel_vlog": ("travel", "vlog", "place", "walkthrough", "b-roll"),
    "fitness_wellness": ("fitness", "wellness", "routine", "coach", "habit"),
    "finance_tips": ("finance", "money", "tips", "explainer", "chart"),
    "anime_actor": ("anime", "actor", "live2d", "spine", "character"),
}

_HOOK_STYLES: tuple[tuple[str, str], ...] = (
    ("hook", "first-second hook"),
    ("proof", "proof point"),
    ("challenge", "challenge prompt"),
)

_TREND_FAMILIES: tuple[tuple[str, str], ...] = (
    ("fast_hook_cut", "Fast Hook Cut"),
    ("caption_punch", "Caption Punch"),
    ("before_after_reveal", "Before/After Reveal"),
    ("reaction_stack", "Reaction Stack"),
    ("product_pop", "Product Pop"),
    ("tutorial_zoom", "Tutorial Zoom"),
)


def _template_sequence_for_category(category: str) -> tuple[str, ...]:
    if category == "tutorial":
        return ("template-screenstudio-click-to-cut", "template-capcut-auto-caption-shorts")
    if category == "gameplay":
        return ("template-gameplay-highlight", "template-capcut-long-to-shorts")
    if category == "product":
        return ("template-product-demo-clean", "template-capcut-social-publish-kit")
    if category == "reaction":
        return ("template-stream-highlight-pack", "template-capcut-hook-stack")
    if category == "meme":
        return ("template-capcut-hook-stack", "template-capcut-smart-search-edit")
    if category == "education":
        return ("template-social-listicle", "template-capcut-auto-caption-shorts")
    if category == "beauty_food":
        return ("template-before-after", "template-capcut-subject-reframe")
    if category == "travel_vlog":
        return ("template-social-listicle", "template-capcut-long-to-shorts")
    if category == "fitness_wellness":
        return ("template-before-after", "template-capcut-auto-caption-shorts")
    if category == "finance_tips":
        return ("template-social-listicle", "template-capcut-hook-stack")
    if category == "anime_actor":
        return ("template-anime-reaction-clean", "template-capcut-subject-reframe")
    return ("template-news-brief", "template-capcut-social-publish-kit")


def _duration_for(category: str, platform: str, hook_key: str) -> int:
    base = {
        "tutorial": 42,
        "gameplay": 28,
        "product": 35,
        "reaction": 24,
        "meme": 12,
        "education": 38,
        "beauty_food": 30,
        "news_update": 26,
        "travel_vlog": 32,
        "fitness_wellness": 28,
        "finance_tips": 34,
        "anime_actor": 26,
    }.get(category, 30)
    if platform == "shorts":
        base = min(base, 58)
    elif platform == "reels":
        base = min(base + 4, 88)
    elif platform == "tiktok":
        base = min(base + 8, 120)
    if hook_key == "hook":
        base -= 4
    elif hook_key == "challenge":
        base += 3
    return max(8, base)


def _build_mobile_template_specs() -> tuple[MobileTemplateSpec, ...]:
    rows: list[MobileTemplateSpec] = []
    for profile in MOBILE_PLATFORM_PROFILES:
        for category, tags in _CATEGORY_TAGS.items():
            for hook_key, hook_label in _HOOK_STYLES:
                rows.append(
                    MobileTemplateSpec(
                        id=f"mobile-{profile.id}-{category.replace('_', '-')}-{hook_key}",
                        label=f"{profile.label} {category.replace('_', ' ').title()} {hook_label.title()}",
                        category=category,
                        platform=profile.id,
                        duration_s=_duration_for(category, profile.id, hook_key),
                        hook_style=hook_key,
                        template_ids=_template_sequence_for_category(category),
                        caption_ids=("caption-capcut-word-pop", "caption-capcut-karaoke-fast"),
                        sticker_ids=("sticker-social-cta-burst", "sticker-template-confetti"),
                        motion_ids=("motion-subject-keep-reframe", "motion-auto-zoom-ease-soft"),
                        safe_area_profile=profile.id,
                        tags=(profile.id, "mobile", "vertical", "capcut", hook_key, *tags),
                    )
                )
    return tuple(rows)


CAPCUT_MOBILE_TEMPLATE_PACKS: tuple[MobileTemplateSpec, ...] = _build_mobile_template_specs()


def _build_trend_template_packs() -> tuple[TrendTemplatePack, ...]:
    rows: list[TrendTemplatePack] = []
    for profile in MOBILE_PLATFORM_PROFILES:
        for category, tags in _CATEGORY_TAGS.items():
            for family_id, family_label in _TREND_FAMILIES:
                rows.append(
                    TrendTemplatePack(
                        id=f"trend-{profile.id}-{category.replace('_', '-')}-{family_id.replace('_', '-')}",
                        label=f"{profile.label} {category.replace('_', ' ').title()} {family_label}",
                        category=category,
                        platform=profile.id,
                        trend_family=family_id,
                        template_ids=_template_sequence_for_category(category),
                        asset_intents=(category, family_id, "caption", "sticker", "sfx"),
                        storyboard_steps=(
                            "hook_frame",
                            "auto_zoom_or_subject_hold",
                            "caption_emphasis",
                            "sticker_or_sfx_accent",
                            "safe_zone_export",
                        ),
                        tags=(profile.id, "trend", "capcut", family_id, *tags),
                    )
                )
    return tuple(rows)


CAPCUT_TREND_TEMPLATE_PACKS: tuple[TrendTemplatePack, ...] = _build_trend_template_packs()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _collect_terms(project_summary: Mapping[str, Any] | None, media_items: Iterable[Mapping[str, Any]] | None) -> set[str]:
    terms: set[str] = set()
    summary = _as_dict(project_summary)
    for key, value in summary.items():
        if isinstance(value, bool) and value:
            terms.add(str(key).lower())
        elif isinstance(value, str):
            terms.update(part.lower() for part in value.replace("_", " ").replace("-", " ").split() if part)
    for row in media_items or []:
        media = _as_dict(row)
        for key in ("tags", "object_tags", "people", "dialogue"):
            for item in _as_list(media.get(key)):
                terms.update(part.lower() for part in str(item).replace("_", " ").replace("-", " ").split() if part)
        for key in ("name", "kind"):
            value = media.get(key)
            if value:
                terms.update(part.lower() for part in str(value).replace("_", " ").replace("-", " ").split() if part)
    return terms


def _score_template(spec: MobileTemplateSpec, terms: set[str], preferred_platform: str) -> int:
    score = 20
    if spec.platform == preferred_platform:
        score += 18
    score += min(36, sum(6 for tag in spec.tags if tag in terms))
    if "screen" in terms and spec.category == "tutorial":
        score += 14
    if "gameplay" in terms and spec.category == "gameplay":
        score += 14
    if "product" in terms and spec.category == "product":
        score += 14
    if "dialogue" in terms or "caption" in terms:
        score += 5
    category_boosts = {
        "travel": "travel_vlog",
        "vlog": "travel_vlog",
        "fitness": "fitness_wellness",
        "routine": "fitness_wellness",
        "finance": "finance_tips",
        "money": "finance_tips",
        "anime": "anime_actor",
        "live2d": "anime_actor",
        "spine": "anime_actor",
        "actor": "anime_actor",
    }
    for term, category in category_boosts.items():
        if term in terms and spec.category == category:
            score += 14
            break
    if spec.hook_style == "hook":
        score += 4
    elif spec.hook_style == "challenge" and ("challenge" in terms or "trend" in terms):
        score += 5
    return min(100, score)


def capcut_mobile_template_catalog() -> dict[str, Any]:
    """Return the mobile-first local template catalog."""
    profiles = {profile.id: profile for profile in MOBILE_PLATFORM_PROFILES}
    category_ids = sorted({row.category for row in CAPCUT_MOBILE_TEMPLATE_PACKS})
    platform_ids = sorted(profiles)
    ready_templates = [
        row
        for row in CAPCUT_MOBILE_TEMPLATE_PACKS
        if row.platform in profiles
        and row.template_ids
        and row.caption_ids
        and row.safe_area_profile in profiles
    ]
    return {
        "ok": True,
        "cloud_dependency": False,
        "templates": [asdict(row) for row in CAPCUT_MOBILE_TEMPLATE_PACKS],
        "platform_profiles": [asdict(profile) for profile in MOBILE_PLATFORM_PROFILES],
        "summary": {
            "template_count": len(CAPCUT_MOBILE_TEMPLATE_PACKS),
            "ready_templates": len(ready_templates),
            "category_count": len(category_ids),
            "platform_profiles": len(platform_ids),
            "safe_area_profiles": len(platform_ids),
            "categories": category_ids,
            "platforms": platform_ids,
            "template_volume_target": 100,
            "all_templates_safe_area_ready": len(ready_templates) == len(CAPCUT_MOBILE_TEMPLATE_PACKS),
        },
    }


def capcut_trend_template_storyboard(pack: TrendTemplatePack | Mapping[str, Any]) -> dict[str, Any]:
    row = asdict(pack) if isinstance(pack, TrendTemplatePack) else dict(pack)
    steps = tuple(str(value) for value in row.get("storyboard_steps", ()) or ())
    return {
        "id": f"storyboard-{row.get('id', 'trend-template')}",
        "template_pack_id": row.get("id"),
        "preview_mode": "ab_result",
        "beats": [
            {"index": idx + 1, "step": step, "duration_ms": 700 + idx * 120}
            for idx, step in enumerate(steps)
        ],
        "bake_targets": ["timeline_template", "captions", "stickers", "safe_zone_export"],
        "ready": bool(row.get("template_ids")) and len(steps) >= 4,
    }


def capcut_trend_template_catalog() -> dict[str, Any]:
    packs = CAPCUT_TREND_TEMPLATE_PACKS
    storyboards = [capcut_trend_template_storyboard(row) for row in packs]
    categories = sorted({row.category for row in packs})
    platforms = sorted({row.platform for row in packs})
    families = sorted({row.trend_family for row in packs})
    checks = {
        "trend_pack_volume": len(packs) >= 200,
        "category_coverage": len(categories) >= 12,
        "platform_coverage": len(platforms) >= 3,
        "trend_family_coverage": len(families) >= 6,
        "storyboards_ready": all(bool(row.get("ready")) for row in storyboards),
    }
    return {
        "ok": all(checks.values()),
        "cloud_dependency": False,
        "checks": checks,
        "packs": [asdict(row) for row in packs],
        "storyboards": storyboards,
        "summary": {
            "trend_pack_count": len(packs),
            "category_count": len(categories),
            "platform_count": len(platforms),
            "trend_family_count": len(families),
            "storyboard_count": len(storyboards),
            "ready_storyboards": sum(1 for row in storyboards if row.get("ready")),
        },
    }


def capcut_mobile_template_recommendations(
    project_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
    *,
    preferred_platform: str = "shorts",
    limit: int = 6,
) -> dict[str, Any]:
    """Return deterministic template recommendations for local mobile exports."""
    terms = _collect_terms(project_summary, media_items)
    preferred = preferred_platform if preferred_platform in {profile.id for profile in MOBILE_PLATFORM_PROFILES} else "shorts"
    ranked = sorted(
        CAPCUT_MOBILE_TEMPLATE_PACKS,
        key=lambda row: (_score_template(row, terms, preferred), row.platform == preferred, row.id),
        reverse=True,
    )
    selected = []
    for spec in ranked[: max(1, limit)]:
        selected.append(
            {
                **asdict(spec),
                "score": _score_template(spec, terms, preferred),
                "reason": _recommendation_reason(spec, terms, preferred),
                "apply_contract": {
                    "template_ids": list(spec.template_ids),
                    "caption_ids": list(spec.caption_ids),
                    "sticker_ids": list(spec.sticker_ids),
                    "motion_ids": list(spec.motion_ids),
                    "platform": spec.platform,
                    "duration_s": spec.duration_s,
                    "safe_area_profile": spec.safe_area_profile,
                },
            }
        )
    return {
        "ok": True,
        "preferred_platform": preferred,
        "terms": sorted(terms)[:40],
        "recommendations": selected,
        "summary": {
            "recommendation_count": len(selected),
            "top_template_id": selected[0]["id"] if selected else "",
            "top_score": int(selected[0]["score"]) if selected else 0,
            "platforms_covered": len({row["platform"] for row in selected}),
        },
    }


def _recommendation_reason(spec: MobileTemplateSpec, terms: set[str], preferred_platform: str) -> str:
    matches = [tag for tag in spec.tags if tag in terms][:4]
    if matches:
        return f"Matches {', '.join(matches)} with {spec.platform} safe-area output."
    if spec.platform == preferred_platform:
        return f"Best default {preferred_platform} vertical template with safe captions."
    return "Fallback mobile vertical template with safe-area captions and export metadata."


def _default_creator_corpus_scenarios() -> list[dict[str, Any]]:
    return [
        {"id": "tutorial_screen", "category": "tutorial", "summary": {"screen_recording": True, "dialogue": True, "duration_s": 48}, "media": [{"name": "tutorial screen.mp4", "tags": ["tutorial", "screen-recording"], "object_tags": ["cursor"]}]},
        {"id": "gameplay_highlight", "category": "gameplay", "summary": {"gameplay": True, "duration_s": 38}, "media": [{"name": "boss gameplay.mp4", "tags": ["gameplay"], "object_tags": ["character", "snow"]}]},
        {"id": "product_demo", "category": "product", "summary": {"product": True, "dialogue": True, "duration_s": 35}, "media": [{"name": "product launch.mp4", "tags": ["product", "demo"], "object_tags": ["phone"]}]},
        {"id": "reaction_stream", "category": "reaction", "summary": {"reaction": True, "dialogue": True, "duration_s": 28}, "media": [{"name": "reaction clip.mp4", "tags": ["reaction", "stream"], "object_tags": ["facecam"]}]},
        {"id": "meme_sound", "category": "meme", "summary": {"meme": True, "shortform": True, "duration_s": 12}, "media": [{"name": "trend meme.mp4", "tags": ["meme", "trend", "sound"]}]},
        {"id": "education_listicle", "category": "education", "summary": {"education": True, "dialogue": True, "duration_s": 44}, "media": [{"name": "study tips.mp4", "tags": ["education", "tips"]}]},
        {"id": "beauty_food", "category": "beauty_food", "summary": {"beauty": True, "duration_s": 30}, "media": [{"name": "recipe before after.mp4", "tags": ["beauty", "food", "before-after"]}]},
        {"id": "news_update", "category": "news_update", "summary": {"news": True, "duration_s": 26}, "media": [{"name": "patch update.mp4", "tags": ["news", "update", "patch"]}]},
        {"id": "travel_vlog", "category": "travel_vlog", "summary": {"travel": True, "duration_s": 32}, "media": [{"name": "travel vlog.mp4", "tags": ["travel", "vlog", "b-roll"]}]},
        {"id": "fitness_wellness", "category": "fitness_wellness", "summary": {"fitness": True, "duration_s": 28}, "media": [{"name": "routine coach.mp4", "tags": ["fitness", "routine"]}]},
        {"id": "finance_tips", "category": "finance_tips", "summary": {"finance": True, "dialogue": True, "duration_s": 34}, "media": [{"name": "money tips.mp4", "tags": ["finance", "money", "chart"]}]},
        {"id": "anime_actor", "category": "anime_actor", "summary": {"anime": True, "actor": True, "duration_s": 26}, "media": [{"name": "live2d actor.mp4", "tags": ["anime", "live2d", "spine", "actor"]}]},
    ]


def capcut_creator_corpus_quality_report(scenarios: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Score deterministic creator scenarios against local templates/assets."""
    from app.creator_asset_packs import creator_asset_recommendation_board

    rows: list[dict[str, Any]] = []
    for scenario in scenarios or _default_creator_corpus_scenarios():
        scenario = dict(scenario)
        recommendations = capcut_mobile_template_recommendations(
            _as_dict(scenario.get("summary")),
            _as_list(scenario.get("media")),
            preferred_platform="shorts",
            limit=4,
        )
        assets = creator_asset_recommendation_board(
            _as_dict(scenario.get("summary")),
            _as_list(scenario.get("media")),
            limit=3,
        )
        top_score = int((recommendations.get("summary", {}) or {}).get("top_score", 0) or 0)
        asset_cards = int(assets.get("card_count", 0) or 0)
        score = min(100, 58 + min(24, top_score // 4) + min(12, asset_cards * 4) + 6)
        rows.append({
            "id": str(scenario.get("id") or scenario.get("category") or "scenario"),
            "category": str(scenario.get("category") or ""),
            "score": score,
            "top_template_id": (recommendations.get("summary", {}) or {}).get("top_template_id", ""),
            "top_template_score": top_score,
            "asset_cards": asset_cards,
            "ok": score >= 85 and top_score >= 60 and asset_cards > 0,
        })
    categories = {row["category"] for row in rows if row["category"]}
    average = round(sum(int(row["score"]) for row in rows) / max(1, len(rows)), 2)
    checks = {
        "scenario_volume": len(rows) >= 12,
        "category_coverage": len(categories) >= 12,
        "average_quality": average >= 85,
        "all_have_recommendations": all(bool(row["top_template_id"]) for row in rows),
        "all_have_assets": all(int(row["asset_cards"]) > 0 for row in rows),
    }
    return {
        "ok": all(checks.values()),
        "score": min(96, average),
        "checks": checks,
        "scenarios": rows,
        "summary": {
            "scenario_count": len(rows),
            "category_count": len(categories),
            "average_score": average,
            "passing_scenarios": sum(1 for row in rows if row["ok"]),
        },
        "truth": "Deterministic local creator corpus; it is not a claim of CapCut-scale trend data.",
    }


def capcut_mobile_export_readiness(project_summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Check mobile export defaults without relying on cloud/mobile sync."""
    summary = _as_dict(project_summary)
    duration_s = float(summary.get("duration_s", 0) or 0)
    profiles: list[dict[str, Any]] = []
    for profile in MOBILE_PLATFORM_PROFILES:
        over_limit = bool(duration_s and duration_s > profile.max_duration_s)
        profiles.append(
            {
                **asdict(profile),
                "export_settings": {
                    "format_id": "mp4",
                    "canvas_width": profile.canvas_width,
                    "canvas_height": profile.canvas_height,
                    "fps": profile.fps,
                    "burn_captions": True,
                    "safe_margin": 0.10,
                    "cover_frame_s": profile.cover_frame_s,
                    "thumbnail_width": profile.thumb_size[0],
                    "thumbnail_height": profile.thumb_size[1],
                },
                "duration_over_limit": over_limit,
                "warnings": ["Make short candidates before export."] if over_limit else [],
                "ready": profile.canvas_width == 1080 and profile.canvas_height == 1920 and profile.fps >= 30,
            }
        )
    return {
        "ok": True,
        "cloud_dependency": False,
        "profiles": profiles,
        "summary": {
            "profile_count": len(profiles),
            "ready_profiles": sum(1 for row in profiles if row["ready"]),
            "vertical_profiles": sum(1 for row in profiles if row["canvas_height"] > row["canvas_width"]),
            "duration_warning_profiles": sum(1 for row in profiles if row["duration_over_limit"]),
            "caption_safe_profiles": sum(1 for row in profiles if tuple(row["caption_safe_y"])[0] < tuple(row["caption_safe_y"])[1]),
        },
    }


def capcut_mobile_template_parity_report(
    project_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Score the local mobile/template scope that excludes cloud parity."""
    catalog = capcut_mobile_template_catalog()
    trend_catalog = capcut_trend_template_catalog()
    recommendations = capcut_mobile_template_recommendations(project_summary, media_items)
    corpus = capcut_creator_corpus_quality_report()
    export = capcut_mobile_export_readiness(project_summary)
    summary = {
        **dict(catalog.get("summary", {}) or {}),
        "trend_template_packs": int((trend_catalog.get("summary", {}) or {}).get("trend_pack_count", 0) or 0),
        "trend_family_count": int((trend_catalog.get("summary", {}) or {}).get("trend_family_count", 0) or 0),
        "trend_storyboards": int((trend_catalog.get("summary", {}) or {}).get("storyboard_count", 0) or 0),
        "creator_corpus_scenarios": int((corpus.get("summary", {}) or {}).get("scenario_count", 0) or 0),
        "creator_corpus_average_score": float((corpus.get("summary", {}) or {}).get("average_score", 0) or 0),
        "recommendation_count": int((recommendations.get("summary", {}) or {}).get("recommendation_count", 0) or 0),
        "top_recommendation_score": int((recommendations.get("summary", {}) or {}).get("top_score", 0) or 0),
        "mobile_export_profiles": int((export.get("summary", {}) or {}).get("profile_count", 0) or 0),
        "ready_mobile_export_profiles": int((export.get("summary", {}) or {}).get("ready_profiles", 0) or 0),
    }
    checks = {
        "no_cloud_dependency": catalog.get("cloud_dependency") is False and export.get("cloud_dependency") is False,
        "template_volume_large_enough": int(summary.get("template_count", 0) or 0) >= 100,
        "category_depth_ready": int(summary.get("category_count", 0) or 0) >= 12,
        "platform_profiles_ready": int(summary.get("platform_profiles", 0) or 0) >= 3,
        "safe_area_profiles_ready": int(summary.get("safe_area_profiles", 0) or 0) >= 3,
        "all_templates_safe_area_ready": bool(summary.get("all_templates_safe_area_ready")),
        "recommendations_ready": int(summary.get("recommendation_count", 0) or 0) >= 5,
        "mobile_exports_ready": int(summary.get("ready_mobile_export_profiles", 0) or 0) >= 3,
        "trend_catalog_ready": bool(trend_catalog.get("ok")) and int(summary.get("trend_template_packs", 0) or 0) >= 200,
        "creator_corpus_ready": bool(corpus.get("ok")) and float(summary.get("creator_corpus_average_score", 0) or 0) >= 85,
    }
    score = 52
    score += 10 if checks["template_volume_large_enough"] else 0
    score += 8 if checks["category_depth_ready"] else 0
    score += 8 if checks["platform_profiles_ready"] else 0
    score += 8 if checks["safe_area_profiles_ready"] else 0
    score += 8 if checks["all_templates_safe_area_ready"] else 0
    score += 4 if checks["recommendations_ready"] else 0
    score += 4 if checks["mobile_exports_ready"] else 0
    score += 4 if checks["trend_catalog_ready"] else 0
    score += 4 if checks["creator_corpus_ready"] else 0
    return {
        "kind": "capcut_mobile_template_parity",
        "ok": all(checks.values()),
        "score": min(96, score),
        "ready": all(checks.values()),
        "summary": summary,
        "checks": checks,
        "catalog": catalog,
        "trend_catalog": trend_catalog,
        "creator_corpus": corpus,
        "recommendations": recommendations,
        "export_readiness": export,
        "truth": "Cloud/mobile sync is excluded; this report covers local mobile export and template scale only.",
    }
