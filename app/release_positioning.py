"""Release-positioning claim audit helpers.

The product has many competitor-inspired workflows, but release copy must stay
honest about what is implemented versus what is still a parity goal.  This
module scans public-facing text for over-strong claims before packaging.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_PUBLIC_COPY_PATHS: tuple[str, ...] = (
    "README.md",
    "CHANGELOG.md",
    "docs/RELEASE_POSITIONING.md",
    "docs/RELEASE_TRUST.md",
)

OPTIONAL_PUBLIC_COPY_PATHS: tuple[str, ...] = (
    "docs/LANDING_COPY.md",
    "docs/PRICING_COPY.md",
    "docs/RELEASE_NOTES.md",
)


@dataclass(frozen=True)
class PositioningRule:
    id: str
    area: str
    pattern: str
    message: str
    safe_alternatives: tuple[str, ...]


@dataclass(frozen=True)
class PositioningFinding:
    rule_id: str
    area: str
    path: str
    line: int
    text: str
    message: str
    safe_alternatives: tuple[str, ...]
    severity: str = "blocker"


PUBLIC_POSITIONING_RULES: tuple[PositioningRule, ...] = (
    PositioningRule(
        "screenstudio_replacement_claim",
        "Screen Studio",
        r"\b(full\s+screen\s+studio\s+parity|100%\s*screen\s+studio|screen\s+studio\s+replacement|screen\s+studio\s+대체)\b",
        "Do not claim Screen Studio replacement/full parity before the interaction-ready real recording corpus passes.",
        ("Screen Studio-inspired polish", "similar polish direction", "screen-recording workflow foundations"),
    ),
    PositioningRule(
        "capcut_ecosystem_claim",
        "CapCut",
        r"\b(full\s+capcut|capcut\s+replacement|capcut-scale|capcut\s+대체|capcut\s+수준의\s+템플릿)\b",
        "Do not claim CapCut-scale ecosystem depth; Tiger Studio is local-first and template scale is still growing.",
        ("CapCut-style creator assist", "local short-form workflow", "creator template foundations"),
    ),
    PositioningRule(
        "capcut_trend_template_claim",
        "CapCut",
        r"\b(capcut-sized\s+template\s+library|capcut\s+template\s+scale|capcut-grade\s+templates|millions?\s+of\s+templates|trend\s+feed\s+equivalent)\b",
        "Do not imply CapCut-scale template or trend-feed depth before the shipped catalog and corpus prove it.",
        ("local trend-template starter packs", "creator template foundations", "CapCut-style local presets"),
    ),
    PositioningRule(
        "descript_replacement_claim",
        "Descript",
        r"\b(descript\s+replacement|full\s+descript|descript-class|descript\s+대체)\b",
        "Do not claim Descript-class text editing until real provider/corpus quality proves it.",
        ("AI Script Edit MVP", "review-first text edit planning", "safe transcript workflow"),
    ),
    PositioningRule(
        "resolve_fairlight_fusion_replacement_claim",
        "Resolve/Fairlight/Fusion",
        r"\b(resolve\s+replacement|fairlight\s+replacement|fusion\s+replacement|full\s+resolve|full\s+fairlight|full\s+fusion|resolve\s+대체|fairlight\s+대체|fusion\s+대체)\b",
        "Do not claim full professional post-suite replacement.",
        ("creator-grade professional foundations", "partial professional workflow", "readiness diagnostics"),
    ),
    PositioningRule(
        "professional_nle_replacement_claim",
        "Professional NLE",
        r"\b(premiere\s+replacement|resolve\s+nle\s+replacement|full\s+nle|professional\s+nle\s+replacement|premiere-grade\s+nle|resolve-grade\s+nle|premiere-class\s+nle|resolve-class\s+nle)\b",
        "Do not claim Premiere/Resolve-class professional NLE replacement until NLE readiness allows it.",
        ("core NLE workflow/action surface", "3-point edit foundations", "NLE readiness diagnostics"),
    ),
    PositioningRule(
        "professional_suite_grade_claim",
        "Resolve/Fairlight/Fusion",
        r"\b(resolve-grade|fairlight-grade|fusion-grade|hollywood-grade|broadcast-ready\s+color|production-ready\s+daw|nuke-class\s+compositor)\b",
        "Avoid professional-suite-grade claims unless the copy clearly says these are foundations or diagnostics.",
        ("creator-grade professional foundations", "partial professional workflow", "runtime QA evidence"),
    ),
    PositioningRule(
        "actor_universal_compat_claim",
        "Live2D/Spine",
        r"\b(all\s+game\s+resources\s+compatible|universal\s+compatibility|every\s+unity/game-exported\s+rig|모든\s+게임\s+리소스\s+호환)\b",
        "Do not imply universal Live2D/Spine compatibility; keep this corpus-qualified.",
        ("large-corpus QA", "actor-track support", "compatibility diagnostics"),
    ),
    PositioningRule(
        "preview_no_latency_claim",
        "Preview performance",
        r"\b(no-latency\s+scrubb?ing|zero-latency\s+scrubb?ing|always\s+smooth\s+scrubb?ing|모든\s+코덱.*무지연)\b",
        "Do not promise no-latency scrubbing across all projects.",
        ("measured preview/cache paths", "scrub-readiness diagnostics", "proxy/native preview improvements"),
    ),
)


_SAFE_NEGATION_TERMS = (
    "not ",
    "not yet",
    "do not",
    "don't",
    "must not",
    "cannot",
    "still wins",
    "still dominates",
    "remains",
    "gap",
    "guardrail",
    "must stay",
    "no claim",
    "foundation",
    "foundations",
    "partial",
    "diagnostic",
    "diagnostics",
    "starter",
    "아직",
    "하지 않습니다",
    "말하면 안",
    "금지",
)


def _is_guardrail_context(text: str) -> bool:
    lowered = str(text or "").casefold()
    return any(term in lowered for term in _SAFE_NEGATION_TERMS)


def scan_release_positioning_text(
    text: str,
    *,
    path: str = "<text>",
    rules: Iterable[PositioningRule] = PUBLIC_POSITIONING_RULES,
) -> list[PositioningFinding]:
    findings: list[PositioningFinding] = []
    compiled = [(rule, re.compile(rule.pattern, re.IGNORECASE)) for rule in rules]
    lines = str(text or "").splitlines()
    for idx, line in enumerate(lines):
        line_no = idx + 1
        guardrail_context = " ".join(lines[max(0, idx - 2): idx + 1])
        if not line.strip() or _is_guardrail_context(guardrail_context):
            continue
        if Path(path).name == "RELEASE_POSITIONING.md" and line.lstrip().startswith("|"):
            continue
        for rule, pattern in compiled:
            if pattern.search(line):
                findings.append(
                    PositioningFinding(
                        rule_id=rule.id,
                        area=rule.area,
                        path=path,
                        line=line_no,
                        text=line.strip(),
                        message=rule.message,
                        safe_alternatives=rule.safe_alternatives,
                    )
                )
    return findings


def build_release_positioning_report(
    root: str | Path = ".",
    *,
    paths: Iterable[str | Path] = DEFAULT_PUBLIC_COPY_PATHS,
    optional_paths: Iterable[str | Path] = OPTIONAL_PUBLIC_COPY_PATHS,
) -> dict[str, Any]:
    root_path = Path(root)
    scanned: list[dict[str, Any]] = []
    findings: list[PositioningFinding] = []
    missing: list[str] = []
    optional_missing: list[str] = []
    scan_targets = [(raw_path, False) for raw_path in paths] + [(raw_path, True) for raw_path in optional_paths]
    for raw_path, optional in scan_targets:
        rel = Path(raw_path)
        path = rel if rel.is_absolute() else root_path / rel
        if not path.is_file():
            if optional:
                optional_missing.append(str(raw_path))
            else:
                missing.append(str(raw_path))
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        line_count = len(text.splitlines())
        scanned.append({"path": str(raw_path), "lines": line_count, "optional": bool(optional)})
        findings.extend(scan_release_positioning_text(text, path=str(raw_path)))
    safe_term_hits = {
        "screenstudio_inspired": False,
        "capcut_style": False,
        "professional_foundations": False,
        "not_replacement": False,
    }
    for item in scanned:
        path = root_path / str(item["path"])
        try:
            text = path.read_text(encoding="utf-8", errors="replace").casefold()
        except Exception:
            text = ""
        safe_term_hits["screenstudio_inspired"] |= "screen studio-style" in text or "screen studio-inspired" in text
        safe_term_hits["capcut_style"] |= "capcut-style" in text
        safe_term_hits["professional_foundations"] |= "professional" in text and "foundation" in text
        safe_term_hits["not_replacement"] |= "not a full" in text or "not a replacement" in text or "remain far deeper" in text

    checks = {
        "public_copy_files_present": not missing,
        "no_blocking_overclaims": not findings,
        "safe_screenstudio_language_present": bool(safe_term_hits["screenstudio_inspired"]),
        "safe_capcut_language_present": bool(safe_term_hits["capcut_style"]),
        "professional_foundation_language_present": bool(safe_term_hits["professional_foundations"]),
        "replacement_caveat_present": bool(safe_term_hits["not_replacement"]),
        "public_surface_coverage": len(scanned) >= 4,
    }
    return {
        "kind": "release_positioning_audit",
        "ok": all(checks.values()),
        "release_copy_claim_ready": all(checks.values()),
        "checks": checks,
        "summary": {
            "files_scanned": len(scanned),
            "missing_files": len(missing),
            "optional_missing_files": len(optional_missing),
            "blocking_findings": len(findings),
            "rules": len(PUBLIC_POSITIONING_RULES),
        },
        "scanned": scanned,
        "missing": missing,
        "optional_missing": optional_missing,
        "findings": [asdict(item) for item in findings],
        "safe_language": safe_term_hits,
        "truth": "This audit blocks over-strong competitor claims; it does not certify feature parity.",
    }


def release_positioning_report_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Small helper for QA dashboards that already hold markdown text."""
    text = str(payload.get("text") or "")
    path = str(payload.get("path") or "<payload>")
    findings = scan_release_positioning_text(text, path=path)
    return {
        "ok": not findings,
        "path": path,
        "findings": [asdict(item) for item in findings],
    }
