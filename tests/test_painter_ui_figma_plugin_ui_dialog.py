from app.painter_ui_figma_plugin_ui_dialog import build_sandboxed_plugin_html


def test_fp3_webview_document_injects_message_bridge_csp_and_dark_theme() -> None:
    source = "<html><head><title>Plugin</title></head><body><button>Go</button></body></html>"
    document = build_sandboxed_plugin_html(source, dark=True, theme_colors=True)

    assert "default-src 'none'" in document
    assert "connect-src 'none'" in document
    assert "qwebchannel.js" in document
    assert "tigerPluginBridge" in document
    assert "pluginMessage" in document
    assert "pluginDrop" in document
    assert "uiDrop" in document
    assert "figma-dark" in document
    assert "--figma-color-bg:#1E1E1E" in document
    assert document.index("qwebchannel.js") < document.index("<button>Go</button>")


def test_fp3_webview_document_omits_theme_variables_when_not_requested() -> None:
    document = build_sandboxed_plugin_html("<p>Plain</p>", dark=False, theme_colors=False)

    assert "figma-light" in document
    assert "--figma-color-bg:" not in document
    assert "<p>Plain</p>" in document


def test_fp3_webview_document_opens_only_approved_csp_sources() -> None:
    document = build_sandboxed_plugin_html(
        "<p>Network</p>",
        dark=False,
        theme_colors=False,
        allowed_domains=("https://api.example.com/v1/", "*.cdn.example.com"),
    )

    assert "connect-src https://api.example.com" in document
    assert "https://*.cdn.example.com" in document
    assert "http://*.cdn.example.com" in document
