"""Distinct layout recipes for the ten Hot Motion 2026 products."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .glass_material import make_glass_effect
from .schema import (
    AnimatedProperty,
    Keyframe,
    MotionBehaviorRef,
    MotionEffectRef,
    MotionLayer,
    MotionMaskRef,
    SourceRef,
)


HOT_TEMPLATE_PREFIX = "hot_2026_"


def _effect(kind: str, **params: Any) -> MotionEffectRef:
    return MotionEffectRef(
        kind=kind,
        params={
            str(key): AnimatedProperty(value_type="number", default=deepcopy(value))
            for key, value in params.items()
        },
        metadata={"template_effect": True, "hot_2026": True},
    )


def _keys(value_type: str, default: Any, rows: tuple[tuple[int, Any], ...]) -> AnimatedProperty:
    return AnimatedProperty(
        value_type=value_type,
        default=deepcopy(default),
        keyframes=[
            Keyframe(time_ms=int(time_ms), value=deepcopy(value), interpolation="bezier")
            for time_ms, value in rows
        ],
    )


def _shape(
    name: str,
    *,
    start: int,
    end: int,
    x: float,
    y: float,
    width: float,
    height: float,
    fill: str,
    shape: str = "rectangle",
    radius: float = 0.0,
    role: str = "graphic",
    rotation: float = 0.0,
) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="shape",
        in_ms=start,
        out_ms=end,
        source=SourceRef(kind="shape", params={
            "shape": shape,
            "width": width,
            "height": height,
            "fill": fill,
            "stroke": "#00000000",
            "stroke_width": 0,
            "radius": radius,
        }),
        metadata={"template_role": role, "hot_2026_distinct_layout": True},
    )
    layer.transform.position.default = [x, y]
    layer.transform.rotation.default = rotation
    return layer


def _image(
    name: str,
    uri: str,
    *,
    start: int,
    end: int,
    x: float,
    y: float,
    width: float,
    height: float,
    role: str,
    rotation: float = 0.0,
    fit: str = "cover",
) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="image",
        in_ms=start,
        out_ms=end,
        source=SourceRef(kind="image", uri=uri, params={
            "width": max(1, round(width)),
            "height": max(1, round(height)),
            "fit": fit,
        }),
        metadata={
            "template_role": role,
            "replaceable": "background_image" if role == "background_media" else role,
            "asset_provenance": "Tiger Studio Generated 2026 Trend Plate",
            "hot_2026_distinct_layout": True,
        },
    )
    layer.transform.position.default = [x, y]
    layer.transform.rotation.default = rotation
    return layer


def _text(
    name: str,
    value: str,
    *,
    start: int,
    end: int,
    x: float,
    y: float,
    width: float,
    size: float,
    fill: str,
    align: str = "left",
    family: str = "Segoe UI",
    weight: int = 700,
    role: str = "headline",
    animation: str = "slide-up-in",
    rotation: float = 0.0,
) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="text",
        in_ms=start,
        out_ms=end,
        source=SourceRef(kind="typography", params={
            "text": value,
            "font_family": family,
            "font_size": size,
            "font_weight": weight,
            "fill": fill,
            "align": align,
            "width": width,
            "height": max(size * 2.4, 80.0),
            "text_animation": {
                "in": animation,
                "hold": "none",
                "out": "fade-out",
                "unit": "word",
                "stagger_ms": 55,
                "in_duration_ms": 520,
                "out_duration_ms": 300,
            },
        }),
        metadata={"template_role": role, "hot_2026_distinct_layout": True},
    )
    layer.transform.position.default = [x, y]
    layer.transform.rotation.default = rotation
    return layer


def _scene_ranges(duration: int, count: int) -> list[tuple[int, int]]:
    return [
        (round(duration * index / count), round(duration * (index + 1) / count))
        for index in range(count)
    ]


def _animate_entry(layer: MotionLayer, *, dx: float = 0.0, dy: float = 0.0, scale: float = 0.92) -> None:
    x, y = layer.transform.position.default
    layer.transform.position = _keys(
        "vector2", [x, y], ((0, [x + dx, y + dy]), (520, [x, y]))
    )
    layer.transform.scale = _keys(
        "vector2", [1.0, 1.0], ((0, [scale, scale]), (620, [1.0, 1.0]))
    )
    layer.transform.opacity = _keys("number", 1.0, ((0, 0.0), (260, 1.0)))


def _add_hit(layer: MotionLayer, *, delay: int = 0, overshoot: float = 1.12) -> None:
    layer.transform.scale = _keys(
        "vector2", [1.0, 1.0],
        ((delay, [0.12, 0.12]), (delay + 180, [overshoot, overshoot]), (delay + 320, [1.0, 1.0])),
    )
    layer.transform.opacity = _keys("number", 1.0, ((delay, 0.0), (delay + 80, 1.0)))


def _base(spec: Mapping[str, Any], width: int, height: int, controls: Mapping[str, Any]) -> tuple[list[MotionLayer], str, int, str, str]:
    duration = int(controls["duration_ms"])
    uri = str(controls.get("background_image") or "")
    accent = str(controls["accent_color"])
    surface = str(controls["surface_color"])
    background = _image(
        "Generated Trend Plate",
        uri,
        start=0,
        end=duration,
        x=width * 0.5,
        y=height * 0.5,
        width=width,
        height=height,
        role="background_media",
    )
    background.behaviors.append(MotionBehaviorRef(
        kind="scale", start_ms=0, end_ms=duration, params={"from": 1.055, "hold_after": True}
    ))
    return [background], uri, duration, accent, surface


def _prompt_playground(spec, width, height, controls) -> list[MotionLayer]:
    layers, uri, duration, accent, _surface = _base(spec, width, height, controls)
    ranges = _scene_ranges(duration, len(spec["scenes"]))
    for index, ((kicker, title, body), (start, end)) in enumerate(zip(spec["scenes"], ranges)):
        for card_index in range(3):
            card = _shape(
                f"Window {index + 1}.{card_index + 1}", start=start, end=end,
                x=width * (0.24 + card_index * 0.20), y=height * (0.30 + card_index * 0.14),
                width=width * (0.31 - card_index * 0.025), height=height * 0.27,
                fill=("#e8e2d5", "#11161d", accent)[card_index], role="ui_window",
                rotation=(-2.0, 1.5, -0.5)[card_index],
            )
            _animate_entry(card, dx=(-1 if card_index % 2 == 0 else 1) * width * 0.18, dy=height * 0.05)
            card.effects.append(_effect("drop_shadow", blur=18.0, opacity=0.55, offset_x=12.0, offset_y=16.0))
            layers.append(card)
        for bar_index in range(7):
            bar = _shape(
                f"Command Pulse {index + 1}.{bar_index + 1}", start=start, end=end,
                x=width * (.10 + bar_index * .06), y=height * (.84 + (bar_index % 2) * .035),
                width=width * .045, height=height * (.035 + (bar_index % 3) * .018),
                fill=accent if bar_index % 2 else "#f4f0e8", role="command_pulse",
            )
            _add_hit(bar, delay=bar_index * 55, overshoot=1.3)
            layers.append(bar)
        title_layer = _text(
            f"Command {index + 1}", title.upper(), start=start, end=end,
            x=width * 0.72, y=height * 0.40, width=width * 0.42,
            size=height * 0.085, fill="#ffffff", role="headline", animation="typewriter-in",
        )
        _animate_entry(title_layer, dx=width * 0.12)
        layers.extend((title_layer, _text(
            f"Status {index + 1}", f"{kicker} / {body}", start=start, end=end,
            x=width * 0.72, y=height * 0.60, width=width * 0.42,
            size=height * 0.027, fill=accent, role="body", animation="fade-in",
        )))
    return layers


def _reality_warp(spec, width, height, controls) -> list[MotionLayer]:
    layers, _uri, duration, accent, _surface = _base(spec, width, height, controls)
    ranges = _scene_ranges(duration, len(spec["scenes"]))
    layers.append(_shape(
        "Optical Shade", start=0, end=duration, x=width * .5, y=height * .5,
        width=width, height=height, fill="#50000000", role="surface",
    ))
    for index, ((kicker, title, body), (start, end)) in enumerate(zip(spec["scenes"], ranges)):
        ring = _shape(
            f"Warp Ring {index + 1}", start=start, end=end,
            x=width * (0.23 + index * 0.26), y=height * (0.34 + (index % 2) * 0.22),
            width=height * 0.48, height=height * 0.48, fill="#20ffffff",
            shape="ellipse", radius=height * .24, role="refractive_lens",
        )
        ring.effects.append(make_glass_effect(preset="liquid_cta"))
        ring.effects.append(_effect("light_sweep", intensity=0.9, width=0.16, angle=28.0, position=0.35))
        ring.transform.scale = _keys("vector2", [1, 1], ((0, [.2, .2]), (700, [1.15, 1.15]), (1100, [1, 1])))
        layers.append(ring)
        title_layer = _text(
            f"Warp Title {index + 1}", title.upper(), start=start, end=end,
            x=width * .5, y=height * .78, width=width * .88, size=height * .12,
            fill="#ffffff", align="center", role="headline", animation="pop-in",
        )
        title_layer.effects.extend((
            _effect("displacement", amount=13.0, scale=42.0, seed=float(index + 3)),
            _effect("directional_blur", radius=8.0, angle=-12.0),
            _effect("glow", radius=12.0, intensity=0.55),
        ))
        layers.append(title_layer)
        layers.append(_text(
            f"Warp Note {index + 1}", f"{kicker}  {body}", start=start, end=end,
            x=width * .5, y=height * .91, width=width * .72, size=height * .026,
            fill=accent, align="center", role="body", animation="fade-in",
        ))
    return layers


def _explorecore(spec, width, height, controls) -> list[MotionLayer]:
    layers, uri, duration, accent, _surface = _base(spec, width, height, controls)
    ranges = _scene_ranges(duration, len(spec["scenes"]))
    for index, ((kicker, title, body), (start, end)) in enumerate(zip(spec["scenes"], ranges)):
        photo = _image(
            f"Field Photo {index + 1}", uri, start=start, end=end,
            x=width * (0.32 + index % 2 * .36), y=height * .48,
            width=width * .52, height=height * .62, role=f"media_slot_{index + 1}",
            rotation=(-3.0 if index % 2 == 0 else 2.0),
        )
        _animate_entry(photo, dx=(-1 if index % 2 == 0 else 1) * width * .20, scale=.82)
        photo.effects.append(_effect("drop_shadow", blur=24.0, opacity=0.7, offset_x=18.0, offset_y=20.0))
        layers.append(photo)
        for echo_index in range(2):
            echo = _shape(
                f"Poster Edge {index + 1}.{echo_index + 1}", start=start, end=end,
                x=photo.transform.position.default[0] + (echo_index + 1) * 18,
                y=photo.transform.position.default[1] + (echo_index + 1) * 15,
                width=width * .52, height=height * .62,
                fill=(accent if echo_index == 0 else "#f1eadf"), role="poster_stack",
                rotation=photo.transform.rotation.default + (echo_index + 1) * 1.5,
            )
            echo.transform.opacity.default = .42
            layers.insert(max(1, len(layers) - 1), echo)
        layers.append(_text(
            f"Chapter Number {index + 1}", f"0{index + 1}", start=start, end=end,
            x=width * (.80 if index % 2 == 0 else .20), y=height * .22,
            width=width * .2, size=height * .15, fill=accent, align="center",
            family="Georgia", role="chapter",
        ))
        layers.append(_text(
            f"Field Title {index + 1}", title, start=start, end=end,
            x=width * (.74 if index % 2 == 0 else .26), y=height * .48,
            width=width * .36, size=height * .07, fill="#ffffff",
            align="center", family="Georgia", role="headline",
        ))
    return layers


def _texture_check(spec, width, height, controls) -> list[MotionLayer]:
    layers, uri, duration, accent, _surface = _base(spec, width, height, controls)
    ranges = _scene_ranges(duration, len(spec["scenes"]))
    for index, ((kicker, title, body), (start, end)) in enumerate(zip(spec["scenes"], ranges)):
        crop = _image(
            f"Sensory Crop {index + 1}", uri, start=start, end=end,
            x=width * (.20 + index * .30), y=height * .45,
            width=height * .52, height=height * .52, role=f"media_slot_{index + 1}",
        )
        crop.masks.append(MotionMaskRef(kind="ellipse", mode="add"))
        crop.effects.extend((
            _effect("unsharp_mask", radius=2.2, amount=1.25),
            _effect("saturation", amount=1.28),
        ))
        crop.transform.scale = _keys("vector2", [1, 1], ((0, [.55, .55]), (700, [1.08, 1.08]), (1000, [1, 1])))
        layers.append(crop)
        orbit = _shape(
            f"Carousel Orbit {index + 1}", start=start, end=end,
            x=width * .5, y=height * .45, width=width * .88, height=height * .62,
            fill="#00000000", shape="ellipse", role="carousel_track",
        )
        orbit.source.params.update({"stroke": accent, "stroke_width": max(2, height * .005)})
        orbit.transform.rotation = _keys("number", 0.0, ((0, -14.0), (end - start, 14.0)))
        layers.append(orbit)
        giant = _text(
            f"Sensory Word {index + 1}", kicker, start=start, end=end,
            x=width * .5, y=height * .76, width=width * .96,
            size=height * .18, fill="#ffffff", align="center", role="headline", animation="pop-in",
        )
        layers.extend((giant, _text(
            f"Sensory Copy {index + 1}", f"{title} / {body}", start=start, end=end,
            x=width * .5, y=height * .92, width=width * .78,
            size=height * .027, fill=accent, align="center", role="body",
        )))
    return layers


def _notes_chic(spec, width, height, controls) -> list[MotionLayer]:
    layers, uri, duration, accent, _surface = _base(spec, width, height, controls)
    ranges = _scene_ranges(duration, len(spec["scenes"]))
    positions = ((.24, .30, -5), (.68, .27, 4), (.30, .68, 2), (.70, .66, -3))
    for index, ((kicker, title, body), (start, end)) in enumerate(zip(spec["scenes"], ranges)):
        px, py, rotation = positions[index]
        note = _shape(
            f"Paper Note {index + 1}", start=start, end=end,
            x=width * px, y=height * py, width=width * .38, height=height * .29,
            fill="#eee9de", role="paper_note", rotation=rotation,
        )
        _animate_entry(note, dy=-height * .22, scale=.72)
        note.effects.append(_effect("drop_shadow", blur=22.0, opacity=0.6, offset_x=12.0, offset_y=18.0))
        layers.append(note)
        layers.append(_shape(
            f"Highlighter {index + 1}", start=start, end=end,
            x=width * px, y=height * (py + .08), width=width * .25, height=height * .035,
            fill=accent, role="marker", rotation=rotation - 1,
        ))
        layers.append(_text(
            f"Note Copy {index + 1}", f"{kicker}\n{title}", start=start, end=end,
            x=width * px, y=height * (py - .02), width=width * .32,
            size=height * .052, fill="#15171a", align="center", family="Georgia",
            role="headline", rotation=rotation,
        ))
        snapshot = _image(
            f"Pinned Snapshot {index + 1}", uri, start=start, end=end,
            x=width * (1 - px), y=height * (1 - py), width=width * .34, height=height * .38,
            role=f"media_slot_{index + 1}", rotation=-rotation,
        )
        _animate_entry(snapshot, dx=(width * .2 if px < .5 else -width * .2), scale=.8)
        snapshot.effects.append(_effect("posterize", levels=7.0))
        layers.append(snapshot)
        rewind = _text(
            f"Rewind Mark {index + 1}", "REW  <<  REPLAY", start=start, end=end,
            x=width * .5, y=height * .91, width=width * .65,
            size=height * .032, fill=accent, align="center", role="transport_echo",
            family="Consolas", animation="typewriter-in",
        )
        rewind.transform.position = _keys("vector2", [width*.5, height*.91], ((0, [width*.78, height*.91]), (end-start, [width*.22, height*.91])))
        layers.append(rewind)
    return layers


def _opt_out(spec, width, height, controls) -> list[MotionLayer]:
    layers, uri, duration, accent, _surface = _base(spec, width, height, controls)
    ranges = _scene_ranges(duration, len(spec["scenes"]))
    layers.append(_shape(
        "Ivory Editorial Field", start=0, end=duration, x=width * .75, y=height * .5,
        width=width * .5, height=height, fill="#e9e3d9", role="surface",
    ))
    for index, ((kicker, title, body), (start, end)) in enumerate(zip(spec["scenes"], ranges)):
        photo = _image(
            f"Still Life {index + 1}", uri, start=start, end=end,
            x=width * .29, y=height * .5, width=width * .58, height=height,
            role=f"media_slot_{index + 1}",
        )
        photo.transform.position = _keys("vector2", [width*.29, height*.5], ((0, [width*.27, height*.5]), (end-start, [width*.31, height*.5])))
        photo.effects.extend((
            _effect("posterize", levels=8.0),
            _effect("fractal_noise", amount=0.12, scale=34.0, octaves=3.0, seed=float(index + 11), phase=0.0),
        ))
        layers.append(photo)
        layers.extend((
            _text(
                f"Quiet Index {index + 1}", kicker, start=start, end=end,
                x=width * .69, y=height * .19, width=width * .35,
                size=height * .028, fill="#6d665d", family="Georgia", role="kicker",
            ),
            _text(
                f"Quiet Title {index + 1}", title, start=start, end=end,
                x=width * .74, y=height * .43, width=width * .39,
                size=height * .075, fill="#181716", family="Georgia", role="headline",
            ),
            _shape(
                f"Fine Rule {index + 1}", start=start, end=end,
                x=width * .74, y=height * .58, width=width * .22, height=2,
                fill="#5c554d", role="rule",
            ),
            _text(
                f"Quiet Body {index + 1}", body, start=start, end=end,
                x=width * .74, y=height * .69, width=width * .36,
                size=height * .026, fill="#5c554d", family="Georgia", weight=400, role="body",
            ),
        ))
    return layers


def _drama_club(spec, width, height, controls) -> list[MotionLayer]:
    layers, _uri, duration, accent, _surface = _base(spec, width, height, controls)
    ranges = _scene_ranges(duration, len(spec["scenes"]))
    for index, ((kicker, title, body), (start, end)) in enumerate(zip(spec["scenes"], ranges)):
        spotlight = _shape(
            f"Spotlight {index + 1}", start=start, end=end,
            x=width * .5, y=height * .38, width=height * (.36 + index * .08),
            height=height * (.36 + index * .08), fill="#35fff1cc", shape="ellipse",
            role="spotlight",
        )
        spotlight.transform.scale = _keys("vector2", [1,1], ((0,[.25,.25]),(900,[1.0,1.0])))
        spotlight.effects.append(_effect("glow", radius=28.0, intensity=1.0))
        layers.append(spotlight)
        stage_title = _text(
            f"Stage Title {index + 1}", title.upper(), start=start, end=end,
            x=width * .5, y=height * .51, width=width * .88,
            size=height * (.10 if index < 3 else .13), fill="#ffffff",
            align="center", family="Georgia", role="headline", animation="pop-in",
        )
        _add_hit(stage_title, overshoot=1.22)
        stage_title.effects.append(_effect("directional_blur", radius=5.0, angle=0.0))
        layers.append(stage_title)
        layers.append(_text(
            f"Stage Billing {index + 1}", f"{kicker} / {body}", start=start, end=end,
            x=width * .5, y=height * .78, width=width * .70,
            size=height * .025, fill=accent, align="center", role="body",
        ))
    return layers


def _local_craft(spec, width, height, controls) -> list[MotionLayer]:
    layers, uri, duration, accent, _surface = _base(spec, width, height, controls)
    ranges = _scene_ranges(duration, len(spec["scenes"]))
    grid = ((.22,.28),(.52,.28),(.82,.28),(.22,.72),(.52,.72),(.82,.72))
    for index, ((kicker, title, body), (start, end)) in enumerate(zip(spec["scenes"], ranges)):
        for tile_index, (px, py) in enumerate(grid):
            tile = _image(
                f"Print Tile {index + 1}.{tile_index + 1}", uri, start=start, end=end,
                x=width * px, y=height * py, width=width * .25, height=height * .34,
                role=f"pattern_slot_{tile_index + 1}", rotation=(-2 + tile_index % 3 * 2),
            )
            tile.transform.scale = _keys("vector2", [1,1], ((0,[0,0]),(180 + tile_index*90,[1.06,1.06]),(350 + tile_index*90,[1,1])))
            tile.effects.append(_effect("posterize", levels=6.0))
            tile.behaviors.append(MotionBehaviorRef(kind="wiggle", start_ms=0, end_ms=end-start, params={"amplitude": 3.0, "frequency": 2.0 + tile_index*.15}))
            layers.append(tile)
        stamp = _shape(
            f"Maker Stamp {index + 1}", start=start, end=end,
            x=width * .5, y=height * .5, width=height * .34, height=height * .34,
            fill="#ddd8784a", shape="ellipse", role="stamp",
        )
        _animate_entry(stamp, scale=.15)
        stamp.effects.append(_effect("fractal_noise", amount=.18, scale=26.0, octaves=2.0, seed=float(index + 20), phase=0.0))
        layers.append(stamp)
        layers.append(_text(
            f"Craft Title {index + 1}", f"{kicker}\n{title}", start=start, end=end,
            x=width * .5, y=height * .5, width=width * .42,
            size=height * .052, fill="#fff8e9", align="center", family="Georgia", role="headline",
        ))
    return layers


def _variable_type(spec, width, height, controls) -> list[MotionLayer]:
    layers, _uri, duration, accent, _surface = _base(spec, width, height, controls)
    ranges = _scene_ranges(duration, len(spec["scenes"]))
    for index, ((kicker, title, _body), (start, end)) in enumerate(zip(spec["scenes"], ranges)):
        words = title.split()
        for word_index, word in enumerate(words):
            for depth_index, depth_fill in enumerate(("#101318", "#00b8d9", "#ee3d8f")):
                depth = _text(
                    f"Type Depth {index + 1}.{word_index + 1}.{depth_index + 1}", word,
                    start=start, end=end,
                    x=width * (.22 + (word_index % 2) * .44) + (3 - depth_index) * 7,
                    y=height * (.22 + word_index * .24) + (3 - depth_index) * 7,
                    width=width * .66, size=height * (.15 if word_index == 0 else .12),
                    fill=depth_fill, align="center", role="type_depth", animation="pop-in",
                    rotation=(-4.0 if word_index % 2 == 0 else 3.0),
                )
                _add_hit(depth, delay=depth_index * 35, overshoot=1.18)
                layers.append(depth)
            layer = _text(
                f"Type Hit {index + 1}.{word_index + 1}", word, start=start, end=end,
                x=width * (.22 + (word_index % 2) * .44),
                y=height * (.22 + word_index * .24), width=width * .66,
                size=height * (.15 if word_index == 0 else .12),
                fill=(accent if word_index == 1 else "#f2eee5"),
                align="center", role="headline", animation="pop-in",
                rotation=(-4.0 if word_index % 2 == 0 else 3.0),
            )
            layer.transform.position = _keys(
                "vector2", layer.transform.position.default,
                ((0, [-width*.2 if word_index%2==0 else width*1.2, layer.transform.position.default[1]]),
                 (420 + word_index*120, layer.transform.position.default)),
            )
            layers.append(layer)
        layers.append(_shape(
            f"Type Slash {index + 1}", start=start, end=end,
            x=width * .72, y=height * .72, width=width * .36, height=height * .045,
            fill=accent, role="rhythm_bar", rotation=-8,
        ))
        layers.append(_text(
            f"Type Kicker {index + 1}", kicker, start=start, end=end,
            x=width * .88, y=height * .12, width=width * .18,
            size=height * .024, fill="#ffffff", align="right", role="kicker",
        ))
    return layers


def _liquid_glass(spec, width, height, controls) -> list[MotionLayer]:
    layers, _uri, duration, accent, _surface = _base(spec, width, height, controls)
    ranges = _scene_ranges(duration, len(spec["scenes"]))
    card_positions = ((.25,.38),(.57,.28),(.72,.62),(.40,.70))
    for index, ((kicker, title, body), (start, end)) in enumerate(zip(spec["scenes"], ranges)):
        for card_index in range(index + 1):
            px, py = card_positions[card_index]
            card = _shape(
                f"Glass Card {index + 1}.{card_index + 1}", start=start, end=end,
                x=width * px, y=height * py, width=width * (.28 + card_index*.025),
                height=height * .29, fill="#2cffffff", radius=height*.035,
                role="glass_card", rotation=(-3 + card_index*2),
            )
            card.effects.append(make_glass_effect(preset="frosted" if card_index < index else "liquid_cta"))
            card.effects.append(_effect("light_sweep", intensity=.75, width=.13, angle=24.0, position=.42))
            _animate_entry(card, dy=height * .20, scale=.74)
            layers.append(card)
        backdrop_type = _text(
            f"Glass Backdrop Type {index + 1}", kicker.upper(), start=start, end=end,
            x=width * .43, y=height * .18, width=width * .82,
            size=height * .18, fill="#26ffffff", align="center", role="depth_type",
            animation="pop-in",
        )
        backdrop_type.effects.append(_effect("glow", radius=18.0, intensity=.45))
        layers.append(backdrop_type)
        layers.append(_text(
            f"Glass Title {index + 1}", title, start=start, end=end,
            x=width * .73, y=height * .42, width=width * .42,
            size=height * .068, fill="#ffffff", role="headline",
        ))
        layers.append(_text(
            f"Glass Detail {index + 1}", f"{kicker} / {body}", start=start, end=end,
            x=width * .73, y=height * .60, width=width * .40,
            size=height * .026, fill=accent, role="body",
        ))
    return layers


_BUILDERS = {
    "hot_2026_prompt_playground": _prompt_playground,
    "hot_2026_reality_warp": _reality_warp,
    "hot_2026_explorecore": _explorecore,
    "hot_2026_texture_check": _texture_check,
    "hot_2026_notes_app_chic": _notes_chic,
    "hot_2026_opt_out_era": _opt_out,
    "hot_2026_drama_club": _drama_club,
    "hot_2026_local_craft": _local_craft,
    "hot_2026_variable_kinetic_type": _variable_type,
    "hot_2026_liquid_glass_next": _liquid_glass,
}


def is_hot_trend_template(template_id: str) -> bool:
    return str(template_id) in _BUILDERS


def build_hot_trend_template_layers(
    template_id: str,
    spec: Mapping[str, Any],
    width: int,
    height: int,
    controls: Mapping[str, Any],
) -> list[MotionLayer]:
    layers = _BUILDERS[str(template_id)](spec, width, height, controls)
    duration = int(controls["duration_ms"])
    ranges = _scene_ranges(duration, len(spec["scenes"]))
    media_uri = str(controls.get("background_image") or "")
    for index, (start, end) in enumerate(ranges, 1):
        media_slot = _image(
            f"Replaceable Media {index:02d}", media_uri,
            start=start, end=end,
            x=width * (.12 if index % 2 else .88),
            y=height * (.18 if index % 2 else .82),
            width=width * .21, height=height * .20,
            role="media_slot",
            rotation=-3.0 if index % 2 else 3.0,
        )
        media_slot.metadata.update({
            "replaceable": "scene_media",
            "scene_index": index,
            "derived_layers_follow_source": True,
        })
        media_slot.transform.opacity.default = .28
        media_slot.effects.append(_effect("posterize", levels=8.0))
        _add_hit(media_slot, delay=80, overshoot=1.08)
        layers.append(media_slot)
    for index, ((kicker, _title, _body), (start, end)) in enumerate(
        zip(spec["scenes"], ranges),
        1,
    ):
        layers.append(MotionLayer(
            name=f"Hot Scene {index:02d} / {kicker}",
            layer_type="group",
            in_ms=start,
            out_ms=end,
            metadata={
                "template_role": "scene",
                "scene_index": index,
                "scene_name": str(kicker),
                "hot_2026_distinct_layout": True,
            },
        ))
    return layers


__all__ = ["build_hot_trend_template_layers", "is_hot_trend_template"]
