"""Per-node masks for DaVinci-style local color grading.

Each ``NodeItem`` in the workbench can carry zero or more masks. When
the project player renders the active clip, every node's grade is
applied only **inside** the union of its masks (or everywhere when no
mask exists). This is what unlocks the canonical colourist workflow
"node 1 reds the lips, node 2 desaturates everything else".

Mask kinds shipped in this module:

- :class:`PowerWindow` — manually-drawn polygon (DaVinci's Window).
- :class:`HSLQualifier` — pixels matching an HSL range (DaVinci's
  Qualifier — "select all reds in this saturation band").
- :class:`MagicMask` — face / lip / eye / person via OpenCV cascades
  (low-rent fallback) or Mediapipe Face Mesh (when installed).
- :class:`MaskTracker` — wraps a Power Window with an OpenCV CSRT
  tracker so the polygon follows the object across frames.

Every mask exposes the same surface:

- ``evaluate(rgb, frame_idx)`` → ``H×W float32`` mask in ``[0, 1]``.
- ``to_dict()`` / ``from_dict(d)`` for round-tripping into
  ``track.node_graph_view_data`` along with the rest of the scene.

The renderer composes a node's masks via union (``max``) — same as a
DaVinci OR'd window stack. Each individual mask carries its own
``invert`` flag so the user can do "everything except the lips" with
one mask + invert toggle.

Mediapipe is an optional dependency. ``MagicMask`` lazily imports it
and falls back to a simpler cascade-based estimator when missing,
so the editor stays usable on machines without it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Public mask kinds — module-level constants so callers can switch on a
# string without importing the dataclasses.
# ---------------------------------------------------------------------------

KIND_POWER_WINDOW = "power_window"
KIND_HSL_QUALIFIER = "hsl_qualifier"
KIND_MAGIC_MASK = "magic_mask"
KIND_TRACKER = "tracker"   # tracker wraps another mask source
KIND_BITMAP = "bitmap"     # rotoscope (GrabCut / SAM) baked-in mask

ALL_KINDS = (
    KIND_POWER_WINDOW, KIND_HSL_QUALIFIER, KIND_MAGIC_MASK, KIND_TRACKER,
    KIND_BITMAP,
)


# ---------------------------------------------------------------------------
# Power Window (polygon)
# ---------------------------------------------------------------------------


@dataclass
class PowerWindow:
    """Polygon mask in normalised [0, 1] coordinates so the same
    points work at any output resolution.

    ``softness_norm`` is in fraction-of-min-dimension units (0.02 ≈
    2 % of the shorter frame edge) so the feather looks the same
    after a resize. Stored separately from ``points`` so the user
    can edit the polygon and the feather independently.
    """

    points: list[tuple[float, float]] = field(default_factory=list)
    softness_norm: float = 0.02
    invert: bool = False
    enabled: bool = True

    KIND = KIND_POWER_WINDOW

    def evaluate(self, rgb: np.ndarray, frame_idx: int = 0) -> np.ndarray:
        h, w = rgb.shape[:2]
        if not self.enabled or len(self.points) < 3:
            return np.ones((h, w), dtype=np.float32)
        try:
            import cv2
        except ImportError:
            return np.ones((h, w), dtype=np.float32)
        pts = np.array(
            [[int(round(x * w)), int(round(y * h))] for x, y in self.points],
            dtype=np.int32,
        )
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [pts], 255)
        soft_px = max(0.0, self.softness_norm) * min(w, h)
        if soft_px >= 1.0:
            ksize = max(3, int(soft_px) | 1)
            mask = cv2.GaussianBlur(mask, (ksize, ksize), soft_px / 2.0)
        m = mask.astype(np.float32) / 255.0
        if self.invert:
            m = 1.0 - m
        return m

    def to_dict(self) -> dict:
        return {
            "kind": self.KIND,
            "points": [list(p) for p in self.points],
            "softness_norm": float(self.softness_norm),
            "invert": bool(self.invert),
            "enabled": bool(self.enabled),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PowerWindow":
        return cls(
            points=[tuple(p) for p in d.get("points", [])],
            softness_norm=float(d.get("softness_norm", 0.02)),
            invert=bool(d.get("invert", False)),
            enabled=bool(d.get("enabled", True)),
        )


# ---------------------------------------------------------------------------
# HSL Qualifier (colour range)
# ---------------------------------------------------------------------------


@dataclass
class HSLQualifier:
    """Pixel-wise HSL range mask. ``h_min``/``h_max`` are in degrees
    [0, 360); ``s_*`` and ``l_*`` are in [0, 1]. Hue can wrap across
    0/360 — when ``h_min > h_max`` the range is interpreted as
    ``[h_min, 360) ∪ [0, h_max]``.

    ``softness`` controls a per-channel band edge feather (Gaussian
    of edge mask). ``denoise_radius`` runs a small morphological
    open + close to suppress speckle in noisy footage."""

    h_min: float = 0.0
    h_max: float = 360.0
    s_min: float = 0.0
    s_max: float = 1.0
    l_min: float = 0.0
    l_max: float = 1.0
    softness: float = 0.02
    denoise_radius: int = 0
    invert: bool = False
    enabled: bool = True

    KIND = KIND_HSL_QUALIFIER

    def evaluate(self, rgb: np.ndarray, frame_idx: int = 0) -> np.ndarray:
        h, w = rgb.shape[:2]
        if not self.enabled:
            return np.ones((h, w), dtype=np.float32)
        try:
            import cv2
        except ImportError:
            return np.ones((h, w), dtype=np.float32)

        # OpenCV BGR ordering — the rest of the pipeline keeps RGB,
        # so stay in RGB by using cvtColor with COLOR_RGB2HLS.
        hls = cv2.cvtColor(rgb, cv2.COLOR_RGB2HLS).astype(np.float32)
        H = hls[..., 0] * 2.0    # OpenCV H is [0, 179] → degrees [0, 360)
        L = hls[..., 1] / 255.0
        S = hls[..., 2] / 255.0

        if self.h_min <= self.h_max:
            in_h = (H >= self.h_min) & (H <= self.h_max)
        else:
            in_h = (H >= self.h_min) | (H <= self.h_max)
        in_s = (S >= self.s_min) & (S <= self.s_max)
        in_l = (L >= self.l_min) & (L <= self.l_max)
        m = (in_h & in_s & in_l).astype(np.float32)

        if self.denoise_radius > 0:
            r = self.denoise_radius
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r * 2 + 1, r * 2 + 1))
            m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)

        if self.softness > 0:
            soft_px = max(0.0, self.softness) * min(w, h)
            if soft_px >= 1.0:
                ksize = max(3, int(soft_px) | 1)
                m = cv2.GaussianBlur(m, (ksize, ksize), soft_px / 2.0)

        if self.invert:
            m = 1.0 - m
        return np.clip(m, 0.0, 1.0).astype(np.float32)

    def to_dict(self) -> dict:
        return {
            "kind": self.KIND,
            "h_min": float(self.h_min), "h_max": float(self.h_max),
            "s_min": float(self.s_min), "s_max": float(self.s_max),
            "l_min": float(self.l_min), "l_max": float(self.l_max),
            "softness": float(self.softness),
            "denoise_radius": int(self.denoise_radius),
            "invert": bool(self.invert),
            "enabled": bool(self.enabled),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "HSLQualifier":
        return cls(
            h_min=float(d.get("h_min", 0.0)), h_max=float(d.get("h_max", 360.0)),
            s_min=float(d.get("s_min", 0.0)), s_max=float(d.get("s_max", 1.0)),
            l_min=float(d.get("l_min", 0.0)), l_max=float(d.get("l_max", 1.0)),
            softness=float(d.get("softness", 0.02)),
            denoise_radius=int(d.get("denoise_radius", 0)),
            invert=bool(d.get("invert", False)),
            enabled=bool(d.get("enabled", True)),
        )


# ---------------------------------------------------------------------------
# Magic Mask (AI face/lip/eye via mediapipe with cascade fallback)
# ---------------------------------------------------------------------------

# Mediapipe Face Mesh landmark indices for the lip outline. Two rings
# (outer + inner) so we can produce a hollow lip mask later if we
# want a "fill the lipstick" look. For now we use the outer ring as
# a single closed polygon.
MEDIAPIPE_LIP_OUTER = [
    61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291,
    409, 270, 269, 267, 0, 37, 39, 40, 185, 61,
]
MEDIAPIPE_LEFT_EYE = [
    33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246, 33,
]
MEDIAPIPE_RIGHT_EYE = [
    362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398, 362,
]
MEDIAPIPE_FACE_OVAL = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379,
    378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127,
    162, 21, 54, 103, 67, 109, 10,
]


def _mediapipe_available() -> bool:
    try:
        import mediapipe  # noqa: F401
        return True
    except ImportError:
        return False


@dataclass
class MagicMask:
    """AI-driven mask. ``feature`` picks what to detect:

    - ``"lips"`` → red polygon around the mouth (Mediapipe ideal,
      cascade fallback estimates from face bbox proportions).
    - ``"face"`` → full face oval (Mediapipe) or face bbox (cascade).
    - ``"left_eye"`` / ``"right_eye"`` → eye polygon (Mediapipe only).
    - ``"person"`` → full-body silhouette (Mediapipe Selfie Seg).

    Each call evaluates *per-frame* — the underlying detector reads
    ``rgb`` directly. Detection results aren't cached to disk yet
    (the editor caches the most recent frame's mask via the
    NodeGraph thumbnail throttle so live UI stays smooth)."""

    feature: str = "lips"
    softness_norm: float = 0.015
    expand_norm: float = 0.0    # erode/dilate the polygon outward
    invert: bool = False
    enabled: bool = True

    KIND = KIND_MAGIC_MASK

    # Class-level lazily-cached detectors so we don't re-init mediapipe
    # / cascade on every frame.
    _mp_face_mesh = None
    _mp_selfie_seg = None
    _cv_face_cascade = None

    def evaluate(self, rgb: np.ndarray, frame_idx: int = 0) -> np.ndarray:
        h, w = rgb.shape[:2]
        if not self.enabled:
            return np.ones((h, w), dtype=np.float32)
        # Try mediapipe first — it gives precise polygon landmarks.
        if _mediapipe_available():
            try:
                m = self._evaluate_mediapipe(rgb)
                if m is not None:
                    return self._postprocess(m)
            except Exception:
                pass
        # Fallback: OpenCV face cascade → estimate region from bbox.
        try:
            m = self._evaluate_cascade(rgb)
            if m is not None:
                return self._postprocess(m)
        except Exception:
            pass
        return np.ones((h, w), dtype=np.float32)

    # ---- mediapipe path ----

    def _evaluate_mediapipe(self, rgb: np.ndarray) -> np.ndarray | None:
        h, w = rgb.shape[:2]
        if self.feature == "person":
            seg = self._get_mp_selfie()
            if seg is None:
                return None
            res = seg.process(rgb)
            if res.segmentation_mask is None:
                return None
            return res.segmentation_mask.astype(np.float32)

        mesh = self._get_mp_face_mesh()
        if mesh is None:
            return None
        res = mesh.process(rgb)
        if not getattr(res, "multi_face_landmarks", None):
            return None
        try:
            import cv2
        except ImportError:
            return None
        landmarks = res.multi_face_landmarks[0].landmark
        if self.feature == "lips":
            indices = MEDIAPIPE_LIP_OUTER
        elif self.feature == "left_eye":
            indices = MEDIAPIPE_LEFT_EYE
        elif self.feature == "right_eye":
            indices = MEDIAPIPE_RIGHT_EYE
        elif self.feature == "face":
            indices = MEDIAPIPE_FACE_OVAL
        else:
            indices = MEDIAPIPE_LIP_OUTER
        pts = np.array(
            [
                [int(round(landmarks[i].x * w)), int(round(landmarks[i].y * h))]
                for i in indices
            ],
            dtype=np.int32,
        )
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [pts], 255)
        return mask.astype(np.float32) / 255.0

    @classmethod
    def _get_mp_face_mesh(cls):
        if cls._mp_face_mesh is None:
            try:
                import mediapipe as mp
                cls._mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=True, max_num_faces=1,
                    refine_landmarks=False,
                )
            except Exception:
                return None
        return cls._mp_face_mesh

    @classmethod
    def _get_mp_selfie(cls):
        if cls._mp_selfie_seg is None:
            try:
                import mediapipe as mp
                cls._mp_selfie_seg = mp.solutions.selfie_segmentation.SelfieSegmentation(
                    model_selection=1,
                )
            except Exception:
                return None
        return cls._mp_selfie_seg

    # ---- cascade fallback ----

    def _evaluate_cascade(self, rgb: np.ndarray) -> np.ndarray | None:
        try:
            import cv2
        except ImportError:
            return None
        if MagicMask._cv_face_cascade is None:
            try:
                xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                MagicMask._cv_face_cascade = cv2.CascadeClassifier(xml)
            except Exception:
                return None
        cas = MagicMask._cv_face_cascade
        if cas is None or cas.empty():
            return None
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        faces = cas.detectMultiScale(gray, 1.2, 4, minSize=(40, 40))
        h, w = rgb.shape[:2]
        if len(faces) == 0:
            return np.zeros((h, w), dtype=np.float32)
        x, y, fw, fh = faces[0]
        mask = np.zeros((h, w), dtype=np.uint8)
        if self.feature == "face":
            cv2.ellipse(
                mask, (x + fw // 2, y + fh // 2), (fw // 2, fh // 2),
                0, 0, 360, 255, -1,
            )
        elif self.feature == "lips":
            # Lips are roughly at 70%–85% face height, central 50% width.
            mx = x + fw // 4
            my = y + int(fh * 0.65)
            mw = fw // 2
            mh = int(fh * 0.20)
            cv2.ellipse(
                mask, (mx + mw // 2, my + mh // 2), (mw // 2, mh // 2),
                0, 0, 360, 255, -1,
            )
        elif self.feature in ("left_eye", "right_eye"):
            ey = y + int(fh * 0.40)
            eh = int(fh * 0.10)
            ew = int(fw * 0.20)
            if self.feature == "left_eye":
                ex = x + int(fw * 0.20)
            else:
                ex = x + int(fw * 0.60)
            cv2.ellipse(
                mask, (ex + ew // 2, ey + eh // 2), (ew // 2, eh // 2),
                0, 0, 360, 255, -1,
            )
        else:
            # Person fallback ≈ face oval (we don't have a body model).
            cv2.ellipse(
                mask, (x + fw // 2, y + fh // 2), (fw // 2, fh // 2),
                0, 0, 360, 255, -1,
            )
        return mask.astype(np.float32) / 255.0

    # ---- common postprocess (expand + soften + invert) ----

    def _postprocess(self, m: np.ndarray) -> np.ndarray:
        try:
            import cv2
        except ImportError:
            return m
        h, w = m.shape[:2]
        if abs(self.expand_norm) > 1e-4:
            r = max(1, int(abs(self.expand_norm) * min(w, h)))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r * 2 + 1, r * 2 + 1))
            if self.expand_norm > 0:
                m = cv2.dilate(m, kernel)
            else:
                m = cv2.erode(m, kernel)
        if self.softness_norm > 0:
            soft_px = max(0.0, self.softness_norm) * min(w, h)
            if soft_px >= 1.0:
                ksize = max(3, int(soft_px) | 1)
                m = cv2.GaussianBlur(m, (ksize, ksize), soft_px / 2.0)
        if self.invert:
            m = 1.0 - m
        return np.clip(m, 0.0, 1.0).astype(np.float32)

    def to_dict(self) -> dict:
        return {
            "kind": self.KIND,
            "feature": str(self.feature),
            "softness_norm": float(self.softness_norm),
            "expand_norm": float(self.expand_norm),
            "invert": bool(self.invert),
            "enabled": bool(self.enabled),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MagicMask":
        return cls(
            feature=str(d.get("feature", "lips")),
            softness_norm=float(d.get("softness_norm", 0.015)),
            expand_norm=float(d.get("expand_norm", 0.0)),
            invert=bool(d.get("invert", False)),
            enabled=bool(d.get("enabled", True)),
        )


# ---------------------------------------------------------------------------
# Tracker — wraps a Power Window so it follows an object frame-to-frame
# ---------------------------------------------------------------------------


@dataclass
class MaskTracker:
    """OpenCV CSRT tracker that translates / scales a base polygon as
    the user scrubs through the clip. ``base_points`` is the polygon
    drawn at ``init_frame``; ``base_bbox`` is its axis-aligned bbox
    used to seed the tracker. The mask returned for any later frame
    is the polygon translated/scaled to follow the tracker's bbox.

    The tracker is initialised lazily on first evaluate() — that's
    when we have access to the first RGB frame. Subsequent frames
    update the bbox via ``tracker.update``.

    Tracking state is NOT persisted to disk (it depends on per-frame
    pixel data). Re-tracking happens automatically on project reload."""

    base_points: list[tuple[float, float]] = field(default_factory=list)
    base_bbox: tuple[float, float, float, float] | None = None
    init_frame: int = 0
    softness_norm: float = 0.02
    invert: bool = False
    enabled: bool = True

    KIND = KIND_TRACKER

    # Runtime-only state (not in to_dict).
    _tracker: Any = None
    _last_frame_idx: int = -1
    _last_bbox: tuple[float, float, float, float] | None = None

    def evaluate(self, rgb: np.ndarray, frame_idx: int = 0) -> np.ndarray:
        h, w = rgb.shape[:2]
        if not self.enabled or len(self.base_points) < 3 or self.base_bbox is None:
            return np.ones((h, w), dtype=np.float32)
        try:
            import cv2
        except ImportError:
            return np.ones((h, w), dtype=np.float32)
        # Init tracker on first call (or when scrubbing back to init).
        if self._tracker is None or frame_idx <= self.init_frame:
            try:
                if hasattr(cv2, "TrackerCSRT_create"):
                    self._tracker = cv2.TrackerCSRT_create()
                elif hasattr(cv2, "legacy"):
                    self._tracker = cv2.legacy.TrackerCSRT_create()
                else:
                    return np.ones((h, w), dtype=np.float32)
            except Exception:
                return np.ones((h, w), dtype=np.float32)
            bx, by, bw, bh = self.base_bbox
            init_bbox = (
                int(round(bx * w)), int(round(by * h)),
                int(round(bw * w)), int(round(bh * h)),
            )
            try:
                self._tracker.init(rgb, init_bbox)
            except Exception:
                self._tracker = None
                return np.ones((h, w), dtype=np.float32)
            self._last_frame_idx = frame_idx
            self._last_bbox = (bx, by, bw, bh)
        elif frame_idx != self._last_frame_idx:
            try:
                ok, box = self._tracker.update(rgb)
            except Exception:
                ok = False
                box = None
            if ok and box is not None:
                bx, by, bw, bh = box
                self._last_bbox = (bx / w, by / h, bw / w, bh / h)
            self._last_frame_idx = frame_idx

        if self._last_bbox is None:
            return np.ones((h, w), dtype=np.float32)
        bx, by, bw, bh = self._last_bbox
        obx, oby, obw, obh = self.base_bbox
        if obw <= 0 or obh <= 0:
            return np.ones((h, w), dtype=np.float32)
        # Map base polygon points (in normalised coords relative to
        # the base bbox) into the current bbox.
        moved = []
        for x, y in self.base_points:
            local_x = (x - obx) / obw
            local_y = (y - oby) / obh
            new_x = bx + local_x * bw
            new_y = by + local_y * bh
            moved.append((new_x, new_y))
        pts = np.array(
            [[int(round(x * w)), int(round(y * h))] for x, y in moved],
            dtype=np.int32,
        )
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [pts], 255)
        if self.softness_norm > 0:
            soft_px = max(0.0, self.softness_norm) * min(w, h)
            if soft_px >= 1.0:
                ksize = max(3, int(soft_px) | 1)
                mask = cv2.GaussianBlur(mask, (ksize, ksize), soft_px / 2.0)
        m = mask.astype(np.float32) / 255.0
        if self.invert:
            m = 1.0 - m
        return m

    def to_dict(self) -> dict:
        return {
            "kind": self.KIND,
            "base_points": [list(p) for p in self.base_points],
            "base_bbox": list(self.base_bbox) if self.base_bbox else None,
            "init_frame": int(self.init_frame),
            "softness_norm": float(self.softness_norm),
            "invert": bool(self.invert),
            "enabled": bool(self.enabled),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MaskTracker":
        bb = d.get("base_bbox")
        return cls(
            base_points=[tuple(p) for p in d.get("base_points", [])],
            base_bbox=tuple(bb) if bb else None,
            init_frame=int(d.get("init_frame", 0)),
            softness_norm=float(d.get("softness_norm", 0.02)),
            invert=bool(d.get("invert", False)),
            enabled=bool(d.get("enabled", True)),
        )


# ---------------------------------------------------------------------------
# BitmapMask — precomputed mask (rotoscope output: GrabCut / SAM)
# ---------------------------------------------------------------------------


@dataclass
class BitmapMask:
    """Pixel-precise mask baked from an interactive rotoscope tool
    (GrabCut, SAM, etc). Stored as a base64-encoded PNG so the mask
    survives project reload at full fidelity, and so the JSON dump
    stays compact relative to a raw float32 array.

    Evaluation:
      1. Decode PNG → uint8 H×W array.
      2. (Optional) feed first-frame bbox to a CSRT tracker and
         translate/scale the mask to follow the object on later
         frames. Stage 3 — opt-in via ``track_object`` flag.
      3. Resize to current frame size (linear, area-preserving).
      4. Apply softness (Gaussian) + invert.
    """

    encoded_png: str = ""    # base64 of PNG-encoded 8-bit mask
    base_width: int = 0      # source frame size when the mask was made
    base_height: int = 0
    softness_norm: float = 0.01
    invert: bool = False
    enabled: bool = True
    # Stage 3: when True, a cv2.TrackerCSRT follows the bbox of the
    # masked subject across frames. The mask shape stays the same
    # (we just translate / scale it to match the new bbox).
    track_object: bool = False
    init_frame: int = 0
    correction_bboxes: dict[int, tuple[float, float, float, float]] = field(default_factory=dict)
    tracking_cache_bboxes: dict[int, tuple[float, float, float, float]] = field(default_factory=dict)
    tracking_failed_frames: set[int] = field(default_factory=set)

    KIND = KIND_BITMAP

    # Lazy / runtime-only state — not in to_dict.
    _decoded: Any = None
    _tracker: Any = None
    _last_frame_idx: int = -1
    _last_bbox: tuple[float, float, float, float] | None = None
    _base_bbox: tuple[float, float, float, float] | None = None
    _track_cache: Any = None          # frame_idx -> pixel bbox (x, y, w, h)
    _failed_frames: Any = None        # set[int]
    _tracking_message: str = ""
    # Result cache — BitmapMask is static (same mask for every frame
    # when track_object=False). Resize + softness are deterministic
    # for a given output (h, w), so cache to avoid re-doing the same
    # expensive cv2.resize + GaussianBlur on every playback frame.
    # Cache is invalidated when the encoded_png changes (new mask).
    _cache: Any = None              # np.ndarray float32 H×W
    _cache_hw: tuple[int, int] = (-1, -1)

    def evaluate(self, rgb, frame_idx: int = 0):
        h, w = rgb.shape[:2]
        if not self.enabled or not self.encoded_png:
            return np.ones((h, w), dtype=np.float32)
        # Fast path: static (non-tracking) mask cached at this res.
        if (not self.track_object
                and self._cache is not None
                and self._cache_hw == (h, w)):
            return self._cache
        try:
            import cv2
        except ImportError:
            return np.ones((h, w), dtype=np.float32)
        if self._decoded is None:
            try:
                import base64
                raw = base64.b64decode(self.encoded_png)
                arr = np.frombuffer(raw, dtype=np.uint8)
                m = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
                if m is None:
                    return np.ones((h, w), dtype=np.float32)
                self._decoded = m
            except Exception:
                return np.ones((h, w), dtype=np.float32)
        m = self._decoded
        if m.shape[0] != h or m.shape[1] != w:
            m = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)

        # Stage 3: translate / scale the mask to follow the tracked
        # bbox if tracking is enabled. The base bbox is computed
        # lazily from the decoded mask on first evaluate().
        if self.track_object:
            try:
                m = self._track_and_warp(rgb, m, frame_idx)
            except Exception:
                pass

        mf = m.astype(np.float32) / 255.0
        if self.softness_norm > 0:
            soft_px = max(0.0, self.softness_norm) * min(w, h)
            if soft_px >= 1.0:
                ksize = max(3, int(soft_px) | 1)
                mf = cv2.GaussianBlur(mf, (ksize, ksize), soft_px / 2.0)
        if self.invert:
            mf = 1.0 - mf
        result = np.clip(mf, 0.0, 1.0).astype(np.float32)
        # Store in cache for repeated calls at the same (h, w).
        # Tracking masks are NOT cached since they change per-frame.
        if not self.track_object:
            self._cache = result
            self._cache_hw = (h, w)
        return result

    def _track_and_warp_legacy_unused(self, rgb, mask_uint8, frame_idx: int):
        """Run the bbox tracker; warp ``mask_uint8`` so the masked
        region matches the tracker's current position. Returns the
        warped uint8 mask. Falls back to the original mask on any
        tracker failure."""
        import cv2
        h, w = mask_uint8.shape[:2]
        # Compute the base bbox (tight rect around the foreground)
        # once so we have a stable reference to warp from.
        if self._base_bbox is None:
            ys, xs = np.where(mask_uint8 > 127)
            if xs.size == 0:
                return mask_uint8
            bx, by = int(xs.min()), int(ys.min())
            bw = int(xs.max() - bx + 1)
            bh = int(ys.max() - by + 1)
            self._base_bbox = (bx, by, bw, bh)

        # Init or re-init tracker when needed.
        need_init = (
            self._tracker is None or frame_idx <= self.init_frame
        )
        if need_init:
            try:
                if hasattr(cv2, "TrackerCSRT_create"):
                    self._tracker = cv2.TrackerCSRT_create()
                elif hasattr(cv2, "legacy"):
                    self._tracker = cv2.legacy.TrackerCSRT_create()
                else:
                    return mask_uint8
                self._tracker.init(rgb, self._base_bbox)
                self._last_bbox = self._base_bbox
                self._last_frame_idx = frame_idx
                return mask_uint8
            except Exception:
                self._tracker = None
                return mask_uint8

        if frame_idx == self._last_frame_idx:
            cur = self._last_bbox or self._base_bbox
        else:
            try:
                ok, box = self._tracker.update(rgb)
            except Exception:
                ok = False
                box = None
            if ok and box is not None:
                self._last_bbox = (float(box[0]), float(box[1]),
                                   float(box[2]), float(box[3]))
            cur = self._last_bbox or self._base_bbox
            self._last_frame_idx = frame_idx

        bx, by, bw, bh = cur
        obx, oby, obw, obh = self._base_bbox
        if obw <= 0 or obh <= 0:
            return mask_uint8
        # Affine warp: scale base→current bbox, translate.
        sx = bw / obw
        sy = bh / obh
        tx = bx - obx * sx
        ty = by - oby * sy
        M = np.array([[sx, 0.0, tx], [0.0, sy, ty]], dtype=np.float32)
        warped = cv2.warpAffine(
            mask_uint8, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        return warped

    def _track_and_warp(self, rgb, mask_uint8, frame_idx: int):
        """Track the selected region and warp the mask to a cached bbox."""
        import cv2
        h, w = mask_uint8.shape[:2]
        self._ensure_tracking_state()
        if self._base_bbox is None:
            self._base_bbox = self._bbox_from_mask(mask_uint8)
        if self._base_bbox is None:
            self._tracking_message = "empty mask"
            return mask_uint8

        corrected = self._correction_bbox_for_frame(frame_idx, w, h)
        if corrected is not None:
            self._cache_track_bbox(frame_idx, corrected)
            if int(frame_idx) in self.correction_bboxes:
                self._init_tracker(cv2, rgb, corrected, frame_idx)
                self._tracking_message = "correction keyframe"
            else:
                self._tracking_message = "interpolated correction"
            return self._warp_mask_to_bbox(mask_uint8, corrected)

        cached = self._track_cache.get(int(frame_idx))
        if cached is not None:
            self._tracking_message = "cached"
            return self._warp_mask_to_bbox(mask_uint8, cached)

        base_bbox = self._base_bbox
        if self._tracker is None:
            nearest = self._nearest_cached_bbox(frame_idx)
            init_bbox = nearest if nearest is not None else base_bbox
            if not self._init_tracker(cv2, rgb, init_bbox, frame_idx):
                self._tracking_message = "tracker unavailable"
                return self._warp_mask_to_bbox(mask_uint8, init_bbox)
            self._cache_track_bbox(frame_idx, init_bbox)
            self._tracking_message = "tracker initialized"
            return self._warp_mask_to_bbox(mask_uint8, init_bbox)

        gap = int(frame_idx) - int(self._last_frame_idx)
        if gap == 0 and self._last_bbox is not None:
            self._tracking_message = "cached current"
            return self._warp_mask_to_bbox(mask_uint8, self._last_bbox)
        if gap < 0 or gap > 5:
            nearest = self._nearest_cached_bbox(frame_idx)
            if nearest is not None:
                self._tracking_message = "nearest cached"
                return self._warp_mask_to_bbox(mask_uint8, nearest)
            self._tracking_message = "seek without cache"
            return self._warp_mask_to_bbox(mask_uint8, base_bbox)

        try:
            ok, box = self._tracker.update(rgb)
        except Exception:
            ok = False
            box = None
        if ok and box is not None:
            cur = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
            self._last_bbox = cur
            self._last_frame_idx = int(frame_idx)
            self._cache_track_bbox(frame_idx, cur)
            self._tracking_message = "tracked"
            return self._warp_mask_to_bbox(mask_uint8, cur)

        self._failed_frames.add(int(frame_idx))
        self.tracking_failed_frames.add(int(frame_idx))
        self._last_frame_idx = int(frame_idx)
        self._tracking_message = "tracking failed"
        fallback = self._last_bbox or self._nearest_cached_bbox(frame_idx) or base_bbox
        return self._warp_mask_to_bbox(mask_uint8, fallback)

    def _ensure_tracking_state(self) -> None:
        if self._track_cache is None:
            self._track_cache = {}
            if self.tracking_cache_bboxes:
                bw = int(self.base_width) if self.base_width > 0 else 1
                bh = int(self.base_height) if self.base_height > 0 else 1
                for frame_idx, bbox in self.tracking_cache_bboxes.items():
                    try:
                        self._track_cache[int(frame_idx)] = self._bbox_from_norm(bbox, bw, bh)
                    except Exception:
                        pass
        if self._failed_frames is None:
            self._failed_frames = set(int(v) for v in self.tracking_failed_frames)

    @staticmethod
    def _bbox_from_mask(mask_uint8):
        ys, xs = np.where(mask_uint8 > 127)
        if xs.size == 0:
            return None
        bx, by = int(xs.min()), int(ys.min())
        bw = int(xs.max() - bx + 1)
        bh = int(ys.max() - by + 1)
        return (float(bx), float(by), float(bw), float(bh))

    @staticmethod
    def _bbox_to_norm(bbox, w: int, h: int):
        bx, by, bw, bh = bbox
        return (
            float(bx) / max(1, w),
            float(by) / max(1, h),
            float(bw) / max(1, w),
            float(bh) / max(1, h),
        )

    @staticmethod
    def _bbox_from_norm(bbox, w: int, h: int):
        bx, by, bw, bh = bbox
        return (
            float(bx) * max(1, w),
            float(by) * max(1, h),
            max(1.0, float(bw) * max(1, w)),
            max(1.0, float(bh) * max(1, h)),
        )

    def _cache_track_bbox(self, frame_idx: int, bbox) -> None:
        self._ensure_tracking_state()
        frame_key = int(frame_idx)
        box = tuple(float(v) for v in bbox)
        self._track_cache[frame_key] = box
        bw = int(self.base_width) if self.base_width > 0 else 1
        bh = int(self.base_height) if self.base_height > 0 else 1
        self.tracking_cache_bboxes[frame_key] = self._bbox_to_norm(box, bw, bh)
        limit = 2400
        if len(self._track_cache) > limit:
            keys = sorted(self._track_cache)
            for k in keys[: max(0, len(keys) - limit)]:
                self._track_cache.pop(k, None)
                self.tracking_cache_bboxes.pop(k, None)

    def _nearest_cached_bbox(self, frame_idx: int):
        self._ensure_tracking_state()
        if not self._track_cache:
            return None
        target = int(frame_idx)
        key = min(self._track_cache, key=lambda k: abs(k - target))
        return self._track_cache.get(key)

    def _correction_bbox_for_frame(self, frame_idx: int, w: int, h: int):
        if not self.correction_bboxes:
            return None
        f = int(frame_idx)
        if f in self.correction_bboxes:
            return self._bbox_from_norm(self.correction_bboxes[f], w, h)
        keys = sorted(int(k) for k in self.correction_bboxes)
        prev_keys = [k for k in keys if k < f]
        next_keys = [k for k in keys if k > f]
        if not prev_keys or not next_keys:
            return None
        a, b = prev_keys[-1], next_keys[0]
        if b <= a:
            return None
        t = (f - a) / float(b - a)
        ba = self.correction_bboxes[a]
        bb = self.correction_bboxes[b]
        interp = tuple(float(ba[i]) + (float(bb[i]) - float(ba[i])) * t for i in range(4))
        return self._bbox_from_norm(interp, w, h)

    def _init_tracker(self, cv2, rgb, bbox, frame_idx: int) -> bool:
        try:
            if hasattr(cv2, "TrackerCSRT_create"):
                tracker = cv2.TrackerCSRT_create()
            elif hasattr(cv2, "legacy"):
                tracker = cv2.legacy.TrackerCSRT_create()
            else:
                return False
            x, y, bw, bh = bbox
            init_bbox = (
                int(round(x)),
                int(round(y)),
                max(1, int(round(bw))),
                max(1, int(round(bh))),
            )
            tracker.init(rgb, init_bbox)
        except Exception:
            self._tracker = None
            return False
        self._tracker = tracker
        self._last_bbox = tuple(float(v) for v in bbox)
        self._last_frame_idx = int(frame_idx)
        return True

    def _warp_mask_to_bbox(self, mask_uint8, bbox):
        import cv2
        h, w = mask_uint8.shape[:2]
        if self._base_bbox is None:
            return mask_uint8
        bx, by, bw, bh = bbox
        obx, oby, obw, obh = self._base_bbox
        if obw <= 0 or obh <= 0:
            return mask_uint8
        sx = bw / obw
        sy = bh / obh
        tx = bx - obx * sx
        ty = by - oby * sy
        M = np.array([[sx, 0.0, tx], [0.0, sy, ty]], dtype=np.float32)
        return cv2.warpAffine(
            mask_uint8, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

    def reset_tracking_cache(self, clear_corrections: bool = False) -> None:
        self._tracker = None
        self._last_frame_idx = -1
        self._last_bbox = None
        self._track_cache = {}
        self._failed_frames = set()
        self.tracking_cache_bboxes.clear()
        self.tracking_failed_frames.clear()
        self._tracking_message = "reset"
        if clear_corrections:
            self.correction_bboxes.clear()

    def add_correction_from_mask(self, mask_uint8, frame_idx: int) -> bool:
        bbox = self._bbox_from_mask(mask_uint8)
        if bbox is None:
            return False
        h, w = mask_uint8.shape[:2]
        self.correction_bboxes[int(frame_idx)] = self._bbox_to_norm(bbox, w, h)
        self.reset_tracking_cache(clear_corrections=False)
        self._tracking_message = f"correction added at frame {int(frame_idx)}"
        return True

    def tracking_status(self) -> dict:
        self._ensure_tracking_state()
        return {
            "enabled": bool(self.track_object),
            "init_frame": int(self.init_frame),
            "cached_frames": len(self._track_cache),
            "corrections": len(self.correction_bboxes),
            "failed_frames": len(self._failed_frames),
            "failed_frame_numbers": sorted(int(v) for v in self._failed_frames)[:12],
            "message": self._tracking_message,
        }

    def tracking_status_text(self) -> str:
        info = self.tracking_status()
        if not info["enabled"]:
            return "Tracking off"
        msg = f" | {info['message']}" if info.get("message") else ""
        failed = ""
        failed_nums = info.get("failed_frame_numbers") or []
        if failed_nums:
            failed = f" ({','.join(str(v) for v in failed_nums[:6])})"
        return (
            f"Tracking from frame {info['init_frame']} | "
            f"cache {info['cached_frames']} | "
            f"corrections {info['corrections']} | "
            f"failures {info['failed_frames']}{failed}"
            f"{msg}"
        )

    def set_from_array(self, mask_uint8) -> None:
        """Encode a uint8 H×W mask into ``encoded_png`` and stash
        the source size so re-evaluation can resize cleanly."""
        try:
            import base64
            import cv2
        except ImportError:
            return
        h, w = mask_uint8.shape[:2]
        ok, buf = cv2.imencode(".png", mask_uint8)
        if not ok:
            return
        self.encoded_png = base64.b64encode(buf.tobytes()).decode("ascii")
        self.base_height = int(h)
        self.base_width = int(w)
        self._decoded = mask_uint8
        self._base_bbox = self._bbox_from_mask(mask_uint8)
        self.reset_tracking_cache(clear_corrections=False)

    def to_dict(self) -> dict:
        return {
            "kind": self.KIND,
            "encoded_png": self.encoded_png,
            "base_width": int(self.base_width),
            "base_height": int(self.base_height),
            "softness_norm": float(self.softness_norm),
            "invert": bool(self.invert),
            "enabled": bool(self.enabled),
            "track_object": bool(self.track_object),
            "init_frame": int(self.init_frame),
            "correction_bboxes": {
                str(int(k)): [float(v) for v in box]
                for k, box in sorted(self.correction_bboxes.items())
            },
            "tracking_cache_bboxes": {
                str(int(k)): [float(v) for v in box]
                for k, box in sorted(self.tracking_cache_bboxes.items())
            },
            "tracking_failed_frames": [
                int(v) for v in sorted(self.tracking_failed_frames)
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BitmapMask":
        return cls(
            encoded_png=str(d.get("encoded_png", "")),
            base_width=int(d.get("base_width", 0)),
            base_height=int(d.get("base_height", 0)),
            softness_norm=float(d.get("softness_norm", 0.01)),
            invert=bool(d.get("invert", False)),
            enabled=bool(d.get("enabled", True)),
            track_object=bool(d.get("track_object", False)),
            init_frame=int(d.get("init_frame", 0)),
            correction_bboxes={
                int(k): tuple(float(v) for v in box)
                for k, box in (d.get("correction_bboxes") or {}).items()
                if box is not None and len(box) == 4
            },
            tracking_cache_bboxes={
                int(k): tuple(float(v) for v in box)
                for k, box in (d.get("tracking_cache_bboxes") or {}).items()
                if box is not None and len(box) == 4
            },
            tracking_failed_frames=set(
                int(v) for v in (d.get("tracking_failed_frames") or [])
            ),
        )


# ---------------------------------------------------------------------------
# GrabCut — interactive rotoscope (click-and-drag rectangle)
# ---------------------------------------------------------------------------


def _rect_pixels(rect_normalised, width: int, height: int) -> tuple[int, int, int, int]:
    nx, ny, nw, nh = rect_normalised
    x = max(0, min(int(round(float(nx) * width)), width - 1))
    y = max(0, min(int(round(float(ny) * height)), height - 1))
    rw = max(1, min(int(round(float(nw) * width)), width - x))
    rh = max(1, min(int(round(float(nh) * height)), height - y))
    return x, y, rw, rh


def _mask_bbox(mask_uint8) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask_uint8 > 127)
    if xs.size == 0 or ys.size == 0:
        return None
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return x0, y0, x1 - x0 + 1, y1 - y0 + 1


def _fill_mask_holes(cv2, mask_uint8):
    padded = cv2.copyMakeBorder(
        mask_uint8, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0,
    )
    h, w = padded.shape[:2]
    flood = padded.copy()
    flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    cv2.floodFill(flood, flood_mask, (0, 0), 255)
    holes = cv2.bitwise_not(flood)
    filled = cv2.bitwise_or(padded, holes)
    return filled[1:-1, 1:-1]


def _clean_binary_mask(cv2, mask_uint8, *, keep_largest: bool = True):
    out = np.where(mask_uint8 > 127, 255, 0).astype(np.uint8)
    if out.size == 0:
        return out
    h, w = out.shape[:2]
    k = max(3, int(round(min(w, h) * 0.006)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    out = cv2.morphologyEx(out, cv2.MORPH_OPEN, kernel)
    out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, kernel)
    out = _fill_mask_holes(cv2, out)
    if not keep_largest:
        return out
    num, labels, stats, _ = cv2.connectedComponentsWithStats((out > 0).astype(np.uint8), 8)
    if num <= 1:
        return out
    min_area = max(8, int(h * w * 0.00015))
    best = None
    best_area = 0
    for idx in range(1, num):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        if area >= min_area and area > best_area:
            best = idx
            best_area = area
    if best is None:
        return out
    return np.where(labels == best, 255, 0).astype(np.uint8)


def _component_seed_from_rect(cv2, rgb, rect_normalised, raw_mask=None, seed_point=None):
    h, w = rgb.shape[:2]
    x, y, rw, rh = _rect_pixels(rect_normalised, w, h)
    crop = rgb[y:y + rh, x:x + rw]
    if crop.size == 0 or rw < 8 or rh < 8:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    if float(mag.max()) > 0:
        mag = mag / float(mag.max())
    dark = (float(np.percentile(gray, 90)) - gray)
    dark = dark - float(dark.min())
    if float(dark.max()) > 0:
        dark = dark / float(dark.max())
    sal = 0.62 * mag + 0.38 * dark
    yy, xx = np.mgrid[0:rh, 0:rw]
    border_dist = np.minimum.reduce([xx, yy, rw - 1 - xx, rh - 1 - yy]).astype(np.float32)
    border_weight = np.clip(border_dist / max(1.0, min(rw, rh) * 0.12), 0.0, 1.0)
    sal *= 0.35 + 0.65 * border_weight
    if raw_mask is not None:
        raw_crop = raw_mask[y:y + rh, x:x + rw] > 0
        sal *= np.where(raw_crop, 1.0, 0.45)
    threshold = max(float(np.percentile(sal, 91)), float(sal.mean() + sal.std() * 0.35))
    cand = np.where(sal >= threshold, 255, 0).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, kernel)
    cand = cv2.dilate(cand, kernel, iterations=1)
    num, labels, stats, centroids = cv2.connectedComponentsWithStats(cand, 8)
    if num <= 1:
        return None
    if seed_point is not None:
        sx = int(round(max(0.0, min(1.0, float(seed_point[0]))) * (w - 1))) - x
        sy = int(round(max(0.0, min(1.0, float(seed_point[1]))) * (h - 1))) - y
    else:
        sx, sy = rw * 0.5, rh * 0.5
    best_idx = None
    best_score = -1.0
    max_area = rw * rh * 0.38
    min_area = max(8, int(rw * rh * 0.001))
    for idx in range(1, num):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        if area < min_area or area > max_area:
            continue
        cx, cy = centroids[idx]
        dx = (float(cx) - float(sx)) / max(1.0, rw)
        dy = (float(cy) - float(sy)) / max(1.0, rh)
        proximity = 1.0 / (1.0 + 7.5 * (dx * dx + dy * dy))
        comp = labels == idx
        score = float(sal[comp].mean()) * (area ** 0.45) * proximity
        if score > best_score:
            best_score = score
            best_idx = idx
    if best_idx is None:
        return None
    sx0 = int(stats[best_idx, cv2.CC_STAT_LEFT])
    sy0 = int(stats[best_idx, cv2.CC_STAT_TOP])
    sw = int(stats[best_idx, cv2.CC_STAT_WIDTH])
    sh = int(stats[best_idx, cv2.CC_STAT_HEIGHT])
    pad = max(4, int(max(sw, sh) * 0.40))
    x0 = max(x, x + sx0 - pad)
    y0 = max(y, y + sy0 - pad)
    x1 = min(x + rw, x + sx0 + sw + pad)
    y1 = min(y + rh, y + sy0 + sh + pad)
    seed_mask = np.zeros((h, w), dtype=np.uint8)
    seed_mask[y + sy0:y + sy0 + sh, x + sx0:x + sx0 + sw] = np.where(
        labels[sy0:sy0 + sh, sx0:sx0 + sw] == best_idx, 255, 0
    ).astype(np.uint8)
    seed_mask = cv2.dilate(seed_mask, kernel, iterations=2)
    return (x0, y0, max(1, x1 - x0), max(1, y1 - y0), seed_mask)


def _grabcut_quality(mask_uint8, rect_normalised) -> dict:
    h, w = mask_uint8.shape[:2]
    x, y, rw, rh = _rect_pixels(rect_normalised, w, h)
    rect_area = max(1, rw * rh)
    selected = int(np.count_nonzero(mask_uint8[y:y + rh, x:x + rw] > 127))
    bbox = _mask_bbox(mask_uint8)
    coverage = selected / rect_area
    touches = 0
    if bbox is not None:
        bx, by, bw, bh = bbox
        touches += int(bx <= x + 1)
        touches += int(by <= y + 1)
        touches += int(bx + bw >= x + rw - 1)
        touches += int(by + bh >= y + rh - 1)
    quality = "wide_spill" if coverage > 0.34 or touches >= 2 else "ok"
    if selected <= 0:
        quality = "empty"
    return {
        "coverage": float(coverage),
        "bbox": bbox,
        "touches_rect_edges": int(touches),
        "quality": quality,
    }


def refine_grabcut_mask(rgb, mask_uint8, rect_normalised, *, seed_point=None, iterations: int = 2):
    """Clean and, when needed, re-seed an over-wide GrabCut mask."""
    try:
        import cv2
    except ImportError:
        return mask_uint8, {"quality": "cv2_unavailable", "refined": False}
    h, w = rgb.shape[:2]
    x, y, rw, rh = _rect_pixels(rect_normalised, w, h)
    raw = np.where(mask_uint8 > 127, 255, 0).astype(np.uint8)
    raw[:y, :] = 0
    raw[y + rh:, :] = 0
    raw[:, :x] = 0
    raw[:, x + rw:] = 0
    quality = _grabcut_quality(raw, rect_normalised)
    cleaned = _clean_binary_mask(cv2, raw)
    refined = False
    if quality.get("quality") in {"wide_spill", "empty"}:
        seed = _component_seed_from_rect(cv2, rgb, rect_normalised, raw_mask=raw, seed_point=seed_point)
        if seed is not None:
            sx, sy, sw, sh, seed_mask = seed
            gc_mask = np.full((h, w), cv2.GC_BGD, dtype=np.uint8)
            gc_mask[y:y + rh, x:x + rw] = cv2.GC_PR_BGD
            gc_mask[sy:sy + sh, sx:sx + sw] = cv2.GC_PR_FGD
            gc_mask[seed_mask > 0] = cv2.GC_FGD
            bgd = np.zeros((1, 65), dtype=np.float64)
            fgd = np.zeros((1, 65), dtype=np.float64)
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            try:
                cv2.grabCut(
                    bgr, gc_mask, None, bgd, fgd, max(1, int(iterations)),
                    cv2.GC_INIT_WITH_MASK,
                )
                candidate = np.where((gc_mask == 1) | (gc_mask == 3), 255, 0).astype(np.uint8)
                candidate[:y, :] = 0
                candidate[y + rh:, :] = 0
                candidate[:, :x] = 0
                candidate[:, x + rw:] = 0
                candidate = _clean_binary_mask(cv2, candidate)
                cand_quality = _grabcut_quality(candidate, rect_normalised)
                if np.count_nonzero(candidate) > 0 and cand_quality["coverage"] <= max(0.30, quality["coverage"] * 0.90):
                    cleaned = candidate
                    quality = cand_quality
                    quality["quality"] = "seed_refined"
                    refined = True
            except Exception:
                pass
    quality["refined"] = bool(refined)
    if quality.get("quality") == "wide_spill":
        quality["suggestion"] = "Loose rectangle: click the object center or use Clean/Shrink."
    elif quality.get("quality") == "empty":
        quality["suggestion"] = "No object found: draw a tighter rectangle or click the object."
    elif refined:
        quality["suggestion"] = "Auto-refined from a high-contrast object seed."
    else:
        quality["suggestion"] = "Mask ready. Use Clean/Shrink/Expand if needed."
    return cleaned, quality


def grabcut_from_rect(
    rgb,
    rect_normalised,
    iterations: int = 4,
    *,
    refine: bool = True,
    seed_point=None,
    return_info: bool = False,
):
    """Run cv2.grabCut on ``rgb`` with the given normalised rectangle
    ``(x, y, w, h)`` (each in [0, 1]). Returns a uint8 H×W mask
    (255 = subject, 0 = background) ready to feed
    ``BitmapMask.set_from_array``.

    Lightweight wrapper — keeps the editor's mask-tool code free of
    cv2 boilerplate. Returns ``None`` when cv2 is unavailable.
    """
    try:
        import cv2
    except ImportError:
        return None
    h, w = rgb.shape[:2]
    x, y, rw, rh = _rect_pixels(rect_normalised, w, h)
    mask = np.zeros((h, w), dtype=np.uint8)
    bgd = np.zeros((1, 65), dtype=np.float64)
    fgd = np.zeros((1, 65), dtype=np.float64)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    try:
        cv2.grabCut(bgr, mask, (x, y, rw, rh), bgd, fgd, iterations,
                    cv2.GC_INIT_WITH_RECT)
    except Exception:
        return None
    # Foreground = both definite (1) and probable (3).
    out = np.where((mask == 1) | (mask == 3), 255, 0).astype(np.uint8)
    info = {"quality": "raw", "refined": False}
    if refine:
        out, info = refine_grabcut_mask(
            rgb,
            out,
            rect_normalised,
            seed_point=seed_point,
            iterations=max(1, iterations // 2),
        )
    if return_info:
        return out, info
    return out


# ---------------------------------------------------------------------------
# Dispatch & composition helpers
# ---------------------------------------------------------------------------


_KIND_TO_CLASS: dict[str, Any] = {
    KIND_POWER_WINDOW: PowerWindow,
    KIND_HSL_QUALIFIER: HSLQualifier,
    KIND_MAGIC_MASK: MagicMask,
    KIND_TRACKER: MaskTracker,
    KIND_BITMAP: BitmapMask,
}


def mask_from_dict(d: dict):
    """Restore a mask of any kind from its serialised dict."""
    kind = d.get("kind")
    cls = _KIND_TO_CLASS.get(kind)
    if cls is None:
        return None
    try:
        return cls.from_dict(d)
    except Exception:
        return None


def evaluate_node_masks(masks: list, rgb: np.ndarray, frame_idx: int = 0) -> np.ndarray | None:
    """Compose a node's mask list into a single ``H×W float32`` mask
    via union (per-pixel max). Returns ``None`` when the list is
    empty / all-disabled, signalling "no mask, apply grade
    everywhere"."""
    if not masks:
        return None
    h, w = rgb.shape[:2]
    out: np.ndarray | None = None
    for m in masks:
        if not getattr(m, "enabled", True):
            continue
        try:
            mk = m.evaluate(rgb, frame_idx)
        except Exception:
            continue
        if mk is None or mk.shape[:2] != (h, w):
            continue
        if out is None:
            out = mk
        else:
            np.maximum(out, mk, out=out)
    return out
