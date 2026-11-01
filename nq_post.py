# NQ Trader's single feed image (1080x1350) using the nq_design templates.
# Usage: python3 nq_post.py spec.json out.jpg
# spec: {"index": <running content number> | "template": "<name>", "variant": 0-2, "seed": 1,
#        "category", "title", "subtitle", "bullets": [...], "footer", "number"}
# Templates: noir_gold, ivory_editorial, glass_aurora, terminal_chart, velvet, bold_split.
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nq_design as D

W, H = 1080, 1350


def template_for(spec, w=W, h=H):
    seed = spec.get("seed", 7)
    if spec.get("template"):
        return D.make(spec["template"], w, h, spec.get("variant", 0), seed)
    return D.pick(spec.get("index", 0), w, h, seed)


def main(spec_path, out):
    s = json.load(open(spec_path, encoding="utf-8"))
    t = template_for(s)
    t.render(s, s.get("kind", "cover" if not s.get("bullets") else "item")).save(out, quality=93)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
