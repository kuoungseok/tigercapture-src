import unreal

registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous(["/Game/TigerStudio"], True)

asset_path = "/Game/TigerStudio/AutoLayout/painter_figma_document_snapshot_figma_artboard_2411_13170/Widgets/WBP_TS_painter_figma_document_snapshot_figma_artboard_2411_13170.WBP_TS_painter_figma_document_snapshot_figma_artboard_2411_13170"
bp = unreal.load_asset(asset_path)
tree = bp.widget_tree
root = tree.root_widget
unreal.log("TIGERWALK root=" + str(root))

def walk(w, depth=0):
    if w is None:
        return
    try:
        vis = w.get_editor_property("visibility")
    except Exception as e:
        vis = "ERR:" + str(e)
    try:
        size = w.get_editor_property("slot")
    except Exception:
        size = None
    unreal.log("TIGERWALK " + "  "*depth + str(w.get_name()) + " | " + str(type(w).__name__) + " | vis=" + str(vis))
    if isinstance(w, unreal.PanelWidget):
        for child in w.get_all_children():
            walk(child, depth+1)

walk(root)
