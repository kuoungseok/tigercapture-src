from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from screen_map_calibrator_web import DEFAULT_SCREEN_MAP, DEFAULT_TEMPLATE, build_payload


ROOT = Path(__file__).resolve().parents[1]
HTML_TEMPLATE = Path(__file__).with_name("screen_map_calibrator_web.html")
DEFAULT_OUT = (
    ROOT.parent
    / "ReviewAutomationWorkspace"
    / "outputs"
    / "template_debug"
    / "screen_map_calibration"
    / "screen_map_calibrator_standalone.html"
)


def build_standalone(template: Path, screen_map: Path, out: Path) -> Path:
    template = template.resolve()
    screen_map = screen_map.resolve()
    out = out.resolve()
    payload = build_payload(template, screen_map)
    payload["template_path"] = str(template)
    payload["screen_map_path"] = str(screen_map)
    image_data = base64.b64encode(template.read_bytes()).decode("ascii")
    state = {
        "state": payload,
        "image_data_url": f"data:image/png;base64,{image_data}",
    }
    html = HTML_TEMPLATE.read_text(encoding="utf-8")
    inject = (
        "<script>\n"
        "window.__SCREEN_MAP_STANDALONE__ = "
        + json.dumps(state, ensure_ascii=False)
        + ";\n"
        "</script>\n"
    )
    html = html.replace("  <script>\n    const canvas", "  " + inject + "  <script>\n    const canvas", 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a standalone screen-map calibrator HTML file.")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--screen-map", type=Path, default=DEFAULT_SCREEN_MAP)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = build_standalone(args.template, args.screen_map, args.out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
