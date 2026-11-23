# Owner's hook clip (first seconds, hook text on top) + designed body scenes from nq_reel + CTA.
# Usage: python3 nq_hookreel.py spec.json out.mp4 [--preview DIR]
# spec = nq_reel spec + {"src": clip, "hook_y": 1250}. The reel's own cover scene is replaced by the clip.
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nq_reel as R
import nq_clip as C
from nq_post import template_for

W, H, FPS = 1080, 1920, 30


def main(spec_path, out, preview=None):
    spec = json.load(open(spec_path, encoding="utf-8"))
    src = spec["src"]
    _, _, dur, has_audio = C.probe(src)
    t = template_for(spec, W, H)
    sc = R.scenes(spec)[1:]          # drop the designed cover; the clip is the hook
    work = out[:-4] + "_work"
    os.makedirs(work, exist_ok=True)
    acc = spec.get("accent", [255, 196, 64])
    hook = spec["hook"]
    C.panel([(hook["title"], "suez", 100, 400, (255, 255, 255), 1.1),
             (hook.get("subtitle", ""), "rubik", 54, 700, tuple(acc), 1.25)],
            spec.get("hook_y", 1250), acc).save(f"{work}/hook.png")
    C.brand().save(f"{work}/brand.png")
    if preview:
        os.makedirs(preview, exist_ok=True)
        t0 = dur
        for i, (d, slide, kind) in enumerate(sc):
            t.render(slide, kind, None, t0 + d).save(f"{preview}/scene{i + 2}.jpg", quality=90)
            t0 += d
    # 1) hook segment
    hk = f"{work}/hook.mp4"
    fc = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS}[v0];"
          f"[v0][1:v]overlay=0:0:shortest=1[v1];[v1][2:v]overlay=0:0:shortest=1[v]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-loop", "1", "-i", f"{work}/hook.png",
           "-loop", "1", "-i", f"{work}/brand.png"]
    if not has_audio:
        cmd += ["-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "0:a" if has_audio else "3:a", "-t", f"{dur}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k", hk]
    subprocess.run(cmd, check=True)
    if preview:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0", "-i", hk, "-frames:v", "1",
                        f"{preview}/scene1a.jpg"], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.3", "-i", hk, "-frames:v", "1",
                        f"{preview}/scene1b.jpg"], check=True)
    # 2) body scenes
    parts, t0 = [], dur
    for i, (d, slide, kind) in enumerate(sc):
        p = f"{work}/s{i}.mp4"
        R.encode(R.scene_frames(t, slide, kind, d, t0, False), p)
        parts.append(p)
        t0 += d
    body = f"{work}/body.mp4"
    with open(f"{work}/list.txt", "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    bdur = t0 - dur
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{work}/list.txt",
                    "-f", "lavfi", "-t", f"{bdur}", "-i", "anullsrc=r=44100:cl=stereo", "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{bdur}", body], check=True)
    # 3) join
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", hk, "-i", body, "-filter_complex",
                    "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], check=True)
    for f in os.listdir(work):
        os.remove(os.path.join(work, f))
    os.rmdir(work)
    print(out, f"{t0:.1f}s", "template:", t.name)


if __name__ == "__main__":
    a = sys.argv[1:]
    pv = a[a.index("--preview") + 1] if "--preview" in a else None
    main(a[0], a[1], pv)
