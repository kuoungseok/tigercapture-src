from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QStyle, QToolBar, QToolButton

from app.i18n import SUPPORTED_LANGUAGES
from app.icons import app_icon, unreal_engine_icon

from .catalog import BEHAVIOR_ITEMS, FILTER_ITEMS, OBJECT_ITEMS


class MotionToolbar(QToolBar):
    open_project_requested = Signal()
    save_project_requested = Signal()
    save_project_as_requested = Signal()
    open_package_requested = Signal()
    export_package_requested = Signal()
    add_layer_requested = Signal(str)
    behavior_requested = Signal(str)
    effect_requested = Signal(str)
    replicator_requested = Signal()
    rig_requested = Signal(str)
    component_requested = Signal(str)
    precompose_requested = Signal()
    navigate_parent_requested = Signal()
    time_remap_requested = Signal(str)
    delete_requested = Signal()
    duplicate_requested = Signal()
    undo_requested = Signal()
    redo_requested = Signal()
    ai_toggled = Signal(bool)
    output_requested = Signal()
    template_gallery_requested = Signal()
    unreal_link_requested = Signal()
    language_requested = Signal(str)
    workspace_panel_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__("Motion Tools", parent)
        self.setMovable(False)
        style = self.style()
        self.library_button = self._workspace_button(
            "Library", QStyle.SP_DirIcon, "library",
            "Show content and object library",
        )
        self.inspector_button = self._workspace_button(
            "Inspector", QStyle.SP_FileDialogDetailedView, "inspector",
            "Show properties for the selected layer",
        )
        self.project_button = self._workspace_button(
            "Project Pane", QStyle.SP_FileDialogListView, "project",
            "Show or hide Layers, Media, and Audio",
        )
        self.addWidget(self.library_button)
        self.addWidget(self.inspector_button)
        self.addWidget(self.project_button)

        self.open_action = QAction(
            style.standardIcon(QStyle.SP_DialogOpenButton), "Open", self,
        )
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.setToolTip("Open a Tiger Studio Motion project")
        self.open_action.triggered.connect(self.open_project_requested)
        self.save_action = QAction(
            style.standardIcon(QStyle.SP_DialogSaveButton), "Save", self,
        )
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.setToolTip("Save the current Motion project")
        self.save_action.triggered.connect(self.save_project_requested)
        self.save_as_action = QAction("Save As", self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(self.save_project_as_requested)
        self.open_package_action = QAction("Open Portable Package", self)
        self.open_package_action.setToolTip(
            "Verify and open a .tgmotionpkg project with embedded resources"
        )
        self.open_package_action.triggered.connect(self.open_package_requested)
        self.export_package_action = QAction("Export Portable Package", self)
        self.export_package_action.setToolTip(
            "Collect the Motion project and local resources into one verified package"
        )
        self.export_package_action.triggered.connect(self.export_package_requested)
        file_button = QToolButton(self)
        file_button.setText("File")
        file_button.setIcon(style.standardIcon(QStyle.SP_DialogOpenButton))
        file_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        file_button.setPopupMode(QToolButton.InstantPopup)
        file_menu = QMenu(file_button)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.open_package_action)
        file_menu.addAction(self.export_package_action)
        file_button.setMenu(file_menu)
        self.addWidget(file_button)
        self.parent_action = QAction(
            style.standardIcon(QStyle.SP_ArrowUp),
            "Parent",
            self,
        )
        self.parent_action.setToolTip("Return to the parent composition")
        self.parent_action.setEnabled(False)
        self.parent_action.triggered.connect(self.navigate_parent_requested)
        self.addAction(self.parent_action)
        self.addSeparator()
        undo = QAction(style.standardIcon(QStyle.SP_ArrowBack), "Undo", self)
        redo = QAction(style.standardIcon(QStyle.SP_ArrowForward), "Redo", self)
        undo.setShortcut("Ctrl+Z")
        redo.setShortcut("Ctrl+Shift+Z")
        undo.triggered.connect(self.undo_requested)
        redo.triggered.connect(self.redo_requested)
        self.addAction(undo)
        self.addAction(redo)
        duplicate = QAction("Duplicate", self)
        duplicate.setShortcut("Ctrl+D")
        duplicate.triggered.connect(self.duplicate_requested)
        delete = QAction(style.standardIcon(QStyle.SP_TrashIcon), "Delete", self)
        delete.setShortcut("Delete")
        delete.triggered.connect(self.delete_requested)
        self.addAction(duplicate)
        self.addAction(delete)
        self.addSeparator()
        self.addWidget(self._menu_button(
            "Add Object", QStyle.SP_FileIcon, OBJECT_ITEMS, self.add_layer_requested,
        ))
        self.addWidget(self._menu_button(
            "Behaviors", QStyle.SP_MediaPlay, BEHAVIOR_ITEMS, self.behavior_requested,
        ))
        self.addWidget(self._menu_button(
            "Time",
            QStyle.SP_BrowserReload,
            (
                ("Linear Remap", "linear"),
                ("Speed Ramp", "speed_ramp"),
                ("Freeze Frame", "freeze"),
                ("Reverse Source", "reverse"),
                ("Clear Remap", "clear"),
                ("Frame Mix", "blend:frame_mix"),
                ("Optical Flow", "blend:optical_flow"),
                ("Blending Off", "blend:off"),
            ),
            self.time_remap_requested,
        ))
        self.addWidget(self._menu_button(
            "Filters", QStyle.SP_DialogApplyButton, FILTER_ITEMS, self.effect_requested,
        ))
        replicate = QToolButton(self)
        replicate.setText("Replicate")
        replicate.setIcon(app_icon("copy", size=18, color="#d9dde3"))
        replicate.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        replicate.setToolTip("Repeat the selected layer in a line, grid, or radial pattern")
        replicate.clicked.connect(self.replicator_requested)
        self.addWidget(replicate)
        self.addWidget(self._menu_button(
            "Rig", QStyle.SP_FileDialogDetailedView,
            (
                ("Full Body Rig...", "full_body"),
                ("Legacy Arm Wave...", "arm_wave"),
            ),
            self.rig_requested,
        ))
        self.addWidget(self._menu_button(
            "Component", QStyle.SP_DialogApplyButton,
            (
                ("Button", "button"),
                ("Controller Null", "controller"),
            ),
            self.component_requested,
        ))
        precompose = QAction(
            app_icon("layers", size=18, color="#d9dde3"),
            "Pre-compose",
            self,
        )
        precompose.setToolTip("Move selected layers into a nested composition")
        precompose.triggered.connect(self.precompose_requested)
        self.addAction(precompose)
        self.addSeparator()
        self.templates_button = QToolButton(self)
        self.templates_button.setText("Templates")
        self.templates_button.setIcon(
            app_icon("layout-grid", size=20, color="#d9dde3")
        )
        self.templates_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.templates_button.setToolTip("Start from a Motion template")
        self.templates_button.clicked.connect(self.template_gallery_requested)
        self.addWidget(self.templates_button)
        self.unreal_link_button = QToolButton(self)
        self.unreal_link_button.setText("Unreal Link")
        self.unreal_link_button.setIcon(
            unreal_engine_icon(22, color="#f2f4f7")
        )
        self.unreal_link_button.setIconSize(QSize(22, 22))
        self.unreal_link_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.unreal_link_button.setToolTip(
            "Connect an Unreal project and generate editable UMG assets"
        )
        self.unreal_link_button.clicked.connect(self.unreal_link_requested)
        self.addWidget(self.unreal_link_button)
        self.addSeparator()
        self.ai_action = QAction(
            app_icon("ai-script", size=18, color="#d9dde3"), "AI", self,
        )
        self.ai_action.setCheckable(True)
        self.ai_action.setChecked(False)
        self.ai_action.setToolTip("Show or hide the multimodal AI workspace")
        self.ai_action.toggled.connect(self.ai_toggled)
        self.addAction(self.ai_action)
        self.addSeparator()
        self.language_button = QToolButton(self)
        self.language_button.setText("Language")
        self.language_button.setIcon(app_icon("language", size=18, color="#d9dde3"))
        self.language_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.language_button.setPopupMode(QToolButton.InstantPopup)
        self.addWidget(self.language_button)
        output = QAction(style.standardIcon(QStyle.SP_DialogSaveButton), "Export", self)
        output.setToolTip("Open Motion delivery and color settings")
        output.triggered.connect(self.output_requested)
        self.addAction(output)

    def rebuild_language_menu(self, active_language: str) -> None:
        menu = QMenu(self.language_button)
        for code, label in SUPPORTED_LANGUAGES.items():
            action = menu.addAction(str(label))
            action.setCheckable(True)
            action.setChecked(str(code) == str(active_language))
            action.triggered.connect(
                lambda _checked=False, value=code: self.language_requested.emit(value)
            )
        self.language_button.setMenu(menu)

    def set_ai_visible(self, visible: bool) -> None:
        self.ai_action.blockSignals(True)
        self.ai_action.setChecked(bool(visible))
        self.ai_action.blockSignals(False)

    def set_parent_navigation_enabled(self, enabled: bool) -> None:
        self.parent_action.setEnabled(bool(enabled))

    def _menu_button(self, label: str, icon: QStyle.StandardPixmap, rows, signal) -> QToolButton:
        button = QToolButton(self)
        button.setText(label)
        button.setIcon(self.style().standardIcon(icon))
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(button)
        for title, value in rows:
            action = menu.addAction(title)
            action.triggered.connect(lambda _checked=False, item=value: signal.emit(item))
        button.setMenu(menu)
        return button

    def _workspace_button(
        self,
        label: str,
        icon: QStyle.StandardPixmap,
        panel: str,
        tooltip: str,
    ) -> QToolButton:
        button = QToolButton(self)
        button.setText(label)
        button.setIcon(self.style().standardIcon(icon))
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setToolTip(tooltip)
        button.clicked.connect(
            lambda _checked=False, value=panel: self.workspace_panel_requested.emit(value)
        )
        return button
