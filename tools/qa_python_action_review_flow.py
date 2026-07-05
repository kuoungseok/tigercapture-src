from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wmv", ".gif"}


class _ReviewFlowPixmap:
    def __init__(self, index: int = 0) -> None:
        self.index = int(index)

    def save(self, path: str) -> bool:
        from PIL import Image, ImageDraw

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (320, 180), (22, 24, 34))
        draw = ImageDraw.Draw(image)
        accent = (255, 92, 68) if self.index % 2 == 0 else (130, 112, 255)
        draw.rounded_rectangle((18, 18, 302, 162), radius=16, outline=accent, width=4)
        draw.rectangle((42, 72, 278, 108), fill=(45, 50, 70))
        draw.text((54, 80), f"Tiger Studio Action QA #{self.index}", fill=(245, 246, 255))
        image.save(target)
        return True


class _ReviewFlowOwner:
    def __init__(self) -> None:
        from app.timeline_model import VideoTrack

        self._tracks = [VideoTrack(id=1)]
        self._audio_tracks = []
        self._timeline_markers = []
        self._selected_clips = []
        self._project_settings = {}
        self._action_imported_media: list[str] = []
        self._grab_index = 0
        self.changes: list[str] = []

    def _register_change(self, label: str = "") -> None:
        self.changes.append(str(label or ""))

    def _refresh_player_tracks(self) -> None:
        pass

    def _update_tracks_host_width(self) -> None:
        pass

    def _sync_markers_to_ruler(self) -> None:
        pass

    def grab(self) -> _ReviewFlowPixmap:
        self._grab_index += 1
        return _ReviewFlowPixmap(self._grab_index)


def find_sample_media(media_dir: str | Path, *, limit: int = 1) -> list[Path]:
    root = Path(media_dir)
    if not root.exists():
        return []
    rows = [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.casefold() in VIDEO_EXTS and not path.stem.endswith("_proxy")
    ]
    return rows[: max(1, int(limit or 1))]


def _step(registry: Any, action: str, params: dict[str, Any] | None = None, **flags: Any) -> dict[str, Any]:
    result = registry.execute(action, dict(params or {}), **flags).to_dict()
    return {"action": action, "params": dict(params or {}), **result}


def _write_review_flow_manifest(out_dir: Path, source: Path) -> Path:
    manifest_dir = out_dir / "review_samples"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "manifest.json"
    payload = {
        "schema_version": 1,
        "kind": "tigercapture_review_sample_resources",
        "sample_root": str(manifest_dir),
        "media_root": str(source.parent),
        "resources": [
            {
                "id": "overview_screen_demo",
                "kind": "video",
                "path": str(source),
                "role": "overview",
                "title": "Python action review flow sample",
                "required": True,
                "metadata": {"duration_ms": 3000, "frame_size": [320, 180], "fps": 10},
            }
        ],
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def run_action_review_flow(
    *,
    media_dir: str | Path = ROOT / "qa_corpus" / "assets",
    out_dir: str | Path = ROOT / "debugCapture" / "python_action_review_flow",
    limit: int = 1,
) -> dict[str, Any]:
    from app.actions import build_default_action_registry

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    media = find_sample_media(media_dir, limit=limit)
    if not media:
        report = {
            "kind": "python_action_review_flow_qa",
            "ok": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "media_dir": str(Path(media_dir)),
            "error": "no sample video media found",
            "steps": [],
        }
        (out / "python_action_review_flow_qa.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return report

    owner = _ReviewFlowOwner()
    registry = build_default_action_registry(owner)
    source = media[0]
    manifest_path = _write_review_flow_manifest(out, source)
    steps: list[dict[str, Any]] = []

    imported = _step(
        registry,
        "media.import_to_timeline",
        {"path": str(source), "kind": "video", "track_id": 1, "at_ms": 0, "duration_ms": 3000},
    )
    steps.append(imported)
    clip_id = int((imported.get("result") or {}).get("clip_id") or 0)

    if imported.get("ok") and clip_id:
        steps.extend(
            [
                _step(registry, "timeline.split", {"track_id": 1, "at_ms": 1500}),
                _step(registry, "clip.set_speed", {"track_id": 1, "clip_id": clip_id, "speed": 1.15}),
                _step(
                    registry,
                    "clip.set_filter",
                    {"track_id": 1, "clip_id": clip_id, "params": {"sharpen": 0.25, "vignette": 0.15}},
                ),
                _step(
                    registry,
                    "clip.set_color_grade",
                    {"track_id": 1, "clip_id": clip_id, "grade": {"brightness": 6, "contrast": 8, "saturation": 5}},
                ),
                _step(
                    registry,
                    "text.add",
                    {
                        "track_id": 1,
                        "clip_id": clip_id,
                        "text": "Action Review",
                        "start_ms": 0,
                        "end_ms": 1200,
                        "style": {"position_x": 0.5, "position_y": 0.18},
                    },
                ),
                _step(registry, "capture.screenshot", {"path": str(out / "action_review.png")}),
                _step(registry, "capture.gif", {"path": str(out / "action_review.gif"), "duration_ms": 1, "fps": 1}),
                _step(
                    registry,
                    "review.scenario.run",
                    {
                        "scenario": "summary",
                        "params": {
                            "project_root": str(ROOT),
                            "out_dir": str(out / "review_automation"),
                            "report_path": str(out / "review_automation" / "review_report.json"),
                            "sample_manifest": str(manifest_path),
                            "write_html": False,
                            "write_ppt": False,
                        },
                    },
                ),
            ]
        )

    artifacts = [
        {"kind": "screenshot", "path": str(out / "action_review.png"), "exists": (out / "action_review.png").exists()},
        {"kind": "gif", "path": str(out / "action_review.gif"), "exists": (out / "action_review.gif").exists()},
        {
            "kind": "review_report",
            "path": str(out / "review_automation" / "review_report.json"),
            "exists": (out / "review_automation" / "review_report.json").exists(),
        },
    ]
    report = {
        "kind": "python_action_review_flow_qa",
        "ok": all(bool(step.get("ok")) for step in steps) and all(bool(row.get("exists")) for row in artifacts),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "media_dir": str(Path(media_dir)),
        "source": str(source),
        "action_count": len(steps),
        "registered_action_count": len(registry.specs()),
        "steps": steps,
        "artifacts": artifacts,
        "changes": list(owner.changes),
    }
    (out / "python_action_review_flow_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Tiger Studio Python Action System review flow.")
    parser.add_argument("--media-dir", default=str(ROOT / "qa_corpus" / "assets"))
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "python_action_review_flow"))
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    report = run_action_review_flow(media_dir=args.media_dir, out_dir=args.out, limit=args.limit)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
