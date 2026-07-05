"""Spine software renderer — follows tileworks/spine-cython + kivy-garden/garden.spine spec.

RegionAttachment:
  1. Compute 4 corners in attachment local space (with attachment rotation/offset)
  2. Transform via bone 2x2 matrix + world pos → screen coords
  3. PIL Image.transform(QUAD) to warp texture into screen quad

MeshAttachment (weighted):
  Parse vertices as [count, bone_idx, lx, ly, weight, ...] per vertex
  weighted_world = sum(weight * (bone_matrix @ local + bone_world))
  Render each triangle via PIL affine warp

"""
from __future__ import annotations
import math
import logging
import numpy as np
from PIL import Image
from typing import Optional
from app.spine_editor.spine_data import SpineSkeleton, RegionAttachment

try:
    import cv2 as _cv2
except Exception:
    _cv2 = None

log = logging.getLogger("spine.renderer")
log.setLevel(logging.WARNING)
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[spine] %(message)s"))
    log.addHandler(_h)


def unpremultiply(img: Image.Image) -> Image.Image:
    """Convert premultiplied-alpha RGBA image to straight alpha."""
    import numpy as np
    arr = np.array(img, dtype=np.float32)
    a = arr[:, :, 3:4]
    mask = a > 0
    for c in range(3):
        arr[:, :, c] = np.where(mask[:, :, 0], arr[:, :, c] / (a[:, :, 0] / 255.0 + 1e-6), 0)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


def _atlas_rotation_degrees(value) -> int:
    if isinstance(value, bool):
        return 90 if value else 0
    try:
        return int(value) % 360
    except Exception:
        return 0


class SpineRenderer:
    def __init__(self, skeleton: SpineSkeleton,
                 atlas_regions: dict | None = None,
                 textures=None,
                 pma: bool = False):
        self.skeleton = skeleton
        self.atlas = atlas_regions or {}
        if textures is None:
            self.textures: list[Optional[Image.Image]] = []
        elif isinstance(textures, list):
            self.textures = textures
        else:
            self.textures = [textures]
        if pma:
            self.textures = [unpremultiply(t) if t is not None else None
                             for t in self.textures]
        self.active_skin: str = "default"

    def _mesh_weights_for(self, slot_name: str, attachment_name: str,
                          attach: RegionAttachment) -> list:
        weights = getattr(attach, "mesh_weights", []) or []
        deforms = getattr(self.skeleton, "active_deforms", {}) or {}
        deform = (
            deforms.get((slot_name, attachment_name))
            or deforms.get((slot_name, attach.name))
        )
        if not deform:
            return weights
        is_weighted = any(
            bone_idx >= 0
            for vtx_bones in weights
            for bone_idx, _lx, _ly, _weight in vtx_bones
        )
        if is_weighted:
            influence_index = 0
            deformed_weights = []
            for vtx_bones in weights:
                deformed_vertex = []
                for bone_idx, lx, ly, weight in vtx_bones:
                    j = influence_index * 2
                    dx = float(deform[j]) if j < len(deform) else 0.0
                    dy = float(deform[j + 1]) if j + 1 < len(deform) else 0.0
                    deformed_vertex.append((bone_idx, lx + dx, ly + dy, weight))
                    influence_index += 1
                deformed_weights.append(deformed_vertex)
            return deformed_weights
        if len(deform) < len(weights) * 2:
            return weights
        for vtx_bones in weights:
            if len(vtx_bones) != 1:
                return weights
            bone_idx, _lx, _ly, weight = vtx_bones[0]
            if bone_idx >= 0 or abs(weight - 1.0) > 1e-5:
                return weights
        return [
            [(-1, float(deform[i * 2]), float(deform[i * 2 + 1]), 1.0)]
            for i in range(len(weights))
        ]

    def visual_bounds(self, skin_name: str = "default") -> tuple[float, float, float, float] | None:
        """Return approximate world-space bounds for visible slot attachments."""
        self.skeleton.update_world_transforms()
        resolved_skin = skin_name or self.active_skin
        merged: dict = {}
        for sn, atts in self.skeleton.skins.get("default", {}).items():
            merged[sn] = dict(atts)
        for sn, atts in self.skeleton.skins.get(resolved_skin, {}).items():
            merged.setdefault(sn, {}).update(atts)

        xs: list[float] = []
        ys: list[float] = []
        for slot in self.skeleton.slots:
            if not slot.attachment:
                continue
            bone = self.skeleton.bone(slot.bone)
            if bone is None:
                continue
            attach = merged.get(slot.name, {}).get(slot.attachment)
            if not isinstance(attach, RegionAttachment):
                continue
            if getattr(attach, "_non_visual", False):
                continue

            weights = self._mesh_weights_for(slot.name, slot.attachment, attach)
            if weights:
                for vtx_bones in weights:
                    wx_sum = wy_sum = 0.0
                    for bone_idx, lx, ly, weight in vtx_bones:
                        if bone_idx < 0:
                            b = bone
                        elif bone_idx < len(self.skeleton.bones):
                            b = self.skeleton.bones[bone_idx]
                        else:
                            b = bone
                        wx = lx * b.m00 + ly * b.m01 + b.world_x
                        wy = lx * b.m10 + ly * b.m11 + b.world_y
                        wx_sum += wx * weight
                        wy_sum += wy * weight
                    xs.append(wx_sum)
                    ys.append(wy_sum)
                continue

            region_name = attach.path or attach.name
            entry = self.atlas.get(region_name)
            if entry and len(entry) >= 5:
                aw, ah = float(entry[3]), float(entry[4])
            else:
                aw, ah = float(attach.width), float(attach.height)
            aw = max(1.0, aw * float(getattr(attach, "scale_x", 1.0)))
            ah = max(1.0, ah * float(getattr(attach, "scale_y", 1.0)))
            hw, hh = aw / 2.0, ah / 2.0

            r = math.radians(float(getattr(attach, "rotation", 0.0)))
            cr, sr = math.cos(r), math.sin(r)
            ax = float(getattr(attach, "x", 0.0))
            ay = float(getattr(attach, "y", 0.0))
            for lx, ly in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
                rx = lx * cr - ly * sr + ax
                ry = lx * sr + ly * cr + ay
                xs.append(rx * bone.m00 + ry * bone.m01 + bone.world_x)
                ys.append(rx * bone.m10 + ry * bone.m11 + bone.world_y)

        if not xs or not ys:
            return None
        return min(xs), min(ys), max(xs), max(ys)

    # ── atlas lookup ──────────────────────────────────────────────────────

    def _get_region_img(self, region_name: str,
                        skin_name: str = "") -> Optional[Image.Image]:
        skin_base = skin_name.rsplit("/", 1)[-1] if skin_name else ""
        entry = (
            self.atlas.get(region_name)
            or (self.atlas.get(f"{skin_name}/{region_name}") if skin_name else None)
            or (self.atlas.get(f"{skin_base}/{region_name}") if skin_base and skin_base != skin_name else None)
            or self.atlas.get(f"common/{region_name}")
        )
        if entry is None:
            return None
        # entry format: (page_idx, x, y, w, h) or (page_idx, x, y, w, h, rotate)
        if len(entry) >= 6:
            page_idx, rx, ry, rw, rh, rotate = entry[0], entry[1], entry[2], entry[3], entry[4], entry[5]
            orig_w = entry[6] if len(entry) > 6 else rw
            orig_h = entry[7] if len(entry) > 7 else rh
            off_x = entry[8] if len(entry) > 8 else 0
            off_y = entry[9] if len(entry) > 9 else 0
            stored_w = entry[10] if len(entry) > 10 else None
            stored_h = entry[11] if len(entry) > 11 else None
        elif len(entry) == 5:
            page_idx, rx, ry, rw, rh = entry
            rotate = False
            orig_w, orig_h, off_x, off_y = rw, rh, 0, 0
            stored_w = stored_h = None
        else:
            page_idx, rx, ry, rw, rh = 0, *entry
            rotate = False
            orig_w, orig_h, off_x, off_y = rw, rh, 0, 0
            stored_w = stored_h = None
        if page_idx >= len(self.textures) or self.textures[page_idx] is None:
            return None
        tex = self.textures[page_idx]
        tw, th = tex.size
        # For rotated regions, the atlas stores the image transposed:
        # natural (w,h) is stored as (h,w) in the atlas.
        rotation = _atlas_rotation_degrees(rotate)
        if stored_w is None or stored_h is None:
            if rotation in (90, 270):
                stored_w, stored_h = rh, rw
            else:
                stored_w, stored_h = rw, rh
        rx2 = min(rx + int(stored_w), tw)
        ry2 = min(ry + int(stored_h), th)
        if rx2 <= rx or ry2 <= ry:
            return None
        img = tex.crop((rx, ry, rx2, ry2))
        # Rotate stored CW-90° back to natural orientation
        if rotation == 90:
            img = img.rotate(-90, expand=True)
        elif rotation == 180:
            img = img.rotate(180, expand=True)
        elif rotation == 270:
            img = img.rotate(90, expand=True)
        if orig_w != img.width or orig_h != img.height or off_x or off_y:
            restored = Image.new(
                "RGBA",
                (max(1, int(orig_w)), max(1, int(orig_h))),
                (0, 0, 0, 0),
            )
            paste_x = int(off_x)
            paste_y = int(orig_h - off_y - img.height)
            restored.alpha_composite(img, (paste_x, paste_y))
            pad = 2
            right = paste_x + img.width
            bottom = paste_y + img.height
            if paste_x > 0:
                col = img.crop((0, 0, 1, img.height)).resize((min(pad, paste_x), img.height))
                restored.alpha_composite(col, (paste_x - col.width, paste_y))
            if right < restored.width:
                col = img.crop((img.width - 1, 0, img.width, img.height)).resize((min(pad, restored.width - right), img.height))
                restored.alpha_composite(col, (right, paste_y))
            if paste_y > 0:
                row = img.crop((0, 0, img.width, 1)).resize((img.width, min(pad, paste_y)))
                restored.alpha_composite(row, (paste_x, paste_y - row.height))
            if bottom < restored.height:
                row = img.crop((0, img.height - 1, img.width, img.height)).resize((img.width, min(pad, restored.height - bottom)))
                restored.alpha_composite(row, (paste_x, bottom))
            img = restored
        return img

    # ── main render ───────────────────────────────────────────────────────

    @staticmethod
    def _alpha_composite_clipped(
        canvas: Image.Image,
        patch: Image.Image,
        x: int | float,
        y: int | float,
    ) -> bool:
        """Composite ``patch`` even when its destination is partly off-canvas."""
        try:
            px = int(round(float(x)))
            py = int(round(float(y)))
            cw, ch = canvas.size
            pw, ph = patch.size
            if pw <= 0 or ph <= 0 or cw <= 0 or ch <= 0:
                return False
            dx0 = max(0, px)
            dy0 = max(0, py)
            dx1 = min(cw, px + pw)
            dy1 = min(ch, py + ph)
            if dx0 >= dx1 or dy0 >= dy1:
                return False
            if dx0 != px or dy0 != py or dx1 != px + pw or dy1 != py + ph:
                patch = patch.crop((dx0 - px, dy0 - py, dx1 - px, dy1 - py))
            canvas.alpha_composite(patch, (dx0, dy0))
            return True
        except Exception:
            return False

    @staticmethod
    def _composite_resized_bbox(
        canvas: Image.Image,
        src: Image.Image,
        x: int | float,
        y: int | float,
        width: int | float,
        height: int | float,
        resample,
    ) -> bool:
        """Resize a source into a destination bbox, clipping before allocation.

        Large Spine meshes and background plates can extend outside the current
        preview frame when the user scales or drags them.  Resizing the full
        off-screen bbox is slow, and ``alpha_composite`` rejects negative
        destinations, so render only the visible destination slice.
        """
        try:
            px = float(x)
            py = float(y)
            bw = float(width)
            bh = float(height)
            if bw <= 0 or bh <= 0:
                return False
            cw, ch = canvas.size
            dx0 = max(0, int(math.floor(px)))
            dy0 = max(0, int(math.floor(py)))
            dx1 = min(cw, int(math.ceil(px + bw)))
            dy1 = min(ch, int(math.ceil(py + bh)))
            if dx0 >= dx1 or dy0 >= dy1:
                return False

            sw, sh = src.size
            sx0 = max(0.0, min(float(sw), (dx0 - px) / bw * sw))
            sy0 = max(0.0, min(float(sh), (dy0 - py) / bh * sh))
            sx1 = max(0.0, min(float(sw), (dx1 - px) / bw * sw))
            sy1 = max(0.0, min(float(sh), (dy1 - py) / bh * sh))
            if sx1 <= sx0 or sy1 <= sy0:
                return False
            crop = src.crop((
                int(math.floor(sx0)),
                int(math.floor(sy0)),
                max(int(math.ceil(sx1)), int(math.floor(sx0)) + 1),
                max(int(math.ceil(sy1)), int(math.floor(sy0)) + 1),
            ))
            patch = crop.resize((dx1 - dx0, dy1 - dy0), resample)
            canvas.alpha_composite(patch, (dx0, dy0))
            return True
        except Exception:
            return False

    def render(self, width: int, height: int,
               scale: float = 1.0,
               anim_name: str | None = None,
               time: float = 0.0,
               skin_name: str = "default",
               offset_x: float = 0.0,
               offset_y: float = 0.0) -> Image.Image:
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        # canvas origin (world 0,0 → screen here)
        cx = width / 2 + offset_x
        cy = height / 2 - offset_y  # Y-up → Y-down flip

        if anim_name:
            anim = self.skeleton.animations.get(anim_name)
            if anim:
                self.skeleton.apply_animation(anim, time)

        resolved_skin = skin_name or self.active_skin
        # Merge default + selected skin
        merged: dict = {}
        for sn, atts in self.skeleton.skins.get("default", {}).items():
            merged[sn] = dict(atts)
        for sn, atts in self.skeleton.skins.get(resolved_skin, {}).items():
            merged.setdefault(sn, {}).update(atts)

        for slot in self.skeleton.slots:
            if not slot.attachment:
                continue
            bone = self.skeleton.bone(slot.bone)
            if bone is None:
                continue
            attach = merged.get(slot.name, {}).get(slot.attachment)
            if not isinstance(attach, RegionAttachment):
                continue
            if getattr(attach, "_non_visual", False):
                continue

            region_img = self._get_region_img(attach.path or attach.name, resolved_skin)
            if region_img is None:
                self._draw_placeholder(canvas, bone, attach, cx, cy, scale)
                continue

            weights = self._mesh_weights_for(slot.name, slot.attachment, attach)
            if weights:
                self._render_mesh(canvas, region_img, bone, attach, weights,
                                  cx, cy, scale, resolved_skin)
            else:
                self._render_region(canvas, region_img, bone, attach, cx, cy, scale)

        return canvas

    # ── region attachment ─────────────────────────────────────────────────

    def _compute_region_corners(self, bone, attach: RegionAttachment,
                                 cx: float, cy: float, scale: float
                                 ) -> list[tuple[float, float]]:
        """Compute 4 world screen positions of the attachment corners.
        Follows spine-cython regionattachment: local corners → attach rotation →
        bone 2x2 matrix → screen (with Y flip and zoom).
        Returns [(sx,sy), ...] TL, TR, BR, BL order.
        """
        aw = attach.width * attach.scale_x / 2
        ah = attach.height * attach.scale_y / 2
        # 4 local corners (around attachment center = 0,0 before offset)
        local = [(-aw, -ah), (aw, -ah), (aw, ah), (-aw, ah)]

        r = math.radians(attach.rotation)
        cr, sr = math.cos(r), math.sin(r)
        ax, ay = attach.x, attach.y

        result = []
        for lx, ly in local:
            # Apply attachment rotation + offset (in bone local space)
            rx = lx * cr - ly * sr + ax
            ry = lx * sr + ly * cr + ay
            # Apply bone world matrix (m00,m01,m10,m11) + world pos → world coords
            wx = rx * bone.m00 + ry * bone.m01 + bone.world_x
            wy = rx * bone.m10 + ry * bone.m11 + bone.world_y
            # World → screen (zoom + Y flip)
            sx = cx + wx * scale
            sy = cy - wy * scale
            result.append((sx, sy))
        return result  # TL, TR, BR, BL

    def _render_region(self, canvas: Image.Image, src: Image.Image,
                       bone, attach: RegionAttachment,
                       cx: float, cy: float, scale: float) -> None:
        """Render region attachment using two UV-mapped triangles (TL-TR-BR + TL-BR-BL)."""
        corners = self._compute_region_corners(bone, attach, cx, cy, scale)
        sw, sh = src.size
        # Source UV corners: TL, TR, BR, BL
        uv = [(0, 0), (sw, 0), (sw, sh), (0, sh)]
        # Render as 2 triangles
        self._render_triangle(canvas, src,
                              [uv[0], uv[1], uv[2]],
                              [corners[0], corners[1], corners[2]])
        self._render_triangle(canvas, src,
                              [uv[0], uv[2], uv[3]],
                              [corners[0], corners[2], corners[3]])

    # ── mesh attachment ───────────────────────────────────────────────────

    def _render_mesh(self, canvas: Image.Image, src: Image.Image,
                     bone, attach: RegionAttachment,
                     weights: list,
                     cx: float, cy: float, scale: float,
                     skin_name: str = "") -> None:
        """Render mesh via UV-mapped triangles (per-triangle affine warp)."""
        bones = self.skeleton.bones
        uvs = getattr(attach, 'mesh_uvs', [])
        triangles = getattr(attach, 'mesh_triangles', [])

        # Compute world screen position for each vertex
        screen_verts = []
        for vtx_bones in weights:
            wx_sum = wy_sum = 0.0
            for bone_idx, lx, ly, weight in vtx_bones:
                # bone_idx == -1 → unweighted: transform by slot's own bone
                if bone_idx < 0:
                    b = bone
                elif bone_idx < len(bones):
                    b = bones[bone_idx]
                else:
                    b = bone
                wx_sum += (lx * b.m00 + ly * b.m01 + b.world_x) * weight
                wy_sum += (lx * b.m10 + ly * b.m11 + b.world_y) * weight
            screen_verts.append((cx + wx_sum * scale, cy - wy_sum * scale))

        if not screen_verts:
            return

        if getattr(self, "_fast_mesh_preview", False):
            xs = [v[0] for v in screen_verts]
            ys = [v[1] for v in screen_verts]
            sw2 = max(1, int(max(xs) - min(xs)))
            sh2 = max(1, int(max(ys) - min(ys)))
            if sw2 > 0 and sh2 > 0:
                self._composite_resized_bbox(
                    canvas,
                    src,
                    min(xs),
                    min(ys),
                    sw2,
                    sh2,
                    Image.Resampling.BILINEAR,
                )
            return

        # If triangles/uvs are missing, fall back to a simple bbox blit
        if not triangles or not uvs:
            xs = [v[0] for v in screen_verts]
            ys = [v[1] for v in screen_verts]
            sw2 = max(1, max(xs) - min(xs)); sh2 = max(1, max(ys) - min(ys))
            self._composite_resized_bbox(
                canvas,
                src,
                min(xs),
                min(ys),
                sw2,
                sh2,
                Image.Resampling.LANCZOS,
            )
            return

        # UV coords: [u0,v0, u1,v1, ...] → list of (u,v) in texture pixels
        sw, sh = src.size
        # Check if this region was stored rotated in atlas
        region_name = attach.path or attach.name
        skin_base = skin_name.rsplit("/", 1)[-1] if skin_name else ""
        entry = (self.atlas.get(region_name)
                 or (self.atlas.get(f"{skin_name}/{region_name}") if skin_name else None)
                 or (self.atlas.get(f"{skin_base}/{region_name}") if skin_base else None)
                 or self.atlas.get(f"common/{region_name}"))
        atlas_rotated = (entry[5] if entry and len(entry) >= 6 else False)
        # UV coords are in NATURAL image space (Spine spec).
        # After rotate(-90) the atlas crop is in natural orientation → use UVs directly.
        uv_pts = [(uvs[i*2]*sw, uvs[i*2+1]*sh) for i in range(len(uvs)//2)]
        src_arr = np.asarray(src, dtype=np.uint8)

        # Render each triangle
        n_tris = len(triangles) // 3
        for t in range(n_tris):
            i0 = triangles[t*3]
            i1 = triangles[t*3+1]
            i2 = triangles[t*3+2]
            if i0 >= len(screen_verts) or i1 >= len(screen_verts) or i2 >= len(screen_verts):
                continue
            if i0 >= len(uv_pts) or i1 >= len(uv_pts) or i2 >= len(uv_pts):
                continue
            self._render_triangle(canvas, src,
                                   [uv_pts[i0], uv_pts[i1], uv_pts[i2]],
                                   [screen_verts[i0], screen_verts[i1], screen_verts[i2]],
                                   src_arr=src_arr)

    @staticmethod
    def _render_triangle(canvas: Image.Image, src: Image.Image,
                         src_pts: list, dst_pts: list,
                         src_arr=None) -> None:
        """Render one UV-mapped triangle via barycentric interpolation (numpy).
        src_pts: [(u0,v0),(u1,v1),(u2,v2)] in source texture pixels
        dst_pts: [(x0,y0),(x1,y1),(x2,y2)] in canvas screen coords
        """
        import numpy as np

        # Bounding box of destination triangle
        xs = np.array([p[0] for p in dst_pts])
        ys = np.array([p[1] for p in dst_pts])
        full_x0, full_x1 = int(math.floor(float(xs.min()))), int(math.ceil(float(xs.max()))) + 1
        full_y0, full_y1 = int(math.floor(float(ys.min()))), int(math.ceil(float(ys.max()))) + 1
        if full_x1 <= full_x0 or full_y1 <= full_y0:
            return
        cw, ch = canvas.size
        x0i, x1i = max(0, full_x0), min(cw, full_x1)
        y0i, y1i = max(0, full_y0), min(ch, full_y1)
        bw, bh = x1i - x0i, y1i - y0i
        if bw <= 0 or bh <= 0:
            return

        if _cv2 is not None:
            try:
                src_np = (
                    np.asarray(src, dtype=np.uint8)
                    if src_arr is None
                    else src_arr.astype(np.uint8, copy=False)
                )
                src_tri = np.asarray(src_pts, dtype=np.float32)
                dst_tri = np.asarray(
                    [(x - x0i, y - y0i) for x, y in dst_pts],
                    dtype=np.float32,
                )
                matrix = _cv2.getAffineTransform(src_tri, dst_tri)
                warped = _cv2.warpAffine(
                    src_np,
                    matrix,
                    (bw, bh),
                    flags=_cv2.INTER_LINEAR,
                    borderMode=_cv2.BORDER_CONSTANT,
                    borderValue=(0, 0, 0, 0),
                )
                mask = np.zeros((bh, bw), dtype=np.uint8)
                _cv2.fillConvexPoly(
                    mask,
                    np.rint(dst_tri).astype(np.int32),
                    255,
                    lineType=_cv2.LINE_AA,
                )
                warped[:, :, 3] = (
                    warped[:, :, 3].astype(np.uint16)
                    * mask.astype(np.uint16)
                    // 255
                ).astype(np.uint8)
                patch = Image.fromarray(warped, "RGBA")
                SpineRenderer._alpha_composite_clipped(canvas, patch, x0i, y0i)
                return
            except Exception:
                pass

        # Grid of pixel centres in bounding box
        px = np.arange(x0i, x1i, dtype=np.float32)
        py = np.arange(y0i, y1i, dtype=np.float32)
        gx, gy = np.meshgrid(px, py)   # (bh, bw)

        # Barycentric coords: solve (gx,gy) = a*d0 + b*d1 + c*d2
        d0 = np.array(dst_pts[0], dtype=np.float64)
        d1 = np.array(dst_pts[1], dtype=np.float64)
        d2 = np.array(dst_pts[2], dtype=np.float64)

        denom = (d1[1]-d2[1])*(d0[0]-d2[0]) + (d2[0]-d1[0])*(d0[1]-d2[1])
        if abs(denom) < 1e-6:
            return

        gx_f = gx.astype(np.float64)
        gy_f = gy.astype(np.float64)

        w0 = ((d1[1]-d2[1])*(gx_f-d2[0]) + (d2[0]-d1[0])*(gy_f-d2[1])) / denom
        w1 = ((d2[1]-d0[1])*(gx_f-d2[0]) + (d0[0]-d2[0])*(gy_f-d2[1])) / denom
        w2 = 1.0 - w0 - w1

        # Pixels inside the triangle
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            return

        # Interpolate source UV coords
        s0 = np.array(src_pts[0], dtype=np.float64)
        s1 = np.array(src_pts[1], dtype=np.float64)
        s2 = np.array(src_pts[2], dtype=np.float64)

        src_u = w0 * s0[0] + w1 * s1[0] + w2 * s2[0]
        src_v = w0 * s0[1] + w1 * s1[1] + w2 * s2[1]

        # Bilinear sampling
        sw, sh = src.size
        if src_arr is None:
            src_arr = np.asarray(src, dtype=np.float32)  # (sh, sw, 4)
        dst_arr = np.zeros((bh, bw, 4), dtype=np.float32)

        # Clamp to valid range
        su = np.clip(src_u, 0, sw - 1)
        sv = np.clip(src_v, 0, sh - 1)
        u0 = np.floor(su).astype(np.int32)
        v0 = np.floor(sv).astype(np.int32)
        u1 = np.minimum(u0 + 1, sw - 1)
        v1 = np.minimum(v0 + 1, sh - 1)
        fu = (su - u0).astype(np.float32)
        fv = (sv - v0).astype(np.float32)

        mask = inside
        fu_m = fu[mask, np.newaxis]
        fv_m = fv[mask, np.newaxis]
        # 4-corner bilinear blend
        dst_arr[mask] = (
            src_arr[v0[mask], u0[mask]] * (1-fu_m) * (1-fv_m) +
            src_arr[v0[mask], u1[mask]] *    fu_m  * (1-fv_m) +
            src_arr[v1[mask], u0[mask]] * (1-fu_m) *    fv_m  +
            src_arr[v1[mask], u1[mask]] *    fu_m  *    fv_m
        )

        # Composite onto canvas
        patch = Image.fromarray(np.clip(dst_arr, 0, 255).astype(np.uint8), 'RGBA')
        SpineRenderer._alpha_composite_clipped(canvas, patch, x0i, y0i)

    # ── placeholder ───────────────────────────────────────────────────────

    def _draw_placeholder(self, canvas: Image.Image,
                          bone, attach: RegionAttachment,
                          cx: float, cy: float, scale: float) -> None:
        sw = max(1, int(abs(attach.width * scale)))
        sh = max(1, int(abs(attach.height * scale)))
        wx = cx + bone.world_x * scale
        wy = cy - bone.world_y * scale
        px = int(wx - sw / 2)
        py = int(wy - sh / 2)
        ph = Image.new("RGBA", (sw, sh), (60, 120, 220, 60))
        self._alpha_composite_clipped(canvas, ph, px, py)

    def get_skin_attachment(self, skin_name: str, slot_name: str,
                            attach_name: str) -> Optional[RegionAttachment]:
        skin = self.skeleton.skins.get(skin_name,
               self.skeleton.skins.get("default", {}))
        return skin.get(slot_name, {}).get(attach_name)
