"""Restricted Qt WebEngine host for one FP3 Figma Plugin UI session."""
from __future__ import annotations

import json
from typing import Any, Callable, Mapping

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

from app.painter_ui_figma_plugin_network import (
    figma_plugin_csp_sources,
    figma_plugin_url_allowed,
)


def build_sandboxed_plugin_html(
    html: str,
    *,
    dark: bool,
    theme_colors: bool,
    allowed_domains: tuple[str, ...] = (),
) -> str:
    theme_class = "figma-dark" if dark else "figma-light"
    colors = (
        ("#1E1E1E", "#FFFFFF", "#383838", "#0D99FF")
        if dark
        else ("#FFFFFF", "#1E1E1E", "#E6E6E6", "#0D99FF")
    )
    theme_style = ""
    if theme_colors:
        theme_style = (
            ":root{"
            f"--figma-color-bg:{colors[0]};--figma-color-text:{colors[1]};"
            f"--figma-color-border:{colors[2]};--figma-color-bg-brand:{colors[3]};"
            "color-scheme:" + ("dark" if dark else "light") + ";}"
        )
    connect_sources = figma_plugin_csp_sources(allowed_domains, connect=True)
    resource_sources = figma_plugin_csp_sources(allowed_domains, connect=False)
    connect_policy = " ".join(connect_sources) if connect_sources else "'none'"
    resource_policy = " ".join(resource_sources)
    remote_resources = (" " + resource_policy) if resource_policy else ""
    bridge = f"""
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: blob:{remote_resources}; style-src 'unsafe-inline'{remote_resources}; script-src 'unsafe-inline' qrc:{remote_resources}; font-src data:{remote_resources}; connect-src {connect_policy}; media-src 'none'; frame-src 'none'">
<style>{theme_style}</style>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
document.documentElement.classList.add({json.dumps(theme_class)});
(() => {{
  const pending=[]; let bridge=null;
  const deliver=(kind,value) => {{
    if (bridge) bridge[kind](value); else pending.push({{kind,value}});
  }};
  const send=async(payload) => {{
    if (!payload) return;
    if (Object.prototype.hasOwnProperty.call(payload,'pluginMessage')) {{
      deliver('uiMessage',JSON.stringify(payload.pluginMessage));
      return;
    }}
    if (Object.prototype.hasOwnProperty.call(payload,'pluginDrop')) {{
      const source=payload.pluginDrop||{{}};
      const files=[];
      for (const file of Array.from(source.files||[]).slice(0,16)) {{
        if (Number(file.size||0)>1048576) throw new Error('Plugin drop file exceeds 1 MiB');
        files.push({{name:String(file.name||''),type:String(file.type||''),text:await file.text()}});
      }}
      deliver('uiDrop',JSON.stringify({{...source,files}}));
    }}
  }};
  window.postMessage=(payload) => {{ void send(payload); }};
  try {{ window.parent.postMessage=(payload) => {{ void send(payload); }}; }} catch (_) {{}}
  window.__tigerReceive=(value) => {{
    const pluginMessage=JSON.parse(value);
    window.dispatchEvent(new MessageEvent('message',{{data:{{pluginMessage}}}}));
  }};
  new QWebChannel(qt.webChannelTransport,(channel) => {{
    bridge=channel.objects.tigerPluginBridge;
    while(pending.length) {{ const row=pending.shift(); bridge[row.kind](row.value); }}
  }});
}})();
</script>
"""
    source = str(html or "")
    lower = source.casefold()
    head_index = lower.find("<head")
    if head_index >= 0:
        close = source.find(">", head_index)
        if close >= 0:
            return source[: close + 1] + bridge + source[close + 1 :]
    return f"<!doctype html><html><head>{bridge}</head><body>{source}</body></html>"


class _BlockedRequestInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, allowed_domains: tuple[str, ...], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._allowed_domains = tuple(allowed_domains)

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:  # noqa: N802
        scheme = info.requestUrl().scheme().casefold()
        if scheme in {"about", "data", "blob", "qrc"}:
            return
        if not figma_plugin_url_allowed(info.requestUrl().toString(), self._allowed_domains):
            info.block(True)


class _PluginPage(QWebEnginePage):
    navigation_blocked = Signal(str)

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):  # noqa: N802
        scheme = url.scheme().casefold()
        if scheme in {"about", "data", "blob", "qrc"}:
            return super().acceptNavigationRequest(url, navigation_type, is_main_frame)
        self.navigation_blocked.emit(url.toString())
        return False


class _PluginBridge(QObject):
    def __init__(
        self,
        message_callback: Callable[[Any], None],
        drop_callback: Callable[[Mapping[str, Any]], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._message_callback = message_callback
        self._drop_callback = drop_callback

    @Slot(str)
    def uiMessage(self, payload: str) -> None:  # noqa: N802
        self._message_callback(json.loads(str(payload)))

    @Slot(str)
    def uiDrop(self, payload: str) -> None:  # noqa: N802
        value = json.loads(str(payload))
        if not isinstance(value, dict):
            raise ValueError("Plugin drop payload must be an object")
        self._drop_callback(value)


class PainterFigmaPluginUIDialog(QDialog):
    runtimeFailed = Signal(str)

    def __init__(
        self,
        session,
        parent: QWidget | None = None,
        *,
        dark: bool = False,
        document_callback: Callable[[Mapping[str, Any]], None] | None = None,
        allowed_domains: tuple[str, ...] = (),
        drop_position_callback: Callable[[Mapping[str, Any]], Mapping[str, Any] | None]
        | None = None,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self._document_callback = document_callback
        self._drop_position_callback = drop_position_callback
        self.ui_messages: list[Any] = []
        self.main_messages: list[Any] = []
        state = dict(session.ready.get("ui") or {})
        self.setObjectName("PainterFigmaPluginUIDialog")
        self.setWindowTitle(str(state.get("title") or "Figma Plugin"))
        self.resize(
            max(70, min(1200, int(state.get("width", 300)))),
            max(1, min(1000, int(state.get("height", 200)))),
        )
        self.view = QWebEngineView(self)
        self.view.setObjectName("PainterFigmaPluginUIWebView")
        self._profile = QWebEngineProfile(self.view)
        self._profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        page = _PluginPage(self._profile, self.view)
        self._allowed_domains = tuple(allowed_domains)
        self._interceptor = _BlockedRequestInterceptor(self._allowed_domains, page)
        self._profile.setUrlRequestInterceptor(self._interceptor)
        self._profile.downloadRequested.connect(lambda request: request.cancel())
        self.view.setPage(page)
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
        self._channel = QWebChannel(page)
        self._bridge = _PluginBridge(
            self._receive_ui_message, self._receive_plugin_drop, self._channel
        )
        self._channel.registerObject("tigerPluginBridge", self._bridge)
        page.setWebChannel(self._channel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        document = build_sandboxed_plugin_html(
            str(state.get("html") or ""),
            dark=bool(dark),
            theme_colors=bool(state.get("themeColors")),
            allowed_domains=self._allowed_domains,
        )
        self.view.loadFinished.connect(self._deliver_ready_messages)
        self.view.setHtml(document, QUrl("about:blank"))
        self._push_timer = QTimer(self)
        self._push_timer.setInterval(40)
        self._push_timer.timeout.connect(self._poll_worker_pushes)
        self._push_timer.start()
        self._apply_document_event(session.ready)
        if not bool(state.get("visible", True)):
            self.hide()

    def _deliver_ready_messages(self, ok: bool) -> None:
        if not ok:
            return
        for message in self.session.ready.get("messages", []):
            self._deliver_main_message(message)

    def _deliver_main_message(self, message: Any) -> None:
        self.main_messages.append(message)
        serialized = json.dumps(message, ensure_ascii=False)
        self.view.page().runJavaScript(
            f"window.__tigerReceive({json.dumps(serialized, ensure_ascii=False)});"
        )

    def _receive_ui_message(self, message: Any) -> None:
        self.ui_messages.append(message)
        try:
            state = self.session.post_ui_message(message)
        except Exception as exc:
            self._set_runtime_failure(str(exc))
            return
        self._apply_document_event(state)
        self._apply_ui_state(state)
        for outbound in state.get("messages", []):
            self._deliver_main_message(outbound)

    def _receive_plugin_drop(self, payload: Mapping[str, Any]) -> None:
        value: Mapping[str, Any] | None = dict(payload)
        if callable(self._drop_position_callback):
            value = self._drop_position_callback(value)
        if value is None:
            return
        try:
            state = self.session.post_plugin_drop(value)
        except Exception as exc:
            self._set_runtime_failure(str(exc))
            return
        self._apply_document_event(state)
        self._apply_ui_state(state)
        for outbound in state.get("messages", []):
            self._deliver_main_message(outbound)

    def _apply_ui_state(self, state: Mapping[str, Any]) -> None:
        ui = dict(state.get("ui") or {})
        self.resize(
            max(70, min(1200, int(ui.get("width", self.width())))),
            max(1, min(1000, int(ui.get("height", self.height())))),
        )
        self.setVisible(bool(ui.get("visible", True)))
        if ui.get("closed"):
            self.close()

    def _poll_worker_pushes(self) -> None:
        try:
            events = self.session.poll_events()
        except Exception as exc:
            self._set_runtime_failure(str(exc))
            return
        for event in events:
            if event.get("event") != "push":
                continue
            self._apply_document_event(event)
            self._apply_ui_state(event)
            for outbound in event.get("messages", []):
                self._deliver_main_message(outbound)

    def _apply_document_event(self, event: Mapping[str, Any]) -> None:
        if callable(self._document_callback) and "nodes" in event:
            try:
                self._document_callback(event)
            except Exception as exc:
                self._set_runtime_failure(str(exc))

    def _set_runtime_failure(self, message: str) -> None:
        if self.property("runtimeFailed"):
            return
        self.setProperty("runtimeFailed", True)
        if hasattr(self, "_push_timer"):
            self._push_timer.stop()
        if hasattr(self, "view"):
            self.view.setEnabled(False)
        self.setWindowTitle(f"{self.windowTitle()} · 실행 오류")
        self.session.terminate()
        self.runtimeFailed.emit(str(message))

    def closeEvent(self, event) -> None:  # noqa: N802
        self.session.close()
        super().closeEvent(event)


__all__ = ["PainterFigmaPluginUIDialog", "build_sandboxed_plugin_html"]
