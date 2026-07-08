"""Registered depth providers for AR/PBR compositing.

The default provider remains deterministic and local so tests never depend on
large models. Production-quality depth can be enabled by pointing the ONNX
provider at a packaged monocular depth model.
"""
from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


DEPTH_PROVIDER_SCHEMA = "tigerstudio.depth.provider.v1"
DEFAULT_DEPTH_PROVIDER = "auto"
SYNTHETIC_LUMA_PROVIDER_ID = "synthetic_luma_depth"
ONNX_MONOCULAR_PROVIDER_ID = "onnx_monocular_depth"
EXTERNAL_SEQUENCE_PROVIDER_ID = "external_depth_sequence"
VIDEO_TEMPORAL_PROVIDER_ID = "video_temporal_depth"


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def frame_to_rgb_array(frame: Any):
    import numpy as np

    try:
        from PIL import Image

        if isinstance(frame, Image.Image):
            return np.asarray(frame.convert("RGB"), dtype=np.uint8)
    except Exception:
        pass
    arr = np.asarray(frame)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError("frame must be grayscale or RGB-like")
    arr = arr[:, :, :3]
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr


def normalize_depth_array(depth: Any):
    import numpy as np

    arr = np.asarray(depth, dtype=np.float32)
    arr = np.squeeze(arr)
    if arr.ndim == 3:
        # Common ONNX outputs are 1xHxW or HxWx1 after squeeze. If the model
        # emits several maps, the first one is the conservative choice.
        if arr.shape[-1] == 1:
            arr = arr[:, :, 0]
        else:
            arr = arr[0]
    if arr.ndim != 2 or arr.size <= 0:
        raise ValueError("depth output must be a 2D map")
    arr = np.nan_to_num(arr, nan=1.0, posinf=1.0, neginf=0.0).astype(np.float32)
    lo = float(arr.min())
    hi = float(arr.max())
    if hi > 1.5 or lo < -0.001:
        span = max(1.0e-6, hi - lo)
        arr = (arr - lo) / span
    return np.clip(arr, 0.0, 1.0).astype(np.float32)


def resize_depth_to_frame(depth: Any, width: int, height: int):
    import numpy as np

    arr = normalize_depth_array(depth)
    if arr.shape == (int(height), int(width)):
        return arr
    try:
        from PIL import Image

        return np.asarray(
            Image.fromarray(arr.astype(np.float32), mode="F").resize(
                (int(width), int(height)),
                Image.Resampling.BILINEAR,
            ),
            dtype=np.float32,
        )
    except Exception:
        y_idx = np.linspace(0, arr.shape[0] - 1, int(height)).astype(np.int32)
        x_idx = np.linspace(0, arr.shape[1] - 1, int(width)).astype(np.int32)
        return arr[y_idx][:, x_idx].astype(np.float32)


@dataclass(frozen=True)
class DepthProviderInfo:
    provider_id: str
    display_name: str
    available: bool
    metric: bool
    temporal: bool
    quality: str
    note: str
    model_path: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": DEPTH_PROVIDER_SCHEMA,
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "available": bool(self.available),
            "metric": bool(self.metric),
            "temporal": bool(self.temporal),
            "quality": self.quality,
            "note": self.note,
            "model_path": self.model_path,
        }


class DepthProvider:
    provider_id = ""
    display_name = ""
    metric = False
    temporal = False
    quality = "fallback"

    def info(self) -> DepthProviderInfo:
        return DepthProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            available=self.available(),
            metric=self.metric,
            temporal=self.temporal,
            quality=self.quality,
            note=self.note(),
            model_path=self.model_path(),
        )

    def available(self) -> bool:
        return True

    def model_path(self) -> str:
        return ""

    def note(self) -> str:
        return ""

    def estimate(
        self,
        frame: Any,
        *,
        source_id: str = "",
        time_ms: int = 0,
        options: Mapping[str, Any] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        raise NotImplementedError


class SyntheticLumaDepthProvider(DepthProvider):
    provider_id = SYNTHETIC_LUMA_PROVIDER_ID
    display_name = "Synthetic luma depth"
    metric = False
    temporal = False
    quality = "qa_fallback"

    def note(self) -> str:
        return "Deterministic QA fallback, not production monocular depth."

    def estimate(
        self,
        frame: Any,
        *,
        source_id: str = "",
        time_ms: int = 0,
        options: Mapping[str, Any] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        import numpy as np

        options = options or {}
        vertical_weight = float(options.get("vertical_weight", 0.7))
        rgb = frame_to_rgb_array(frame)
        h, w = rgb.shape[:2]
        luma = (
            rgb[..., 0].astype(np.float32) * 0.2126
            + rgb[..., 1].astype(np.float32) * 0.7152
            + rgb[..., 2].astype(np.float32) * 0.0722
        ) / 255.0
        y = np.linspace(1.0, 0.0, h, dtype=np.float32)[:, None]
        v = max(0.0, min(1.0, vertical_weight))
        depth = np.clip(y * v + luma * (1.0 - v), 0.0, 1.0).astype(np.float32)
        if depth.shape[1] == 1 and w > 1:
            depth = np.repeat(depth, w, axis=1)
        diagnostics = {
            "ok": True,
            "backend": self.provider_id,
            "provider_id": self.provider_id,
            "metric": False,
            "depth_source_id": str(source_id or ""),
            "time_ms": int(time_ms),
            "shape": [int(h), int(w)],
            "range": [float(depth.min()), float(depth.max())],
            "warnings": ["synthetic depth is for QA and placeholder previews only"],
        }
        return depth, diagnostics


class OnnxMonocularDepthProvider(DepthProvider):
    provider_id = ONNX_MONOCULAR_PROVIDER_ID
    display_name = "ONNX monocular depth"
    metric = False
    temporal = False
    quality = "production_candidate"

    def model_path(self) -> str:
        return str(os.environ.get("TIGERCAPTURE_DEPTH_ONNX_MODEL_PATH", "") or "")

    def available(self) -> bool:
        model_path = self.model_path()
        return bool(model_path) and Path(model_path).exists() and _module_available("onnxruntime")

    def note(self) -> str:
        if not _module_available("onnxruntime"):
            return "onnxruntime is not installed."
        if not self.model_path():
            return "Set TIGERCAPTURE_DEPTH_ONNX_MODEL_PATH to enable this provider."
        if not Path(self.model_path()).exists():
            return "Configured ONNX depth model file does not exist."
        return "Local ONNX monocular depth provider is available."

    @staticmethod
    def _input_hw(input_shape: list[Any] | tuple[Any, ...], fallback: tuple[int, int]) -> tuple[int, int]:
        h, w = fallback
        if len(input_shape) >= 4:
            raw_h, raw_w = input_shape[-2], input_shape[-1]
            if isinstance(raw_h, int) and raw_h > 0:
                h = int(raw_h)
            if isinstance(raw_w, int) and raw_w > 0:
                w = int(raw_w)
        return max(8, int(h)), max(8, int(w))

    def estimate(
        self,
        frame: Any,
        *,
        source_id: str = "",
        time_ms: int = 0,
        options: Mapping[str, Any] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        import numpy as np
        from PIL import Image
        import onnxruntime as ort

        del options
        if not self.available():
            raise RuntimeError(self.note())
        rgb = frame_to_rgb_array(frame)
        h, w = rgb.shape[:2]
        session = ort.InferenceSession(self.model_path(), providers=["CPUExecutionProvider"])
        input_meta = session.get_inputs()[0]
        input_name = input_meta.name
        target_h, target_w = self._input_hw(list(input_meta.shape or []), (h, w))
        image = Image.fromarray(rgb, "RGB").resize((target_w, target_h), Image.Resampling.BILINEAR)
        arr = np.asarray(image, dtype=np.float32) / 255.0
        tensor = np.transpose(arr, (2, 0, 1))[None, ...].astype(np.float32)
        raw = session.run(None, {input_name: tensor})[0]
        depth = resize_depth_to_frame(raw, w, h)
        diagnostics = {
            "ok": True,
            "backend": self.provider_id,
            "provider_id": self.provider_id,
            "metric": False,
            "depth_source_id": str(source_id or ""),
            "time_ms": int(time_ms),
            "shape": [int(h), int(w)],
            "model_path": self.model_path(),
            "input_shape": list(tensor.shape),
            "output_shape": list(np.asarray(raw).shape),
            "range": [float(depth.min()), float(depth.max())],
            "warnings": [],
        }
        return depth, diagnostics


class ExternalDepthSequenceProvider(DepthProvider):
    provider_id = EXTERNAL_SEQUENCE_PROVIDER_ID
    display_name = "External depth sequence"
    metric = False
    temporal = True
    quality = "production_input"

    def model_path(self) -> str:
        return str(os.environ.get("TIGERCAPTURE_DEPTH_SEQUENCE_DIR", "") or "")

    def available(self) -> bool:
        path = self.model_path()
        return bool(path) and Path(path).exists()

    def note(self) -> str:
        if not self.model_path():
            return "Set TIGERCAPTURE_DEPTH_SEQUENCE_DIR to a directory of .npy/.png depth maps."
        if not Path(self.model_path()).exists():
            return "Configured depth sequence directory does not exist."
        return "External depth sequence directory is available."

    def estimate(
        self,
        frame: Any,
        *,
        source_id: str = "",
        time_ms: int = 0,
        options: Mapping[str, Any] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        import numpy as np
        from PIL import Image

        del source_id
        rgb = frame_to_rgb_array(frame)
        h, w = rgb.shape[:2]
        options = options or {}
        folder = Path(str(options.get("sequence_dir") or self.model_path())).expanduser()
        candidates = [
            folder / f"{int(time_ms):010d}.npy",
            folder / f"{int(time_ms):010d}.png",
            folder / f"{int(time_ms):010d}.exr",
        ]
        chosen = next((path for path in candidates if path.exists()), None)
        if chosen is None:
            raise FileNotFoundError(f"no external depth frame for {int(time_ms)} ms")
        if chosen.suffix.lower() == ".npy":
            arr = np.load(chosen)
        else:
            arr = np.asarray(Image.open(chosen))
        depth = resize_depth_to_frame(arr, w, h)
        diagnostics = {
            "ok": True,
            "backend": self.provider_id,
            "provider_id": self.provider_id,
            "metric": False,
            "depth_source_id": str(options.get("depth_source_id") or ""),
            "time_ms": int(time_ms),
            "shape": [int(h), int(w)],
            "frame_path": str(chosen),
            "range": [float(depth.min()), float(depth.max())],
            "warnings": [],
        }
        return depth, diagnostics


class VideoTemporalDepthProvider(DepthProvider):
    provider_id = VIDEO_TEMPORAL_PROVIDER_ID
    display_name = "Video temporal depth"
    metric = False
    temporal = True
    quality = "stabilized_fallback"

    def available(self) -> bool:
        return True

    def note(self) -> str:
        return "Temporal stabilization wrapper around the best available local depth provider."

    def estimate(
        self,
        frame: Any,
        *,
        source_id: str = "",
        time_ms: int = 0,
        options: Mapping[str, Any] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        options = options or {}
        base_provider = str(options.get("base_provider") or DEFAULT_DEPTH_PROVIDER)
        if base_provider in {"", "auto", self.provider_id}:
            base_provider = ONNX_MONOCULAR_PROVIDER_ID if OnnxMonocularDepthProvider().available() else SYNTHETIC_LUMA_PROVIDER_ID
        depth, diagnostics = estimate_depth(
            frame,
            provider=base_provider,
            source_id=source_id,
            time_ms=time_ms,
            options=options,
        )
        previous_depth = options.get("previous_depth")
        if previous_depth is not None:
            try:
                from app.depth.temporal import stabilize_depth_frame

                depth, temporal_diag = stabilize_depth_frame(
                    depth,
                    previous_depth,
                    reference_frame=frame,
                    previous_reference_frame=options.get("previous_frame"),
                    settings=options,
                )
                diagnostics["temporal"] = temporal_diag
            except Exception as exc:
                diagnostics.setdefault("warnings", []).append(
                    f"temporal stabilization skipped: {type(exc).__name__}: {exc}"
                )
        diagnostics["backend"] = self.provider_id
        diagnostics["provider_id"] = self.provider_id
        diagnostics["base_provider_id"] = base_provider
        diagnostics["metric"] = False
        return depth, diagnostics


def registered_depth_providers() -> dict[str, DepthProvider]:
    providers: list[DepthProvider] = [
        SyntheticLumaDepthProvider(),
        OnnxMonocularDepthProvider(),
        ExternalDepthSequenceProvider(),
        VideoTemporalDepthProvider(),
    ]
    return {provider.provider_id: provider for provider in providers}


def depth_provider_status() -> dict[str, Any]:
    providers = registered_depth_providers()
    selected = select_depth_provider_id()
    return {
        "ok": True,
        "schema": "tigerstudio.depth.providers.status.v1",
        "cloud_enabled": False,
        "auto_download": False,
        "selected_provider": selected,
        "capabilities": {key: provider.info().as_dict() for key, provider in providers.items()},
    }


def select_depth_provider_id(preferred: str | None = None) -> str:
    requested = str(preferred or os.environ.get("TIGERCAPTURE_DEPTH_PROVIDER", DEFAULT_DEPTH_PROVIDER) or DEFAULT_DEPTH_PROVIDER)
    requested = requested.strip().casefold()
    aliases = {
        "synthetic": SYNTHETIC_LUMA_PROVIDER_ID,
        "luma": SYNTHETIC_LUMA_PROVIDER_ID,
        "fallback": SYNTHETIC_LUMA_PROVIDER_ID,
        "onnx": ONNX_MONOCULAR_PROVIDER_ID,
        "monocular": ONNX_MONOCULAR_PROVIDER_ID,
        "external": EXTERNAL_SEQUENCE_PROVIDER_ID,
        "sequence": EXTERNAL_SEQUENCE_PROVIDER_ID,
        "temporal": VIDEO_TEMPORAL_PROVIDER_ID,
        "video": VIDEO_TEMPORAL_PROVIDER_ID,
    }
    requested = aliases.get(requested, requested)
    providers = registered_depth_providers()
    if requested in providers and providers[requested].available():
        return requested
    if requested != DEFAULT_DEPTH_PROVIDER:
        return SYNTHETIC_LUMA_PROVIDER_ID
    for candidate in (ONNX_MONOCULAR_PROVIDER_ID, EXTERNAL_SEQUENCE_PROVIDER_ID):
        provider = providers.get(candidate)
        if provider is not None and provider.available():
            return candidate
    return SYNTHETIC_LUMA_PROVIDER_ID


def estimate_depth(
    frame: Any,
    *,
    provider: str | None = None,
    source_id: str = "",
    time_ms: int = 0,
    options: Mapping[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    providers = registered_depth_providers()
    selected = select_depth_provider_id(provider)
    depth_provider = providers[selected]
    try:
        return depth_provider.estimate(frame, source_id=source_id, time_ms=time_ms, options=options)
    except Exception as exc:
        if selected == SYNTHETIC_LUMA_PROVIDER_ID:
            raise
        fallback = providers[SYNTHETIC_LUMA_PROVIDER_ID]
        depth, diagnostics = fallback.estimate(frame, source_id=source_id, time_ms=time_ms, options=options)
        diagnostics["provider_fallback"] = {
            "requested_provider": selected,
            "reason": f"{type(exc).__name__}: {exc}",
        }
        diagnostics.setdefault("warnings", []).append(
            f"{selected} unavailable; used synthetic luma fallback"
        )
        return depth, diagnostics
