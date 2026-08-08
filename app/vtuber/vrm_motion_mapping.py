"""Coordinate conversion helpers for source tracking -> VRM pose."""
from __future__ import annotations

from typing import Any


VRM_MOTION_MAPPING_SCHEMA = "tigerstudio.vtuber.vrm_motion_mapping.v1"
VRM_PITCH_SIGN = -1.0
VRM_REST_PITCH_BIAS_DEG = -12.0


def source_pitch_to_vrm_pitch(pitch_deg: Any, *, rest_bias_deg: float = VRM_REST_PITCH_BIAS_DEG) -> float:
    """Convert source tracker pitch into TigerCapture's VRM pose X rotation.

    OpenSeeFace pitch is stored as source motion.  The internal VRM/MToon pose
    path uses the opposite X-rotation convention, so applying source pitch
    directly can make a down-looking source look like the avatar leans back.
    The rest bias keeps the avatar slightly forward because broadcast/talking
    head sources often start already looking down, which neutral calibration can
    otherwise erase.
    """
    try:
        return float(pitch_deg) * VRM_PITCH_SIGN + float(rest_bias_deg)
    except (TypeError, ValueError):
        return float(rest_bias_deg)


def vrm_motion_mapping_contract() -> dict[str, Any]:
    return {
        "schema": VRM_MOTION_MAPPING_SCHEMA,
        "source": "OpenSeeFace source motion",
        "target": "TigerCapture VRM/MToon pose",
        "pitch": {
            "source_channel": "pitch_deg",
            "target_rotation_axis": "x",
            "sign": VRM_PITCH_SIGN,
            "rest_bias_deg": VRM_REST_PITCH_BIAS_DEG,
            "reason": "match visual down/up pitch direction in VRM coordinate space",
        },
    }
