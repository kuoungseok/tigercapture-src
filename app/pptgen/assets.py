"""Deck-local media pool helpers for the user PPT generator."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.pptgen.asset_bridge import asset_kind_for_path, slide_element_from_media_asset
from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec


PPT_ASSET_SCHEMA = "tigercapture.ppt.asset.v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _asset_key(path: str | Path) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    try:
        return str(Path(raw).expanduser().resolve()).casefold()
    except Exception:
        return str(Path(raw)).casefold()


def _slug(text: str) -> str:
    chars: list[str] = []
    for char in str(text or "").casefold():
        if char.isalnum() and char.isascii():
            chars.append(char)
        elif char in {"-", "_", " "}:
            chars.append("-")
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "asset"


def _unique_asset_id(deck: DeckSpec, path: str | Path, preferred: str = "") -> str:
    existing = {str(row.get("id") or "") for row in deck.assets if isinstance(row, dict)}
    base = _slug(preferred or Path(path).stem or Path(path).name or "asset")
    candidate = f"asset-{base}"
    if candidate not in existing:
        return candidate
    index = 2
    while f"{candidate}-{index}" in existing:
        index += 1
    return f"{candidate}-{index}"


def _normalize_asset_record(row: dict[str, Any], *, deck: DeckSpec | None = None) -> dict[str, Any]:
    path = str(row.get("path") or row.get("source_path") or "").strip()
    kind = str(row.get("kind") or row.get("asset_kind") or asset_kind_for_path(path)).strip() or "media_actor"
    name = str(row.get("name") or Path(path).stem or Path(path).name or kind.replace("_", " ").title()).strip()
    asset_id = str(row.get("id") or "").strip()
    if not asset_id and deck is not None:
        asset_id = _unique_asset_id(deck, path, name)
    elif not asset_id:
        asset_id = f"asset-{_slug(name or path)}"
    created_at = str(row.get("created_at") or _utc_now())
    normalized = dict(row)
    normalized.update(
        {
            "schema": str(row.get("schema") or PPT_ASSET_SCHEMA),
            "id": asset_id,
            "kind": kind,
            "name": name,
            "path": path,
            "source_path": path,
            "source": str(row.get("source") or "ppt_media_pool"),
            "created_at": created_at,
        }
    )
    return normalized


def normalize_deck_assets(deck: DeckSpec) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in list(deck.assets or []):
        if not isinstance(row, dict):
            continue
        asset = _normalize_asset_record(row, deck=deck)
        if asset["id"] in seen_ids:
            asset["id"] = _unique_asset_id(deck, asset.get("path") or "", asset.get("name") or "")
        seen_ids.add(asset["id"])
        normalized.append(asset)
    deck.assets = normalized
    return deck.assets


def add_deck_asset(
    deck: DeckSpec,
    path: str | Path,
    *,
    kind: str | None = None,
    name: str = "",
    source: str = "ppt_media_pool",
) -> dict[str, Any]:
    normalize_deck_assets(deck)
    raw_path = str(path or "").strip()
    if not raw_path:
        raise RuntimeError("path is required")
    key = _asset_key(raw_path)
    for row in deck.assets:
        if _asset_key(row.get("path") or row.get("source_path") or "") != key:
            continue
        if kind:
            row["kind"] = str(kind)
        if name:
            row["name"] = str(name)
        row["source"] = str(source or row.get("source") or "ppt_media_pool")
        row["source_path"] = str(row.get("path") or raw_path)
        return row
    payload = _normalize_asset_record(
        {
            "path": raw_path,
            "kind": kind or asset_kind_for_path(raw_path),
            "name": name,
            "source": source,
        },
        deck=deck,
    )
    deck.assets.append(payload)
    return payload


def list_deck_assets(deck: DeckSpec) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in normalize_deck_assets(deck):
        path = Path(str(row.get("path") or ""))
        payload = dict(row)
        payload.update(
            {
                "exists": path.is_file(),
                "file_name": path.name,
                "extension": path.suffix.lower(),
            }
        )
        rows.append(payload)
    return rows


def deck_asset_by_id(deck: DeckSpec, asset_id: str) -> dict[str, Any] | None:
    wanted = str(asset_id or "").strip()
    for row in normalize_deck_assets(deck):
        if str(row.get("id") or "") == wanted:
            return row
    return None


def remove_deck_asset(deck: DeckSpec, asset_id: str) -> dict[str, Any]:
    wanted = str(asset_id or "").strip()
    if not wanted:
        raise RuntimeError("asset_id is required")
    normalize_deck_assets(deck)
    for index, row in enumerate(deck.assets):
        if str(row.get("id") or "") != wanted:
            continue
        return deck.assets.pop(index)
    raise RuntimeError(f"PPT asset not found: {wanted}")


def element_from_deck_asset(
    deck: DeckSpec,
    asset_id: str,
    element_id: str,
    *,
    x: float = 0.18,
    y: float = 0.24,
    w: float | None = None,
    h: float | None = None,
    source: str = "ppt_media_pool",
) -> SlideElement:
    asset = deck_asset_by_id(deck, asset_id)
    if asset is None:
        raise RuntimeError(f"PPT asset not found: {asset_id}")
    element = slide_element_from_media_asset(
        str(asset.get("path") or asset.get("source_path") or ""),
        element_id,
        x=x,
        y=y,
        w=w,
        h=h,
        kind=str(asset.get("kind") or ""),
        name=str(asset.get("name") or ""),
        source=source,
    )
    element.metadata["ppt_asset_id"] = str(asset.get("id") or "")
    return element


def insert_deck_asset_to_slide(
    deck: DeckSpec,
    asset_id: str,
    slide: SlideSpec,
    *,
    element_id: str,
    x: float = 0.18,
    y: float = 0.24,
    w: float | None = None,
    h: float | None = None,
    source: str = "ppt_media_pool",
) -> SlideElement:
    element = element_from_deck_asset(deck, asset_id, element_id, x=x, y=y, w=w, h=h, source=source)
    slide.add_element(element)
    return element


__all__ = [
    "PPT_ASSET_SCHEMA",
    "add_deck_asset",
    "deck_asset_by_id",
    "element_from_deck_asset",
    "insert_deck_asset_to_slide",
    "list_deck_assets",
    "normalize_deck_assets",
    "remove_deck_asset",
]
