"""AR/PBR real-time compositor package.

The package is intentionally UI-neutral. Integration with ProjectPlayer,
VideoExporter, project I/O, and Media Pool should be added through thin hooks.
"""

from app.ar_pbr.compositor import composite_export_frame, composite_preview_frame
from app.ar_pbr.gpu_preview import build_gpu_preview_items
from app.ar_pbr.asset_cache import load_asset_descriptor, store_asset_descriptor
from app.ar_pbr.importer import import_asset, import_track_asset, importer_backend_status
from app.ar_pbr.placement import camera_ray_from_image_point, intersect_ray_plane, resolve_track_placement
from app.ar_pbr.scene_anchor import promote_track_to_scene_anchor, road_plane_sample_points
from app.ar_pbr.software_renderer import render_software_pbr_frame

__all__ = [
    "composite_preview_frame",
    "composite_export_frame",
    "build_gpu_preview_items",
    "import_asset",
    "import_track_asset",
    "importer_backend_status",
    "load_asset_descriptor",
    "store_asset_descriptor",
    "render_software_pbr_frame",
    "camera_ray_from_image_point",
    "intersect_ray_plane",
    "resolve_track_placement",
    "promote_track_to_scene_anchor",
    "road_plane_sample_points",
]
