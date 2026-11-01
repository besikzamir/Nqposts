# NQ Trader's Instagram Reel generator (1080x1920, 30fps, silent AAC track)
# Usage: python3 nq_reel.py reel.json out.mp4 [--preview DIR]
# reel.json: {"palette": "<name>", "seed": 1,
#   "hook": {"category": "...", "title": "...", "subtitle": "..."},
#   "items": [{"title": "...", "text": "..."}, ...],      # 2-5 items
#   "item_label": "טעות",                                    # shown as "<label> 1 מתוך 3"
#   "cta": {"title": "...", "subtitle": "..."}}
# Needs Heebo.ttf next to this script, Pillow with raqm, ffmpeg.
import json, os, random, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nq_post import PALETTES, FONT, mix, wrap

W, H, FPS = 1080, 1920, 30
R, L = W - 90, 90
MAXW = R - L
_fonts = {}


def font(size, weight):
    k = (size, weight)
    if k not in _fonts:
        f = ImageFont.truetype(FONT, size, layout_engine=ImageFont.Layout.RAQM)
        f.set_variation_by_axes([weight])
        _fonts[k] = f
    return _fonts[k]


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def text_layer(lines, f, color, line_h, align="ra"):
    """Render RTL lines to a tight RGBA layer; returns (img, height)."""
    h = line_h * len(lines) + 20
    img = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = R if align == "ra" else W // 2
    for i, ln in enumerate(lines):
        d.text((x, i * line_h), ln, font=f, fill=color + (255,), anchor=align, direction="rtl")
    return img


def fit_title(d, text, start, weight, minsize=70):
    size = start
    while size > minsize and max(d.textlength(w, font=font(size, weight), direction="rtl") for w in text.split()) > MAXW:
        size -= 6
    lines = wrap(d, text, font(size, weight), MAXW)
    while len(lines) > 3 and size > minsize:
        size -= 6
        lines = wrap(d, text, font(size, weight), MAXW)
    return size, lines


class Reel:
    def __init__(self, spec):
        self.s = spec
        p = PALETTES[spec.get("palette", "emerald")]
        self.BG, self.A, self.A2, self.TXT, self.MUT = p["bg"], p["accent"], p["accent2"], p["txt"], p["muted"]
        self.scratch = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        self.candles = self._candles(spec.get("seed", 7))
        self.n_items = len(spec["items"])

    def _candles(self, seed):
        rnd = random.Random(seed)
        n, step = 70, 44
        img = Image.new("RGBA", (n * step + 40, 700), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        price = 420
        for i in range(n):
            x = 20 + i * step
            o = price
            c = min(max(price + rnd.randint(-70, 74) - 9, 80), 620)
            hi, lo = min(o, c) - rnd.randint(10, 40), max(o, c) + rnd.randint(10, 40)
            col = mix(self.A if c < o else self.A2, self.BG, 0.28) + (255,)
            d.line([(x + 12, hi), (x + 12, lo)], fill=col, width=4)
            d.rectangle([x, min(o, c), x + 24, max(o, c)], fill=col)
            price = min(max(c, 140), 600)
        return img

    def base(self, t_global, scene_idx, n_scenes, reveal=1.0):
        img = Image.new("RGB", (W, H), self.BG)
        # drifting candle backdrop, revealed left-to-right during the hook
        off = int(t_global * 38)
        strip = self.candles.crop((off, 0, off + W, 700))
        if reveal < 1:
            mask = Image.new("L", (W, 700), 0)
            ImageDraw.Draw(mask).rectangle([0, 0, int(W * reveal), 700], fill=255)
            strip.putalpha(Image.composite(strip.getchannel("A"), mask, mask))
        img.paste(strip, (0, 1200), strip)
        d = ImageDraw.Draw(img)
        # progress segments
        seg_w = (MAXW - (n_scenes - 1) * 12) / n_scenes
        for i in range(n_scenes):
            x0 = R - (i + 1) * seg_w - i * 12
            col = self.A if i <= scene_idx else mix(self.MUT, self.BG, 0.35)
            d.rounded_rectangle([x0, 200, x0 + seg_w, 208], radius=4, fill=col)
        # brand pill + handle
        d.rounded_rectangle([R - 250, 250, R, 306], radius=28, outline=self.A, width=3)
        d.text((R - 125, 278), "NQ TRADER'S", font=font(30, 700), fill=self.A, anchor="mm")
        d.text((L, 278), "@nq_tradersss", font=font(36, 600), fill=self.A, anchor="lm")
        return img

    @staticmethod
    def put(img, layer, y, t, start, dur=0.45, rise=50):
        k = ease((t - start) / dur)
        if k <= 0:
            return
        lay = layer
        if k < 1:
            lay = layer.copy()
            lay.putalpha(lay.getchannel("A").point(lambda a: int(a * k)))
        img.paste(lay, (0, int(y + (1 - k) * rise)), lay)

    # ---- scenes: each returns (duration, frame_fn) ----
    def scene_hook(self):
        h = self.s["hook"]
        size, tl = fit_title(self.scratch, h["title"], 150, 900)
        layers = [
            (text_layer([h.get("category", "")], font(48, 500), self.MUT, 60), 520, 0.1),
            (text_layer(tl, font(size, 900), self.TXT, int(size * 1.12)), 600, 0.35),
        ]
        sub = wrap(self.scratch, h.get("subtitle", ""), font(66, 700), MAXW)
        layers.append((text_layer(sub, font(66, 700), self.A, 82), 620 + int(size * 1.12) * len(tl) + 20, 0.8))
        return 3.0, layers, True

    def scene_item(self, i):
        it = self.s["items"][i]
        size, tl = fit_title(self.scratch, it["title"], 128, 900)
        body = wrap(self.scratch, it["text"], font(58, 400), MAXW)
        num = text_layer([f"0{i + 1}"], font(220, 900), self.A, 230)
        y_title = 740
        y_body = y_title + int(size * 1.12) * len(tl) + 40
        label = self.s.get("item_label", "טעות")
        layers = [
            (num, 470, 0.0),
            (text_layer(tl, font(size, 900), self.TXT, int(size * 1.12)), y_title, 0.25),
            (text_layer(body, font(58, 400), self.TXT, 78), y_body, 0.7),
            (text_layer([f"{label} {i + 1} מתוך {self.n_items}"], font(40, 500), self.MUT, 50), y_body + 78 * len(body) + 50, 0.9),
        ]
        return 4.0, layers, False

    def scene_cta(self):
        c = self.s["cta"]
        size, tl = fit_title(self.scratch, c["title"], 130, 900)
        sub = wrap(self.scratch, c.get("subtitle", ""), font(64, 700), MAXW)
        y2 = 560 + int(size * 1.12) * len(tl) + 30
        layers = [
            (text_layer(tl, font(size, 900), self.TXT, int(size * 1.12)), 560, 0.0),
            (text_layer(sub, font(64, 700), self.A, 80), y2, 0.35),
            (text_layer(["פוסט חדש כל יום ב-10:00"], font(46, 500), self.MUT, 56), y2 + 80 * len(sub) + 60, 0.7),
        ]
        return 3.0, layers, False

    def scenes(self):
        out = [self.scene_hook()]
        out += [self.scene_item(i) for i in range(self.n_items)]
        out.append(self.scene_cta())
        return out

    def frame(self, scenes, idx, t, t0):
        dur, layers, reveal = scenes[idx]
        img = self.base(t0 + t, idx, len(scenes), ease(t / 1.6) if reveal else 1.0)
        for lay, y, start in layers:
            self.put(img, lay, y, t, start)
        # quick fade-in from background at scene start (inside the scene file)
        if idx > 0 and t < 0.2:
            img = Image.blend(Image.new("RGB", (W, H), self.BG), img, t / 0.2)
        return img


def encode(frames_iter, path):
    tmp = path[:-4] + ".part.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                          "-crf", "20", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for im in frames_iter:
        p.stdin.write(im.tobytes())
    p.stdin.close()
    if p.wait() != 0:
        sys.exit(f"ffmpeg failed on {path}")
    os.replace(tmp, path)


def main(spec_path, out, preview_dir=None):
    reel = Reel(json.load(open(spec_path, encoding="utf-8")))
    scenes = reel.scenes()
    if preview_dir:  # full-size stills at the busiest moment of each scene
        os.makedirs(preview_dir, exist_ok=True)
        t0 = 0
        for i, (dur, _, _) in enumerate(scenes):
            reel.frame(scenes, i, dur - 0.1, t0).save(os.path.join(preview_dir, f"scene{i + 1}.jpg"), quality=90)
            t0 += dur
        return
    work = out[:-4] + "_scenes"
    os.makedirs(work, exist_ok=True)
    parts, t0 = [], 0.0
    for i, (dur, _, _) in enumerate(scenes):
        part = os.path.join(work, f"s{i}.mp4")
        n = int(round(dur * FPS))
        encode((reel.frame(scenes, i, f / FPS, t0) for f in range(n)), part)
        parts.append(part)
        t0 += dur
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    total = t0
    tmp = out[:-4] + ".part.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-f", "lavfi", "-t", f"{total}", "-i", "anullsrc=r=44100:cl=stereo",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest",
                    "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, out)
    print(out)


if __name__ == "__main__":
    args = sys.argv[1:]
    prev = None
    if "--preview" in args:
        i = args.index("--preview")
        prev = args[i + 1]
        args = args[:i] + args[i + 2:]
    main(args[0], args[1], prev)
