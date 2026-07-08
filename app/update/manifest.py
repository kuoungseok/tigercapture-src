"""Update manifest parsing and version-gate logic.

The manifest deliberately supports both a modern ``artifacts`` list and the
older single-artifact fields so the public distribution repo can start simple
and grow into channel/platform-specific packages later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Mapping


SCHEMA = "tigerstudio.update_manifest.v1"
DEFAULT_PLATFORM = "windows-x64"
DEFAULT_KIND = "installer"


@dataclass(frozen=True)
class UpdateArtifact:
    url: str
    sha256: str
    platform: str = DEFAULT_PLATFORM
    kind: str = DEFAULT_KIND
    size: int = 0
    filename: str = ""
    signature: str = ""
    signature_url: str = ""

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "UpdateArtifact":
        url = str(data.get("url") or data.get("artifact_url") or "").strip()
        sha256 = normalize_sha256(data.get("sha256") or data.get("artifact_sha256") or "")
        if not url:
            raise ValueError("update artifact url is required")
        if not sha256:
            raise ValueError("update artifact sha256 is required")
        try:
            size = max(0, int(data.get("size", data.get("size_bytes", 0)) or 0))
        except Exception:
            size = 0
        return cls(
            url=url,
            sha256=sha256,
            platform=str(data.get("platform") or DEFAULT_PLATFORM).strip() or DEFAULT_PLATFORM,
            kind=str(data.get("kind") or data.get("type") or DEFAULT_KIND).strip() or DEFAULT_KIND,
            size=size,
            filename=str(data.get("filename") or "").strip(),
            signature=str(data.get("signature") or "").strip(),
            signature_url=str(data.get("signature_url") or "").strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "url": self.url,
            "sha256": self.sha256,
            "platform": self.platform,
            "kind": self.kind,
        }
        if self.size:
            out["size"] = int(self.size)
        if self.filename:
            out["filename"] = self.filename
        if self.signature:
            out["signature"] = self.signature
        if self.signature_url:
            out["signature_url"] = self.signature_url
        return out


@dataclass(frozen=True)
class UpdateManifest:
    version: str
    channel: str = "stable"
    published_at: str = ""
    minimum_app_version: str = "0.0.0"
    release_notes_url: str = ""
    artifacts: tuple[UpdateArtifact, ...] = field(default_factory=tuple)
    schema: str = SCHEMA
    app_id: str = "TigerCapture"
    signature_policy: str = "sha256-required"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "UpdateManifest":
        version = str(data.get("version") or "").strip()
        if not version:
            raise ValueError("update manifest version is required")
        artifacts = _artifacts_from_mapping(data)
        if not artifacts:
            raise ValueError("update manifest must contain at least one artifact")
        return cls(
            version=version,
            channel=str(data.get("channel") or "stable").strip() or "stable",
            published_at=str(data.get("published_at") or "").strip(),
            minimum_app_version=str(data.get("minimum_app_version") or "0.0.0").strip() or "0.0.0",
            release_notes_url=str(data.get("release_notes_url") or "").strip(),
            artifacts=tuple(artifacts),
            schema=str(data.get("schema") or SCHEMA).strip() or SCHEMA,
            app_id=str(data.get("app_id") or "TigerCapture").strip() or "TigerCapture",
            signature_policy=str(data.get("signature_policy") or "sha256-required").strip() or "sha256-required",
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": self.schema,
            "app_id": self.app_id,
            "version": self.version,
            "channel": self.channel,
            "minimum_app_version": self.minimum_app_version,
            "signature_policy": self.signature_policy,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }
        if self.published_at:
            out["published_at"] = self.published_at
        if self.release_notes_url:
            out["release_notes_url"] = self.release_notes_url
        return out


@dataclass(frozen=True)
class UpdateCheck:
    available: bool
    reason: str
    current_version: str
    latest_version: str
    channel: str
    artifact: UpdateArtifact | None = None
    blocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": bool(self.available),
            "blocked": bool(self.blocked),
            "reason": self.reason,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "channel": self.channel,
            "artifact": self.artifact.to_dict() if self.artifact is not None else None,
        }


def normalize_sha256(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("sha256:"):
        text = text.split(":", 1)[1].strip()
    return text


def normalize_version(value: Any) -> tuple[int, int, int, tuple[str, ...]]:
    text = str(value or "0").strip()
    core = re.split(r"[-+]", text, maxsplit=1)[0]
    suffix = tuple(part for part in re.split(r"[-+]", text, maxsplit=1)[1:] if part)
    parts = []
    for raw in core.split("."):
        match = re.match(r"(\d+)", raw.strip())
        parts.append(int(match.group(1)) if match else 0)
    while len(parts) < 3:
        parts.append(0)
    return int(parts[0]), int(parts[1]), int(parts[2]), suffix


def compare_versions(left: Any, right: Any) -> int:
    a = normalize_version(left)
    b = normalize_version(right)
    if a[:3] < b[:3]:
        return -1
    if a[:3] > b[:3]:
        return 1
    if a[3] == b[3]:
        return 0
    if not a[3] and b[3]:
        return 1
    if a[3] and not b[3]:
        return -1
    return -1 if a[3] < b[3] else 1


def choose_artifact(
    manifest: UpdateManifest,
    *,
    platform: str = DEFAULT_PLATFORM,
    kind: str | None = DEFAULT_KIND,
) -> UpdateArtifact | None:
    platform_key = str(platform or DEFAULT_PLATFORM).strip()
    kind_key = str(kind or "").strip()
    candidates = [artifact for artifact in manifest.artifacts if artifact.platform == platform_key]
    if not candidates:
        candidates = list(manifest.artifacts)
    if kind_key:
        for artifact in candidates:
            if artifact.kind == kind_key:
                return artifact
    return candidates[0] if candidates else None


def evaluate_manifest(
    manifest: UpdateManifest | Mapping[str, Any],
    *,
    current_version: str,
    channel: str = "stable",
    platform: str = DEFAULT_PLATFORM,
    kind: str | None = DEFAULT_KIND,
) -> UpdateCheck:
    parsed = manifest if isinstance(manifest, UpdateManifest) else UpdateManifest.from_mapping(manifest)
    current = str(current_version or "0.0.0").strip() or "0.0.0"
    requested_channel = str(channel or "stable").strip() or "stable"
    if parsed.channel != requested_channel:
        return UpdateCheck(False, "channel_mismatch", current, parsed.version, requested_channel)
    if compare_versions(parsed.version, current) <= 0:
        return UpdateCheck(False, "already_current", current, parsed.version, requested_channel)
    if compare_versions(current, parsed.minimum_app_version) < 0:
        return UpdateCheck(
            False,
            "current_version_below_minimum_full_installer_required",
            current,
            parsed.version,
            requested_channel,
            blocked=True,
        )
    artifact = choose_artifact(parsed, platform=platform, kind=kind)
    if artifact is None:
        return UpdateCheck(False, "no_matching_artifact", current, parsed.version, requested_channel, blocked=True)
    return UpdateCheck(True, "update_available", current, parsed.version, requested_channel, artifact=artifact)


def build_manifest(
    *,
    version: str,
    artifact_url: str,
    sha256: str,
    channel: str = "stable",
    platform: str = DEFAULT_PLATFORM,
    kind: str = DEFAULT_KIND,
    size: int = 0,
    filename: str = "",
    published_at: str = "",
    minimum_app_version: str = "0.0.0",
    release_notes_url: str = "",
    app_id: str = "TigerCapture",
    signature: str = "",
    signature_url: str = "",
) -> UpdateManifest:
    artifact = UpdateArtifact(
        url=str(artifact_url),
        sha256=normalize_sha256(sha256),
        platform=str(platform or DEFAULT_PLATFORM),
        kind=str(kind or DEFAULT_KIND),
        size=max(0, int(size or 0)),
        filename=str(filename or ""),
        signature=str(signature or ""),
        signature_url=str(signature_url or ""),
    )
    return UpdateManifest(
        version=str(version),
        channel=str(channel or "stable"),
        published_at=str(published_at or ""),
        minimum_app_version=str(minimum_app_version or "0.0.0"),
        release_notes_url=str(release_notes_url or ""),
        artifacts=(artifact,),
        app_id=str(app_id or "TigerCapture"),
    )


def manifest_from_json(text: str) -> UpdateManifest:
    data = json.loads(text)
    if not isinstance(data, Mapping):
        raise ValueError("update manifest JSON must contain an object")
    return UpdateManifest.from_mapping(data)


def manifest_to_json(manifest: UpdateManifest) -> str:
    return json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _artifacts_from_mapping(data: Mapping[str, Any]) -> list[UpdateArtifact]:
    raw_artifacts = data.get("artifacts")
    artifacts: list[UpdateArtifact] = []
    if isinstance(raw_artifacts, list):
        for row in raw_artifacts:
            if isinstance(row, Mapping):
                artifacts.append(UpdateArtifact.from_mapping(row))
    if artifacts:
        return artifacts
    if data.get("artifact_url") or data.get("url"):
        artifacts.append(
            UpdateArtifact.from_mapping(
                {
                    "url": data.get("artifact_url") or data.get("url"),
                    "sha256": data.get("sha256") or data.get("artifact_sha256"),
                    "platform": data.get("platform") or DEFAULT_PLATFORM,
                    "kind": data.get("kind") or data.get("artifact_kind") or DEFAULT_KIND,
                    "size": data.get("size") or data.get("size_bytes") or 0,
                    "filename": data.get("filename") or "",
                    "signature": data.get("signature") or "",
                    "signature_url": data.get("signature_url") or "",
                }
            )
        )
    return artifacts
