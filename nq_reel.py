# NQ Trader's Instagram Reel (1080x1920, 30fps) using the nq_design templates.
# Usage: python3 nq_reel.py reel.json out.mp4 [--preview DIR] [--music file.m4a]
# reel.json: {"index": <running content number> | "template": "<name>", "variant": 0-2, "seed": 1,
#   "hook": {"category", "title", "subtitle"},
#   "items": [{"title", "text"}, ...],          # 2-5 items
#   "item_label": "טעות",                        # footer "<label> 1 מתוך 3"
#   "cta": {"title", "subtitle", "footer"}}
# Without --music a silent AAC track is added (Instagram expects an audio stream).
import json, os, subprocess, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nq_post import template_for
import nq_design as D

D.SCALE = 1.22

W, H, FPS = 1080, 1920, 30


def scenes(spec):
    # short and punchy: viewers decide in the first 1-2 seconds (hook is fully on screen at frame 1)
    out = [(2.4, dict(spec["hook"], bullets=[]), "cover")]
    n = len(spec["items"])
    label = spec.get("item_label", "טיפ")
    for i, it in enumerate(spec["items"]):
        out.append((3.4, {"number": f"0{i + 1}", "title": it["title"], "subtitle": it.get("text", ""),
                          "bullets": [], "footer": f"{label} {i + 1} מתוך {n}"}, "item"))
    c = spec["cta"]
    out.append((2.6, {"title": c["title"], "subtitle": c.get("subtitle", ""), "bullets": [],
                      "footer": c.get("footer", "תוכן חדש כל בוקר ב-10:00")}, "cta"))
    return out


def encode(frames, path):
    tmp = path[:-4] + ".part.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                          "-crf", "19", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for im in frames:
        p.stdin.write(im.tobytes())
    p.stdin.close()
    if p.wait() != 0:
        sys.exit(f"ffmpeg failed on {path}")
    os.replace(tmp, path)


def scene_frames(t, slide, kind, dur, t0, first):
    els = t.elements(slide, kind)
    for f in range(int(round(dur * FPS))):
        ts = f / FPS
        # the hook scene starts fully drawn so the first frame already carries the message
        img = t.render(slide, kind, None if first else ts, t0 + ts, els)
        if not first and ts < 0.2:  # quick dip from the bare background, inside the scene file
            img = Image.blend(t.background(t0 + ts).convert("RGB"), img, ts / 0.2)
        yield img


def main(spec_path, out, preview_dir=None, music=None):
    spec = json.load(open(spec_path, encoding="utf-8"))
    t = template_for(spec, W, H)
    sc = scenes(spec)
    if preview_dir:
        os.makedirs(preview_dir, exist_ok=True)
        t0 = 0.0
        for i, (dur, slide, kind) in enumerate(sc):
            t.render(slide, kind, None, t0 + dur).save(os.path.join(preview_dir, f"scene{i + 1}.jpg"), quality=90)
            t0 += dur
        print("template:", t.name)
        return
    work = out[:-4] + "_scenes"
    os.makedirs(work, exist_ok=True)
    parts, t0 = [], 0.0
    for i, (dur, slide, kind) in enumerate(sc):
        part = os.path.join(work, f"s{i}.mp4")
        encode(scene_frames(t, slide, kind, dur, t0, i == 0), part)
        parts.append(part)
        t0 += dur
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    tmp = out[:-4] + ".part.mp4"
    if music:
        audio = ["-stream_loop", "-1", "-i", music]
        af = ["-af", f"afade=t=in:d=0.8,afade=t=out:st={t0 - 1.5}:d=1.5"]
    else:
        audio = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        af = []
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, *audio,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", *af, "-c:a", "aac", "-b:a", "192k",
                    "-t", f"{t0}", "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, out)
    for p in parts:
        os.unlink(p)
    os.unlink(lst)
    os.rmdir(work)
    print(out, "template:", t.name)


if __name__ == "__main__":
    args = sys.argv[1:]
    opts = {}
    for flag in ("--preview", "--music"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            args = args[:i] + args[i + 2:]
    main(args[0], args[1], opts.get("--preview"), opts.get("--music"))
