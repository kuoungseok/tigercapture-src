from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .fonts import REVIEW_FONT_CSS


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _rel_from_html(path: str, html_path: Path) -> str:
    if not path:
        return ""
    try:
        return Path(os.path.relpath(Path(path), start=html_path.parent)).as_posix()
    except Exception:
        return Path(path).as_posix()


def _artifact_map(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("id")): row
        for row in list(report.get("artifacts", []) or [])
        if isinstance(row, Mapping) and row.get("id")
    }


def _resolve_output_path(artifact: Mapping[str, Any], project_root: str | Path) -> Path:
    raw = Path(str(artifact.get("output_path") or ""))
    return raw if raw.is_absolute() else Path(project_root) / raw


def _feature_page_name(feature: Mapping[str, Any]) -> str:
    raw = str(feature.get("id") or "feature")
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in raw)
    return f"{safe or 'feature'}.html"


def _artifact_media_html(
    artifact: Mapping[str, Any],
    *,
    html_path: Path,
    project_root: str | Path,
) -> str:
    path = _resolve_output_path(artifact, project_root)
    src = _rel_from_html(str(path), html_path)
    title = _esc(artifact.get("title") or artifact.get("id") or path.name)
    kind = str(artifact.get("kind") or path.suffix.lower().lstrip("."))
    if kind in {"screenshot", "image", "contact_sheet", "gif"} or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"}:
        return f"""
        <figure class="artifact artifact-image">
          <img src="{_esc(src)}" alt="{title}">
          <figcaption>{title}</figcaption>
        </figure>
        """
    if kind == "video" or path.suffix.lower() in {".mp4", ".webm", ".mov"}:
        return f"""
        <figure class="artifact">
          <video src="{_esc(src)}" controls muted playsinline></video>
          <figcaption>{title}</figcaption>
        </figure>
        """
    if kind == "audio" or path.suffix.lower() in {".wav", ".mp3", ".flac", ".m4a"}:
        return f"""
        <figure class="artifact">
          <audio src="{_esc(src)}" controls></audio>
          <figcaption>{title}</figcaption>
        </figure>
        """
    if kind == "transcript" or path.suffix.lower() in {".srt", ".vtt", ".txt"}:
        try:
            text = path.read_text(encoding="utf-8")[:5000]
        except Exception:
            text = ""
        return f"""
        <figure class="artifact">
          <pre class="transcript">{_esc(text or 'Transcript file is available as a linked artifact.')}</pre>
          <figcaption><a href="{_esc(src)}">{title}</a></figcaption>
        </figure>
        """
    return f"""
    <div class="artifact artifact-link">
      <a href="{_esc(src)}">{title}</a>
    </div>
    """


def _artifact_href(artifact: Mapping[str, Any], *, html_path: Path, project_root: str | Path | None) -> str:
    if project_root is None:
        return _rel_from_html(str(artifact.get("output_path") or ""), html_path)
    return _rel_from_html(str(_resolve_output_path(artifact, project_root)), html_path)


def _feature_artifacts(
    feature: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for artifact_id in list(feature.get("artifact_ids", []) or []):
        key = str(artifact_id)
        artifact = artifacts.get(key)
        if artifact and artifact.get("exists") and key not in seen:
            rows.append(artifact)
            seen.add(key)
    return rows


def _scenario_rows_for_feature(report: Mapping[str, Any], feature_id: str) -> list[Mapping[str, Any]]:
    return [
        row
        for row in list(report.get("scenarios", []) or [])
        if isinstance(row, Mapping) and str(row.get("feature_id") or "") == str(feature_id)
    ]


def build_review_html(
    report: Mapping[str, Any],
    *,
    html_path: str | Path,
    project_root: str | Path | None = None,
) -> str:
    target = Path(html_path)
    artifacts = _artifact_map(report)
    features = [row for row in list(report.get("features", []) or []) if isinstance(row, Mapping)]
    counts = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    contact = artifacts.get("catalog_editor_surface") or artifacts.get("review_contact_sheet") or artifacts.get("editor_contact_sheet") or {}
    contact_src = _artifact_href(contact, html_path=target, project_root=project_root) if contact else ""
    poster = artifacts.get("catalog_editor_surface") or artifacts.get("review_overview_poster") or {}
    poster_src = _artifact_href(poster or contact, html_path=target, project_root=project_root) if (poster or contact) else ""

    feature_cards = []
    for feature in features:
        status = str(feature.get("status") or "unknown")
        artifact_links = []
        for artifact in _feature_artifacts(feature, artifacts):
            href = _artifact_href(artifact, html_path=target, project_root=project_root)
            artifact_links.append(f'<a href="{_esc(href)}">{_esc(artifact.get("title") or artifact.get("id"))}</a>')
        guardrails = "".join(f"<li>{_esc(item)}</li>" for item in list(feature.get("guardrails", []) or []))
        card_class = f"feature status-{_esc(status)}"
        feature_href = f"features/{_esc(_feature_page_name(feature))}"
        feature_cards.append(
            f"""
            <article class="{card_class}">
              <div class="feature-topline">
                <span>{_esc(feature.get("category"))}</span>
                <strong>{_esc(status.replace("_", " "))}</strong>
              </div>
              <h3>{_esc(feature.get("title"))}</h3>
              <p>{_esc(feature.get("summary"))}</p>
              <p class="claim">{_esc(feature.get("claim"))}</p>
              <div class="evidence">{' | '.join(artifact_links) if artifact_links else 'Evidence pending'}</div>
              <a class="feature-link" href="{feature_href}">Open feature evidence</a>
              {f'<ul class="guardrails">{guardrails}</ul>' if guardrails else ''}
            </article>
            """
        )

    scenario_cards = []
    for scenario in [row for row in list(report.get("scenarios", []) or []) if isinstance(row, Mapping)]:
        status = str(scenario.get("status") or "unknown")
        actions = len(list(scenario.get("action_ids", []) or []))
        artifacts_count = len(list(scenario.get("artifact_ids", []) or []))
        scenario_cards.append(
            f"""
            <article class="scenario status-{_esc(status)}">
              <div class="feature-topline">
                <span>{_esc(scenario.get("mode"))}</span>
                <strong>{_esc(status.replace("_", " "))}</strong>
              </div>
              <h3>{_esc(scenario.get("title"))}</h3>
              <p>{_esc(scenario.get("summary"))}</p>
              <div class="evidence">{actions} actions / {artifacts_count} artifacts</div>
            </article>
            """
        )

    warnings = "".join(f"<li>{_esc(item)}</li>" for item in list(report.get("warnings", []) or []))
    stale = bool(report.get("stale"))
    generated_at = _esc(report.get("generated_at", ""))
    report_json = _esc(json.dumps(report.get("summary", {}), ensure_ascii=False, indent=2))
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TigerCapture Review Automation</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #090d16;
      --panel: #121827;
      --panel-2: #182033;
      --text: #f4f7fb;
      --muted: #aeb9ca;
      --line: #2f3c56;
      --ok: #43d39e;
      --warn: #f5c451;
      --bad: #ff6b7c;
      --accent: #82aaff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: {REVIEW_FONT_CSS};
      background: var(--bg);
      color: var(--text);
      letter-spacing: 0;
    }}
    header {{
      min-height: 62vh;
      display: grid;
      align-items: end;
      padding: 56px clamp(24px, 6vw, 76px);
      background:
        linear-gradient(180deg, rgba(9,13,22,0.24), rgba(9,13,22,0.96)),
        url("{_esc(poster_src)}") center/cover no-repeat;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 16px;
      max-width: 980px;
      font-size: clamp(44px, 7vw, 92px);
      line-height: 0.94;
      letter-spacing: 0;
    }}
    header p {{
      max-width: 780px;
      margin: 0;
      color: var(--muted);
      font-size: 21px;
      line-height: 1.45;
    }}
    main {{
      padding: 34px clamp(20px, 5vw, 72px) 72px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin: 0 0 30px;
    }}
    .metric {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 18px;
    }}
    .metric strong {{
      display: block;
      font-size: 34px;
      line-height: 1;
    }}
    .metric span {{
      display: block;
      margin-top: 8px;
      color: var(--muted);
      font-size: 14px;
    }}
    .showcase {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
      gap: 24px;
      align-items: start;
      margin-bottom: 34px;
    }}
    .showcase img {{
      width: 100%;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #050811;
      display: block;
    }}
    .note {{
      background: var(--panel-2);
      border-left: 4px solid var(--accent);
      padding: 18px 20px;
      border-radius: 6px;
      color: var(--muted);
      line-height: 1.55;
    }}
    .features {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }}
    .feature, .scenario {{
      min-height: 250px;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .feature-topline {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    .feature-topline strong {{ color: var(--warn); }}
    .status-evidence_ready .feature-topline strong {{ color: var(--ok); }}
    .status-action_ready .feature-topline strong {{ color: var(--ok); }}
    .status-captured .feature-topline strong {{ color: var(--ok); }}
    .status-blocked .feature-topline strong {{ color: var(--bad); }}
    h2 {{ margin: 28px 0 16px; font-size: 28px; }}
    h3 {{ margin: 0; font-size: 22px; }}
    .feature p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
    }}
    .scenario {{
      min-height: 210px;
      background: var(--panel-2);
    }}
    .scenario p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
    }}
    .claim {{
      color: var(--text) !important;
      font-weight: 600;
    }}
    .evidence {{
      margin-top: auto;
      color: var(--muted);
      font-size: 14px;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    .feature-link {{
      display: inline-block;
      margin-top: 4px;
      font-weight: 700;
    }}
    .guardrails {{
      margin: 0;
      padding-left: 18px;
      color: var(--warn);
      font-size: 13px;
      line-height: 1.35;
    }}
    pre {{
      overflow: auto;
      border: 1px solid var(--line);
      background: #050811;
      padding: 16px;
      border-radius: 8px;
      color: var(--muted);
    }}
    footer {{
      padding-top: 28px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 980px) {{
      .summary, .showcase, .features {{ grid-template-columns: 1fr; }}
      header {{ min-height: 54vh; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>TigerCapture Review Automation</h1>
      <p>QA evidence, deterministic sample media, screenshots, GIFs, HTML, and deck output generated from the current project state.</p>
    </div>
  </header>
  <main>
    <section class="summary" aria-label="summary">
      <div class="metric"><strong>{int(counts.get("features", 0) or 0)}</strong><span>tracked features</span></div>
      <div class="metric"><strong>{int(counts.get("evidence_ready", 0) or 0)}</strong><span>evidence ready</span></div>
      <div class="metric"><strong>{int(counts.get("artifacts", 0) or 0)}</strong><span>collected artifacts</span></div>
      <div class="metric"><strong>{'STALE' if stale else 'FRESH'}</strong><span>spec fingerprint</span></div>
    </section>
    <section class="showcase">
      <img src="{_esc(contact_src)}" alt="Review automation contact sheet">
      <div class="note">
        <strong>Generated at</strong><br>{generated_at}<br><br>
        Outputs are intentionally tied to SPEC, release positioning, QA reports, and the review sample manifest. When those inputs change, downstream material should be regenerated.
      </div>
    </section>
    <h2>Feature Evidence</h2>
    <section class="features">
      {''.join(feature_cards)}
    </section>
    <h2>Automation Scenarios</h2>
    <section class="features">
      {''.join(scenario_cards)}
    </section>
    {f'<h2>Warnings</h2><ul>{warnings}</ul>' if warnings else ''}
    <h2>Report Summary</h2>
    <pre>{report_json}</pre>
    <footer>Source report: {_esc(report.get("report_path", ""))}</footer>
  </main>
</body>
</html>
"""


def write_review_html(
    report: Mapping[str, Any],
    path: str | Path,
    *,
    project_root: str | Path | None = None,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_review_html(report, html_path=target, project_root=project_root), encoding="utf-8")
    return target


def build_feature_html(
    report: Mapping[str, Any],
    feature: Mapping[str, Any],
    *,
    html_path: str | Path,
    project_root: str | Path,
) -> str:
    target = Path(html_path)
    artifacts = _artifact_map(report)
    media_blocks = [
        _artifact_media_html(artifact, html_path=target, project_root=project_root)
        for artifact in _feature_artifacts(feature, artifacts)
    ]
    qa_states = feature.get("qa_states", {}) if isinstance(feature.get("qa_states"), Mapping) else {}
    qa_rows = "".join(
        f"<tr><td>{_esc(path)}</td><td>{'missing' if state is None else ('ok' if state else 'failed')}</td></tr>"
        for path, state in qa_states.items()
    )
    guardrails = "".join(f"<li>{_esc(item)}</li>" for item in list(feature.get("guardrails", []) or []))
    missing = list(feature.get("missing_resources", []) or []) + list(feature.get("missing_reports", []) or []) + list(feature.get("failing_reports", []) or [])
    missing_rows = "".join(f"<li>{_esc(item)}</li>" for item in missing)
    scenario_rows = _scenario_rows_for_feature(report, str(feature.get("id") or ""))
    scenarios_html = "".join(
        f"""
        <tr>
          <td>{_esc(row.get("title"))}</td>
          <td>{_esc(row.get("mode"))}</td>
          <td>{_esc(str(row.get("status") or "unknown").replace("_", " "))}</td>
          <td>{len(list(row.get("action_ids", []) or []))}</td>
          <td>{len(list(row.get("artifact_ids", []) or []))}</td>
        </tr>
        """
        for row in scenario_rows
    )
    status = str(feature.get("status") or "unknown")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(feature.get("title"))} - TigerCapture Review</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #090d16;
      --panel: #121827;
      --panel-2: #182033;
      --text: #f4f7fb;
      --muted: #aeb9ca;
      --line: #2f3c56;
      --ok: #43d39e;
      --warn: #f5c451;
      --bad: #ff6b7c;
      --accent: #82aaff;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: {REVIEW_FONT_CSS}; background: var(--bg); color: var(--text); letter-spacing: 0; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 34px 24px 72px; }}
    a {{ color: var(--accent); text-decoration: none; font-weight: 700; }}
    header {{ border-bottom: 1px solid var(--line); padding: 28px 24px; background: #0d1322; }}
    header div {{ max-width: 1180px; margin: 0 auto; }}
    h1 {{ margin: 14px 0 12px; font-size: clamp(36px, 6vw, 72px); line-height: 0.98; letter-spacing: 0; }}
    h2 {{ margin: 34px 0 14px; font-size: 28px; }}
    p {{ color: var(--muted); line-height: 1.55; }}
    .status {{ display: inline-block; color: var(--ok); text-transform: uppercase; font-size: 13px; font-weight: 800; }}
    .status-blocked {{ color: var(--bad); }}
    .claim {{ color: var(--text); font-weight: 700; font-size: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
    .artifact {{ margin: 0; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 14px; }}
    .artifact img, .artifact video {{ width: 100%; display: block; border-radius: 6px; background: #050811; }}
    .artifact audio {{ width: 100%; }}
    figcaption {{ margin-top: 10px; color: var(--muted); font-size: 13px; }}
    .transcript {{ max-height: 360px; overflow: auto; white-space: pre-wrap; color: var(--muted); background: #050811; border-radius: 6px; padding: 14px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
    td {{ border-top: 1px solid var(--line); padding: 10px 12px; color: var(--muted); }}
    tr:first-child td {{ border-top: 0; }}
    ul {{ color: var(--warn); line-height: 1.45; }}
    .empty {{ border: 1px solid var(--line); background: var(--panel); border-radius: 8px; padding: 18px; color: var(--muted); }}
    @media (max-width: 860px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <div>
      <a href="../index.html">Back to review overview</a>
      <h1>{_esc(feature.get("title"))}</h1>
      <span class="status status-{_esc(status)}">{_esc(status.replace("_", " "))}</span>
    </div>
  </header>
  <main>
    <p>{_esc(feature.get("summary"))}</p>
    <p class="claim">{_esc(feature.get("claim"))}</p>
    <h2>Evidence Media</h2>
    <section class="grid">
      {''.join(media_blocks) if media_blocks else '<div class="empty">Evidence media is pending.</div>'}
    </section>
    <h2>QA State</h2>
    {f'<table>{qa_rows}</table>' if qa_rows else '<div class="empty">No external QA reports are linked to this feature.</div>'}
    <h2>Automation Scenarios</h2>
    {f'<table><tr><td>Scenario</td><td>Mode</td><td>Status</td><td>Actions</td><td>Artifacts</td></tr>{scenarios_html}</table>' if scenarios_html else '<div class="empty">No automation scenario is linked to this feature yet.</div>'}
    {f'<h2>Guardrails</h2><ul>{guardrails}</ul>' if guardrails else ''}
    {f'<h2>Missing Or Failing Evidence</h2><ul>{missing_rows}</ul>' if missing_rows else ''}
  </main>
</body>
</html>
"""


def write_review_feature_pages(
    report: Mapping[str, Any],
    site_dir: str | Path,
    *,
    project_root: str | Path,
) -> list[dict[str, Any]]:
    root = Path(project_root)
    features_dir = Path(site_dir) / "features"
    features_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for feature in list(report.get("features", []) or []):
        if not isinstance(feature, Mapping):
            continue
        page = features_dir / _feature_page_name(feature)
        page.write_text(build_feature_html(report, feature, html_path=page, project_root=root), encoding="utf-8")
        try:
            rel = page.resolve().relative_to(root.resolve()).as_posix()
        except Exception:
            rel = page.as_posix()
        rows.append(
            {
                "id": f"feature_page_{feature.get('id')}",
                "feature_id": feature.get("id"),
                "title": f"{feature.get('title')} feature page",
                "kind": "html",
                "source_path": "",
                "output_path": rel,
                "exists": page.exists(),
                "size": int(page.stat().st_size) if page.exists() else 0,
            }
        )
    return rows


def write_review_site(
    report: Mapping[str, Any],
    site_dir: str | Path,
    *,
    project_root: str | Path,
) -> tuple[Path, list[dict[str, Any]]]:
    target_dir = Path(site_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    index = write_review_html(report, target_dir / "index.html", project_root=project_root)
    pages = write_review_feature_pages(report, target_dir, project_root=project_root)
    return index, pages
