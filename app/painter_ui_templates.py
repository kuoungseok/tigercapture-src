"""Built-in complete-document templates for Painter UI Design."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document, validate_ui_document


UI_TEMPLATE_CATALOG_SCHEMA = "tigerstudio.painter.ui.template_catalog.v1"
UI_TEMPLATE_PACKAGE_SCHEMA = "tigerstudio.painter.ui.template_package.v1"


_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "id": "mobile_onboarding",
        "name": "Mobile Onboarding Flow",
        "category": "Mobile",
        "layout": "mobile",
        "description": "Three polished onboarding screens with reusable CTA and progress states.",
        "tags": ["onboarding", "mobile", "app", "flow"],
        "artboards": [("Welcome", 390, 844), ("Discover", 390, 844), ("Ready", 390, 844)],
        "palette": ["#111827", "#F7F8FC", "#5B6CFF", "#A7F3D0"],
        "headline": "Make every idea visible",
        "difficulty": "Starter",
    },
    {
        "id": "mobile_finance",
        "name": "Personal Finance Mobile",
        "category": "Mobile",
        "layout": "mobile_dashboard",
        "description": "Balance overview, spending cards, quick actions, and accessible navigation.",
        "tags": ["finance", "mobile", "dashboard", "charts"],
        "artboards": [("Overview", 390, 844), ("Activity", 390, 844)],
        "palette": ["#101418", "#F4F7F5", "#19A974", "#D8F3E7"],
        "headline": "Good morning, Mina",
        "difficulty": "Intermediate",
    },
    {
        "id": "saas_dashboard",
        "name": "Responsive SaaS Dashboard",
        "category": "Web & SaaS",
        "layout": "dashboard",
        "description": "Desktop and mobile product dashboard sharing one component and token system.",
        "tags": ["saas", "dashboard", "responsive", "analytics"],
        "artboards": [("Desktop", 1440, 900), ("Mobile", 390, 844)],
        "palette": ["#12151B", "#F7F8FA", "#4462FF", "#DDE4FF"],
        "headline": "Workspace overview",
        "difficulty": "Intermediate",
    },
    {
        "id": "analytics_command_center",
        "name": "Analytics Command Center",
        "category": "Dashboard",
        "layout": "dashboard",
        "description": "Dense operational analytics with KPI cards, chart regions, and alert states.",
        "tags": ["analytics", "operations", "kpi", "enterprise"],
        "artboards": [("Command Center", 1440, 900)],
        "palette": ["#0E1116", "#F5F7FA", "#00A6A6", "#D2F4F4"],
        "headline": "Live performance",
        "difficulty": "Advanced",
    },
    {
        "id": "commerce_product",
        "name": "Editorial Product Detail",
        "category": "E-commerce",
        "layout": "commerce",
        "description": "Product media, purchase controls, trust details, and responsive mobile layout.",
        "tags": ["commerce", "product", "store", "responsive"],
        "artboards": [("Product Desktop", 1440, 960), ("Product Mobile", 390, 844)],
        "palette": ["#181714", "#FAFAF7", "#E85D3F", "#F5DED6"],
        "headline": "Studio Headphones",
        "difficulty": "Intermediate",
    },
    {
        "id": "portfolio_case_study",
        "name": "Designer Case Study",
        "category": "Portfolio",
        "layout": "editorial",
        "description": "Editorial portfolio cover with project facts, outcome metrics, and visual rhythm.",
        "tags": ["portfolio", "case study", "editorial", "designer"],
        "artboards": [("Case Study", 1440, 1024)],
        "palette": ["#151515", "#F2EFE8", "#2B7A78", "#D7E9E7"],
        "headline": "A calmer way to work",
        "difficulty": "Starter",
    },
    {
        "id": "game_hud",
        "name": "Tactical Game HUD",
        "category": "Game UI",
        "layout": "game_hud",
        "description": "Safe-area HUD with status, objective, reticle, minimap, and action prompts.",
        "tags": ["game", "hud", "console", "tactical"],
        "artboards": [("Gameplay 16:9", 1920, 1080)],
        "palette": ["#07100E", "#DDF8ED", "#45E0A8", "#F2C94C"],
        "headline": "OBJECTIVE UPDATED",
        "difficulty": "Advanced",
    },
    {
        "id": "broadcast_overlay",
        "name": "Live Broadcast Overlay",
        "category": "Broadcast",
        "layout": "broadcast",
        "description": "Program-safe lower third, score strip, chat rail, and sponsor region.",
        "tags": ["broadcast", "stream", "lower third", "overlay"],
        "artboards": [("Program 16:9", 1920, 1080)],
        "palette": ["#111217", "#F8FAFC", "#FF5D5D", "#FFD6D6"],
        "headline": "LIVE SESSION",
        "difficulty": "Intermediate",
    },
    {
        "id": "pitch_deck_cover",
        "name": "Product Pitch Story",
        "category": "Presentation",
        "layout": "pitch",
        "description": "A concise presentation cover, proof metrics, and next-step composition.",
        "tags": ["pitch", "presentation", "product", "story"],
        "artboards": [("Cover", 1920, 1080), ("Proof", 1920, 1080), ("Next", 1920, 1080)],
        "palette": ["#16181D", "#F5F2EA", "#EBB94E", "#F8E9C6"],
        "headline": "Build what people remember",
        "difficulty": "Starter",
    },
    {
        "id": "wireframe_user_flow",
        "name": "Product Wireframe Flow",
        "category": "Wireframe",
        "layout": "wireframe",
        "description": "Low-fidelity desktop and mobile flow for fast product structure decisions.",
        "tags": ["wireframe", "ux", "flow", "prototype"],
        "artboards": [("Desktop Flow", 1280, 800), ("Mobile Flow", 390, 844)],
        "palette": ["#262626", "#F3F3F3", "#787878", "#DDDDDD"],
        "headline": "Plan the experience",
        "difficulty": "Starter",
    },
    {
        "id": "accessible_checkout",
        "name": "Accessible Checkout Form",
        "category": "Forms",
        "layout": "form",
        "description": "Keyboard-ready checkout form with labels, focus order, validation, and summary.",
        "tags": ["form", "checkout", "accessibility", "keyboard"],
        "artboards": [("Checkout", 1080, 900)],
        "palette": ["#17202A", "#FFFFFF", "#246BFD", "#DCE7FF"],
        "headline": "Complete your order",
        "difficulty": "Intermediate",
    },
    {
        "id": "design_system_starter",
        "name": "Design System Starter",
        "category": "Design System",
        "layout": "design_system",
        "description": "Foundations, tokens, buttons, fields, cards, states, and responsive examples.",
        "tags": ["design system", "tokens", "components", "library"],
        "artboards": [("Foundations", 1440, 1024), ("Components", 1440, 1024)],
        "palette": ["#121820", "#F8FAFC", "#5B67F1", "#E0E4FF"],
        "headline": "Tiger UI Foundations",
        "difficulty": "Advanced",
    },
)


def _manifest(spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": UI_TEMPLATE_PACKAGE_SCHEMA,
        "id": str(spec["id"]),
        "version": 1,
        "name": str(spec["name"]),
        "category": str(spec["category"]),
        "description": str(spec["description"]),
        "tags": list(spec["tags"]),
        "difficulty": str(spec["difficulty"]),
        "artboard_presets": [
            {"name": name, "width": width, "height": height}
            for name, width, height in spec["artboards"]
        ],
        "features": [
            "Complete editable document",
            "Shared design tokens",
            "Reusable CTA component",
            "Prototype-ready interaction",
            "Stable object IDs",
        ],
        "author": "Tiger Studio",
        "source": "Tiger Studio built-in original",
        "source_url": "",
        "license": {
            "id": "Tiger-Studio-Built-In-1.0",
            "name": "Tiger Studio Built-in Template License",
            "commercial_use": True,
            "attribution_required": False,
            "redistribution": "Only as part of a substantially edited design output",
        },
    }


def list_ui_templates(
    *,
    query: str = "",
    category: str = "",
) -> list[dict[str, Any]]:
    query_key = str(query or "").strip().casefold()
    category_key = str(category or "").strip().casefold()
    rows = []
    for spec in _TEMPLATES:
        manifest = _manifest(spec)
        if category_key and manifest["category"].casefold() != category_key:
            continue
        haystack = " ".join(
            [
                manifest["name"],
                manifest["category"],
                manifest["description"],
                *manifest["tags"],
            ]
        ).casefold()
        if query_key and query_key not in haystack:
            continue
        rows.append(manifest)
    return rows


def get_ui_template(template_id: str) -> dict[str, Any]:
    key = str(template_id or "")
    spec = next((row for row in _TEMPLATES if row["id"] == key), None)
    if spec is None:
        raise ValueError(f"Painter UI template not found: {key}")
    return copy.deepcopy(spec)


def inspect_ui_template_catalog() -> dict[str, Any]:
    templates = list_ui_templates()
    categories = sorted({row["category"] for row in templates})
    return {
        "schema": UI_TEMPLATE_CATALOG_SCHEMA,
        "template_count": len(templates),
        "category_count": len(categories),
        "categories": {
            category: [
                row["id"] for row in templates if row["category"] == category
            ]
            for category in categories
        },
        "templates": templates,
    }


def _token_rows(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    ink, surface, accent, accent_soft = spec["palette"]
    return [
        {
            "id": "ui-token-color-ink",
            "name": "Color / Ink",
            "kind": "color",
            "value": ink,
            "theme_values": {"dark": surface},
        },
        {
            "id": "ui-token-color-surface",
            "name": "Color / Surface",
            "kind": "color",
            "value": surface,
            "theme_values": {"dark": ink},
        },
        {
            "id": "ui-token-color-accent",
            "name": "Color / Accent",
            "kind": "color",
            "value": accent,
        },
        {
            "id": "ui-token-color-accent-soft",
            "name": "Color / Accent Soft",
            "kind": "color",
            "value": accent_soft,
        },
        {
            "id": "ui-token-space-unit",
            "name": "Spacing / Unit",
            "kind": "spacing",
            "value": 8,
        },
        {
            "id": "ui-token-radius-control",
            "name": "Radius / Control",
            "kind": "radius",
            "value": 8,
        },
        {
            "id": "ui-token-shadow-panel",
            "name": "Shadow / Panel",
            "kind": "shadow",
            "value": {"x": 0, "y": 8, "blur": 24, "color": "#00000022"},
        },
    ]


def _object(
    object_id: str,
    artboard_id: str,
    kind: str,
    name: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    fill: str = "ui-token-color-surface",
    text: str = "",
    text_color: str = "ui-token-color-ink",
    radius: float = 8,
    parent_id: str = "",
    role: str = "none",
    component_id: str = "",
    focus_order: int = 0,
) -> dict[str, Any]:
    bindings = {"style.fill": fill} if fill else {}
    if text:
        bindings["style.text_color"] = text_color
    return {
        "id": object_id,
        "kind": kind,
        "name": name,
        "artboard_id": artboard_id,
        "parent_id": parent_id,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "style": {
            "fill": "#FFFFFF",
            "text_color": "#111111",
            "radius": radius,
            "font_size": max(14, min(52, int(height * 0.35))),
        },
        "content": {"text": text} if text else {},
        "token_bindings": bindings,
        "component_role": role,
        "component_id": component_id,
        "component_source_object_id": object_id if role == "definition" else "",
        "accessibility": {
            "role": "button" if kind == "button" else "text" if text else "none",
            "label": text,
            "focus_order": focus_order,
        },
    }


def _artboard_objects(
    spec: Mapping[str, Any],
    artboard_id: str,
    width: int,
    height: int,
    index: int,
) -> list[dict[str, Any]]:
    layout = str(spec["layout"])
    prefix = f"ui-object-{index + 1}"
    margin = max(24, int(width * 0.045))
    objects: list[dict[str, Any]] = []

    if layout in {"game_hud", "broadcast"}:
        objects.extend(
            [
                _object(f"{prefix}-top", artboard_id, "frame", "Top Status", margin, margin, width - margin * 2, 72, fill="ui-token-color-ink", radius=4),
                _object(f"{prefix}-headline", artboard_id, "text", "Status Label", margin + 28, margin + 12, width * 0.36, 48, fill="", text=str(spec["headline"]), text_color="ui-token-color-surface"),
                _object(f"{prefix}-rail", artboard_id, "frame", "Information Rail", width - margin - 300, 150, 300, height - 300, fill="ui-token-color-ink", radius=4),
                _object(f"{prefix}-lower", artboard_id, "frame", "Lower Third", margin, height - margin - 116, width * 0.5, 116, fill="ui-token-color-accent", radius=4),
                _object(f"{prefix}-prompt", artboard_id, "button", "Action Prompt", width * 0.5 - 110, height - margin - 64, 220, 48, fill="ui-token-color-accent-soft", text="PRIMARY ACTION", role="definition" if index == 0 else "none", component_id="ui-component-primary-button" if index == 0 else "", focus_order=1),
            ]
        )
        return objects

    if layout == "pitch":
        objects.extend(
            [
                _object(f"{prefix}-eyebrow", artboard_id, "text", "Section", margin, margin, 320, 42, fill="", text=f"STORY {index + 1}"),
                _object(f"{prefix}-headline", artboard_id, "text", "Headline", margin, height * 0.2, width * 0.68, 170, fill="", text=str(spec["headline"])),
                _object(f"{prefix}-accent", artboard_id, "frame", "Accent Field", width * 0.72, 0, width * 0.28, height, fill="ui-token-color-accent"),
                _object(f"{prefix}-metric-a", artboard_id, "frame", "Metric A", margin, height * 0.68, width * 0.22, 150, fill="ui-token-color-accent-soft"),
                _object(f"{prefix}-metric-b", artboard_id, "frame", "Metric B", margin + width * 0.25, height * 0.68, width * 0.22, 150),
                _object(f"{prefix}-button", artboard_id, "button", "Primary CTA", margin, height - margin - 64, 240, 52, fill="ui-token-color-accent", text="Continue", role="definition" if index == 0 else "none", component_id="ui-component-primary-button" if index == 0 else "", focus_order=1),
            ]
        )
        return objects

    if layout == "design_system":
        objects.append(_object(f"{prefix}-headline", artboard_id, "text", "Page Title", margin, margin, width * 0.6, 90, fill="", text=str(spec["headline"])))
        swatch_width = (width - margin * 2 - 48) / 4
        for swatch_index, token_id in enumerate(
            ("ui-token-color-ink", "ui-token-color-surface", "ui-token-color-accent", "ui-token-color-accent-soft")
        ):
            objects.append(_object(f"{prefix}-swatch-{swatch_index}", artboard_id, "frame", f"Color Swatch {swatch_index + 1}", margin + swatch_index * (swatch_width + 16), 160, swatch_width, 150, fill=token_id))
        objects.extend(
            [
                _object(f"{prefix}-button", artboard_id, "button", "Primary Button", margin, 380, 240, 56, fill="ui-token-color-accent", text="Continue", role="definition", component_id="ui-component-primary-button", focus_order=1),
                _object(f"{prefix}-field", artboard_id, "frame", "Text Field", margin + 280, 380, 360, 56),
                _object(f"{prefix}-card", artboard_id, "frame", "Content Card", margin, 500, width - margin * 2, 300, fill="ui-token-color-accent-soft"),
            ]
        )
        return objects

    nav_height = 64 if width > 700 else 52
    objects.append(_object(f"{prefix}-nav", artboard_id, "frame", "Navigation", 0, 0, width, nav_height, fill="ui-token-color-surface", radius=0))
    objects.append(_object(f"{prefix}-brand", artboard_id, "text", "Brand", margin, 12, min(260, width * 0.5), 40, fill="", text=str(spec["name"])))

    if layout in {"dashboard", "mobile_dashboard"}:
        sidebar = 220 if width > 700 else 0
        if sidebar:
            objects.append(_object(f"{prefix}-sidebar", artboard_id, "frame", "Sidebar", 0, nav_height, sidebar, height - nav_height, fill="ui-token-color-ink", radius=0))
        content_x = sidebar + margin
        content_width = width - content_x - margin
        objects.append(_object(f"{prefix}-headline", artboard_id, "text", "Page Heading", content_x, nav_height + margin, content_width, 72, fill="", text=str(spec["headline"])))
        columns = 3 if width > 700 else 1
        card_gap = 16
        card_width = (content_width - card_gap * (columns - 1)) / columns
        for card_index in range(3):
            column = card_index % columns
            row = card_index // columns
            objects.append(_object(f"{prefix}-metric-{card_index}", artboard_id, "frame", f"Metric Card {card_index + 1}", content_x + column * (card_width + card_gap), nav_height + 130 + row * 150, card_width, 132, fill="ui-token-color-accent-soft"))
        objects.append(_object(f"{prefix}-chart", artboard_id, "frame", "Chart Region", content_x, nav_height + (310 if columns > 1 else 560), content_width, max(180, height * 0.32)))
        objects.append(_object(f"{prefix}-button", artboard_id, "button", "Primary CTA", content_x, height - margin - 56, min(220, content_width), 48, fill="ui-token-color-accent", text="View details", role="definition" if index == 0 else "none", component_id="ui-component-primary-button" if index == 0 else "", focus_order=1))
        return objects

    content_width = width - margin * 2
    objects.extend(
        [
            _object(f"{prefix}-headline", artboard_id, "text", "Hero Headline", margin, nav_height + margin * 1.5, content_width * (0.62 if width > 700 else 1), 110, fill="", text=str(spec["headline"])),
            _object(f"{prefix}-media", artboard_id, "image", "Hero Media", margin if width <= 700 else width * 0.56, nav_height + 160, content_width if width <= 700 else width * 0.38, height * 0.36, fill="ui-token-color-accent-soft"),
            _object(f"{prefix}-body", artboard_id, "text", "Supporting Copy", margin, nav_height + 160, content_width * (0.46 if width > 700 else 1), 90, fill="", text="A complete editable starting point with sensible structure and reusable foundations."),
            _object(f"{prefix}-button", artboard_id, "button", "Primary CTA", margin, nav_height + 280, min(260, content_width), 56, fill="ui-token-color-accent", text="Get started", role="definition" if index == 0 else "none", component_id="ui-component-primary-button" if index == 0 else "", focus_order=1),
            _object(f"{prefix}-card-a", artboard_id, "frame", "Feature Card A", margin, height * 0.68, (content_width - 16) / 2, 150),
            _object(f"{prefix}-card-b", artboard_id, "frame", "Feature Card B", margin + (content_width + 16) / 2, height * 0.68, (content_width - 16) / 2, 150, fill="ui-token-color-accent-soft"),
        ]
    )
    return objects


def instantiate_ui_template(template_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = get_ui_template(template_id)
    manifest = _manifest(spec)
    artboards = []
    objects: list[dict[str, Any]] = []
    right_edge = 0.0
    for index, (name, width, height) in enumerate(spec["artboards"]):
        artboard_id = f"artboard-{index + 1}"
        artboards.append(
            {
                "id": artboard_id,
                "name": name,
                "width": width,
                "height": height,
                "x": right_edge,
                "y": 0,
                "background": spec["palette"][1],
                "breakpoint": "mobile" if width < 700 else "desktop",
                "theme": "light",
                "layout_grid": {
                    "mode": "columns" if width >= 700 else "grid",
                    "visible": False,
                    "size": 8,
                    "count": 12 if width >= 700 else 4,
                    "gutter": 20 if width >= 700 else 12,
                    "margin": 48 if width >= 700 else 24,
                    "color": "#4C9AFF32",
                },
                "safe_area_visible": spec["layout"] in {"game_hud", "broadcast"},
                "safe_area": {"left": 64, "top": 48, "right": 64, "bottom": 48},
            }
        )
        objects.extend(_artboard_objects(spec, artboard_id, width, height, index))
        right_edge += width + 80
    definition = next(
        (
            row
            for row in objects
            if row.get("component_role") == "definition"
        ),
        None,
    )
    components = (
        [
            {
                "id": "ui-component-primary-button",
                "name": "Primary Button",
                "root_object_id": definition["id"],
                "description": "Reusable primary action from the template.",
                "metadata": {
                    "template_id": template_id,
                    "library_path": "Controls / Buttons / Primary",
                },
            }
        ]
        if definition is not None
        else []
    )
    interaction = next(
        (row for row in objects if row["kind"] == "button"),
        None,
    )
    interactions = (
        [
            {
                "id": "ui-interaction-primary",
                "name": "Primary action",
                "source_object_id": interaction["id"],
                "trigger": "click",
                "action": "navigate" if len(artboards) > 1 else "change_state",
                "target_artboard_id": artboards[1]["id"] if len(artboards) > 1 else "",
                "target_object_id": interaction["id"] if len(artboards) == 1 else "",
                "component_id": str(interaction.get("component_id") or ""),
                "parameters": {"state": "pressed"} if len(artboards) == 1 else {},
            }
        ]
        if interaction is not None
        else []
    )
    document = normalize_ui_document(
        {
            "document_id": f"ui-template-{template_id}-copy",
            "revision": 1,
            "active_artboard_id": artboards[0]["id"],
            "artboards": artboards,
            "objects": objects,
            "components": components,
            "tokens": _token_rows(spec),
            "interactions": interactions,
            "linked_targets": {
                "template_source": {
                    "template_id": template_id,
                    "template_version": manifest["version"],
                    "author": manifest["author"],
                    "source": manifest["source"],
                    "license": copy.deepcopy(manifest["license"]),
                }
            },
        }
    )
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise ValueError(
            f"Invalid built-in UI template {template_id}: "
            + ", ".join(validation["errors"])
        )
    return document, {
        "schema": "tigerstudio.painter.ui.template.instantiate.v1",
        "template": manifest,
        "document_id": document["document_id"],
        "artboard_count": len(document["artboards"]),
        "object_count": len(document["objects"]),
        "component_count": len(document["components"]),
        "token_count": len(document["tokens"]),
        "interaction_count": len(document["interactions"]),
    }


__all__ = [
    "UI_TEMPLATE_CATALOG_SCHEMA",
    "UI_TEMPLATE_PACKAGE_SCHEMA",
    "get_ui_template",
    "inspect_ui_template_catalog",
    "instantiate_ui_template",
    "list_ui_templates",
]
