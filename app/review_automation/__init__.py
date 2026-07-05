"""Review/demo automation helpers.

This package is intentionally separate from ordinary QA helpers. QA proves the
product works; review automation reuses that proof to produce stable demo
assets for screenshots, GIFs, decks, and web pages.
"""

from .dev_gate import require_review_automation_dev, review_automation_dev_enabled
from .paths import (
    DEFAULT_REVIEW_OUTPUT_DIR,
    DEFAULT_REVIEW_QA_REPORT,
    DEFAULT_REVIEW_ROOT,
    DEFAULT_REVIEW_SAMPLE_REPORT,
    DEFAULT_REVIEW_REPORT,
)
from .sample_resources import (
    DEFAULT_REVIEW_SAMPLE_MANIFEST,
    DEFAULT_REVIEW_SAMPLE_ROOT,
    ReviewSampleResource,
    build_default_review_sample_manifest,
    load_review_sample_manifest,
    review_sample_resource_report,
    write_review_sample_manifest,
)
from .registry import ReviewFeature, default_review_features, evaluate_review_features
from .qa import validate_review_automation_report
from .runner import build_review_automation_report
from .action_scenarios import run_action_review_scenario
from .live_runner import run_live_feature_action_captures, run_live_review_scenario
from .evidence_graph import build_review_evidence_graph, write_review_evidence_graph
from .scenario_manifest import ReviewScenario, default_review_scenarios, evaluate_review_scenarios
from .deck_modes import DECK_MODES, DECK_MODE_DESCRIPTIONS, DECK_MODE_LABELS, normalize_deck_mode

__all__ = [
    "DEFAULT_REVIEW_OUTPUT_DIR",
    "DEFAULT_REVIEW_QA_REPORT",
    "DEFAULT_REVIEW_REPORT",
    "DEFAULT_REVIEW_ROOT",
    "DEFAULT_REVIEW_SAMPLE_MANIFEST",
    "DEFAULT_REVIEW_SAMPLE_REPORT",
    "DEFAULT_REVIEW_SAMPLE_ROOT",
    "DECK_MODES",
    "DECK_MODE_DESCRIPTIONS",
    "DECK_MODE_LABELS",
    "ReviewFeature",
    "ReviewScenario",
    "ReviewSampleResource",
    "build_default_review_sample_manifest",
    "build_review_automation_report",
    "build_review_evidence_graph",
    "default_review_features",
    "default_review_scenarios",
    "evaluate_review_features",
    "evaluate_review_scenarios",
    "load_review_sample_manifest",
    "normalize_deck_mode",
    "require_review_automation_dev",
    "review_sample_resource_report",
    "review_automation_dev_enabled",
    "run_action_review_scenario",
    "run_live_feature_action_captures",
    "run_live_review_scenario",
    "validate_review_automation_report",
    "write_review_evidence_graph",
    "write_review_sample_manifest",
]
