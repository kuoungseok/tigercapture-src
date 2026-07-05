from __future__ import annotations

from types import SimpleNamespace


class FakeStyle:
    def __init__(self, events: list[tuple]) -> None:
        self._events = events

    def unpolish(self, widget) -> None:
        self._events.append(("unpolish", widget))

    def polish(self, widget) -> None:
        self._events.append(("polish", widget))


class FakeButton:
    def __init__(self, events: list[tuple]) -> None:
        self.properties: dict[str, object] = {}
        self.tooltip = ""
        self.updated = False
        self._style = FakeStyle(events)

    def setProperty(self, name: str, value: object) -> None:
        self.properties[name] = value

    def setToolTip(self, text: str) -> None:
        self.tooltip = text

    def style(self) -> FakeStyle:
        return self._style

    def update(self) -> None:
        self.updated = True


def _attach_startup_template_wrappers(owner: SimpleNamespace, controller) -> None:
    owner._startup_template_status = lambda: controller._startup_template_status(owner)
    owner._refresh_startup_template_ui = lambda: controller._refresh_startup_template_ui(owner)
    owner._startup_template_has_media_target = lambda: controller._startup_template_has_media_target(owner)
    owner._startup_template_target_state = lambda: controller._startup_template_target_state(owner)
    owner._startup_template_required_target_gap = (
        lambda preset, **kwargs: controller._startup_template_required_target_gap(
            owner,
            preset,
            **kwargs,
        )
    )
    owner._startup_template_preset = lambda: controller._startup_template_preset(owner)


def test_show_startup_template_hint_sets_state_and_refreshes_duck_typed_ui():
    from app import video_editor_startup_template_controller as controller

    events: list[tuple] = []
    owner = SimpleNamespace(
        template_browser_btn=FakeButton(events),
        _flash_status=lambda message: events.append(("flash", message)),
    )

    def set_placeholder(kind: str) -> None:
        owner._preview_placeholder_kind = kind
        events.append(("placeholder", kind))

    owner._set_preview_placeholder = set_placeholder

    controller.show_startup_template_hint(owner, "template-intro", "Intro Template")

    status = controller._startup_template_status(owner)
    assert status == {
        "id": "template-intro",
        "name": "Intro Template",
        "pending": True,
        "applied": False,
        "last_failure": "",
        "state": "ready",
        "preview_placeholder": "template",
    }
    assert owner.template_browser_btn.properties["startupTemplate"] is True
    assert "Template ready: Intro Template" in owner.template_browser_btn.tooltip
    assert "Import media to auto-apply this template." in owner.template_browser_btn.tooltip
    assert owner.template_browser_btn.updated is True
    assert ("placeholder", "template") in events
    assert ("flash", "Template ready: Intro Template") in events


def test_startup_template_auto_applies_after_first_video_media(monkeypatch):
    import app.preset_library as preset_library
    from app import video_editor_startup_template_controller as controller
    from app.preset_library import EditorPreset

    template = EditorPreset(
        id="template-auto-apply",
        kind="template",
        name="Auto Apply Template",
        payload={"sequence": []},
    )
    monkeypatch.setattr(
        preset_library,
        "preset_by_id",
        lambda preset_id: template if str(preset_id) == template.id else None,
    )

    events: list[tuple] = []
    owner = SimpleNamespace(
        _startup_template_id=template.id,
        _startup_template_name=template.name,
        _startup_template_pending=True,
        _startup_template_applied=False,
        _startup_template_last_failure="",
        _tracks=[SimpleNamespace(source_path=None, clips=[object()])],
        _audio_tracks=[],
        _live2d_actor_tracks=[],
        _spine_actor_tracks=[],
        _capcut_feature_disabled=lambda _feature: False,
        _preset_apply_failure_reason=lambda _preset: "",
        _apply_editor_preset_object=lambda preset, depth=0: events.append(("apply", preset.id, depth)) or True,
        _workflow_apply_summary_rows=lambda _preset: [
            {"kind": "effect", "status": "will_apply"},
            {"kind": "title", "status": "will_apply"},
        ],
        _flash_status=lambda message: events.append(("flash", message)),
    )
    _attach_startup_template_wrappers(owner, controller)

    def finish(preset, *, undo_context: str, status_prefix: str) -> None:
        events.append(("finish", preset.id, undo_context, status_prefix))
        owner._flash_status(f"{status_prefix}: {preset.name}")

    owner._finish_workflow_preset_application = finish

    assert controller._try_apply_startup_template_if_ready(owner, "video import")
    assert owner._startup_template_pending is False
    assert owner._startup_template_applied is True
    assert owner._startup_template_last_failure == ""
    assert owner._pending_workflow_apply_summary_rows == [
        {"kind": "effect", "status": "will_apply"},
        {"kind": "title", "status": "will_apply"},
    ]
    assert ("apply", template.id, 0) in events
    assert ("finish", template.id, "startup template", "Template applied") in events
    assert ("flash", "Template applied: Auto Apply Template") in events

    events.clear()
    assert not controller._try_apply_startup_template_if_ready(owner, "video import")
    assert events == []


def test_startup_template_waits_for_video_media_before_video_only_child(monkeypatch):
    import app.preset_library as preset_library
    from app import video_editor_startup_template_controller as controller
    from app.preset_library import EditorPreset

    template = EditorPreset(
        id="template-video-required",
        kind="template",
        name="Video Required Template",
        payload={"sequence": [{"preset_id": "effect-video-required", "kind": "effect"}]},
    )
    effect = EditorPreset(
        id="effect-video-required",
        kind="effect",
        name="Video Effect",
    )
    by_id = {template.id: template, effect.id: effect}
    monkeypatch.setattr(preset_library, "preset_by_id", lambda preset_id: by_id.get(str(preset_id)))

    events: list[tuple] = []
    owner = SimpleNamespace(
        _startup_template_id=template.id,
        _startup_template_name=template.name,
        _startup_template_pending=True,
        _startup_template_applied=False,
        _startup_template_last_failure="",
        _tracks=[],
        _audio_tracks=[SimpleNamespace(is_loaded=True, clips=[object()])],
        _live2d_actor_tracks=[],
        _spine_actor_tracks=[],
        _capcut_feature_disabled=lambda _feature: False,
        _preset_apply_failure_reason=lambda _preset: "",
        _apply_editor_preset_object=lambda _preset, depth=0: (_ for _ in ()).throw(AssertionError("should not apply")),
        _flash_status=lambda message: events.append(("flash", message)),
    )
    _attach_startup_template_wrappers(owner, controller)

    assert not controller._try_apply_startup_template_if_ready(owner, "audio import")
    assert owner._startup_template_pending is True
    assert owner._startup_template_applied is False
    assert "비디오 미디어" in owner._startup_template_last_failure
    assert any("비디오 미디어" in item[1] for item in events if item[0] == "flash")


def test_startup_template_waits_for_audio_media_before_audio_child(monkeypatch):
    import app.preset_library as preset_library
    from app import video_editor_startup_template_controller as controller
    from app.preset_library import EditorPreset

    template = EditorPreset(
        id="template-audio-required",
        kind="template",
        name="Audio Required Template",
        payload={"sequence": [{"preset_id": "audio-required", "kind": "audio"}]},
    )
    audio = EditorPreset(
        id="audio-required",
        kind="audio",
        name="Audio Cleanup",
    )
    by_id = {template.id: template, audio.id: audio}
    monkeypatch.setattr(preset_library, "preset_by_id", lambda preset_id: by_id.get(str(preset_id)))

    events: list[tuple] = []
    owner = SimpleNamespace(
        _startup_template_id=template.id,
        _startup_template_name=template.name,
        _startup_template_pending=True,
        _startup_template_applied=False,
        _startup_template_last_failure="",
        _tracks=[SimpleNamespace(source_path="clip.mp4", clips=[])],
        _audio_tracks=[],
        _live2d_actor_tracks=[],
        _spine_actor_tracks=[],
        _capcut_feature_disabled=lambda _feature: False,
        _preset_apply_failure_reason=lambda _preset: "",
        _apply_editor_preset_object=lambda _preset, depth=0: (_ for _ in ()).throw(AssertionError("should not apply")),
        _flash_status=lambda message: events.append(("flash", message)),
    )
    _attach_startup_template_wrappers(owner, controller)

    assert not controller._try_apply_startup_template_if_ready(owner, "video import")
    assert owner._startup_template_pending is True
    assert owner._startup_template_applied is False
    assert "오디오 미디어" in owner._startup_template_last_failure
    assert any("오디오 미디어" in item[1] for item in events if item[0] == "flash")

