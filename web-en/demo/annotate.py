"""Annotated version of the paper figure: lettered regions (A–F) + a caption legend.

    python annotate.py      (after make_figure.js) -> figures/<name>-annotated.png + figures/<name>-legend.txt
    FIG_DIR=Amazon-Google python annotate.py   -> same, inside figures/Amazon-Google/
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures", os.environ.get("FIG_DIR", ""))  # FIG_DIR: optional subfolder (as in make_figure.js)
COLOR = (225, 29, 72)  # rose — not used anywhere in the UI, so callouts never blend with it
LEGEND = {
    "A": "Run configuration: data source (built-in or uploaded dataset with its trained model), explanation method (LEMON/SHAP or the TREATS baseline), stream parameters (pairs per increment, time budget τ) and advanced options (ranking top-k, max. increments, simulation mode).",
    "B": "Run header: dataset and algorithm, run parameters, progress with one segment per increment (green = processed within τ) and stream facts (increments, pairs processed, queue delay, elapsed time).",
    "C": "Indicators after the latest increment, with trend and change: Precision@20, the fairness metrics Bias@k, PPVP and TPRP (0 = parity), and the mean Explanation Score.",
    "D": "Evolution per increment: Precision@k, fairness metrics, Explanation Score, and processing time per step against the time budget τ.",
    "E": "Increment detail: time breakdown (matching, ranking, explanation, queue wait) and the global top-k after aggregation, with similarity, sensitive group, Explanation Score and ground truth.",
    "F": "Per-attribute explanation (cumulative): attribute weight (towards match/non-match) and potential score for each attribute of the left and right entities.",
}


def font(size):
    for f in ("segoeuib.ttf", "arialbd.ttf"):
        p = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", f)
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def annotate(name):
    meta = json.load(open(os.path.join(FIG, name + ".regions.json"), encoding="utf-8"))
    k = meta["scale"]
    im = Image.open(os.path.join(FIG, name + ".png")).convert("RGB")
    d = ImageDraw.Draw(im)
    f = font(int(22 * k))
    used = []
    for key in "ABCDEF":
        r = meta.get(key)
        if not r:
            continue
        used.append(key)
        x0, y0, x1, y1 = [v * k for v in (r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"])]
        d.rounded_rectangle([x0, y0, x1, y1], radius=int(16 * k), outline=COLOR, width=int(3 * k))
        R = 19 * k
        cx, cy = max(R + 4, x0 + 4 * k), max(R + 4, y0 + 4 * k)
        if key == "F":  # nested in E; its top-left corner sits on the section title, the top-right is empty
            cx = x1 - 4 * k
        d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=COLOR, outline=(255, 255, 255), width=int(3 * k))
        w = d.textlength(key, font=f)
        d.text((cx - w / 2, cy - 15 * k), key, font=f, fill=(255, 255, 255))
    out = os.path.join(FIG, name + "-annotated.png")
    im.save(out, optimize=True)
    with open(os.path.join(FIG, name + "-legend.txt"), "w", encoding="utf-8") as fh:
        fh.write("X-TREATS web console (run: %s · %s · %s).\n" % (meta["run"], meta["params"]["dataset"],
                 ["TREATS", "X-TREATS+LEMON", "X-TREATS+SHAP"][meta["params"]["algorithm"]]))
        for key in used:
            fh.write("(%s) %s\n" % (key, LEGEND[key]))
    print(out, im.size, "regions:", "".join(used))


if __name__ == "__main__":
    for name in ("x-treats-figure", "x-treats-figure-compact"):
        if os.path.isfile(os.path.join(FIG, name + ".regions.json")):
            annotate(name)
