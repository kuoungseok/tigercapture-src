from app.painter_ui_figma_plugin_network import (
    figma_plugin_url_allowed,
    parse_figma_plugin_domain_pattern,
    validate_figma_plugin_domains,
)


def test_network_domain_matching_is_scheme_host_and_path_bounded() -> None:
    domains = ["https://api.example.com/v1/", "*.cdn.example.com"]

    assert figma_plugin_url_allowed("https://api.example.com/v1/items", domains)
    assert not figma_plugin_url_allowed("http://api.example.com/v1/items", domains)
    assert not figma_plugin_url_allowed("https://api.example.com/v2/items", domains)
    assert figma_plugin_url_allowed("https://img.cdn.example.com/a.png", domains)
    assert not figma_plugin_url_allowed("https://cdn.example.com/a.png", domains)
    assert not figma_plugin_url_allowed("file:///etc/passwd", ["*"])


def test_network_domain_validation_rejects_unsafe_patterns() -> None:
    values, errors = validate_figma_plugin_domains(
        ["none", "example.com", "ftp://example.com", "foo.*.example.com"],
        field="networkAccess.allowedDomains",
    )

    assert values == ["none", "example.com"]
    assert any("used alone" in item for item in errors)
    assert any("Unsupported network scheme" in item for item in errors)
    assert any("Wildcard" in item for item in errors)


def test_exact_path_pattern_does_not_authorize_descendants() -> None:
    pattern = parse_figma_plugin_domain_pattern("example.com/api/item")

    assert pattern.matches("https://example.com/api/item")
    assert not pattern.matches("https://example.com/api/item/child")
