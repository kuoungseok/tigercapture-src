"""Local BiRefNet and SAM 2 inference used by Motion image decomposition."""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .segmentation_setup import (
    BIREFNET_PROVIDER_ID,
    SAM2_PROVIDER_ID,
    provider_model_path,
    segmentation_provider_status,
)


_birefnet_model: Any = None
_sam2_model: Any = None
_sam2_processor: Any = None


def _device():
    import torch

    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _image_tensor(rgb, *, size: int = 1024):
    import numpy as np
    import torch
    import torch.nn.functional as functional

    tensor = torch.from_numpy(np.ascontiguousarray(rgb)).permute(2, 0, 1)
    tensor = tensor.to(dtype=torch.float32).unsqueeze(0) / 255.0
    tensor = functional.interpolate(
        tensor,
        size=(size, size),
        mode="bilinear",
        align_corners=False,
    )
    mean = torch.tensor((0.485, 0.456, 0.406), dtype=tensor.dtype).view(1, 3, 1, 1)
    std = torch.tensor((0.229, 0.224, 0.225), dtype=tensor.dtype).view(1, 3, 1, 1)
    return (tensor - mean) / std


def _load_birefnet():
    global _birefnet_model
    if _birefnet_model is not None:
        return _birefnet_model
    if not segmentation_provider_status(BIREFNET_PROVIDER_ID)["available"]:
        raise RuntimeError("BiRefNet Matting is not installed.")
    from transformers import AutoModelForImageSegmentation

    model = AutoModelForImageSegmentation.from_pretrained(
        str(provider_model_path(BIREFNET_PROVIDER_ID)),
        trust_remote_code=True,
        local_files_only=True,
    )
    model.to(_device())
    model.eval()
    _birefnet_model = model
    return model


def birefnet_alpha(rgb):
    """Return a full-resolution uint8 soft alpha matte."""
    import cv2
    import numpy as np
    import torch

    height, width = rgb.shape[:2]
    model = _load_birefnet()
    tensor = _image_tensor(rgb).to(_device())
    with torch.inference_mode():
        output = model(tensor)
    if isinstance(output, Mapping):
        logits = output.get("logits")
        output = logits if logits is not None else output.get("predicted_mask")
    elif isinstance(output, (tuple, list)):
        output = output[-1]
    if isinstance(output, (tuple, list)):
        output = output[-1]
    if output is None:
        raise RuntimeError("BiRefNet returned no alpha output.")
    matte = output.sigmoid().detach().float().cpu().squeeze().numpy()
    matte = cv2.resize(matte, (width, height), interpolation=cv2.INTER_CUBIC)
    return np.clip(matte * 255.0, 0, 255).astype(np.uint8)


def _load_sam2():
    global _sam2_model, _sam2_processor
    if _sam2_model is not None and _sam2_processor is not None:
        return _sam2_model, _sam2_processor
    if not segmentation_provider_status(SAM2_PROVIDER_ID)["available"]:
        raise RuntimeError("SAM 2 Assisted is not installed.")
    from transformers import Sam2Model, Sam2Processor

    path = str(provider_model_path(SAM2_PROVIDER_ID))
    processor = Sam2Processor.from_pretrained(path, local_files_only=True)
    model = Sam2Model.from_pretrained(path, local_files_only=True)
    model.to(_device())
    model.eval()
    _sam2_model = model
    _sam2_processor = processor
    return model, processor


def _pixel_bbox(
    bbox: Sequence[float],
    width: int,
    height: int,
) -> list[int]:
    x, y, box_width, box_height = [float(value) for value in bbox[:4]]
    if max(abs(x), abs(y), abs(box_width), abs(box_height)) <= 1.0:
        x *= width
        y *= height
        box_width *= width
        box_height *= height
    return [
        max(0, min(width - 1, int(round(x)))),
        max(0, min(height - 1, int(round(y)))),
        max(1, min(width, int(round(x + box_width)))),
        max(1, min(height, int(round(y + box_height)))),
    ]


def sam2_masks_from_hints(
    rgb,
    object_hints: Iterable[Mapping[str, Any] | Sequence[Any]],
) -> list[tuple[Any, float, dict[str, Any]]]:
    """Return one best full-resolution SAM 2 mask for each box hint."""
    import numpy as np
    import torch
    from PIL import Image

    model, processor = _load_sam2()
    height, width = rgb.shape[:2]
    rows: list[tuple[Any, float, dict[str, Any]]] = []
    image = Image.fromarray(rgb, "RGB")
    for index, raw in enumerate(object_hints):
        if isinstance(raw, Mapping):
            bbox = raw.get("bbox")
            metadata = dict(raw)
        else:
            bbox = raw
            metadata = {"id": f"object_{index + 1:02d}", "label": "subject"}
        if not isinstance(bbox, Sequence) or len(bbox) < 4:
            continue
        box = _pixel_bbox(bbox, width, height)
        inputs = processor(
            images=image,
            input_boxes=[[box]],
            return_tensors="pt",
        ).to(model.device)
        with torch.inference_mode():
            output = model(**inputs)
        masks = processor.post_process_masks(
            output.pred_masks.cpu(),
            inputs["original_sizes"],
        )[0]
        scores = output.iou_scores.detach().float().cpu().reshape(-1)
        flat_masks = masks.reshape(-1, height, width)
        best = int(torch.argmax(scores).item()) if len(scores) else 0
        mask = np.where(flat_masks[best].numpy() > 0, 255, 0).astype(np.uint8)
        score = float(scores[best].item()) if len(scores) else 0.7
        rows.append((mask, score, metadata))
    return rows


__all__ = ["birefnet_alpha", "sam2_masks_from_hints"]
