# NQ Trader's Instagram carousel generator (wraps nq_post.py)
# Usage: python3 nq_carousel.py carousel.json out_dir name
# carousel.json: {"palette": "<name>", "seed": 1,
#   "slides": [{"category": "...", "title": "...", "subtitle": "...", "bullets": [...], "footer": "..."}, ...]}
# Writes out_dir/name-1.jpg ... name-N.jpg (2-10 slides, Instagram's carousel limit).
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nq_post


def main(spec_path, out_dir, name):
    c = json.load(open(spec_path, encoding="utf-8"))
    slides = c["slides"]
    if not 2 <= len(slides) <= 10:
        sys.exit("carousel needs 2-10 slides")
    os.makedirs(out_dir, exist_ok=True)
    for i, s in enumerate(slides, 1):
        spec = dict(s, palette=c.get("palette", "emerald"), seed=c.get("seed", 7))
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False)
        out = os.path.join(out_dir, f"{name}-{i}.jpg")
        nq_post.main(f.name, out)
        os.unlink(f.name)
        print(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
