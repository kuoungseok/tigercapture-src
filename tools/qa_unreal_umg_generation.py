"""Generate a real UE 5.8 Widget Blueprint from a Tiger Motion document."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.interactive_button import ButtonAction, create_button_component
from app.motion_designer.schema import Keyframe, MotionComposition, MotionLayer, SourceRef
from app.unreal_umg_document import package_motion_composition_for_umg
from app.unreal_umg_workflow import run_unreal_umg_generation


DEFAULT_WORKSPACE = ROOT / "debugCapture" / "unreal_umg_generation_qa"
DEFAULT_IMAGE = ROOT / "resources" / "branding" / "composer_logo.png"
DEFAULT_SOUND = (
    ROOT
    / "external"
    / "assets"
    / "tts"
    / "generated"
    / "20260713_142238"
    / "tts_sub_0000_00000000_line_b16e703e.wav"
)


def build_composition(image_path: Path, sound_path: Path | None) -> MotionComposition:
    layer = MotionLayer(
        id="cta_button",
        name="Generate",
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=str(image_path),
            params={"width": 420, "height": 132},
        ),
        out_ms=2000,
    )
    layer.transform.position.default = [430.0, 280.0]
    layer.transform.position.keyframes = [
        Keyframe(time_ms=0, value=[430.0, 280.0]),
        Keyframe(time_ms=600, value=[520.0, 280.0], interpolation="ease_out"),
    ]
    layer.transform.opacity.keyframes = [
        Keyframe(time_ms=0, value=0.25),
        Keyframe(time_ms=350, value=1.0, interpolation="ease_out"),
    ]
    button = create_button_component(layer)
    button.actions["clicked"] = [
        ButtonAction(action_type="play_animation", name="TigerTimeline"),
        ButtonAction(action_type="emit_event", name="generate_clicked"),
    ]
    if sound_path and sound_path.is_file():
        button.actions["clicked"].insert(
            1,
            ButtonAction(action_type="play_sound", resource_uri=str(sound_path)),
        )
    layer.metadata["interactive_component"] = button.to_dict()
    return MotionComposition(
        id="qa_interactive_button",
        name="Tiger UMG Interactive Button QA",
        width=1280,
        height=720,
        fps=30.0,
        duration_ms=2000,
        layers=[layer],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--sound", type=Path, default=DEFAULT_SOUND)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    project_root = workspace / "UnrealProject"
    project_root.mkdir(parents=True, exist_ok=True)
    project = project_root / "TigerUMGQA.uproject"
    if not project.is_file():
        project.write_text(
            json.dumps(
                {
                    "FileVersion": 3,
                    "EngineAssociation": "5.8",
                    "Category": "",
                    "Description": "Tiger Studio UMG generation QA",
                    "Plugins": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    packet = package_motion_composition_for_umg(
        build_composition(
            args.image.resolve(),
            args.sound.resolve() if args.sound else None,
        ),
        workspace / "packet",
    )
    if not packet["ok"]:
        report = {"ok": False, "stage": "package", "packet": packet}
    else:
        result = run_unreal_umg_generation(project, packet["document_path"])
        report = {
            "ok": bool(result.get("ok")),
            "stage": "generation",
            "project_path": str(project),
            "packet": {
                "document_path": packet["document_path"],
                "asset_count": packet["asset_count"],
            },
            "generation": result,
        }
    report_path = workspace / "qa_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
