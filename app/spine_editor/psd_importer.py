"""PSD file importer — extracts layers as PIL images with metadata."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from PIL import Image


@dataclass
class LayerInfo:
    name: str
    image: Image.Image          # RGBA
    left: int                   # bounding box in PSD canvas space
    top: int
    right: int
    bottom: int
    visible: bool = True
    layer_id: int = -1

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def cx(self) -> float:
        return (self.left + self.right) / 2.0

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2.0


def import_psd(path: str) -> tuple[list[LayerInfo], int, int]:
    """
    Open a .psd file and return (layers, canvas_width, canvas_height).
    Only leaf layers with actual pixel data are returned.
    Groups are flattened (content merged at group level if no sub-layers detected).
    """
    from psd_tools import PSDImage
    psd = PSDImage.open(path)
    layers: list[LayerInfo] = []
    _collect_layers(psd, layers)
    return layers, psd.width, psd.height


def _collect_layers(node, out: list[LayerInfo]) -> None:
    """Recursively collect leaf pixel layers."""
    for layer in reversed(list(node)):  # bottom-to-top in PSD order → top-to-bottom
        if layer.is_group():
            _collect_layers(layer, out)
        else:
            try:
                img = layer.composite()
                if img is None:
                    continue
                # Ensure RGBA
                img = img.convert("RGBA")
                bbox = layer.bbox
                out.append(LayerInfo(
                    name=layer.name,
                    image=img,
                    left=bbox.x1,
                    top=bbox.y1,
                    right=bbox.x2,
                    bottom=bbox.y2,
                    visible=layer.visible,
                    layer_id=getattr(layer, 'layer_id', -1),
                ))
            except Exception:
                pass  # skip layers that can't be composited
