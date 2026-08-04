"""Bounded tile, GPU-upload, async-map, and Undo budgets for large Painter canvases."""
from __future__ import annotations

import time
import hashlib
import math
import threading
import dataclasses
import sys
from concurrent.futures import Future, ThreadPoolExecutor, wait
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPixmap


DEFAULT_TILE_SIZE = 256
DEFAULT_TILE_BUDGET_MB = 192
DEFAULT_UNDO_BUDGET_MB = 256
MIN_TILE_SIZE = 32
MAX_TILE_SIZE = 1024
MIN_TILE_BUDGET_MB = 1
MAX_TILE_BUDGET_MB = 4096
MIN_UNDO_BUDGET_MB = 1
MAX_UNDO_BUDGET_MB = 8192

LARGE_CANVAS_RESOURCE_POLICY_CONTRACT = {
    "schema": "tigerstudio.painter.large_canvas_resource_policy.v1",
    "source": "tiger_authored_resource_defaults_with_runtime_telemetry",
    "default_tile_size": DEFAULT_TILE_SIZE,
    "default_tile_budget_mb": DEFAULT_TILE_BUDGET_MB,
    "default_undo_budget_mb": DEFAULT_UNDO_BUDGET_MB,
    "configuration_bounds": {
        "tile_size": [MIN_TILE_SIZE, MAX_TILE_SIZE],
        "tile_budget_mb": [MIN_TILE_BUDGET_MB, MAX_TILE_BUDGET_MB],
        "undo_budget_mb": [MIN_UNDO_BUDGET_MB, MAX_UNDO_BUDGET_MB],
    },
    "cache_shares": {
        "main_tiles": 0.60,
        "brush_stamps": 0.10,
        "material_maps": 0.20,
        "wet_canvas": 0.10,
    },
    "default_material_task_capacity": 4096,
    "default_material_result_capacity": 4096,
    "performance_threshold_claim": False,
    "universal_memory_safety_claim": False,
}


def _rect(value: QRect | tuple[int, int, int, int] | None, width: int, height: int) -> QRect:
    bounds = QRect(0, 0, max(1, int(width)), max(1, int(height)))
    if value is None:
        return bounds
    candidate = QRect(value) if isinstance(value, QRect) else QRect(*map(int, value))
    return candidate.normalized().intersected(bounds)


def tile_coordinates(rect: QRect, width: int, height: int, tile_size: int = DEFAULT_TILE_SIZE) -> list[tuple[int, int]]:
    clipped = _rect(rect, width, height)
    if clipped.isEmpty():
        return []
    size = max(MIN_TILE_SIZE, int(tile_size))
    left, top = clipped.left() // size, clipped.top() // size
    right, bottom = clipped.right() // size, clipped.bottom() // size
    return [(tx, ty) for ty in range(top, bottom + 1) for tx in range(left, right + 1)]


@dataclass
class TileRecord:
    image: QImage
    bytes: int
    revision: int
    gpu_handle: int = 0


class RetainedTileCache:
    """LRU cache that uploads only dirty document tiles when a GPU uploader exists."""

    def __init__(
        self,
        *,
        tile_size: int = DEFAULT_TILE_SIZE,
        budget_bytes: int = DEFAULT_TILE_BUDGET_MB * 1024 * 1024,
        gpu_uploader: Callable[[tuple[str, int, int], QImage, int], int] | None = None,
        gpu_deleter: Callable[[int], None] | None = None,
    ) -> None:
        self.tile_size = max(MIN_TILE_SIZE, min(MAX_TILE_SIZE, int(tile_size)))
        self.budget_bytes = max(self.tile_size * self.tile_size * 4, int(budget_bytes))
        self.gpu_uploader = gpu_uploader; self.gpu_deleter = gpu_deleter
        self._tiles: OrderedDict[tuple[str, int, int], TileRecord] = OrderedDict()
        self._layer_sizes: dict[str, tuple[int, int]] = {}
        self._revision = 0; self._bytes = 0
        self.uploaded_tiles = 0; self.uploaded_bytes = 0; self.cache_hits = 0
        self.evictions = 0; self.gpu_failures = 0
        self.gpu_cleanup_failures = 0
        self.display_reads = 0
        self.last_gpu_error = ""
        self.last_gpu_cleanup_error = ""

    def _delete_gpu_handle(self, handle: int) -> None:
        if not handle or self.gpu_deleter is None:
            return
        try:
            self.gpu_deleter(handle)
        except Exception as exc:
            self.gpu_cleanup_failures += 1
            self.last_gpu_cleanup_error = f"{type(exc).__name__}: {exc}"

    def clear(self) -> None:
        if self.gpu_deleter:
            for row in self._tiles.values():
                if row.gpu_handle:
                    self._delete_gpu_handle(row.gpu_handle)
        self._tiles.clear(); self._layer_sizes.clear(); self._bytes = 0

    def remove_layer(self, layer_id: str) -> int:
        keys = [key for key in self._tiles if key[0] == str(layer_id)]
        for key in keys:
            row = self._tiles.pop(key); self._bytes -= row.bytes
            if row.gpu_handle and self.gpu_deleter:
                self._delete_gpu_handle(row.gpu_handle)
        self._layer_sizes.pop(str(layer_id), None)
        return len(keys)

    def invalidate_gpu_handles(self) -> int:
        invalidated = 0
        for row in self._tiles.values():
            if row.gpu_handle:
                row.gpu_handle = 0; invalidated += 1
        return invalidated

    def update_layer(
        self,
        layer_id: str,
        image: QImage,
        *,
        dirty_rect: QRect | tuple[int, int, int, int] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(image, QImage) or image.isNull():
            return {"updated_tiles": 0, "uploaded_bytes": 0, "backend": self.backend}
        started = time.perf_counter(); key_layer = str(layer_id); self._revision += 1
        self._layer_sizes[key_layer] = (image.width(), image.height())
        coords = tile_coordinates(_rect(dirty_rect, image.width(), image.height()), image.width(), image.height(), self.tile_size)
        bytes_before = self.uploaded_bytes; updated = 0
        for tx, ty in coords:
            x, y = tx * self.tile_size, ty * self.tile_size
            tile = image.copy(x, y, min(self.tile_size, image.width() - x), min(self.tile_size, image.height() - y))
            key = (key_layer, tx, ty); old = self._tiles.pop(key, None)
            old_handle = int(old.gpu_handle) if old else 0
            if old:
                self._bytes -= old.bytes
            byte_count = tile.width() * tile.height() * 4; handle = old_handle
            if self.gpu_uploader:
                try:
                    handle = int(self.gpu_uploader(key, tile, old_handle) or 0)
                except Exception as exc:
                    self.gpu_failures += 1; self.last_gpu_error = f"{type(exc).__name__}: {exc}"
                    self.gpu_uploader = None; handle = 0
            self._tiles[key] = TileRecord(tile, byte_count, self._revision, handle)
            self._bytes += byte_count; self.uploaded_tiles += 1; self.uploaded_bytes += byte_count; updated += 1
        self._evict()
        return {
            "updated_tiles": updated, "uploaded_bytes": self.uploaded_bytes - bytes_before,
            "dirty_rect": [int(v) for v in (_rect(dirty_rect, image.width(), image.height()).getRect())],
            "backend": self.backend, "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
        }

    def _evict(self) -> None:
        while self._bytes > self.budget_bytes and self._tiles:
            _key, row = self._tiles.popitem(last=False); self._bytes -= row.bytes; self.evictions += 1
            if row.gpu_handle and self.gpu_deleter:
                self._delete_gpu_handle(row.gpu_handle)

    @property
    def backend(self) -> str:
        return "retained_gpu_texture_tiles" if self.gpu_uploader is not None else "bounded_qimage_tile_fallback"

    def tile(self, layer_id: str, tx: int, ty: int) -> QImage | None:
        key = (str(layer_id), int(tx), int(ty)); row = self._tiles.pop(key, None)
        if row is None: return None
        self._tiles[key] = row; self.cache_hits += 1; return QImage(row.image)

    def reconstruct(self, layer_id: str) -> QImage:
        width, height = self._layer_sizes.get(str(layer_id), (1, 1))
        result = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied); result.fill(0)
        from PySide6.QtGui import QPainter
        painter = QPainter(result)
        for (candidate, tx, ty), row in self._tiles.items():
            if candidate == str(layer_id): painter.drawImage(tx * self.tile_size, ty * self.tile_size, row.image)
        painter.end(); return result

    def layer_records(self, layer_id: str) -> list[tuple[int, int, TileRecord]]:
        target = str(layer_id)
        return [
            (tx, ty, row)
            for (candidate, tx, ty), row in self._tiles.items()
            if candidate == target
        ]

    def layer_complete(self, layer_id: str) -> bool:
        target = str(layer_id)
        width, height = self._layer_sizes.get(target, (0, 0))
        if width <= 0 or height <= 0:
            return False
        expected = len(tile_coordinates(QRect(0, 0, width, height), width, height, self.tile_size))
        return len(self.layer_records(target)) == expected

    def telemetry(self) -> dict[str, Any]:
        gpu_tiles = sum(1 for row in self._tiles.values() if row.gpu_handle)
        return {
            "schema": "tigerstudio.painter.large-canvas.tiles.v1", "backend": self.backend,
            "tile_size": self.tile_size, "tile_count": len(self._tiles), "gpu_tile_count": gpu_tiles,
            "bytes": self._bytes, "budget_bytes": self.budget_bytes,
            "uploaded_tiles": self.uploaded_tiles, "uploaded_bytes": self.uploaded_bytes,
            "cache_hits": self.cache_hits, "evictions": self.evictions, "gpu_failures": self.gpu_failures,
            "gpu_cleanup_failures": self.gpu_cleanup_failures,
            "display_reads": self.display_reads,
            "last_gpu_error": self.last_gpu_error,
            "last_gpu_cleanup_error": self.last_gpu_cleanup_error,
            "bounded": self._bytes <= self.budget_bytes,
        }


class DirtyMaterialTileQueue:
    def __init__(self, *, max_tasks: int = 4096) -> None:
        self.max_tasks = max(1, int(max_tasks)); self._queue: deque[tuple[str, int, int]] = deque(); self._known: set[tuple[str, int, int]] = set(); self.dropped = 0

    def schedule(self, kinds: Iterable[str], coordinates: Iterable[tuple[int, int]]) -> int:
        added = 0
        for kind in kinds:
            for tx, ty in coordinates:
                task = (str(kind), int(tx), int(ty))
                if task in self._known: continue
                if len(self._queue) >= self.max_tasks:
                    removed = self._queue.popleft(); self._known.discard(removed); self.dropped += 1
                self._queue.append(task); self._known.add(task); added += 1
        return added

    def drain(self, worker: Callable[[str, int, int], Any], *, limit: int = 32) -> list[Any]:
        output = []
        for _ in range(min(max(0, int(limit)), len(self._queue))):
            task = self._queue.popleft(); self._known.discard(task); output.append(worker(*task))
        return output

    def complete_kinds(self, kinds: Iterable[str]) -> int:
        selected = {str(kind) for kind in kinds}; before = len(self._queue)
        self._queue = deque(task for task in self._queue if task[0] not in selected)
        self._known = set(self._queue)
        return before - len(self._queue)

    def telemetry(self) -> dict[str, Any]:
        return {"queued": len(self._queue), "max_tasks": self.max_tasks, "dropped": self.dropped, "bounded": len(self._queue) <= self.max_tasks}


class MaterialTileExecutor:
    """Process actual derived-map tile bytes with revision/stale/cancel semantics."""

    def __init__(self, *, max_workers: int = 1, max_results: int = 4096, processor=None) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max(1, int(max_workers)), thread_name_prefix="PainterMaterialTile")
        self.max_results = max(1, int(max_results)); self._processor = processor or self._fingerprint
        self._lock = threading.RLock(); self._revision: dict[str, int] = {}; self._futures: set[Future] = set()
        self._results: OrderedDict[tuple[str, int, int], dict[str, Any]] = OrderedDict()
        self.submitted = 0; self.completed = 0; self.stale = 0; self.cancelled = 0; self.failed = 0
        self.error_capacity = 32
        self._recent_errors: deque[dict[str, Any]] = deque(maxlen=self.error_capacity)

    @staticmethod
    def _fingerprint(kind: str, tx: int, ty: int, revision: int, payload: bytes, width: int, height: int) -> dict[str, Any]:
        return {"kind": kind, "tx": tx, "ty": ty, "revision": revision, "width": width, "height": height, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}

    def submit_image(self, kind: str, image: QImage, coordinates: Iterable[tuple[int, int]], tile_size: int) -> dict[str, int]:
        target = str(kind); size = max(1, int(tile_size))
        with self._lock:
            revision = self._revision.get(target, 0) + 1; self._revision[target] = revision
        added = 0
        for tx, ty in coordinates:
            tile = image.copy(int(tx) * size, int(ty) * size, min(size, image.width() - int(tx) * size), min(size, image.height() - int(ty) * size)).convertToFormat(QImage.Format.Format_RGBA8888)
            if tile.isNull(): continue
            payload = bytes(tile.constBits())
            future = self._pool.submit(self._processor, target, int(tx), int(ty), revision, payload, tile.width(), tile.height())
            with self._lock:
                self._futures.add(future); self.submitted += 1
            future.add_done_callback(lambda done, k=target, r=revision, x=int(tx), y=int(ty): self._finish(done, k, r, x, y))
            added += 1
        return {"revision": revision, "submitted": added}

    def _finish(self, future: Future, kind: str, revision: int, tx: int, ty: int) -> None:
        with self._lock:
            self._futures.discard(future)
            if future.cancelled(): self.cancelled += 1; return
            try: result = dict(future.result())
            except Exception as exc:
                self.failed += 1
                self._recent_errors.append({
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "kind": kind,
                    "tile": [int(tx), int(ty)],
                    "revision": int(revision),
                })
                return
            if self._revision.get(kind, 0) != revision:
                self.stale += 1; return
            key = (kind, tx, ty); self._results.pop(key, None); self._results[key] = result; self.completed += 1
            while len(self._results) > self.max_results: self._results.popitem(last=False)

    def cancel_kind(self, kind: str) -> int:
        target = str(kind)
        with self._lock:
            self._revision[target] = self._revision.get(target, 0) + 1
            removed = [key for key in self._results if key[0] == target]
            for key in removed: self._results.pop(key, None)
            return len(removed)

    def wait(self, timeout: float = 5.0) -> bool:
        with self._lock: pending = tuple(self._futures)
        if not pending: return True
        _done, unfinished = wait(pending, timeout=max(0.0, float(timeout)))
        return not unfinished

    def close(self) -> None:
        self._pool.shutdown(wait=True, cancel_futures=True)

    def telemetry(self) -> dict[str, Any]:
        with self._lock:
            return {"schema": "tigerstudio.painter.material-tile-executor.v1", "pending": len(self._futures), "submitted": self.submitted, "completed": self.completed, "stale": self.stale, "cancelled": self.cancelled, "failed": self.failed, "result_count": len(self._results), "max_results": self.max_results, "bounded": len(self._results) <= self.max_results, "revisions": dict(self._revision), "recent_errors": list(self._recent_errors), "error_capacity": self.error_capacity}


def measure_history_payload_bytes(value: Any, _seen: set[int] | None = None) -> int:
    """Measure owned logical history payload; this is not process RSS.

    Qt raster storage uses the binding's actual byte count. Python containers
    use CPython's reported shallow size plus recursively owned values. Shared
    references are counted once. No arbitrary unknown-object byte constant is
    used.
    """
    seen = _seen if _seen is not None else set()
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    shallow = int(sys.getsizeof(value, 0))
    if isinstance(value, QImage):
        return shallow + (0 if value.isNull() else int(value.sizeInBytes()))
    if isinstance(value, QPixmap):
        image = value.toImage()
        return shallow + (0 if image.isNull() else int(image.sizeInBytes()))
    if isinstance(value, dict):
        return shallow + sum(measure_history_payload_bytes(k, seen) + measure_history_payload_bytes(v, seen) for k, v in value.items())
    if isinstance(value, (list, tuple, set, frozenset, deque)):
        return shallow + sum(measure_history_payload_bytes(item, seen) for item in value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return shallow + sum(measure_history_payload_bytes(getattr(value, field.name), seen) for field in dataclasses.fields(value))
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return shallow + measure_history_payload_bytes(attributes, seen)
    return shallow


def estimate_history_bytes(value: Any, _seen: set[int] | None = None) -> int:
    """Compatibility alias for the v2 logical-payload measurement."""
    return measure_history_payload_bytes(value, _seen)


class UndoMemoryBudget:
    def __init__(self, budget_bytes: int = DEFAULT_UNDO_BUDGET_MB * 1024 * 1024) -> None:
        self.budget_bytes = max(1024 * 1024, int(budget_bytes)); self.evicted_states = 0; self.last_bytes = 0; self.last_count = 0

    def enforce(self, stack: list[Any], labels: list[str]) -> dict[str, Any]:
        sizes = [measure_history_payload_bytes(row) for row in stack]; total = sum(sizes)
        while total > self.budget_bytes and len(stack) > 1:
            stack.pop(0); sizes.pop(0); total = sum(sizes); self.evicted_states += 1
            if labels: labels.pop(0)
        self.last_bytes = total
        self.last_count = len(stack)
        return self.telemetry()

    def telemetry(self, count: int | None = None) -> dict[str, Any]:
        if count is None: count = self.last_count
        within = self.last_bytes <= self.budget_bytes
        return {"schema": "tigerstudio.painter.undo-payload-budget.v2", "bytes": self.last_bytes, "budget_bytes": self.budget_bytes, "accounting": "owned_logical_history_payload_bytes", "process_memory_claim": False, "state_count": int(count), "evicted_states": self.evicted_states, "within_budget": within, "oversize_single_state": bool(not within and int(count) == 1), "bounded": within or int(count) <= 1}


class LargeCanvasRuntime:
    def __init__(self, *, tile_size: int = DEFAULT_TILE_SIZE, tile_budget_mb: int = DEFAULT_TILE_BUDGET_MB, undo_budget_mb: int = DEFAULT_UNDO_BUDGET_MB, gpu_uploader=None, gpu_deleter=None) -> None:
        total_budget = max(3, int(tile_budget_mb)) * 1024 * 1024
        self.tiles = RetainedTileCache(tile_size=tile_size, budget_bytes=int(total_budget * 0.60), gpu_uploader=gpu_uploader, gpu_deleter=gpu_deleter)
        self.brush_stamps = RetainedTileCache(tile_size=tile_size, budget_bytes=int(total_budget * 0.10), gpu_uploader=gpu_uploader, gpu_deleter=gpu_deleter)
        self.material_maps = RetainedTileCache(tile_size=tile_size, budget_bytes=int(total_budget * 0.20), gpu_uploader=gpu_uploader, gpu_deleter=gpu_deleter)
        self.wet_canvas = RetainedTileCache(tile_size=tile_size, budget_bytes=int(total_budget * 0.10), gpu_uploader=gpu_uploader, gpu_deleter=gpu_deleter)
        self.material_tasks = DirtyMaterialTileQueue(); self.undo = UndoMemoryBudget(int(undo_budget_mb) * 1024 * 1024)
        self.material_executor = MaterialTileExecutor()
        self.last_update: dict[str, Any] = {}
        self.gpu_owner = gpu_uploader if hasattr(gpu_uploader, "telemetry") else getattr(gpu_uploader, "__self__", None)
        self.layer_signatures: dict[str, int] = {}
        self.display_render_calls = 0
        self.display_gpu_calls = 0
        self.display_cpu_tile_calls = 0
        self.display_source_fallbacks = 0
        self.last_display: dict[str, Any] = {}
        self.gpu_creation_error = ""
        self.gpu_cleanup_error = ""

    def update_layer(self, layer_id: str, image: QImage, *, dirty_rect=None, material: bool = False, wet: bool = False) -> dict[str, Any]:
        self.last_update = self.tiles.update_layer(layer_id, image, dirty_rect=dirty_rect)
        self.layer_signatures[str(layer_id)] = int(image.cacheKey())
        self._synchronize_gpu_fallback()
        coords = tile_coordinates(_rect(dirty_rect, image.width(), image.height()), image.width(), image.height(), self.tiles.tile_size)
        if material: self.material_tasks.schedule(("height", "normal", "ao"), coords)
        if wet:
            self.material_tasks.schedule(("wet_canvas",), coords)
            self.wet_canvas.update_layer(f"wet:{layer_id}", image, dirty_rect=dirty_rect)
            self._synchronize_gpu_fallback()
        return dict(self.last_update)

    def sync_layer_images(self, images: dict[str, QImage]) -> int:
        updated = 0
        for layer_id, image in dict(images or {}).items():
            if not isinstance(image, QImage) or image.isNull(): continue
            if self.layer_signatures.get(str(layer_id)) == int(image.cacheKey()): continue
            self.update_layer(str(layer_id), image); updated += 1
        removed = set(self.layer_signatures) - {str(key) for key in images}
        for layer_id in removed:
            self.layer_signatures.pop(layer_id, None); self.tiles.remove_layer(layer_id)
        return updated

    def cache_brush_stamp(self, stamp_id: str, image: QImage) -> dict[str, Any]:
        report = self.brush_stamps.update_layer(f"stamp:{stamp_id}", image); self._synchronize_gpu_fallback(); return report

    def update_material_map(self, kind: str, image: QImage, *, dirty_rect=None) -> dict[str, Any]:
        report = self.material_maps.update_layer(f"map:{kind}", image, dirty_rect=dirty_rect)
        coords = tile_coordinates(_rect(dirty_rect, image.width(), image.height()), image.width(), image.height(), self.material_maps.tile_size)
        report["executor"] = self.material_executor.submit_image(str(kind), image, coords, self.material_maps.tile_size)
        self._synchronize_gpu_fallback(); return report

    def close(self) -> None:
        self.material_executor.close()
        owner = self.gpu_owner
        self.gpu_owner = None
        for cache in (self.tiles, self.brush_stamps, self.material_maps, self.wet_canvas):
            cache.gpu_uploader = None
            cache.invalidate_gpu_handles()
        if owner is not None and hasattr(owner, "close"):
            try:
                owner.close()
            except Exception as exc:
                self.gpu_cleanup_error = f"{type(exc).__name__}: {exc}"

    def render_layer_image(self, layer_id: str, source: QImage) -> QImage:
        """Return the display image from retained tiles only when coverage is complete."""
        target = str(layer_id)
        self.display_render_calls += 1
        if not self.tiles.layer_complete(target):
            self.display_source_fallbacks += 1
            self.last_display = {
                "layer_id": target,
                "backend": "source_qimage_incomplete_tile_cache",
                "complete_tiles": False,
            }
            return QImage(source)
        records = self.tiles.layer_records(target)
        self.tiles.display_reads += len(records)
        if self.gpu_owner is not None and hasattr(self.gpu_owner, "composite_tile_records"):
            try:
                image, report = self.gpu_owner.composite_tile_records(
                    records, source.width(), source.height(), self.tiles.tile_size,
                )
                if (
                    not isinstance(image, QImage)
                    or image.isNull()
                    or image.width() != source.width()
                    or image.height() != source.height()
                ):
                    raise RuntimeError(
                        "retained GL tile compositor returned an invalid image"
                    )
                if not isinstance(report, dict) or not str(report.get("renderer") or ""):
                    raise RuntimeError(
                        "retained GL tile compositor returned an invalid report"
                    )
                self.display_gpu_calls += 1
                self.last_display = {
                    "layer_id": target,
                    "backend": "retained_gl_tile_display_readback",
                    "complete_tiles": True,
                    **dict(report or {}),
                }
                return image
            except Exception as exc:
                self.tiles.gpu_failures += 1
                self.tiles.last_gpu_error = f"{type(exc).__name__}: {exc}"
                self.tiles.gpu_uploader = None
                self._synchronize_gpu_fallback()
                fallback_reason = f"{type(exc).__name__}: {exc}"
        else:
            fallback_reason = "retained GL tile compositor unavailable"
        self.display_cpu_tile_calls += 1
        image = self.tiles.reconstruct(target)
        self.last_display = {
            "layer_id": target,
            "backend": "retained_qimage_tile_display",
            "complete_tiles": True,
            "fallback_reason": fallback_reason,
        }
        return image

    def render_layer_images(self, images: dict[str, QImage]) -> dict[str, QImage]:
        return {
            str(layer_id): self.render_layer_image(str(layer_id), image)
            for layer_id, image in dict(images or {}).items()
            if isinstance(image, QImage) and not image.isNull()
        }

    def budget_plan(self, width: int, height: int, layer_count: int) -> dict[str, Any]:
        width = max(1, int(width)); height = max(1, int(height)); layers = max(0, int(layer_count))
        required = width * height * 4 * layers
        configured = int(self.tiles.budget_bytes)
        minimum_total = int(math.ceil(required / 0.60)) if required else 0
        return {
            "schema": "tigerstudio.painter.large-canvas-budget-plan.v1",
            "canvas": [width, height], "raster_layer_count": layers,
            "required_main_tile_bytes": required,
            "configured_main_tile_bytes": configured,
            "full_layer_coverage_possible": required <= configured,
            "minimum_total_tile_budget_bytes_for_full_coverage": minimum_total,
            "minimum_total_tile_budget_mb_for_full_coverage": int(math.ceil(minimum_total / (1024 * 1024))) if minimum_total else 0,
            "fallback_when_incomplete": "source_qimage_incomplete_tile_cache",
            "formula": "width*height*4*raster_layers / main_cache_share_0.60",
            "performance_threshold_claim": False,
        }

    def composite_normal_layers(self, layers: list[tuple[QImage, float]], width: int, height: int) -> tuple[QImage, dict[str, Any]]:
        if self.gpu_owner is not None and hasattr(self.gpu_owner, "composite_normal_layers"):
            try:
                image, report = self.gpu_owner.composite_normal_layers(layers, width, height)
                if (
                    not isinstance(image, QImage)
                    or image.isNull()
                    or image.width() != max(1, int(width))
                    or image.height() != max(1, int(height))
                ):
                    raise RuntimeError(
                        "retained GL normal compositor returned an invalid image"
                    )
                if not isinstance(report, dict) or not str(report.get("renderer") or ""):
                    raise RuntimeError(
                        "retained GL normal compositor returned an invalid report"
                    )
                return image, report
            except Exception as exc:
                self.tiles.gpu_failures += 1
                self.tiles.last_gpu_error = f"{type(exc).__name__}: {exc}"
                self.tiles.gpu_uploader = None; self._synchronize_gpu_fallback()
                fallback_reason = f"{type(exc).__name__}: {exc}"
        else:
            fallback_reason = "retained GL compositor unavailable"
        from PySide6.QtGui import QPainter
        result = QImage(max(1, int(width)), max(1, int(height)), QImage.Format.Format_ARGB32_Premultiplied); result.fill(0)
        painter = QPainter(result)
        for image, opacity in layers:
            painter.setOpacity(max(0.0, min(1.0, float(opacity)))); painter.drawImage(0, 0, image)
        painter.end()
        return result, {"renderer": "painter_qpainter_normal_compositor_v1", "fallback": True, "reason": fallback_reason, "mask_policy": "preapplied_alpha", "remote_safe": True}

    def _synchronize_gpu_fallback(self) -> None:
        caches = (self.tiles, self.brush_stamps, self.material_maps, self.wet_canvas)
        if any(cache.gpu_failures and cache.gpu_uploader is None for cache in caches):
            for cache in caches:
                cache.gpu_uploader = None; cache.invalidate_gpu_handles()
            failed_owner = self.gpu_owner; self.gpu_owner = None
            if failed_owner is not None and hasattr(failed_owner, "close"):
                try:
                    failed_owner.close()
                except Exception as exc:
                    self.gpu_cleanup_error = f"{type(exc).__name__}: {exc}"

    def telemetry(self) -> dict[str, Any]:
        gpu_status = (
            self.gpu_owner.telemetry()
            if self.gpu_owner is not None and hasattr(self.gpu_owner, "telemetry")
            else {"active": self.tiles.gpu_uploader is not None, "telemetry": "callback_only" if self.tiles.gpu_uploader is not None else "unavailable"}
        )
        return {"schema": "tigerstudio.painter.large-canvas.runtime.v1", "resource_policy_contract": dict(LARGE_CANVAS_RESOURCE_POLICY_CONTRACT), "tiles": self.tiles.telemetry(), "brush_stamp_atlas": self.brush_stamps.telemetry(), "material_map_tiles": self.material_maps.telemetry(), "wet_canvas_tiles": self.wet_canvas.telemetry(), "material_tasks": self.material_tasks.telemetry(), "material_executor": self.material_executor.telemetry(), "undo": self.undo.telemetry(), "last_update": dict(self.last_update), "display": {"render_calls": self.display_render_calls, "gpu_tile_calls": self.display_gpu_calls, "cpu_tile_calls": self.display_cpu_tile_calls, "source_fallbacks": self.display_source_fallbacks, "last": dict(self.last_display)}, "gpu": {**gpu_status, "creation_error": self.gpu_creation_error, "cleanup_error": self.gpu_cleanup_error}, "cpu_fallback": self.tiles.gpu_uploader is None, "compositor": {"gpu_normal_source_over": self.gpu_owner is not None and hasattr(self.gpu_owner, "composite_normal_layers"), "gpu_tile_display": self.gpu_owner is not None and hasattr(self.gpu_owner, "composite_tile_records"), "advanced_blend_and_mask": "qpainter_parity_fallback", "mask_policy": "preapplied_alpha", "silent_fallback": False}, "remote_safe": True}


__all__ = [
    "DEFAULT_TILE_SIZE", "DEFAULT_TILE_BUDGET_MB", "DEFAULT_UNDO_BUDGET_MB",
    "MIN_TILE_SIZE", "MAX_TILE_SIZE", "MIN_TILE_BUDGET_MB", "MAX_TILE_BUDGET_MB",
    "MIN_UNDO_BUDGET_MB", "MAX_UNDO_BUDGET_MB",
    "LARGE_CANVAS_RESOURCE_POLICY_CONTRACT", "RetainedTileCache",
    "DirtyMaterialTileQueue", "MaterialTileExecutor", "UndoMemoryBudget",
    "LargeCanvasRuntime", "tile_coordinates", "estimate_history_bytes",
    "measure_history_payload_bytes",
]
