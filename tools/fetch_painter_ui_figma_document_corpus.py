from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Callable, Mapping
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT / "qa_corpus" / "painter_ui_figma_documents" / "manifest.json"
)
DEFAULT_OUTPUT_ROOT = ROOT / "external" / "assets" / "figma" / "compat_corpus"
MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MANIFEST_V1 = "tigercapture.painter.figma_document_corpus.v1"
_MANIFEST_V2 = "tigercapture.painter.figma_document_corpus.v2"
MAX_MANIFEST_INCLUDES = 16
MAX_INCLUDE_DEPTH = 8
MAX_SELECTORS_PER_ARTIFACT = 128
MAX_SELECTOR_NODES = 1_500
MAX_SELECTOR_JSON_BYTES = 4 * 1024 * 1024
MAX_MANIFEST_SELECTOR_NODES = 10_000
MAX_MANIFEST_SELECTOR_JSON_BYTES = 16 * 1024 * 1024
MAX_SELECTOR_ANCESTRY_DEPTH = 64


class FigmaCorpusError(RuntimeError):
    pass


def _read_manifest(
    path: Path,
    *,
    _stack: tuple[Path, ...] = (),
) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if path in _stack:
        raise FigmaCorpusError(
            "Figma corpus manifest include cycle: "
            + " -> ".join(str(item) for item in (*_stack, path))
        )
    if len(_stack) >= MAX_INCLUDE_DEPTH:
        raise FigmaCorpusError("Figma corpus manifest include depth exceeded")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FigmaCorpusError(f"Cannot read Figma corpus manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise FigmaCorpusError("Figma corpus manifest must contain an object")
    validate_manifest(value)
    if value.get("schema") == _MANIFEST_V1:
        return value

    expanded_cases: list[dict[str, Any]] = []
    for include in value.get("includes", []):
        relative = _safe_relative_path(include.get("path"))
        if relative.suffix.lower() != ".json":
            raise FigmaCorpusError(
                f"Manifest include must be JSON: {relative.as_posix()}"
            )
        included_path = (path.parent / relative).resolve()
        try:
            included_path.relative_to(path.parent)
        except ValueError as exc:
            raise FigmaCorpusError(
                f"Manifest include escapes its directory: {relative.as_posix()}"
            ) from exc
        included = _read_manifest(
            included_path,
            _stack=(*_stack, path),
        )
        included_cases = list(included.get("cases") or [])
        requested = {str(item) for item in include.get("case_ids", [])}
        known = {str(item.get("id") or "") for item in included_cases}
        if requested - known:
            raise FigmaCorpusError(
                "Unknown included corpus case ids: "
                + ", ".join(sorted(requested - known))
            )
        expanded_cases.extend(
            dict(item)
            for item in included_cases
            if not requested or str(item.get("id") or "") in requested
        )

    artifacts = value.get("source_artifacts")
    assert isinstance(artifacts, Mapping)
    for item in value.get("cases", []):
        artifact_ref = str(item.get("artifact_ref") or "")
        artifact_row = artifacts[artifact_ref]
        resolved = dict(item)
        resolved["source"] = dict(artifact_row["source"])
        resolved["artifact"] = dict(artifact_row["artifact"])
        resolved.setdefault("format", "figma_rest_archive_selector")
        expanded_cases.append(resolved)

    ids = [str(item.get("id") or "") for item in expanded_cases]
    duplicates = sorted(
        case_id for case_id in set(ids) if ids.count(case_id) > 1
    )
    if duplicates:
        raise FigmaCorpusError(
            "Duplicate expanded corpus case ids: " + ", ".join(duplicates)
        )
    coverage = value.get("coverage")
    coverage = coverage if isinstance(coverage, Mapping) else {}
    expected_count = coverage.get("expected_case_count")
    if expected_count is not None and len(expanded_cases) != int(expected_count):
        raise FigmaCorpusError(
            "Expanded corpus case count mismatch: "
            f"expected {expected_count}, got {len(expanded_cases)}"
        )
    result = dict(value)
    result["cases"] = expanded_cases
    result["manifest_path"] = str(path)
    return result


def _safe_relative_path(value: object) -> Path:
    raw = str(value or "").replace("\\", "/")
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise FigmaCorpusError(f"Unsafe corpus relative path: {raw!r}")
    return Path(*path.parts)


def _validate_source_artifact(
    label: str,
    source: object,
    artifact: object,
    *,
    seen_paths: set[str],
) -> None:
    if not isinstance(source, Mapping) or not isinstance(artifact, Mapping):
        raise FigmaCorpusError(f"Corpus {label} needs source and artifact")
    url = str(source.get("url") or "")
    if not url.startswith("https://raw.githubusercontent.com/"):
        raise FigmaCorpusError(
            f"Corpus {label} must use a pinned raw.githubusercontent.com URL"
        )
    commit = str(source.get("commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise FigmaCorpusError(f"Corpus {label} needs a 40-character commit")
    if f"/{commit}/" not in url.lower():
        raise FigmaCorpusError(f"Corpus {label} URL is not pinned to its commit")
    license_id = str(source.get("license") or "").strip()
    license_url = str(source.get("license_url") or "")
    if not license_id or not license_url.startswith("https://"):
        raise FigmaCorpusError(f"Corpus {label} needs license provenance")
    if license_id.upper().startswith("CC-BY"):
        required_attribution = {
            "creator",
            "original_url",
            "license_evidence_url",
            "license_scope",
            "modifications",
            "attribution",
        }
        missing_attribution = sorted(
            key
            for key in required_attribution
            if not str(source.get(key) or "").strip()
        )
        if missing_attribution:
            raise FigmaCorpusError(
                f"Corpus {label} needs CC BY metadata: "
                + ", ".join(missing_attribution)
            )
        original_url = str(source["original_url"])
        evidence_url = str(source["license_evidence_url"])
        if not original_url.startswith("https://"):
            raise FigmaCorpusError(
                f"Corpus {label} needs an HTTPS original URL"
            )
        if (
            not evidence_url.startswith("https://github.com/")
            or f"/{commit}/" not in evidence_url.lower()
        ):
            raise FigmaCorpusError(
                f"Corpus {label} needs pinned CC BY license evidence"
            )
    digest = str(artifact.get("sha256") or "").lower()
    if not _SHA256_RE.fullmatch(digest):
        raise FigmaCorpusError(f"Corpus {label} needs a SHA-256 digest")
    relative = _safe_relative_path(artifact.get("relative_path"))
    if relative.suffix.lower() not in {".json", ".zip"}:
        raise FigmaCorpusError(
            f"Corpus {label} artifact must be JSON or a ZIP archive"
        )
    relative_key = relative.as_posix().casefold()
    if relative_key in seen_paths:
        raise FigmaCorpusError(
            f"Duplicate corpus artifact path: {relative.as_posix()}"
        )
    seen_paths.add(relative_key)
    expected_bytes = artifact.get("bytes")
    if (
        isinstance(expected_bytes, bool)
        or not isinstance(expected_bytes, int)
        or not 0 < expected_bytes <= MAX_ARTIFACT_BYTES
    ):
        raise FigmaCorpusError(f"Corpus {label} has invalid byte size")


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    schema = manifest.get("schema")
    if schema not in {_MANIFEST_V1, _MANIFEST_V2}:
        raise FigmaCorpusError("Unsupported Figma corpus manifest schema")
    if schema == _MANIFEST_V2:
        _validate_release_manifest(manifest)
        return
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise FigmaCorpusError("Figma corpus manifest must contain cases")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, item in enumerate(cases):
        if not isinstance(item, Mapping):
            raise FigmaCorpusError(f"Corpus case {index} must contain an object")
        case_id = str(item.get("id") or "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", case_id):
            raise FigmaCorpusError(f"Invalid corpus case id: {case_id!r}")
        if case_id in seen_ids:
            raise FigmaCorpusError(f"Duplicate corpus case id: {case_id}")
        seen_ids.add(case_id)
        _validate_source_artifact(
            f"case {case_id}",
            item.get("source"),
            item.get("artifact"),
            seen_paths=seen_paths,
        )


def _validate_release_manifest(manifest: Mapping[str, Any]) -> None:
    includes = manifest.get("includes")
    if not isinstance(includes, list) or not includes:
        raise FigmaCorpusError("Release manifest must contain includes")
    if len(includes) > MAX_MANIFEST_INCLUDES:
        raise FigmaCorpusError("Release manifest has too many includes")
    seen_includes: set[str] = set()
    for index, include in enumerate(includes):
        if not isinstance(include, Mapping):
            raise FigmaCorpusError(f"Manifest include {index} must be an object")
        relative = _safe_relative_path(include.get("path"))
        if relative.suffix.lower() != ".json":
            raise FigmaCorpusError("Manifest includes must be JSON")
        key = relative.as_posix().casefold()
        if key in seen_includes:
            raise FigmaCorpusError(f"Duplicate manifest include: {relative.as_posix()}")
        seen_includes.add(key)
        case_ids = include.get("case_ids", [])
        if not isinstance(case_ids, list) or any(
            not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", str(value or ""))
            for value in case_ids
        ) or len({str(value) for value in case_ids}) != len(case_ids):
            raise FigmaCorpusError("Manifest include case_ids are invalid")

    artifacts = manifest.get("source_artifacts")
    if not isinstance(artifacts, Mapping) or not artifacts:
        raise FigmaCorpusError("Release manifest needs source_artifacts")
    seen_paths: set[str] = set()
    for artifact_id, row in artifacts.items():
        artifact_id = str(artifact_id)
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", artifact_id):
            raise FigmaCorpusError(f"Invalid source artifact id: {artifact_id!r}")
        if not isinstance(row, Mapping):
            raise FigmaCorpusError(f"Source artifact {artifact_id} must be an object")
        _validate_source_artifact(
            f"source artifact {artifact_id}",
            row.get("source"),
            row.get("artifact"),
            seen_paths=seen_paths,
        )
        relative = _safe_relative_path(row["artifact"].get("relative_path"))
        if relative.suffix.lower() != ".zip":
            raise FigmaCorpusError(
                f"Selector source artifact {artifact_id} must be a ZIP archive"
            )

    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise FigmaCorpusError("Release manifest must contain selector cases")
    seen_case_ids: set[str] = set()
    seen_selector_keys: set[tuple[str, str]] = set()
    seen_exact_hashes: set[str] = set()
    seen_semantic_hashes: set[str] = set()
    ancestry_rows: dict[str, list[tuple[str, ...]]] = {}
    selector_counts: Counter[str] = Counter()
    total_nodes = 0
    total_bytes = 0
    for index, item in enumerate(cases):
        if not isinstance(item, Mapping):
            raise FigmaCorpusError(f"Selector case {index} must be an object")
        case_id = str(item.get("id") or "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", case_id):
            raise FigmaCorpusError(f"Invalid selector case id: {case_id!r}")
        if case_id in seen_case_ids:
            raise FigmaCorpusError(f"Duplicate selector case id: {case_id}")
        seen_case_ids.add(case_id)
        artifact_ref = str(item.get("artifact_ref") or "")
        if artifact_ref not in artifacts:
            raise FigmaCorpusError(
                f"Selector case {case_id} has unknown artifact_ref {artifact_ref!r}"
            )
        selector_counts[artifact_ref] += 1
        selector = item.get("selector")
        if not isinstance(selector, Mapping):
            raise FigmaCorpusError(f"Selector case {case_id} needs selector")
        if selector.get("kind") != "node_subtree":
            raise FigmaCorpusError(f"Selector case {case_id} has unsupported kind")
        if selector.get("wrapper") != "promote_to_original_canvas":
            raise FigmaCorpusError(f"Selector case {case_id} has unsupported wrapper")
        node_id = str(selector.get("node_id") or "")
        if not node_id or (artifact_ref, node_id) in seen_selector_keys:
            raise FigmaCorpusError(
                f"Duplicate or empty selector node: {artifact_ref}:{node_id}"
            )
        seen_selector_keys.add((artifact_ref, node_id))
        ancestry = selector.get("ancestry")
        if (
            not isinstance(ancestry, list)
            or not 3 <= len(ancestry) <= MAX_SELECTOR_ANCESTRY_DEPTH
            or any(not str(value or "") for value in ancestry)
            or str(ancestry[-1]) != node_id
        ):
            raise FigmaCorpusError(f"Selector case {case_id} has invalid ancestry")
        ancestry_tuple = tuple(str(value) for value in ancestry)
        for previous in ancestry_rows.setdefault(artifact_ref, []):
            shorter = min(len(previous), len(ancestry_tuple))
            if previous[:shorter] == ancestry_tuple[:shorter]:
                raise FigmaCorpusError(
                    f"Overlapping selector subtrees in {artifact_ref}: "
                    f"{previous[-1]} and {node_id}"
                )
        ancestry_rows[artifact_ref].append(ancestry_tuple)
        if str(selector.get("ancestor_canvas_id") or "") not in ancestry_tuple:
            raise FigmaCorpusError(
                f"Selector case {case_id} ancestry omits ancestor_canvas_id"
            )
        if str(selector.get("expected_type") or "") in {"", "DOCUMENT", "CANVAS", "TEXT"}:
            raise FigmaCorpusError(f"Selector case {case_id} has unsafe root type")
        if not str(selector.get("expected_name") or "").strip():
            raise FigmaCorpusError(f"Selector case {case_id} needs expected_name")
        exact_hash = str(selector.get("subtree_sha256") or "").lower()
        semantic_hash = str(selector.get("semantic_sha256") or "").lower()
        if not _SHA256_RE.fullmatch(exact_hash) or exact_hash in seen_exact_hashes:
            raise FigmaCorpusError(f"Selector case {case_id} has invalid/duplicate exact hash")
        if not _SHA256_RE.fullmatch(semantic_hash) or semantic_hash in seen_semantic_hashes:
            raise FigmaCorpusError(
                f"Selector case {case_id} has invalid/duplicate semantic hash"
            )
        seen_exact_hashes.add(exact_hash)
        seen_semantic_hashes.add(semantic_hash)
        observed_nodes = selector.get("observed_nodes")
        observed_bytes = selector.get("observed_json_bytes")
        if (
            isinstance(observed_nodes, bool)
            or not isinstance(observed_nodes, int)
            or not 1 <= observed_nodes <= MAX_SELECTOR_NODES
        ):
            raise FigmaCorpusError(f"Selector case {case_id} has invalid node count")
        if (
            isinstance(observed_bytes, bool)
            or not isinstance(observed_bytes, int)
            or not 1 <= observed_bytes <= MAX_SELECTOR_JSON_BYTES
        ):
            raise FigmaCorpusError(f"Selector case {case_id} has invalid JSON size")
        total_nodes += observed_nodes
        total_bytes += observed_bytes
    if any(count > MAX_SELECTORS_PER_ARTIFACT for count in selector_counts.values()):
        raise FigmaCorpusError("Release manifest has too many selectors per artifact")
    if total_nodes > MAX_MANIFEST_SELECTOR_NODES:
        raise FigmaCorpusError("Release manifest selector node budget exceeded")
    if total_bytes > MAX_MANIFEST_SELECTOR_JSON_BYTES:
        raise FigmaCorpusError("Release manifest selector JSON budget exceeded")
    coverage = manifest.get("coverage")
    if not isinstance(coverage, Mapping):
        raise FigmaCorpusError("Release manifest needs coverage ratchets")
    integer_fields = {
        "expected_case_count": 1,
        "expected_selector_case_count": 1,
        "min_selector_original_sources": 1,
        "min_selector_nodes": 1,
        "max_missing_image_count": 0,
    }
    for field, minimum in integer_fields.items():
        value = coverage.get(field)
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < minimum
        ):
            raise FigmaCorpusError(
                f"Release manifest has invalid coverage field {field}"
            )
    if int(coverage["expected_selector_case_count"]) != len(cases):
        raise FigmaCorpusError(
            "Release selector case-count ratchet must equal selector cases"
        )
    if int(coverage["expected_case_count"]) < len(cases):
        raise FigmaCorpusError("Release expected case count is too small")
    if int(coverage["min_selector_original_sources"]) > len(artifacts):
        raise FigmaCorpusError("Release original-source ratchet is impossible")
    if int(coverage["min_selector_nodes"]) > total_nodes:
        raise FigmaCorpusError("Release selector-node ratchet is impossible")
    feature_minima = coverage.get("selector_min_source_feature_cases")
    if not isinstance(feature_minima, Mapping) or not feature_minima:
        raise FigmaCorpusError("Release manifest needs feature-case ratchets")
    for feature, minimum in feature_minima.items():
        if (
            not str(feature).strip()
            or isinstance(minimum, bool)
            or not isinstance(minimum, int)
            or not 1 <= minimum <= len(cases)
        ):
            raise FigmaCorpusError(
                f"Release manifest has invalid feature ratchet {feature!r}"
            )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch_url(url: str, *, timeout: float = 60.0) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TigerCapture-FigmaCompatibilityCorpus/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_ARTIFACT_BYTES:
            raise FigmaCorpusError(f"Artifact is larger than {MAX_ARTIFACT_BYTES} bytes")
        data = response.read(MAX_ARTIFACT_BYTES + 1)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise FigmaCorpusError(f"Artifact is larger than {MAX_ARTIFACT_BYTES} bytes")
    return data


def fetch_corpus(
    manifest_path: str | Path = DEFAULT_MANIFEST,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    *,
    refresh: bool = False,
    case_ids: set[str] | None = None,
    fetcher: Callable[[str], bytes] | None = None,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path).expanduser().resolve()
    output_root = Path(output_root).expanduser().resolve()
    manifest = _read_manifest(manifest_path)
    selected = set(case_ids or ())
    known = {str(item["id"]) for item in manifest["cases"]}
    missing_ids = sorted(selected - known)
    if missing_ids:
        raise FigmaCorpusError(f"Unknown corpus case ids: {', '.join(missing_ids)}")
    fetch = fetcher or _fetch_url
    selected_cases = [
        item
        for item in manifest["cases"]
        if not selected or str(item["id"]) in selected
    ]
    artifacts_to_fetch: list[tuple[str, Mapping[str, Any]]] = []
    seen_artifacts: set[tuple[str, str]] = set()
    for item in selected_cases:
        case_id = str(item["id"])
        artifact = item["artifact"]
        relative = _safe_relative_path(artifact["relative_path"])
        artifact_key = (
            relative.as_posix().casefold(),
            str(artifact["sha256"]).lower(),
        )
        if artifact_key in seen_artifacts:
            continue
        seen_artifacts.add(artifact_key)
        artifacts_to_fetch.append(
            (str(item.get("artifact_ref") or case_id), item)
        )

    rows: list[dict[str, Any]] = []
    for artifact_id, item in artifacts_to_fetch:
        artifact = item["artifact"]
        source = item["source"]
        relative = _safe_relative_path(artifact["relative_path"])
        target = (output_root / relative).resolve()
        try:
            target.relative_to(output_root)
        except ValueError as exc:
            raise FigmaCorpusError(f"Corpus path escapes output root: {relative}") from exc
        expected_sha = str(artifact["sha256"]).lower()
        expected_bytes = int(artifact["bytes"])
        status = "cached"
        if refresh or not target.is_file() or _file_sha256(target) != expected_sha:
            data = fetch(str(source["url"]))
            actual_sha = _sha256(data)
            if len(data) != expected_bytes:
                raise FigmaCorpusError(
                    f"Corpus artifact {artifact_id} size mismatch: "
                    f"expected {expected_bytes}, got {len(data)}"
                )
            if actual_sha != expected_sha:
                raise FigmaCorpusError(
                    f"Corpus artifact {artifact_id} SHA-256 mismatch: "
                    f"expected {expected_sha}, got {actual_sha}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + ".part")
            temporary.write_bytes(data)
            temporary.replace(target)
            status = "downloaded"
        rows.append(
            {
                "id": artifact_id,
                "status": status,
                "path": str(target),
                "bytes": target.stat().st_size,
                "sha256": _file_sha256(target),
            }
        )
    return {
        "schema": "tigercapture.painter.figma_document_corpus_fetch.v1",
        "manifest": str(manifest_path),
        "output_root": str(output_root),
        "case_count": len(selected_cases),
        "artifact_count": len(rows),
        "downloaded_count": sum(row["status"] == "downloaded" for row in rows),
        "cached_count": sum(row["status"] == "cached" for row in rows),
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch the pinned public Figma document compatibility corpus."
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    try:
        report = fetch_corpus(
            args.manifest,
            args.output_root,
            refresh=args.refresh,
            case_ids=set(args.case),
        )
    except FigmaCorpusError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, **report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
