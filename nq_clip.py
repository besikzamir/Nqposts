# Turn the owner's raw clip (screen recording, phone video, PNL clip) into a branded 9:16 reel.
# Usage: python3 nq_clip.py clip.json out.mp4 [--preview DIR]
# clip.json: {"src": "raw.mp4", "start": 0, "end": null,          # optional trim in seconds
#   "hook": {"title": "...", "subtitle": "..."},                 # on screen from frame 1 for hook_secs
#   "hook_secs": 3.0,
#   "notes": [{"t0": 3.5, "t1": 7, "text": "..."}],              # optional timed on-screen lines
#   "cta": {"title": "...", "subtitle": "..."},                  # 2.2s end card over a frozen last frame
#   "accent": [255, 196, 64]}
# Landscape/square sources sit in the middle over a blurred fill; portrait sources are cropped to fill.
# The original audio is kept (a silent track is added if there is none).
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nq_design as D

W, H = 1080, 1920
MAXW = W - 140


def probe(src):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                          "-of", "json", src], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in j["streams"])
    return v["width"], v["height"], float(j["format"]["duration"]), has_audio


def panel(lines_spec, y, accent, top_pad=34):
    """Dark rounded card holding stacked RTL text blocks; returns an RGBA canvas-sized layer."""
    blocks = []
    for text, font, size, weight, color, lh in lines_spec:
        f, lines, sz = D.fit(text, font, weight, size, MAXW - 60, 3, 40)
        blocks.append(D.Text(W, lines, f, color, int(sz * lh), "c").img)
    hgt = sum(b.height for b in blocks) + top_pad * 2
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    card = Image.new("RGBA", (W - 80, hgt), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, card.width - 1, hgt - 1], 36, fill=(10, 10, 14, 215))
    ImageDraw.Draw(card).rectangle([60, 0, card.width - 60, 6], fill=tuple(accent) + (255,))
    layer.alpha_composite(card, (40, y))
    cy = y + top_pad
    for b in blocks:
        layer.alpha_composite(b, (0, cy))
        cy += b.height
    return layer


def brand():
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    t = D.Text(W, ["@nq_tradersss"], D.F("rubik", 34, 600), (255, 255, 255, 210), 40, "c", stroke=0).img
    sh = t.copy()
    sh.putalpha(t.getchannel("A").filter(ImageFilter.GaussianBlur(6)))
    layer.alpha_composite(sh, (0, H - 190))
    layer.alpha_composite(t, (0, H - 190))
    return layer


def build(spec, out, preview=None):
    src = spec["src"]
    w, h, dur, has_audio = probe(src)
    start = float(spec.get("start") or 0)
    end = float(spec.get("end") or dur)
    clip_len = end - start
    acc = spec.get("accent", [255, 196, 64])
    tmp = os.path.splitext(out)[0] + "_ov"
    os.makedirs(tmp, exist_ok=True)

    hook = spec["hook"]
    hs = float(spec.get("hook_secs", 3.0))
    hook_l = panel([(hook["title"], "suez", 96, 400, (255, 255, 255), 1.1),
                    (hook.get("subtitle", ""), "rubik", 50, 700, tuple(acc), 1.25)], 230, acc)
    hook_l.save(f"{tmp}/hook.png")
    brand().save(f"{tmp}/brand.png")
    notes = []
    for i, n in enumerate(spec.get("notes") or []):
        p = f"{tmp}/note{i}.png"
        panel([(n["text"], "rubik", 54, 700, (255, 255, 255), 1.25)], 1380, acc, 26).save(p)
        notes.append((p, float(n["t0"]), float(n["t1"])))
    cta = spec["cta"]
    cta_l = Image.new("RGBA", (W, H), (0, 0, 0, 150))
    cta_l.alpha_composite(panel([(cta["title"], "suez", 96, 400, (255, 255, 255), 1.1),
                                 (cta.get("subtitle", ""), "rubik", 50, 700, tuple(acc), 1.25),
                                 ("תוכן חדש כל בוקר ב-10:00", "rubik", 34, 500, (255, 255, 255, 170), 1.3)],
                                760, acc))
    cta_l.save(f"{tmp}/cta.png")

    portrait = h / w > 1.5
    if portrait:
        base = f"[0:v]trim={start}:{end},setpts=PTS-STARTPTS,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[v0]"
    else:
        base = (f"[0:v]trim={start}:{end},setpts=PTS-STARTPTS,split[a][b];"
                f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:3,eq=brightness=-0.18[bg];"
                f"[b]scale={W}:-2[fg];[bg][fg]overlay=0:(H-h)/2,setsar=1[v0]")
    inputs = ["-i", src, "-loop", "1", "-i", f"{tmp}/hook.png", "-loop", "1", "-i", f"{tmp}/brand.png"]
    fc = [base, f"[v0][2:v]overlay=0:0:shortest=1[v1]",
          f"[1:v]fade=t=out:st={hs - 0.3}:d=0.3:alpha=1[hk]", f"[v1][hk]overlay=0:0:shortest=1:enable='lt(t,{hs})'[v2]"]
    last, k = "v2", 3
    for p, t0, t1 in notes:
        inputs += ["-loop", "1", "-i", p]
        fc.append(f"[{last}][{k}:v]overlay=0:0:shortest=1:enable='between(t,{t0},{t1})'[n{k}]")
        last, k = f"n{k}", k + 1
    # end card: freeze the last frame for 2.2s under the CTA
    inputs += ["-loop", "1", "-i", f"{tmp}/cta.png"]
    fc.append(f"[{last}]tpad=stop_mode=clone:stop_duration=2.2,fps=30[vp]")
    fc.append(f"[{k}:v]fade=t=in:st=0:d=0.25:alpha=1,setpts=PTS+{clip_len}/TB[ct]")
    fc.append(f"[vp][ct]overlay=0:0:shortest=1:enable='gte(t,{clip_len})'[vout]")
    total = clip_len + 2.2
    if has_audio:
        fc.append(f"[0:a]atrim={start}:{end},asetpts=PTS-STARTPTS,apad=whole_dur={total}[aout]")
        amap = ["-map", "[aout]"]
    else:
        inputs += ["-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=44100:cl=stereo"]
        amap = ["-map", f"{k + 1}:a"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error"] + inputs + ["-filter_complex", ";".join(fc), "-map", "[vout]"] + amap + \
          ["-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-r", "30", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    if preview:
        os.makedirs(preview, exist_ok=True)
        times = [0.0, min(hs + 0.5, clip_len - 0.1)] + [(t0 + t1) / 2 for _, t0, t1 in notes] + [total - 0.5]
        for i, t in enumerate(times):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", out, "-frames:v", "1",
                            f"{preview}/clip{i + 1}.jpg"], check=True)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    print(f"{out}: {total:.1f}s")


if __name__ == "__main__":
    a = sys.argv[1:]
    prev = a[a.index("--preview") + 1] if "--preview" in a else None
    spec = json.load(open(a[0], encoding="utf-8"))
    if not os.path.isabs(spec["src"]):
        spec["src"] = os.path.join(os.path.dirname(os.path.abspath(a[0])), spec["src"])
    build(spec, a[1], prev)
