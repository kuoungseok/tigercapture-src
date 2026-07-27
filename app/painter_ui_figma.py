"""Figma REST import and Figma Plugin export for Painter UI documents."""
from __future__ import annotations

import base64
import copy
import json
import mimetypes
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

from app.painter_ui_document import normalize_ui_document, validate_ui_document


FIGMA_EXCHANGE_SCHEMA = "tigerstudio.painter.ui.figma_exchange.v1"
FIGMA_IMPORT_SCHEMA = "tigerstudio.painter.ui.figma_import.v1"
FIGMA_API_ROOT = "https://api.figma.com/v1"
_FIGMA_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?figma\.com/(?:design|file|proto|board)/([^/?#]+)",
    re.IGNORECASE,
)


class PainterUIFigmaError(ValueError):
    pass


def default_figma_asset_root(file_key: str) -> Path:
    return Path.home() / "TigerStudio" / "PainterFigmaAssets" / _stable_id(
        "file", file_key
    )


def figma_file_key(value: str) -> str:
    text = str(value or "").strip()
    match = _FIGMA_URL_PATTERN.search(text)
    candidate = match.group(1) if match else text
    candidate = candidate.split("?")[0].split("#")[0].strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,256}", candidate):
        raise PainterUIFigmaError("Enter a Figma file URL or file key")
    return candidate


def _stable_id(prefix: str, value: object) -> str:
    source = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "")).strip("-")
    return f"figma-{prefix}-{source or 'node'}"


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _color(value: object, default: str = "#00000000") -> str:
    if not isinstance(value, Mapping):
        return default
    channels = [
        max(0, min(255, round(_number(value.get(key)) * 255)))
        for key in ("r", "g", "b", "a")
    ]
    if "a" not in value:
        channels[3] = 255
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def _solid_paint(paints: object) -> Mapping[str, Any] | None:
    if not isinstance(paints, list):
        return None
    return next(
        (
            row
            for row in paints
            if isinstance(row, Mapping)
            and row.get("visible", True)
            and str(row.get("type") or "").upper() == "SOLID"
        ),
        None,
    )


def _image_paint(paints: object) -> Mapping[str, Any] | None:
    if not isinstance(paints, list):
        return None
    return next(
        (
            row
            for row in paints
            if isinstance(row, Mapping)
            and row.get("visible", True)
            and str(row.get("type") or "").upper() == "IMAGE"
        ),
        None,
    )


def _box(node: Mapping[str, Any]) -> dict[str, float]:
    value = node.get("absoluteBoundingBox")
    value = value if isinstance(value, Mapping) else {}
    return {
        "x": _number(value.get("x")),
        "y": _number(value.get("y")),
        "width": max(1.0, _number(value.get("width"), 160.0)),
        "height": max(1.0, _number(value.get("height"), 64.0)),
    }


def _map_kind(node: Mapping[str, Any]) -> str:
    node_type = str(node.get("type") or "").upper()
    if node_type in {"FRAME", "SECTION", "COMPONENT", "COMPONENT_SET"}:
        return "frame"
    if node_type in {"GROUP", "INSTANCE"}:
        return "group"
    if node_type == "ELLIPSE":
        return "ellipse"
    if node_type == "LINE":
        return "line"
    if node_type == "TEXT":
        return "text"
    if node_type in {
        "VECTOR",
        "BOOLEAN_OPERATION",
        "STAR",
        "POLYGON",
    }:
        return "path"
    if _image_paint(node.get("fills")) is not None:
        return "image"
    return "rectangle"


def _map_layout(node: Mapping[str, Any]) -> dict[str, Any]:
    mode = str(node.get("layoutMode") or "NONE").casefold()
    main = {
        "min": "start",
        "center": "center",
        "max": "end",
        "space_between": "space_between",
    }.get(str(node.get("primaryAxisAlignItems") or "MIN").casefold(), "start")
    cross = {
        "min": "start",
        "center": "center",
        "max": "end",
        "baseline": "start",
    }.get(str(node.get("counterAxisAlignItems") or "MIN").casefold(), "start")
    return {
        "mode": mode if mode in {"horizontal", "vertical"} else "none",
        "padding": {
            "left": _number(node.get("paddingLeft")),
            "top": _number(node.get("paddingTop")),
            "right": _number(node.get("paddingRight")),
            "bottom": _number(node.get("paddingBottom")),
        },
        "gap": max(0.0, _number(node.get("itemSpacing"))),
        "main_alignment": main,
        "cross_alignment": cross,
        "wrap": str(node.get("layoutWrap") or "").upper() == "WRAP",
        "width_sizing": {
            "HUG": "hug",
            "FILL": "fill",
        }.get(str(node.get("layoutSizingHorizontal") or "").upper(), "fixed"),
        "height_sizing": {
            "HUG": "hug",
            "FILL": "fill",
        }.get(str(node.get("layoutSizingVertical") or "").upper(), "fixed"),
        "positioning": (
            "absolute"
            if str(node.get("layoutPositioning") or "").upper() == "ABSOLUTE"
            else "auto"
        ),
    }


def _map_constraints(node: Mapping[str, Any]) -> dict[str, Any]:
    source = node.get("constraints")
    source = source if isinstance(source, Mapping) else {}
    horizontal = {
        "MIN": "left",
        "MAX": "right",
        "CENTER": "center",
        "STRETCH": "stretch",
        "SCALE": "scale",
    }.get(str(source.get("horizontal") or "MIN").upper(), "left")
    vertical = {
        "MIN": "top",
        "MAX": "bottom",
        "CENTER": "center",
        "STRETCH": "stretch",
        "SCALE": "scale",
    }.get(str(source.get("vertical") or "MIN").upper(), "top")
    return {"horizontal": horizontal, "vertical": vertical}


def _map_token_bindings(node: Mapping[str, Any]) -> dict[str, str]:
    source = node.get("boundVariables")
    source = source if isinstance(source, Mapping) else {}
    field_paths = {
        "fills": "style.fill",
        "strokes": "style.stroke",
        "opacity": "opacity",
        "cornerRadius": "style.radius",
    }
    result: dict[str, str] = {}
    for field, path in field_paths.items():
        raw = source.get(field)
        aliases = raw if isinstance(raw, list) else [raw]
        alias = next(
            (
                row
                for row in aliases
                if isinstance(row, Mapping) and str(row.get("id") or "")
            ),
            None,
        )
        if alias is not None:
            result[path] = _stable_id("token", alias["id"])
    return result


def _map_style(node: Mapping[str, Any]) -> dict[str, Any]:
    fill = _solid_paint(node.get("fills"))
    stroke = _solid_paint(node.get("strokes"))
    effects = node.get("effects") if isinstance(node.get("effects"), list) else []
    shadow = next(
        (
            effect
            for effect in effects
            if isinstance(effect, Mapping)
            and effect.get("visible", True)
            and str(effect.get("type") or "").upper() == "DROP_SHADOW"
        ),
        None,
    )
    result: dict[str, Any] = {
        "fill": _color(fill.get("color"), "#00000000") if fill else "#00000000",
        "stroke": _color(stroke.get("color"), "#00000000") if stroke else "#00000000",
        "stroke_width": max(0.0, _number(node.get("strokeWeight"))),
        "radius": max(
            0.0,
            _number(
                node.get("cornerRadius"),
                (node.get("rectangleCornerRadii") or [0])[0]
                if isinstance(node.get("rectangleCornerRadii"), list)
                and node.get("rectangleCornerRadii")
                else 0.0,
            ),
        ),
    }
    if isinstance(shadow, Mapping):
        offset = shadow.get("offset")
        offset = offset if isinstance(offset, Mapping) else {}
        result["shadow"] = {
            "color": _color(shadow.get("color"), "#00000040"),
            "x": _number(offset.get("x")),
            "y": _number(offset.get("y"), 4.0),
            "blur": max(0.0, _number(shadow.get("radius"), 8.0)),
            "spread": max(0.0, _number(shadow.get("spread"))),
        }
    return result


def _map_content(
    node: Mapping[str, Any],
    image_urls: Mapping[str, str],
    image_paths: Mapping[str, str],
) -> dict[str, Any]:
    node_type = str(node.get("type") or "").upper()
    result: dict[str, Any] = {
        "figma_node_id": str(node.get("id") or ""),
        "figma_type": node_type,
    }
    if node_type == "TEXT":
        style = node.get("style")
        style = style if isinstance(style, Mapping) else {}
        result.update(
            {
                "text": str(node.get("characters") or ""),
                "font_family": str(style.get("fontFamily") or "Inter"),
                "font_size": max(1.0, _number(style.get("fontSize"), 16.0)),
                "font_weight": int(_number(style.get("fontWeight"), 400)),
                "text_align": str(style.get("textAlignHorizontal") or "LEFT").casefold(),
                "line_height": max(0.0, _number(style.get("lineHeightPx"))),
            }
        )
    image = _image_paint(node.get("fills"))
    if image is not None:
        image_ref = str(image.get("imageRef") or "")
        result.update(
            {
                "image_ref": image_ref,
                "image_url": str(image_urls.get(image_ref) or ""),
                "image_path": str(image_paths.get(image_ref) or ""),
                "image_mode": str(image.get("scaleMode") or "FILL").casefold(),
            }
        )
    paths = node.get("fillGeometry")
    if isinstance(paths, list):
        result["vector_paths"] = [
            str(row.get("path") or "")
            for row in paths
            if isinstance(row, Mapping) and str(row.get("path") or "")
        ]
    return result


def _top_level_frames(page: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    children = [
        row for row in page.get("children", []) if isinstance(row, Mapping)
    ]
    frames = [
        row
        for row in children
        if str(row.get("type") or "").upper()
        in {"FRAME", "COMPONENT", "COMPONENT_SET", "SECTION"}
    ]
    return frames or [page]


def import_figma_payload(
    payload: Mapping[str, Any],
    *,
    source: str = "",
    image_urls: Mapping[str, str] | None = None,
    image_paths: Mapping[str, str] | None = None,
    variables_payload: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = payload.get("document")
    if not isinstance(root, Mapping):
        raise PainterUIFigmaError("Figma JSON does not contain a document node")
    pages = [
        row
        for row in root.get("children", [])
        if isinstance(row, Mapping)
        and str(row.get("type") or "").upper() == "CANVAS"
    ]
    if not pages:
        raise PainterUIFigmaError("Figma document does not contain any pages")
    images = dict(image_urls or {})
    local_images = dict(image_paths or {})
    file_key = ""
    try:
        file_key = figma_file_key(source)
    except PainterUIFigmaError:
        file_key = str(payload.get("key") or "snapshot")

    artboards: list[dict[str, Any]] = []
    objects: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    interactions: list[dict[str, Any]] = []
    pending_reactions: list[tuple[str, list[Mapping[str, Any]]]] = []
    figma_targets: dict[str, tuple[str, str]] = {}
    warnings: list[str] = []
    supported = 0
    skipped = 0
    artboard_x = 0.0

    for page in pages:
        for frame in _top_level_frames(page):
            frame_box = _box(frame)
            frame_id = _stable_id("artboard", frame.get("id"))
            background = _solid_paint(frame.get("backgrounds") or frame.get("fills"))
            artboards.append(
                {
                    "id": frame_id,
                    "name": str(frame.get("name") or page.get("name") or "Figma"),
                    "width": int(round(frame_box["width"])),
                    "height": int(round(frame_box["height"])),
                    "x": artboard_x,
                    "y": 0.0,
                    "background": (
                        _color(background.get("color"), "#FFFFFF")
                        if background
                        else "#FFFFFF"
                    ),
                    "breakpoint": "figma",
                    "orientation": (
                        "landscape"
                        if frame_box["width"] >= frame_box["height"]
                        else "portrait"
                    ),
                }
            )
            figma_targets[str(frame.get("id") or "")] = ("artboard", frame_id)
            artboard_x += frame_box["width"] + 160.0

            def visit(
                node: Mapping[str, Any],
                parent_id: str = "",
                *,
                include_self: bool = True,
            ) -> None:
                nonlocal supported, skipped
                node_type = str(node.get("type") or "").upper()
                unsupported = {"SLICE", "CONNECTOR", "WIDGET", "EMBED", "LINK_UNFURL"}
                if node_type in unsupported:
                    skipped += 1
                    warnings.append(f"blocked:{node.get('id')}:{node_type}")
                    return
                current_parent = parent_id
                if include_self:
                    node_box = _box(node)
                    object_id = _stable_id("node", node.get("id"))
                    kind = _map_kind(node)
                    role = "none"
                    component_id = ""
                    source_object_id = ""
                    if node_type == "COMPONENT":
                        component_id = _stable_id("component", node.get("id"))
                        role = "definition"
                        source_object_id = object_id
                        components.append(
                            {
                                "id": component_id,
                                "name": str(node.get("name") or "Component"),
                                "root_object_id": object_id,
                                "metadata": {
                                    "figma_node_id": str(node.get("id") or ""),
                                    "figma_key": str(node.get("key") or ""),
                                },
                            }
                        )
                    elif node_type == "INSTANCE":
                        component_id = _stable_id(
                            "component",
                            node.get("componentId") or node.get("mainComponent", ""),
                        )
                        role = "instance"
                    objects.append(
                        {
                            "id": object_id,
                            "kind": kind,
                            "name": str(node.get("name") or kind.title()),
                            "artboard_id": frame_id,
                            "parent_id": parent_id,
                            "x": node_box["x"] - frame_box["x"],
                            "y": node_box["y"] - frame_box["y"],
                            "width": node_box["width"],
                            "height": node_box["height"],
                            "rotation": _number(node.get("rotation")),
                            "opacity": max(
                                0.0, min(1.0, _number(node.get("opacity"), 1.0))
                            ),
                            "visible": bool(node.get("visible", True)),
                            "locked": bool(node.get("locked", False)),
                            "z_index": len(objects),
                            "style": _map_style(node),
                            "content": _map_content(node, images, local_images),
                            "constraints": _map_constraints(node),
                            "layout": _map_layout(node),
                            "component_id": component_id,
                            "component_role": role,
                            "component_source_object_id": source_object_id,
                            "token_bindings": _map_token_bindings(node),
                        }
                    )
                    figma_targets[str(node.get("id") or "")] = (
                        "object",
                        object_id,
                    )
                    reactions = [
                        row
                        for row in node.get("reactions", [])
                        if isinstance(row, Mapping)
                    ]
                    if reactions:
                        pending_reactions.append((object_id, reactions))
                    supported += 1
                    current_parent = object_id
                for child in node.get("children", []):
                    if isinstance(child, Mapping):
                        visit(child, current_parent)

            if str(frame.get("type") or "").upper() == "COMPONENT":
                visit(frame)
            else:
                for child in frame.get("children", []):
                    if isinstance(child, Mapping):
                        visit(child)

    component_roots = {
        str(row["id"]): str(row["root_object_id"]) for row in components
    }
    for row in objects:
        if row.get("component_role") != "instance":
            continue
        component_id = str(row.get("component_id") or "")
        source_object_id = component_roots.get(component_id, "")
        if source_object_id:
            row["component_source_object_id"] = source_object_id
            continue
        row["content"]["figma_component_id"] = component_id
        row["component_id"] = ""
        row["component_role"] = "none"
        warnings.append(
            f"converted:{row['id']}:remote_component_instance_to_group"
        )

    trigger_map = {
        "ON_CLICK": "click",
        "MOUSE_ENTER": "hover",
        "MOUSE_DOWN": "press",
        "ON_KEY_DOWN": "keyboard",
    }
    for source_object_id, reactions in pending_reactions:
        for reaction in reactions:
            trigger_row = reaction.get("trigger")
            trigger_row = trigger_row if isinstance(trigger_row, Mapping) else {}
            trigger = trigger_map.get(
                str(trigger_row.get("type") or "ON_CLICK").upper(),
                "click",
            )
            actions = reaction.get("actions")
            if not isinstance(actions, list):
                legacy = reaction.get("action")
                actions = [legacy] if isinstance(legacy, Mapping) else []
            for action_index, raw_action in enumerate(actions):
                if not isinstance(raw_action, Mapping):
                    continue
                action_type = str(raw_action.get("type") or "").upper()
                navigation = str(raw_action.get("navigation") or "").upper()
                destination = str(raw_action.get("destinationId") or "")
                target_kind, target_id = figma_targets.get(destination, ("", ""))
                mapped_action = "navigate"
                if action_type == "BACK":
                    mapped_action = "back"
                elif action_type in {"CLOSE", "CLOSE_OVERLAY"}:
                    mapped_action = "close_overlay"
                elif navigation in {"OVERLAY", "SWAP"}:
                    mapped_action = "open_overlay"
                elif action_type != "NODE":
                    warnings.append(
                        f"blocked_reaction:{source_object_id}:{action_type}"
                    )
                    continue
                interactions.append(
                    {
                        "id": _stable_id(
                            "interaction",
                            f"{source_object_id}-{len(interactions)}-{action_index}",
                        ),
                        "name": f"Figma {trigger} {mapped_action}",
                        "source_object_id": source_object_id,
                        "trigger": trigger,
                        "action": mapped_action,
                        "target_artboard_id": (
                            target_id if target_kind == "artboard" else ""
                        ),
                        "target_object_id": (
                            target_id if target_kind == "object" else ""
                        ),
                        "parameters": {
                            "figma_transition": copy.deepcopy(
                                raw_action.get("transition")
                            ),
                            "preserve_scroll_position": bool(
                                raw_action.get("preserveScrollPosition", False)
                            ),
                        },
                    }
                )

    tokens: list[dict[str, Any]] = []
    variable_root = (
        variables_payload.get("meta")
        if isinstance(variables_payload, Mapping)
        else {}
    )
    variable_root = variable_root if isinstance(variable_root, Mapping) else {}
    variables = variable_root.get("variables")
    variables = variables if isinstance(variables, Mapping) else {}
    for variable_id, row in variables.items():
        if not isinstance(row, Mapping):
            continue
        resolved_type = str(row.get("resolvedType") or "").upper()
        kind = {
            "COLOR": "color",
            "FLOAT": "spacing",
            "STRING": "typography",
        }.get(resolved_type)
        if not kind:
            continue
        values = row.get("valuesByMode")
        values = values if isinstance(values, Mapping) else {}
        first = next(iter(values.values()), None)
        value = _color(first, "#000000") if resolved_type == "COLOR" else first
        tokens.append(
            {
                "id": _stable_id("token", variable_id),
                "name": str(row.get("name") or variable_id),
                "kind": kind,
                "value": value,
                "description": str(row.get("description") or ""),
            }
        )

    token_ids = {str(row["id"]) for row in tokens}
    for row in objects:
        bindings = dict(row.get("token_bindings") or {})
        row["token_bindings"] = {
            path: token_id
            for path, token_id in bindings.items()
            if str(token_id) in token_ids
        }
        for path, token_id in bindings.items():
            if str(token_id) not in token_ids:
                warnings.append(
                    f"converted:{row['id']}:{path}:missing_figma_variable"
                )

    document = normalize_ui_document(
        {
            "document_id": _stable_id("document", file_key),
            "active_artboard_id": artboards[0]["id"],
            "artboards": artboards,
            "objects": objects,
            "components": components,
            "tokens": tokens,
            "interactions": interactions,
            "linked_targets": {
                "figma": {
                    "file_key": file_key,
                    "source": source,
                    "name": str(payload.get("name") or ""),
                    "version": str(payload.get("version") or ""),
                    "last_modified": str(payload.get("lastModified") or ""),
                    "mode": "imported",
                }
            },
        }
    )
    validation = validate_ui_document(document)
    report = {
        "schema": FIGMA_IMPORT_SCHEMA,
        "ok": not validation["errors"],
        "file_key": file_key,
        "name": str(payload.get("name") or ""),
        "artboard_count": len(document["artboards"]),
        "object_count": len(document["objects"]),
        "component_count": len(document["components"]),
        "token_count": len(document["tokens"]),
        "interaction_count": len(document["interactions"]),
        "supported_node_count": supported,
        "blocked_node_count": skipped,
        "warnings": warnings + list(validation["warnings"]),
        "errors": list(validation["errors"]),
    }
    if report["errors"]:
        raise PainterUIFigmaError(
            "Figma conversion produced an invalid document: "
            + ", ".join(report["errors"][:5])
        )
    return document, report


def _request_json(
    url: str,
    *,
    token: str,
    timeout: float,
    opener: Callable[..., Any] | None = None,
    optional: bool = False,
) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "TigerStudio-PainterUI/1.0",
    }
    if str(token).startswith("Bearer "):
        headers["Authorization"] = str(token)
    else:
        headers["X-Figma-Token"] = str(token)
    request = urllib.request.Request(url, headers=headers)
    open_request = opener or urllib.request.urlopen
    try:
        response = open_request(request, timeout=timeout)
        with response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if optional and exc.code in {403, 404}:
            return {}
        message = exc.read().decode("utf-8", errors="replace")
        raise PainterUIFigmaError(
            f"Figma API returned HTTP {exc.code}: {message[:240]}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PainterUIFigmaError(f"Could not connect to Figma: {exc}") from exc
    if not isinstance(payload, dict):
        raise PainterUIFigmaError("Figma API returned an invalid response")
    return payload


def _download_figma_images(
    image_urls: Mapping[str, str],
    *,
    root: Path,
    timeout: float,
    opener: Callable[..., Any] | None = None,
) -> tuple[dict[str, str], list[str]]:
    root.mkdir(parents=True, exist_ok=True)
    open_request = opener or urllib.request.urlopen
    paths: dict[str, str] = {}
    warnings: list[str] = []
    for image_ref, url in image_urls.items():
        ref = str(image_ref or "")
        address = str(url or "")
        if not ref or not address:
            continue
        request = urllib.request.Request(
            address,
            headers={"User-Agent": "TigerStudio-PainterUI/1.0"},
        )
        try:
            response = open_request(request, timeout=timeout)
            with response:
                data = response.read()
                content_type = str(response.headers.get("Content-Type") or "")
        except Exception as exc:
            warnings.append(f"image_download_failed:{ref}:{exc}")
            continue
        extension = mimetypes.guess_extension(content_type.split(";")[0]) or ".png"
        target = root / f"{_stable_id('image', ref)}{extension}"
        target.write_bytes(data)
        paths[ref] = str(target)
    return paths, warnings


def import_figma_file(
    source: str,
    *,
    token: str = "",
    timeout: float = 30.0,
    opener: Callable[..., Any] | None = None,
    asset_root: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    access_token = str(token or os.environ.get("FIGMA_ACCESS_TOKEN") or "").strip()
    if not access_token:
        raise PainterUIFigmaError(
            "A Figma token with file_content:read scope is required"
        )
    key = figma_file_key(source)
    encoded = urllib.parse.quote(key, safe="")
    payload = _request_json(
        f"{FIGMA_API_ROOT}/files/{encoded}?geometry=paths&plugin_data=shared",
        token=access_token,
        timeout=timeout,
        opener=opener,
    )
    image_payload = _request_json(
        f"{FIGMA_API_ROOT}/files/{encoded}/images",
        token=access_token,
        timeout=timeout,
        opener=opener,
        optional=True,
    )
    variable_payload = _request_json(
        f"{FIGMA_API_ROOT}/files/{encoded}/variables/local",
        token=access_token,
        timeout=timeout,
        opener=opener,
        optional=True,
    )
    image_urls = image_payload.get("meta", {}).get("images")
    if not isinstance(image_urls, Mapping):
        image_urls = image_payload.get("images")
    image_urls = image_urls if isinstance(image_urls, Mapping) else {}
    local_images, image_warnings = _download_figma_images(
        image_urls,
        root=Path(asset_root).expanduser().resolve()
        if asset_root
        else default_figma_asset_root(key),
        timeout=timeout,
        opener=opener,
    )
    document, report = import_figma_payload(
        payload,
        source=source,
        image_urls=image_urls,
        image_paths=local_images,
        variables_payload=variable_payload,
    )
    report["asset_root"] = str(
        Path(asset_root).expanduser().resolve()
        if asset_root
        else default_figma_asset_root(key)
    )
    report["downloaded_image_count"] = len(local_images)
    report["warnings"].extend(image_warnings)
    return document, report


def import_figma_json(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source = Path(path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise PainterUIFigmaError("Figma JSON snapshot must contain an object")
    return import_figma_payload(payload, source=str(source))


def merge_figma_document(
    current: Mapping[str, Any],
    imported: Mapping[str, Any],
    *,
    mode: str = "replace",
) -> dict[str, Any]:
    normalized = normalize_ui_document(imported)
    if str(mode).strip().casefold() == "replace":
        return normalized
    if str(mode).strip().casefold() != "append":
        raise PainterUIFigmaError("Import mode must be replace or append")
    result = normalize_ui_document(current)
    used = {
        str(row.get("id") or "")
        for key in ("artboards", "objects", "components", "tokens", "interactions")
        for row in result[key]
    }
    mapping: dict[str, str] = {}
    for key in ("artboards", "objects", "components", "tokens", "interactions"):
        for row in normalized[key]:
            source_id = str(row["id"])
            candidate = source_id
            serial = 2
            while candidate in used:
                candidate = f"{source_id}-{serial}"
                serial += 1
            mapping[source_id] = candidate
            used.add(candidate)

    def remap_row(key: str, row: Mapping[str, Any]) -> dict[str, Any]:
        value = copy.deepcopy(dict(row))
        value["id"] = mapping[str(row["id"])]
        reference_fields = {
            "objects": (
                "artboard_id",
                "parent_id",
                "component_id",
                "component_source_object_id",
            ),
            "components": ("root_object_id", "base_component_id"),
            "tokens": ("alias_token_id",),
            "interactions": (
                "source_object_id",
                "target_artboard_id",
                "target_object_id",
                "component_id",
            ),
        }.get(key, ())
        for field in reference_fields:
            reference = str(value.get(field) or "")
            if reference in mapping:
                value[field] = mapping[reference]
        if key == "objects":
            value["token_bindings"] = {
                path: mapping.get(str(token_id), str(token_id))
                for path, token_id in value.get("token_bindings", {}).items()
            }
        return value

    for key in ("artboards", "objects", "components", "tokens", "interactions"):
        result[key].extend(remap_row(key, row) for row in normalized[key])
    result["active_artboard_id"] = mapping[normalized["active_artboard_id"]]
    result["linked_targets"]["figma"] = copy.deepcopy(
        normalized.get("linked_targets", {}).get("figma", {})
    )
    result["revision"] = int(result.get("revision", 0)) + 1
    return normalize_ui_document(result)


def inspect_figma_compatibility(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = normalize_ui_document(document)
    rows: list[dict[str, str]] = []
    for row in normalized["objects"]:
        kind = str(row["kind"])
        status = "native"
        reason = "Maps to an editable Figma node"
        if kind == "motion_actor":
            status = "baked"
            reason = "Motion actors require a poster-frame image in Figma"
        elif kind not in {
            "frame",
            "group",
            "rectangle",
            "ellipse",
            "line",
            "path",
            "text",
            "image",
            "button",
            "progress",
        }:
            status = "blocked"
            reason = f"Unsupported Painter UI kind: {kind}"
        rows.append({"id": row["id"], "status": status, "reason": reason})
    counts = {
        status: sum(1 for row in rows if row["status"] == status)
        for status in ("native", "converted", "baked", "blocked")
    }
    return {
        "schema": FIGMA_EXCHANGE_SCHEMA,
        "ok": counts["blocked"] == 0,
        "counts": counts,
        "objects": rows,
        "artboard_count": len(normalized["artboards"]),
        "component_count": len(normalized["components"]),
        "token_count": len(normalized["tokens"]),
        "interaction_count": len(normalized["interactions"]),
    }


def _asset_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    assets: dict[str, Any] = {}
    for row in document["objects"]:
        content = row.get("content")
        content = content if isinstance(content, Mapping) else {}
        source = str(
            content.get("path")
            or content.get("source_path")
            or content.get("image_path")
            or ""
        )
        if not source:
            continue
        path = Path(source).expanduser()
        if not path.is_file():
            continue
        mime, _ = mimetypes.guess_type(path.name)
        assets[row["id"]] = {
            "name": path.name,
            "mime": mime or "application/octet-stream",
            "base64": base64.b64encode(path.read_bytes()).decode("ascii"),
        }
    return assets


def _plugin_code(exchange: Mapping[str, Any]) -> str:
    payload = json.dumps(exchange, ensure_ascii=False, separators=(",", ":"))
    return f"""const exchange = {payload};
const doc = exchange.document;
const created = new Map();
const components = new Map();
const tokenVars = new Map();
const objectById = new Map(doc.objects.map(row => [row.id, row]));
function insideInstance(row) {{
  let parent=objectById.get(row.parent_id);
  while(parent) {{
    if(parent.component_role==='instance') return true;
    parent=objectById.get(parent.parent_id);
  }}
  return false;
}}

function color(value) {{
  const text = String(value || '#00000000').replace('#', '');
  const full = text.length === 3 ? text.split('').map(x => x + x).join('') + 'FF'
    : text.length === 6 ? text + 'FF' : text.padEnd(8, 'F').slice(0, 8);
  return {{ r: parseInt(full.slice(0,2),16)/255, g: parseInt(full.slice(2,4),16)/255,
    b: parseInt(full.slice(4,6),16)/255, a: parseInt(full.slice(6,8),16)/255 }};
}}
function paint(value) {{ const c=color(value); return {{type:'SOLID',color:{{r:c.r,g:c.g,b:c.b}},opacity:c.a}}; }}
function decode64(text) {{
  const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let buffer=0,bits=0,out=[];
  for (const ch of text.replace(/=+$/,'')) {{
    const value=alphabet.indexOf(ch); if(value<0) continue;
    buffer=(buffer<<6)|value; bits+=6;
    if(bits>=8) {{ bits-=8; out.push((buffer>>bits)&255); }}
  }}
  return new Uint8Array(out);
}}
function applyFrame(node,row) {{
  node.name=row.name || row.id; node.x=Number(row.x)||0; node.y=Number(row.y)||0;
  node.resize(Math.max(1,Number(row.width)||1),Math.max(1,Number(row.height)||1));
  node.rotation=Number(row.rotation)||0; node.opacity=Math.max(0,Math.min(1,Number(row.opacity ?? 1)));
  node.visible=row.visible !== false; node.locked=!!row.locked;
  node.setSharedPluginData('tigerstudio','stable_id',row.id);
  const s=row.style||{{}};
  if('fills' in node) node.fills=[paint(s.fill||'#00000000')];
  if('strokes' in node && s.stroke && !String(s.stroke).endsWith('00')) node.strokes=[paint(s.stroke)];
  if('strokeWeight' in node) node.strokeWeight=Math.max(0,Number(s.stroke_width)||0);
  if('cornerRadius' in node && typeof node.cornerRadius==='number') node.cornerRadius=Math.max(0,Number(s.radius)||0);
  if(row.layout && 'layoutMode' in node) {{
    node.layoutMode=String(row.layout.mode||'NONE').toUpperCase();
    if(node.layoutMode!=='NONE') {{
      const p=row.layout.padding||{{}}; node.paddingLeft=Number(p.left)||0; node.paddingTop=Number(p.top)||0;
      node.paddingRight=Number(p.right)||0; node.paddingBottom=Number(p.bottom)||0;
      node.itemSpacing=Number(row.layout.gap)||0;
      node.primaryAxisAlignItems={{start:'MIN',center:'CENTER',end:'MAX',space_between:'SPACE_BETWEEN'}}[row.layout.main_alignment]||'MIN';
      node.counterAxisAlignItems={{start:'MIN',center:'CENTER',end:'MAX',stretch:'MIN'}}[row.layout.cross_alignment]||'MIN';
    }}
  }}
}}
async function main() {{
  const page=figma.currentPage;
  let variableCollection=null;
  if(doc.tokens.length && figma.variables) {{
    variableCollection=figma.variables.createVariableCollection('Tiger Studio Tokens');
    variableCollection.renameMode(variableCollection.modes[0].modeId,'Default');
    for(const row of doc.tokens) {{
      const type=row.kind==='color'?'COLOR':row.kind==='opacity'||row.kind==='spacing'||row.kind==='radius'?'FLOAT':'STRING';
      try {{
        const v=figma.variables.createVariable(row.name,variableCollection,type);
        v.setValueForMode(variableCollection.defaultModeId,type==='COLOR'?color(row.value):row.value);
        tokenVars.set(row.id,v);
      }} catch (_) {{}}
    }}
  }}
  for(const board of doc.artboards) {{
    const node=figma.createFrame(); node.name=board.name; node.x=board.x; node.y=board.y;
    node.resize(board.width,board.height); node.fills=[paint(board.background||'#FFFFFF')];
    node.clipsContent=false; node.setSharedPluginData('tigerstudio','stable_id',board.id);
    page.appendChild(node); created.set(board.id,node);
  }}
  const ordered=[...doc.objects].sort((a,b)=>(a.z_index||0)-(b.z_index||0));
  for(const row of ordered.filter(x => x.component_role !== 'instance' && !insideInstance(x))) {{
    let node;
    if(row.component_role==='definition') node=figma.createComponent();
    else if(row.kind==='ellipse') node=figma.createEllipse();
    else if(row.kind==='line') node=figma.createLine();
    else if(row.kind==='text') node=figma.createText();
    else if(['frame','group','button','progress'].includes(row.kind)) node=figma.createFrame();
    else node=figma.createRectangle();
    const parent=created.get(row.parent_id)||created.get(row.artboard_id)||page;
    parent.appendChild(node); applyFrame(node,row); created.set(row.id,node);
    if(row.component_role==='definition') components.set(row.component_id,node);
    if(row.kind==='text') {{
      const c=row.content||{{}}; const font={{family:c.font_family||'Inter',style:'Regular'}};
      try {{ await figma.loadFontAsync(font); node.fontName=font; }} catch (_) {{ await figma.loadFontAsync({{family:'Inter',style:'Regular'}}); }}
      node.characters=String(c.text||''); node.fontSize=Math.max(1,Number(c.font_size)||16);
      node.textAlignHorizontal=String(c.text_align||'LEFT').toUpperCase();
    }}
    const asset=exchange.assets[row.id];
    if(asset && 'fills' in node) {{
      const image=figma.createImage(decode64(asset.base64));
      node.fills=[{{type:'IMAGE',scaleMode:String((row.content||{{}}).image_mode||'FILL').toUpperCase(),imageHash:image.hash}}];
    }}
    for(const [path,tokenId] of Object.entries(row.token_bindings||{{}})) {{
      const variable=tokenVars.get(tokenId); if(!variable) continue;
      try {{
        if(path==='style.fill' && 'fills' in node && node.fills.length)
          node.fills=[figma.variables.setBoundVariableForPaint(node.fills[0],'color',variable)];
        else if(path==='style.stroke' && 'strokes' in node && node.strokes.length)
          node.strokes=[figma.variables.setBoundVariableForPaint(node.strokes[0],'color',variable)];
        else if(path==='opacity' && node.setBoundVariable) node.setBoundVariable('opacity',variable);
        else if(path==='style.radius' && node.setBoundVariable) node.setBoundVariable('cornerRadius',variable);
      }} catch (_) {{}}
    }}
  }}
  for(const row of ordered.filter(x => x.component_role === 'instance')) {{
    const definition=components.get(row.component_id); let node=definition?definition.createInstance():figma.createFrame();
    const parent=created.get(row.parent_id)||created.get(row.artboard_id)||page;
    parent.appendChild(node); applyFrame(node,row); created.set(row.id,node);
  }}
  for(const link of doc.interactions) {{
    const source=created.get(link.source_object_id), target=created.get(link.target_artboard_id||link.target_object_id);
    if(!source || !target || !source.setReactionsAsync) continue;
    const trigger={{click:'ON_CLICK',double_click:'ON_CLICK',hover:'MOUSE_ENTER',press:'MOUSE_DOWN',focus:'ON_KEY_DOWN',keyboard:'ON_KEY_DOWN'}}[link.trigger]||'ON_CLICK';
    const action=link.action==='back'?{{type:'BACK'}}:{{type:'NODE',destinationId:target.id,navigation:'NAVIGATE',transition:null,preserveScrollPosition:false}};
    try {{ await source.setReactionsAsync([{{trigger:{{type:trigger}},actions:[action]}}]); }} catch (_) {{}}
  }}
  figma.currentPage.selection=doc.artboards.map(x=>created.get(x.id)).filter(Boolean);
  figma.viewport.scrollAndZoomIntoView(figma.currentPage.selection);
  figma.closePlugin(`Imported ${{doc.artboards.length}} artboards and ${{doc.objects.length}} objects from Tiger Studio`);
}}
main().catch(error => figma.closePlugin('Tiger Studio import failed: '+error.message));
"""


def export_figma_plugin_package(
    document: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    normalized = normalize_ui_document(document)
    compatibility = inspect_figma_compatibility(normalized)
    if compatibility["counts"]["blocked"]:
        raise PainterUIFigmaError(
            "Figma export is blocked by unsupported objects; inspect compatibility"
        )
    target = Path(output_dir).expanduser().resolve() / "TigerStudioFigmaExport"
    target.mkdir(parents=True, exist_ok=True)
    exchange = {
        "schema": FIGMA_EXCHANGE_SCHEMA,
        "document": normalized,
        "assets": _asset_payload(normalized),
        "compatibility": compatibility,
    }
    manifest = {
        "name": "Tiger Studio Painter UI Import",
        "id": "tigerstudio-painter-ui-local-export",
        "api": "1.0.0",
        "main": "code.js",
        "editorType": ["figma"],
        "documentAccess": "dynamic-page",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "figma_exchange.json").write_text(
        json.dumps(exchange, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "compatibility_report.json").write_text(
        json.dumps(compatibility, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "code.js").write_text(_plugin_code(exchange), encoding="utf-8")
    (target / "README.txt").write_text(
        "Figma Desktop > Plugins > Development > Import plugin from manifest...\n"
        "Choose manifest.json, open a Figma Design file, then run the plugin.\n"
        "The bundle creates editable nodes; it is not a native .fig file.\n",
        encoding="utf-8",
    )
    return {
        "schema": FIGMA_EXCHANGE_SCHEMA,
        "ok": True,
        "output_dir": str(target),
        "manifest_path": str(target / "manifest.json"),
        "exchange_path": str(target / "figma_exchange.json"),
        "compatibility": compatibility,
    }


__all__ = [
    "FIGMA_EXCHANGE_SCHEMA",
    "FIGMA_IMPORT_SCHEMA",
    "PainterUIFigmaError",
    "default_figma_asset_root",
    "export_figma_plugin_package",
    "figma_file_key",
    "import_figma_file",
    "import_figma_json",
    "import_figma_payload",
    "inspect_figma_compatibility",
    "merge_figma_document",
]
