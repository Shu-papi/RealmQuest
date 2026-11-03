"""
import_knight_sheets.py - turns the hand-made Warrior frame grids into game frames.

Used by tools/generate_knight_sprites.py (run that one - it calls this automatically):
    python tools/generate_knight_sprites.py

Input : assets/characters/source/knight_run_sheet.png      16 run frames, 5 per row, 256x256 cells
        assets/characters/source/knight_attack_sheet.png   22 sword-strike frames, 5 per row, 512x512 cells
Output: frames trimmed to their pixels and packed into knight_spritesheet.png (below the
        75x70 idle/hurt/dead cells). Every frame gets its own "pivot" in the manifest so the
        knight's feet stay put even though the frames are different sizes.

TUNING (everything an artist may want to change is in SOURCES below):
    scale     - size on screen. 0.5 makes the 512px attack cells ~46px tall, like the old knight.
    anchor    - (x, y) *inside the source cell* that lines up with the player: x = middle of the
                body, y = the bottom row of the planted feet. Same for every frame of a sheet.
    durations - milliseconds per frame (one number = all frames the same).
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR = os.path.join(ROOT, "assets", "characters", "source")

SOURCES = {
    "run": {
        "file": "knight_run_sheet.png", "cell": 256, "cols": 5, "count": 16,
        "scale": 0.42, "anchor": (126, 193),
        "durations": 35, "loop": True,              # 16 frames x 35 ms = one stride in 0.56 s
    },
    "attack": {
        "file": "knight_attack_sheet.png", "cell": 512, "cols": 5, "count": 22,
        "scale": 0.50, "anchor": (250, 433),
        # ready, wind-up (2-8), slash (9), impact burst (10-14), recovery (15-21) = 0.735 s,
        # just under the warrior's 0.8 s attack cooldown so a swing never gets cut off.
        "durations": [25, 25] + [30] * 7 + [30] + [40] * 5 + [35] * 7,
        "loop": False,
    },
}


def _resize(img, size):
    """Resize with premultiplied alpha so transparent pixels don't leave dark/white halos."""
    return img.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")


def load_frames(name, spec, feet_below_pivot):
    """-> list of (trimmed RGBA image, (pivot_x, pivot_y) inside that image)."""
    sheet = Image.open(os.path.join(SOURCE_DIR, spec["file"])).convert("RGBA")
    cell = spec["cell"]
    out_cell = max(1, round(cell * spec["scale"]))
    k = out_cell / cell                                   # exact scale actually applied
    ax, ay = round(spec["anchor"][0] * k), round(spec["anchor"][1] * k)
    px_cell, py_cell = ax, ay - feet_below_pivot          # player's pivot, in scaled-cell pixels
    frames = []
    for i in range(spec["count"]):
        col, row = i % spec["cols"], i // spec["cols"]
        box = (col * cell, row * cell, (col + 1) * cell, (row + 1) * cell)
        img = _resize(sheet.crop(box), (out_cell, out_cell))
        bbox = img.getchannel("A").point(lambda a: 255 if a > 0 else 0).getbbox()
        if bbox is None:
            raise ValueError(f"{spec['file']}: frame {i} (row {row}, col {col}) is empty - "
                             f"check 'cell', 'cols' and 'count' for '{name}' in SOURCES")
        frames.append((img.crop(bbox), (px_cell - bbox[0], py_cell - bbox[1])))
    return frames


def _durations(spec):
    d = spec["durations"]
    if isinstance(d, list):
        assert len(d) == spec["count"], f"{spec['file']}: need {spec['count']} durations"
    return d


def build(sheet_width, start_y, feet_below_pivot):
    """Pack every imported frame below `start_y` on a sheet `sheet_width` wide.

    Returns (sheet_part, rects, animations, strips):
        sheet_part  RGBA image, sheet_width x (rows used) - paste it at (0, start_y)
        rects       {frame name: {"x", "y", "w", "h", "pivot": [px, py]}}  (y already offset)
        animations  {name: manifest entry}
        strips      {name: preview strip image, frames side by side, feet aligned}
    """
    packed, rects, animations, strips = [], {}, {}, {}
    x = y = shelf_h = 0
    gap = 1
    for name, spec in SOURCES.items():
        frames = load_frames(name, spec, feet_below_pivot)
        names = []
        for i, (img, pivot) in enumerate(frames):
            if x + img.width > sheet_width:               # next shelf
                x, y, shelf_h = 0, y + shelf_h + gap, 0
            fname = f"{name}_{i}"
            packed.append((img, x, y))
            rects[fname] = {"x": x, "y": start_y + y, "w": img.width, "h": img.height,
                            "pivot": list(pivot)}
            names.append(fname)
            x += img.width + gap
            shelf_h = max(shelf_h, img.height)
        animations[name] = {"frames": names, "frame_duration_ms": _durations(spec),
                            "loop": spec["loop"]}

        # preview strip: every cell as big as the largest frame, pivots lined up
        left = max(p[0] for _, p in frames)
        right = max(img.width - p[0] for img, p in frames)
        up = max(p[1] for _, p in frames)
        down = max(img.height - p[1] for img, p in frames)
        cw, ch = left + right, up + down
        strip = Image.new("RGBA", (cw * len(frames), ch), (0, 0, 0, 0))
        for i, (img, p) in enumerate(frames):
            strip.alpha_composite(img, (i * cw + left - p[0], up - p[1]))
        strips[name] = strip

    part = Image.new("RGBA", (sheet_width, y + shelf_h), (0, 0, 0, 0))
    for img, px, py in packed:
        part.alpha_composite(img, (px, py))
    return part, rects, animations, strips
