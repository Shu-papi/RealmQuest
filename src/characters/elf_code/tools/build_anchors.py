#!/usr/bin/env python3
"""
Build ``assets/anchors.json`` - one registration point per sprite frame.

WHY THIS EXISTS
---------------
The PNG frames are tightly cropped, so every frame has a different canvas size
(attack frames are even larger because arrows / shard effects extend the canvas).
Drawing each PNG at the same top-left corner would make the character jitter and
slide. Instead, each frame gets an *anchor*: the pixel that must sit exactly on the
character's world position (her feet on the ground, horizontally centred on the
body).

HOW THE ANCHOR IS FOUND
-----------------------
1. Take the alpha mask of the frame.
2. Morphological *opening* removes thin things (bow string, arrow, shards, sparks).
3. The largest remaining blob is the character's body.
4. anchor_x = centroid of the body (stable even when the bow/arm swings),
   anchor_y = lowest body pixel (ground contact; boot tips are recovered).

Run (needs numpy, scipy, Pillow - NOT needed at game runtime):

    python tools/build_anchors.py            # writes assets/anchors.json
    python tools/build_anchors.py --preview  # also writes aligned contact sheets
                                             # to assets/_preview/ so you can check them

Anchors can be hand-edited afterwards; the game only reads the JSON.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ANIMATIONS = ["idle", "walk", "run", "quick_attack", "charge_attack"]
ALPHA_THRESHOLD = 40          # ignore near-invisible antialiasing fringe for detection
OPENING_SIZE = 9              # px; thinner features than this are not "body"
BOOT_RECOVERY = 6             # px; grow the body slightly to recover boot tips


def natural_key(path: Path) -> int:
    """Sort by the trailing frame number so 'xxx_02' < 'xxx_10'."""
    m = re.search(r"(\d+)\.png$", path.name, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def frame_files(anim: str) -> list[Path]:
    return sorted((ASSETS / anim).glob("*.png"), key=natural_key)


def find_anchor(path: Path) -> tuple[float, int]:
    alpha = np.array(Image.open(path).convert("RGBA"))[:, :, 3] > ALPHA_THRESHOLD
    core = ndimage.binary_opening(alpha, structure=np.ones((OPENING_SIZE,) * 2))
    if not core.any():                       # tiny/odd frame: fall back to full mask
        core = alpha
    labels, n = ndimage.label(core)
    sizes = ndimage.sum(core, labels, range(1, n + 1))
    body = labels == (int(np.argmax(sizes)) + 1)
    cx = float(np.where(body)[1].mean())
    region = ndimage.binary_dilation(body, iterations=BOOT_RECOVERY) & alpha
    bottom = int(np.where(region)[0].max())
    return round(cx, 1), bottom


def write_preview(anim: str, anchors: dict[str, list[float]]) -> None:
    """Draw every frame aligned on its anchor with a ground line, tiled in a grid."""
    files = frame_files(anim)
    imgs = [Image.open(f).convert("RGBA") for f in files]
    ax = [anchors[f.name][0] for f in files]
    ay = [anchors[f.name][1] for f in files]
    left = int(max(ax)) + 4
    right = int(max(i.width - a for i, a in zip(imgs, ax))) + 4
    up = int(max(ay)) + 4
    down = int(max(i.height - a for i, a in zip(imgs, ay))) + 4
    cw, ch = left + right, up + down
    cols = min(6, len(imgs))
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cw, rows * ch), (60, 62, 80, 255))
    draw = ImageDraw.Draw(sheet)
    for n, (img, a, b) in enumerate(zip(imgs, ax, ay)):
        ox, oy = (n % cols) * cw, (n // cols) * ch
        draw.line([(ox, oy + up), (ox + cw, oy + up)], fill=(255, 80, 80, 255))        # ground
        draw.line([(ox + left, oy), (ox + left, oy + ch)], fill=(80, 200, 255, 255))   # centre
        sheet.alpha_composite(img, (ox + left - int(round(a)), oy + up - b))
    out = ASSETS / "_preview"
    out.mkdir(exist_ok=True)
    sheet.save(out / f"{anim}_aligned.png")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preview", action="store_true", help="write aligned contact sheets to assets/_preview/")
    args = ap.parse_args()

    result: dict[str, dict[str, list[float]]] = {}
    for anim in ANIMATIONS:
        files = frame_files(anim)
        if not files:
            raise SystemExit(f"No PNG frames found in {ASSETS / anim}")
        result[anim] = {f.name: list(find_anchor(f)) for f in files}
        print(f"{anim:14s} {len(files):2d} frames")
        if args.preview:
            write_preview(anim, result[anim])

    (ASSETS / "anchors.json").write_text(json.dumps(result, indent=1))
    print(f"wrote {ASSETS / 'anchors.json'}")


if __name__ == "__main__":
    main()
