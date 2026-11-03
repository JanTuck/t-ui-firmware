"""Export LVGL frames with optional 8-pixel alignment grids (requires Pillow)."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument("directory", type=Path)
args = parser.parse_args()
for path in args.directory.glob("*.ppm"):
    original = Image.open(path)
    original.save(path.with_suffix(".png"))
    scaled = original.resize((640, 480), Image.Resampling.NEAREST).convert("RGBA")
    overlay = Image.new("RGBA", scaled.size)
    draw = ImageDraw.Draw(overlay)
    for x in range(0, 640, 16):
        draw.line((x, 0, x, 479), fill=(100, 210, 255, 45))
    for y in range(0, 480, 16):
        draw.line((0, y, 639, y), fill=(100, 210, 255, 45))
    Image.alpha_composite(scaled, overlay).save(path.with_name(path.stem + "-grid.png"))
