"""Feature gates for CapCut-style creator extensions.

CapCut-style creator extensions are enabled by default. Set
``TIGERCAPTURE_CAPCUT_DISABLED=1`` to disable them globally, or override an
individual route with ``TIGERCAPTURE_CAPCUT_<FEATURE>_ENABLED=0``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable


CAPCUT_GLOBAL_ENV = "TIGERCAPTURE_CAPCUT_ENABLED"
CAPCUT_GLOBAL_DISABLED_ENV = "TIGERCAPTURE_CAPCUT_DISABLED"


@dataclass(frozen=True)
class CapCutFeature:
    id: str
    label: str
    env_name: str


CAPCUT_FEATURES: tuple[CapCutFeature, ...] = (
    CapCutFeature("local_ml", "Local ML media analysis", "TIGERCAPTURE_CAPCUT_LOCAL_ML_ENABLED"),
    CapCutFeature("creator_assist", "Creator Assist panel", "TIGERCAPTURE_CAPCUT_CREATOR_ASSIST_ENABLED"),
    CapCutFeature("apply_bundle", "CapCut apply bundle/project mutation", "TIGERCAPTURE_CAPCUT_APPLY_BUNDLE_ENABLED"),
    CapCutFeature("template_auto_apply", "CapCut template auto-apply", "TIGERCAPTURE_CAPCUT_TEMPLATE_AUTO_APPLY_ENABLED"),
    CapCutFeature("qa", "CapCut QA/report integration", "TIGERCAPTURE_CAPCUT_QA_ENABLED"),
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _falsey(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"0", "false", "no", "off", "disabled"}


def _feature(feature_id: str) -> CapCutFeature | None:
    key = str(feature_id or "").strip().lower().replace("-", "_")
    for feature in CAPCUT_FEATURES:
        if feature.id == key:
            return feature
    return None


def capcut_global_enabled() -> bool:
    if _truthy(os.environ.get(CAPCUT_GLOBAL_DISABLED_ENV)):
        return False
    value = os.environ.get(CAPCUT_GLOBAL_ENV)
    if value is None:
        return True
    return _truthy(value) and not _falsey(value)


def capcut_feature_enabled(feature_id: str) -> bool:
    feature = _feature(feature_id)
    if feature is None:
        return capcut_global_enabled()
    value = os.environ.get(feature.env_name)
    if value is not None:
        return _truthy(value) and not _falsey(value)
    return capcut_global_enabled()


def capcut_feature_disabled(feature_id: str) -> bool:
    return not capcut_feature_enabled(feature_id)


def capcut_disabled_reason(feature_id: str) -> str:
    feature = _feature(feature_id)
    label = feature.label if feature is not None else str(feature_id)
    env = feature.env_name if feature is not None else f"TIGERCAPTURE_CAPCUT_{str(feature_id).upper()}_ENABLED"
    return f"{label} is disabled by feature gate. Set {env}=1 or clear {CAPCUT_GLOBAL_DISABLED_ENV} to enable."


def capcut_status_rows(features: Iterable[str] | None = None) -> list[dict[str, object]]:
    ids = list(features or [feature.id for feature in CAPCUT_FEATURES])
    rows: list[dict[str, object]] = []
    for feature_id in ids:
        feature = _feature(feature_id)
        rows.append(
            {
                "id": feature_id,
                "label": feature.label if feature is not None else feature_id,
                "enabled": capcut_feature_enabled(feature_id),
                "env_name": feature.env_name if feature is not None else "",
            }
        )
    return rows
