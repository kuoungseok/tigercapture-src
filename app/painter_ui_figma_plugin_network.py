"""Explicit, per-run network policy for the limited Figma Plugin UI host."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


ALLOWED_NETWORK_SCHEMES = frozenset({"http", "https", "ws", "wss"})


@dataclass(frozen=True)
class FigmaPluginDomainPattern:
    raw: str
    scheme: str
    host: str
    port: int | None
    path: str
    wildcard_subdomains: bool = False
    all_domains: bool = False

    def matches(self, url: str) -> bool:
        if self.raw == "none":
            return False
        parsed = urlsplit(str(url))
        scheme = parsed.scheme.casefold()
        if scheme not in ALLOWED_NETWORK_SCHEMES:
            return False
        if self.all_domains:
            return True
        if self.scheme and scheme != self.scheme:
            return False
        host = (parsed.hostname or "").casefold()
        if self.wildcard_subdomains:
            if not host.endswith("." + self.host):
                return False
        elif host != self.host:
            return False
        try:
            port = parsed.port
        except ValueError:
            return False
        if self.port is not None and port != self.port:
            return False
        request_path = parsed.path or "/"
        if self.path:
            if self.path.endswith("/"):
                return request_path.startswith(self.path)
            return request_path == self.path
        return True


def parse_figma_plugin_domain_pattern(value: object) -> FigmaPluginDomainPattern:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Network domain pattern cannot be empty")
    if raw == "none":
        return FigmaPluginDomainPattern(raw, "", "", None, "")
    if raw == "*":
        return FigmaPluginDomainPattern(raw, "", "", None, "", all_domains=True)
    if any(character.isspace() for character in raw) or "\\" in raw:
        raise ValueError(f"Invalid network domain pattern: {raw}")
    explicit_scheme = "://" in raw
    candidate = raw if explicit_scheme else "https://" + raw
    parsed = urlsplit(candidate)
    scheme = parsed.scheme.casefold() if explicit_scheme else ""
    if explicit_scheme and scheme not in ALLOWED_NETWORK_SCHEMES:
        raise ValueError(f"Unsupported network scheme in domain pattern: {raw}")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError(f"Unsafe network domain pattern: {raw}")
    hostname = (parsed.hostname or "").casefold()
    wildcard = hostname.startswith("*.")
    if "*" in hostname and not wildcard:
        raise ValueError(f"Wildcard must be the leading subdomain label: {raw}")
    host = hostname[2:] if wildcard else hostname
    if not host or "*" in host:
        raise ValueError(f"Invalid network host pattern: {raw}")
    try:
        host.encode("ascii")
        port = parsed.port
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError(f"Invalid network host or port pattern: {raw}") from exc
    path = parsed.path or ""
    return FigmaPluginDomainPattern(
        raw=raw,
        scheme=scheme,
        host=host,
        port=port,
        path=path,
        wildcard_subdomains=wildcard,
    )


def validate_figma_plugin_domains(values: object, *, field: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        return [], [f"Figma plugin {field} must be an array of strings"]
    normalized: list[str] = []
    for value in values:
        try:
            pattern = parse_figma_plugin_domain_pattern(value)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if pattern.raw not in normalized:
            normalized.append(pattern.raw)
    if "none" in normalized and len(normalized) != 1:
        errors.append("Network domain pattern 'none' must be used alone")
    return normalized, errors


def figma_plugin_url_allowed(url: str, allowed_domains: tuple[str, ...] | list[str]) -> bool:
    for value in allowed_domains:
        try:
            if parse_figma_plugin_domain_pattern(value).matches(url):
                return True
        except ValueError:
            continue
    return False


def figma_plugin_csp_sources(
    allowed_domains: tuple[str, ...] | list[str], *, connect: bool
) -> list[str]:
    sources: list[str] = []
    for value in allowed_domains:
        pattern = parse_figma_plugin_domain_pattern(value)
        if pattern.raw == "none":
            continue
        if pattern.all_domains:
            candidates = ["http:", "https:", "ws:", "wss:"] if connect else ["http:", "https:"]
        else:
            host = ("*." if pattern.wildcard_subdomains else "") + pattern.host
            if pattern.port is not None:
                host += f":{pattern.port}"
            schemes = [pattern.scheme] if pattern.scheme else (
                ["http", "https", "ws", "wss"] if connect else ["http", "https"]
            )
            candidates = [f"{scheme}://{host}" for scheme in schemes]
        for candidate in candidates:
            if candidate not in sources:
                sources.append(candidate)
    return sources


def figma_plugin_network_reasoning_required(domains: list[str]) -> bool:
    for value in domains:
        pattern = parse_figma_plugin_domain_pattern(value)
        if pattern.all_domains or pattern.host in {"localhost", "127.0.0.1", "::1"}:
            return True
    return False


__all__ = [
    "ALLOWED_NETWORK_SCHEMES",
    "FigmaPluginDomainPattern",
    "figma_plugin_csp_sources",
    "figma_plugin_network_reasoning_required",
    "figma_plugin_url_allowed",
    "parse_figma_plugin_domain_pattern",
    "validate_figma_plugin_domains",
]
