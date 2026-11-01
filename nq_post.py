# NQ Trader's Instagram post generator
# Usage: python3 nq_post.py spec.json out.jpg
# spec: {"palette": "<name>", "category": "...", "title": "...", "subtitle": "...",
#        "bullets": ["...", "..."], "footer": "...", "seed": 1}
# Requires: Heebo.ttf next to this script (google/fonts ofl/heebo/Heebo[wght].ttf), Pillow with raqm.
import json, os, random, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "Heebo.ttf")
W, H = 1080, 1350

PALETTES = {
    "emerald":  {"bg": (11, 14, 20),  "accent": (34, 214, 140), "accent2": (240, 72, 88),  "txt": (236, 240, 245), "muted": (130, 140, 155)},
    "gold":     {"bg": (16, 13, 8),   "accent": (240, 186, 60), "accent2": (200, 90, 50),  "txt": (248, 242, 230), "muted": (160, 145, 120)},
    "electric": {"bg": (8, 12, 30),   "accent": (70, 150, 255), "accent2": (150, 90, 255), "txt": (235, 240, 255), "muted": (130, 145, 180)},
    "crimson":  {"bg": (20, 8, 12),   "accent": (255, 76, 96),  "accent2": (255, 160, 80), "txt": (250, 236, 238), "muted": (170, 130, 138)},
    "violet":   {"bg": (16, 10, 26),  "accent": (180, 120, 255),"accent2": (255, 110, 200),"txt": (242, 236, 255), "muted": (150, 135, 175)},
    "cyan":     {"bg": (6, 18, 22),   "accent": (40, 220, 230), "accent2": (40, 200, 140), "txt": (230, 248, 250), "muted": (120, 160, 165)},
    "orange":   {"bg": (18, 11, 6),   "accent": (255, 128, 40), "accent2": (255, 200, 60), "txt": (252, 240, 230), "muted": (170, 140, 120)},
    "light":    {"bg": (244, 241, 234),"accent": (20, 110, 80), "accent2": (190, 60, 60),  "txt": (20, 22, 28),    "muted": (110, 110, 115)},
}

def font(size, weight):
    f = ImageFont.truetype(FONT, size, layout_engine=ImageFont.Layout.RAQM)
    f.set_variation_by_axes([weight])
    return f

def mix(c, bg, a):
    return tuple(int(v * a + b * (1 - a)) for v, b in zip(c, bg))

def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f, direction="rtl") <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def main(spec_path, out):
    s = json.load(open(spec_path, encoding="utf-8"))
    p = PALETTES[s.get("palette", "emerald")]
    BG, A, A2, TXT, MUTED = p["bg"], p["accent"], p["accent2"], p["txt"], p["muted"]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # candlestick backdrop
    rnd = random.Random(s.get("seed", 7))
    price, drift = 980, rnd.choice([4.0, 6.0, 8.0])
    for i in range(26):
        x = 40 + i * 40
        o = price
        c = min(max(price + rnd.randint(-55, 60) - drift * 3, 620), 1040)
        hi, lo = min(o, c) - rnd.randint(8, 30), min(max(o, c) + rnd.randint(8, 30), 1100)
        col = mix(A if c < o else A2, BG, 0.2)
        d.line([(x + 10, hi), (x + 10, lo)], fill=col, width=3)
        d.rectangle([x, min(o, c), x + 20, max(o, c)], fill=col)
        price = min(max(c, 700), 1040)

    R, L = W - 90, 90
    maxw = R - L

    d.rounded_rectangle([R - 250, 90, R, 146], radius=28, outline=A, width=3)
    d.text((R - 125, 118), "NQ TRADER'S", font=font(30, 700), fill=A, anchor="mm")

    y = 210
    d.text((R, y), s.get("category", ""), font=font(44, 500), fill=MUTED, anchor="ra", direction="rtl")
    y += 60
    size = 150
    while size > 80 and d.textlength(s["title"], font=font(size, 900), direction="rtl") > maxw:
        size -= 6
    for ln in wrap(d, s["title"], font(size, 900), maxw):
        d.text((R, y), ln, font=font(size, 900), fill=TXT, anchor="ra", direction="rtl")
        y += int(size * 1.15)
    y += 10
    for ln in wrap(d, s.get("subtitle", ""), font(64, 700), maxw):
        d.text((R, y), ln, font=font(64, 700), fill=A, anchor="ra", direction="rtl")
        y += 80
    y = max(y + 60, 600)

    bf = font(42, 400)
    for b in s.get("bullets", []):
        lines = wrap(d, b, bf, maxw - 40)
        d.ellipse([R - 18, y + 22, R, y + 40], fill=A)
        for ln in lines:
            d.text((R - 38, y), ln, font=bf, fill=TXT, anchor="ra", direction="rtl")
            y += 58
        y += 44

    d.line([(L, 1130), (R, 1130)], fill=mix(MUTED, BG, 0.3), width=2)
    d.text((R, 1160), s.get("footer", ""), font=font(36, 500), fill=MUTED, anchor="ra", direction="rtl")
    d.text((L, 1250), "@nq_tradersss", font=font(34, 600), fill=A, anchor="la")
    img.save(out, quality=92)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
