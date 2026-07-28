"""OpenCV point and planar tracking for Motion Designer mask caches."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import atan2, ceil, degrees, exp, hypot
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .keyframes import evaluate_property
from .mask_tracking import MotionTrackSample, MotionTrackingCache
from .schema import MotionComposition, MotionLayer, MotionMaskRef


ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]


class MotionTrackingCancelled(RuntimeError):
    """Raised when a caller cancels a tracking analysis."""


@dataclass(slots=True)
class MotionTrackingRequest:
    video_path: str
    mode: str = "point"
    start_ms: int = 0
    end_ms: int | None = None
    timeline_start_ms: int | None = None
    timeline_time_scale: float = 1.0
    sample_interval_ms: int = 100
    analysis_fps: float = 30.0
    max_analysis_dimension: int = 960
    max_analysis_frames: int = 5400
    max_features: int = 240
    target_size: tuple[int, int] | None = None
    roi: tuple[float, float, float, float] | None = None

    def normalized_mode(self) -> str:
        mode = str(self.mode or "point").lower()
        if mode not in {"point", "planar"}:
            raise ValueError(f"unsupported tracking mode: {self.mode}")
        return mode


def _animated_default(mask: MotionMaskRef, key: str, time_ms: int, default: Any) -> Any:
    prop = mask.params.get(key)
    return evaluate_property(prop, time_ms) if prop is not None else default


def mask_tracking_roi(
    mask: MotionMaskRef,
    target_size: tuple[int, int],
    time_ms: int,
) -> tuple[float, float, float, float]:
    """Return the authored mask bounds in layer-local target coordinates."""
    target_width, target_height = target_size
    x = float(_animated_default(mask, "x", time_ms, 0.0))
    y = float(_animated_default(mask, "y", time_ms, 0.0))
    width = float(_animated_default(mask, "width", time_ms, target_width))
    height = float(_animated_default(mask, "height", time_ms, target_height))
    if mask.kind == "path":
        path = _animated_default(mask, "path", time_ms, {})
        points = path.get("points", []) if isinstance(path, Mapping) else []
        positions = [
            item.get("position") for item in points
            if isinstance(item, Mapping) and isinstance(item.get("position"), Sequence)
            and len(item.get("position")) >= 2
        ]
        if positions:
            xs = [float(item[0]) for item in positions]
            ys = [float(item[1]) for item in positions]
            x += min(xs)
            y += min(ys)
            width = max(4.0, max(xs) - min(xs))
            height = max(4.0, max(ys) - min(ys))
    return _clamp_roi((x, y, width, height), target_width, target_height)


def tracking_request_for_mask(
    composition: MotionComposition,
    layer: MotionLayer,
    mask: MotionMaskRef,
    *,
    video_path: str = "",
    mode: str = "",
    start_ms: int | None = None,
    end_ms: int | None = None,
    timeline_start_ms: int | None = None,
    sample_interval_ms: int = 100,
    target_size: Sequence[int] | None = None,
    roi: Sequence[float] | None = None,
) -> MotionTrackingRequest:
    """Build a video request from the selected Motion layer and mask."""
    if layer.reverse:
        raise ValueError("automatic mask tracking does not support reversed Motion layers yet")
    source_uri = str(video_path or layer.source.uri or "")
    if not source_uri:
        raise ValueError("a source video is required for automatic mask tracking")
    if target_size is None:
        target_width = int(round(float(layer.source.params.get("width", composition.width))))
        target_height = int(round(float(layer.source.params.get("height", composition.height))))
    else:
        values = list(target_size)
        if len(values) < 2:
            raise ValueError("target_size must contain width and height")
        target_width, target_height = int(values[0]), int(values[1])
    target = (max(1, target_width), max(1, target_height))
    source_start_ms = int(layer.source_in_ms if start_ms is None else start_ms)
    time_scale = max(1e-6, abs(float(layer.time_scale or 1.0)))
    if end_ms is None:
        source_duration_ms = int(round(max(1, layer.out_ms - layer.in_ms) * time_scale))
        source_end_ms = source_start_ms + source_duration_ms
    else:
        source_end_ms = int(end_ms)
    cache = MotionTrackingCache.from_dict(mask.metadata.get("tracking_cache"))
    request_mode = str(mode or cache.mode or "point")
    request_roi = tuple(float(value) for value in roi) if roi is not None else mask_tracking_roi(
        mask, target, layer.in_ms,
    )
    if len(request_roi) != 4:
        raise ValueError("roi must contain x, y, width and height")
    return MotionTrackingRequest(
        video_path=source_uri,
        mode=request_mode,
        start_ms=source_start_ms,
        end_ms=source_end_ms,
        timeline_start_ms=layer.in_ms if timeline_start_ms is None else int(timeline_start_ms),
        timeline_time_scale=time_scale,
        sample_interval_ms=max(1, int(sample_interval_ms)),
        target_size=target,
        roi=request_roi,
    )


def _source_revision(path: Path) -> str:
    stat = path.stat()
    value = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    return sha256(value.encode("utf-8", errors="replace")).hexdigest()[:20]


def _clamp_roi(
    roi: tuple[float, float, float, float] | None,
    width: int,
    height: int,
) -> tuple[float, float, float, float]:
    if roi is None:
        return 0.0, 0.0, float(width), float(height)
    x, y, roi_width, roi_height = (float(value) for value in roi)
    x = max(0.0, min(float(width - 1), x))
    y = max(0.0, min(float(height - 1), y))
    roi_width = max(2.0, min(float(width) - x, roi_width))
    roi_height = max(2.0, min(float(height) - y, roi_height))
    if roi_width < 4.0 or roi_height < 4.0:
        raise ValueError("tracking ROI is too small")
    return x, y, roi_width, roi_height


def _resize_gray(cv2, frame, max_dimension: int):
    height, width = frame.shape[:2]
    scale = min(1.0, max(64, int(max_dimension)) / float(max(width, height)))
    if scale < 0.999:
        frame = cv2.resize(
            frame,
            (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
            interpolation=cv2.INTER_AREA,
        )
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), scale


def _roi_polygon(roi, scale: float):
    import numpy as np

    x, y, width, height = roi
    return np.asarray(
        [[x, y], [x + width, y], [x + width, y + height], [x, y + height]],
        dtype=np.float32,
    ) * float(scale)


def _feature_mask(cv2, shape: tuple[int, int], polygon):
    import numpy as np

    mask = np.zeros(shape, dtype=np.uint8)
    points = np.rint(polygon).astype(np.int32)
    cv2.fillConvexPoly(mask, points, 255)
    return mask


def _detect_features(cv2, gray, polygon, max_features: int):
    points = cv2.goodFeaturesToTrack(
        gray,
        maxCorners=max(16, int(max_features)),
        qualityLevel=0.008,
        minDistance=6.0,
        mask=_feature_mask(cv2, gray.shape[:2], polygon),
        blockSize=7,
        useHarrisDetector=False,
    )
    return points


def _track_features(cv2, previous_gray, current_gray, points):
    import numpy as np

    if points is None or len(points) < 2:
        return None, None, float("inf")
    options = {
        "winSize": (25, 25),
        "maxLevel": 3,
        "criteria": (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    }
    current, forward_status, _error = cv2.calcOpticalFlowPyrLK(
        previous_gray, current_gray, points, None, **options,
    )
    if current is None or forward_status is None:
        return None, None, float("inf")
    backward, backward_status, _error = cv2.calcOpticalFlowPyrLK(
        current_gray, previous_gray, current, None, **options,
    )
    if backward is None or backward_status is None:
        return None, None, float("inf")
    forward_status = forward_status.reshape(-1).astype(bool)
    backward_status = backward_status.reshape(-1).astype(bool)
    forward_backward_error = np.linalg.norm(
        points.reshape(-1, 2) - backward.reshape(-1, 2), axis=1,
    )
    finite = np.isfinite(current.reshape(-1, 2)).all(axis=1)
    good = forward_status & backward_status & finite & (forward_backward_error <= 2.5)
    previous = points.reshape(-1, 2)[good]
    current = current.reshape(-1, 2)[good]
    if len(previous) < 2:
        return None, None, float("inf")
    return previous, current, float(np.median(forward_backward_error[good]))


def _is_scene_cut(cv2, previous_gray, current_gray) -> bool:
    previous = cv2.resize(previous_gray, (160, 90), interpolation=cv2.INTER_AREA)
    current = cv2.resize(current_gray, (160, 90), interpolation=cv2.INTER_AREA)
    mean_difference = float(cv2.absdiff(previous, current).mean())
    previous_hist = cv2.calcHist([previous], [0], None, [32], [0, 256])
    current_hist = cv2.calcHist([current], [0], None, [32], [0, 256])
    correlation = float(cv2.compareHist(previous_hist, current_hist, cv2.HISTCMP_CORREL))
    return mean_difference >= 42.0 or (mean_difference >= 10.0 and correlation < 0.68)


def _transform_polygon(cv2, polygon, matrix):
    import numpy as np

    return cv2.transform(np.asarray([polygon], dtype=np.float32), matrix[:2]).reshape(-1, 2)


def _matrix_sample(matrix, origin, time_ms: int, confidence: float) -> MotionTrackSample:
    a = float(matrix[0, 0])
    b = float(matrix[1, 0])
    c = float(matrix[0, 1])
    d = float(matrix[1, 1])
    scale_x = max(1e-6, hypot(a, b))
    scale_y = max(1e-6, hypot(c, d))
    rotation = degrees(atan2(b, a))
    origin_x, origin_y = origin
    translate_x = float(matrix[0, 2]) - origin_x + a * origin_x + c * origin_y
    translate_y = float(matrix[1, 2]) - origin_y + b * origin_x + d * origin_y
    return MotionTrackSample(
        time_ms=int(time_ms),
        translate=(translate_x, translate_y),
        scale=(scale_x, scale_y),
        rotation=rotation,
        confidence=max(0.0, min(1.0, float(confidence))),
    )


def _translation_sample(offset, time_ms: int, confidence: float) -> MotionTrackSample:
    return MotionTrackSample(
        time_ms=int(time_ms),
        translate=(float(offset[0]), float(offset[1])),
        confidence=max(0.0, min(1.0, float(confidence))),
    )


def generate_tracking_cache(
    request: MotionTrackingRequest,
    *,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
) -> MotionTrackingCache:
    """Analyze a video and return the shared point/planar mask tracking cache."""
    import cv2
    import numpy as np

    mode = request.normalized_mode()
    path = Path(request.video_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"tracking source video not found: {path}")
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"could not open tracking source video: {path}")
    try:
        source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if not np.isfinite(source_fps) or source_fps <= 0.1:
            source_fps = 30.0
        frame_count = max(1, int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 1)))
        duration_ms = max(1, int(round(frame_count * 1000.0 / source_fps)))
        start_ms = max(0, min(duration_ms - 1, int(request.start_ms)))
        requested_end = duration_ms if request.end_ms is None else int(request.end_ms)
        end_ms = max(start_ms + 1, min(duration_ms, requested_end))
        start_frame = max(0, min(frame_count - 1, int(round(start_ms * source_fps / 1000.0))))
        end_frame = max(start_frame, min(frame_count - 1, int(round(end_ms * source_fps / 1000.0))))
        range_frames = max(1, end_frame - start_frame + 1)
        fps_stride = max(1, int(ceil(source_fps / max(1.0, float(request.analysis_fps)))))
        limit_stride = max(1, int(ceil(range_frames / max(2, int(request.max_analysis_frames)))))
        frame_stride = max(fps_stride, limit_stride)
        total_steps = max(1, int(ceil((end_frame - start_frame) / frame_stride)))

        capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        ok, first_frame = capture.read()
        if not ok or first_frame is None:
            raise ValueError("could not decode the first tracking frame")
        source_height, source_width = first_frame.shape[:2]
        target_width, target_height = request.target_size or (source_width, source_height)
        target_width = max(1, int(target_width))
        target_height = max(1, int(target_height))
        roi_target = _clamp_roi(request.roi, target_width, target_height)
        target_to_source_x = source_width / float(target_width)
        target_to_source_y = source_height / float(target_height)
        roi_source = (
            roi_target[0] * target_to_source_x,
            roi_target[1] * target_to_source_y,
            roi_target[2] * target_to_source_x,
            roi_target[3] * target_to_source_y,
        )
        previous_gray, analysis_scale = _resize_gray(
            cv2, first_frame, request.max_analysis_dimension,
        )
        original_polygon = _roi_polygon(roi_source, analysis_scale)
        points = _detect_features(cv2, previous_gray, original_polygon, request.max_features)
        minimum_features = 4 if mode == "point" else 6
        acquired_frame_index = start_frame
        acquisition_frames_skipped = 0
        acquisition_limit = min(
            end_frame,
            start_frame + max(1, int(round(source_fps * 1.5))),
        )
        while (
            (points is None or len(points) < minimum_features)
            and acquired_frame_index < acquisition_limit
        ):
            ok, candidate_frame = capture.read()
            if not ok or candidate_frame is None:
                break
            acquired_frame_index += 1
            acquisition_frames_skipped += 1
            candidate_gray, candidate_scale = _resize_gray(
                cv2,
                candidate_frame,
                request.max_analysis_dimension,
            )
            if abs(candidate_scale - analysis_scale) > 1e-6:
                break
            candidate_points = _detect_features(
                cv2,
                candidate_gray,
                original_polygon,
                request.max_features,
            )
            if candidate_points is not None and len(candidate_points) >= minimum_features:
                first_frame = candidate_frame
                previous_gray = candidate_gray
                points = candidate_points
                break
        if points is None or len(points) < minimum_features:
            raise ValueError(
                f"tracking source has too few features in the selected region ({0 if points is None else len(points)})"
            )
        initial_feature_count = len(points)

        timeline_start_ms = start_ms if request.timeline_start_ms is None else int(request.timeline_start_ms)
        timeline_time_scale = max(1e-6, abs(float(request.timeline_time_scale or 1.0)))
        origin = (
            roi_target[0] + roi_target[2] * 0.5,
            roi_target[1] + roi_target[3] * 0.5,
        )
        cumulative_analysis = np.eye(3, dtype=np.float64)
        cumulative_translation_target = np.zeros(2, dtype=np.float64)
        samples = [MotionTrackSample(time_ms=timeline_start_ms)]
        next_sample_source_ms = start_ms + max(1, int(request.sample_interval_ms))
        analyzed_frames = 1
        failed_frames = 0
        motion_outlier_frames = 0
        shot_cut_frames = 0
        terminated_reason = ""
        actual_end_ms = start_ms
        confidence_total = 1.0
        confidence_count = 1
        awaiting_reacquire = False
        reacquired_frames = 0
        predicted_frames = 0
        consecutive_failed_frames = 0
        last_point_delta_analysis = np.zeros(2, dtype=np.float64)
        last_point_delta_target = np.zeros(2, dtype=np.float64)
        target_diagonal = float(target_width * target_width + target_height * target_height) ** 0.5
        maximum_prediction_steps = max(
            1,
            int(round(source_fps * 0.5 / frame_stride)),
        )
        current_frame_index = acquired_frame_index

        if progress is not None:
            progress(0, total_steps)
        step_index = 0
        while current_frame_index < end_frame:
            if cancelled is not None and cancelled():
                raise MotionTrackingCancelled("motion tracking was cancelled")
            target_frame_index = min(end_frame, current_frame_index + frame_stride)
            decode_ok = True
            for _index in range(current_frame_index + 1, target_frame_index):
                if cancelled is not None and cancelled():
                    raise MotionTrackingCancelled("motion tracking was cancelled")
                if not capture.grab():
                    decode_ok = False
                    break
            ok, current_frame = capture.read() if decode_ok else (False, None)
            if not ok or current_frame is None:
                break
            current_frame_index = target_frame_index
            current_gray, current_scale = _resize_gray(
                cv2, current_frame, request.max_analysis_dimension,
            )
            if abs(current_scale - analysis_scale) > 1e-6:
                raise ValueError("tracking source changed dimensions during analysis")
            source_time_ms = min(end_ms, int(round(current_frame_index * 1000.0 / source_fps)))
            actual_end_ms = source_time_ms
            if _is_scene_cut(cv2, previous_gray, current_gray):
                failed_frames += 1
                shot_cut_frames += 1
                analyzed_frames += 1
                terminated_reason = "shot_cut"
                output_time_ms = timeline_start_ms + int(round(
                    max(0, source_time_ms - start_ms) / timeline_time_scale
                ))
                if mode == "point":
                    sample = _translation_sample(cumulative_translation_target, output_time_ms, 0.0)
                else:
                    analysis_to_target = np.diag([
                        1.0 / analysis_scale / target_to_source_x,
                        1.0 / analysis_scale / target_to_source_y,
                        1.0,
                    ])
                    cumulative_target = (
                        analysis_to_target @ cumulative_analysis @ np.linalg.inv(analysis_to_target)
                    )
                    sample = _matrix_sample(cumulative_target, origin, output_time_ms, 0.0)
                if sample.time_ms > samples[-1].time_ms:
                    samples.append(sample)
                    confidence_count += 1
                if progress is not None:
                    progress(min(step_index + 1, total_steps), total_steps)
                break
            previous_good, current_good, median_fb_error = _track_features(
                cv2, previous_gray, current_gray, points,
            )
            confidence = 0.0
            transform_valid = previous_good is not None and len(previous_good) >= minimum_features
            inlier_ratio = 0.0
            if transform_valid and mode == "point":
                delta_analysis = np.median(current_good - previous_good, axis=0)
                delta_target = np.asarray([
                    delta_analysis[0] / analysis_scale / target_to_source_x,
                    delta_analysis[1] / analysis_scale / target_to_source_y,
                ])
                transform_valid = (
                    np.linalg.norm(delta_target)
                    <= target_diagonal * 0.04
                )
                if not transform_valid:
                    motion_outlier_frames += 1
                if transform_valid:
                    last_point_delta_analysis = np.asarray(
                        delta_analysis,
                        dtype=np.float64,
                    )
                    last_point_delta_target = delta_target
                    cumulative_translation_target += delta_target
                    cumulative_analysis[0, 2] += float(delta_analysis[0])
                    cumulative_analysis[1, 2] += float(delta_analysis[1])
                    inlier_ratio = min(
                        1.0,
                        len(current_good) / max(1.0, float(initial_feature_count)),
                    )
            elif transform_valid:
                step_matrix, inliers = cv2.estimateAffinePartial2D(
                    previous_good,
                    current_good,
                    method=cv2.RANSAC,
                    ransacReprojThreshold=3.0,
                    maxIters=2000,
                    confidence=0.995,
                    refineIters=10,
                )
                transform_valid = step_matrix is not None and inliers is not None
                if transform_valid:
                    inlier_ratio = float(np.count_nonzero(inliers)) / max(1.0, float(len(inliers)))
                    transform_valid = inlier_ratio >= 0.35
                    if transform_valid:
                        step_homogeneous = np.eye(3, dtype=np.float64)
                        step_homogeneous[:2] = np.asarray(step_matrix, dtype=np.float64)
                        cumulative_analysis = step_homogeneous @ cumulative_analysis
            if transform_valid:
                if awaiting_reacquire:
                    reacquired_frames += 1
                    awaiting_reacquire = False
                consecutive_failed_frames = 0
                feature_ratio = min(1.0, len(current_good) / max(12.0, float(initial_feature_count)))
                confidence = feature_ratio * max(0.0, min(1.0, inlier_ratio)) * exp(-median_fb_error / 2.5)
                points = current_good.reshape(-1, 1, 2).astype(np.float32)
            else:
                failed_frames += 1
                points = None
                awaiting_reacquire = True
                consecutive_failed_frames += 1
                if (
                    mode == "point"
                    and consecutive_failed_frames <= maximum_prediction_steps
                    and np.linalg.norm(last_point_delta_target) > 1e-6
                    and np.linalg.norm(last_point_delta_target)
                    <= target_diagonal * 0.025
                ):
                    cumulative_analysis[0, 2] += last_point_delta_analysis[0]
                    cumulative_analysis[1, 2] += last_point_delta_analysis[1]
                    cumulative_translation_target += last_point_delta_target
                    predicted_frames += 1

            analyzed_frames += 1
            step_index += 1
            output_time_ms = timeline_start_ms + int(round(
                max(0, source_time_ms - start_ms) / timeline_time_scale
            ))
            should_sample = source_time_ms >= next_sample_source_ms or current_frame_index >= end_frame
            if should_sample:
                if mode == "point":
                    sample = _translation_sample(cumulative_translation_target, output_time_ms, confidence)
                else:
                    analysis_to_target = np.diag([
                        1.0 / analysis_scale / target_to_source_x,
                        1.0 / analysis_scale / target_to_source_y,
                        1.0,
                    ])
                    target_to_analysis = np.linalg.inv(analysis_to_target)
                    cumulative_target = analysis_to_target @ cumulative_analysis @ target_to_analysis
                    sample = _matrix_sample(cumulative_target, origin, output_time_ms, confidence)
                if sample.time_ms > samples[-1].time_ms:
                    samples.append(sample)
                    confidence_total += sample.confidence
                    confidence_count += 1
                while next_sample_source_ms <= source_time_ms:
                    next_sample_source_ms += max(1, int(request.sample_interval_ms))

            refresh_polygon = _transform_polygon(cv2, original_polygon, cumulative_analysis)
            if points is None or len(points) < max(minimum_features * 2, initial_feature_count // 3) or step_index % 15 == 0:
                refreshed = _detect_features(
                    cv2, current_gray, refresh_polygon, request.max_features,
                )
                if refreshed is not None and len(refreshed) >= minimum_features:
                    points = refreshed
                    initial_feature_count = max(initial_feature_count, len(refreshed))
            previous_gray = current_gray
            if progress is not None:
                progress(min(step_index, total_steps), total_steps)

        if len(samples) < 2:
            raise ValueError("tracking analysis did not produce enough samples")
        effective_analysis_fps = source_fps / frame_stride
        metadata = {
            "provider": "opencv_lk_ransac_v1",
            "source_uri": str(path),
            "source_width": int(source_width),
            "source_height": int(source_height),
            "target_width": int(target_width),
            "target_height": int(target_height),
            "source_fps": float(source_fps),
            "analysis_fps": float(effective_analysis_fps),
            "frame_stride": int(frame_stride),
            "start_ms": int(start_ms),
            "end_ms": int(end_ms),
            "timeline_start_ms": int(timeline_start_ms),
            "timeline_time_scale": float(timeline_time_scale),
            "sample_interval_ms": int(request.sample_interval_ms),
            "roi": [float(value) for value in roi_target],
            "analyzed_frames": int(analyzed_frames),
            "failed_frames": int(failed_frames),
            "motion_outlier_frames": int(motion_outlier_frames),
            "acquisition_frames_skipped": int(acquisition_frames_skipped),
            "reacquired_frames": int(reacquired_frames),
            "predicted_frames": int(predicted_frames),
            "shot_cut_frames": int(shot_cut_frames),
            "actual_end_ms": int(actual_end_ms),
            "terminated_reason": terminated_reason,
            "mean_confidence": float(confidence_total / max(1, confidence_count)),
        }
        return MotionTrackingCache(
            mode=mode,
            enabled=True,
            origin=origin,
            samples=samples,
            source_revision=_source_revision(path),
            metadata=metadata,
        )
    finally:
        capture.release()
