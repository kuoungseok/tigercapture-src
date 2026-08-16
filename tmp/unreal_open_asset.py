
import unreal

ASSET_PATH = '/Game/TigerStudio/AutoLayout/painter_figma_document_snapshot_figma_artboard_2411_13170/Widgets/WBP_TS_painter_figma_document_snapshot_figma_artboard_2411_13170'

registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous(["/Game/TigerStudio"], True)


def open_asset(delta_seconds):
    unreal.unregister_slate_post_tick_callback(handle)
    asset = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    if asset is None:
        unreal.log_error("Tiger: asset not found: " + ASSET_PATH)
        return
    subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
    subsystem.open_editor_for_assets([asset])
    unreal.log("Tiger: opened " + ASSET_PATH)


# The asset editor cannot open while the engine is still starting up, so this
# defers to the first Slate tick.
handle = unreal.register_slate_post_tick_callback(open_asset)
