from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX_PATH = ROOT / "docs" / "UI_RENEWAL_EVIDENCE_INDEX.md"


@dataclass(frozen=True)
class UIEvidenceRecord:
    feature_area: str
    source: str
    artifact: Path
    review_use: str

    @property
    def exists(self) -> bool:
        return self.artifact.exists() and self.artifact.is_file()


TOPIC_TO_FEATURE_AREA: dict[str, str] = {
    # Some review topics predate the renewed feature-capture index. These
    # mappings intentionally point to the closest real action-backed editor
    # capture instead of generating illustrative stand-ins.
    "screen_recording": "Main editor shell / media pool / timeline",
    "creator_assist": "Preset drag/drop guides",
    "multilingual_localization": "Typography",
    "ai_script_edit": "Cut / edit point",
    "timeline_editing": "Node graph",
    "actors": "Live2D actor",
    "color_audio_vfx": "Effects / transitions",
    "export_parity": "Render queue / export",
    "ar_pbr_3d": "AR/PBR / 3D object",
    "performance_health": "Main editor shell / media pool / timeline",
    "productization_release": "Render queue / export",
}


def _feature_editor_surface_artifact_id(topic_id: str) -> str:
    return f"feature_{topic_id}_editor_surface"


def _split_markdown_row(line: str) -> list[str]:
    text = line.strip()
    if not text.startswith("|") or not text.endswith("|"):
        return []
    return [cell.strip() for cell in text.strip("|").split("|")]


def _clean_inline_code(value: str) -> str:
    text = value.strip()
    if text.startswith("`") and text.endswith("`") and len(text) >= 2:
        return text[1:-1]
    return text


def load_ui_renewal_evidence_index(
    index_path: str | Path = DEFAULT_INDEX_PATH,
    *,
    project_root: str | Path = ROOT,
) -> dict[str, UIEvidenceRecord]:
    """Load the real UI-renewal evidence table from Markdown.

    The index is intentionally simple and human-editable. Review automation uses
    it only as a pointer to already-produced editor captures; it does not infer
    or synthesize evidence if a row is missing.
    """

    root = Path(project_root)
    path = Path(index_path)
    if not path.is_absolute():
        path = root / path
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {}

    records: dict[str, UIEvidenceRecord] = {}
    for line in lines:
        cells = _split_markdown_row(line)
        if len(cells) < 4:
            continue
        if cells[0].lower() == "feature area" or set(cells[0]) <= {"-"}:
            continue
        feature_area = cells[0]
        source = _clean_inline_code(cells[1])
        artifact_text = _clean_inline_code(cells[2])
        review_use = cells[3]
        if not feature_area or artifact_text.lower() == "blocked":
            continue
        artifact = Path(artifact_text)
        if not artifact.is_absolute():
            artifact = root / artifact
        records[feature_area] = UIEvidenceRecord(
            feature_area=feature_area,
            source=source,
            artifact=artifact,
            review_use=review_use,
        )
    return records


def evidence_record_for_topic(
    topic_id: str,
    records: Mapping[str, UIEvidenceRecord],
) -> UIEvidenceRecord | None:
    feature_area = TOPIC_TO_FEATURE_AREA.get(str(topic_id or ""))
    if not feature_area:
        return None
    row = records.get(feature_area)
    return row if row and row.exists else None


def seed_feature_editor_surfaces_from_index(
    *,
    project_root: str | Path = ROOT,
    assets_dir: str | Path,
    force: bool = False,
) -> dict[str, UIEvidenceRecord]:
    """Copy indexed real captures into review feature-surface artifact slots."""

    root = Path(project_root)
    out = Path(assets_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = load_ui_renewal_evidence_index(project_root=root)
    seeded: dict[str, UIEvidenceRecord] = {}
    for topic_id in TOPIC_TO_FEATURE_AREA:
        record = evidence_record_for_topic(topic_id, records)
        if record is None:
            continue
        target = out / f"{_feature_editor_surface_artifact_id(topic_id)}.png"
        if force or not target.exists():
            shutil.copy2(record.artifact, target)
        if target.exists():
            seeded[topic_id] = record
    return seeded


def preferred_catalog_editor_source(
    *,
    project_root: str | Path = ROOT,
) -> UIEvidenceRecord | None:
    records = load_ui_renewal_evidence_index(project_root=project_root)
    for feature_area in (
        "Main editor shell / media pool / timeline",
        "Effects / transitions",
        "Cut / edit point",
    ):
        row = records.get(feature_area)
        if row and row.exists:
            return row
    return None
