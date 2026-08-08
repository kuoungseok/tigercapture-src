from __future__ import annotations

from app.motion_designer.curves import interpolate_value
from app.motion_designer.vector_shapes import (
    VectorPath, VectorPoint, flatten_path, path_from_params, primitive_path,
    repeater_instances, trim_polylines,
)


def test_vector_path_round_trip_and_bezier_flattening_are_deterministic() -> None:
    path = VectorPath(closed=False, points=[
        VectorPoint((0.0, 0.0), out_tangent=(40.0, 80.0)),
        VectorPoint((100.0, 0.0), in_tangent=(-40.0, 80.0)),
    ])
    restored = VectorPath.from_dict(path.to_dict())
    first = flatten_path(restored, tolerance=.25)
    second = flatten_path(restored, tolerance=.25)
    assert first == second
    assert first[0] == (0.0, 0.0)
    assert first[-1] == (100.0, 0.0)
    assert max(point[1] for point in first) > 50.0


def test_polygon_star_and_rounded_rectangle_primitives_have_expected_topology() -> None:
    assert len(primitive_path("polygon", 200, 120, {"sides": 6}).points) == 6
    assert len(primitive_path("star", 200, 120, {"sides": 7}).points) == 14
    rounded = primitive_path("rectangle", 200, 120, {"radius": 18})
    assert len(rounded.points) == 8
    assert any(point.in_tangent != (0.0, 0.0) for point in rounded.points)
    ellipse = primitive_path("ellipse", 200, 120)
    assert len(ellipse.points) == 4
    assert len(flatten_path(ellipse, tolerance=.25)) > 16


def test_path_params_accept_generated_primitive_alias() -> None:
    ellipse = path_from_params({"primitive": "ellipse", "width": 200, "height": 120})
    assert len(ellipse.points) == 4
    assert len(flatten_path(ellipse, tolerance=.25)) > 16


def test_trim_path_supports_closed_wrap_and_repeater_is_bounded() -> None:
    square = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0),
              (0.0, 100.0), (0.0, 0.0)]
    quarter = trim_polylines(square, 0.0, .25, closed=True)
    assert quarter == [[(0.0, 0.0), (100.0, 0.0)]]
    wrapped = trim_polylines(square, .75, .25, closed=True)
    assert len(wrapped) == 2
    instances = repeater_instances({
        "count": 600, "offset": [12, -4], "rotation": 8,
        "scale": [.9, .8], "opacity_start": 1, "opacity_end": .2,
    })
    assert len(instances) == 512
    assert instances[2]["translate"] == [24.0, -8.0]
    assert instances[2]["rotation"] == 16.0
    assert instances[-1]["opacity"] == .2


def test_nested_path_keyframe_values_interpolate_without_switching_whole_path() -> None:
    start = {"closed": False, "points": [{"position": [0.0, 10.0], "in": [0, 0], "out": [0, 0]}]}
    end = {"closed": False, "points": [{"position": [100.0, 30.0], "in": [0, 0], "out": [0, 0]}]}
    middle = interpolate_value(start, end, .5)
    assert middle["points"][0]["position"] == [50.0, 20.0]
    path = path_from_params({
        "width": 200, "height": 100, "shape": "path",
        "path": {"value_type": "path", "default": start, "keyframes": [
            {"time_ms": 0, "value": start}, {"time_ms": 1000, "value": end},
        ]},
    }, 500)
    assert path.points[0].position == (50.0, 20.0)
