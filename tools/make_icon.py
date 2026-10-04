"""Writes the app icon (gold tile, dark H) as several pixel-aligned PNG sizes into ui/index.html.
Each size is drawn on whole pixels so the H stays sharp in the taskbar. Run: python tools/make_icon.py"""
import base64, io, re
from pathlib import Path
from PIL import Image, ImageDraw

SIZES = (16, 24, 32, 48, 64, 128, 256)
GOLD, INK = (242, 193, 78, 255), (16, 26, 22, 255)


def icon(s):
    k = 8                                              # supersample only the rounded tile, not the H
    tile = Image.new("L", (s * k, s * k), 0)
    ImageDraw.Draw(tile).rounded_rectangle([0, 0, s * k - 1, s * k - 1], radius=round(s * 0.2 * k), fill=255)
    tile = tile.resize((s, s), Image.LANCZOS)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (s, s), GOLD), mask=tile)
    stem = max(2, round(s * 0.17)); bar = max(2, round(s * 0.15))
    w = round(s * 0.54); h = round(s * 0.6)
    w += (s - w) % 2; h += (s - h) % 2                 # same parity as the tile, so it centres on whole pixels
    x0, y0 = (s - w) // 2, (s - h) // 2
    d = ImageDraw.Draw(img)
    d.rectangle([x0, y0, x0 + stem - 1, y0 + h - 1], fill=INK)
    d.rectangle([x0 + w - stem, y0, x0 + w - 1, y0 + h - 1], fill=INK)
    yb = y0 + (h - bar) // 2
    d.rectangle([x0, yb, x0 + w - 1, yb + bar - 1], fill=INK)
    return img


def main():
    tags = []
    for s in SIZES:
        b = io.BytesIO(); icon(s).save(b, "PNG", optimize=True)
        tags.append(f'<link rel="icon" type="image/png" sizes="{s}x{s}" href="data:image/png;base64,{base64.b64encode(b.getvalue()).decode()}">')
    p = Path(__file__).resolve().parent.parent / "ui" / "index.html"
    t = p.read_text(encoding="utf8")
    t = re.sub(r'(?:<link rel="icon"[^\n]*\n)+', "\n".join(tags) + "\n", t, count=1)
    p.write_text(t, encoding="utf8")
    icon(256).save(Path(__file__).with_name("_icon_preview.png"))


main()
