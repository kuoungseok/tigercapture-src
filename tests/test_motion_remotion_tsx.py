from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QImage

from app.motion_designer.adapters.remotion_tsx import render_remotion_tsx
from app.motion_designer.remotion_tsx import (
    REMOTION_TSX_SOURCE_KIND,
    create_remotion_tsx_layer,
    inspect_remotion_tsx,
    remotion_tsx_runtime_status,
    sync_runtime_scaffold,
)
from app.motion_designer.schema import MotionComposition
from app.motion_designer.validation import validate_composition


class _ActionOwner:
    def __init__(self) -> None:
        self._motion_compositions = {}


SAMPLE = '''
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
export default function Sample() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const x = interpolate(frame, [0, fps], [0, 100]);
  const scale = spring({frame, fps});
  return <div style={{transform: `translateX(${x}px) scale(${scale})`}}>TSX</div>;
}
'''


def test_inspection_preserves_source_and_reports_supported_contract(tmp_path: Path) -> None:
    source = tmp_path / "sample.tsx"
    source.write_text(SAMPLE, encoding="utf-8")

    report = inspect_remotion_tsx(source)

    assert report.ok is True
    assert report.imports == ("remotion",)
    assert {"interpolate", "spring", "useCurrentFrame", "useVideoConfig"}.issubset(report.hooks)
    assert source.read_text(encoding="utf-8") == SAMPLE
    assert report.to_dict()["source_preserved"] is True


def test_external_import_is_reported_without_executing_source(tmp_path: Path) -> None:
    source = tmp_path / "unsafe.tsx"
    source.write_text(
        'import widget from "unknown-runtime"; export default () => <div>{widget}</div>;',
        encoding="utf-8",
    )

    report = inspect_remotion_tsx(source)

    assert report.ok is False
    assert report.unsupported_imports == ("unknown-runtime",)


def test_linked_layer_uses_cache_only_while_source_hash_matches(tmp_path: Path) -> None:
    source = tmp_path / "sample.tsx"
    source.write_text(SAMPLE, encoding="utf-8")
    inspection = inspect_remotion_tsx(source)
    frames = tmp_path / "frames"
    frames.mkdir()
    image = QImage(64, 32, QImage.Format_RGBA8888)
    image.fill(QColor("#ef476f"))
    assert image.save(str(frames / "frame_000000.png"), "PNG")
    layer = create_remotion_tsx_layer(
        source,
        width=64,
        height=32,
        fps=30,
        duration_ms=1000,
        prepared={
            "job_key": "test",
            "frame_dir": str(frames),
            "duration_frames": 1,
            "source_sha256": inspection.source_sha256,
        },
    )

    rendered = render_remotion_tsx(layer, 0)
    assert rendered.width() == 64 and rendered.height() == 32
    source.write_text(SAMPLE + "\n// changed", encoding="utf-8")
    stale = render_remotion_tsx(layer, 0)
    assert stale.width() == 1 and stale.height() == 1


def test_validation_warns_when_linked_preview_is_stale(tmp_path: Path) -> None:
    source = tmp_path / "sample.tsx"
    source.write_text(SAMPLE, encoding="utf-8")
    layer = create_remotion_tsx_layer(
        source, width=1280, height=720, fps=30, duration_ms=1000,
    )
    layer.source.params["prepared_source_sha256"] = "old"
    composition = MotionComposition(duration_ms=1000, layers=[layer])

    report = validate_composition(composition)

    assert report.ok is True
    assert any(issue.code == "stale_remotion_tsx_preview" for issue in report.issues)


def test_runtime_scaffold_is_copyable_without_installing_packages(tmp_path: Path) -> None:
    root = sync_runtime_scaffold(tmp_path / "runtime")
    status = remotion_tsx_runtime_status(root)

    assert (root / "build.mjs").is_file()
    assert (root / "shim-remotion.tsx").is_file()
    assert status["installed"] is False
    assert status["remotion_dependency"] is False
    assert REMOTION_TSX_SOURCE_KIND == "remotion_tsx"


def test_prepare_reuses_complete_frame_cache(tmp_path: Path, monkeypatch) -> None:
    import app.motion_designer.remotion_tsx as remotion_tsx

    frames = tmp_path / "frames"
    frames.mkdir()
    for index in range(2):
        (frames / f"frame_{index:06d}.png").write_bytes(b"cached")
    manifest = {
        "frame_dir": str(frames),
        "duration_frames": 2,
        "source_sha256": "hash",
    }
    monkeypatch.setattr(
        remotion_tsx,
        "build_remotion_tsx_page",
        lambda *_args, **_kwargs: dict(manifest),
    )
    monkeypatch.setattr(
        remotion_tsx.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("renderer ran")),
    )

    report = remotion_tsx.prepare_remotion_tsx_frames("unused.tsx", trusted=True)

    assert report["cache_reused"] is True
    assert report["frame_count"] == 2


def test_actions_link_source_without_executing_or_rewriting_it(tmp_path: Path) -> None:
    from app.actions.registry import ActionRegistry

    source = tmp_path / "linked.tsx"
    source.write_text(SAMPLE, encoding="utf-8")
    owner = _ActionOwner()
    registry = ActionRegistry(owner)
    specs = {row["id"] for row in registry.list_actions()}
    assert {
        "motion.remotion_tsx.runtime.status",
        "motion.remotion_tsx.runtime.install",
        "motion.remotion_tsx.inspect",
        "motion.remotion_tsx.import",
        "motion.remotion_tsx.refresh",
    }.issubset(specs)

    created = registry.execute("motion.composition.create", {
        "name": "Linked TSX",
        "width": 640,
        "height": 360,
        "duration_ms": 10000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    imported = registry.execute("motion.remotion_tsx.import", {
        "composition_id": composition_id,
        "path": str(source),
        "prepare_preview": False,
    })
    assert imported.ok
    assert imported.result["source_preserved"] is True
    assert imported.result["prepared"] is False
    assert source.read_text(encoding="utf-8") == SAMPLE
    layer = owner._motion_compositions[composition_id].layers[0]
    assert layer.source.uri == str(source.resolve())
    assert layer.source.metadata["linked_source"] is True
    assert layer.out_ms == 5000
