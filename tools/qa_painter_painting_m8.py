from __future__ import annotations

import hashlib
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1.5")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_required_tests(*, skip: bool = False) -> dict[str, object]:
    if skip:
        return {
            "passed": False,
            "skipped": True,
            "reason": "--skip-tests cannot produce a passing readiness report",
            "commands": [],
        }
    painter_tests = sorted(
        str(path) for path in (ROOT / "tests").glob("test_painter_*.py")
        if not path.name.startswith("test_painter_ui")
    )
    commands = [
        [sys.executable, "-m", "pytest", *painter_tests, "-q"],
        [
            sys.executable, "-m", "pytest",
            str(ROOT / "tests" / "test_editor_architecture_rules.py"),
            str(ROOT / "tests" / "test_debug_capture_boundary.py"),
            "-q",
        ],
    ]
    rows = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        rows.append({
            "command": command,
            "returncode": int(completed.returncode),
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-2000:],
        })
        if completed.returncode:
            break
    return {
        "passed": bool(len(rows) == len(commands) and all(not row["returncode"] for row in rows)),
        "skipped": False,
        "commands": rows,
    }


def _pil_hash(image) -> str:
    return hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()


def _qimage(width: int, height: int, painter_fn):
    from PySide6.QtGui import QImage, QPainter

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter_fn(painter, width, height)
    painter.end()
    return image


def _character_layers(dialog):
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QLinearGradient, QPainterPath, QPen

    width, height = dialog._canvas_document_size
    base = _qimage(width, height, lambda p, w, h: p.fillRect(0, 0, w, h, QColor("#24334A")))
    dialog._paint_layers[0].name = "Character backdrop"
    dialog._set_paint_layer_raster(dialog._paint_layers[0].layer_id, base)

    def flats(p, w, h):
        halo = QLinearGradient(0, h * .15, 0, h * .9)
        halo.setColorAt(0, QColor("#6DC7C8")); halo.setColorAt(1, QColor("#35537C"))
        p.setBrush(halo); p.setPen(QPen(QColor("#11223A"), 5))
        p.drawEllipse(QRectF(w * .31, h * .13, w * .38, h * .44))
        p.setBrush(QColor("#E9B18D")); p.drawEllipse(QRectF(w * .39, h * .21, w * .22, h * .28))
        p.setBrush(QColor("#E45A62"));
        body = QPainterPath(); body.moveTo(w*.28, h*.88); body.cubicTo(w*.3,h*.57,w*.7,h*.57,w*.72,h*.88); body.closeSubpath(); p.drawPath(body)
        p.setBrush(QColor("#F2C04F")); p.drawEllipse(QRectF(w*.46,h*.58,w*.08,h*.1))
    flat = dialog._new_paint_layer("Flat colors")
    dialog._set_paint_layer_raster(flat.layer_id, _qimage(width, height, flats))

    def line(p, w, h):
        pen = QPen(QColor("#18202E"), max(2, w//180)); pen.setCapStyle(pen.capStyle().RoundCap); p.setPen(pen)
        p.drawArc(QRectF(w*.4,h*.28,w*.08,h*.07), 10*16, 160*16)
        p.drawArc(QRectF(w*.52,h*.28,w*.08,h*.07), 10*16, 160*16)
        p.drawLine(QPointF(w*.46,h*.43), QPointF(w*.54,h*.43))
        p.drawLine(QPointF(w*.35,h*.7), QPointF(w*.46,h*.75)); p.drawLine(QPointF(w*.65,h*.7), QPointF(w*.54,h*.75))
    lines = dialog._new_paint_layer("Line art")
    dialog._set_paint_layer_raster(lines.layer_id, _qimage(width, height, line))

    def render(p, w, h):
        gradient = QLinearGradient(w*.35,h*.25,w*.64,h*.52)
        gradient.setColorAt(0, QColor(255,255,255,150)); gradient.setColorAt(1, QColor(40,50,90,0))
        p.setPen(QPen(QColor(255,255,255,100), 2)); p.setBrush(gradient)
        p.drawEllipse(QRectF(w*.34,h*.17,w*.32,h*.4))
        p.setBrush(QColor(16,24,42,100)); p.drawEllipse(QRectF(w*.55,h*.35,w*.08,h*.13))
    render_layer = dialog._new_paint_layer("Render light")
    dialog._set_paint_layer_raster(render_layer.layer_id, _qimage(width, height, render))
    dialog._set_layer_clipping(render_layer.layer_id, True)
    dialog.canvas.set_selection_snapshot([(0.3,0.12),(0.7,0.12),(0.7,0.92),(0.3,0.92)])
    mask_created = dialog._create_layer_mask("selection", render_layer.layer_id)
    transformed = dialog._apply_selection_transform(target="selected_pixels", translate_x=4.0, translate_y=2.0)
    group = dialog._new_paint_layer_group("Character", layer_ids=[flat.layer_id, lines.layer_id, render_layer.layer_id])
    dialog._select_paint_layer_by_id(render_layer.layer_id)
    return {
        "line": lines.layer_id, "flat": flat.layer_id, "render": render_layer.layer_id,
        "group": group.layer_id, "clipping": render_layer.clipping,
        "mask": bool(mask_created and render_layer.mask_enabled), "selection_transform": transformed,
    }


def _background_layers(dialog):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QLinearGradient, QPen, QPolygonF

    width, height = dialog._canvas_document_size
    def thumb(p,w,h):
        sky=QLinearGradient(0,0,0,h); sky.setColorAt(0,QColor("#172B4C")); sky.setColorAt(1,QColor("#E59662")); p.fillRect(0,0,w,h,sky)
        p.setBrush(QColor("#14202E")); p.setPen(QPen(QColor("#14202E"),1)); p.drawPolygon(QPolygonF([QPointF(0,h*.7),QPointF(w*.22,h*.38),QPointF(w*.42,h*.72),QPointF(w*.67,h*.3),QPointF(w,h*.68),QPointF(w,h),QPointF(0,h)]))
    dialog._paint_layers[0].name="Thumbnail"; dialog._set_paint_layer_raster(dialog._paint_layers[0].layer_id,_qimage(width,height,thumb))
    def block(p,w,h):
        p.setPen(QPen(QColor("#3E5661"), max(2,w//160))); p.setBrush(QColor("#31434C"))
        p.drawRect(int(w*.12),int(h*.48),int(w*.22),int(h*.32)); p.drawRect(int(w*.66),int(h*.4),int(w*.23),int(h*.4))
        p.setBrush(QColor("#C27652")); p.drawPolygon(QPolygonF([QPointF(0,h),QPointF(w*.43,h*.65),QPointF(w*.57,h*.65),QPointF(w,h),QPointF(0,h)]))
    block_layer=dialog._new_paint_layer("Block-in"); dialog._set_paint_layer_raster(block_layer.layer_id,_qimage(width,height,block))
    def detail(p,w,h):
        p.setPen(QPen(QColor(245,214,151,175), max(1,w//320)))
        for i in range(13):
            x=w*(.08+i*.071); p.drawLine(QPointF(x,h*.52),QPointF(w*.5,h*.66))
        p.setBrush(QColor("#F7D071")); p.setPen(QPen(QColor("#FFF1B3"),2)); p.drawEllipse(QPointF(w*.78,h*.18),w*.055,w*.055)
    detail_layer=dialog._new_paint_layer("Detail"); dialog._set_paint_layer_raster(detail_layer.layer_id,_qimage(width,height,detail))
    perspective=dialog._set_perspective_guide_options(enabled=True,horizon=.62,left_x=.04,left_y=.62,right_x=.96,right_y=.62)
    return {"thumbnail":dialog._paint_layers[0].layer_id,"block_in":block_layer.layer_id,"detail":detail_layer.layer_id,"perspective":perspective}


def _material_layers(dialog):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QLinearGradient, QPen
    from app.drawing import Stroke

    width,height=dialog._canvas_document_size
    dialog._paint_layers[0].name="Dark ground"; dialog._set_paint_layer_raster(dialog._paint_layers[0].layer_id,_qimage(width,height,lambda p,w,h:p.fillRect(0,0,w,h,QColor("#201D25"))))
    material=dialog._new_material_paint_layer("Impasto pigment")
    def pigment(p,w,h):
        p.setPen(QPen(QColor("#F3C969"),max(8,w//35)))
        for i in range(16):
            y=h*(.18+i*.04); p.drawLine(QPointF(w*.18,y),QPointF(w*(.78+(i%3)*.035),y+h*.09))
        shine=QLinearGradient(w*.2,0,w*.8,0); shine.setColorAt(0,QColor(205,67,52,220)); shine.setColorAt(.5,QColor(247,186,66,230)); shine.setColorAt(1,QColor(47,135,132,220)); p.fillRect(int(w*.18),int(h*.3),int(w*.64),int(h*.42),shine)
    dialog._set_paint_layer_raster(material.layer_id,_qimage(width,height,pigment))
    dialog._set_wet_canvas_settings({"enabled":True,"wetness":.7,"flow":.6,"drying_seconds":20},layer_id=material.layer_id)
    tablet=Stroke(points=[(.12,.82),(.3,.68),(.49,.8),(.7,.62),(.9,.78)],color=(247,225,166),opacity=230,width_px=26,brush_style="bristle_oil",brush_dynamics={"enabled":True,"mode":"mixer","buildup":65,"texture_strength":55},point_pressure=[.12,.35,.78,1,.52],point_tilt_x=[0,.2,.45,-.25,-.4],point_tilt_y=[0,-.3,.1,.5,.2],point_rotation=[.05,.25,.5,.7,.95],point_tangential_pressure=[0,.2,.4,.75,1],layer_id=material.layer_id)
    dialog.canvas.add_stroke_direct(tablet)
    dialog._sync_canvas_layer_view()
    return material, tablet


def _capture(dialog, path: Path, width: int, height: int):
    from PySide6.QtWidgets import QApplication
    dialog.resize(width,height); dialog.show(); QApplication.processEvents()
    pixmap=dialog.grab(); ok=pixmap.save(str(path),"PNG")
    return {"path":str(path.resolve()),"saved":bool(ok),"logical_size":[width,height],"pixel_size":[pixmap.width(),pixmap.height()],"device_pixel_ratio":float(pixmap.devicePixelRatio())}


def _save_exchange(dialog, root: Path, stem: str):
    from PySide6.QtWidgets import QApplication

    # Stroke widths are display-space inputs and are normalized back to the
    # document by the compositor.  Keep both sides at the same viewport so the
    # comparison measures persistence rather than a different zoom geometry.
    dialog.resize(1100, 720); dialog.show(); QApplication.processEvents()
    native=root/f"{stem}.tspaint"; save=dialog.save_document_to_path(native)
    original=dialog._painter_composite_pil(include_background=False)
    reopened=type(dialog)(background_pixmap=dialog._bg_pixmap_source.copy(0,0,8,8),initial_strokes=[],time_ms=0,standalone=True)
    reopened.resize(1100, 720); reopened.show(); QApplication.processEvents()
    load=reopened.open_document_from_path(native); QApplication.processEvents()
    after=reopened._painter_composite_pil(include_background=False)
    png=dialog.export_document_to_path(root/f"{stem}.png",format_name="png",include_background=False)
    tiff=dialog.export_document_to_path(root/f"{stem}.tiff",format_name="tiff",include_background=False)
    psd=dialog.export_document_to_path(root/f"{stem}.psd",format_name="psd",include_background=False,bake_unsupported=True)
    parity=_pil_hash(original)==_pil_hash(after)
    reopened_strokes=reopened.canvas.embedded_strokes()
    input_roundtrip=all(
        len(getattr(row, "point_pressure", [])) == len(getattr(row, "points", []))
        and len(getattr(row, "point_rotation", [])) == len(getattr(row, "points", []))
        for row in reopened_strokes
    )
    reopened.close()
    return {"native":str(native.resolve()),"save":save,"load":load,"pixel_parity":parity,"input_roundtrip":input_roundtrip,"png":png,"tiff":tiff,"psd":psd}


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate Painter M8 automated-baseline evidence")
    parser.add_argument("--skip-tests", action="store_true", help="Generate artifacts only; readiness will fail")
    args = parser.parse_args()
    test_evidence = _run_required_tests(skip=bool(args.skip_tests))
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from app.drawing import DrawingCanvas, PaintDialog, Stroke, create_blank_paint_pixmap
    from app.painter_autosave import discard_recovery_snapshot, save_recovery_snapshot
    from app.painter_large_canvas import LargeCanvasRuntime
    from app.painter_product_readiness import evaluate_painting_readiness, painting_known_limitations, painting_support_matrix
    from app.painter_evidence_contract import evidence_record

    app=QApplication.instance() or QApplication([])
    root=ROOT/"debugCapture"/"painter"/"painting_m8"; root.mkdir(parents=True,exist_ok=True)
    character=PaintDialog(background_pixmap=create_blank_paint_pixmap(640,480,"transparent"),initial_strokes=[],time_ms=0,standalone=True)
    character_features=_character_layers(character)
    reference=_qimage(240,160,lambda p,w,h:(p.fillRect(0,0,w,h,QColor("#EEE3CC")),p.setPen(QColor("#8A5B42")),p.drawLine(20,130,210,30)))
    reference_path=root/"reference_board_source.png"; reference.save(str(reference_path),"PNG")
    reference_added=character._add_reference_image_path(str(reference_path),name="M8 palette reference")
    character_exchange=_save_exchange(character,root,"character_complete")
    capture_760=_capture(character,root/"ui_character_760x560.png",760,560)
    capture_1080=_capture(character,root/"ui_character_1920x1080.png",1920,1080)

    background=PaintDialog(background_pixmap=create_blank_paint_pixmap(800,450,"transparent"),initial_strokes=[],time_ms=0,standalone=True)
    background_features=_background_layers(background); background_exchange=_save_exchange(background,root,"background_complete")
    background_capture=_capture(background,root/"ui_background.png",1100,720)

    material=PaintDialog(background_pixmap=create_blank_paint_pixmap(640,480,"transparent"),initial_strokes=[],time_ms=0,standalone=True)
    material_layer,tablet_stroke=_material_layers(material); material_exchange=_save_exchange(material,root,"material_impasto")
    material_capture=_capture(material,root/"ui_material_impasto.png",1100,720)

    recovery_root=root/"recovery"
    recovery_row=save_recovery_snapshot("painting-m8-crash",character._painter_document_payload(),source_path=str(root/"unsaved_character.tspaint"),background_png=character._painter_background_png_bytes(),layer_raster_pngs=character._painter_layer_raster_png_bytes(),selection_mask_png=character._painter_selection_mask_png_bytes(),root=recovery_root)
    recovered=PaintDialog(background_pixmap=create_blank_paint_pixmap(8,8,"transparent"),initial_strokes=[],time_ms=0,standalone=True)
    recovery_report=recovered._restore_painter_recovery_snapshot(recovery_row)
    recovery_parity=_pil_hash(character._painter_composite_pil(include_background=False))==_pil_hash(recovered._painter_composite_pil(include_background=False))
    discard_recovery_snapshot("painting-m8-crash",root=recovery_root)

    four_k=QImage(3840,2160,QImage.Format.Format_ARGB32_Premultiplied); four_k.fill(QColor("#294A61"))
    runtime=LargeCanvasRuntime(tile_size=256,tile_budget_mb=96,undo_budget_mb=64)
    started=time.perf_counter(); initial_tiles=runtime.update_layer("4k",four_k)
    for index in range(240):
        x=(index*137)%3830; y=(index*83)%2150; four_k.setPixelColor(x,y,QColor(240,index%255,80)); runtime.update_layer("4k",four_k,dirty_rect=(x,y,1,1))
    tile_stress_ms=(time.perf_counter()-started)*1000
    stroke_image=QImage(1920,1080,QImage.Format.Format_ARGB32_Premultiplied); stroke_image.fill(0)
    long_stroke=Stroke(points=[(i/2999.0,.5+.22*((i%67)/66-.5)) for i in range(3000)],width_px=20,brush_style="bristle_oil",brush_dynamics={"enabled":True,"buildup":45,"scatter":10,"scatter_count":2},point_pressure=[.35+(i%31)/50 for i in range(3000)])
    from PySide6.QtGui import QPainter
    p=QPainter(stroke_image); stroke_started=time.perf_counter(); DrawingCanvas._paint_stroke(p,long_stroke,1920,1080); p.end(); stroke_ms=(time.perf_counter()-stroke_started)*1000
    stroke_painted=stroke_image.pixelColor(960,540).alpha()>0
    stress_passed=bool(initial_tiles["updated_tiles"]==135 and runtime.telemetry()["tiles"]["bounded"] and stroke_painted)

    tablet_roundtrip=material_exchange["input_roundtrip"] and len(tablet_stroke.point_pressure)==5 and len(tablet_stroke.point_rotation)==5
    evidence={
        "character":{"line":character_features["line"],"flat":character_features["flat"],"render":character_features["render"]},
        "background":{"thumbnail":background_features["thumbnail"],"block_in":background_features["block_in"],"detail":background_features["detail"]},
        "material_impasto":{"material_paint":material_layer.layer_type=="material","impasto":bool(tablet_stroke.brush_dynamics)},
        "editing_workflow":{"reference":reference_added,"perspective":background_features["perspective"].get("enabled"),"selection_transform":character_features["selection_transform"],"group":character_features["group"],"clipping":character_features["clipping"],"mask":character_features["mask"]},
        "exchange_recovery":{"tspaint":character_exchange["pixel_parity"],"recovery":recovery_parity,"png":Path(character_exchange["png"]["path"]).is_file(),"tiff":Path(character_exchange["tiff"]["path"]).is_file(),"psd":all(Path(row["psd"]["path"]).is_file() and bool((row["psd"].get("composite_parity") or {}).get("within_tolerance")) for row in (character_exchange,background_exchange,material_exchange))},
        "display_input":{"offscreen_window_760x560":capture_760["saved"],"offscreen_window_1080p":capture_1080["saved"],"simulated_high_dpi_layout":capture_760["device_pixel_ratio"]>1.0 or capture_760["pixel_size"]!=capture_760["logical_size"],"4k_tile_cardinality":initial_tiles["updated_tiles"]==135,"synthetic_tablet_channel_roundtrip":tablet_roundtrip},
        "stress":{"large_stroke_render":stroke_painted,"bounded_tile_cache":runtime.telemetry()["tiles"]["bounded"],"reopen":all(row["pixel_parity"] for row in (character_exchange,background_exchange,material_exchange))},
    }
    workflow_passed=all(
        bool(value)
        for section in evidence.values()
        for value in section.values()
    )
    provenance=[
        evidence_record("m8-offscreen-workflows","synthetic_integration",passed=workflow_passed,producer="tools/qa_painter_painting_m8.py",claims=("automated_functional_baseline",),command="python tools/qa_painter_painting_m8.py",environment={"QT_QPA_PLATFORM":os.environ.get("QT_QPA_PLATFORM"),"QT_SCALE_FACTOR":os.environ.get("QT_SCALE_FACTOR")},artifacts=[root/"ui_character_760x560.png",root/"ui_character_1920x1080.png"]),
        evidence_record("m8-simulated-high-dpi","simulated_environment",passed=bool(evidence["display_input"]["simulated_high_dpi_layout"]),producer="Qt QT_SCALE_FACTOR",environment={"QT_SCALE_FACTOR":os.environ.get("QT_SCALE_FACTOR")},limitations=["Qt documentation defines QT_SCALE_FACTOR as a hardware-independent test override; this is not native monitor evidence."]),
    ]
    readiness=evaluate_painting_readiness(evidence,tests_passed=bool(test_evidence["passed"]),recovery_passed=recovery_parity,stress_passed=stress_passed,evidence_records=provenance)
    report={"schema":"tigerstudio.painter.painting_m8_qa.v4","artifacts":{"root":str(root.resolve()),"captures":[capture_760,capture_1080,background_capture,material_capture],"documents":[character_exchange,background_exchange,material_exchange]},"test_evidence":test_evidence,"evidence":evidence,"provenance":provenance,"recovery":{"report":recovery_report,"pixel_parity":recovery_parity,"cleanup":not any(recovery_root.glob("*"))},"stress":{"canvas":[3840,2160],"initial_tiles":initial_tiles,"dirty_updates":240,"tile_elapsed_ms":round(tile_stress_ms,3),"stroke_points":3000,"stroke_elapsed_ms":round(stroke_ms,3),"stroke_painted":stroke_painted,"telemetry":runtime.telemetry(),"passed":stress_passed,"classification":"correctness_stress_with_raw_timing","performance_threshold_claim":False},"support_matrix":painting_support_matrix(),"known_limitations":list(painting_known_limitations()),"readiness":readiness,"passed":readiness["passed"],"release_ready":readiness["release_ready"]}
    (root/"known_limitations.json").write_text(json.dumps({"support_matrix":report["support_matrix"],"known_limitations":report["known_limitations"]},ensure_ascii=False,indent=2),encoding="utf-8")
    (root/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps({"baseline_passed":report["passed"],"release_ready":report["release_ready"],"classification":readiness["classification"],"evidence":evidence,"stress":report["stress"],"captures":report["artifacts"]["captures"]},ensure_ascii=False,default=str))
    for dialog in (recovered,material,background,character): dialog.close()
    app.processEvents()
    return 0 if report["passed"] else 1


if __name__=="__main__": raise SystemExit(main())
