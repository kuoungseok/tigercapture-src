"""Action adapter for editable Motion Designer collage boards."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.motion_designer.collage import (
    add_collage_item,
    collage_boards,
    collage_painter_payload,
    create_collage_board,
    find_collage_board,
    preflight_collage,
    reorder_collage_item,
    replace_collage_item_source,
    set_collage_attachment,
    set_collage_edge,
    set_collage_painter_link,
    set_collage_scan_cleanup,
    update_collage_item,
)
from app.motion_designer.collage_assets import (
    collage_asset_catalog,
    create_collage_asset_layer,
)


class MotionCollageAdapterMixin:
    def _motion_collage_changed(
        self,
        composition,
        undo_label: str,
        **payload: Any,
    ) -> dict[str, Any]:
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": undo_label,
            "composition_id": composition.id,
            "revision": composition.revision,
            **payload,
        }

    def motion_collage_list(self, *, composition_id: str) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        boards = collage_boards(composition)
        return {"count": len(boards), "boards": boards}

    def motion_collage_asset_catalog(self) -> dict[str, Any]:
        assets = collage_asset_catalog()
        return {"count": len(assets), "assets": assets}

    def motion_collage_asset_add(
        self,
        *,
        composition_id: str,
        asset_id: str,
        seed: int = 17,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = create_collage_asset_layer(
            composition,
            asset_id,
            seed=seed,
        )
        composition.layers.append(layer)
        return self._motion_collage_changed(
            composition,
            "Add Collage Material",
            layer=layer.to_dict(),
        )

    def motion_collage_create(
        self,
        *,
        composition_id: str,
        layer_ids: list[str],
        name: str = "Collage Board",
        layout: str = "manual",
        seed: int = 17,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        board = create_collage_board(
            composition,
            layer_ids,
            name=name,
            layout=layout,
            seed=seed,
        )
        return self._motion_collage_changed(
            composition,
            "Create Collage Board",
            board=board,
        )

    def motion_collage_item_add(
        self,
        *,
        composition_id: str,
        board_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        item = add_collage_item(composition, board_id, layer_id)
        return self._motion_collage_changed(
            composition,
            "Add Collage Item",
            board_id=board_id,
            item=item,
        )

    def motion_collage_item_update(
        self,
        *,
        composition_id: str,
        board_id: str,
        item_id: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        item = update_collage_item(
            composition,
            board_id,
            item_id,
            changes,
        )
        return self._motion_collage_changed(
            composition,
            "Update Collage Item",
            board_id=board_id,
            item=item,
        )

    def motion_collage_item_reorder(
        self,
        *,
        composition_id: str,
        board_id: str,
        item_id: str,
        z_index: int,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        item = reorder_collage_item(
            composition,
            board_id,
            item_id,
            z_index,
        )
        return self._motion_collage_changed(
            composition,
            "Reorder Collage Item",
            board_id=board_id,
            item=item,
        )

    def motion_collage_edge_set(
        self,
        *,
        composition_id: str,
        board_id: str,
        item_id: str,
        mode: str,
        roughness: float = 0.35,
        feather: float = 0.0,
        seed: int = 17,
        points: list[list[float]] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        edge = set_collage_edge(
            composition,
            board_id,
            item_id,
            mode=mode,
            roughness=roughness,
            feather=feather,
            seed=seed,
            points=points,
        )
        return self._motion_collage_changed(
            composition,
            "Set Collage Edge",
            board_id=board_id,
            item_id=item_id,
            edge=edge,
        )

    def motion_collage_attachment_set(
        self,
        *,
        composition_id: str,
        board_id: str,
        item_id: str,
        kind: str,
        color: str = "#D8D0B099",
        strength: float = 0.35,
        angle: float = 0.0,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        attachment = set_collage_attachment(
            composition,
            board_id,
            item_id,
            kind=kind,
            color=color,
            strength=strength,
            angle=angle,
        )
        return self._motion_collage_changed(
            composition,
            "Set Collage Attachment",
            board_id=board_id,
            item_id=item_id,
            attachment=attachment,
        )

    def motion_collage_source_replace(
        self,
        *,
        composition_id: str,
        board_id: str,
        item_id: str,
        source: Mapping[str, Any],
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        result = replace_collage_item_source(
            composition,
            board_id,
            item_id,
            source,
        )
        return self._motion_collage_changed(
            composition,
            "Replace Collage Source",
            board_id=board_id,
            item_id=item_id,
            **result,
        )

    def motion_collage_scan_set(
        self,
        *,
        composition_id: str,
        board_id: str,
        item_id: str,
        white_balance: float = 0.8,
        paper_remove: float = 0.0,
        ink_preserve: float = 0.75,
        threshold: float = 0.72,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        settings = set_collage_scan_cleanup(
            composition,
            board_id,
            item_id,
            white_balance=white_balance,
            paper_remove=paper_remove,
            ink_preserve=ink_preserve,
            threshold=threshold,
        )
        return self._motion_collage_changed(
            composition,
            "Set Collage Scan Cleanup",
            board_id=board_id,
            item_id=item_id,
            settings=settings,
        )

    def motion_collage_paint_send(
        self,
        *,
        composition_id: str,
        board_id: str,
        item_id: str,
        document_id: str,
        object_id: str,
        revision: int = 1,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        link = set_collage_painter_link(
            composition,
            board_id,
            item_id,
            document_id=document_id,
            object_id=object_id,
            revision=revision,
        )
        payload = collage_painter_payload(composition, board_id, item_id)
        return self._motion_collage_changed(
            composition,
            "Send Collage Item To Painter",
            painter_link=link,
            painter_handoff=payload,
        )

    def motion_collage_paint_refresh(
        self,
        *,
        composition_id: str,
        board_id: str,
        item_id: str,
        revision: int,
        source: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        board = find_collage_board(composition, board_id)
        item = next(
            (
                row for row in board.get("items", [])
                if str(row.get("id") or "") == item_id
            ),
            None,
        )
        if not isinstance(item, dict):
            raise ValueError(f"collage item not found: {item_id}")
        link = item.get("painter_link")
        if not isinstance(link, dict) or not link:
            raise ValueError("collage item is not linked to Painter")
        previous_layer_id = str(item.get("layer_id") or "")
        if source is not None:
            replace_collage_item_source(
                composition,
                board_id,
                item_id,
                source,
            )
        link["revision"] = max(int(link.get("revision", 1) or 1), int(revision))
        if str(item.get("layer_id") or "") != previous_layer_id:
            raise RuntimeError("Painter refresh changed the stable Motion layer ID")
        return self._motion_collage_changed(
            composition,
            "Refresh Collage Item From Painter",
            painter_link=dict(link),
            painter_handoff=collage_painter_payload(
                composition,
                board_id,
                item_id,
            ),
        )

    def motion_collage_preflight(
        self,
        *,
        composition_id: str,
        board_id: str,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        return preflight_collage(composition, board_id)


__all__ = ["MotionCollageAdapterMixin"]
