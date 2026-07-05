from __future__ import annotations

import json


def test_actor_compat_matrix_audits_spine_and_live2d_dependencies(tmp_path):
    from tools.actor_compat_matrix import build_actor_compat_matrix

    spine_dir = tmp_path / "spine"
    spine_dir.mkdir()
    spine_json = spine_dir / "hero.json"
    spine_json.write_text(
        json.dumps({"skeleton": {"spine": "4.1"}, "bones": [], "slots": []}),
        encoding="utf-8",
    )
    (spine_dir / "hero.atlas").write_text(
        "hero.png\nsize: 64,64\nformat: RGBA8888\n",
        encoding="utf-8",
    )
    (spine_dir / "hero.png").write_bytes(b"png")

    live2d_dir = tmp_path / "live2d"
    live2d_dir.mkdir()
    (live2d_dir / "model.moc3").write_bytes(b"moc")
    tex_dir = live2d_dir / "textures"
    tex_dir.mkdir()
    (tex_dir / "tex.png").write_bytes(b"png")
    model = live2d_dir / "sample.model3.json"
    model.write_text(
        json.dumps({
            "FileReferences": {
                "Moc": "model.moc3",
                "Textures": ["textures/tex.png"],
            }
        }),
        encoding="utf-8",
    )

    report = build_actor_compat_matrix([tmp_path])

    assert report["ok"] is True
    assert report["summary"]["by_kind"]["spine"]["ok"] == 1
    assert report["summary"]["by_kind"]["live2d"]["ok"] == 1
    assert report["summary"]["by_family"]["spine"]["ok"] == 1
    assert report["summary"]["by_family"]["live2d"]["ok"] == 1
    assert len(report["rows"]) == 2
    assert all("severity" in row for row in report["rows"])
    assert all("recommendation" in row for row in report["rows"])


def test_actor_compat_matrix_reports_missing_dependencies(tmp_path):
    from tools.actor_compat_matrix import build_actor_compat_matrix

    live2d_dir = tmp_path / "live2d"
    live2d_dir.mkdir()
    model = live2d_dir / "broken.model3.json"
    model.write_text(
        json.dumps({
            "FileReferences": {
                "Moc": "missing.moc3",
                "Textures": ["textures/missing.png"],
            }
        }),
        encoding="utf-8",
    )

    report = build_actor_compat_matrix([tmp_path])

    assert report["ok"] is False
    row = report["rows"][0]
    assert row["kind"] == "live2d"
    assert len(row["missing_dependencies"]) == 2
    assert row["severity"] == "high"
    assert "live2d_dependency_missing" in row["issue_codes"]
    assert row["missing_dependency_kinds"] == {
        "live2d_moc": 1,
        "live2d_texture": 1,
    }
    assert report["summary"]["issue_counts"]["live2d_dependency_missing"] == 1
    assert report["summary"]["missing_dependency_counts"]["live2d_moc"] == 1
    assert report["summary"]["top_failures"][0]["model_name"] == "broken.model3"
    assert "Restore required model3" in report["summary"]["top_failures"][0]["recommendation"]


def test_actor_compat_matrix_treats_missing_live2d_expression_as_warning(tmp_path):
    from tools.actor_compat_matrix import build_actor_compat_matrix

    live2d_dir = tmp_path / "live2d"
    live2d_dir.mkdir()
    (live2d_dir / "model.moc3").write_bytes(b"MOC3\x04")
    tex_dir = live2d_dir / "textures"
    tex_dir.mkdir()
    (tex_dir / "tex.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    model = live2d_dir / "warn.model3.json"
    model.write_text(
        json.dumps({
            "FileReferences": {
                "Moc": "model.moc3",
                "Textures": ["textures/tex.png"],
                "Expressions": [{"Name": "Smile", "File": "expressions/missing.exp3.json"}],
            }
        }),
        encoding="utf-8",
    )

    report = build_actor_compat_matrix([tmp_path])
    row = report["rows"][0]

    assert report["ok"] is True
    assert row["ok"] is True
    assert row["required_missing_dependencies"] == []
    assert len(row["optional_missing_dependencies"]) == 1
    assert row["severity"] == "medium"
    assert "live2d_optional_dependency_missing" in row["issue_codes"]
    assert "live2d_dependency_missing" not in row["issue_codes"]
    assert report["summary"]["by_kind"]["live2d"]["ok"] == 1
    assert report["summary"]["missing_dependency_counts"]["live2d_expression"] == 1


def test_actor_compat_matrix_groups_families_and_parser_failures(tmp_path):
    from tools.actor_compat_matrix import build_actor_compat_matrix

    spine_dir = tmp_path / "spine" / "bad"
    spine_dir.mkdir(parents=True)
    (spine_dir / "bad.skel").write_bytes(b"not a spine binary")
    (spine_dir / "bad.atlas").write_text(
        "missing.png\nsize: 64,64\nformat: RGBA8888\n",
        encoding="utf-8",
    )

    report = build_actor_compat_matrix([tmp_path], parse_spine=True)
    row = report["rows"][0]

    assert report["ok"] is False
    assert row["family"] == "spine/bad"
    assert row["severity"] == "high"
    assert "spine_texture_missing" in row["issue_codes"]
    assert "spine_parser_failed" in row["issue_codes"]
    assert report["summary"]["by_family"]["spine/bad"]["failed"] == 1
    assert report["summary"]["issue_counts"]["spine_parser_failed"] == 1


def test_actor_compat_matrix_prefers_same_stem_spine_json(tmp_path):
    from tools.actor_compat_matrix import find_spine_models

    spine_dir = tmp_path / "spine"
    spine_dir.mkdir()
    skel = spine_dir / "hero.skel"
    spine_json = spine_dir / "hero.json"
    skel.write_bytes(b"Spine 4.2 binary sample")
    spine_json.write_text(
        json.dumps({"skeleton": {"spine": "4.2"}, "bones": [], "slots": []}),
        encoding="utf-8",
    )

    assert find_spine_models([tmp_path]) == [spine_json]
    assert find_spine_models([skel]) == [spine_json]


def test_actor_compat_matrix_classifies_spine_stress_features(tmp_path):
    from tools.actor_compat_matrix import build_actor_compat_matrix

    spine_dir = tmp_path / "spine"
    spine_dir.mkdir()
    spine_json = spine_dir / "stress.json"
    spine_json.write_text(
        json.dumps({
            "skeleton": {"spine": "4.2.0", "name": "stress"},
            "bones": [{"name": "root"}],
            "slots": [{"name": "slot", "bone": "root", "attachment": "body"}],
            "skins": [{
                "name": "default",
                "attachments": {
                    "slot": {
                        "body": {
                            "type": "mesh",
                            "uvs": [0, 0, 1, 0, 1, 1],
                            "vertices": [2, 0, 0, 0, 0.6, 0, 1, 1, 0.4],
                            "triangles": [0, 1, 2],
                        },
                        "linked": {
                            "type": "linkedmesh",
                            "skin": "default",
                            "parent": "body",
                            "uvs": [0, 0, 1, 0, 1, 1],
                        },
                    }
                },
            }],
            "ik": [{"name": "aim", "bones": ["root"], "target": "root"}],
            "events": {"hit": {}},
            "animations": {"idle": {}},
        }),
        encoding="utf-8",
    )
    (spine_dir / "stress.atlas").write_text(
        "page_a.png\nsize: 64,64\nformat: RGBA8888\n"
        "body\nbounds: 0,0,32,32\n"
        "page_b.png\nsize: 64,64\nformat: RGBA8888\n"
        "linked\nbounds: 0,0,32,32\n",
        encoding="utf-8",
    )
    (spine_dir / "page_a.png").write_bytes(b"png")
    (spine_dir / "page_b.png").write_bytes(b"png")

    report = build_actor_compat_matrix([tmp_path])
    row = report["rows"][0]

    assert report["ok"] is True
    assert row["ok"] is True
    assert row["stress_tier"] == "stress"
    assert row["mesh_count"] == 2
    assert row["weighted_mesh_count"] == 1
    assert "weighted_mesh" in row["feature_flags"]
    assert "linked_mesh" in row["feature_flags"]
    assert "multi_page_atlas" in row["feature_flags"]
    assert "spine_weighted_mesh" in row["risk_codes"]
    assert "spine_linked_mesh" in row["risk_codes"]
    assert "spine_multi_page_atlas" in row["risk_codes"]
    assert report["summary"]["risk_counts"]["spine_weighted_mesh"] == 1
    assert report["summary"]["feature_counts"]["multi_page_atlas"] == 1
    assert report["summary"]["stress_tiers"]["stress"] == 1
    assert report["summary"]["top_risks"][0]["model_name"] == "stress"


def test_actor_compat_matrix_classifies_nikke_like_spine_as_stress(tmp_path):
    from tools.actor_compat_matrix import build_actor_compat_matrix

    spine_dir = tmp_path / "nikke" / "hero"
    spine_dir.mkdir(parents=True)
    model = spine_dir / "hero.json"
    model.write_text(
        json.dumps({
            "skeleton": {"spine": "4.1.0", "name": "hero"},
            "bones": [{"name": "root"}],
            "slots": [{"name": "slot", "bone": "root", "attachment": "body"}],
            "skins": [{
                "name": "default",
                "attachments": {
                    "slot": {
                        "body": {
                            "type": "mesh",
                            "uvs": [0, 0, 1, 0, 1, 1],
                            "vertices": [2, 0, 0, 0, 0.6, 0, 1, 1, 0.4],
                            "triangles": [0, 1, 2],
                        },
                    },
                },
            }],
            "ik": [{"name": "aim", "bones": ["root"], "target": "root"}],
            "animations": {"idle": {}},
        }),
        encoding="utf-8",
    )
    (spine_dir / "hero.atlas").write_text(
        "page_a.png\nsize: 64,64\nformat: RGBA8888\n"
        "body\nbounds: 0,0,32,32\n"
        "page_b.png\nsize: 64,64\nformat: RGBA8888\n"
        "extra\nbounds: 0,0,32,32\n",
        encoding="utf-8",
    )
    (spine_dir / "page_a.png").write_bytes(b"png")
    (spine_dir / "page_b.png").write_bytes(b"png")

    report = build_actor_compat_matrix([tmp_path])
    row = report["rows"][0]

    assert row["risk_score"] == 9
    assert row["risk_codes"] == [
        "spine_constraints",
        "spine_multi_page_atlas",
        "spine_weighted_mesh",
    ]
    assert row["stress_tier"] == "stress"
    assert report["summary"]["stress_tiers"]["stress"] == 1


def test_actor_compat_matrix_classifies_live2d_stress_features(tmp_path):
    from tools.actor_compat_matrix import build_actor_compat_matrix

    live2d_dir = tmp_path / "라이브2d"
    live2d_dir.mkdir()
    (live2d_dir / "model.moc3").write_bytes(b"MOC3\x04")
    tex_dir = live2d_dir / "textures"
    tex_dir.mkdir()
    for idx in range(4):
        (tex_dir / f"tex{idx}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    motion_dir = live2d_dir / "motions"
    motion_dir.mkdir()
    motions = []
    for idx in range(21):
        path = motion_dir / f"idle{idx}.motion3.json"
        path.write_text("{}", encoding="utf-8")
        motions.append({"File": f"motions/{path.name}"})
    expr_dir = live2d_dir / "expressions"
    expr_dir.mkdir()
    (expr_dir / "smile.exp3.json").write_text("{}", encoding="utf-8")
    for name in ("physics.json", "pose.json", "display.json", "userdata.json"):
        (live2d_dir / name).write_text("{}", encoding="utf-8")
    model = live2d_dir / "stress.model3.json"
    model.write_text(
        json.dumps({
            "FileReferences": {
                "Moc": "model.moc3",
                "Textures": [f"textures/tex{idx}.png" for idx in range(4)],
                "Motions": {"Idle": motions},
                "Expressions": [{"Name": "Smile", "File": "expressions/smile.exp3.json"}],
                "Physics": "physics.json",
                "Pose": "pose.json",
                "DisplayInfo": "display.json",
                "UserData": "userdata.json",
            },
            "HitAreas": [{"Id": "Head", "Name": "Head"}],
        }),
        encoding="utf-8",
    )

    report = build_actor_compat_matrix([tmp_path])
    row = report["rows"][0]

    assert report["ok"] is True
    assert row["ok"] is True
    assert row["stress_tier"] == "stress"
    assert row["texture_count"] == 4
    assert row["motion_count"] == 21
    assert row["expression_count"] == 1
    assert row["hit_area_count"] == 1
    assert "many_textures" in row["feature_flags"]
    assert "many_motions" in row["feature_flags"]
    assert "non_ascii_path" in row["feature_flags"]
    assert "live2d_many_textures" in row["risk_codes"]
    assert "live2d_many_motions" in row["risk_codes"]
    assert "live2d_non_ascii_path" in row["risk_codes"]
    assert report["summary"]["risk_counts"]["live2d_many_motions"] == 1
    assert report["summary"]["feature_counts"]["non_ascii_path"] == 1
    assert report["summary"]["stress_tiers"]["stress"] == 1


def test_actor_compat_matrix_known_failure_quarantines_expected_failure(tmp_path):
    from tools.actor_compat_matrix import build_actor_compat_matrix

    spine_dir = tmp_path / "spine" / "bad"
    spine_dir.mkdir(parents=True)
    model = spine_dir / "bad.json"
    model.write_text(
        json.dumps({"skeleton": {"spine": "4.1"}, "bones": [], "slots": []}),
        encoding="utf-8",
    )

    report = build_actor_compat_matrix(
        [tmp_path],
        known_failures=[{
            "id": "missing-atlas-fixture",
            "kind": "spine",
            "path_suffix": "spine/bad/bad.json",
            "issue_codes": ["spine_atlas_missing"],
            "reason": "fixture intentionally lacks atlas",
        }],
    )

    row = report["rows"][0]
    assert report["ok"] is True
    assert row["ok"] is False
    assert row["quarantined"] is True
    assert row["known_failure"]["id"] == "missing-atlas-fixture"
    assert report["summary"]["failed"] == 0
    assert report["summary"]["quarantined"] == 1
    assert report["summary"]["known_failures"][0]["model_name"] == "bad"
