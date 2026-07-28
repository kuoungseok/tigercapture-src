"""Action adapter for Motion tracking, stabilization, and camera solve."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.motion_designer.commands import find_layer


class MotionTrackingAdapterMixin:
    def _motion_tracking_composition(self, composition_id: str):
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return composition

    def _motion_tracking_changed(
        self,
        composition,
        undo_label: str,
        **result: Any,
    ) -> dict[str, Any]:
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": undo_label,
            "composition_id": composition.id,
            "revision": composition.revision,
            **result,
        }

    def _motion_store_track(
        self,
        composition,
        data: Mapping[str, Any],
    ) -> dict[str, Any]:
        from app.motion_designer.tracking_workflow import normalize_track_asset

        asset = normalize_track_asset(data)
        assets = [
            dict(item)
            for item in composition.metadata.get("tracking_assets", [])
            if isinstance(item, Mapping) and str(item.get("id") or "") != asset["id"]
        ]
        assets.append(asset)
        composition.metadata["tracking_assets"] = assets
        return asset

    def motion_track_create(
        self,
        *,
        composition_id: str,
        kind: str,
        samples: Sequence[Mapping[str, Any]],
        name: str = "",
        source_uri: str = "",
        source_revision: str = "",
        origin: Sequence[float] = (0.0, 0.0),
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_tracking_composition(composition_id)
        asset = self._motion_store_track(composition, {
            "kind": kind,
            "name": name,
            "source_uri": source_uri,
            "source_revision": source_revision,
            "origin": list(origin),
            "samples": list(samples),
            "metadata": dict(metadata or {}),
        })
        return self._motion_tracking_changed(
            composition,
            "Create Motion Track",
            track=asset,
        )

    def _motion_track_video(
        self,
        *,
        composition_id: str,
        video_path: str,
        kind: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        sample_interval_ms: int = 100,
        target_size: Sequence[int] | None = None,
        roi: Sequence[float] | None = None,
        name: str = "",
        analysis_mode: str = "",
    ) -> dict[str, Any]:
        from app.motion_designer.tracking_provider import (
            MotionTrackingRequest,
            generate_tracking_cache,
        )

        mode = str(analysis_mode or "").lower()
        if mode not in {"point", "planar"}:
            mode = "planar" if kind in {"planar", "multi_point"} else "point"
        size_values = list(target_size or ())
        roi_values = list(roi or ())
        request = MotionTrackingRequest(
            video_path=str(video_path),
            mode=mode,
            start_ms=int(start_ms),
            end_ms=None if end_ms is None else int(end_ms),
            sample_interval_ms=int(sample_interval_ms),
            target_size=(
                (int(size_values[0]), int(size_values[1]))
                if len(size_values) >= 2 else None
            ),
            roi=(
                tuple(float(value) for value in roi_values[:4])
                if len(roi_values) >= 4 else None
            ),
        )
        cache = generate_tracking_cache(request)
        composition = self._motion_tracking_composition(composition_id)
        asset = self._motion_store_track(composition, {
            "kind": kind,
            "name": name or f"{kind.replace('_', ' ').title()} Track",
            "source_uri": str(video_path),
            "source_revision": cache.source_revision,
            "origin": list(cache.origin),
            "samples": [item.to_dict() for item in cache.samples],
            "metadata": dict(cache.metadata),
        })
        return self._motion_tracking_changed(
            composition,
            f"Analyze Motion {kind.replace('_', ' ').title()} Track",
            track=asset,
        )

    def motion_track_point(self, **params: Any) -> dict[str, Any]:
        return self._motion_track_video(kind="point", **params)

    def motion_track_planar(self, **params: Any) -> dict[str, Any]:
        return self._motion_track_video(kind="planar", **params)

    def motion_track_multi_point(self, **params: Any) -> dict[str, Any]:
        return self._motion_track_video(kind="multi_point", **params)

    def motion_track_mask(self, **params: Any) -> dict[str, Any]:
        values = dict(params)
        values["analysis_mode"] = str(values.pop("mode", "planar"))
        return self._motion_track_video(kind="mask", **values)

    def motion_track_face(
        self,
        *,
        composition_id: str,
        samples: Sequence[Mapping[str, Any]] = (),
        name: str = "Face Track",
        source_uri: str = "",
        source_revision: str = "",
        origin: Sequence[float] = (0.0, 0.0),
        video_path: str = "",
        backend: str = "auto",
        max_fps: float = 15.0,
        max_frames: int | None = None,
        source_in_ms: int = 0,
        timeline_in_ms: int = 0,
        timeline_out_ms: int | None = None,
        time_scale: float = 1.0,
    ) -> dict[str, Any]:
        values = list(samples)
        face_metadata: dict[str, Any] = {
            "provider": "external_or_tiger_face_landmarks",
        }
        resolved_source = str(source_uri or video_path or "")
        track_origin = list(origin)
        if not values and video_path:
            from app.motion_designer.tracking_workflow import (
                face_tracking_cache_from_video,
            )

            cache = face_tracking_cache_from_video(
                video_path,
                backend=backend,
                max_fps=max_fps,
                max_frames=max_frames,
            )
            values = [item.to_dict() for item in cache.samples]
            face_metadata = {
                **cache.metadata,
                "video_face_driver": dict(cache.metadata),
            }
            source_revision = cache.source_revision
            track_origin = list(cache.origin)
        if not values:
            raise ValueError("motion.track.face requires samples or video_path")
        if timeline_out_ms is not None:
            from app.motion_designer.tracking_workflow import (
                retime_tracking_samples,
            )

            values = retime_tracking_samples(
                values,
                source_in_ms=int(source_in_ms),
                timeline_in_ms=int(timeline_in_ms),
                timeline_out_ms=int(timeline_out_ms),
                time_scale=float(time_scale),
            )
            if not values:
                raise ValueError(
                    "face tracking produced no samples inside the requested timeline range"
                )
        if not source_revision and resolved_source:
            from app.motion_designer.tracking_workflow import (
                source_revision_for_path,
            )

            source_revision = source_revision_for_path(resolved_source)
        return self.motion_track_create(
            composition_id=composition_id,
            kind="face",
            samples=values,
            name=name,
            source_uri=resolved_source,
            source_revision=source_revision,
            origin=track_origin,
            metadata=face_metadata,
        )

    def _motion_track_asset(self, composition, track_id: str) -> dict[str, Any]:
        for item in composition.metadata.get("tracking_assets", []):
            if isinstance(item, Mapping) and str(item.get("id") or "") == str(track_id):
                return dict(item)
        raise ValueError(f"Motion track not found: {track_id}")

    def motion_track_apply(
        self,
        *,
        composition_id: str,
        track_id: str,
        layer_id: str,
        channels: Sequence[str] = ("position", "scale", "rotation"),
        stabilize: bool = False,
        target_kind: str = "layer",
        effect_id: str = "",
        parameter: str = "",
        pin_id: str = "",
    ) -> dict[str, Any]:
        from app.motion_designer.tracking_workflow import (
            apply_planar_track_to_corner_pin,
            apply_track_to_effect_point,
            apply_track_to_layer,
            apply_track_to_puppet_pin,
        )

        composition = self._motion_tracking_composition(composition_id)
        asset = self._motion_track_asset(composition, track_id)
        layer = find_layer(composition, layer_id)
        current_revision = str(layer.source.revision or "")
        expected_revision = str(asset.get("source_revision") or "")
        if expected_revision and current_revision and expected_revision != current_revision:
            raise ValueError("Motion track source revision does not match the target layer")
        target = str(target_kind or "layer").lower()
        if target == "effect_point":
            if stabilize:
                raise ValueError("effect-point tracking does not support stabilization")
            if not effect_id or not parameter:
                raise ValueError("effect_point target requires effect_id and parameter")
            applied = apply_track_to_effect_point(
                layer,
                asset,
                effect_id=effect_id,
                parameter=parameter,
            )
        elif target == "puppet_pin":
            if stabilize:
                raise ValueError("Puppet-pin tracking does not support stabilization")
            if not pin_id:
                raise ValueError("puppet_pin target requires pin_id")
            applied = apply_track_to_puppet_pin(
                layer,
                asset,
                pin_id=pin_id,
                target_size=(
                    float(layer.source.params.get("width", composition.width)),
                    float(layer.source.params.get("height", composition.height)),
                ),
            )
        elif target == "corner_pin":
            if stabilize:
                raise ValueError("corner-pin tracking does not support stabilization")
            if not effect_id:
                raise ValueError("corner_pin target requires effect_id")
            applied = apply_planar_track_to_corner_pin(
                layer,
                asset,
                effect_id=effect_id,
                target_size=(
                    float(layer.source.params.get("width", composition.width)),
                    float(layer.source.params.get("height", composition.height)),
                ),
            )
        elif target == "layer":
            applied = apply_track_to_layer(
                layer,
                asset,
                stabilize=bool(stabilize),
                channels=channels,
            )
        else:
            raise ValueError(f"unsupported Motion tracking target: {target_kind}")
        return self._motion_tracking_changed(
            composition,
            "Stabilize Motion Layer" if stabilize else "Apply Motion Track",
            **applied,
        )

    def motion_stabilize_create(self, **params: Any) -> dict[str, Any]:
        values = dict(params)
        values["stabilize"] = True
        return self.motion_track_apply(**values)

    def motion_track_diagnostics(
        self,
        *,
        composition_id: str,
        track_id: str = "",
        current_source_revision: str = "",
    ) -> dict[str, Any]:
        from app.motion_designer.tracking_workflow import track_asset_diagnostics

        composition = self._motion_tracking_composition(composition_id)
        assets = [
            dict(item)
            for item in composition.metadata.get("tracking_assets", [])
            if isinstance(item, Mapping)
            and (not track_id or str(item.get("id") or "") == str(track_id))
        ]
        if track_id and not assets:
            raise ValueError(f"Motion track not found: {track_id}")
        return {
            "composition_id": composition.id,
            "tracks": [
                track_asset_diagnostics(
                    item,
                    current_source_revision=current_source_revision,
                )
                for item in assets
            ],
        }

    def motion_track_relink(
        self,
        *,
        composition_id: str,
        track_id: str,
        source_uri: str,
        source_revision: str = "",
    ) -> dict[str, Any]:
        from app.motion_designer.tracking_workflow import (
            normalize_track_asset,
            source_revision_for_path,
        )

        composition = self._motion_tracking_composition(composition_id)
        assets = []
        updated = None
        resolved_revision = str(
            source_revision or source_revision_for_path(source_uri)
        )
        if not resolved_revision:
            raise ValueError("Motion track relink source is missing or unreadable")
        for item in composition.metadata.get("tracking_assets", []):
            if not isinstance(item, Mapping):
                continue
            candidate = dict(item)
            if str(candidate.get("id") or "") == str(track_id):
                candidate["source_uri"] = str(source_uri)
                candidate["source_revision"] = resolved_revision
                metadata = dict(candidate.get("metadata") or {})
                metadata["relinked"] = True
                candidate["metadata"] = metadata
                updated = normalize_track_asset(candidate)
                assets.append(updated)
            else:
                assets.append(candidate)
        if updated is None:
            raise ValueError(f"Motion track not found: {track_id}")
        composition.metadata["tracking_assets"] = assets
        return self._motion_tracking_changed(
            composition,
            "Relink Motion Track",
            track=updated,
        )

    def motion_camera_solve_create(
        self,
        *,
        composition_id: str,
        image_points: Sequence[Sequence[float]],
        frame_size: Sequence[int],
        source_id: str = "",
        depth_source_id: str = "",
        time_ms: int = 0,
        focal_length_px: float | None = None,
    ) -> dict[str, Any]:
        from app.camera_solve.solver import solve_road_plane_from_points

        values = list(frame_size)
        if len(values) < 2:
            raise ValueError("frame_size must contain width and height")
        solution, diagnostics = solve_road_plane_from_points(
            [list(item) for item in image_points],
            frame_size=(int(values[0]), int(values[1])),
            source_id=source_id,
            depth_source_id=depth_source_id,
            time_ms=int(time_ms),
            focal_length_px=focal_length_px,
        )
        if solution is None:
            raise ValueError(str(diagnostics.get("reason") or "camera solve failed"))
        composition = self._motion_tracking_composition(composition_id)
        solutions = [
            dict(item)
            for item in composition.metadata.get("camera_solutions", [])
            if isinstance(item, Mapping)
            and str(item.get("id") or "") != str(solution["id"])
        ]
        solutions.append(solution)
        composition.metadata["camera_solutions"] = solutions
        return self._motion_tracking_changed(
            composition,
            "Create Assisted Camera Solve",
            camera_solution=solution,
            diagnostics=diagnostics,
        )
