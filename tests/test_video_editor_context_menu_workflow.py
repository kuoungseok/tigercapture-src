from __future__ import annotations

from pathlib import Path


def test_context_menu_text_uses_readable_korean_and_english() -> None:
    from app.i18n import initialize, set_language
    from app.video_editor_context_menu_workflow import _context_menu_text

    initialize()
    set_language("ko")
    assert _context_menu_text("오디오 연결", "Link audio") == "오디오 연결"
    assert _context_menu_text("위로 이동 (레이어 올리기)", "Move up") == "위로 이동 (레이어 올리기)"

    set_language("en")
    assert _context_menu_text("오디오 연결", "Link audio") == "Link audio"


def test_timeline_context_menu_workflow_has_no_known_mojibake_labels() -> None:
    source = Path("app/video_editor_context_menu_workflow.py").read_text(encoding="utf-8")
    for token in (
        "?ㅻ뵒",
        "?꾨줈",
        "?꾨옒",
        "?ш린??",
        "??젣",
        "?대┰ ?댄럺",
    ):
        assert token not in source


def test_track_context_menu_language_fallbacks_do_not_mojibake() -> None:
    from app.i18n import initialize, set_language, tr
    from app.video_editor_context_menu_workflow import _context_menu_text

    initialize()
    ko_link = "\uc624\ub514\uc624 \uc5f0\uacb0"
    ko_move = "\uc704\ub85c \uc774\ub3d9 (\ub808\uc774\uc5b4 \uc62c\ub9ac\uae30)"
    localized_keys = (
        "veditor.menu.blade_at_playhead",
        "veditor.menu.ripple_delete",
        "veditor.menu.extract_audio",
        "veditor.menu.delete_track",
    )
    for lang in ("ko", "en", "ja", "zh", "fr", "de"):
        set_language(lang)
        link_label = _context_menu_text(ko_link, "Link audio")
        move_label = _context_menu_text(ko_move, "Move up (raise layer)")
        assert "\ufffd" not in link_label
        assert "\ufffd" not in move_label
        if lang == "ko":
            assert link_label == ko_link
            assert move_label == ko_move
        else:
            assert link_label == "Link audio"
            assert move_label == "Move up (raise layer)"
        for key in localized_keys:
            text = tr(key)
            assert "\ufffd" not in text
            assert "??" not in text
