from __future__ import annotations

import html
import mimetypes
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .artifacts import feature_editor_surface_artifact_id
from .fonts import is_korean_locale, review_ppt_font


EMU = 914400
SLIDE_W = 12192000
SLIDE_H = 6858000

THEME_BG = "F0F1F1"
THEME_INK = "202126"
THEME_MUTED = "6C6D70"
THEME_DIM = "9A9C9F"
THEME_ACCENT = "2A2B2D"
THEME_CYAN = "2A2B2D"
THEME_LIME = "3A4631"
THEME_PANEL = "FBFBFB"
THEME_PANEL_2 = "F7F7F7"
THEME_LINE = "DCDCDC"
THEME_WARN = "8A6A3A"


TOPIC_KO: dict[str, dict[str, Any]] = {
    "screen_recording": {
        "title": "화면 녹화와 자동 폴리시",
        "category": "크리에이터 캡처",
        "bullets": [
            "스크린샷, GIF, MP4 캡처와 Windows Graphics Capture를 지원합니다.",
            "커서 사이드카 메타데이터로 커서 보정, 클릭 링, 단축키 배지, 드래그 트레일, 자동 줌을 만듭니다.",
            "Screen Studio식 튜토리얼 폴리시와 내보내기 흐름을 로컬 작업 안에 유지합니다.",
        ],
    },
    "creator_assist": {
        "title": "Creator Assist와 CapCut식 워크플로",
        "category": "크리에이터 워크플로",
        "bullets": [
            "캡션, 쇼츠 구간, 세로 리프레임, 게시 문구, 렌더 작업을 계획합니다.",
            "Quick Result, Publish, Voice, Prompt Edit, 협업/전달 리포트로 CapCut식 격차를 추적합니다.",
            "핵심 경로는 클라우드 API 없이 로컬 우선으로 동작합니다.",
        ],
    },
    "multilingual_localization": {
        "title": "타이포그래피, 타이틀, 다국어 텍스트",
        "category": "타이포그래피",
        "bullets": [
            "큰 타이틀, 캡션, 본문 텍스트를 스타일 프리셋과 키프레임이 있는 타임라인 레이어로 다룹니다.",
            "카탈로그 화면에서도 읽히도록 한국어, 영어, 일본어 샘플을 크게 배치합니다.",
            "타이틀 프리셋, opacity/position/scale 키, CJK 폰트 폴백으로 내보내기 가능한 타이포그래피를 보여줍니다.",
        ],
    },
    "ai_script_edit": {
        "title": "AI 스크립트 편집과 로컬 LLM",
        "category": "AI 지원",
        "bullets": [
            "하단 AI Command dock과 Script Edit 패널이 텍스트/자막을 검토 가능한 편집 계획으로 바꿉니다.",
            "provider 상태를 rule-based, local LLM, Qwen 호환, 외부 provider로 명확히 표시합니다.",
            "코퍼스 품질 증거가 부족하면 강한 AI 마케팅 문구를 막습니다.",
        ],
    },
    "timeline_editing": {
        "title": "타임라인, 미디어 풀, 워크벤치",
        "category": "편집 코어",
        "bullets": [
            "컷, split, marker, speed segment, fade, actor track, zoom actor를 타임라인 모델에서 다룹니다.",
            "미디어 풀은 thumbnail, relink health, proxy state, actor QA badge, preset 탐색을 추적합니다.",
            "워크벤치는 노드 그래프 효과, 마스크, clip FX stack, metadata, inspector를 연결합니다.",
        ],
    },
    "actors": {
        "title": "Live2D, Spine, NIKKE 액터 트랙",
        "category": "액터 오버레이",
        "bullets": [
            "Live2D와 Spine 클립은 전용 액터 트랙에 놓이고 최종 내보내기에 bake됩니다.",
            "Live2D는 model3, moc, texture, motion, physics 의존성 검사를 갖습니다.",
            "Spine/NIKKE와 VTuber 브리지는 시각/런타임 증거가 충분해질 때까지 guardrail을 유지합니다.",
        ],
    },
    "color_audio_vfx": {
        "title": "컬러, 오디오, 마스크와 VFX",
        "category": "피니싱",
        "bullets": [
            "Rec.709, sRGB, HDR PQ/HLG, P3, ACES intent, LUT, scope를 다룹니다.",
            "오디오는 lane, Sound Editor, AI Master preset, loudness, true peak, separation fallback을 포함합니다.",
            "마스크, 로토스코프, chroma key, stabilization, background removal, tracked effect가 preview/export 대상입니다.",
        ],
    },
    "export_parity": {
        "title": "내보내기, 렌더 큐, 프리뷰 패리티",
        "category": "전달",
        "bullets": [
            "MP4, WebM, MOV, 1080p, 4K, 세로, 정사각, HDR metadata 경로를 추적합니다.",
            "FFmpeg 그래프로 안전하게 표현하기 어려운 preview-only 효과는 raw pre-render fallback으로 처리합니다.",
            "GPU preview/export parity는 노드 그래프, 마스크, 액터, 타이포그래피, 컬러 metadata를 검사합니다.",
        ],
    },
    "ar_pbr_3d": {
        "title": "AR/PBR 3D 합성",
        "category": "3D 합성",
        "bullets": [
            "AR/PBR track schema, depth/camera solve, road-plane placement, HDR environment preview가 문서화되어 있습니다.",
            "Attachment stability는 3D 모델이 영상 움직임에 붙어 있는지 검사합니다.",
            "Camera scene asset을 에디터 프리뷰 안에서 검토할 수 있습니다.",
        ],
    },
    "performance_health": {
        "title": "성능, Health, Native Worker",
        "category": "신뢰성",
        "bullets": [
            "Health Center는 crash, QA failure, render failure, media health, actor risk를 요약합니다.",
            "preview/cache 병목은 OpenCV, OpenGL, FFmpeg, proxy, Rust 이전에 먼저 측정합니다.",
            "Native worker는 선택 사항이며 JSON-lines 프로세스 경계를 유지합니다.",
        ],
    },
    "productization_release": {
        "title": "제품화, 릴리스 증거, 포지셔닝",
        "category": "릴리스",
        "bullets": [
            "Final readiness, productization loop, release gap closure, release evidence 리포트가 claim을 제한합니다.",
            "Public positioning guardrail은 미완성 parity claim이 마케팅 문구로 새는 것을 막습니다.",
            "리뷰 자동화는 docs, screenshot, HTML, PPT에 같은 evidence graph를 재사용합니다.",
        ],
    },
}

FEATURE_TITLE_KO: dict[str, str] = {
    "overview_editor": "스튜디오 오버뷰",
    "screenstudio_auto_polish": "Screen Studio 자동 폴리시",
    "multilingual_ui": "6개 언어 런타임 UI",
    "ai_script_edit": "AI 스크립트 편집",
    "action_automation": "AI/MCP 액션 자동화",
    "live2d_overlay": "Live2D 오버레이 타임라인",
    "audio_cleanup": "대화 음성 및 오디오 정리",
    "review_site_deck": "리뷰 사이트와 덱 생성기",
}

STATUS_KO: dict[str, str] = {
    "evidence_ready": "증거 준비",
    "implemented": "구현됨",
    "blocked": "차단",
    "planned": "계획",
    "stale": "오래됨",
    "unknown": "알 수 없음",
}


def _x(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _emu(inches: float) -> int:
    return int(inches * EMU)


def _artifact_map(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("id")): row
        for row in list(report.get("artifacts", []) or [])
        if isinstance(row, Mapping) and row.get("id")
    }


def _ko(locale: str | None) -> bool:
    return is_korean_locale(locale)


def _tr(locale: str | None, english: str, korean: str) -> str:
    return korean if _ko(locale) else english


def _localized_topic(topic: Mapping[str, Any], locale: str | None) -> dict[str, Any]:
    out = dict(topic)
    if not _ko(locale):
        return out
    row = TOPIC_KO.get(str(topic.get("id") or ""))
    if not row:
        return out
    out["title"] = row.get("title", out.get("title", ""))
    out["category"] = row.get("category", out.get("category", ""))
    out["bullets"] = list(row.get("bullets", out.get("bullets", []) or []))
    return out


def _localized_feature_title(feature: Mapping[str, Any], locale: str | None) -> str:
    title = str(feature.get("title") or "")
    if not _ko(locale):
        return title
    return FEATURE_TITLE_KO.get(str(feature.get("id") or ""), title)


def _localized_status(status: Any, locale: str | None) -> str:
    raw = str(status or "unknown").replace("_", " ")
    if not _ko(locale):
        return raw
    return STATUS_KO.get(str(status or "unknown"), raw)


def _text_box(
    shape_id: int,
    x: int,
    y: int,
    w: int,
    h: int,
    text: str,
    *,
    size: int = 2400,
    bold: bool = False,
    color: str = THEME_INK,
    align: str = "l",
    caps: bool = False,
    font_face: str = "",
) -> str:
    font = font_face or review_ppt_font()
    runs = []
    for line in str(text).splitlines() or [""]:
        line_text = line.upper() if caps else line
        runs.append(
            f"""
            <a:p><a:pPr algn="{_x(align)}"/>
              <a:r>
                <a:rPr lang="ko-KR" sz="{int(size)}" {'b="1"' if bold else ''}>
                  <a:solidFill><a:srgbClr val="{_x(color)}"/></a:solidFill>
                  <a:latin typeface="{_x(font)}"/>
                  <a:ea typeface="{_x(font)}"/>
                  <a:cs typeface="{_x(font)}"/>
                </a:rPr>
                <a:t>{_x(line_text)}</a:t>
              </a:r>
            </a:p>
            """
        )
    return f"""
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="{shape_id}" name="TextBox {shape_id}"/>
          <p:cNvSpPr txBox="1"/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
          <a:noFill/>
        </p:spPr>
        <p:txBody>
          <a:bodyPr wrap="square" anchor="t" lIns="0" tIns="0" rIns="0" bIns="0"/>
          <a:lstStyle/>
          {''.join(runs)}
        </p:txBody>
      </p:sp>
    """


def _rect(
    shape_id: int,
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    fill: str = THEME_PANEL,
    line: str = THEME_LINE,
    geom: str = "rect",
    line_width: int = 12700,
) -> str:
    ln = (
        "<a:ln w=\"0\"><a:noFill/></a:ln>"
        if line_width <= 0 or not line
        else f'<a:ln w="{int(line_width)}"><a:solidFill><a:srgbClr val="{_x(line)}"/></a:solidFill></a:ln>'
    )
    return f"""
      <p:sp>
        <p:nvSpPr><p:cNvPr id="{shape_id}" name="Rect {shape_id}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
          <a:prstGeom prst="{_x(geom)}"><a:avLst/></a:prstGeom>
          <a:solidFill><a:srgbClr val="{_x(fill)}"/></a:solidFill>
          {ln}
        </p:spPr>
      </p:sp>
    """


def _picture(
    shape_id: int,
    rel_id: str,
    x: int,
    y: int,
    w: int,
    h: int,
    name: str,
    *,
    line: str = "",
    line_width: int = 0,
) -> str:
    ln = (
        "<a:ln w=\"0\"><a:noFill/></a:ln>"
        if line_width <= 0 or not line
        else f'<a:ln w="{int(line_width)}"><a:solidFill><a:srgbClr val="{_x(line)}"/></a:solidFill></a:ln>'
    )
    return f"""
      <p:pic>
        <p:nvPicPr>
          <p:cNvPr id="{shape_id}" name="{_x(name)}"/>
          <p:cNvPicPr/>
          <p:nvPr/>
        </p:nvPicPr>
        <p:blipFill>
          <a:blip r:embed="{_x(rel_id)}"/>
          <a:stretch><a:fillRect/></a:stretch>
        </p:blipFill>
        <p:spPr>
          <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          {ln}
        </p:spPr>
      </p:pic>
    """


def _slide_number(shape_id: int, index: int, total: int) -> str:
    return _text_box(
        shape_id,
        _emu(11.9),
        _emu(6.82),
        _emu(0.72),
        _emu(0.22),
        f"{index:02}/{total:02}",
        size=850,
        bold=False,
        color=THEME_DIM,
        align="r",
    )


def _slide_xml(shapes: list[str], *, background: str = THEME_BG) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="{_x(background)}"/></a:solidFill></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      {''.join(shapes)}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>
"""


def _rels_xml(rels: list[tuple[str, str, str]]) -> str:
    rows = [
        f'<Relationship Id="{_x(rid)}" Type="{_x(rtype)}" Target="{_x(target)}"/>'
        for rid, rtype, target in rels
    ]
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rows)
        + "</Relationships>"
    )


def _slide_layout_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
             type="blank" preserve="1">
  <p:cSld name="Blank">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>
"""


def _slide_master_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
  </p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>
"""


def _theme_xml() -> str:
    font = review_ppt_font()
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="TigerCapture">
  <a:themeElements>
    <a:clrScheme name="TigerCapture">
      <a:dk1><a:srgbClr val="{THEME_BG}"/></a:dk1><a:lt1><a:srgbClr val="{THEME_INK}"/></a:lt1>
      <a:dk2><a:srgbClr val="{THEME_PANEL}"/></a:dk2><a:lt2><a:srgbClr val="{THEME_MUTED}"/></a:lt2>
      <a:accent1><a:srgbClr val="{THEME_ACCENT}"/></a:accent1><a:accent2><a:srgbClr val="{THEME_CYAN}"/></a:accent2>
      <a:accent3><a:srgbClr val="{THEME_LIME}"/></a:accent3><a:accent4><a:srgbClr val="{THEME_WARN}"/></a:accent4>
      <a:accent5><a:srgbClr val="C7CCC8"/></a:accent5><a:accent6><a:srgbClr val="CCCCCC"/></a:accent6>
      <a:hlink><a:srgbClr val="{THEME_CYAN}"/></a:hlink><a:folHlink><a:srgbClr val="C4A2FF"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="TigerCapture">
      <a:majorFont><a:latin typeface="{_x(font)}"/><a:ea typeface="{_x(font)}"/><a:cs typeface="{_x(font)}"/></a:majorFont>
      <a:minorFont><a:latin typeface="{_x(font)}"/><a:ea typeface="{_x(font)}"/><a:cs typeface="{_x(font)}"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="TigerCapture"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme>
  </a:themeElements>
</a:theme>
"""


def _core_xml() -> str:
    now = datetime.now(timezone.utc).isoformat()
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>TigerCapture Review Automation</dc:title>
  <dc:creator>TigerCapture review automation</dc:creator>
  <cp:lastModifiedBy>TigerCapture review automation</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{_x(now)}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{_x(now)}</dcterms:modified>
</cp:coreProperties>
"""


def _app_xml(slide_count: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>TigerCapture</Application>
  <PresentationFormat>Widescreen</PresentationFormat>
  <Slides>{int(slide_count)}</Slides>
</Properties>
"""


def _presentation_xml(slide_count: int) -> str:
    slide_ids = "".join(
        f'<p:sldId id="{256 + idx}" r:id="rId{idx + 2}"/>'
        for idx in range(slide_count)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>
"""


def _content_types(slide_count: int, media: list[Path]) -> str:
    defaults = [
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
    ]
    for ext in sorted({path.suffix.lower().lstrip(".") for path in media if path.suffix}):
        ctype = mimetypes.types_map.get(f".{ext}", "application/octet-stream")
        defaults.append(f'<Default Extension="{_x(ext)}" ContentType="{_x(ctype)}"/>')
    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for idx in range(1, slide_count + 1):
        overrides.append(f'<Override PartName="/ppt/slides/slide{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        + "".join(defaults)
        + "".join(overrides)
        + "</Types>"
    )


def _media_path(artifact: Mapping[str, Any], project_root: Path) -> Path | None:
    out = str(artifact.get("output_path") or "")
    if not out:
        return None
    path = Path(out)
    return path if path.is_absolute() else project_root / path


def _build_summary_slides(
    report: Mapping[str, Any],
    project_root: Path,
    *,
    locale: str | None = None,
) -> tuple[list[dict[str, Any]], list[Path]]:
    artifacts = _artifact_map(report)
    features = [row for row in list(report.get("features", []) or []) if isinstance(row, Mapping)]
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    media: list[Path] = []

    def add_image(slide: dict[str, Any], artifact_id: str, x: float, y: float, w: float, h: float) -> None:
        artifact = artifacts.get(artifact_id)
        path = _media_path(artifact or {}, project_root)
        if path and path.exists() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            media.append(path)
            slide.setdefault("images", []).append((path, _emu(x), _emu(y), _emu(w), _emu(h)))

    title = {
        "texts": [
            (_emu(0.58), _emu(0.48), _emu(4.5), _emu(0.3), _tr(locale, "TIGERCAPTURE STUDIO 2026", "TIGERCAPTURE STUDIO 2026"), 950, True, THEME_CYAN),
            (_emu(0.58), _emu(0.98), _emu(5.9), _emu(2.05), _tr(locale, "Creator\nEditing Suite", "크리에이터\n편집 스튜디오"), 4600, True, THEME_INK),
            (_emu(0.62), _emu(2.78), _emu(4.9), _emu(0.86), _tr(locale, "Record, edit, composite, finish. A local studio for creator demos, actor overlays, and multilingual delivery.", "녹화, 편집, 합성, 피니싱까지. 크리에이터 데모, 액터 오버레이, 다국어 전달을 위한 로컬 스튜디오."), 1500, False, THEME_MUTED),
            (_emu(0.68), _emu(4.52), _emu(1.35), _emu(0.36), "01", 2200, True, THEME_ACCENT),
            (_emu(1.5), _emu(4.58), _emu(3.2), _emu(0.36), _tr(locale, "Screen capture", "화면 캡처"), 1200, True, THEME_INK),
            (_emu(0.68), _emu(5.12), _emu(1.35), _emu(0.36), "02", 2200, True, THEME_CYAN),
            (_emu(1.5), _emu(5.18), _emu(3.2), _emu(0.36), _tr(locale, "Timeline + actors", "타임라인 + 액터"), 1200, True, THEME_INK),
            (_emu(0.68), _emu(5.72), _emu(1.35), _emu(0.36), "03", 2200, True, THEME_LIME),
            (_emu(1.5), _emu(5.78), _emu(3.2), _emu(0.36), _tr(locale, "Multilingual publish", "다국어 전달"), 1200, True, THEME_INK),
        ],
        "rects": [
            (_emu(5.95), _emu(0.0), _emu(7.38), _emu(7.5), THEME_PANEL, THEME_PANEL),
            (_emu(6.26), _emu(0.52), _emu(0.06), _emu(5.9), THEME_ACCENT, THEME_ACCENT),
            (_emu(0.62), _emu(4.12), _emu(4.15), _emu(0.02), THEME_LINE, THEME_LINE),
            (_emu(0.62), _emu(6.38), _emu(4.9), _emu(0.03), THEME_CYAN, THEME_CYAN),
        ],
        "images": [],
    }
    add_image(title, "catalog_editor_surface", 6.62, 0.78, 5.95, 3.35)
    add_image(title, "catalog_timeline_detail", 8.03, 4.72, 3.74, 2.1)
    slides = [title]

    overview = {
        "texts": [
            (_emu(0.56), _emu(0.46), _emu(4.7), _emu(0.42), _tr(locale, "EDITOR SURFACE", "편집 화면"), 950, True, THEME_CYAN),
            (_emu(0.56), _emu(0.9), _emu(6.3), _emu(0.62), _tr(locale, "One canvas for creator work", "크리에이터 작업을 위한 하나의 캔버스"), 3000, True, THEME_INK),
            (_emu(9.98), _emu(1.9), _emu(2.18), _emu(0.34), _tr(locale, "MEDIA POOL", "미디어 풀"), 1050, True, THEME_CYAN),
            (_emu(9.98), _emu(2.32), _emu(2.36), _emu(0.58), _tr(locale, "Import, relink, proxy, and organize creator assets.", "가져오기, relink, proxy, asset 정리를 한 곳에서 처리합니다."), 1120, False, THEME_MUTED),
            (_emu(9.98), _emu(3.3), _emu(2.18), _emu(0.34), _tr(locale, "TIMELINE", "타임라인"), 1050, True, THEME_ACCENT),
            (_emu(9.98), _emu(3.72), _emu(2.36), _emu(0.58), _tr(locale, "Cut clips, place actors, stack effects, and preview instantly.", "클립 컷, 액터 배치, 효과 스택, 즉시 preview를 지원합니다."), 1120, False, THEME_MUTED),
            (_emu(9.98), _emu(4.7), _emu(2.18), _emu(0.34), _tr(locale, "WORKBENCH", "워크벤치"), 1050, True, THEME_LIME),
            (_emu(9.98), _emu(5.12), _emu(2.36), _emu(0.58), _tr(locale, "Color, masks, subtitles, audio cleanup, and render queue.", "컬러, 마스크, 자막, 오디오 정리, 렌더 큐를 연결합니다."), 1120, False, THEME_MUTED),
            (_emu(0.62), _emu(6.62), _emu(10.7), _emu(0.38), _tr(locale, "A clean public screenshot is generated separately from QA evidence captures.", "공개용 스크린샷은 QA 증거 캡처와 별도로 생성됩니다."), 1250, False, THEME_MUTED),
        ],
        "rects": [
            (_emu(0.48), _emu(1.72), _emu(9.18), _emu(4.6), THEME_PANEL_2, THEME_LINE),
            (_emu(9.86), _emu(1.72), _emu(2.72), _emu(4.6), THEME_PANEL, THEME_LINE),
            (_emu(0.48), _emu(6.38), _emu(12.35), _emu(0.03), THEME_ACCENT, THEME_ACCENT),
        ],
        "images": [],
    }
    add_image(overview, "catalog_editor_surface", 0.68, 1.93, 8.78, 4.22)
    slides.append(overview)

    feature_lines = (
        [
            "캡처 폴리시        커서 트레일 / 클릭 링 / 자동 줌",
            "액터 타임라인      일반 영상 옆 Live2D lane",
            "6개 언어 UI        한국어 / 영어 / 일본어 / 중국어 / 프랑스어 / 독일어",
            "Creator Assist     캡션 / 쇼츠 / 게시 문구 / prompt edit",
            "피니싱 도구        컬러 / 오디오 정리 / 마스크 / preset",
        ]
        if _ko(locale)
        else [
            "Capture polish       Cursor trails / click rings / auto zoom",
            "Actor timeline       Live2D lanes beside normal video",
            "Six-language UI      Korean / English / Japanese / Chinese / French / German",
            "Creator assist       Captions / shorts / publish copy / prompt edits",
            "Finishing tools      Color / audio cleanup / masks / presets",
        ]
    )
    features_slide = {
        "texts": [
            (_emu(0.56), _emu(0.48), _emu(4.8), _emu(0.42), _tr(locale, "SIGNATURE WORKFLOWS", "대표 워크플로"), 950, True, THEME_ACCENT),
            (_emu(0.56), _emu(0.95), _emu(5.8), _emu(0.75), _tr(locale, "The parts people remember.", "기억에 남는 핵심 기능."), 3500, True, THEME_INK),
            (_emu(0.7), _emu(2.05), _emu(7.15), _emu(3.45), "\n".join(feature_lines), 1380, False, THEME_INK),
            (_emu(8.68), _emu(1.18), _emu(2.45), _emu(0.7), "6", 6900, True, THEME_LIME),
            (_emu(8.86), _emu(2.02), _emu(2.45), _emu(0.42), _tr(locale, "languages", "언어"), 1250, True, THEME_MUTED),
            (_emu(8.72), _emu(3.02), _emu(3.15), _emu(0.42), _tr(locale, "Local-first", "로컬 우선"), 1500, True, THEME_CYAN),
            (_emu(8.72), _emu(3.48), _emu(3.18), _emu(0.86), _tr(locale, "Sample media, screenshots, and generated catalogs stay in the developer workspace.", "샘플 미디어, 스크린샷, 생성 카탈로그는 개발자 워크스페이스에 유지됩니다."), 1280, False, THEME_MUTED),
            (_emu(8.72), _emu(5.08), _emu(3.15), _emu(0.58), _tr(locale, "Renderer claims stay private until the visual result passes.", "시각 결과가 통과하기 전까지 renderer claim은 제한합니다."), 1150, False, THEME_DIM),
        ],
        "rects": [
            (_emu(0.48), _emu(2.02), _emu(7.64), _emu(3.92), THEME_PANEL, THEME_LINE),
            (_emu(8.28), _emu(0.82), _emu(4.18), _emu(5.12), THEME_PANEL_2, THEME_LINE),
            (_emu(0.48), _emu(6.38), _emu(12.35), _emu(0.03), THEME_CYAN, THEME_CYAN),
        ],
        "images": [],
    }
    slides.append(features_slide)

    final = {
        "texts": [
            (_emu(0.58), _emu(0.48), _emu(4.8), _emu(0.42), _tr(locale, "CATALOG KIT", "카탈로그 키트"), 950, True, THEME_CYAN),
            (_emu(0.58), _emu(0.96), _emu(6.8), _emu(1.3), _tr(locale, "Three editions, one product story.", "세 가지 버전, 하나의 제품 이야기."), 3800, True, THEME_INK),
            (_emu(0.68), _emu(2.78), _emu(5.9), _emu(1.08), _tr(locale, "Use it as a product introduction, a feature catalog, or a showroom handoff when the spec changes.", "스펙이 바뀔 때마다 제품 소개, 기능 카탈로그, 쇼룸 전달 자료로 다시 생성합니다."), 1500, False, THEME_MUTED),
            (_emu(7.1), _emu(1.05), _emu(4.8), _emu(0.42), _tr(locale, "DELIVERABLES", "산출물"), 1100, True, THEME_ACCENT),
            (_emu(7.1), _emu(1.65), _emu(5.3), _emu(3.0), _tr(locale, "Summary deck\nDetailed feature book\nVisual appendix\nHTML catalog\nScreenshot set", "요약 덱\n상세 기능 북\n시각 증거 부록\nHTML 카탈로그\n스크린샷 세트"), 1600, False, THEME_INK),
            (_emu(0.68), _emu(5.72), _emu(8.8), _emu(0.38), _tr(locale, f"{summary.get('ready_artifacts', 0)} assets / {summary.get('sample_resources_ready', 0)} sample files / 3 deck modes", f"{summary.get('ready_artifacts', 0)}개 asset / {summary.get('sample_resources_ready', 0)}개 sample / 3개 deck mode"), 1200, False, THEME_LIME),
        ],
        "rects": [
            (_emu(7.0), _emu(0.82), _emu(5.55), _emu(4.02), THEME_PANEL, THEME_LINE),
            (_emu(0.58), _emu(5.52), _emu(11.95), _emu(0.78), THEME_PANEL_2, THEME_LINE),
            (_emu(0.48), _emu(6.38), _emu(12.35), _emu(0.03), THEME_ACCENT, THEME_ACCENT),
        ],
        "images": [],
    }
    slides.append(final)
    return slides, media


def _text_slide(
    title: str,
    lines: list[str],
    *,
    subtitle: str = "",
    footer: str = "",
    accent: str = THEME_CYAN,
    locale: str | None = None,
) -> dict[str, Any]:
    body = "\n".join(lines)
    body_size = 1120 if len(lines) > 11 else 1320 if len(lines) > 7 else 1520
    texts = [
        (_emu(0.58), _emu(0.44), _emu(3.6), _emu(0.35), _tr(locale, "TIGERCAPTURE REVIEW", "TIGERCAPTURE 리뷰"), 850, True, accent),
        (_emu(0.58), _emu(0.87), _emu(10.2), _emu(0.75), title, 3100, True, THEME_INK),
    ]
    if subtitle:
        texts.append((_emu(0.62), _emu(1.55), _emu(7.5), _emu(0.36), subtitle, 1100, False, THEME_MUTED))
    texts.append((_emu(0.86), _emu(2.18), _emu(10.95), _emu(3.78), body, body_size, False, THEME_INK))
    if footer:
        texts.append((_emu(0.68), _emu(6.72), _emu(11.5), _emu(0.24), footer, 800, False, THEME_DIM))
    return {
        "texts": texts,
        "rects": [
            (_emu(0.48), _emu(2.0), _emu(12.3), _emu(4.18), THEME_PANEL, THEME_LINE),
            (_emu(0.48), _emu(6.38), _emu(12.35), _emu(0.03), accent, accent),
            (_emu(11.9), _emu(0.45), _emu(0.66), _emu(0.08), accent, accent),
        ],
        "images": [],
    }


def _mode_title_slide(
    report: Mapping[str, Any],
    project_root: Path,
    *,
    title: str,
    subtitle: str,
    locale: str | None = None,
) -> tuple[dict[str, Any], list[Path]]:
    artifacts = _artifact_map(report)
    media: list[Path] = []
    slide = {
        "texts": [
            (_emu(0.58), _emu(0.48), _emu(3.8), _emu(0.3), _tr(locale, "TIGERCAPTURE / REVIEW SYSTEM", "TIGERCAPTURE / 리뷰 시스템"), 950, True, THEME_CYAN),
            (_emu(0.58), _emu(0.95), _emu(6.2), _emu(2.05), title, 4600, True, THEME_INK),
            (_emu(0.65), _emu(3.08), _emu(4.95), _emu(0.9), subtitle, 1500, False, THEME_MUTED),
            (_emu(0.62), _emu(6.76), _emu(8.2), _emu(0.26), str(report.get("generated_at") or ""), 800, False, THEME_DIM),
        ],
        "rects": [
            (_emu(6.15), _emu(0.0), _emu(7.18), _emu(7.5), THEME_PANEL, THEME_PANEL),
            (_emu(6.44), _emu(0.42), _emu(0.08), _emu(6.15), THEME_ACCENT, THEME_ACCENT),
        ],
        "images": [],
    }
    poster = _media_path(artifacts.get("review_overview_poster") or {}, project_root)
    if poster and poster.exists() and poster.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        media.append(poster)
        slide["images"].append((poster, _emu(7.05), _emu(0.82), _emu(5.35), _emu(3.1)))
    return slide, media


def _contact_sheet_slide(report: Mapping[str, Any], project_root: Path, *, title: str) -> tuple[dict[str, Any], list[Path]]:
    artifacts = _artifact_map(report)
    media: list[Path] = []
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    slide = {
        "texts": [
            (_emu(0.56), _emu(0.46), _emu(4.7), _emu(0.42), "VISUAL EVIDENCE", 950, True, THEME_CYAN),
            (_emu(0.56), _emu(0.87), _emu(6.8), _emu(0.62), title, 3000, True, THEME_INK),
            (
                _emu(0.62),
                _emu(6.62),
                _emu(11.8),
                _emu(0.34),
                f"{summary.get('evidence_ready', 0)}/{summary.get('features', 0)} review features evidence-ready · "
                f"{summary.get('ready_artifacts', 0)}/{summary.get('artifacts', 0)} artifacts ready · "
                f"deck mode={report.get('deck_mode', 'summary')}",
                1150,
                False,
                THEME_MUTED,
            ),
        ],
        "rects": [
            (_emu(0.48), _emu(1.72), _emu(12.35), _emu(4.55), THEME_PANEL_2, THEME_LINE),
            (_emu(0.48), _emu(6.38), _emu(12.35), _emu(0.03), THEME_ACCENT, THEME_ACCENT),
        ],
        "images": [],
    }
    contact = _media_path(artifacts.get("review_contact_sheet") or artifacts.get("editor_contact_sheet") or {}, project_root)
    if contact and contact.exists() and contact.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        media.append(contact)
        slide["images"].append((contact, _emu(0.74), _emu(1.95), _emu(11.82), _emu(4.05)))
    return slide, media


def _qa_line(row: Mapping[str, Any]) -> str:
    state = "OK" if row.get("exists") and row.get("ok") else "ATTN" if row.get("exists") else "MISS"
    return f"{state} · {row.get('label', row.get('kind', 'QA'))}: {row.get('summary', '')}"


def _topic_slide(
    topic: Mapping[str, Any],
    report: Mapping[str, Any] | None = None,
    project_root: Path | None = None,
) -> tuple[dict[str, Any], list[Path]]:
    lines = [f"- {item}" for item in list(topic.get("bullets", []) or [])]
    title = str(topic.get("title") or "Feature Topic")
    category = str(topic.get("category") or "")
    media: list[Path] = []
    artifact_path: Path | None = None
    if report is not None and project_root is not None:
        artifacts = _artifact_map(report)
        artifact = artifacts.get(feature_editor_surface_artifact_id(str(topic.get("id") or "")))
        path = _media_path(artifact or {}, project_root)
        if path and path.exists() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            artifact_path = path
            media.append(path)
    if artifact_path is None:
        return (
            _text_slide(
                title,
                lines,
                subtitle=category,
                footer="Missing feature editor screenshot; review automation must capture this feature.",
                accent=THEME_ACCENT,
            ),
            media,
        )
    slide = {
        "texts": [
            (_emu(0.58), _emu(0.44), _emu(3.6), _emu(0.35), "FEATURE WORKFLOW", 850, True, THEME_CYAN),
            (_emu(0.58), _emu(0.86), _emu(4.75), _emu(0.85), title, 2500, True, THEME_INK),
            (_emu(0.62), _emu(1.62), _emu(4.1), _emu(0.36), category, 1100, False, THEME_MUTED),
            (_emu(0.72), _emu(2.18), _emu(4.18), _emu(2.85), "\n".join(lines), 1160, False, THEME_INK),
            (_emu(0.68), _emu(6.62), _emu(11.4), _emu(0.34), "Feature explanation is anchored to an automated editor-work screenshot.", 1050, False, THEME_MUTED),
        ],
        "rects": [
            (_emu(5.1), _emu(0.72), _emu(7.54), _emu(5.62), THEME_PANEL_2, THEME_LINE),
            (_emu(0.48), _emu(2.0), _emu(4.42), _emu(3.48), THEME_PANEL, THEME_LINE),
            (_emu(0.48), _emu(6.38), _emu(12.35), _emu(0.03), THEME_CYAN, THEME_CYAN),
        ],
        "images": [
            (artifact_path, _emu(5.3), _emu(0.92), _emu(7.12), _emu(5.0)),
        ],
    }
    return slide, media


def _topic_qa_slide(topic: Mapping[str, Any]) -> dict[str, Any]:
    rows = [row for row in list(topic.get("qa_rows", []) or []) if isinstance(row, Mapping)]
    lines = [_qa_line(row) for row in rows[:9]] or ["No matching QA rows are currently linked to this topic."]
    return _text_slide(
        f"{topic.get('title', 'Feature Topic')} Evidence",
        lines,
        subtitle="QA Dashboard evidence linked by topic keywords",
        accent=THEME_WARN,
    )


def _qa_evidence_slide(row: Mapping[str, Any], index: int, total: int) -> dict[str, Any]:
    state = "OK" if row.get("exists") and row.get("ok") else "ATTENTION" if row.get("exists") else "MISSING"
    lines = [
        f"Status: {state}",
        f"Kind: {row.get('kind', '-')}",
        f"Report: {row.get('path', '-')}",
        f"Summary: {row.get('summary', 'missing')}",
    ]
    return _text_slide(
        str(row.get("label") or row.get("kind") or "QA Evidence"),
        lines,
        subtitle=f"Evidence appendix {index}/{total}",
        footer="Generated from QA Dashboard REPORT_SPECS.",
        accent=THEME_CYAN if state == "OK" else THEME_ACCENT,
    )


def _contact_sheet_slide(
    report: Mapping[str, Any],
    project_root: Path,
    *,
    title: str,
    locale: str | None = None,
) -> tuple[dict[str, Any], list[Path]]:
    artifacts = _artifact_map(report)
    media: list[Path] = []
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    footer = _tr(
        locale,
        f"{summary.get('evidence_ready', 0)}/{summary.get('features', 0)} review features evidence-ready / "
        f"{summary.get('ready_artifacts', 0)}/{summary.get('artifacts', 0)} artifacts ready / "
        f"deck mode={report.get('deck_mode', 'summary')}",
        f"리뷰 기능 {summary.get('evidence_ready', 0)}/{summary.get('features', 0)}개 증거 준비 / "
        f"artifact {summary.get('ready_artifacts', 0)}/{summary.get('artifacts', 0)}개 준비 / "
        f"deck mode={report.get('deck_mode', 'summary')}",
    )
    slide = {
        "texts": [
            (_emu(0.56), _emu(0.46), _emu(4.7), _emu(0.42), _tr(locale, "VISUAL EVIDENCE", "시각 증거"), 950, True, THEME_CYAN),
            (_emu(0.56), _emu(0.87), _emu(6.8), _emu(0.62), title, 3000, True, THEME_INK),
            (_emu(0.62), _emu(6.62), _emu(11.8), _emu(0.34), footer, 1150, False, THEME_MUTED),
        ],
        "rects": [
            (_emu(0.48), _emu(1.72), _emu(12.35), _emu(4.55), THEME_PANEL_2, THEME_LINE),
            (_emu(0.48), _emu(6.38), _emu(12.35), _emu(0.03), THEME_ACCENT, THEME_ACCENT),
        ],
        "images": [],
    }
    contact = _media_path(artifacts.get("review_contact_sheet") or artifacts.get("editor_contact_sheet") or {}, project_root)
    if contact and contact.exists() and contact.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        media.append(contact)
        slide["images"].append((contact, _emu(0.74), _emu(1.95), _emu(11.82), _emu(4.05)))
    return slide, media


def _qa_line(row: Mapping[str, Any], locale: str | None = None) -> str:
    state = "OK" if row.get("exists") and row.get("ok") else "ATTN" if row.get("exists") else "MISS"
    if _ko(locale):
        state = "통과" if state == "OK" else "확인" if state == "ATTN" else "누락"
    return f"{state} · {row.get('label', row.get('kind', 'QA'))}: {row.get('summary', '')}"


def _topic_slide(
    topic: Mapping[str, Any],
    report: Mapping[str, Any] | None = None,
    project_root: Path | None = None,
    locale: str | None = None,
) -> tuple[dict[str, Any], list[Path]]:
    topic = _localized_topic(topic, locale)
    lines = [f"- {item}" for item in list(topic.get("bullets", []) or [])]
    title = str(topic.get("title") or "Feature Topic")
    category = str(topic.get("category") or "")
    media: list[Path] = []
    artifact_path: Path | None = None
    if report is not None and project_root is not None:
        artifacts = _artifact_map(report)
        artifact = artifacts.get(feature_editor_surface_artifact_id(str(topic.get("id") or "")))
        path = _media_path(artifact or {}, project_root)
        if path and path.exists() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            artifact_path = path
            media.append(path)
    if artifact_path is None:
        return (
            _text_slide(
                title,
                lines,
                subtitle=category,
                footer=_tr(locale, "Missing feature editor screenshot; review automation must capture this feature.", "기능 에디터 스크린샷이 없습니다. 리뷰 자동화가 이 기능 캡처를 생성해야 합니다."),
                accent=THEME_ACCENT,
                locale=locale,
            ),
            media,
        )
    slide = {
        "texts": [
            (_emu(0.58), _emu(0.44), _emu(3.6), _emu(0.35), _tr(locale, "FEATURE WORKFLOW", "기능 워크플로"), 850, True, THEME_CYAN),
            (_emu(0.58), _emu(0.86), _emu(4.75), _emu(0.85), title, 2500, True, THEME_INK),
            (_emu(0.62), _emu(1.62), _emu(4.1), _emu(0.36), category, 1100, False, THEME_MUTED),
            (_emu(0.72), _emu(2.18), _emu(4.18), _emu(2.85), "\n".join(lines), 1160, False, THEME_INK),
            (_emu(0.68), _emu(6.62), _emu(11.4), _emu(0.34), _tr(locale, "Feature explanation is anchored to an automated editor-work screenshot.", "기능 설명은 자동화된 에디터 작업 스크린샷을 기준으로 작성됩니다."), 1050, False, THEME_MUTED),
        ],
        "rects": [
            (_emu(5.1), _emu(0.72), _emu(7.54), _emu(5.62), THEME_PANEL_2, THEME_LINE),
            (_emu(0.48), _emu(2.0), _emu(4.42), _emu(3.48), THEME_PANEL, THEME_LINE),
            (_emu(0.48), _emu(6.38), _emu(12.35), _emu(0.03), THEME_CYAN, THEME_CYAN),
        ],
        "images": [
            (artifact_path, _emu(5.3), _emu(0.92), _emu(7.12), _emu(5.0)),
        ],
    }
    return slide, media


def _topic_qa_slide(topic: Mapping[str, Any], locale: str | None = None) -> dict[str, Any]:
    topic = _localized_topic(topic, locale)
    rows = [row for row in list(topic.get("qa_rows", []) or []) if isinstance(row, Mapping)]
    lines = [_qa_line(row, locale) for row in rows[:9]] or [_tr(locale, "No matching QA rows are currently linked to this topic.", "이 토픽에 연결된 QA 행이 아직 없습니다.")]
    return _text_slide(
        _tr(locale, f"{topic.get('title', 'Feature Topic')} Evidence", f"{topic.get('title', '기능 토픽')} 증거"),
        lines,
        subtitle=_tr(locale, "QA Dashboard evidence linked by topic keywords", "토픽 키워드로 연결된 QA Dashboard 증거"),
        accent=THEME_WARN,
        locale=locale,
    )


def _qa_evidence_slide(row: Mapping[str, Any], index: int, total: int, *, locale: str | None = None) -> dict[str, Any]:
    state = "OK" if row.get("exists") and row.get("ok") else "ATTENTION" if row.get("exists") else "MISSING"
    if _ko(locale):
        lines = [
            f"상태: {'통과' if state == 'OK' else '확인 필요' if state == 'ATTENTION' else '누락'}",
            f"종류: {row.get('kind', '-')}",
            f"리포트: {row.get('path', '-')}",
            f"요약: {row.get('summary', 'missing')}",
        ]
    else:
        lines = [
            f"Status: {state}",
            f"Kind: {row.get('kind', '-')}",
            f"Report: {row.get('path', '-')}",
            f"Summary: {row.get('summary', 'missing')}",
        ]
    return _text_slide(
        str(row.get("label") or row.get("kind") or "QA Evidence"),
        lines,
        subtitle=_tr(locale, f"Evidence appendix {index}/{total}", f"증거 부록 {index}/{total}"),
        footer=_tr(locale, "Generated from QA Dashboard REPORT_SPECS.", "QA Dashboard REPORT_SPECS에서 생성되었습니다."),
        accent=THEME_CYAN if state == "OK" else THEME_ACCENT,
        locale=locale,
    )


def _build_detailed_slides(report: Mapping[str, Any], project_root: Path) -> tuple[list[dict[str, Any]], list[Path]]:
    plan = report.get("deck_plan", {}) if isinstance(report.get("deck_plan"), Mapping) else {}
    topics = [row for row in list(plan.get("topics", []) or []) if isinstance(row, Mapping)]
    features = [row for row in list(report.get("features", []) or []) if isinstance(row, Mapping)]
    title, title_media = _mode_title_slide(
        report,
        project_root,
        title="TigerCapture\nDetailed Review",
        subtitle="Feature-group deck generated from README, SPEC, QA Dashboard, and review automation evidence.",
    )
    contact, contact_media = _contact_sheet_slide(report, project_root, title="Evidence Overview")
    feature_lines = [
        f"{feature.get('title')}: {str(feature.get('status', 'unknown')).replace('_', ' ')}"
        for feature in features[:10]
    ]
    slides = [
        title,
        contact,
        _text_slide(
            "Review Feature Registry",
            feature_lines or ["No review features registered."],
            subtitle="Current review automation registry status",
            accent="C4A2FF",
        ),
    ]
    topic_media: list[Path] = []
    for topic in topics:
        topic_slide, media = _topic_slide(topic, report, project_root)
        slides.append(topic_slide)
        topic_media.extend(media)
        slides.append(_topic_qa_slide(topic))
    slides.append(
        _text_slide(
            "Regeneration Contract",
            [
                "Regenerate when SPEC.md, README.md, release positioning, QA reports, or sample resources change.",
                "Summary mode is for quick introductions.",
                "Detailed mode is for feature presentations.",
                "Evidence Full mode is for appendix-style proof and internal review.",
            ],
            subtitle="How this deck stays aligned with moving specs",
            accent=THEME_CYAN,
        )
    )
    return slides, title_media + contact_media + topic_media


def _build_evidence_full_slides(report: Mapping[str, Any], project_root: Path) -> tuple[list[dict[str, Any]], list[Path]]:
    plan = report.get("deck_plan", {}) if isinstance(report.get("deck_plan"), Mapping) else {}
    topics = [row for row in list(plan.get("topics", []) or []) if isinstance(row, Mapping)]
    qa_rows = [row for row in list(plan.get("qa_rows", []) or []) if isinstance(row, Mapping)]
    title, title_media = _mode_title_slide(
        report,
        project_root,
        title="TigerCapture\nEvidence Full",
        subtitle="Full evidence appendix generated from QA Dashboard report contracts and review automation outputs.",
    )
    contact, contact_media = _contact_sheet_slide(report, project_root, title="Collected Visual Evidence")
    slides = [
        title,
        _text_slide(
            "How To Read This Evidence Deck",
            [
                "Each appendix slide maps to a QA Dashboard row.",
                "OK means the report file exists and reports ok=true.",
                "ATTENTION means the report exists but reports ok=false.",
                "MISSING means the report artifact has not been generated yet.",
                "Blocked product claims should remain blocked until their evidence slide is OK.",
            ],
            subtitle="Evidence Full mode",
            accent=THEME_WARN,
        ),
        contact,
        _text_slide(
            "Feature Group Index",
            [f"{idx + 1}. {topic.get('title')} ({topic.get('category')})" for idx, topic in enumerate(topics)],
            subtitle=f"{len(topics)} feature groups · {len(qa_rows)} QA evidence rows",
            accent=THEME_CYAN,
        ),
    ]
    topic_media: list[Path] = []
    for topic in topics:
        topic_slide, media = _topic_slide(topic, report, project_root)
        slides.append(topic_slide)
        topic_media.extend(media)
    for index, row in enumerate(qa_rows, start=1):
        slides.append(_qa_evidence_slide(row, index, len(qa_rows)))
    slides.append(
        _text_slide(
            "Evidence Full Close",
            [
                f"QA rows covered: {len(qa_rows)}",
                f"Feature groups covered: {len(topics)}",
                "Use this deck as an appendix or internal review artifact, not as the main sales presentation.",
            ],
            subtitle="Generated appendix complete",
            accent=THEME_CYAN,
        )
    )
    return slides, title_media + contact_media + topic_media


def _build_detailed_slides(
    report: Mapping[str, Any],
    project_root: Path,
    *,
    locale: str | None = None,
) -> tuple[list[dict[str, Any]], list[Path]]:
    plan = report.get("deck_plan", {}) if isinstance(report.get("deck_plan"), Mapping) else {}
    topics = [row for row in list(plan.get("topics", []) or []) if isinstance(row, Mapping)]
    features = [row for row in list(report.get("features", []) or []) if isinstance(row, Mapping)]
    title, title_media = _mode_title_slide(
        report,
        project_root,
        title=_tr(locale, "TigerCapture\nDetailed Review", "TigerCapture\n상세 리뷰"),
        subtitle=_tr(
            locale,
            "Feature-group deck generated from README, SPEC, QA Dashboard, and review automation evidence.",
            "README, SPEC, QA Dashboard, 리뷰 자동화 증거에서 생성한 기능별 덱입니다.",
        ),
        locale=locale,
    )
    contact, contact_media = _contact_sheet_slide(
        report,
        project_root,
        title=_tr(locale, "Evidence Overview", "증거 오버뷰"),
        locale=locale,
    )
    feature_lines = [
        f"{_localized_feature_title(feature, locale)}: {_localized_status(feature.get('status', 'unknown'), locale)}"
        for feature in features[:10]
    ]
    slides = [
        title,
        contact,
        _text_slide(
            _tr(locale, "Review Feature Registry", "리뷰 기능 레지스트리"),
            feature_lines or [_tr(locale, "No review features registered.", "등록된 리뷰 기능이 없습니다.")],
            subtitle=_tr(locale, "Current review automation registry status", "현재 리뷰 자동화 registry 상태"),
            accent="C7CCC8",
            locale=locale,
        ),
    ]
    topic_media: list[Path] = []
    for topic in topics:
        topic_slide, media = _topic_slide(topic, report, project_root, locale=locale)
        slides.append(topic_slide)
        topic_media.extend(media)
        slides.append(_topic_qa_slide(topic, locale=locale))
    slides.append(
        _text_slide(
            _tr(locale, "Regeneration Contract", "재생성 계약"),
            [
                _tr(locale, "Regenerate when SPEC.md, README.md, release positioning, QA reports, or sample resources change.", "SPEC.md, README.md, release positioning, QA report, sample resource가 바뀌면 다시 생성합니다."),
                _tr(locale, "Summary mode is for quick introductions.", "Summary mode는 빠른 소개용입니다."),
                _tr(locale, "Detailed mode is for feature presentations.", "Detailed mode는 기능 설명용입니다."),
                _tr(locale, "Evidence Full mode is for appendix-style proof and internal review.", "Evidence Full mode는 증거 부록과 내부 리뷰용입니다."),
            ],
            subtitle=_tr(locale, "How this deck stays aligned with moving specs", "변하는 스펙과 덱을 맞추는 방식"),
            accent=THEME_CYAN,
            locale=locale,
        )
    )
    return slides, title_media + contact_media + topic_media


def _build_evidence_full_slides(
    report: Mapping[str, Any],
    project_root: Path,
    *,
    locale: str | None = None,
) -> tuple[list[dict[str, Any]], list[Path]]:
    plan = report.get("deck_plan", {}) if isinstance(report.get("deck_plan"), Mapping) else {}
    topics = [row for row in list(plan.get("topics", []) or []) if isinstance(row, Mapping)]
    qa_rows = [row for row in list(plan.get("qa_rows", []) or []) if isinstance(row, Mapping)]
    title, title_media = _mode_title_slide(
        report,
        project_root,
        title=_tr(locale, "TigerCapture\nEvidence Full", "TigerCapture\n전체 증거"),
        subtitle=_tr(
            locale,
            "Full evidence appendix generated from QA Dashboard report contracts and review automation outputs.",
            "QA Dashboard report contract와 리뷰 자동화 output에서 생성한 전체 증거 부록입니다.",
        ),
        locale=locale,
    )
    contact, contact_media = _contact_sheet_slide(
        report,
        project_root,
        title=_tr(locale, "Collected Visual Evidence", "수집된 시각 증거"),
        locale=locale,
    )
    localized_topics = [_localized_topic(topic, locale) for topic in topics]
    slides = [
        title,
        _text_slide(
            _tr(locale, "How To Read This Evidence Deck", "전체 증거 덱 읽는 법"),
            [
                _tr(locale, "Each appendix slide maps to a QA Dashboard row.", "각 부록 슬라이드는 QA Dashboard 행에 대응합니다."),
                _tr(locale, "OK means the report file exists and reports ok=true.", "OK는 report 파일이 있고 ok=true라는 뜻입니다."),
                _tr(locale, "ATTENTION means the report exists but reports ok=false.", "ATTENTION은 report는 있지만 ok=false라는 뜻입니다."),
                _tr(locale, "MISSING means the report artifact has not been generated yet.", "MISSING은 report artifact가 아직 생성되지 않았다는 뜻입니다."),
                _tr(locale, "Blocked product claims should remain blocked until their evidence slide is OK.", "차단된 product claim은 증거 slide가 OK가 될 때까지 차단 상태로 유지해야 합니다."),
            ],
            subtitle=_tr(locale, "Evidence Full mode", "전체 증거 모드"),
            accent=THEME_WARN,
            locale=locale,
        ),
        contact,
        _text_slide(
            _tr(locale, "Feature Group Index", "기능 그룹 인덱스"),
            [f"{idx + 1}. {topic.get('title')} ({topic.get('category')})" for idx, topic in enumerate(localized_topics)],
            subtitle=_tr(locale, f"{len(topics)} feature groups / {len(qa_rows)} QA evidence rows", f"기능 그룹 {len(topics)}개 / QA 증거 행 {len(qa_rows)}개"),
            accent=THEME_CYAN,
            locale=locale,
        ),
    ]
    topic_media: list[Path] = []
    for topic in topics:
        topic_slide, media = _topic_slide(topic, report, project_root, locale=locale)
        slides.append(topic_slide)
        topic_media.extend(media)
    for index, row in enumerate(qa_rows, start=1):
        slides.append(_qa_evidence_slide(row, index, len(qa_rows), locale=locale))
    slides.append(
        _text_slide(
            _tr(locale, "Evidence Full Close", "전체 증거 마무리"),
            [
                _tr(locale, f"QA rows covered: {len(qa_rows)}", f"포함된 QA 행: {len(qa_rows)}개"),
                _tr(locale, f"Feature groups covered: {len(topics)}", f"포함된 기능 그룹: {len(topics)}개"),
                _tr(locale, "Use this deck as an appendix or internal review artifact, not as the main sales presentation.", "이 덱은 메인 세일즈 자료가 아니라 부록 또는 내부 리뷰 자료로 사용합니다."),
            ],
            subtitle=_tr(locale, "Generated appendix complete", "생성된 부록 완료"),
            accent=THEME_CYAN,
            locale=locale,
        )
    )
    return slides, title_media + contact_media + topic_media


def _build_slides(
    report: Mapping[str, Any],
    project_root: Path,
    *,
    deck_mode: str = "summary",
    locale: str | None = None,
) -> tuple[list[dict[str, Any]], list[Path]]:
    mode = str(deck_mode or report.get("deck_mode") or "summary").strip().lower().replace("_", "-")
    if mode == "detailed":
        return _build_detailed_slides(report, project_root, locale=locale)
    if mode in {"evidence-full", "evidence"}:
        return _build_evidence_full_slides(report, project_root, locale=locale)
    return _build_summary_slides(report, project_root, locale=locale)


def write_review_pptx(
    report: Mapping[str, Any],
    path: str | Path,
    *,
    project_root: str | Path,
    deck_mode: str = "summary",
    locale: str | None = None,
) -> Path:
    target = Path(path)
    root = Path(project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    slides, media = _build_slides(report, root, deck_mode=deck_mode, locale=locale)
    font_face = review_ppt_font(locale)
    rel_type_base = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types(len(slides), media))
        zf.writestr("_rels/.rels", _rels_xml([
            ("rId1", f"{rel_type_base}/officeDocument", "ppt/presentation.xml"),
            ("rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"),
            ("rId3", f"{rel_type_base}/extended-properties", "docProps/app.xml"),
        ]))
        zf.writestr("docProps/core.xml", _core_xml())
        zf.writestr("docProps/app.xml", _app_xml(len(slides)))
        zf.writestr("ppt/presentation.xml", _presentation_xml(len(slides)))
        pres_rels = [("rId1", f"{rel_type_base}/slideMaster", "slideMasters/slideMaster1.xml")]
        for idx in range(1, len(slides) + 1):
            pres_rels.append((f"rId{idx + 1}", f"{rel_type_base}/slide", f"slides/slide{idx}.xml"))
        zf.writestr("ppt/_rels/presentation.xml.rels", _rels_xml(pres_rels))
        zf.writestr("ppt/slideMasters/slideMaster1.xml", _slide_master_xml())
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", _rels_xml([
            ("rId1", f"{rel_type_base}/slideLayout", "../slideLayouts/slideLayout1.xml"),
            ("rId2", f"{rel_type_base}/theme", "../theme/theme1.xml"),
        ]))
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", _slide_layout_xml())
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", _rels_xml([
            ("rId1", f"{rel_type_base}/slideMaster", "../slideMasters/slideMaster1.xml"),
        ]))
        zf.writestr("ppt/theme/theme1.xml", _theme_xml())
        media_index = 1
        for idx, slide in enumerate(slides, start=1):
            shapes: list[str] = []
            shape_id = 2
            for x, y, w, h, fill, line in slide.get("rects", []):
                shapes.append(_rect(shape_id, x, y, w, h, fill=fill, line=line))
                shape_id += 1
            rels = [("rId1", f"{rel_type_base}/slideLayout", "../slideLayouts/slideLayout1.xml")]
            for image, x, y, w, h in slide.get("images", []):
                ext = image.suffix.lower() or ".png"
                media_name = f"image{media_index}{ext}"
                media_index += 1
                rel_id = f"rId{len(rels) + 1}"
                zf.write(image, f"ppt/media/{media_name}")
                rels.append((rel_id, f"{rel_type_base}/image", f"../media/{media_name}"))
                shapes.append(_picture(shape_id, rel_id, x, y, w, h, image.name))
                shape_id += 1
            for row in slide.get("texts", []):
                x, y, w, h, text, size, bold, color, *extra = row
                align = str(extra[0]) if len(extra) >= 1 else "l"
                caps = bool(extra[1]) if len(extra) >= 2 else False
                shapes.append(
                    _text_box(
                        shape_id,
                        x,
                        y,
                        w,
                        h,
                        text,
                        size=size,
                        bold=bold,
                        color=color,
                        align=align,
                        caps=caps,
                        font_face=font_face,
                    )
                )
                shape_id += 1
            if len(slides) > 1:
                shapes.append(_slide_number(shape_id, idx, len(slides)))
                shape_id += 1
            zf.writestr(f"ppt/slides/slide{idx}.xml", _slide_xml(shapes))
            zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", _rels_xml(rels))
    return target
