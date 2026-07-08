from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.video_editor_command_bar import (
    apply_catalog_command_button_size,
    command_bar_breakpoints,
)
from app.video_editor_preset_cards import (
    _normalize_preset_query,
    _preset_alias_text,
    _preset_category_from_tags,
    _preset_query_matches,
    _preset_query_score,
)


def _command_palette_state_path() -> Path:
    try:
        from app.paths import default_save_dir

        root = default_save_dir()
    except Exception:
        root = Path.home() / ".tigercapture"
    root.mkdir(parents=True, exist_ok=True)
    return root / "command_palette_state.json"


def _load_command_palette_state() -> dict:
    try:
        raw = json.loads(_command_palette_state_path().read_text(encoding="utf-8"))
        return {
            "favorites": [str(v) for v in raw.get("favorites", [])],
            "recent": [str(v) for v in raw.get("recent", [])],
        }
    except Exception:
        return {"favorites": [], "recent": []}


def _save_command_palette_state(state: dict) -> None:
    try:
        payload = {
            "favorites": [str(v) for v in state.get("favorites", [])][:96],
            "recent": [str(v) for v in state.get("recent", [])][:64],
        }
        _command_palette_state_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _refresh_command_bar_responsive(self) -> None:
    scroll = getattr(self, "_command_bar_scroll", None)
    host = getattr(self, "_command_bar_host", None)
    if scroll is None or host is None:
        return
    try:
        width = int(scroll.viewport().width())
    except Exception:
        width = int(host.width() or self.width())
    bp = command_bar_breakpoints(width)
    tight = bp.tight
    narrow = bp.narrow
    tiny = bp.tiny

    catalog_grouped = bool(getattr(self, "_catalog_command_groups_active", False))
    left_rail = bool(getattr(self, "_command_bar_left_rail", False))
    for attr in ("_top_brand_label", "_top_breadcrumb_label"):
        widget = getattr(self, attr, None)
        if widget is not None:
            widget.setVisible(bool(catalog_grouped and not left_rail))
    for attr in (
        "_project_menu_btn",
        "_create_menu_btn",
        "_actor_menu_btn",
        "_view_menu_btn",
        "_more_tools_btn",
    ):
        widget = getattr(self, attr, None)
        if widget is not None:
            widget.setVisible(bool(catalog_grouped))
            if catalog_grouped:
                apply_catalog_command_button_size(widget, left_rail=left_rail)
    export_menu = getattr(self, "_export_menu_btn", None)
    if export_menu is not None:
        export_menu.setVisible(bool(catalog_grouped and not left_rail))
    for attr in (
        "command_palette_btn",
        "template_browser_btn",
        "creator_assist_btn",
        "script_edit_btn",
        "auto_polish_btn",
        "screenstudio_subtitle_btn",
        "vtuber_studio_btn",
    ):
        widget = getattr(self, attr, None)
        if widget is not None:
            widget.setVisible(False if catalog_grouped else not tight)
    for attr in ("language_btn", "proxy_btn", "proxy_manage_btn"):
        widget = getattr(self, attr, None)
        if widget is not None:
            widget.setVisible(False if catalog_grouped else not tiny)
    switch = getattr(self, "workspace_mode_switch", None)
    if switch is not None:
        switch.setVisible(False if catalog_grouped else not narrow)
    panels = getattr(self, "screenstudio_advanced_btn", None)
    if panels is not None:
        simple_mode = False
        try:
            simple_mode = bool(self._screenstudio_simple_mode_enabled())
        except Exception:
            simple_mode = False
        panels.setVisible(bool(simple_mode))
        panels.setText("" if tight else "Panels")
        panels.setIcon(app_icon("layers", size=16, color="#D7DAE7"))
        panels.setIconSize(icon_size(16))
        panels.setFixedWidth(42 if tight else 78)
    status = getattr(self, "proxy_status_label", None)
    if status is not None:
        status.setVisible(False if catalog_grouped else not narrow)
    for attr in ("resolution_btn", "fps_btn", "format_btn", "quality_btn", "batch_export_btn"):
        widget = getattr(self, attr, None)
        if widget is not None and catalog_grouped:
            widget.setVisible(False)

    res = getattr(self, "_export_resolution", None)
    if hasattr(self, "resolution_btn"):
        if res is None:
            label = "Orig" if tight else "Original  v"
        else:
            label = "9:16" if tuple(res) == (1080, 1920) else (f"{int(res[1])}p" if tight else f"{res[0]}x{res[1]}  v")
        self.resolution_btn.setText(label)
        self.resolution_btn.setFixedWidth(70 if tight else 126)
    if hasattr(self, "fps_btn"):
        fps = getattr(self, "_export_fps", None)
        label = "FPS" if fps is None else f"{int(fps) if fps == int(fps) else fps}"
        if not tight:
            label = "FPS Auto  v" if fps is None else f"{label} fps  v"
        self.fps_btn.setText(label)
        self.fps_btn.setFixedWidth(58 if tight else 102)
    if hasattr(self, "format_btn"):
        fmt = str(getattr(self, "_export_format_id", "mp4") or "mp4").upper()
        self.format_btn.setText(fmt if tight else f"{fmt}  v")
        self.format_btn.setFixedWidth(58 if tight else 96)
    if hasattr(self, "quality_btn"):
        quality = "Q"
        try:
            from app.video_exporter import get_quality_preset

            quality = tr(get_quality_preset(getattr(self, "_export_quality_id", "")).name_key)
        except Exception:
            quality = "Q"
        self.quality_btn.setText("Q" if tight else f"{quality}  v")
        self.quality_btn.setFixedWidth(50 if tight else 118)
    export = getattr(self, "export_btn", None)
    if export is not None:
        export.setText("")
        export.setToolTip("Export")
        if left_rail:
            export.setFixedSize(28, 28)
            export.setIcon(app_icon("export", size=14, color="#FFFFFF"))
            export.setIconSize(icon_size(14))
        else:
            export.setFixedWidth(46)
            export.setIcon(app_icon("export", size=17, color="#FFFFFF"))
            export.setIconSize(icon_size(17))
    try:
        host.adjustSize()
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            if catalog_grouped
            else (
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
                if int(host.sizeHint().width()) > max(1, width)
                else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
        )
    except Exception:
        pass


def _compact_command_bar(self, toolbar: QHBoxLayout) -> None:
    """Reduce top-bar noise by grouping low-frequency commands.

    The original buttons stay alive for existing code paths; they are just
    hidden once their actions are available from compact menus.
    """
    self._catalog_command_groups_active = True
    self._top_brand_label = QLabel("TigerCapture Studio")
    self._top_brand_label.setObjectName("TopBrandLabel")
    self._top_brand_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    toolbar.insertWidget(0, self._top_brand_label)

    self._top_breadcrumb_label = QLabel()
    self._top_breadcrumb_label.setObjectName("TopBreadcrumbLabel")
    self._top_breadcrumb_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    self._refresh_top_project_breadcrumb()
    toolbar.insertWidget(1, self._top_breadcrumb_label)

    project_entries = (
        ("New Project", self._on_new_project),
        ("Open Project", self._on_open_project),
        ("Save Project", self._on_save_project),
        ("Recovery", self._show_recovery_candidates),
        ("Relink Media", self._on_relink_project_media),
        ("Project Health", self._show_media_health),
        ("Health Center", self._open_health_center),
        ("Crash Report", self._open_crash_report),
        ("QA Dashboard", self._open_qa_dashboard),
    )
    self._project_menu_btn = self._make_command_menu_button(
        "Project",
        "New, open, save, relink, recovery, and health checks.",
    )
    self._install_lazy_action_menu(
        self._project_menu_btn,
        project_entries,
        object_name="ProjectCommandMenu",
    )
    toolbar.insertWidget(2, self._project_menu_btn)

    create_entries = (
        ("Command Palette", self._open_command_palette),
        ("Template Browser", self._open_template_browser),
        ("PPT Generator", self._open_ppt_generator),
        ("PPT From Timeline", lambda: self._open_ppt_generator(import_timeline=True)),
        ("Creator Assist", self._open_creator_assist_panel),
        ("AI Command Dock", self._toggle_ai_command_dock),
        ("Auto Polish", self._open_screenstudio_polish_panel),
        None,
        ("Import SRT", self._import_screenstudio_srt_subtitles),
        ("AI Subtitles", self._generate_ai_subtitles),
        None,
        ("Language", lambda: self._show_existing_button_menu(
            "language_btn",
            self._build_language_menu,
            anchor_attr="_create_menu_btn",
        )),
    )
    self._create_menu_btn = self._make_command_menu_button(
        "Create",
        "Templates, AI edit, captions, language, and creator helpers.",
    )
    self._install_lazy_action_menu(
        self._create_menu_btn,
        create_entries,
        object_name="CreateCommandMenu",
    )
    toolbar.insertWidget(3, self._create_menu_btn)

    actor_entries = (
        ("Add Spine at Playhead", self._add_spine_actor_at_playhead),
        ("Open Spine Editor", self._open_spine_editor),
        ("Add Live2D at Playhead", self._add_live2d_actor_at_playhead),
        ("Open Live2D Viewer", self._open_live2d_viewer),
        ("Open VTuber Studio", self._open_vtuber_broadcast_studio),
        ("Map Performance Source to Live2D", self._apply_performance_source_to_selected_live2d),
        ("Apply Video Motion to Live2D", self._apply_video_mocap_to_live2d),
        ("Auto Storyboard Live2D Motions", self._apply_live2d_motion_storyboard),
        ("Actor QA Browser", self._open_actor_qa_browser),
    )
    self._actor_menu_btn = self._make_command_menu_button(
        "Actors",
        "Spine and Live2D actor commands.",
    )
    self._install_lazy_action_menu(
        self._actor_menu_btn,
        actor_entries,
        object_name="ActorCommandMenu",
    )
    toolbar.insertWidget(4, self._actor_menu_btn)

    view_entries = (
        ("Standard Workspace", lambda: self._on_workspace_mode_selected(False)),
        ("Simple Workspace", lambda: self._on_workspace_mode_selected(True)),
        ("Toggle Secondary Panels", lambda: self.screenstudio_advanced_btn.toggle()),
        None,
        ("Viewer Popout", self._toggle_preview_popout),
        ("Timeline Popout", self._toggle_timeline_popout),
        ("Workbench Popout", self._toggle_workbench_popout),
        ("Color Popout", self._toggle_color_popout),
        None,
        ("Toggle Audio Scopes", lambda _checked=False: self.audio_scopes_btn.toggle()),
        ("Toggle Audio Mixer", lambda _checked=False: self.audio_mixer_tl_btn.toggle()),
        ("Toggle Proxy Mode", lambda _checked=False: self.proxy_btn.toggle()),
        ("Proxy Options", lambda: self._show_existing_button_menu(
            "proxy_manage_btn",
            getattr(self, "_ensure_proxy_manage_menu", None),
            anchor_attr="_view_menu_btn",
        )),
    )
    self._view_menu_btn = self._make_command_menu_button(
        "View",
        "Workspace, panel visibility, popouts, scopes, mixer, and proxy.",
    )
    self._install_lazy_action_menu(
        self._view_menu_btn,
        view_entries,
        object_name="ViewCommandMenu",
    )
    toolbar.insertWidget(5, self._view_menu_btn)

    edit_entries = (
        ("Generate Auto Polish Zooms", self._apply_screenstudio_auto_polish),
        ("Reset Active Track", self._on_reset_active_track),
        ("Refresh Actor QA Badges", self._refresh_actor_qa_badges),
        ("Timeline Zoom Out", self._shortcut_zoom_out),
        ("Timeline Zoom In", self._shortcut_zoom_in),
        ("Timeline Fit", self._shortcut_zoom_fit),
    )
    self._more_tools_btn = self._make_command_menu_button(
        "More",
        "Secondary timeline and diagnostic commands.",
    )
    self._install_lazy_action_menu(
        self._more_tools_btn,
        edit_entries,
        object_name="MoreCommandMenu",
    )
    toolbar.insertWidget(6, self._more_tools_btn)

    export_entries = (
        ("Export Current Timeline", self._on_export),
        ("Render Queue", self._on_batch_export),
        None,
        ("Resolution...", lambda: self._show_existing_button_menu(
            "resolution_btn",
            self._build_resolution_menu,
            anchor_attr="_export_menu_btn",
        )),
        ("FPS...", lambda: self._show_existing_button_menu(
            "fps_btn",
            self._build_fps_menu,
            anchor_attr="_export_menu_btn",
        )),
        ("Format...", lambda: self._show_existing_button_menu(
            "format_btn",
            self._build_format_menu,
            anchor_attr="_export_menu_btn",
        )),
        ("Quality...", lambda: self._show_existing_button_menu(
            "quality_btn",
            self._build_quality_menu,
            anchor_attr="_export_menu_btn",
        )),
    )
    self._export_menu_btn = self._make_command_menu_button(
        "Export",
        "Render queue and export settings.",
    )
    self._install_lazy_action_menu(
        self._export_menu_btn,
        export_entries,
        object_name="ExportCommandMenu",
    )
    export_index = toolbar.indexOf(self.export_btn)
    toolbar.insertWidget(max(0, export_index), self._export_menu_btn)

    for widget in (
        self.new_project_btn,
        self.open_project_btn,
        self.recovery_project_btn,
        self.relink_project_btn,
        self.media_health_btn,
        self.command_palette_btn,
        self.language_btn,
        self.template_browser_btn,
        self.creator_assist_btn,
        self.script_edit_btn,
        self.auto_polish_btn,
        self.screenstudio_subtitle_btn,
        self.workspace_mode_switch,
        self.screenstudio_advanced_btn,
        self.save_project_btn,
        self.spine_btn,
        self.live2d_btn,
        self.reset_btn,
        self.audio_scopes_btn,
        self.batch_export_btn,
        self.proxy_btn,
        self.proxy_manage_btn,
        self.proxy_status_label,
        self.zoom_out_btn,
        self.zoom_label,
        self.zoom_in_btn,
        self.zoom_fit_btn,
        self.resolution_btn,
        self.fps_btn,
        self.format_btn,
        self.quality_btn,
    ):
        widget.hide()


def _open_command_palette(self) -> None:
    rows: list[dict] = []
    try:
        for path in self._media_pool.items():
            p = Path(path)
            rows.append({
                "kind": "media",
                "label": p.name,
                "search": f"media {p.name} {path}",
                "path": str(path),
                "icon": "media",
            })
    except Exception:
        pass
    try:
        from app.preset_library import load_editor_presets

        for preset in load_editor_presets():
            kind = str(preset.kind)
            alias = _preset_alias_text(
                str(preset.name),
                _preset_category_from_tags(tuple(preset.tags), kind.title()),
                kind,
                tuple(preset.tags),
                dict(preset.payload or {}),
            )
            rows.append({
                "kind": "preset",
                "label": f"{preset.kind}: {preset.name}",
                "search": " ".join((preset.kind, preset.id, preset.name, preset.description, " ".join(preset.tags), alias)),
                "preset": preset,
                "icon": {
                    "effect": "effects",
                    "transition": "scissors",
                    "title": "cursor",
                    "template": "nest",
                    "caption_style": "list",
                    "sticker": "spark",
                    "motion": "zoom",
                    "audio": "audio",
                    "color": "palette",
                    "actor": "actors",
                }.get(str(preset.kind), "grid"),
            })
    except Exception:
        pass
    rows.extend([
        {"kind": "command", "label": "Run preset QA report", "search": "qa preset report check", "command": self._show_preset_qa_report, "icon": "scope", "shortcut": "QA", "detail": "Audit preset count, topic coverage, and broken template references."},
        {"kind": "command", "label": "Open Project Health", "search": "health readiness media proxy relink color audio preset", "command": self._show_media_health, "icon": "scope", "shortcut": "Health", "detail": "Open the project health and professional readiness dashboard."},
        {"kind": "command", "label": "Open Templates", "search": "template browser drawer workflow one click screen studio preset", "command": self._open_template_browser, "icon": "spark", "shortcut": "Templates", "detail": "Open a focused browser for one-click template presets."},
        {"kind": "command", "label": "Open PPT Generator", "search": "ppt powerpoint presentation deck slide generator document", "command": self._open_ppt_generator, "icon": "layers", "shortcut": "PPT", "detail": "Open the user presentation studio for slide editing and PPTX export."},
        {"kind": "command", "label": "Create PPT from timeline", "search": "ppt powerpoint presentation deck slide generator timeline clips export", "command": lambda: self._open_ppt_generator(import_timeline=True), "icon": "layers", "shortcut": "PPT", "detail": "Open the PPT generator with the current editor timeline converted into slide drafts."},
        {"kind": "command", "label": "Open Auto Polish panel", "search": "screen studio auto polish panel cursor click smoothing hide static background padding shadow vertical", "command": self._open_screenstudio_polish_panel, "icon": "spark", "shortcut": "Polish", "detail": "Tune Screen Studio-style cursor, click, wallpaper, shadow, and auto-zoom settings."},
        {"kind": "command", "label": "Generate Auto Polish zooms", "search": "screen studio auto polish automatic zoom cursor click metadata", "command": self._apply_screenstudio_auto_polish, "icon": "zoom", "shortcut": "Zoom", "detail": "Generate renderable zoom windows from cursor/click metadata or smart fallback points."},
        {"kind": "command", "label": "Apply one-click preset plan", "search": "auto ai template one click preset", "command": self._apply_auto_preset_plan, "icon": "spark", "shortcut": "Auto", "detail": "Analyze current media/timeline and apply compatible template/effect/audio/color presets."},
        {"kind": "command", "label": "Open Template Composer", "search": "template composer build workflow preset", "command": self._open_template_composer, "icon": "nest", "shortcut": "Build", "detail": "Create a reusable multi-step template from existing presets."},
        {"kind": "command", "label": "Manage preset packs", "search": "preset pack manager import export repair conflict", "command": self._manage_preset_packs, "icon": "layers", "shortcut": "Packs", "detail": "Enable, disable, inspect, repair, and summarize imported preset packs."},
        {"kind": "command", "label": "Run preset application corpus", "search": "preset application corpus real project qa export parity", "command": self._show_preset_application_corpus_report, "icon": "scope", "shortcut": "Corpus", "detail": "Scan real project fixtures and verify one-click preset plans plus export-bake parity."},
        {"kind": "command", "label": "Manage preset preview cache", "search": "preset preview cache warm clear thumbnail", "command": self._manage_preset_preview_cache, "icon": "proxy", "shortcut": "Cache", "detail": "Warm or clear static/current-frame preset thumbnail caches."},
        {"kind": "command", "label": "Open visual QA viewer", "search": "visual qa screenshot baseline regression layout", "command": self._open_visual_qa_viewer, "icon": "camera", "shortcut": "Visual", "detail": "Browse QA captures and approve a selected capture as a baseline."},
        {"kind": "command", "label": "Run productization loop", "search": "productization commercial polish screen studio ui render media recovery starter template qa", "command": self._show_productization_loop_report, "icon": "spark", "shortcut": "Product", "detail": "Build one consolidated report for UI, presets, render queue, media pool, Color/Audio, actor QA, recovery, and starter templates."},
        {"kind": "command", "label": "Open QA Dashboard", "search": "qa dashboard trends baseline failures timeline fuzzer color audio actor render", "command": self._open_qa_dashboard, "icon": "scope", "shortcut": "QA", "detail": "Open the product QA dashboard with recent reports, failing areas, and baseline comparisons."},
        {"kind": "command", "label": "Open Health Center", "search": "health center crash qa media proxy render actor diagnostic", "command": self._open_health_center, "icon": "scope", "shortcut": "Health", "detail": "Open the unified diagnostic center for crash, QA, render, media/proxy, and actor risks."},
        {"kind": "command", "label": "Open Crash Report", "search": "crash report recent actions repro autosave recovery logs", "command": self._open_crash_report, "icon": "bug", "shortcut": "Crash", "detail": "Open the latest crash report, recent actions, emergency autosave, and repro exporter."},
        {"kind": "command", "label": "Refresh Actor QA Badges", "search": "live2d spine compatibility pass fail atlas motion moc baseline media pool", "command": self._refresh_actor_qa_badges, "icon": "actors", "shortcut": "Actor", "detail": "Reload Live2D/Spine corpus status and show pass/fail badges in the Media Pool."},
        {"kind": "command", "label": "Open Actor QA Browser", "search": "live2d spine compatibility browser atlas motion moc golden baseline pass fail", "command": self._open_actor_qa_browser, "icon": "actors", "shortcut": "Actor", "detail": "Browse model-level Live2D/Spine pass/fail, missing dependencies, and golden baseline status."},
        {"kind": "command", "label": "Open Actor Loading Manager", "search": "live2d spine loading cache timeout progress prerender isolated probe crash", "command": self._open_actor_loading_manager, "icon": "actors", "shortcut": "Actor", "detail": "Inspect actor loading stages, cache records, prerender state, and loading QA."},
        {"kind": "command", "label": "Open VTuber Studio", "search": "vtuber broadcast studio program output source tracking avatar mapping performance source live2d", "command": self._open_vtuber_broadcast_studio, "icon": "video", "shortcut": "VTuber", "detail": "Open Program Output, Source Tracking, and Avatar Mapping monitors."},
        {"kind": "command", "label": "Map Performance Source to Live2D", "search": "live2d performance source mapping face eye mouth vtuber tracking", "command": self._apply_performance_source_to_selected_live2d, "icon": "actors", "shortcut": "Map", "detail": "Apply the active input-only Performance Source to the selected Live2D actor clip."},
        {"kind": "command", "label": "Apply Video Motion to Live2D", "search": "live2d webcam video file face mocap motion capture retarget actor storyboard export bake", "command": self._apply_video_mocap_to_live2d, "icon": "actors", "shortcut": "Mocap", "detail": "Analyze a local video, write Live2D retarget keys, and auto-storyboard model motions when available."},
        {"kind": "command", "label": "Auto Storyboard Live2D Motions", "search": "live2d motion storyboard all motions video cuts cut based automatic motion3", "command": self._apply_live2d_motion_storyboard, "icon": "actors", "shortcut": "Motion", "detail": "Split the selected Live2D actor into video-cut ranges and cycle through every model motion."},
        {"kind": "command", "label": "Import preset pack", "search": "import preset pack json", "command": self._import_preset_pack, "icon": "folder", "shortcut": "Import", "detail": "Copy a JSON preset pack into the user preset directory."},
        {"kind": "command", "label": "Export user preset pack", "search": "export user preset pack json", "command": self._export_user_preset_pack, "icon": "export", "shortcut": "Export", "detail": "Export non-bundled user presets as a portable JSON pack."},
    ])
    state = _load_command_palette_state()

    def _row_id(row: dict) -> str:
        if row.get("kind") == "media":
            return f"media:{row.get('path', '')}"
        if row.get("kind") == "preset":
            preset = row.get("preset")
            return f"preset:{getattr(preset, 'kind', '')}:{getattr(preset, 'id', '')}"
        return f"command:{row.get('label', '')}"

    dlg = QDialog(self)
    dlg.setWindowTitle("Command Palette")
    dlg.resize(640, 520)
    root = QVBoxLayout(dlg)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(8)
    search = QLineEdit()
    search.setPlaceholderText("Search media, presets, or commands")
    search.setClearButtonEnabled(True)
    root.addWidget(search)
    meta = QLabel("Favorites and recent actions float to the top. Enter applies the highlighted item.")
    meta.setStyleSheet("color:#A7ADC2;font-size:10px;")
    root.addWidget(meta)
    listw = QListWidget()
    root.addWidget(listw, 1)
    details = QLabel("Select a row to see target requirements and action details.")
    details.setWordWrap(True)
    details.setStyleSheet(
        "QLabel{background:rgba(255,255,255,8);border:1px solid #30384F;"
        "border-radius:10px;color:#A7ADC2;padding:7px;font-size:10px;}"
    )
    root.addWidget(details)
    action_row = QHBoxLayout()
    favorite_btn = QPushButton("Favorite")
    recent_btn = QPushButton("Forget Recent")
    preview_btn = QPushButton("Preview Apply")
    fix_btn = QPushButton("Fix Target")
    for btn in (favorite_btn, recent_btn, preview_btn, fix_btn):
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
    action_row.addWidget(favorite_btn)
    action_row.addWidget(recent_btn)
    action_row.addWidget(preview_btn)
    action_row.addWidget(fix_btn)
    action_row.addStretch(1)
    root.addLayout(action_row)

    def _visible_rows() -> list[tuple[int, dict, int]]:
        q = search.text()
        favorite_ids = set(str(v) for v in state.get("favorites", []) or [])
        recent_ids = [str(v) for v in state.get("recent", []) or []]
        recent_rank = {row_id: idx for idx, row_id in enumerate(recent_ids)}
        visible: list[tuple[int, dict, int]] = []
        for idx, row in enumerate(rows):
            hay = _normalize_preset_query(row.get("search") or row.get("label"))
            score = _preset_query_score(hay, q)
            if q and score <= 0:
                continue
            if not q and not _preset_query_matches(hay, q):
                continue
            visible.append((idx, row, score))
        visible.sort(
            key=lambda pair: (
                0 if _row_id(pair[1]) in favorite_ids else 1,
                recent_rank.get(_row_id(pair[1]), 9999),
                -int(pair[2] or 0),
                str(pair[1].get("kind", "")),
                str(pair[1].get("label", "")).casefold(),
            )
        )
        return visible

    def _current_row() -> dict | None:
        item = listw.currentItem()
        if item is None:
            return None
        idx = item.data(Qt.ItemDataRole.UserRole)
        try:
            return rows[int(idx)]
        except Exception:
            return None

    def _row_detail(row: dict | None) -> str:
        if not row:
            return "Select a row to see target requirements and action details."
        if row.get("kind") == "media":
            return f"Media path: {row.get('path', '')}"
        if row.get("kind") == "preset":
            preset = row.get("preset")
            reason = self._preset_apply_failure_reason(preset)
            status = f"Blocked: {reason}" if reason else "Compatible with the current target."
            tags = ", ".join(getattr(preset, "tags", ())[:6])
            desc = str(getattr(preset, "description", "") or "")
            return f"{status}\n{desc}\nTags: {tags}" if tags else f"{status}\n{desc}"
        return str(row.get("detail") or row.get("label") or "")

    def _update_action_buttons() -> None:
        row = _current_row()
        if not row:
            favorite_btn.setEnabled(False)
            recent_btn.setEnabled(False)
            preview_btn.setEnabled(False)
            fix_btn.setEnabled(False)
            favorite_btn.setText("Favorite")
            recent_btn.setText("Forget Recent")
            details.setText(_row_detail(None))
            return
        favorite_btn.setEnabled(True)
        row_id = _row_id(row)
        favorite_btn.setText("Unfavorite" if row_id in set(state.get("favorites", []) or []) else "Favorite")
        recent_btn.setEnabled(row_id in set(state.get("recent", []) or []))
        recent_btn.setText("Forget Recent")
        is_preset = row.get("kind") == "preset"
        preview_btn.setEnabled(is_preset)
        fix_btn.setEnabled(is_preset and bool(self._preset_apply_failure_reason(row.get("preset"))))
        details.setText(_row_detail(row))

    def _populate() -> None:
        listw.clear()
        favorite_ids = set(str(v) for v in state.get("favorites", []) or [])
        recent_ids = set(str(v) for v in state.get("recent", []) or [])
        for idx, row, score in _visible_rows():
            row_id = _row_id(row)
            prefix = "*" if row_id in favorite_ids else ("R" if row_id in recent_ids else " ")
            shortcut = str(row.get("shortcut", "") or "")
            score_suffix = f"  {score}" if search.text() and score else ""
            suffix = f"   [{shortcut}]" if shortcut else ""
            item = QListWidgetItem(f"{prefix}  {row.get('kind', '').upper()}  {row.get('label', '')}{suffix}")
            item.setIcon(app_icon(str(row.get("icon", "search"))))
            item.setData(Qt.ItemDataRole.UserRole, idx)
            if row.get("kind") == "preset":
                preset = row.get("preset")
                item.setToolTip(
                    f"Search score: {score_suffix.strip() or '0'}\n"
                    + str(getattr(preset, "description", "") or row.get("label", ""))
                )
            else:
                item.setToolTip(
                    f"Search score: {score_suffix.strip() or '0'}\n"
                    + str(row.get("detail") or row.get("path") or row.get("label", ""))
                )
            listw.addItem(item)
        if listw.count() > 0:
            listw.setCurrentRow(0)
        _update_action_buttons()

    def _mark_recent(row: dict) -> None:
        row_id = _row_id(row)
        recent = [str(v) for v in (state.get("recent") or []) if str(v) != row_id]
        recent.insert(0, row_id)
        state["recent"] = recent[:64]
        _save_command_palette_state(state)

    def _activate(item=None) -> None:
        item = item or listw.currentItem()
        if item is None:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        try:
            row = rows[int(idx)]
        except Exception:
            return
        _mark_recent(row)
        dlg.accept()
        if row.get("kind") == "command":
            cmd = row.get("command")
            if callable(cmd):
                cmd()
            return
        if row.get("kind") == "media":
            try:
                self._media_pool._search_edit.setText(Path(row.get("path", "")).name)
            except Exception:
                pass
            self._flash_status(f"Media found: {Path(row.get('path', '')).name}")
            return
        if row.get("kind") == "preset":
            preset = row.get("preset")
            self._clear_preset_live_preview()
            if self._apply_editor_preset_object(preset):
                self._register_change(self._preset_undo_label(preset, "command palette"))
                self._refresh_player_tracks()
                self._refresh_preview_soft()
                btn = getattr(self, "command_palette_btn", None)
                if btn is not None:
                    self._pulse_icon_button(btn, base=18, peak=25, duration=210)
                self._flash_status(f"Applied: {getattr(preset, 'name', 'preset')}")
            else:
                self._flash_status(self._preset_apply_failure_message(preset, "Preset blocked"))

    def _toggle_favorite() -> None:
        row = _current_row()
        if not row:
            return
        row_id = _row_id(row)
        favorites = [str(v) for v in (state.get("favorites") or []) if str(v) != row_id]
        if row_id not in set(state.get("favorites", []) or []):
            favorites.insert(0, row_id)
        state["favorites"] = favorites[:96]
        _save_command_palette_state(state)
        _populate()

    def _clear_recent_for_current() -> None:
        row = _current_row()
        if not row:
            return
        row_id = _row_id(row)
        state["recent"] = [str(v) for v in (state.get("recent") or []) if str(v) != row_id]
        _save_command_palette_state(state)
        _populate()

    def _preview_current() -> None:
        row = _current_row()
        if not row or row.get("kind") != "preset":
            return
        _mark_recent(row)
        self._open_preset_application_preview(row.get("preset"))
        _populate()

    def _fix_current() -> None:
        row = _current_row()
        if not row or row.get("kind") != "preset":
            return
        self._run_preset_fix_action(row.get("preset"))
        _populate()

    search.textChanged.connect(_populate)
    search.returnPressed.connect(lambda: _activate())
    listw.itemDoubleClicked.connect(_activate)
    listw.currentItemChanged.connect(lambda *_: _update_action_buttons())
    favorite_btn.clicked.connect(_toggle_favorite)
    recent_btn.clicked.connect(_clear_recent_for_current)
    preview_btn.clicked.connect(_preview_current)
    fix_btn.clicked.connect(_fix_current)
    close_btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_btns.rejected.connect(dlg.reject)
    root.addWidget(close_btns)
    _populate()
    search.setFocus()
    dlg.exec()
