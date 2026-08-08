import os, sys, time, collections
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
ROOT="E:/ClaudeCodeApp/GifCam"; sys.path.insert(0,ROOT)
tot=collections.Counter(); cnt=collections.Counter()
def wrap(mod,name,label):
    m=__import__("app."+mod,fromlist=["x"]); orig=getattr(m,name)
    def f(*a,**k):
        t=time.perf_counter()
        try: return orig(*a,**k)
        finally: tot[label]+=(time.perf_counter()-t)*1000; cnt[label]+=1
    setattr(m,name,f)
wrap("painter_ui_components","resolve_ui_component_document","  component")
wrap("painter_ui_responsive","resolve_ui_responsive_document","  responsive")
wrap("painter_ui_themes","resolve_ui_theme_object","  theme_row")
wrap("painter_ui_themes","resolve_ui_theme_document","THEME")
wrap("painter_ui_layout_diagnostics","diagnose_ui_layout","DIAG")
wrap("painter_ui_document","validate_ui_document","VALIDATE")
wrap("painter_ui_constraints","resolve_ui_constraints","CONSTRAINTS")
from PySide6.QtWidgets import QApplication
from app.actions.registry import ActionRegistry
from app.drawing import PaintDialog, create_blank_paint_pixmap
from app.painter_ui_figma import import_figma_json
from app.painter_ui_document import add_ui_object
QApplication.instance() or QApplication([])
d=PaintDialog(background_pixmap=create_blank_paint_pixmap(1440,900,"transparent"),initial_strokes=[],time_ms=0,standalone=True)
ActionRegistry(owner=d).execute("paint.ui.workspace.set",{"mode":"ui_design"})
doc,_=import_figma_json(ROOT+"/tmp/auto_layout_playground.json",image_dir=None)
d._painter_ui_document=doc
doc,row=add_ui_object(doc,kind="rectangle",name="probe",x=40,y=40,width=120,height=48)
d._painter_ui_document=doc
d._move_painter_ui_object(str(row["id"]),50.0,60.0)
tot.clear(); cnt.clear()
t=time.perf_counter(); d._move_painter_ui_object(str(row["id"]),77.0,88.0); el=(time.perf_counter()-t)*1000
print(f"\nmove {el:.0f} ms")
for k,v in tot.most_common(12): print(f"  {v:8.0f} ms  x{cnt[k]:<6d} {k}")
