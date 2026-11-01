# NQ Trader's Instagram carousel (1080x1350 slides) using one nq_design template for the whole set.
# Usage: python3 nq_carousel.py carousel.json out_dir name
# carousel.json: {"index": <running content number> | "template": "<name>", "variant": 0-2, "seed": 1,
#   "slides": [{"category", "title", "subtitle", "bullets": [...], "footer", "number"}, ...]}
# First slide renders as a cover, last as a closing slide, the rest as items.
# Writes out_dir/name-1.jpg ... name-N.jpg (2-10 slides).
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nq_post import template_for


def main(spec_path, out_dir, name):
    c = json.load(open(spec_path, encoding="utf-8"))
    slides = c["slides"]
    if not 2 <= len(slides) <= 10:
        sys.exit("carousel needs 2-10 slides")
    t = template_for(c)
    os.makedirs(out_dir, exist_ok=True)
    for i, s in enumerate(slides, 1):
        kind = "cover" if i == 1 else "cta" if i == len(slides) else "item"
        out = os.path.join(out_dir, f"{name}-{i}.jpg")
        t.render(s, kind).save(out, quality=93)
        print(out)
    print("template:", t.name, "variant:", t.variants.index(t.v))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
