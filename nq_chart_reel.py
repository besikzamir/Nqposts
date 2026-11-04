# Candle-replay reel from REAL NQ data (e.g. the minutes around a CPI / NFP / ISM release).
# Usage: python3 nq_chart_reel.py chart.json out.mp4 [--preview DIR]
# chart.json: {"csv": "nq.csv",                       # time,open,high,low,close,volume (TradeZella get_market_data)
#   "event_time": "2026-11-06T15:30:00",              # candle where the marker goes (optional)
#   "event_label": "דוח התעסוקה 15:30",
#   "window": 15,                                     # minutes after the event used for the move stat
#   "hook": {"title": "...", "subtitle": "..."},
#   "cta": {"title": "...", "subtitle": "..."}}
# The move stat ("X נקודות ב-Y דקות") is computed from the CSV only, never typed by hand.
import csv, json, os, subprocess, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nq_design as D

W, H, FPS = 1080, 1920, 30
BG_TOP, BG_BOT = (14, 15, 20), (5, 6, 9)
UP, DN, GOLD = (38, 214, 140), (240, 72, 88), (232, 196, 120)
CX0, CX1, CY0, CY1 = 70, 900, 760, 1580  # chart box (price axis on the right)


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(l for l in f if not l.startswith("#") and l.strip()):
            rows.append({"t": r["time"], "o": float(r["open"]), "h": float(r["high"]),
                         "l": float(r["low"]), "c": float(r["close"])})
    return rows


def move_stat(rows, ev_idx, window):
    """Largest excursion from the pre-event close within `window` candles after the event."""
    ref = rows[ev_idx - 1]["c"] if ev_idx > 0 else rows[ev_idx]["o"]
    seg = rows[ev_idx: ev_idx + window]
    hi = max(seg, key=lambda r: r["h"])
    lo = min(seg, key=lambda r: r["l"])
    up, dn = hi["h"] - ref, ref - lo["l"]
    if up >= dn:
        return "+", up, seg.index(hi) + 1
    return "-", dn, seg.index(lo) + 1


def background():
    bg = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        a = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(t * (1 - a) + b * a) for t, b in zip(BG_TOP, BG_BOT)))
    for i in range(6):
        y = CY0 + (CY1 - CY0) * i / 5
        d.line([(CX0, y), (CX1, y)], fill=(30, 32, 40), width=1)
    bg = bg.convert("RGBA")
    bg.alpha_composite(D.Text(W, ["NQ TRADER'S"], D.F("rubik", 28, 700), (255, 255, 255, 200), 30, "r", 70, track=5).img, (0, 150))
    bg.alpha_composite(D.Text(W, ["NQ 1M  |  נתונים אמיתיים"], D.F("rubik", 30, 500), (255, 255, 255, 120), 34, "l", 70).img, (0, CY1 + 40))
    bg.alpha_composite(D.Text(W, ["@nq_tradersss"], D.F("rubik", 30, 600), (255, 255, 255, 170), 34, "c").img, (0, H - 200))
    return bg


def text_block(title, subtitle, y, tsize=100):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    f, lines, sz = D.fit(title, "suez", 400, tsize, W - 160, 2, 56)
    t = D.Text(W, lines, f, (255, 255, 255), int(sz * 1.08), "r", 80).img
    layer.alpha_composite(t, (0, y))
    if subtitle:
        s = D.Text(W, D.wrap(subtitle, D.F("rubik", 46, 700), W - 160), D.F("rubik", 46, 700), GOLD, 58, "r", 80).img
        layer.alpha_composite(s, (0, y + t.height + 6))
    return layer


def chart(rows, n_vis, partial, lo, hi, ev_idx, ev_label, stat_layer):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    n = len(rows)
    step = (CX1 - CX0) / n
    bw = max(3, int(step * 0.62))
    py = lambda p: CY1 - (p - lo) / (hi - lo) * (CY1 - CY0)
    for i in range(6):
        p = lo + (hi - lo) * i / 5
        d.text((CX1 + 14, py(p)), f"{p:,.0f}", font=D.F("rubik", 24, 500), fill=(150, 152, 160), anchor="lm")
    if ev_idx is not None and n_vis > ev_idx:
        x = CX0 + step * (ev_idx + 0.5)
        for yy in range(CY0 - 20, CY1, 18):
            d.line([(x, yy), (x, yy + 9)], fill=GOLD, width=3)
        lab = D.Text(W, [ev_label], D.F("rubik", 34, 700), GOLD, 40, "c").img
        lb = lab.getbbox()
        if lb:
            crop = lab.crop(lb)
            img.alpha_composite(crop, (int(min(max(x - crop.width / 2, 20), W - crop.width - 20)), CY0 - 58))
    for i in range(min(n_vis, n)):
        r = rows[i]
        c = r["c"]
        hgt_frac = partial if i == n_vis - 1 else 1.0
        if i == n_vis - 1:  # last candle "ticks" toward its close
            c = r["o"] + (r["c"] - r["o"]) * hgt_frac
        col = UP if c >= r["o"] else DN
        x = CX0 + step * (i + 0.5)
        hi_p = max(r["o"], c) + (r["h"] - max(r["o"], r["c"])) * hgt_frac
        lo_p = min(r["o"], c) - (min(r["o"], r["c"]) - r["l"]) * hgt_frac
        d.line([(x, py(hi_p)), (x, py(lo_p))], fill=col, width=2)
        y0, y1 = sorted([py(r["o"]), py(c)])
        d.rectangle([x - bw / 2, y0, x + bw / 2, max(y1, y0 + 2)], fill=col)
    if stat_layer is not None:
        img.alpha_composite(stat_layer)
    return img


def main(spec_path, out, preview=None):
    spec = json.load(open(spec_path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(spec_path))
    rows = load(spec["csv"] if os.path.isabs(spec["csv"]) else os.path.join(base, spec["csv"]))
    ev_idx = next((i for i, r in enumerate(rows) if r["t"].startswith(spec.get("event_time", "~"))), None)
    lo = min(r["l"] for r in rows)
    hi = max(r["h"] for r in rows)
    pad = (hi - lo) * 0.08
    lo, hi = lo - pad, hi + pad
    stat_layer, stat_txt = None, None  # filled only when the event candle is in the data
    if ev_idx is not None:
        sign, pts, mins = move_stat(rows, ev_idx, int(spec.get("window", 15)))
        stat_txt = f"{'זינוק' if sign == '+' else 'צניחה'} של {pts:,.0f} נקודות ב-{mins} דקות"
        stat_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        f, _, _ = D.fit(stat_txt, "suez", 400, 72, W - 220, 1, 40)
        t = D.Text(W, [stat_txt], f, UP if sign == "+" else DN, 90, "c").img
        card = Image.new("RGBA", (W - 160, t.height + 40), (0, 0, 0, 0))
        ImageDraw.Draw(card).rounded_rectangle([0, 0, card.width - 1, card.height - 1], 30, fill=(8, 9, 12, 225),
                                               outline=GOLD, width=3)
        stat_layer.alpha_composite(card, (80, CY0 + 20))
        stat_layer.alpha_composite(t, (0, CY0 + 40))
    bg = background()
    hook = text_block(spec["hook"]["title"], spec["hook"].get("subtitle", ""), 240)
    cta = spec["cta"]
    cta_l = Image.new("RGBA", (W, H), (0, 0, 0, 170))
    cta_l.alpha_composite(text_block(cta["title"], cta.get("subtitle", ""), 980, 104))

    n = len(rows)
    replay = 9.0
    hold = 2.6 if stat_layer is not None else 1.2
    end = 2.4
    total = replay + hold + end
    nf = int(total * FPS)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-f", "lavfi", "-t", f"{total}", "-i", "anullsrc=r=44100:cl=stereo",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac",
                          "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    keep = {0, int(replay * FPS * 0.6), int((replay + 0.8) * FPS), nf - 10}
    if preview:
        os.makedirs(preview, exist_ok=True)
    # the first frame already shows a third of the chart so the hook frame is not empty
    first = max(3, n // 3)
    for fi in range(nf):
        ts = fi / FPS
        prog = min(1.0, ts / replay)
        vis_f = first + (n - first) * prog
        n_vis = min(n, int(vis_f) + 1)
        partial = 1.0 if prog >= 1 else vis_f - int(vis_f)
        frame = bg.copy()
        frame.alpha_composite(hook)
        frame.alpha_composite(chart(rows, n_vis, partial, lo, hi, ev_idx, spec.get("event_label", ""),
                                    stat_layer if ts >= replay else None))
        if ts >= replay + hold:
            a = min(1.0, (ts - replay - hold) / 0.25)
            c = cta_l.copy()
            c.putalpha(c.getchannel("A").point(lambda v: int(v * a)))
            frame.alpha_composite(c)
        rgb = frame.convert("RGB")
        p.stdin.write(rgb.tobytes())
        if preview and fi in keep:
            rgb.save(f"{preview}/chart{sorted(keep).index(fi) + 1}.jpg", quality=88)
    p.stdin.close()
    if p.wait() != 0:
        sys.exit("ffmpeg failed")
    print(f"{out}: {total:.1f}s" + (f" | stat: {stat_txt}" if stat_txt else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[a.index("--preview") + 1] if "--preview" in a else None)
