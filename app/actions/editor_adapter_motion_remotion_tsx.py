"""Actions for linked Remotion-style TSX sources."""
from __future__ import annotations

from typing import Any


class MotionRemotionTsxAdapterMixin:
    def motion_remotion_tsx_runtime_status(self) -> dict[str, Any]:
        from app.motion_designer.remotion_tsx import remotion_tsx_runtime_status

        return remotion_tsx_runtime_status()

    def motion_remotion_tsx_runtime_install(self) -> dict[str, Any]:
        from app.motion_designer.remotion_tsx import install_remotion_tsx_runtime

        return install_remotion_tsx_runtime()

    def motion_remotion_tsx_inspect(self, *, path: str) -> dict[str, Any]:
        from app.motion_designer.remotion_tsx import inspect_remotion_tsx

        return inspect_remotion_tsx(path).to_dict()

    def motion_remotion_tsx_import(
        self,
        *,
        composition_id: str,
        path: str,
        trust_source: bool = False,
        prepare_preview: bool = True,
        duration_ms: int = 5000,
    ) -> dict[str, Any]:
        from app.motion_designer.remotion_tsx import (
            create_remotion_tsx_layer,
            prepare_remotion_tsx_frames,
        )

        service = self._motion_service()
        composition = service.get(composition_id)
        linked_duration_ms = min(
            composition.duration_ms,
            max(1, int(duration_ms or 5000)),
        )
        prepared = None
        if prepare_preview:
            prepared = prepare_remotion_tsx_frames(
                path,
                width=composition.width,
                height=composition.height,
                fps=composition.fps,
                duration_ms=linked_duration_ms,
                trusted=bool(trust_source),
            )
        layer = create_remotion_tsx_layer(
            path,
            width=composition.width,
            height=composition.height,
            fps=composition.fps,
            duration_ms=linked_duration_ms,
            prepared=prepared,
        )
        result = service.add_layer(composition.id, layer)
        self._motion_commit(service)
        self._motion_sync_owner()
        return {
            "imported": True,
            "source_preserved": True,
            "prepared": prepared is not None,
            "layer": result.to_dict(),
        }

    def motion_remotion_tsx_refresh(
        self,
        *,
        composition_id: str,
        layer_id: str,
        trust_source: bool = False,
    ) -> dict[str, Any]:
        from app.motion_designer.commands import find_layer
        from app.motion_designer.remotion_tsx import (
            REMOTION_TSX_SOURCE_KIND,
            prepare_remotion_tsx_frames,
        )

        service = self._motion_service()
        composition = service.get(composition_id)
        layer = find_layer(composition, layer_id)
        if layer.source.kind != REMOTION_TSX_SOURCE_KIND:
            raise ValueError("Layer is not a linked Remotion TSX source")
        prepared = prepare_remotion_tsx_frames(
            layer.source.uri,
            width=composition.width,
            height=composition.height,
            fps=composition.fps,
            duration_ms=max(1, int(layer.out_ms - layer.in_ms)),
            trusted=bool(trust_source),
        )
        layer.source.revision = str(prepared["source_sha256"])
        layer.source.params.update({
            "source_sha256": str(prepared["source_sha256"]),
            "prepared_source_sha256": str(prepared["source_sha256"]),
            "job_key": str(prepared["job_key"]),
            "frame_dir": str(prepared["frame_dir"]),
            "duration_frames": int(prepared["duration_frames"]),
        })
        composition.revision += 1
        self._motion_commit(service)
        self._motion_sync_owner()
        return {
            "refreshed": True,
            "source_preserved": True,
            "layer": layer.to_dict(),
        }


__all__ = ["MotionRemotionTsxAdapterMixin"]
