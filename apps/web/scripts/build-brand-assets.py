"""Erzeugt alle Logo-Dateien der Website aus dem Original-Logo.

Aufruf (aus apps/web):  python scripts/build-brand-assets.py

Quelle:  docs/brand/pathly-logo-original.png (weißer Hintergrund)
Ergebnis:
  public/brand/pathly-logo.png        Wortmarke, dunkel, transparent
  public/brand/pathly-logo-white.png  Wortmarke für dunkle Flächen
  src/app/icon.png, apple-icon.png, favicon.ico   "y"-Pfeil-Signet
  src/app/opengraph-image.png         Vorschaubild für Links (1200×630)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parents[1] / "docs" / "brand" / "pathly-logo-original.png"

PRIMARY = (0x04, 0x4B, 0x39)  # Pathly Grün
SIGNAL = (0x72, 0xC6, 0x13)   # Signalgrün
LIME = (0xCB, 0xF3, 0x9D)
CREAM = (0xF6, 0xF3, 0xB8)
WHITE = (255, 255, 255)

# Position des "y" mit Pfeil im Original (x von–bis), per Spaltenprofil ermittelt
Y_MARK_X = (743, 921)


def to_alpha(img: Image.Image, dark=PRIMARY, accent=SIGNAL) -> Image.Image:
    """Weiß wird transparent; Schrift → Markenfarben (Pfeil grün, Rest dunkel)."""
    src = img.convert("RGB")
    out = Image.new("RGBA", src.size)
    s, o = src.load(), out.load()
    for y in range(src.height):
        for x in range(src.width):
            r, g, b = s[x, y]
            alpha = 255 - min(r, g, b)
            if alpha < 8:
                o[x, y] = (0, 0, 0, 0)
                continue
            # Pfeil: deutlich grüner als die dunkle Schrift
            color = accent if g > 120 and g - r > 50 else dark
            o[x, y] = (*color, min(255, int(alpha * 1.05)))
    return out


def crop(img: Image.Image, pad: int = 6) -> Image.Image:
    left, top, right, bottom = img.getbbox()
    return img.crop((left - pad, top - pad, right + pad, bottom + pad))


def main() -> None:
    original = Image.open(SOURCE)
    brand = ROOT / "public" / "brand"
    app = ROOT / "src" / "app"
    brand.mkdir(parents=True, exist_ok=True)

    logo = crop(to_alpha(original))
    logo.save(brand / "pathly-logo.png", optimize=True)
    crop(to_alpha(original, dark=WHITE)).save(brand / "pathly-logo-white.png", optimize=True)

    # Signet: "y" mit Pfeil, weiß/grün auf Pathly Grün
    mark = crop(to_alpha(original.crop((Y_MARK_X[0], 0, Y_MARK_X[1], original.height)), dark=WHITE), pad=0)
    size = 512
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(icon).rounded_rectangle((0, 0, size - 1, size - 1), radius=112, fill=PRIMARY)
    scale = (size * 0.68) / mark.height
    m = mark.resize((round(mark.width * scale), round(mark.height * scale)), Image.LANCZOS)
    icon.alpha_composite(m, ((size - m.width) // 2, (size - m.height) // 2))
    icon.save(app / "icon.png", optimize=True)
    icon.resize((180, 180), Image.LANCZOS).save(app / "apple-icon.png", optimize=True)
    icon.save(app / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

    # Vorschaubild für Links: Lime-Creme-Schimmer von oben, Logo mittig
    # Schimmer direkt auf Weiß zeichnen – Weichzeichnen über Transparenz erzeugt graue Ränder
    glow = Image.new("RGB", (1200, 630), WHITE)
    d = ImageDraw.Draw(glow)
    d.ellipse((550, -220, 1350, 280), fill=CREAM)
    d.ellipse((150, -380, 1050, 230), fill=LIME)
    og = glow.filter(ImageFilter.GaussianBlur(90)).convert("RGBA")
    w = 640
    l = logo.resize((w, round(logo.height * w / logo.width)), Image.LANCZOS)
    og.alpha_composite(l, ((og.width - l.width) // 2, (og.height - l.height) // 2 + 20))
    og.convert("RGB").save(app / "opengraph-image.png", optimize=True)

    print("Logo-Dateien erzeugt:", logo.size)


if __name__ == "__main__":
    main()
