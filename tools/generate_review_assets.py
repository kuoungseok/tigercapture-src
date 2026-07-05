from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.review_automation.dev_gate import require_review_automation_dev
from app.review_automation.paths import DEFAULT_REVIEW_ROOT, DEFAULT_REVIEW_VIDEO_SOURCE_DIR, review_paths


def _sample_resource_path(sample_report: dict[str, Any], resource_id: str) -> Path | None:
    for row in list(sample_report.get("resources", []) or []):
        if not isinstance(row, dict):
            continue
        if str(row.get("id") or "") != resource_id:
            continue
        raw = Path(str(row.get("path") or ""))
        path = raw if raw.is_absolute() else ROOT / raw
        return path if path.exists() else None
    return None


def _run_editor_capture(*, import_media: Path, review_out_dir: Path, sample_manifest: Path) -> None:
    cmd = [
        sys.executable or "python",
        "tools/qa_editor_e2e_smoke.py",
        "--out-dir",
        "debugCapture/editor_e2e_smoke",
        "--report",
        "debugCapture/editor_e2e_smoke_report.json",
        "--import-media",
        str(import_media),
        "--catalog-capture",
        "--live-feature-captures",
        "--review-out-dir",
        str(review_out_dir),
        "--sample-manifest",
        str(sample_manifest),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def generate_review_assets(args: argparse.Namespace) -> dict[str, Any]:
    require_review_automation_dev(ROOT)

    from tools.prepare_review_sample_resources import prepare_review_sample_resources

    from app.review_automation.action_scenarios import run_action_review_scenario
    from app.review_automation.runner import build_review_automation_report

    sample_report = prepare_review_sample_resources(
        args.sample_root,
        force=bool(args.force),
        media=not bool(args.manifest_only),
        video_source_dir=None if args.synthetic_video else args.video_source_dir,
        allow_synthetic_video=bool(args.synthetic_video),
    )
    args.sample_report.parent.mkdir(parents=True, exist_ok=True)
    args.sample_report.write_text(json.dumps(sample_report, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = args.sample_root / "manifest.json"
    if not bool(args.manifest_only) and not bool(getattr(args, "skip_editor_capture", False)):
        import_media = _sample_resource_path(sample_report, "overview_screen_demo")
        if import_media is None:
            raise RuntimeError(
                "No real YouTube Imports review video is available. "
                "Put a video under the review video source folder or pass --synthetic-video for explicit test media."
            )
        _run_editor_capture(
            import_media=import_media,
            review_out_dir=args.out_dir,
            sample_manifest=manifest_path,
        )
    run_action_review_scenario(
        project_root=ROOT,
        out_dir=args.out_dir,
        sample_manifest=manifest_path,
        scenario=str(args.deck_mode),
        force=bool(args.force),
    )

    return build_review_automation_report(
        project_root=ROOT,
        out_dir=args.out_dir,
        report_path=args.report,
        sample_manifest=manifest_path,
        write_html=not bool(args.skip_html),
        write_ppt=not bool(args.skip_ppt),
        deck_mode=str(args.deck_mode),
        force=bool(args.force),
    )


def _generation_outputs_ready(report: dict[str, Any], *, skip_html: bool = False, skip_ppt: bool = False) -> bool:
    outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
    required: list[Path] = []
    if not skip_html:
        html = outputs.get("html")
        if html:
            required.append(Path(str(html)))
    if not skip_ppt:
        pptx = outputs.get("pptx")
        if pptx:
            required.append(Path(str(pptx)))
    artifacts = [
        row for row in list(report.get("artifacts", []) or [])
        if isinstance(row, dict) and (bool(row.get("ready")) or bool(row.get("exists")))
    ]
    if not required and not artifacts:
        return bool(report.get("ok"))
    return all(path.exists() for path in required) and bool(artifacts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate TigerCapture review automation assets.")
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--sample-root", type=Path, default=None)
    parser.add_argument("--sample-report", type=Path, default=None)
    parser.add_argument("--video-source-dir", type=Path, default=DEFAULT_REVIEW_VIDEO_SOURCE_DIR)
    parser.add_argument("--synthetic-video", action="store_true", help="Ignore imported videos and generate deterministic synthetic clips.")
    parser.add_argument("--skip-editor-capture", action="store_true", help="Skip live editor import/capture. Internal debugging only; public review decks should not use this.")
    parser.add_argument("--run-qa", action="store_true", help="Deprecated alias. Editor capture now runs by default unless --skip-editor-capture is passed.")
    parser.add_argument("--skip-html", action="store_true")
    parser.add_argument("--skip-ppt", action="store_true")
    parser.add_argument(
        "--strict-report-ok",
        action="store_true",
        help="Return exit code 1 when the product-readiness report is not fully OK. By default, generation succeeds if review outputs were written.",
    )
    parser.add_argument(
        "--deck-mode",
        choices=("summary", "detailed", "evidence-full"),
        default="summary",
        help="PPTX depth: summary, detailed, or evidence-full.",
    )
    parser.add_argument("--manifest-only", action="store_true", help="Only write sample manifest, then generate a missing-resource report.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    paths = review_paths(args.review_root)
    args.out_dir = args.out_dir or paths["outputs"]
    args.report = args.report or paths["report"]
    args.sample_root = args.sample_root or paths["samples"]
    args.sample_report = args.sample_report or paths["sample_report"]

    try:
        report = generate_review_assets(args)
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if bool(args.strict_report_ok):
        return 0 if report.get("ok") else 1
    return 0 if _generation_outputs_ready(report, skip_html=bool(args.skip_html), skip_ppt=bool(args.skip_ppt)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
