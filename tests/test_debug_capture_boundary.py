from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_DEFAULT_RE = re.compile(
    r"DEFAULT_(VIDEO|CSV|DESCRIPTOR|MOTION|MODEL|ASSET|MEDIA|VRM)\b.*debugCapture",
    re.IGNORECASE,
)
FORBIDDEN_ARG_RE = re.compile(
    r"parser\.add_argument\(\s*[\"']--(video|csv|asset|media|model|motion|descriptor)[\"'].*debugCapture",
    re.IGNORECASE,
)


def test_debug_capture_is_not_used_as_default_required_input() -> None:
    """debugCapture may hold regenerated outputs, never durable default inputs."""
    offenders: list[str] = []
    for folder in ("app", "tools"):
        for path in (ROOT / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for line_no, line in enumerate(text.splitlines(), start=1):
                if "debugCapture" not in line:
                    continue
                if FORBIDDEN_DEFAULT_RE.search(line) or FORBIDDEN_ARG_RE.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{line_no}: {line.strip()}")

    assert not offenders, (
        "debugCapture is disposable. Do not use it as a default input for source media, "
        "motion CSVs, descriptors, models, or durable assets:\n" + "\n".join(offenders)
    )
