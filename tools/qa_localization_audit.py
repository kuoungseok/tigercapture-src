"""Audit TigerCapture locale tables for missing keys and broken text.

Run from the repository root:

    .venv\\Scripts\\python.exe tools\\qa_localization_audit.py

The audit is intentionally read-only. It catches the class of mojibake that
shows up as broken punctuation, replacement glyphs, or old double-encoded
Korean fragments in visible UI strings.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from string import Formatter


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LANGS = ("en", "ko", "ja", "zh", "fr", "de")
REFERENCE_LANG = "en"
SUSPICIOUS_TOKENS = (
    "\ufffd",
    "\u25a1",
    "\u25a0",
    "Ã",
    "Â",
    "â€",
    "竊",
    "쨌",
    "횞",
    "?뮶",
    "?뱥",
    "?뱚",
    "?렗",
    "?뱛",
    "?뿊",
    "?뵇",
)


@dataclass
class LocaleAudit:
    lang: str
    keys: int
    missing_from_reference: list[str]
    extra_over_reference: list[str]
    suspicious: list[tuple[str, str]]
    placeholder_mismatches: list[tuple[str, list[str], list[str]]]


def _table(lang: str) -> dict[str, str]:
    mod = importlib.import_module(f"app.locales.{lang}")
    return dict(mod.TRANSLATIONS)


def _placeholders(text: str) -> list[str]:
    names: list[str] = []
    for _literal, field_name, _format_spec, _conversion in Formatter().parse(text):
        if field_name:
            names.append(field_name.split(".", 1)[0].split("[", 1)[0])
    return sorted(set(names))


def audit_locale(lang: str, reference: dict[str, str]) -> LocaleAudit:
    table = _table(lang)
    ref_keys = set(reference)
    keys = set(table)
    suspicious: list[tuple[str, str]] = []
    placeholder_mismatches: list[tuple[str, list[str], list[str]]] = []

    for key, value in table.items():
        if any(token in value for token in SUSPICIOUS_TOKENS):
            suspicious.append((key, value))
        if key in reference:
            ref_ph = _placeholders(reference[key])
            cur_ph = _placeholders(value)
            if ref_ph != cur_ph:
                placeholder_mismatches.append((key, ref_ph, cur_ph))

    return LocaleAudit(
        lang=lang,
        keys=len(table),
        missing_from_reference=sorted(ref_keys - keys),
        extra_over_reference=sorted(keys - ref_keys),
        suspicious=suspicious,
        placeholder_mismatches=placeholder_mismatches,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--out", type=Path, default=None, help="Optional JSON report output path.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on missing non-reference locale keys as well as suspicious text.",
    )
    args = parser.parse_args()

    reference = _table(REFERENCE_LANG)
    audits = [audit_locale(lang, reference) for lang in LANGS]
    failed = False
    for audit in audits:
        if audit.suspicious or audit.placeholder_mismatches:
            failed = True
        if args.strict and audit.missing_from_reference:
            failed = True

    report = {
        "kind": "localization_audit",
        "ok": not failed,
        "summary": {
            "languages": len(audits),
            "reference_language": REFERENCE_LANG,
            "total_keys": sum(a.keys for a in audits),
            "missing_keys": sum(len(a.missing_from_reference) for a in audits),
            "suspicious_strings": sum(len(a.suspicious) for a in audits),
            "placeholder_mismatches": sum(len(a.placeholder_mismatches) for a in audits),
            "strict": bool(args.strict),
        },
        "languages": [asdict(a) for a in audits],
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for audit in audits:
            print(
                f"{audit.lang}: keys={audit.keys} "
                f"missing={len(audit.missing_from_reference)} "
                f"suspicious={len(audit.suspicious)} "
                f"placeholder_mismatch={len(audit.placeholder_mismatches)}"
            )
            for key, value in audit.suspicious[:20]:
                print(f"  suspicious {key}: {value!r}")
            for key, ref, cur in audit.placeholder_mismatches[:20]:
                print(f"  placeholder {key}: ref={ref} current={cur}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
