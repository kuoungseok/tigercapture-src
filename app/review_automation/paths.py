from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW_ROOT_ENV = "TIGERCAPTURE_REVIEW_ROOT"
REVIEW_VIDEO_SOURCE_ENV = "TIGERCAPTURE_REVIEW_VIDEO_SOURCE_DIR"


def default_review_root(project_root: str | Path = ROOT) -> Path:
    raw = os.environ.get(REVIEW_ROOT_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    root = Path(project_root).resolve()
    return root.parent / "ReviewAutomationWorkspace"


def default_review_video_source_dir() -> Path:
    raw = os.environ.get(REVIEW_VIDEO_SOURCE_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / "Videos" / "TigerCapture" / "YouTube Imports"


def review_paths(
    review_root: str | Path | None = None,
    *,
    project_root: str | Path = ROOT,
) -> dict[str, Path]:
    root = Path(review_root).expanduser() if review_root is not None else default_review_root(project_root)
    samples = root / "samples"
    outputs = root / "outputs"
    qa = root / "qa"
    return {
        "root": root,
        "samples": samples,
        "sample_manifest": samples / "manifest.json",
        "outputs": outputs,
        "report": outputs / "review_report.json",
        "qa": qa,
        "sample_report": qa / "review_sample_resources_qa.json",
        "qa_report": qa / "review_automation_qa.json",
    }


DEFAULT_REVIEW_ROOT = review_paths()["root"]
DEFAULT_REVIEW_SAMPLE_ROOT = review_paths()["samples"]
DEFAULT_REVIEW_SAMPLE_MANIFEST = review_paths()["sample_manifest"]
DEFAULT_REVIEW_OUTPUT_DIR = review_paths()["outputs"]
DEFAULT_REVIEW_REPORT = review_paths()["report"]
DEFAULT_REVIEW_QA_DIR = review_paths()["qa"]
DEFAULT_REVIEW_SAMPLE_REPORT = review_paths()["sample_report"]
DEFAULT_REVIEW_QA_REPORT = review_paths()["qa_report"]
DEFAULT_REVIEW_VIDEO_SOURCE_DIR = default_review_video_source_dir()
