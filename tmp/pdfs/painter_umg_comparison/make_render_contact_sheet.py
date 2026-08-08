from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
pages = sorted(
    (ROOT / "rendered").glob("page-*.png"),
    key=lambda path: int(path.stem.rsplit("-", 1)[-1]),
)
if len(pages) != 21:
    raise RuntimeError(f"Expected 21 rendered PDF pages, found {len(pages)}")

cell_width = 380
cell_height = 292
label_height = 24
columns = 3
rows = (len(pages) + columns - 1) // columns
sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "#08111F")
draw = ImageDraw.Draw(sheet)
font_path = Path(r"C:\Windows\Fonts\segoeuib.ttf")
font = ImageFont.truetype(str(font_path), 13) if font_path.is_file() else None

for index, page_path in enumerate(pages):
    with Image.open(page_path) as source:
        page = source.convert("RGB")
        page.thumbnail((cell_width - 12, cell_height - label_height - 12))
    x = (index % columns) * cell_width
    y = (index // columns) * cell_height
    image_x = x + (cell_width - page.width) // 2
    image_y = y + label_height + (cell_height - label_height - page.height) // 2
    sheet.paste(page, (image_x, image_y))
    draw.text((x + 8, y + 4), f"Page {index + 1:02d}", fill="#EAF2FF", font=font)
    draw.rounded_rectangle(
        (x + 3, y + 3, x + cell_width - 4, y + cell_height - 4),
        radius=8,
        outline="#2FCEA0",
        width=2,
    )

target = ROOT / "rendered_contact_sheet.png"
sheet.save(target, "PNG")
print(target)
