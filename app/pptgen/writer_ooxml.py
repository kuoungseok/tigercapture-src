"""OOXML PPTX writer for the user PPT generator."""
from __future__ import annotations

import html
import mimetypes
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.pptgen.formula import evaluate_numeric_formula, format_formula_value
from app.pptgen.animations import animation_is_active, animation_payload, animation_sequence_sort_key
from app.pptgen.overlays import slide_overlay_elements
from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec


SLIDE_W = 12192000
SLIDE_H = 6858000


def _x(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _hex(value: str | None, fallback: str = "#FFFFFF") -> str:
    raw = str(value or fallback).strip().lstrip("#")
    if len(raw) == 8:
        raw = raw[:6]
    if len(raw) != 6:
        raw = fallback.lstrip("#")
    return raw.upper()


def _emu_x(value: float) -> int:
    return int(round(max(0.0, min(1.0, float(value))) * SLIDE_W))


def _emu_y(value: float) -> int:
    return int(round(max(0.0, min(1.0, float(value))) * SLIDE_H))


def _pt100(value: int | float) -> int:
    return max(800, int(round(float(value) * 100)))


def _rels_xml(rels: list[tuple[str, str, str]]) -> str:
    rows = [f'<Relationship Id="{_x(rid)}" Type="{_x(rtype)}" Target="{_x(target)}"/>' for rid, rtype, target in rels]
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rows)
        + "</Relationships>"
    )


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


def _core_xml(deck: DeckSpec) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{_x(deck.title)}</dc:title>
  <dc:creator>TigerCapture PPT Generator</dc:creator>
  <cp:lastModifiedBy>TigerCapture PPT Generator</cp:lastModifiedBy>
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
    slide_ids = "".join(f'<p:sldId id="{256 + idx}" r:id="rId{idx + 2}"/>' for idx in range(slide_count))
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


def _slide_layout_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
             type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name="Group 1"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
  </p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>
"""


def _slide_master_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name="Group 1"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
  </p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>
"""


def _theme_xml(deck: DeckSpec) -> str:
    font = deck.theme.font_family or "Noto Sans KR"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="TigerCapture">
  <a:themeElements>
    <a:clrScheme name="TigerCapture">
      <a:dk1><a:srgbClr val="{_hex(deck.theme.background)}"/></a:dk1><a:lt1><a:srgbClr val="{_hex(deck.theme.ink)}"/></a:lt1>
      <a:dk2><a:srgbClr val="{_hex(deck.theme.surface)}"/></a:dk2><a:lt2><a:srgbClr val="{_hex(deck.theme.muted)}"/></a:lt2>
      <a:accent1><a:srgbClr val="{_hex(deck.theme.accent)}"/></a:accent1><a:accent2><a:srgbClr val="D88716"/></a:accent2>
      <a:accent3><a:srgbClr val="3A8F5A"/></a:accent3><a:accent4><a:srgbClr val="8B5CF6"/></a:accent4>
      <a:accent5><a:srgbClr val="C7CCC8"/></a:accent5><a:accent6><a:srgbClr val="CCCCCC"/></a:accent6>
      <a:hlink><a:srgbClr val="{_hex(deck.theme.accent)}"/></a:hlink><a:folHlink><a:srgbClr val="C4A2FF"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="TigerCapture">
      <a:majorFont><a:latin typeface="{_x(font)}"/><a:ea typeface="{_x(font)}"/><a:cs typeface="{_x(font)}"/></a:majorFont>
      <a:minorFont><a:latin typeface="{_x(font)}"/><a:ea typeface="{_x(font)}"/><a:cs typeface="{_x(font)}"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="TigerCapture">
      <a:fillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:gradFill rotWithShape="1">
          <a:gsLst>
            <a:gs pos="0"><a:schemeClr val="phClr"><a:tint val="50000"/><a:satMod val="300000"/></a:schemeClr></a:gs>
            <a:gs pos="35000"><a:schemeClr val="phClr"><a:tint val="37000"/><a:satMod val="300000"/></a:schemeClr></a:gs>
            <a:gs pos="100000"><a:schemeClr val="phClr"><a:tint val="15000"/><a:satMod val="350000"/></a:schemeClr></a:gs>
          </a:gsLst>
          <a:lin ang="16200000" scaled="1"/>
        </a:gradFill>
        <a:gradFill rotWithShape="1">
          <a:gsLst>
            <a:gs pos="0"><a:schemeClr val="phClr"><a:shade val="51000"/><a:satMod val="130000"/></a:schemeClr></a:gs>
            <a:gs pos="80000"><a:schemeClr val="phClr"><a:shade val="93000"/><a:satMod val="130000"/></a:schemeClr></a:gs>
            <a:gs pos="100000"><a:schemeClr val="phClr"><a:shade val="94000"/><a:satMod val="135000"/></a:schemeClr></a:gs>
          </a:gsLst>
          <a:lin ang="16200000" scaled="0"/>
        </a:gradFill>
      </a:fillStyleLst>
      <a:lnStyleLst>
        <a:ln w="6350" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>
        <a:ln w="12700" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>
        <a:ln w="19050" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>
      </a:lnStyleLst>
      <a:effectStyleLst>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
      </a:effectStyleLst>
      <a:bgFillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"><a:tint val="95000"/><a:satMod val="170000"/></a:schemeClr></a:solidFill>
        <a:gradFill rotWithShape="1">
          <a:gsLst>
            <a:gs pos="0"><a:schemeClr val="phClr"><a:tint val="93000"/><a:satMod val="150000"/><a:shade val="98000"/></a:schemeClr></a:gs>
            <a:gs pos="50000"><a:schemeClr val="phClr"><a:tint val="98000"/><a:satMod val="130000"/><a:shade val="90000"/></a:schemeClr></a:gs>
            <a:gs pos="100000"><a:schemeClr val="phClr"><a:shade val="63000"/><a:satMod val="120000"/></a:schemeClr></a:gs>
          </a:gsLst>
          <a:lin ang="16200000" scaled="0"/>
        </a:gradFill>
      </a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
  <a:objectDefaults/>
  <a:extraClrSchemeLst/>
</a:theme>
"""


def _shape_xml(shape_id: int, element: SlideElement, deck: DeckSpec) -> str:
    x, y = _emu_x(element.x), _emu_y(element.y)
    w, h = _emu_x(element.w), _emu_y(element.h)
    fill = _hex(element.style.fill or deck.theme.surface)
    line = _hex(element.style.stroke or deck.theme.accent)
    line_width = max(0, int(round(float(element.style.stroke_width or 0) * 12700)))
    line_xml = '<a:ln w="0"><a:noFill/></a:ln>' if line_width <= 0 else f'<a:ln w="{line_width}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
    return f"""
      <p:sp>
        <p:nvSpPr><p:cNvPr id="{shape_id}" name="{_x(element.name or element.kind)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>{line_xml}</p:spPr>
      </p:sp>
"""


def _text_xml(shape_id: int, element: SlideElement, deck: DeckSpec) -> str:
    x, y = _emu_x(element.x), _emu_y(element.y)
    w, h = _emu_x(element.w), _emu_y(element.h)
    color = _hex(element.style.color or deck.theme.ink)
    align = {"center": "ctr", "right": "r"}.get(str(element.style.align).lower(), "l")
    bold = ' b="1"' if element.style.bold else ""
    italic = ' i="1"' if element.style.italic else ""
    underline = ' u="sng"' if element.style.underline else ""
    spacing = f' spc="{int(round(float(element.style.letter_spacing or 0.0) * 1000))}"' if element.style.letter_spacing else ""
    line_height = max(0.8, min(2.4, float(element.style.line_height or 1.2)))
    line_spacing = f'<a:lnSpc><a:spcPct val="{int(round(line_height * 100000))}"/></a:lnSpc>'
    font = element.style.font_family or deck.theme.font_family
    paragraphs = str(element.text or "").splitlines() or [""]
    para_xml = "".join(
        f'<a:p><a:pPr algn="{align}">{line_spacing}</a:pPr><a:r><a:rPr lang="ko-KR" sz="{_pt100(element.style.font_size)}"{bold}{italic}{underline}{spacing}><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="{_x(font)}"/><a:ea typeface="{_x(font)}"/></a:rPr><a:t>{_x(line)}</a:t></a:r></a:p>'
        for line in paragraphs
    )
    fill_xml = ""
    if element.style.fill:
        fill_xml = f'<a:solidFill><a:srgbClr val="{_hex(element.style.fill)}"/></a:solidFill>'
    return f"""
      <p:sp>
        <p:nvSpPr><p:cNvPr id="{shape_id}" name="{_x(element.name or 'Text')}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>{fill_xml}<a:ln w="0"><a:noFill/></a:ln></p:spPr>
        <p:txBody><a:bodyPr wrap="square" anchor="t"/><a:lstStyle/>{para_xml}</p:txBody>
      </p:sp>
"""


def _table_cells(element: SlideElement) -> tuple[int, int, list[list[str]]]:
    rows = max(1, int(element.metadata.get("rows", 3) or 3))
    cols = max(1, int(element.metadata.get("cols", 3) or 3))
    raw_cells = element.metadata.get("cells")
    cells: list[list[str]] = []
    if isinstance(raw_cells, list):
        for row in raw_cells[:rows]:
            if isinstance(row, list):
                cells.append([str(cell) for cell in row[:cols]])
    while len(cells) < rows:
        cells.append([])
    for row_index, row in enumerate(cells):
        while len(row) < cols:
            row.append(f"Cell {row_index + 1}-{len(row) + 1}")
    return rows, cols, cells


def _table_cell_xml(
    text: str,
    *,
    width: int,
    height: int,
    fill: str,
    color: str,
    font: str,
    font_size: int,
    bold: bool = False,
) -> str:
    bold_xml = ' b="1"' if bold else ""
    return f"""
          <a:tc>
            <a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="ko-KR" sz="{_pt100(font_size)}"{bold_xml}><a:solidFill><a:srgbClr val="{_hex(color)}"/></a:solidFill><a:latin typeface="{_x(font)}"/><a:ea typeface="{_x(font)}"/></a:rPr><a:t>{_x(text)}</a:t></a:r></a:p></a:txBody>
            <a:tcPr marL="91440" marR="91440" marT="45720" marB="45720"><a:solidFill><a:srgbClr val="{_hex(fill)}"/></a:solidFill></a:tcPr>
          </a:tc>
"""


def _table_xml(shape_id: int, element: SlideElement, deck: DeckSpec) -> str:
    x, y = _emu_x(element.x), _emu_y(element.y)
    w, h = _emu_x(element.w), _emu_y(element.h)
    rows, cols, cells = _table_cells(element)
    col_w = max(1, int(w / cols))
    row_h = max(1, int(h / rows))
    header = bool(element.metadata.get("header", True))
    header_fill = str(element.metadata.get("header_fill") or "#EAF1FF")
    body_fill = str(element.metadata.get("body_fill") or element.style.fill or "#FFFFFF")
    grid_color = _hex(str(element.metadata.get("grid_color") or element.style.stroke or "#B8C2D6"))
    font = element.style.font_family or deck.theme.font_family
    color = element.style.color or deck.theme.ink
    grid_cols = "".join(f'<a:gridCol w="{col_w}"/>' for _ in range(cols))
    table_rows: list[str] = []
    for row_index, row in enumerate(cells):
        fill = header_fill if header and row_index == 0 else body_fill
        cell_xml = "".join(
            _table_cell_xml(
                format_formula_value(cell, cells=cells),
                width=col_w,
                height=row_h,
                fill=fill,
                color=color,
                font=font,
                font_size=int(element.style.font_size or 16),
                bold=bool(header and row_index == 0),
            )
            for cell in row
        )
        table_rows.append(f'<a:tr h="{row_h}">{cell_xml}</a:tr>')
    return f"""
      <p:graphicFrame>
        <p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="{_x(element.name or 'Table')}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
        <p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></p:xfrm>
        <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">
          <a:tbl>
            <a:tblPr firstRow="{1 if header else 0}" bandRow="1"><a:tableStyleId>{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}</a:tableStyleId></a:tblPr>
            <a:tblGrid>{grid_cols}</a:tblGrid>
            {''.join(table_rows)}
          </a:tbl>
        </a:graphicData></a:graphic>
      </p:graphicFrame>
"""


def _line_xml(shape_id: int, element: SlideElement, deck: DeckSpec) -> str:
    x, y = _emu_x(element.x), _emu_y(element.y + element.h * 0.5)
    w, h = _emu_x(element.w), max(1, _emu_y(element.h * 0.01))
    line = _hex(element.style.stroke or element.style.color or deck.theme.accent)
    line_width = max(12700, int(round(float(element.style.stroke_width or 2) * 12700)))
    return f"""
      <p:sp>
        <p:nvSpPr><p:cNvPr id="{shape_id}" name="{_x(element.name or 'Line')}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="line"><a:avLst/></a:prstGeom><a:noFill/><a:ln w="{line_width}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln></p:spPr>
      </p:sp>
"""


def _chart_xml(shape_id: int, element: SlideElement, deck: DeckSpec) -> str:
    base = shape_id * 1000
    background = SlideElement(
        id=f"{element.id}-bg",
        kind="shape",
        name=element.name or "Chart",
        x=element.x,
        y=element.y,
        w=element.w,
        h=element.h,
        style=element.style,
    )
    shapes = [_shape_xml(shape_id, background, deck)]
    raw_labels = element.metadata.get("labels") or ["A", "B", "C", "D"]
    raw_values = element.metadata.get("values") or [32, 58, 44, 72]
    labels = [str(label) for label in raw_labels] if isinstance(raw_labels, list) else ["A", "B", "C", "D"]
    source_values = list(raw_values) if isinstance(raw_values, list) else [32.0, 58.0, 44.0, 72.0]
    cells = [[labels[index] if index < len(labels) else f"Item {index + 1}", value] for index, value in enumerate(source_values)]
    values: list[float] = []
    for value in source_values:
        try:
            values.append(evaluate_numeric_formula(value, cells=cells))
        except Exception:
            values.append(0.0)
    if not values:
        values = [32.0, 58.0, 44.0, 72.0]
    count = max(1, min(len(labels), len(values), 8))
    labels = labels[:count] or ["A"]
    values = values[:count] or [1.0]
    max_value = max(1.0, max(values))
    pad_x = element.w * 0.10
    pad_y = element.h * 0.14
    plot_x = element.x + pad_x
    plot_y = element.y + pad_y
    plot_w = max(0.01, element.w - pad_x * 2.0)
    plot_h = max(0.01, element.h - pad_y * 2.0)
    slot = plot_w / count
    gap = slot * 0.18
    bar_w = max(0.004, slot - gap * 2.0)
    bar_fill = str(element.metadata.get("bar_fill") or deck.theme.accent)
    for index, value in enumerate(values):
        bar_h = plot_h * max(0.0, value) / max_value
        bar = SlideElement(
            id=f"{element.id}-bar-{index}",
            kind="shape",
            name=f"Bar {index + 1}",
            x=plot_x + index * slot + gap,
            y=plot_y + plot_h - bar_h,
            w=bar_w,
            h=bar_h,
            style=type(element.style)(fill=bar_fill, stroke=bar_fill, stroke_width=0.0),
        )
        shapes.append(_shape_xml(base + 10 + index, bar, deck))
        label = SlideElement.text_box(
            f"{element.id}-label-{index}",
            labels[index],
            x=plot_x + index * slot,
            y=element.y + element.h - pad_y * 0.82,
            w=slot,
            h=min(0.035, element.h * 0.10),
            font_size=10,
            color=deck.theme.muted,
            align="center",
        )
        shapes.append(_text_xml(base + 110 + index, label, deck))
    x_axis = SlideElement.line(f"{element.id}-x-axis", x=plot_x, y=plot_y + plot_h, w=plot_w, h=0.002)
    x_axis.style.stroke = "#9AA7BA"
    x_axis.style.stroke_width = 1.0
    shapes.append(_line_xml(base + 300, x_axis, deck))
    y_axis = SlideElement.line(f"{element.id}-y-axis", x=plot_x, y=plot_y, w=0.002, h=plot_h)
    y_axis.style.stroke = "#9AA7BA"
    y_axis.style.stroke_width = 1.0
    shapes.append(_line_xml(base + 301, y_axis, deck))
    return "".join(shapes)


def _picture_xml(shape_id: int, element: SlideElement, rel_id: str) -> str:
    x, y = _emu_x(element.x), _emu_y(element.y)
    w, h = _emu_x(element.w), _emu_y(element.h)
    return f"""
      <p:pic>
        <p:nvPicPr><p:cNvPr id="{shape_id}" name="{_x(element.name or Path(element.source_path).name)}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
        <p:blipFill><a:blip r:embed="{_x(rel_id)}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
        <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:ln w="0"><a:noFill/></a:ln></p:spPr>
      </p:pic>
"""


def _animation_effect_xml(index: int, shape_id: int, element: SlideElement) -> str:
    payload = animation_payload(element.animation)
    effect = str(payload["in_animation"])
    if effect == "none":
        return ""
    effect_filter = {
        "appear": "",
        "fade_in": "fade",
        "fade_out": "fade",
        "move": "fly",
        "scale": "zoom",
    }.get(effect, "fade")
    transition = "out" if effect == "fade_out" else "in"
    delay = max(0, int(payload["start_ms"]))
    dur = max(1, int(payload["duration_ms"]))
    par_id = 100 + index * 3
    effect_id = par_id + 1
    behavior_id = par_id + 2
    trigger = str(payload["trigger"])
    if trigger == "on_click":
        start_cond = f'<p:stCondLst><p:cond evt="onClick" delay="{delay}"><p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl></p:cond></p:stCondLst>'
    else:
        start_cond = f'<p:stCondLst><p:cond delay="{delay}"/></p:stCondLst>'
    if effect == "appear":
        return f"""
          <p:par>
            <p:cTn id="{par_id}" fill="hold">{start_cond}<p:childTnLst>
              <p:set>
                <p:cBhvr><p:cTn id="{behavior_id}" dur="1" fill="hold"/><p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>
                <p:to><p:strVal val="visible"/></p:to>
              </p:set>
            </p:childTnLst></p:cTn>
          </p:par>
"""
    return f"""
          <p:par>
            <p:cTn id="{par_id}" fill="hold">{start_cond}<p:childTnLst>
              <p:animEffect transition="{transition}" filter="{_x(effect_filter)}">
                <p:cBhvr><p:cTn id="{effect_id}" dur="{dur}" fill="hold"/><p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl></p:cBhvr>
              </p:animEffect>
            </p:childTnLst></p:cTn>
          </p:par>
"""


def _timing_xml(animations: list[str], animated_shape_ids: list[int]) -> str:
    if not animations:
        return ""
    build_list = "".join(f'<p:bldP spid="{shape_id}" grpId="0"/>' for shape_id in animated_shape_ids)
    return f"""
  <p:timing>
    <p:tnLst>
      <p:par>
        <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
          <p:childTnLst>{''.join(animations)}
          </p:childTnLst>
        </p:cTn>
      </p:par>
    </p:tnLst>
    <p:bldLst>{build_list}</p:bldLst>
  </p:timing>
"""


def _slide_xml(deck: DeckSpec, slide: SlideSpec, shapes: list[str], animations: list[str], animated_shape_ids: list[int]) -> str:
    bg = _hex(slide.background or deck.theme.background)
    timing = _timing_xml(animations, animated_shape_ids)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="{bg}"/></a:solidFill></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name="Group 1"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      {''.join(shapes)}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
  {timing}
</p:sld>
"""


def _media_elements(deck: DeckSpec) -> list[Path]:
    media: list[Path] = []
    for slide in deck.slides:
        for element in slide.elements:
            if element.kind in {"image", "timeline_moment", "screen_capture"} and element.source_path:
                path = Path(element.source_path)
                if path.exists():
                    media.append(path)
    return media


def write_pptx(deck: DeckSpec, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    media = _media_elements(deck)
    rel_type_base = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types(len(deck.slides), media))
        zf.writestr("_rels/.rels", _rels_xml([
            ("rId1", f"{rel_type_base}/officeDocument", "ppt/presentation.xml"),
            ("rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"),
            ("rId3", f"{rel_type_base}/extended-properties", "docProps/app.xml"),
        ]))
        zf.writestr("docProps/core.xml", _core_xml(deck))
        zf.writestr("docProps/app.xml", _app_xml(len(deck.slides)))
        zf.writestr("ppt/presentation.xml", _presentation_xml(len(deck.slides)))
        pres_rels = [("rId1", f"{rel_type_base}/slideMaster", "slideMasters/slideMaster1.xml")]
        for idx in range(1, len(deck.slides) + 1):
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
        zf.writestr("ppt/theme/theme1.xml", _theme_xml(deck))

        media_index = 1
        for idx, slide in enumerate(deck.slides, start=1):
            shapes: list[str] = []
            animation_entries: list[tuple[SlideElement, int]] = []
            rels = [("rId1", f"{rel_type_base}/slideLayout", "../slideLayouts/slideLayout1.xml")]
            shape_id = 2
            overlay_elements = slide_overlay_elements(deck, slide.id, slide_index=idx, slide_count=len(deck.slides))
            for element in sorted([*slide.elements, *overlay_elements], key=lambda row: int(row.z_index)):
                if not element.visible:
                    continue
                if animation_is_active(element.animation):
                    animation_entries.append((element, shape_id))
                media_path = Path(element.source_path) if element.source_path else None
                if element.kind in {"image", "timeline_moment", "screen_capture"} and media_path and media_path.exists():
                    ext = media_path.suffix.lower() or ".png"
                    media_name = f"image{media_index}{ext}"
                    media_index += 1
                    rel_id = f"rId{len(rels) + 1}"
                    zf.write(media_path, f"ppt/media/{media_name}")
                    rels.append((rel_id, f"{rel_type_base}/image", f"../media/{media_name}"))
                    shapes.append(_picture_xml(shape_id, element, rel_id))
                elif element.kind in {"text", "typography_actor"}:
                    shapes.append(_text_xml(shape_id, element, deck))
                elif element.kind == "table":
                    shapes.append(_table_xml(shape_id, element, deck))
                elif element.kind == "line":
                    shapes.append(_line_xml(shape_id, element, deck))
                elif element.kind == "chart":
                    shapes.append(_chart_xml(shape_id, element, deck))
                else:
                    shapes.append(_shape_xml(shape_id, element, deck))
                    if element.name or element.kind:
                        label = SlideElement.text_box(
                            f"{element.id}-label",
                            element.name or element.kind.replace("_", " ").title(),
                            x=element.x + element.w * 0.08,
                            y=element.y + element.h * 0.42,
                            w=element.w * 0.84,
                            h=min(0.12, element.h * 0.22),
                            font_size=18,
                            bold=True,
                            color=element.style.color or deck.theme.ink,
                            align="center",
                        )
                        shapes.append(_text_xml(shape_id + 1000, label, deck))
                shape_id += 1
            animations: list[str] = []
            animated_shape_ids: list[int] = []
            for anim_index, (element, element_shape_id) in enumerate(
                sorted(animation_entries, key=lambda row: animation_sequence_sort_key(row[0])),
                start=1,
            ):
                animations.append(_animation_effect_xml(anim_index, element_shape_id, element))
                animated_shape_ids.append(element_shape_id)
            zf.writestr(f"ppt/slides/slide{idx}.xml", _slide_xml(deck, slide, shapes, animations, animated_shape_ids))
            zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", _rels_xml(rels))
    return target


__all__ = ["write_pptx"]
