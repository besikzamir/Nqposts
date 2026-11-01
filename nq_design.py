# NQ Trader's design system: 6 distinct luxury templates shared by posts, carousels and reels.
# A template turns a "slide" dict into a background + animated elements, at any canvas size
# (1080x1350 feed posts, 1080x1920 reels).
#
# slide = {"category", "title", "subtitle", "bullets": [...], "footer", "number": "01", "label"}
# kind  = "cover" | "item" | "cta"
import math, os, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(HERE, "fonts")
FONTS = {
    "heebo": os.path.join(HERE, "Heebo.ttf"),
    "frank": os.path.join(FD, "FrankRuhlLibre.ttf"),
    "bellefair": os.path.join(FD, "Bellefair.ttf"),
    "suez": os.path.join(FD, "SuezOne.ttf"),
    "rubik": os.path.join(FD, "Rubik.ttf"),
    "secular": os.path.join(FD, "SecularOne.ttf"),
}
VARIABLE = {"heebo", "frank", "rubik"}
_fc = {}
SCALE = 1.0  # typography multiplier; nq_reel sets this for the tall 9:16 canvas


def F(name, size, weight=400):
    size = int(size * SCALE)
    k = (name, size, weight)
    if k not in _fc:
        f = ImageFont.truetype(FONTS[name], size, layout_engine=ImageFont.Layout.RAQM)
        if name in VARIABLE:
            f.set_variation_by_axes([weight])
        _fc[k] = f
    return _fc[k]


def is_rtl(s):
    return any("֐" <= ch <= "׿" for ch in s)


def tl(d, s, f):
    return d.textlength(s, font=f, direction="rtl" if is_rtl(s) else None)


_scr = ImageDraw.Draw(Image.new("L", (8, 8)))


def wrap(text, f, maxw):
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if tl(_scr, t, f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(text, name, weight, start, maxw, max_lines=3, minsize=60):
    size = start
    while size > minsize:
        f = F(name, size, weight)
        lines = wrap(text, f, maxw)
        if len(lines) <= max_lines and all(tl(_scr, ln, f) <= maxw for ln in lines):
            return f, lines, size
        size -= 4
    f = F(name, minsize, weight)
    return f, wrap(text, f, maxw), minsize


def mix(c, bg, a):
    return tuple(int(v * a + b * (1 - a)) for v, b in zip(c, bg))


def vgrad(w, h, stops):
    """Vertical multi-stop gradient as RGB image."""
    col = Image.new("RGB", (1, len(stops)))
    for i, c in enumerate(stops):
        col.putpixel((0, i), c)
    return col.resize((w, h), Image.BILINEAR)


def hgrad(w, h, stops):
    row = Image.new("RGB", (len(stops), 1))
    for i, c in enumerate(stops):
        row.putpixel((i, 0), c)
    return row.resize((w, h), Image.BILINEAR)


GOLD = [(110, 80, 36), (214, 176, 104), (250, 232, 178), (226, 190, 118), (150, 112, 52)]
ROSE = [(112, 62, 52), (214, 150, 128), (252, 222, 204), (220, 160, 138), (130, 76, 62)]
PLAT = [(90, 94, 102), (190, 196, 206), (250, 252, 255), (200, 206, 214), (110, 116, 126)]


class Text:
    """A block of lines rendered to an RGBA layer the width of the canvas."""

    def __init__(self, W, lines, f, fill, line_h, align="r", margin=90, stroke=0, glow=None, track=0):
        self.lines, self.f, self.fill, self.lh = lines, f, fill, line_h
        asc, desc = f.getmetrics()
        self.h = line_h * (len(lines) - 1) + asc + desc + 8 + 2 * stroke
        pad = 40 if glow else 0
        mask = Image.new("L", (W, self.h + 2 * pad), 0)
        d = ImageDraw.Draw(mask)
        x = {"r": W - margin, "c": W // 2, "l": margin}[align]
        anchor = {"r": "ra", "c": "ma", "l": "la"}[align]
        for i, ln in enumerate(lines):
            y = pad + i * line_h + stroke
            if track and not is_rtl(ln):
                self._tracked(d, ln, f, x, y, align, track, stroke)
            else:
                d.text((x, y), ln, font=f, fill=255, anchor=anchor,
                       direction="rtl" if is_rtl(ln) else None, stroke_width=stroke)
        if stroke:  # outline only
            inner = Image.new("L", mask.size, 0)
            di = ImageDraw.Draw(inner)
            for i, ln in enumerate(lines):
                di.text((x, pad + i * line_h + stroke), ln, font=f, fill=255, anchor=anchor,
                        direction="rtl" if is_rtl(ln) else None)
            mask = ImageChops.subtract(mask, inner)
        if isinstance(fill, Image.Image):
            src = fill.resize(mask.size)
        else:
            src = Image.new("RGB", mask.size, fill[:3])
        layer = src.convert("RGBA")
        if not isinstance(fill, Image.Image) and len(fill) == 4:
            a = mask.point(lambda v: v * fill[3] // 255)
        else:
            a = mask
        layer.putalpha(a)
        if glow:
            g = Image.new("RGBA", mask.size, glow[:3] + (0,))
            g.putalpha(mask.filter(ImageFilter.GaussianBlur(18)).point(lambda v: min(255, v * glow[3] // 100)))
            g.alpha_composite(layer)
            layer = g
        self.img, self.pad = layer, pad

    @staticmethod
    def _tracked(d, s, f, x, y, align, track, stroke):
        widths = [d.textlength(ch, font=f) for ch in s]
        total = sum(widths) + track * (len(s) - 1)
        cx = {"r": x - total, "c": x - total / 2, "l": x}[align]
        for ch, w in zip(s, widths):
            d.text((cx, y), ch, font=f, fill=255, anchor="la", stroke_width=stroke)
            cx += w + track


class El:
    """Positioned animated element."""

    def __init__(self, img, y, delay=0.0, style="fade_up", x=0):
        self.img, self.y, self.x, self.delay, self.style = img, y, x, delay, style


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def place(canvas, el, t, dur=0.55):
    """Composite element at time t (seconds since scene start). t=None → final state."""
    k = 1.0 if t is None else ease((t - el.delay) / dur)
    if k <= 0:
        return
    img, x, y = el.img, el.x, el.y
    if k < 1:
        if el.style == "fade_up":
            y += int((1 - k) * 60)
        elif el.style == "slide_rtl":
            x += int((1 - k) * 140)
        elif el.style == "drop":
            y -= int((1 - k) * 60)
        elif el.style == "scale":
            s = 0.88 + 0.12 * k
            w, h = img.size
            img = img.resize((int(w * s), int(h * s)), Image.BILINEAR)
            x += (w - img.width) // 2
            y += (h - img.height) // 2
        elif el.style == "wipe_rtl":
            w = img.width
            img = img.copy()
            m = Image.new("L", img.size, 0)
            ImageDraw.Draw(m).rectangle([int(w * (1 - k)), 0, w, img.height], fill=255)
            img.putalpha(ImageChops.multiply(img.getchannel("A"), m))
            k = 1.0
        if k < 1:
            img = img.copy()
            img.putalpha(img.getchannel("A").point(lambda a: int(a * k)))
    comp(canvas, img, x, y)


def grain(W, H, amount, seed=1):
    rnd = random.Random(seed)
    small = Image.new("L", (W // 2, H // 2))
    small.putdata([128 + int(rnd.gauss(0, 40)) for _ in range(small.width * small.height)])
    n = small.resize((W, H))
    layer = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    layer.putalpha(n.point(lambda v: max(0, v - 128) * amount // 128))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dark.putalpha(n.point(lambda v: max(0, 128 - v) * amount // 128))
    dark.alpha_composite(layer)
    return dark


_rad = {}


def radial(d):
    """Smooth radial falloff (L image d x d), zero at the edge."""
    if d not in _rad:
        n = 96
        small = Image.new("L", (n, n))
        c = (n - 1) / 2
        small.putdata([int(255 * max(0.0, 1 - math.hypot(x - c, y - c) / c) ** 2) for y in range(n) for x in range(n)])
        _rad[d] = small.resize((d, d), Image.BICUBIC)
    return _rad[d]


def orb(r, color, alpha):
    a = radial(2 * r).point(lambda v: v * alpha // 255)
    lay = Image.new("RGBA", (2 * r, 2 * r), color + (0,))
    lay.putalpha(a)
    return lay


def comp(canvas, img, x, y):
    """alpha_composite that tolerates negative / overflowing offsets."""
    sx, sy = max(0, -x), max(0, -y)
    x, y = max(0, x), max(0, y)
    w, h = min(img.width - sx, canvas.width - x), min(img.height - sy, canvas.height - y)
    if w > 0 and h > 0:
        canvas.alpha_composite(img.crop((sx, sy, sx + w, sy + h)), (x, y))


def glow_blob(W, H, cx, cy, r, color, alpha):
    lay = Image.new("RGBA", (W, H), color + (0,))
    comp(lay, orb(r, color, alpha), int(cx - r), int(cy - r))
    return lay


# ---------------------------------------------------------------------------------------------
class Template:
    name = "base"
    variants = [{}]
    margin = 90

    def __init__(self, W, H, variant=0, seed=7):
        self.W, self.H, self.seed = W, H, seed
        self.v = self.variants[variant % len(self.variants)]
        self.reel = H > 1500
        # content box (reels keep clear of Instagram UI at top and bottom)
        self.top = 330 if self.reel else 200
        self.bottom = H - (430 if self.reel else 170)
        self.maxw = W - 2 * self.margin
        self._bg = None

    # subclasses: build_bg() -> RGBA, decor(kind) -> list[El] (static, drawn above bg),
    #             blocks(slide, kind) -> list of (Text|Image, gap_before, style, x)
    def background(self, t=0.0):
        if self._bg is None:
            self._bg = self.build_bg()
        return self._bg

    def decor(self, slide, kind):
        return []

    def stack(self, items, align="center"):
        """items: list of (layer RGBA, gap_before, style). Returns El list positioned in content box."""
        total = sum(g + im.height for im, g, _ in items)
        gaps = sum(g for _, g, _ in items)
        avail = self.bottom - self.top
        if total > avail and gaps:  # tighten spacing before anything overflows
            k = max(0.0, 1 - (total - avail) / gaps)
            items = [(im, int(g * k), st) for im, g, st in items]
            total = sum(g + im.height for im, g, _ in items)
        y = self.top + max(0, (self.bottom - self.top - total) // 2) if align == "center" else self.top
        out, delay = [], 0.05
        for im, gap, style in items:
            y += gap
            out.append(El(im, y, delay, style))
            y += im.height
            delay += 0.22
        return out

    def elements(self, slide, kind):
        return self.decor(slide, kind) + self.stack(self.blocks(slide, kind), self.valign(kind))

    def valign(self, kind):
        return "center"

    def render(self, slide, kind, t=None, t_global=0.0, els=None):
        canvas = self.background(t_global).copy()
        for el in (els if els is not None else self.elements(slide, kind)):
            place(canvas, el, t)
        return canvas.convert("RGB")

    # helpers
    def T(self, lines, f, fill, lh, align="r", **kw):
        return Text(self.W, lines, f, fill, lh, align, self.margin, **kw)

    def tlayer(self, text, f, fill, lh_mul=1.25, align="r", maxw=None, **kw):
        lines = wrap(text, f, maxw or self.maxw)
        return self.T(lines, f, fill, int(f.size * lh_mul), align, **kw).img


# 1 ── Noir & Gold: black lacquer, gold foil, double frame, centred serif ─────────────────────────
class NoirGold(Template):
    name = "noir_gold"
    variants = [{"foil": GOLD, "line": (201, 164, 96), "glow": (92, 66, 24)},
                {"foil": ROSE, "line": (214, 150, 128), "glow": (96, 50, 42)},
                {"foil": PLAT, "line": (190, 196, 206), "glow": (50, 58, 76)}]
    margin = 120

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.top = 190 if not self.reel else 330
        self.bottom = self.H - (150 if not self.reel else 450)

    def build_bg(self):
        W, H, v = self.W, self.H, self.v
        bg = Image.new("RGBA", (W, H), (11, 10, 9, 255))
        bg.alpha_composite(glow_blob(W, H, W // 2, int(H * 0.05), int(W * 0.8), v["glow"], 90))
        bg.alpha_composite(glow_blob(W, H, W // 2, H, int(W * 0.5), v["glow"], 40))
        bg.alpha_composite(grain(W, H, 12, self.seed))
        d = ImageDraw.Draw(bg)
        c = v["line"]
        d.rectangle([34, 34, W - 34, H - 34], outline=c + (200,), width=2)
        d.rectangle([46, 46, W - 46, H - 46], outline=c + (90,), width=1)
        # monogram + handle
        mono_y = 120 if not self.reel else 250
        d.ellipse([W // 2 - 46, mono_y - 46, W // 2 + 46, mono_y + 46], outline=c + (220,), width=2)
        m = Text(W, ["NQ"], F("frank", 40, 700), c, 40, "c").img
        bg.alpha_composite(m, (0, mono_y - 26))
        h = Text(W, ["@nq_tradersss"], F("heebo", 26, 400), c + (170,), 30, "c", track=0).img
        bg.alpha_composite(h, (0, H - (92 if not self.reel else 330)))
        return bg

    def ornament(self, text):
        f = F("heebo", 34, 400)
        lay = self.T([text], f, self.v["line"], 40, "c").img
        d = ImageDraw.Draw(lay)
        w = tl(_scr, text, f)
        y = lay.height // 2 + 2
        c = self.v["line"] + (200,)
        for s in (-1, 1):
            x0 = self.W // 2 + s * (w / 2 + 24)
            d.line([(x0, y), (x0 + s * 90, y)], fill=c, width=1)
            dx = x0 + s * 100
            d.polygon([(dx, y - 6), (dx + 6, y), (dx, y + 6), (dx - 6, y)], fill=c)
        return lay

    def divider(self):
        lay = Image.new("RGBA", (self.W, 22), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        c = self.v["line"] + (150,)
        d.line([(self.W // 2 - 50, 11), (self.W // 2 + 50, 11)], fill=c, width=1)
        return lay

    def blocks(self, s, kind):
        foil = vgrad(10, 10, self.v["foil"])
        out = []
        if s.get("number"):
            out.append((self.T([f"— {s['number']} —"], F("frank", 46, 500), foil, 50, "c").img, 0, "fade"))
        if s.get("category"):
            out.append((self.ornament(s["category"]), 18, "fade"))
        size0 = 150 if kind == "cover" else 118
        f, lines, size = fit(s["title"], "frank", 800, size0, self.maxw, 3)
        out.append((self.T(lines, f, foil, int(size * 1.08), "c").img, 34, "fade_up"))
        if s.get("subtitle"):
            out.append((self.tlayer(s["subtitle"], F("heebo", 46 if not self.reel else 52, 300),
                                    (238, 230, 214), 1.3, "c"), 22, "fade_up"))
        bl = s.get("bullets") or []
        if bl:
            out.append((self.divider(), 40, "fade"))
            for b in bl:
                out.append((self.tlayer(b, F("heebo", 40 if not self.reel else 46, 400), (230, 222, 206), 1.3, "c"), 22, "fade_up"))
                out.append((self.divider(), 18, "fade"))
        if s.get("footer"):
            out.append((self.tlayer(s["footer"], F("heebo", 32, 400), self.v["line"], 1.2, "c"), 40, "fade"))
        return out


# 2 ── Ivory Editorial: magazine page, black serif, numbered rules ──────────────────────────────
class IvoryEditorial(Template):
    name = "ivory_editorial"
    variants = [{"acc": (18, 92, 66)}, {"acc": (122, 22, 38)}, {"acc": (24, 44, 96)}]

    def build_bg(self):
        W, H = self.W, self.H
        bg = Image.new("RGBA", (W, H), (243, 238, 228, 255))
        bg.alpha_composite(glow_blob(W, H, W, 0, int(W * 0.7), (255, 252, 244), 160))
        bg.alpha_composite(grain(W, H, 26, self.seed))
        d = ImageDraw.Draw(bg)
        y = 110 if not self.reel else 250
        ink = (22, 20, 18, 255)
        bg.alpha_composite(Text(W, ["NQ TRADER'S"], F("rubik", 28, 700), ink, 30, "r", self.margin, track=5).img, (0, y - 18))
        bg.alpha_composite(Text(W, ["@nq_tradersss"], F("rubik", 26, 500), ink, 30, "l", self.margin).img, (0, y - 16))
        d.line([(self.margin, y + 34), (W - self.margin, y + 34)], fill=ink, width=4)
        d.line([(self.margin, y + 44), (W - self.margin, y + 44)], fill=ink, width=1)
        yb = H - (110 if not self.reel else 400)
        d.line([(self.margin, yb), (W - self.margin, yb)], fill=ink, width=1)
        return bg

    def decor(self, s, kind):
        if not s.get("number"):
            return []
        f = F("frank", 520 if self.reel else 440, 900)
        big = Text(self.W, [s["number"]], f, mix(self.v["acc"], (243, 238, 228), 0.13), 500, "l", 40).img
        return [El(big, self.top - 40, 0.0, "fade")]

    def rule(self):
        lay = Image.new("RGBA", (self.W, 3), (0, 0, 0, 0))
        ImageDraw.Draw(lay).line([(self.margin, 1), (self.W - self.margin, 1)], fill=(22, 20, 18, 90), width=1)
        return lay

    def blocks(self, s, kind):
        acc, ink = self.v["acc"], (22, 20, 18)
        out = []
        if s.get("category"):
            out.append((self.T([s["category"]], F("rubik", 34, 600), acc, 40, "r").img, 0, "wipe_rtl"))
        f, lines, size = fit(s["title"], "frank", 900, 150 if kind == "cover" else 124, self.maxw, 3)
        out.append((self.T(lines, f, ink, int(size * 1.02), "r").img, 16, "wipe_rtl"))
        if s.get("subtitle"):
            out.append((self.tlayer(s["subtitle"], F("frank", 48 if not self.reel else 54, 500), acc, 1.25), 14, "wipe_rtl"))
        for i, b in enumerate(s.get("bullets") or []):
            out.append((self.rule(), 30 if i == 0 else 18, "fade"))
            row = Image.new("RGBA", (self.W, 10), (0, 0, 0, 0))
            num = self.T([f"0{i + 1}"], F("frank", 46, 700), acc, 50, "r").img
            fb = F("heebo", 40 if not self.reel else 46, 400)
            txt = Text(self.W, wrap(b, fb, self.maxw - 110), fb, ink, int(fb.size * 1.3), "r", self.margin + 100).img
            h = max(num.height, txt.height)
            row = Image.new("RGBA", (self.W, h), (0, 0, 0, 0))
            row.alpha_composite(num, (0, 0))
            row.alpha_composite(txt, (0, 4))
            out.append((row, 18, "slide_rtl"))
        if s.get("footer"):
            out.append((self.tlayer(s["footer"], F("rubik", 30, 500), mix(ink, (243, 238, 228), 0.6)), 44, "fade"))
        return out


# 3 ── Glass Aurora: drifting colour orbs behind a frosted card ────────────────────────────────
class GlassAurora(Template):
    name = "glass_aurora"
    variants = [{"c": [(124, 77, 255), (0, 210, 200), (255, 64, 160)]},
                {"c": [(255, 110, 64), (255, 40, 120), (255, 196, 70)]},
                {"c": [(40, 110, 255), (0, 220, 255), (120, 70, 255)]}]
    margin = 130

    def build_base(self):
        W, H = self.W, self.H
        base = Image.new("RGBA", (W, H), (7, 9, 22, 255))
        return base

    def background(self, t=0.0):
        W, H = self.W, self.H
        if self._bg is None:
            self._base = self.build_base()
            rnd = random.Random(self.seed)
            self._orbs = []
            for c in self.v["c"]:
                r = int(W * rnd.uniform(0.45, 0.6))
                self._orbs.append((orb(r, c, 210), rnd.uniform(0.1, 0.9) * W, rnd.uniform(0.15, 0.85) * H, rnd.uniform(0, 6.28)))
            self._grain = grain(W, H, 18, self.seed)
            self._bg = True
            self._static = None
        if self._static is not None and t == self._static[0]:
            return self._static[1]
        img = self._base.copy()
        for ob, x, y, ph in self._orbs:
            dx = math.sin(t * 0.35 + ph) * 80
            dy = math.cos(t * 0.28 + ph) * 60
            comp(img, ob, int(x + dx - ob.width // 2), int(y + dy - ob.height // 2))
        img.alpha_composite(self._grain)
        d = ImageDraw.Draw(img)
        y = 110 if not self.reel else 250
        img.alpha_composite(Text(W, ["NQ TRADER'S"], F("rubik", 28, 700), (255, 255, 255, 220), 30, "c", track=6).img, (0, y - 16))
        img.alpha_composite(Text(W, ["@nq_tradersss"], F("rubik", 28, 500), (255, 255, 255, 170), 30, "c").img,
                            (0, H - (100 if not self.reel else 330)))
        self._static = (t, img)
        return img

    def elements(self, s, kind):
        els = self.stack(self.blocks(s, kind), "center")
        top = min(e.y for e in els) - 70
        bot = max(e.y + e.img.height for e in els) + 60
        card = Image.new("RGBA", (self.W, bot - top), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        x0, x1 = 70, self.W - 70
        d.rounded_rectangle([x0, 0, x1, card.height - 1], radius=48, fill=(255, 255, 255, 30), outline=(255, 255, 255, 80), width=2)
        hl = vgrad(x1 - x0, card.height, [(255, 255, 255), (255, 255, 255)]).convert("RGBA")
        hl.putalpha(vgrad(x1 - x0, card.height, [(26, 26, 26), (0, 0, 0), (0, 0, 0)]).convert("L"))
        m = Image.new("L", hl.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, hl.width - 1, hl.height - 1], radius=48, fill=255)
        hl.putalpha(ImageChops.multiply(hl.getchannel("A"), m))
        card.alpha_composite(hl, (x0, 0))
        return [El(card, top, 0.0, "scale")] + els

    def blocks(self, s, kind):
        c1, c2, c3 = self.v["c"]
        grad = hgrad(10, 10, [mix(c2, (255, 255, 255), 0.75), mix(c1, (255, 255, 255), 0.75)])
        out = []
        if s.get("number"):
            out.append((self.T([s["number"]], F("rubik", 150, 800), grad, 150, "r").img, 0, "scale"))
        if s.get("category"):
            f = F("rubik", 32, 500)
            lay = self.T([s["category"]], f, (255, 255, 255), 40, "r").img
            pill = Image.new("RGBA", (self.W, lay.height + 22), (0, 0, 0, 0))
            w = tl(_scr, s["category"], f)
            ImageDraw.Draw(pill).rounded_rectangle([self.W - self.margin - w - 30, 0, self.W - self.margin + 30, pill.height - 1],
                                                   radius=pill.height // 2, outline=(255, 255, 255, 140), width=2)
            pill.alpha_composite(lay, (0, 10))
            out.append((pill, 12, "fade"))
        f, lines, size = fit(s["title"], "rubik", 800, 132 if kind == "cover" else 108, self.maxw, 3)
        out.append((self.T(lines, f, (255, 255, 255), int(size * 1.1), "r").img, 22, "fade_up"))
        if s.get("subtitle"):
            out.append((self.tlayer(s["subtitle"], F("rubik", 48 if not self.reel else 54, 600), grad, 1.25), 12, "fade_up"))
        fb = F("rubik", 38 if not self.reel else 44, 400)
        for i, b in enumerate(s.get("bullets") or []):
            txt = Text(self.W, wrap(b, fb, self.maxw - 50), fb, (240, 242, 255), int(fb.size * 1.3), "r", self.margin + 44).img
            d = ImageDraw.Draw(txt)
            cy = int(fb.size * 0.72)
            x = self.W - self.margin - 12
            d.ellipse([x - 9, cy - 9, x + 9, cy + 9], fill=c2 + (255,))
            out.append((txt, 34 if i == 0 else 18, "fade_up"))
        if s.get("footer"):
            out.append((self.tlayer(s["footer"], F("rubik", 30, 400), (255, 255, 255, 170)), 34, "fade"))
        return out


# 4 ── Terminal Chart: trading desk, grid, glowing area chart ───────────────────────────────────
class TerminalChart(Template):
    name = "terminal_chart"
    variants = [{"acc": (0, 230, 140)}, {"acc": (64, 160, 255)}, {"acc": (255, 176, 32)}]

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.bottom = self.H - int(self.H * 0.2) - (90 if not self.reel else 400)

    def build_bg(self):
        W, H = self.W, self.H
        bg = Image.new("RGBA", (W, H), (6, 8, 11, 255))
        d = ImageDraw.Draw(bg)
        for x in range(0, W, 90):
            d.line([(x, 0), (x, H)], fill=(255, 255, 255, 10))
        for y in range(0, H, 90):
            d.line([(0, y), (W, y)], fill=(255, 255, 255, 10))
        bg.alpha_composite(glow_blob(W, H, W, 0, int(W * 0.6), self.v["acc"], 40))
        y = 110 if not self.reel else 250
        acc = self.v["acc"]
        bg.alpha_composite(Text(W, ["NQ TRADER'S"], F("rubik", 28, 700), (255, 255, 255, 230), 30, "r", self.margin, track=4).img, (0, y - 16))
        d.ellipse([self.margin - 2, y - 5, self.margin + 14, y + 11], fill=acc + (255,))
        bg.alpha_composite(Text(W, ["MARKET NOTES"], F("rubik", 24, 600), acc, 30, "l", self.margin + 28, track=4).img, (0, y - 14))
        bg.alpha_composite(Text(W, ["@nq_tradersss"], F("rubik", 28, 500), (255, 255, 255, 150), 30, "l", self.margin).img,
                           (0, H - (100 if not self.reel else 330)))
        self._chart = self.chart()
        return bg

    def chart(self):
        W, H = self.W, self.H
        rnd = random.Random(self.seed)
        n = 60
        vals, v = [], 0.5
        for _ in range(n):
            v = min(0.95, max(0.05, v + rnd.uniform(-0.09, 0.105)))
            vals.append(v)
        ch = int(H * (0.19 if not self.reel else 0.2))
        y0 = H - ch - (70 if not self.reel else 380)
        pts = [(int(i * W / (n - 1)), int(y0 + ch * (1 - vals[i]))) for i in range(n)]
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        area = Image.new("L", (W, H), 0)
        ImageDraw.Draw(area).polygon(pts + [(W, H), (0, H)], fill=255)
        fill = vgrad(W, H, [(0, 0, 0)] * 2 + [self.v["acc"], (0, 0, 0)]).convert("RGBA")
        fill.putalpha(ImageChops.multiply(area, vgrad(W, H, [(0, 0, 0), (0, 0, 0), (70, 70, 70), (0, 0, 0)]).convert("L")))
        lay.alpha_composite(fill)
        line = Image.new("L", (W, H), 0)
        ImageDraw.Draw(line).line(pts, fill=255, width=5, joint="curve")
        g = Image.new("RGBA", (W, H), self.v["acc"] + (0,))
        g.putalpha(line.filter(ImageFilter.GaussianBlur(10)).point(lambda a: min(255, a * 2)))
        lay.alpha_composite(g)
        l2 = Image.new("RGBA", (W, H), self.v["acc"] + (0,))
        l2.putalpha(line)
        lay.alpha_composite(l2)
        return lay

    def background(self, t=0.0):
        if self._bg is None:
            self._bg = self.build_bg()
        return self._bg

    def render(self, slide, kind, t=None, t_global=0.0, els=None):
        canvas = self.background().copy()
        k = 1.0 if t is None else ease(t / 1.4)
        ch = self._chart if k >= 1 else self._chart.crop((0, 0, max(1, int(self.W * k)), self.H))
        canvas.alpha_composite(ch, (0, 0))
        for el in (els if els is not None else self.elements(slide, kind)):
            place(canvas, el, t, 0.4)
        return canvas.convert("RGB")

    def valign(self, kind):
        return "top"

    def blocks(self, s, kind):
        acc = self.v["acc"]
        out = []
        if s.get("number"):
            lay = self.T([s["number"]], F("suez", 96 if not self.reel else 120, 400), acc, 100, "r", glow=acc + (60,)).img
            out.append((lay, 0, "slide_rtl"))
        if s.get("category"):
            out.append((self.T([s["category"]], F("rubik", 34, 600), acc, 40, "r").img, 6, "slide_rtl"))
        f, lines, size = fit(s["title"], "suez", 400, 140 if kind == "cover" else 112, self.maxw, 3)
        out.append((self.T(lines, f, (250, 252, 255), int(size * 1.08), "r").img, 10, "slide_rtl"))
        if s.get("subtitle"):
            out.append((self.tlayer(s["subtitle"], F("heebo", 46 if not self.reel else 52, 500), (200, 208, 220), 1.25), 8, "slide_rtl"))
        fb = F("heebo", 36 if not self.reel else 42, 500)
        for i, b in enumerate(s.get("bullets") or []):
            w = min(self.maxw, tl(_scr, b, fb) + 60)
            pill = Image.new("RGBA", (self.W, fb.size + 34), (0, 0, 0, 0))
            d = ImageDraw.Draw(pill)
            x1 = self.W - self.margin
            d.rounded_rectangle([x1 - w, 0, x1, pill.height - 1], radius=pill.height // 2,
                                fill=(14, 18, 24, 235), outline=acc + (110,), width=2)
            pill.alpha_composite(Text(self.W, [b], fb, (235, 240, 248), fb.size, "r", self.margin + 30).img, (0, 10))
            out.append((pill, 30 if i == 0 else 14, "slide_rtl"))
        if s.get("footer"):
            out.append((self.tlayer(s["footer"], F("rubik", 30, 500), acc), 30, "fade"))
        return out


# 5 ── Velvet: deep jewel tone, gold leaf, outlined numeral ─────────────────────────────────────
class Velvet(Template):
    name = "velvet"
    variants = [{"bg": (6, 46, 36), "foil": GOLD}, {"bg": (10, 24, 62), "foil": PLAT}, {"bg": (58, 8, 22), "foil": GOLD}]

    def build_bg(self):
        W, H, b = self.W, self.H, self.v["bg"]
        bg = Image.new("RGBA", (W, H), mix(b, (0, 0, 0), 0.45) + (255,))
        bg.alpha_composite(glow_blob(W, H, int(W * 0.7), int(H * 0.35), int(W * 0.8), mix(b, (255, 255, 255), 0.85), 255))
        bg.alpha_composite(grain(W, H, 20, self.seed))
        foil = vgrad(10, 10, self.v["foil"])
        y = 110 if not self.reel else 250
        bg.alpha_composite(Text(W, ["NQ TRADER'S"], F("frank", 34, 700), foil, 36, "r", self.margin, track=6).img, (0, y - 20))
        d = ImageDraw.Draw(bg)
        gc = self.v["foil"][1]
        d.line([(self.margin, y + 36), (self.margin + 120, y + 36)], fill=gc + (200,), width=2)
        d.line([(W - self.margin - 120, y + 36), (W - self.margin, y + 36)], fill=gc + (200,), width=2)
        bg.alpha_composite(Text(W, ["@nq_tradersss"], F("heebo", 28, 400), gc + (190,), 30, "l", self.margin).img,
                           (0, H - (100 if not self.reel else 330)))
        return bg

    def decor(self, s, kind):
        txt = s.get("number") or ("NQ" if kind == "cover" else None)
        if not txt:
            return []
        f = F("frank", 560 if self.reel else 480, 900)
        lay = Text(self.W, [txt], f, self.v["foil"][1] + (48,), 500, "l", 30, stroke=2).img
        return [El(lay, self.bottom - lay.height + 40, 0.0, "fade")]

    def blocks(self, s, kind):
        foil = vgrad(10, 10, self.v["foil"])
        gc = self.v["foil"][1]
        out = []
        if s.get("category"):
            f = F("heebo", 34, 500)
            lay = self.T([s["category"]], f, gc, 40, "r").img
            out.append((lay, 0, "fade_up"))
        f, lines, size = fit(s["title"], "frank", 900, 152 if kind == "cover" else 126, self.maxw, 3)
        out.append((self.T(lines, f, foil, int(size * 1.05), "r").img, 14, "fade_up"))
        if s.get("subtitle"):
            out.append((self.tlayer(s["subtitle"], F("heebo", 46 if not self.reel else 52, 300), (240, 236, 226), 1.3), 14, "fade_up"))
        fb = F("heebo", 40 if not self.reel else 46, 400)
        for i, b in enumerate(s.get("bullets") or []):
            txt = Text(self.W, wrap(b, fb, self.maxw - 50), fb, (240, 236, 226), int(fb.size * 1.3), "r", self.margin + 46).img
            d = ImageDraw.Draw(txt)
            cy, x = int(fb.size * 0.72), self.W - self.margin - 12
            d.polygon([(x, cy - 11), (x + 11, cy), (x, cy + 11), (x - 11, cy)], fill=gc + (255,))
            out.append((txt, 40 if i == 0 else 20, "fade_up"))
        if s.get("footer"):
            out.append((self.tlayer(s["footer"], F("heebo", 32, 400), gc), 40, "fade"))
        return out


# 6 ── Bold Split: colour block headline over dark body ────────────────────────────────────────
class BoldSplit(Template):
    name = "bold_split"
    variants = [{"blk": (150, 18, 40), "acc": (255, 92, 110)}, {"blk": (28, 60, 200), "acc": (110, 160, 255)},
                {"blk": (198, 160, 82), "acc": (226, 190, 118), "dark_text": True}]

    def build_bg(self):
        W, H = self.W, self.H
        self.split = int(H * (0.50 if not self.reel else 0.47))
        bg = Image.new("RGBA", (W, H), (12, 12, 14, 255))
        blk = self.v["blk"]
        top = vgrad(W, self.split, [mix(blk, (255, 255, 255), 0.85), blk, mix(blk, (0, 0, 0), 0.75)]).convert("RGBA")
        d = ImageDraw.Draw(top)
        for x in range(-self.split, W, 28):  # fine diagonal satin
            d.line([(x, 0), (x + self.split, self.split)], fill=(255, 255, 255, 10), width=1)
        bg.alpha_composite(top)
        bg.alpha_composite(grain(W, H, 16, self.seed))
        d = ImageDraw.Draw(bg)
        d.line([(0, self.split), (W, self.split)], fill=(226, 190, 118, 255), width=4)
        ink = (20, 16, 10) if self.v.get("dark_text") else (255, 255, 255)
        y = 110 if not self.reel else 250
        bg.alpha_composite(Text(W, ["NQ TRADER'S"], F("secular", 30, 400), ink + (230,), 32, "r", self.margin, track=4).img, (0, y - 18))
        bg.alpha_composite(Text(W, ["@nq_tradersss"], F("rubik", 28, 500), (255, 255, 255, 160), 30, "l", self.margin).img,
                           (0, H - (100 if not self.reel else 330)))
        return bg

    def elements(self, s, kind):
        self.background()
        ink = (20, 16, 10) if self.v.get("dark_text") else (255, 255, 255)
        acc = self.v["acc"]
        head = []
        if s.get("number"):
            head.append((self.T([s["number"]], F("suez", 110, 400), ink + (150,), 110, "r").img, 0, "drop"))
        if s.get("category"):
            head.append((self.T([s["category"]], F("rubik", 34, 600), ink + (200,), 40, "r").img, 0, "drop"))
        f, lines, size = fit(s["title"], "suez", 400, 150 if kind == "cover" else 124, self.maxw, 3)
        head.append((self.T(lines, f, ink, int(size * 1.08), "r").img, 10, "drop"))
        # bottom-anchor the headline above the split line
        total = sum(g + im.height for im, g, _ in head)
        y = self.split - 50 - total
        els, delay = [], 0.0
        for im, g, st in head:
            y += g
            els.append(El(im, y, delay, st))
            y += im.height
            delay += 0.18
        body = []
        if s.get("subtitle"):
            body.append((self.tlayer(s["subtitle"], F("rubik", 48 if not self.reel else 54, 700), acc, 1.25), 0, "fade_up"))
        fb = F("heebo", 40 if not self.reel else 46, 400)
        for i, b in enumerate(s.get("bullets") or []):
            row = Text(self.W, wrap(b, fb, self.maxw - 90), fb, (236, 236, 240), int(fb.size * 1.3), "r", self.margin + 80).img
            num = self.T([f"{i + 1}"], F("suez", 44, 400), acc, 44, "r").img
            row.alpha_composite(num, (0, -2))
            body.append((row, 30 if i == 0 else 16, "slide_rtl"))
        if s.get("footer"):
            body.append((self.tlayer(s["footer"], F("rubik", 30, 500), (255, 255, 255, 150)), 36, "fade"))
        y = self.split + 60
        for im, g, st in body:
            y += g
            els.append(El(im, y, delay, st))
            y += im.height
            delay += 0.18
        return els


TEMPLATES = [NoirGold, IvoryEditorial, GlassAurora, TerminalChart, Velvet, BoldSplit]
BY_NAME = {t.name: t for t in TEMPLATES}


def pick(index, W, H, seed=7):
    """Template + variant for a running content index, so consecutive posts never share a template."""
    cls = TEMPLATES[index % len(TEMPLATES)]
    variant = (index // len(TEMPLATES)) % 3
    return cls(W, H, variant, seed)


def make(name, W, H, variant=0, seed=7):
    return BY_NAME[name](W, H, variant, seed)
