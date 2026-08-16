import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.painter_ui_text_layout import text_content_geometry
style = {"font_size": 72.0, "line_height": 80.0, "font_family": "Inter", "font_weight": 700}
w, h = text_content_geometry("Auto Layout ", style, mode="auto_height", width=562.0, height=160.0)
print("title ->", w, h)
style2 = {"font_size": 24.0, "line_height": 32.0, "font_family": "Inter", "font_weight": 400}
w2, h2 = text_content_geometry(
    "Create layouts, frames, and components for more flexible and responsive designs.",
    style2, mode="auto_height", width=454.0, height=64.0,
)
print("desc ->", w2, h2)
