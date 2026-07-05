"""VMD motion reader and interpolation helpers."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
import math
import struct


class VMDParseError(ValueError):
    """Raised when a VMD file is malformed."""


_VMD_SAMPLE_CACHE_LIMIT = 4096
_BONE_POSE_CACHE: OrderedDict[tuple[int, str, int, float], dict[str, tuple[tuple[float, float, float], tuple[float, float, float, float]]]] = OrderedDict()
_MORPH_WEIGHT_CACHE: OrderedDict[tuple[int, str, int, float], dict[str, float]] = OrderedDict()
_BEZIER_EPSILON = 1.0e-7


@dataclass(frozen=True)
class VMDBezier:
    x1: float = 20.0 / 127.0
    y1: float = 20.0 / 127.0
    x2: float = 107.0 / 127.0
    y2: float = 107.0 / 127.0


@dataclass(frozen=True)
class VMDBoneInterpolation:
    x: VMDBezier
    y: VMDBezier
    z: VMDBezier
    rotation: VMDBezier


@dataclass(frozen=True)
class VMDCameraInterpolation:
    x: VMDBezier
    y: VMDBezier
    z: VMDBezier
    rotation: VMDBezier
    distance: VMDBezier
    fov: VMDBezier


@dataclass(frozen=True)
class VMDBoneFrame:
    name: str
    frame: int
    translation: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    interpolation: VMDBoneInterpolation


@dataclass(frozen=True)
class VMDMorphFrame:
    name: str
    frame: int
    weight: float


@dataclass(frozen=True)
class VMDCameraFrame:
    frame: int
    distance: float
    position: tuple[float, float, float]
    rotation: tuple[float, float, float]
    fov_degrees: float
    perspective: bool
    interpolation: VMDCameraInterpolation


@dataclass(frozen=True)
class VMDMotion:
    path: Path
    header: str
    model_name: str
    bone_frames: dict[str, tuple[VMDBoneFrame, ...]]
    morph_frames: dict[str, tuple[VMDMorphFrame, ...]]
    camera_frames: tuple[VMDCameraFrame, ...]
    max_frame: int

    @property
    def has_model_motion(self) -> bool:
        return bool(self.bone_frames or self.morph_frames)

    @property
    def has_camera_motion(self) -> bool:
        return bool(self.camera_frames)


class _Reader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    def _take(self, size: int) -> bytes:
        end = self._offset + int(size)
        if size < 0 or end > len(self._data):
            raise VMDParseError("Unexpected end of VMD data")
        out = self._data[self._offset:end]
        self._offset = end
        return out

    def u8(self) -> int:
        return self._take(1)[0]

    def u32(self) -> int:
        return struct.unpack("<I", self._take(4))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self._take(4))[0]

    def vec3(self) -> tuple[float, float, float]:
        return self.f32(), self.f32(), self.f32()

    def vec4(self) -> tuple[float, float, float, float]:
        return self.f32(), self.f32(), self.f32(), self.f32()

    def text(self, size: int) -> str:
        raw = self._take(size).split(b"\x00", 1)[0]
        return raw.decode("cp932", errors="replace").strip()


def _append(mapping: dict[str, list], key: str, value) -> None:
    mapping.setdefault(key, []).append(value)


def _bezier_from_bytes(raw: bytes, offsets: tuple[int, int, int, int]) -> VMDBezier:
    vals = []
    for off in offsets:
        vals.append(max(0.0, min(1.0, float(raw[off]) / 127.0)) if off < len(raw) else 0.0)
    return VMDBezier(vals[0], vals[1], vals[2], vals[3])


def _bone_interpolation(raw: bytes) -> VMDBoneInterpolation:
    return VMDBoneInterpolation(
        x=_bezier_from_bytes(raw, (0, 4, 8, 12)),
        y=_bezier_from_bytes(raw, (1, 5, 9, 13)),
        z=_bezier_from_bytes(raw, (2, 6, 10, 14)),
        rotation=_bezier_from_bytes(raw, (3, 7, 11, 15)),
    )


def _camera_interpolation(raw: bytes) -> VMDCameraInterpolation:
    return VMDCameraInterpolation(
        x=_bezier_from_bytes(raw, (0, 1, 2, 3)),
        y=_bezier_from_bytes(raw, (4, 5, 6, 7)),
        z=_bezier_from_bytes(raw, (8, 9, 10, 11)),
        rotation=_bezier_from_bytes(raw, (12, 13, 14, 15)),
        distance=_bezier_from_bytes(raw, (16, 17, 18, 19)),
        fov=_bezier_from_bytes(raw, (20, 21, 22, 23)),
    )


def load_vmd(path: str | Path) -> VMDMotion:
    vmd_path = Path(path)
    reader = _Reader(vmd_path.read_bytes())
    header = reader.text(30)
    if "Vocaloid Motion Data" not in header:
        raise VMDParseError("Not a VMD motion file")
    model_name = reader.text(20)

    bone_frames: dict[str, list[VMDBoneFrame]] = {}
    max_frame = 0
    for _ in range(reader.u32()):
        name = reader.text(15)
        frame = int(reader.u32())
        translation = reader.vec3()
        rotation = _quat_normalize(reader.vec4())
        interpolation = _bone_interpolation(reader._take(64))
        _append(bone_frames, name, VMDBoneFrame(name, frame, translation, rotation, interpolation))
        max_frame = max(max_frame, frame)

    morph_frames: dict[str, list[VMDMorphFrame]] = {}
    for _ in range(reader.u32()):
        name = reader.text(15)
        frame = int(reader.u32())
        weight = float(reader.f32())
        _append(morph_frames, name, VMDMorphFrame(name, frame, weight))
        max_frame = max(max_frame, frame)

    camera_frames: list[VMDCameraFrame] = []
    for _ in range(reader.u32()):
        frame = int(reader.u32())
        distance = float(reader.f32())
        position = reader.vec3()
        rotation = reader.vec3()
        interpolation = _camera_interpolation(reader._take(24))
        fov = float(reader.u32())
        perspective = reader.u8() == 0
        camera_frames.append(
            VMDCameraFrame(
                frame=frame,
                distance=distance,
                position=tuple(float(v) for v in position),
                rotation=tuple(float(v) for v in rotation),
                fov_degrees=fov,
                perspective=perspective,
                interpolation=interpolation,
            )
        )
        max_frame = max(max_frame, frame)

    return VMDMotion(
        path=vmd_path,
        header=header,
        model_name=model_name,
        bone_frames={k: tuple(sorted(v, key=lambda f: f.frame)) for k, v in bone_frames.items()},
        morph_frames={k: tuple(sorted(v, key=lambda f: f.frame)) for k, v in morph_frames.items()},
        camera_frames=tuple(sorted(camera_frames, key=lambda f: f.frame)),
        max_frame=int(max_frame),
    )


def _quat_normalize(q: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x, y, z, w = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 0.000001:
        return 0.0, 0.0, 0.0, 1.0
    return x / length, y / length, z / length, w / length


def _quat_slerp(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    t: float,
) -> tuple[float, float, float, float]:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    dot = ax * bx + ay * by + az * bz + aw * bw
    if dot < 0.0:
        bx, by, bz, bw = -bx, -by, -bz, -bw
        dot = -dot
    if dot > 0.9995:
        return _quat_normalize((
            ax + (bx - ax) * t,
            ay + (by - ay) * t,
            az + (bz - az) * t,
            aw + (bw - aw) * t,
        ))
    theta_0 = math.acos(max(-1.0, min(1.0, dot)))
    theta = theta_0 * t
    sin_theta = math.sin(theta)
    sin_theta_0 = math.sin(theta_0)
    s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0
    return (
        ax * s0 + bx * s1,
        ay * s0 + by * s1,
        az * s0 + bz * s1,
        aw * s0 + bw * s1,
    )


def _lerp3(a: tuple[float, float, float], b: tuple[float, float, float], t: float) -> tuple[float, float, float]:
    return (
        float(a[0] + (b[0] - a[0]) * t),
        float(a[1] + (b[1] - a[1]) * t),
        float(a[2] + (b[2] - a[2]) * t),
    )


def _lerp(a: float, b: float, t: float) -> float:
    return float(a + (b - a) * t)


def _lerp_angle(a: float, b: float, t: float) -> float:
    delta = (float(b) - float(a) + math.pi) % (math.pi * 2.0) - math.pi
    return float(a) + delta * float(t)


def _lerp3_angles(a: tuple[float, float, float], b: tuple[float, float, float], t: float) -> tuple[float, float, float]:
    return (
        _lerp_angle(a[0], b[0], t),
        _lerp_angle(a[1], b[1], t),
        _lerp_angle(a[2], b[2], t),
    )


def _bezier_eval_axis(p1: float, p2: float, t: float) -> float:
    inv = 1.0 - t
    return 3.0 * inv * inv * t * p1 + 3.0 * inv * t * t * p2 + t * t * t


def _bezier_derivative_axis(p1: float, p2: float, t: float) -> float:
    inv = 1.0 - t
    return 3.0 * inv * inv * p1 + 6.0 * inv * t * (p2 - p1) + 3.0 * t * t * (1.0 - p2)


def vmd_bezier_is_linear(curve: VMDBezier, *, epsilon: float = 1.0 / 127.0) -> bool:
    return abs(float(curve.x1) - float(curve.y1)) <= epsilon and abs(float(curve.x2) - float(curve.y2)) <= epsilon


def _bezier_t(curve: VMDBezier, linear_t: float) -> float:
    x = max(0.0, min(1.0, float(linear_t)))
    if x <= 0.0 or x >= 1.0:
        return x
    if vmd_bezier_is_linear(curve, epsilon=_BEZIER_EPSILON):
        return x
    guess = x
    lo = 0.0
    hi = 1.0
    for _ in range(12):
        sample = _bezier_eval_axis(curve.x1, curve.x2, guess) - x
        if abs(sample) <= _BEZIER_EPSILON:
            return max(0.0, min(1.0, _bezier_eval_axis(curve.y1, curve.y2, guess)))
        if sample > 0.0:
            hi = guess
        else:
            lo = guess
        deriv = _bezier_derivative_axis(curve.x1, curve.x2, guess)
        if abs(deriv) <= _BEZIER_EPSILON:
            break
        candidate = guess - sample / deriv
        if candidate <= lo or candidate >= hi:
            break
        guess = max(0.0, min(1.0, candidate))
    for _ in range(24):
        guess = (lo + hi) * 0.5
        sample = _bezier_eval_axis(curve.x1, curve.x2, guess)
        if sample < x:
            lo = guess
        else:
            hi = guess
    return max(0.0, min(1.0, _bezier_eval_axis(curve.y1, curve.y2, guess)))


def vmd_bezier_value(curve: VMDBezier, linear_t: float) -> float:
    return _bezier_t(curve, linear_t)


def vmd_bezier_max_linear_delta(curve: VMDBezier) -> float:
    return max(abs(vmd_bezier_value(curve, value) - value) for value in (0.25, 0.5, 0.75))


def _bracket(frames, frame: float):
    if not frames:
        return None, None, 0.0
    target = float(frame)
    lo = 0
    hi = len(frames)
    while lo < hi:
        mid = (lo + hi) // 2
        if float(frames[mid].frame) <= target:
            lo = mid + 1
        else:
            hi = mid
    idx = lo
    if idx <= 0:
        return frames[0], frames[0], 0.0
    if idx >= len(frames):
        return frames[-1], frames[-1], 0.0
    prev_f = frames[idx - 1]
    next_f = frames[idx]
    span = max(1.0, float(next_f.frame - prev_f.frame))
    return prev_f, next_f, max(0.0, min(1.0, (float(frame) - float(prev_f.frame)) / span))


def _sample_cache_key(motion: VMDMotion, frame: float) -> tuple[int, str, int, float]:
    return (
        id(motion),
        str(motion.path),
        int(motion.max_frame),
        round(float(frame), 4),
    )


def _cache_get(cache: OrderedDict, key):
    value = cache.get(key)
    if value is not None:
        cache.move_to_end(key)
        return dict(value)
    return None


def _cache_put(cache: OrderedDict, key, value) -> dict:
    stored = dict(value)
    cache[key] = stored
    cache.move_to_end(key)
    while len(cache) > _VMD_SAMPLE_CACHE_LIMIT:
        cache.popitem(last=False)
    return dict(stored)


def bone_pose_at(motion: VMDMotion | None, frame: float) -> dict[str, tuple[tuple[float, float, float], tuple[float, float, float, float]]]:
    if motion is None:
        return {}
    key = _sample_cache_key(motion, frame)
    cached = _cache_get(_BONE_POSE_CACHE, key)
    if cached is not None:
        return cached
    out = {}
    for name, frames in motion.bone_frames.items():
        a, b, t = _bracket(frames, frame)
        if a is None or b is None:
            continue
        interp = b.interpolation
        translation = (
            _lerp(a.translation[0], b.translation[0], _bezier_t(interp.x, t)),
            _lerp(a.translation[1], b.translation[1], _bezier_t(interp.y, t)),
            _lerp(a.translation[2], b.translation[2], _bezier_t(interp.z, t)),
        )
        out[name] = (translation, _quat_slerp(a.rotation, b.rotation, _bezier_t(interp.rotation, t)))
    return _cache_put(_BONE_POSE_CACHE, key, out)


def morph_weights_at(motion: VMDMotion | None, frame: float) -> dict[str, float]:
    if motion is None:
        return {}
    key = _sample_cache_key(motion, frame)
    cached = _cache_get(_MORPH_WEIGHT_CACHE, key)
    if cached is not None:
        return cached
    out = {}
    for name, frames in motion.morph_frames.items():
        a, b, t = _bracket(frames, frame)
        if a is None or b is None:
            continue
        out[name] = _lerp(a.weight, b.weight, t)
    return _cache_put(_MORPH_WEIGHT_CACHE, key, out)


def camera_at(motion: VMDMotion | None, frame: float) -> VMDCameraFrame | None:
    if motion is None or not motion.camera_frames:
        return None
    a, b, t = _bracket(motion.camera_frames, frame)
    if a is None or b is None:
        return None
    return VMDCameraFrame(
        frame=int(round(frame)),
        distance=_lerp(a.distance, b.distance, _bezier_t(b.interpolation.distance, t)),
        position=(
            _lerp(a.position[0], b.position[0], _bezier_t(b.interpolation.x, t)),
            _lerp(a.position[1], b.position[1], _bezier_t(b.interpolation.y, t)),
            _lerp(a.position[2], b.position[2], _bezier_t(b.interpolation.z, t)),
        ),
        rotation=_lerp3_angles(a.rotation, b.rotation, _bezier_t(b.interpolation.rotation, t)),
        fov_degrees=_lerp(a.fov_degrees, b.fov_degrees, _bezier_t(b.interpolation.fov, t)),
        perspective=a.perspective if t < 0.5 else b.perspective,
        interpolation=b.interpolation,
    )


def camera_to_view_controls(
    camera: VMDCameraFrame | None,
    *,
    fallback_yaw: float,
    fallback_pitch: float,
    fallback_zoom: float,
    fallback_offset_x: float = 0.0,
    fallback_offset_y: float = -0.02,
) -> dict[str, float]:
    if camera is None:
        return {
            "yaw": float(fallback_yaw),
            "pitch": float(fallback_pitch),
            "roll": 0.0,
            "zoom": float(fallback_zoom),
            "offset_x": float(fallback_offset_x),
            "offset_y": float(fallback_offset_y),
        }
    rx, ry, rz = camera.rotation
    distance = max(1.0, abs(float(camera.distance)))
    fov = max(8.0, min(80.0, float(camera.fov_degrees or 45.0)))
    zoom = max(0.15, min(3.0, (45.0 / fov) * (35.0 / distance)))
    return {
        "yaw": math.degrees(float(ry)),
        "pitch": math.degrees(float(rx)),
        "roll": math.degrees(float(rz)),
        "zoom": zoom,
        "offset_x": max(-1.0, min(1.0, float(camera.position[0]) / 18.0)),
        "offset_y": max(-1.0, min(1.0, float(camera.position[1]) / 18.0)) - 0.02,
    }
