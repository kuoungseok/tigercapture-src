from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.6-sol"
TOOL_ACTIONS = (
    "paint.state",
    "paint.document.new",
    "paint.fill.solid",
    "paint.fill.gradient",
    "paint.layer.add",
    "paint.layer.select",
    "paint.layer.rename",
    "paint.layer.set_type",
    "paint.material.settings.set",
    "paint.material.preview.set",
    "paint.stroke.draw",
    "paint.study.analyze_reference",
    "paint.study.segment_regions",
    "paint.study.build_underpaint",
    "paint.study.trace_contours",
    "paint.study.generate_strokes",
    "paint.study.compare_render",
    "paint.study.refine_region",
    "paint.study.quality_report",
)
REFINE_ACTIONS = tuple(action for action in TOOL_ACTIONS if action != "paint.document.new")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Let OpenAI directly paint through Tiger Studio paint.* actions."
    )
    parser.add_argument(
        "--prompt",
        default=(
            "Create an original vertical nocturne painting: a contemplative woman beside "
            "dark water, a monumental warm moon, distant city lights, cobalt shadows, and "
            "gold reflections. Preserve a readable face and silhouette. Use expressive oil "
            "brushwork, broken color, varied edges, and restrained native impasto."
        ),
    )
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--replay-log",
        type=Path,
        help="Replay a previous action log without calling OpenAI.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--max-tool-calls", type=int, default=22)
    parser.add_argument("--width", type=int, default=1100)
    parser.add_argument("--height", type=int, default=880)
    return parser.parse_args()


def _replay_action_log(
    *,
    registry: Any,
    log_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    actions = list(payload.get("actions") or [])
    replayed = 0
    for entry in actions:
        action = str(entry.get("action") or "")
        if not action or action == "paint.state":
            continue
        result = registry.execute_action(
            action,
            dict(entry.get("params") or {}),
        ).to_dict()
        if not result.get("ok"):
            raise RuntimeError(
                f"Replay failed at {replayed} ({action}): "
                f"{result.get('error') or 'unknown error'}"
            )
        replayed += 1
    result = registry.execute_action(
        "paint.document.export_png",
        {"path": str(output_path), "include_background": True},
    ).to_dict()
    if not result.get("ok"):
        raise RuntimeError(str(result.get("error") or "Replay export failed"))
    return {"ok": True, "output": str(output_path), "replayed_actions": replayed}


def _data_url(path: Path) -> str:
    suffix = path.suffix.casefold()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _post_response(api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        redacted = re.sub(r"sk-[A-Za-z0-9_\-*.]+", "<redacted-api-key>", detail)
        raise RuntimeError(f"OpenAI API HTTP {exc.code}: {redacted[:1600]}") from exc


def _tool_name(action: str) -> str:
    return action.replace(".", "_")


def _tool_definitions(registry: Any, actions: tuple[str, ...]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for action in actions:
        spec = registry.get_action_schema(action)
        parameters = copy.deepcopy(
            dict(spec.get("params_schema") or {"type": "object"})
        )
        if action == "paint.stroke.draw":
            stroke_schema = (
                parameters.get("properties", {})
                .get("strokes", {})
                .get("items", {})
            )
            required = list(stroke_schema.get("required") or [])
            for field in ("layer_id", "path_mode"):
                if field not in required:
                    required.append(field)
            stroke_schema["required"] = required
        tools.append(
            {
                "type": "function",
                "name": _tool_name(action),
                "description": str(spec.get("title") or action),
                "parameters": parameters,
                "strict": False,
            }
        )
    return tools


def _compact_action_result(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("result") if isinstance(result.get("result"), dict) else {}
    layers = payload.get("layers") if isinstance(payload.get("layers"), list) else []
    document = payload.get("document") if isinstance(payload.get("document"), dict) else {}
    brush = payload.get("brush") if isinstance(payload.get("brush"), dict) else {}
    stroke_draw = (
        payload.get("stroke_draw") if isinstance(payload.get("stroke_draw"), dict) else {}
    )
    return {
        "ok": bool(result.get("ok")),
        "error": str(result.get("error") or ""),
        "document": {
            "width": document.get("width"),
            "height": document.get("height"),
        },
        "active_layer_id": payload.get("active_layer_id"),
        "layers": [
            {
                "id": layer.get("id") or layer.get("layer_id"),
                "name": layer.get("name"),
                "type": layer.get("type") or layer.get("layer_type"),
            }
            for layer in layers
            if isinstance(layer, dict)
        ],
        "brush": {
            "style": brush.get("style"),
            "width": brush.get("width"),
        },
        "stroke_draw": stroke_draw,
    }


def _response_text(response: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in response.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") == "output_text":
                chunks.append(str(content.get("text") or ""))
    return "\n".join(part for part in chunks if part).strip()


def _run_tool_pass(
    *,
    registry: Any,
    api_key: str,
    model: str,
    prompt: str,
    image_paths: list[Path],
    actions: tuple[str, ...],
    max_tool_calls: int,
    pass_index: int,
    action_log: list[dict[str, Any]],
    preview_dir: Path,
) -> str:
    tool_map = {_tool_name(action): action for action in actions}
    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for path in image_paths:
        if path.exists():
            content.append(
                {
                    "type": "input_image",
                    "image_url": _data_url(path),
                    "detail": "high",
                }
            )
    payload: dict[str, Any] = {
        "model": model,
        "input": [{"role": "user", "content": content}],
        "tools": _tool_definitions(registry, actions),
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "reasoning": {"effort": "medium"},
    }
    response = _post_response(api_key, payload)
    call_count = 0
    visual_mutation_count = 0
    while call_count < max_tool_calls:
        calls = [
            item
            for item in response.get("output") or []
            if isinstance(item, dict) and item.get("type") == "function_call"
        ]
        if not calls:
            return _response_text(response)
        call = calls[0]
        name = str(call.get("name") or "")
        action = tool_map.get(name)
        if action is None:
            raise RuntimeError(f"OpenAI requested an unavailable tool: {name}")
        try:
            params = json.loads(str(call.get("arguments") or "{}"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenAI returned invalid tool arguments for {name}") from exc
        if not isinstance(params, dict):
            raise RuntimeError(f"OpenAI tool arguments for {name} must be an object")

        result = registry.execute_action(action, params).to_dict()
        compact = _compact_action_result(result)
        action_log.append(
            {
                "pass": pass_index,
                "index": call_count,
                "action": action,
                "params": params,
                "result": compact,
            }
        )
        (preview_dir / "openai_painter_action_log.inprogress.json").write_text(
            json.dumps(
                {
                    "schema": "tigerstudio.painter.openai_direct_artwork.checkpoint.v1",
                    "actions": action_log,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if not result.get("ok"):
            compact["instruction"] = (
                "Correct the parameters and retry. Do not abandon the painting."
            )
        followup_input: list[dict[str, Any]] = [
            {
                "type": "function_call_output",
                "call_id": call["call_id"],
                "output": json.dumps(compact, ensure_ascii=False),
            }
        ]
        if result.get("ok") and action in {
            "paint.fill.solid",
            "paint.fill.gradient",
            "paint.stroke.draw",
        }:
            visual_mutation_count += 1
            if visual_mutation_count % 2 == 0:
                preview_path = (
                    preview_dir
                    / f"pass_{pass_index:02d}_working_{visual_mutation_count:02d}.png"
                )
                preview = registry.execute_action(
                    "paint.document.export_png",
                    {"path": str(preview_path), "include_background": True},
                ).to_dict()
                if preview.get("ok") and preview_path.exists():
                    followup_input.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": (
                                        "This is the current Tiger Studio canvas after "
                                        "your latest actions. Inspect it before choosing "
                                        "the next marks; correct weak composition, scale, "
                                        "silhouettes, repetition, and value hierarchy."
                                    ),
                                },
                                {
                                    "type": "input_image",
                                    "image_url": _data_url(preview_path),
                                    "detail": "high",
                                },
                            ],
                        }
                    )
        response = _post_response(
            api_key,
            {
                "model": model,
                "previous_response_id": response["id"],
                "input": followup_input,
                "tools": _tool_definitions(registry, actions),
                "tool_choice": "auto",
                "parallel_tool_calls": False,
                "reasoning": {"effort": "medium"},
            },
        )
        call_count += 1
    return f"Stopped after {max_tool_calls} tool calls."


def main() -> int:
    args = _parse_args()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(
            max(64, int(args.width)),
            max(64, int(args.height)),
            "#101923",
        ),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()
    registry = ActionRegistry(owner=dialog)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = ROOT / "external" / "assets" / "painter_openai_agent" / stamp
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output.resolve() if args.output else output_dir / "openai_tiger_painter.png"
    if args.replay_log:
        replay_result = _replay_action_log(
            registry=registry,
            log_path=args.replay_log.resolve(),
            output_path=output_path,
        )
        print(json.dumps(replay_result, ensure_ascii=False))
        dialog.close()
        return 0

    api_key = str(os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    action_log: list[dict[str, Any]] = []

    reference_paths = [args.reference.resolve()] if args.reference else []
    first_prompt = f"""
You are controlling Tiger Studio Painter directly through function tools.
Do not generate or return an image. Every visible pixel must be made by paint.* actions.

Artwork brief:
{args.prompt}

Approved local reference path:
{str(args.reference.resolve()) if args.reference else "(none)"}

Build the work in deliberate passes:
1. Create a {max(64, int(args.width))}x{max(64, int(args.height))} canvas with an appropriate ground.
2. Establish broad value masses with fills and broad strokes.
3. Add separate standard or Material Paint layers for major forms, light, and impasto accents.
4. Use paint.stroke.draw batches of roughly 20-60 strokes. Every stroke must explicitly
   target the intended layer_id. Use path_mode=smooth for natural curves and
   path_mode=polyline only for deliberate architectural corners. Prefer coherent paths,
   varied pressure/load, and multiple brush styles over repetitive single dabs.
5. Keep thick impasto selective around focal highlights and characteristic contours.
   Do not cover the entire image with uniform tubes or dots.
6. Preserve the reference's large value structure, spatial depth, focal hierarchy, and
   characteristic directional rhythm.

When an approved reference path exists, prefer the deterministic paint.study.* workflow:
analyze with semantic focus regions, segment, underpaint, forms/detail/accent, contours,
compare, and refine observed pixel error within the configured tool-call/pass budget.
Treat quality_report as diagnostic evidence only: it does not define a release threshold
or return a measured-quality ready decision. Do not replace this workflow with
hand-authored coordinate guesses.

Inspect tool results for layer ids before targeting new layers. Finish only after a
complete first-pass painting exists. This is pass 1.
""".strip()
    notes = [
        _run_tool_pass(
            registry=registry,
            api_key=api_key,
            model=args.model,
            prompt=first_prompt,
            image_paths=reference_paths,
            actions=TOOL_ACTIONS,
            max_tool_calls=max(4, int(args.max_tool_calls)),
            pass_index=1,
            action_log=action_log,
            preview_dir=output_dir,
        )
    ]

    preview_path = output_dir / "pass_01.png"
    export_result = registry.execute_action(
        "paint.document.export_png",
        {"path": str(preview_path), "include_background": True},
    ).to_dict()
    if not export_result.get("ok"):
        raise RuntimeError(str(export_result.get("error") or "Painter export failed"))

    for pass_index in range(2, max(1, int(args.passes)) + 1):
        refine_prompt = f"""
You are continuing an existing Tiger Studio Painter document through paint.* actions.
The first supplied image is the current Tiger Studio render. Any later image is a
reference only. Do not generate an image and do not replace the canvas.

Critique the current composition, silhouettes, value hierarchy, edge variety, color
harmony, directional rhythm, and material relief. Then improve it with targeted actions.
Use coherent stroke batches, not repetitive dots. Add detail where it matters and
simplify elsewhere. Preserve successful passages. This is refinement pass {pass_index}.
""".strip()
        notes.append(
            _run_tool_pass(
                registry=registry,
                api_key=api_key,
                model=args.model,
                prompt=refine_prompt,
                image_paths=[preview_path, *reference_paths],
                actions=REFINE_ACTIONS,
                max_tool_calls=max(4, int(args.max_tool_calls) // 2),
                pass_index=pass_index,
                action_log=action_log,
                preview_dir=output_dir,
            )
        )
        preview_path = output_dir / f"pass_{pass_index:02d}.png"
        registry.execute_action(
            "paint.document.export_png",
            {"path": str(preview_path), "include_background": True},
        )

    final_result = registry.execute_action(
        "paint.document.export_png",
        {"path": str(output_path), "include_background": True},
    ).to_dict()
    if not final_result.get("ok"):
        raise RuntimeError(str(final_result.get("error") or "Final Painter export failed"))

    log_path = output_dir / "openai_painter_action_log.json"
    log_path.write_text(
        json.dumps(
            {
                "schema": "tigerstudio.painter.openai_direct_artwork.v1",
                "model": args.model,
                "prompt": args.prompt,
                "reference_paths": [str(path) for path in reference_paths],
                "image_generation_endpoint_used": False,
                "tool_actions": [entry["action"] for entry in action_log],
                "passes": notes,
                "actions": action_log,
                "output": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output_path),
                "log": str(log_path),
                "action_count": len(action_log),
                "model": args.model,
            },
            ensure_ascii=False,
        )
    )
    dialog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
