"""Known MMD material/render regression profiles."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]

_PROFILES: dict[str, dict[str, Any]] = {
    "cantarella_wavefile_cloth_motion": {
        "id": "cantarella_wavefile_cloth_motion",
        "label": "Cantarella + Wavefile cloth/hair motion",
        "model_path": "local_resources/mmd/model_pool/playable/flashy_girls/wuthering_waves/Cantarella/Cantarella.pmx",
        "motion_path": "local_resources/mmd/model_pool/motions/validated/wavefile_v2_arora_14.vmd",
        "capture": {
            "out": "debugCapture/mmd_player/regression/cantarella_wavefile_cloth_motion.png",
            "report_out": "debugCapture/mmd_player/regression/cantarella_wavefile_cloth_motion.json",
            "lighting": "studio_soft",
            "bloom": 0.35,
            "yaw": 0.0,
            "zoom": 0.92,
            "offset_x": 0.0,
            "offset_y": -0.02,
            "time_ms": 2600,
            "pause": True,
        },
        "physics_expectations": {
            "active_rigid_body_count": {"min": 200},
            "secondary_candidate_count": {"min": 200},
            "probe_rotation_bone_count": {"min": 200},
            "probe_max_rotation_degrees": {"min": 1.0},
        },
        "report_expectations": [
            {"path": "animation.max_pose_delta", "min": 1.0},
            {"path": "animation.max_active_bones", "min": 40},
            {"path": "animation.max_active_ik", "min": 1},
            {"path": "animation.max_physics_bodies", "min": 100},
            {"path": "motion_policy.bone_track_count", "min": 80},
            {"path": "motion_policy.nonlinear_curve_count", "min": 100},
        ],
    },
    "zzz_alice_sea_of_thyme": {
        "id": "zzz_alice_sea_of_thyme",
        "label": "ZZZ Alice - Sea of Thyme face/hair transparency",
        "model_path": "local_resources/mmd/model_pool/playable/flashy_girls/zzz/Alice_Skin/Alice - Sea of Thyme/Alice - Sea of Thyme.pmx",
        "capture": {
            "out": "debugCapture/mmd_player/regression/zzz_alice_sea_of_thyme.png",
            "report_out": "debugCapture/mmd_player/regression/zzz_alice_sea_of_thyme.json",
            "lighting": "studio_soft",
            "bloom": 0.35,
            "yaw": 0.0,
            "zoom": 1.10,
            "offset_x": 0.0,
            "offset_y": -0.03,
            "time_ms": 0,
            "pause": True,
        },
        "expectations": [
            {
                "name": "\u524d\u9aea",
                "material_class_name": "hair",
                "render_bucket_name": "opaque",
                "uv_alpha_mode": "opaque",
                "edge_enabled": False,
                "depth_write": True,
                "casts_self_shadow": True,
                "receives_self_shadow": True,
            },
            {
                "name": "\u9aee+",
                "material_class_name": "hair",
                "render_bucket_name": "transparent",
                "uv_alpha_mode": "blend",
                "edge_enabled": False,
                "depth_write": False,
                "casts_self_shadow": False,
                "receives_self_shadow": False,
            },
            {
                "name": "\u76ee\u5f71",
                "render_bucket_name": "transparent",
                "face_layer_priority": 30,
                "edge_enabled": False,
                "alpha": {"max": 0.23},
                "casts_self_shadow": False,
                "receives_self_shadow": False,
            },
            {
                "name": "\u76ee",
                "material_class_name": "eye",
                "render_bucket_name": "transparent",
                "face_layer_priority": 40,
                "edge_enabled": False,
                "casts_self_shadow": False,
                "receives_self_shadow": False,
            },
            {
                "name": "\u76ee\u5149",
                "material_class_name": "eye",
                "render_bucket_name": "transparent",
                "face_layer_priority": 60,
                "edge_enabled": False,
                "emissive_strength": {"min": 0.50},
                "alpha": {"max": 0.25},
                "casts_self_shadow": False,
                "receives_self_shadow": False,
            },
            {
                "name": "\u776b\u7709",
                "render_bucket_name": "transparent",
                "face_layer_priority": 70,
                "edge_enabled": False,
                "casts_self_shadow": False,
                "receives_self_shadow": False,
            },
        ],
        "physics_expectations": {
            "active_rigid_body_count": {"min": 100},
            "secondary_candidate_count": {"min": 100},
            "probe_rotation_bone_count": {"min": 80},
            "probe_max_rotation_degrees": {"min": 1.0},
        },
    },
}


def mmd_regression_profile_ids() -> tuple[str, ...]:
    return tuple(sorted(_PROFILES))


def mmd_regression_profile(profile_id: str) -> dict[str, Any]:
    key = str(profile_id or "").strip()
    if key not in _PROFILES:
        raise KeyError(f"unknown MMD regression profile: {profile_id}")
    return deepcopy(_PROFILES[key])


def mmd_regression_profile_model_path(profile_id: str) -> Path:
    profile = mmd_regression_profile(profile_id)
    return (ROOT / str(profile.get("model_path") or "")).resolve()


def mmd_regression_profile_motion_path(profile_id: str) -> Path | None:
    profile = mmd_regression_profile(profile_id)
    motion_path = str(profile.get("motion_path") or "")
    if not motion_path:
        return None
    return (ROOT / motion_path).resolve()


def _render_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("render"), Mapping):
        rows = payload["render"].get("material_bucket_rows")  # type: ignore[index]
    elif isinstance(payload.get("diagnostics"), Mapping):
        rows = payload["diagnostics"].get("material_bucket_rows")  # type: ignore[index]
    else:
        rows = payload.get("material_bucket_rows")
    return [dict(row) for row in list(rows or []) if isinstance(row, Mapping)]


def _find_row(rows: list[dict[str, Any]], expectation: Mapping[str, Any]) -> dict[str, Any] | None:
    if "material_index" in expectation:
        wanted = int(expectation.get("material_index", -1) or -1)
        for row in rows:
            if int(row.get("material_index", -2) or -2) == wanted:
                return row
    wanted_name = str(expectation.get("name") or "")
    wanted_english = str(expectation.get("english_name") or "")
    for row in rows:
        if wanted_name and str(row.get("name") or "") == wanted_name:
            return row
        if wanted_english and str(row.get("english_name") or "") == wanted_english:
            return row
    return None


def _field_matches(actual: Any, expected: Any) -> tuple[bool, str]:
    if isinstance(expected, Mapping):
        try:
            value = float(actual)
        except Exception:
            return False, f"{actual!r} is not numeric"
        if "equals" in expected and value != float(expected["equals"]):
            return False, f"{value!r} != {float(expected['equals'])!r}"
        if "min" in expected and value < float(expected["min"]):
            return False, f"{value!r} < {float(expected['min'])!r}"
        if "max" in expected and value > float(expected["max"]):
            return False, f"{value!r} > {float(expected['max'])!r}"
        return True, ""
    if actual != expected:
        return False, f"{actual!r} != {expected!r}"
    return True, ""


def _payload_path(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for part in str(path or "").split("."):
        if not part:
            continue
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def evaluate_mmd_regression_profile(payload: Mapping[str, Any], profile_id: str) -> dict[str, Any]:
    profile = mmd_regression_profile(profile_id)
    rows = _render_rows(payload)
    checks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for expectation in list(profile.get("expectations") or []):
        if not isinstance(expectation, Mapping):
            continue
        row = _find_row(rows, expectation)
        label = str(expectation.get("name") or expectation.get("english_name") or expectation.get("material_index") or "")
        if row is None:
            failure = {"material": label, "field": "material", "reason": "missing_material"}
            failures.append(failure)
            checks.append({"ok": False, **failure})
            continue
        for field, expected in expectation.items():
            if field in {"name", "english_name", "material_index", "description"}:
                continue
            actual = row.get(str(field))
            ok, reason = _field_matches(actual, expected)
            check = {
                "ok": bool(ok),
                "material": label,
                "material_index": int(row.get("material_index", -1) or -1),
                "field": str(field),
                "actual": actual,
                "expected": expected,
            }
            if reason:
                check["reason"] = reason
            checks.append(check)
            if not ok:
                failures.append(check)
    for expectation in list(profile.get("report_expectations") or []):
        if not isinstance(expectation, Mapping):
            continue
        path = str(expectation.get("path") or "")
        if not path:
            continue
        expected = {key: value for key, value in expectation.items() if key not in {"path", "description"}}
        if not expected:
            continue
        actual = _payload_path(payload, path)
        ok, reason = _field_matches(actual, expected)
        check = {
            "ok": bool(ok),
            "material": "report",
            "material_index": -1,
            "field": path,
            "actual": actual,
            "expected": expected,
        }
        if reason:
            check["reason"] = reason
        checks.append(check)
        if not ok:
            failures.append(check)
    physics_policy = payload.get("physics_policy")
    if isinstance(physics_policy, Mapping):
        for field, expected in dict(profile.get("physics_expectations") or {}).items():
            actual = physics_policy.get(str(field))
            ok, reason = _field_matches(actual, expected)
            check = {
                "ok": bool(ok),
                "material": "physics_policy",
                "material_index": -1,
                "field": str(field),
                "actual": actual,
                "expected": expected,
            }
            if reason:
                check["reason"] = reason
            checks.append(check)
            if not ok:
                failures.append(check)
    return {
        "ok": not failures,
        "profile_id": str(profile.get("id") or profile_id),
        "label": str(profile.get("label") or profile_id),
        "material_count": int(len(rows)),
        "check_count": int(len(checks)),
        "failure_count": int(len(failures)),
        "checks": checks,
        "failures": failures,
    }
