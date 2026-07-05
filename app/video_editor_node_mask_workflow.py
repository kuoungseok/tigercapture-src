from __future__ import annotations

from app.i18n import tr


def build_node_item_chain(scene, target_node=None) -> list:
    from app.workbench.node_graph.items.blur_node_item import BlurNodeItem
    from app.workbench.node_graph.items.io_node import IONodeItem
    from app.workbench.node_graph.items.node_item import NodeItem
    from app.workbench.node_graph.items.parallel_mixer import ParallelMixerItem

    if target_node is None:
        target_node = scene._out_node
    if isinstance(target_node, IONodeItem) and target_node.kind == "IN":
        return []
    chain_nodes: list = []
    cur = target_node
    seen: set[int] = set()
    if isinstance(cur, IONodeItem) and cur.kind == "OUT":
        for port_name in ("rgb_in", "in_port", "input_port"):
            in_p = getattr(cur, port_name, None)
            if in_p is not None and getattr(in_p, "connections", None):
                upstream = in_p.connections[0].source.parentItem()
                if upstream is not None:
                    cur = upstream
                break
    if isinstance(cur, (NodeItem, ParallelMixerItem, BlurNodeItem)):
        chain_nodes.append(cur)
        seen.add(id(cur))
    while True:
        in_port = getattr(cur, "rgb_in", None)
        if in_port is None or not in_port.connections:
            break
        up_conn = in_port.connections[0]
        upstream = up_conn.source.parentItem()
        if upstream is None or id(upstream) in seen:
            break
        seen.add(id(upstream))
        if isinstance(upstream, IONodeItem) and upstream.kind == "IN":
            break
        chain_nodes.append(upstream)
        cur = upstream
    chain_nodes.reverse()
    result = []
    for node in chain_nodes:
        if not isinstance(node, (NodeItem, ParallelMixerItem, BlurNodeItem)):
            continue
        if getattr(node, "bypassed", False):
            continue
        result.append((node, getattr(node, "masks", None) or []))
    return result


def select_view_target_node(self, scene):
    return scene._out_node


def apply_node_effect(node, rgb, masks: list, frame_idx: int):
    from app.node_mask import evaluate_node_masks

    kind = getattr(node, "NODE_KIND", "serial")
    if kind == "blur":
        params = getattr(node, "blur_params", None)
        if params is None or params.is_identity():
            return rgb
        mask = evaluate_node_masks(masks, rgb, frame_idx) if masks else None
        return params.apply_with_mask(
            rgb,
            mask,
            invert_mask=bool(getattr(node, "blur_invert_mask", True)),
        )
    grade = getattr(node, "color_grade", None)
    if grade is None or grade.is_identity():
        return rgb
    from app.color_grading import apply_to_rgb

    if masks:
        mask = evaluate_node_masks(masks, rgb, frame_idx)
        if mask is not None:
            import numpy as np

            graded = apply_to_rgb(rgb, grade).astype("float32")
            blended = mask[..., None] * graded + (1.0 - mask[..., None]) * rgb.astype("float32")
            return np.clip(blended, 0, 255).astype("uint8")
    return apply_to_rgb(rgb, grade)


def evaluate_node_chain_with_masks(scene, target_node=None):
    from app.workbench.node_graph.items.io_node import IONodeItem
    from app.workbench.node_graph.items.node_item import NodeItem
    from app.workbench.node_graph.items.parallel_mixer import ParallelMixerItem

    if target_node is None:
        target_node = scene._out_node
    if isinstance(target_node, IONodeItem) and target_node.kind == "IN":
        return [], []
    chain_nodes: list = []
    cur = target_node
    seen: set[int] = set()
    if isinstance(cur, (NodeItem, ParallelMixerItem)):
        chain_nodes.append(cur)
        seen.add(id(cur))
    while True:
        in_port = getattr(cur, "rgb_in", None)
        if in_port is None or not in_port.connections:
            break
        up_conn = in_port.connections[0]
        upstream = up_conn.source.parentItem()
        if upstream is None or id(upstream) in seen:
            break
        seen.add(id(upstream))
        if isinstance(upstream, IONodeItem) and upstream.kind == "IN":
            break
        chain_nodes.append(upstream)
        cur = upstream
    chain_nodes.reverse()
    grades: list = []
    masks: list = []
    for node in chain_nodes:
        if not isinstance(node, (NodeItem, ParallelMixerItem)):
            continue
        if getattr(node, "bypassed", False):
            continue
        grade = getattr(node, "color_grade", None)
        if grade is None:
            continue
        grades.append(grade)
        masks.append(getattr(node, "masks", None) or None)
    return grades, masks


def on_node_mask_request(self, node, kind: str) -> None:
    from app.node_mask import HSLQualifier, MagicMask
    from app.node_mask_dialogs import HSLQualifierDialog, MagicMaskDialog

    if node is None:
        return
    on_change = self._refresh_preview_for_mask_edit
    if kind == "clear":
        node.masks = []
        node.update()
        self._rebuild_active_chain()
        return
    if kind == "hsl":
        mask = HSLQualifier()
        node.masks = [mask]
        self._rebuild_active_chain()
        HSLQualifierDialog(mask, on_change=on_change, parent=self).exec()
        on_change()
        return
    if kind.startswith("magic:"):
        feature = kind.split(":", 1)[1]
        if feature == "eyes":
            node.masks = [MagicMask(feature="left_eye"), MagicMask(feature="right_eye")]
        else:
            node.masks = [MagicMask(feature=feature)]
        node.update()
        self._rebuild_active_chain()
        on_change()
        if node.masks and isinstance(node.masks[0], MagicMask):
            MagicMaskDialog(node.masks[0], on_change=on_change, parent=self).exec()
            on_change()
        return
    if kind in ("power_window", "roto:grabcut", "roto:sam", "track_region", "edit"):
        rgb = self._current_preview_rgb()
        if rgb is None:
            self._flash_status(tr("nodemask.flash.no_frame"))
            return
        from app.mask_editor_window import MaskEditorWindow

        initial_tool = {
            "power_window": "polygon",
            "roto:grabcut": "rect",
            "roto:sam": "click",
            "track_region": "rect",
            "edit": None,
        }.get(kind, "rect")
        dlg = MaskEditorWindow.open_for_node(
            rgb,
            node,
            on_commit=on_change,
            parent=self,
            frame_idx=self._current_preview_frame_idx(),
        )
        if initial_tool:
            dlg._set_tool(initial_tool)
        if kind == "track_region":
            try:
                dlg._track_chk.setChecked(True)
            except Exception:
                pass
        dlg.exec()
        on_change()


def _enter_grabcut_mode(self, node) -> None:
    canvas = getattr(self, "_drawing_canvas", None)
    if canvas is None:
        return
    self._flash_status(tr("nodemask.flash.draw_rect"))
    self._roto_target = (node, "grabcut")
    canvas.set_rect_hook(self._on_rotoscope_rect)


def current_preview_rgb(self):
    latest = getattr(self, "_latest_preview_rgb", None)
    if latest is not None:
        try:
            import numpy as np

            arr = np.asarray(latest)
            if arr.ndim == 3 and arr.shape[2] >= 3:
                if arr.dtype != np.uint8:
                    arr = np.clip(arr, 0, 255).astype(np.uint8)
                if (
                    self._preview_tab_guard_active()
                    and self._active_renderable_clip_at_current_position()
                    and self._rgb_looks_like_blank_preview(arr)
                ):
                    recovered = self._preview_recovery_rgb()
                    if recovered is not None:
                        return recovered
                return np.ascontiguousarray(arr[:, :, :3]).copy()
        except Exception:
            pass
    pix = getattr(self, "_preview_pixmap", None)
    if pix is None or pix.isNull():
        recovered = self._preview_recovery_rgb() if hasattr(self, "_preview_recovery_rgb") else None
        return recovered
    if (
        self._preview_black_recovery_active()
        and self._active_renderable_clip_at_current_position()
        and self._pixmap_looks_like_black_frame(pix)
    ):
        recovered = self._preview_recovery_rgb()
        if recovered is not None:
            return recovered
    from PySide6.QtGui import QImage
    import numpy as np

    img = pix.toImage().convertToFormat(QImage.Format.Format_RGB888)
    width, height = img.width(), img.height()
    if width <= 0 or height <= 0:
        return None
    bytes_per_line = img.bytesPerLine()
    buf = bytes(img.bits())[: bytes_per_line * height]
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(height, bytes_per_line)[:, : width * 3]
    return np.ascontiguousarray(arr.reshape(height, width, 3))


def current_preview_frame_idx(self) -> int:
    try:
        idx = int(getattr(self._player, "_last_rendered_frame_idx", -1))
    except Exception:
        idx = -1
    return max(0, idx)


def refresh_preview_for_mask_edit(self) -> None:
    backup = self._start_preview_transition_guard(650)
    self._rebuild_active_chain()
    if hasattr(self, "_player"):
        self._player.refresh_current_frame()
    self._schedule_preview_transition_restore(backup)
    if (
        hasattr(self, "_preview_pixmap")
        and self._preview_pixmap is not None
        and hasattr(self, "_workbench_panel")
    ):
        try:
            self._workbench_panel.set_node_thumbnail(self._preview_pixmap)
        except Exception:
            pass
    workbench = getattr(self, "_workbench_panel", None)
    if workbench is not None:
        node_graph = workbench.expose_node_graph_widget()
        if node_graph is not None:
            for node in node_graph.scene._serial_nodes:
                node.update()


def mask_toolbar_action(self, kind: str) -> None:
    node = getattr(self, "_node_grade_target", None)
    if node is None:
        return
    self._on_node_mask_request(node, kind)


def _on_node_graph_selection(self, node) -> None:
        """User picked a NodeItem/BlurNodeItem (or deselected).
        Routes to the right panel based on node kind:
          - ColorNode   ??colour dock + _node_grade_target
          - BlurNode    ??workbench blur controls
          - EffectNode  ??inline _EffectParamsPanel inside the node-graph
                          widget (see ``widget.py``)
          - None        ??fall back to primary node
        """
        from app.workbench.node_graph.items.blur_node_item import BlurNodeItem
        from app.workbench.node_graph.items.effect_node_item import EffectNodeItem
        wb = getattr(self, "_workbench_panel", None)
        ngw = wb.expose_node_graph_widget() if wb is not None else None
        is_blur   = isinstance(node, BlurNodeItem)
        is_effect = isinstance(node, EffectNodeItem)

        if is_effect:
            self._node_grade_target = (
                ngw.scene._out_node if ngw is not None else None
            )

        if node is not None and not is_blur and not is_effect:
            # Color node selected: show chain up to this node.
            self._node_grade_target = node
        elif (is_blur or node is None) and not is_effect:
            # Blur node selected OR nothing selected.
            self._node_grade_target = (
                ngw.scene._out_node if ngw is not None else None
            )
        # Pull the now-active grade into the slider widgets.
        if hasattr(self, "_sync_color_panel"):
            self._sync_color_panel()
        # Reveal / hide the color dock (color nodes only).
        self._update_color_dock_visibility(node if not is_blur and not is_effect else None)
        # Route blur controls in workbench.
        if wb is not None and hasattr(wb, "set_blur_node"):
            if is_blur:
                wb.set_blur_node(node, on_change=self._on_blur_params_changed)
            elif not is_effect:
                wb.set_blur_node(None)
        # Retarget the main preview pipeline so the user sees IN??
        # selected-node output. Without this the preview always
        # showed full IN?萸UT regardless of which node the user was
        # tweaking ??confusing because mid-chain edits looked
        # smaller than they actually were.
        self._rebuild_active_chain()
        # When the selected node has a non-identity grade (e.g. a
        # colour-wheel position was saved from a previous session),
        # immediately refresh the preview so the user can SEE the
        # current grade before they touch anything. Without this the
        # preview looked unchanged after node selection and only
        # went "gray" on the first interaction, which felt like a bug.
        if (node is not None
                and hasattr(node, "color_grade")
                and node.color_grade is not None
                and not node.color_grade.is_identity()):
            from app.simple_video_player import PlayerState
            if (hasattr(self, "_player")
                    and self._player.state() is not PlayerState.PLAYING):
                self._player.refresh_current_frame()

# Interactive node-mask editing helpers moved out of VideoEditorWindow.
def _enter_sam_mode(self, node) -> None:
    """Stage 2 rotoscope ??try SAM. Falls back to GrabCut when
    the library / model isn't available so the workflow still
    produces a result."""
    try:
        from app.sam_segment import is_sam_available
        sam_ok = is_sam_available()
    except Exception:
        sam_ok = False
    if not sam_ok:
        self._flash_status(tr("nodemask.flash.sam_unavailable"))
        self._enter_grabcut_mode(node)
        return
    # SAM uses a click hook (single point) instead of a rect
    # drag. Falls back to grabcut if the click misses content.
    canvas = getattr(self, "_drawing_canvas", None)
    if canvas is None:
        return
    self._flash_status(tr("nodemask.flash.draw_rect"))
    self._roto_target = (node, "sam")
    canvas.set_click_hook(self._on_sam_click)


def _on_rotoscope_rect(self, nx, ny, nw, nh) -> None:
    """DrawingCanvas rect hook. ``(nx, ny, nw, nh)`` are
    normalised [0,1] coordinates of the user's drag rectangle.
    Run GrabCut against the current preview frame and bake the
    result into a BitmapMask attached to the active node."""
    canvas = getattr(self, "_drawing_canvas", None)
    if canvas is not None:
        canvas.set_rect_hook(None)
    target = getattr(self, "_roto_target", None)
    if not target:
        return
    node, _kind = target
    self._roto_target = None
    rgb = self._current_preview_rgb()
    if rgb is None:
        self._flash_status(tr("nodemask.flash.no_frame"))
        return
    from app.node_mask import BitmapMask, grabcut_from_rect
    mask_uint8 = grabcut_from_rect(rgb, (nx, ny, nw, nh), iterations=4)
    if mask_uint8 is None:
        return
    bm = BitmapMask()
    bm.set_from_array(mask_uint8)
    node.masks = [bm]
    node.update()
    self._rebuild_active_chain()
    self._refresh_preview_for_mask_edit()
    self._flash_status(tr("nodemask.flash.grabcut_done"))


def _on_sam_click(self, nx, ny, kind: str) -> bool:
    """Stage 2 click hook ??single point on object ??SAM mask."""
    if kind != "click":
        return False
    canvas = getattr(self, "_drawing_canvas", None)
    if canvas is not None:
        canvas.set_click_hook(None)
    target = getattr(self, "_roto_target", None)
    if not target:
        return True
    node, _kind = target
    self._roto_target = None
    rgb = self._current_preview_rgb()
    if rgb is None:
        self._flash_status(tr("nodemask.flash.no_frame"))
        return True
    try:
        from app.sam_segment import sam_mask_from_point
        mask_uint8 = sam_mask_from_point(rgb, nx, ny)
    except Exception:
        mask_uint8 = None
    if mask_uint8 is None:
        self._flash_status(tr("nodemask.flash.sam_unavailable"))
        return True
    from app.node_mask import BitmapMask
    bm = BitmapMask()
    bm.set_from_array(mask_uint8)
    node.masks = [bm]
    node.update()
    self._rebuild_active_chain()
    self._refresh_preview_for_mask_edit()
    self._flash_status(tr("nodemask.flash.grabcut_done"))
    return True


def _open_power_window_editor(self, node, mask) -> None:
    """Show the Power Window dialog and enter polygon-edit mode
    on the preview pane. Clicks on the preview append points to
    the mask; double-click closes / commits."""
    from app.node_mask_dialogs import PowerWindowDialog

    # Mark the editor as in polygon-edit mode so preview clicks
    # land on the mask instead of scrubbing.
    self._power_window_target = (node, mask)
    # Install click hook on the drawing canvas so its
    # mousePressEvent routes here while the dialog is open.
    canvas = getattr(self, "_drawing_canvas", None)
    if canvas is not None:
        canvas.set_click_hook(self._on_power_window_click)
        canvas._power_window_preview = mask
        canvas.update()
    dlg = PowerWindowDialog(
        mask, on_change=self._refresh_preview_for_mask_edit, parent=self,
    )
    self._power_window_dialog = dlg
    try:
        dlg.exec()
    finally:
        if canvas is not None:
            canvas.set_click_hook(None)
            canvas._power_window_preview = None
            canvas.update()
        self._power_window_target = None
        self._power_window_dialog = None
        self._refresh_preview_for_mask_edit()


def _on_power_window_click(self, nx: float, ny: float, kind: str) -> bool:
    """DrawingCanvas click hook for Power Window polygon edit.
    ``kind`` is ``"click"`` (add point) or ``"double"`` (commit).
    Returns True to consume the click."""
    if not getattr(self, "_power_window_target", None):
        return False
    node, mask = self._power_window_target
    if kind == "double":
        # Double-click closes the polygon ??no-op on the data
        # since polygons are already closed implicitly. Just
        # refresh and let the user keep editing if they want.
        self._refresh_preview_for_mask_edit()
        dlg = getattr(self, "_power_window_dialog", None)
        if dlg is not None and hasattr(dlg, "refresh_points_count"):
            dlg.refresh_points_count()
        return True
    mask.points.append((float(nx), float(ny)))
    self._refresh_preview_for_mask_edit()
    dlg = getattr(self, "_power_window_dialog", None)
    if dlg is not None and hasattr(dlg, "refresh_points_count"):
        dlg.refresh_points_count()
    return True

