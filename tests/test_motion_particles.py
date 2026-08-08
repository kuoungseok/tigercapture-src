from __future__ import annotations

from app.motion_designer.particles import create_particle_layer, simulate_particles


def test_particle_simulation_is_deterministic_and_supports_emitters() -> None:
    for kind in ("point", "box", "circle", "path"):
        layer = create_particle_layer(width=640, height=360, duration_ms=2000, params={
            "emitter": {"kind": kind, "position": [320, 180], "size": [100, 60], "radius": 50,
                        "path": [[100, 100], [540, 260]]},
            "seed": 42, "birth_rate": 12, "bursts": [{"time_ms": 100, "count": 4}],
        })
        first = simulate_particles(layer, 500)
        second = simulate_particles(layer, 500)
        assert first == second
        assert first


def test_particle_life_controls_color_size_opacity_and_depth_sort() -> None:
    layer = create_particle_layer(params={
        "birth_rate": 0, "bursts": [{"time_ms": 0, "count": 8}], "lifetime_ms": 1000,
        "particle": {"shape": "square", "size_start": 20, "size_end": 4,
                     "opacity_start": 1, "opacity_end": 0, "color_start": "#ff0000",
                     "color_end": "#0000ff00", "rotation_speed": 90, "sprite_uri": ""},
    })
    early = simulate_particles(layer, 100)
    late = simulate_particles(layer, 800)
    assert len(early) == len(late) == 8
    assert early[0].size > late[0].size
    assert early[0].opacity > late[0].opacity
    assert [item.depth for item in late] == sorted(item.depth for item in late)
