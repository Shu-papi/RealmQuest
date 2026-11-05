"""
tools/build_minotaur_sprites.py - Builds the Minotaur's in-game sprites from the template painting.

    python tools/build_minotaur_sprites.py            writes the 4 PNGs + sprite.json into assets/bosses/minotaur/
    python tools/build_minotaur_sprites.py --sheet    also writes tools/minotaur_sheet.png (8x zoom, for review)

Template:  tools/reference/minotaur_template.png  (the hunched Minotaur painting)

What the script does
    1. Removes the axe (blade + handle) from the template, leaving the clenched fist.
    2. Shrinks the painting to a 56 x 56 pixel-art sprite (the game draws every pixel as a 4 x 4
       block, so he is 224 x 224 on screen), brightens and sharpens it so it reads on the dark
       arena floor, limits it to ~32 colours and adds a 1 pixel dark outline.
    3. Paints the details that vanish when shrinking: the red eyes and the mouth.
    4. Phase 2 (enraged, below 50% HP): crimson fur, white-hot eyes and lava cracks.
    5. Frame B of each phase: the upper body sinks 1 pixel (a heavy breath / stomp).
    6. Two extra poses per phase, made by rotating the arms of the painting around the shoulders:
         pose_raise_*  both fists overhead (used while he winds up a slam or calls down rocks)
         pose_cast_*   arms flung wide (used while he roars and casts)
       All frames share one colour palette so nothing flickers when the game switches between them.
    7. An 8-frame WALK cycle (walk_phase*.png, frames side by side): the legs of the painting swing
       from the hips and lift, one after the other. The game picks the frame from how far he has
       actually moved, so his feet do not skate.
    8. BACK VIEWS (back_*, pose_*_back_*, walk_back_*) for isometric play, where he sometimes faces
       away from the camera. Made from the front art: the face and the belt emblem are painted out,
       the colours are darkened and a mane of fur tufts is added. They are an approximation:
       paint real back views over those files if you want them to look better.

The result is plain PNG, so you can keep editing it by hand in any pixel editor. Re-running this
script OVERWRITES those files, so only re-run it if you want to start over from the template.
"""
import json
import math
import os
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "reference", "minotaur_template.png")
OUT_DIR = os.path.join(os.path.dirname(HERE), "assets", "bosses", "minotaur")

SIZE = 56                  # final canvas is SIZE x SIZE
MARGIN = 1                 # empty border so the outline fits
COLOURS = 32
OUTLINE = (26, 16, 20)

SPRITE_JSON = {
    "scale": 4,
    "anchor": [28, 30],
    "shadow": {"y": 24, "widths": [34, 44, 34]},
    "bob": 1.0,
}

# ---------------------------------------------------------------------------
# 1. take the axe out of the template
# ---------------------------------------------------------------------------


def remove_axe(path=TEMPLATE):
    from PIL import ImageDraw
    a = np.array(Image.open(path).convert("RGBA")).astype(int)
    h, w = a.shape[:2]
    r, b, alpha = a[..., 0], a[..., 2], a[..., 3]

    zone = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(zone)
    draw.polygon([(318, 160), (w, 160), (w, h), (318, h)], fill=255)          # the blade
    draw.line([(262, 138), (335, 172), (410, 222)], fill=255, width=22)       # the handle
    in_zone = np.array(zone) > 0
    bluish = b >= r - 2                       # the axe is blue-grey / navy, the fur is red-brown
    axe = in_zone & bluish & (alpha > 0)
    axe[:150, 300:] = False                   # keep the steel bracer on the right wrist
    a[axe, 3] = 0

    # throw away the stray dots the handle leaves behind (anything not part of the main body)
    solid = a[..., 3] > 0
    label = np.zeros((h, w), int)
    sizes, count = {}, 0
    for y in range(h):
        for x in range(w):
            if solid[y, x] and not label[y, x]:
                count += 1
                label[y, x] = count
                queue, size = deque([(y, x)]), 0
                while queue:
                    cy, cx = queue.popleft()
                    size += 1
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and solid[ny, nx] and not label[ny, nx]:
                                label[ny, nx] = count
                                queue.append((ny, nx))
                sizes[count] = size
    small = [k for k, v in sizes.items() if v <= 60]
    a[np.isin(label, small), 3] = 0
    return Image.fromarray(a.astype(np.uint8))


# ---------------------------------------------------------------------------
# 2. shrink to game size
# ---------------------------------------------------------------------------


def _square_crop(img, box=None):
    """Crop to `box` (the base pose's bounding box, so every pose is shrunk identically)."""
    crop = img.crop(box or img.getchannel("A").getbbox())
    w, h = crop.size
    side = max(w, h)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(crop, ((side - w) // 2, side - h))
    return square


def _box_down(img, n):
    arr = np.array(img).astype(np.float32)
    cover = arr[..., 3] / 255.0
    premult = arr[..., :3] * cover[..., None]

    def shrink(plane):
        return np.array(Image.fromarray(plane.astype(np.float32), mode="F").resize((n, n), Image.BOX))

    colour = np.stack([shrink(premult[..., i]) for i in range(3)], -1)
    cover = shrink(cover)
    colour = np.where(cover[..., None] > 0.01, colour / np.maximum(cover[..., None], 1e-3), 0)
    return np.clip(colour, 0, 255).astype(np.uint8), cover


def _grade(rgb, cover):
    """Bleed colour into empty pixels, sharpen, saturate and lift the shadows."""
    arr = rgb.astype(np.float32)
    filled = cover > 0.42
    for _ in range(3):
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            moved = np.roll(np.roll(arr, dy, 0), dx, 1)
            moved_ok = np.roll(np.roll(filled, dy, 0), dx, 1)
            take = ~filled & moved_ok
            arr[take] = moved[take]
            filled = filled | take
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    img = img.filter(ImageFilter.UnsharpMask(1.2, 180, 2))
    img = ImageEnhance.Color(img).enhance(1.15)
    out = (np.array(img).astype(np.float32) / 255.0) ** 0.88
    return (out * 255).astype(np.uint8)


def shrink_to_sprite(template, box=None, palette=None):
    """Returns (sprite, palette). Pass the first sprite's palette back in to share colours."""
    inner = SIZE - 2 * MARGIN
    rgb, cover = _box_down(_square_crop(template, box), inner)
    rgb = _grade(rgb, cover)
    if palette is None:
        quant = Image.fromarray(rgb).quantize(colors=COLOURS, method=Image.Quantize.MEDIANCUT,
                                              dither=Image.Dither.NONE)
        colours = np.array(quant.getpalette()[:COLOURS * 3], np.int32).reshape(-1, 3)
        used = sorted(set(quant.getdata()))
        palette = colours[used]
    flat = rgb.reshape(-1, 3).astype(np.int32)
    distance = ((flat[:, None, :] - palette[None, :, :]) ** 2).sum(-1)
    mapped = palette[distance.argmin(1)].reshape(rgb.shape).astype(np.uint8)
    out = np.zeros((SIZE, SIZE, 4), np.uint8)
    out[MARGIN:SIZE - MARGIN, MARGIN:SIZE - MARGIN, :3] = mapped
    out[MARGIN:SIZE - MARGIN, MARGIN:SIZE - MARGIN, 3] = np.where(cover > 0.42, 255, 0)
    return add_outline(Image.fromarray(out)), palette


def add_outline(img, colour=OUTLINE):
    a = np.array(img)
    solid = a[..., 3] > 0
    grown = np.zeros_like(solid)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        grown |= np.roll(np.roll(solid, dy, 0), dx, 1)
    a[grown & ~solid] = colour + (255,)
    return Image.fromarray(a)


# ---------------------------------------------------------------------------
# 3 + 4. details, and the enraged phase 2
# ---------------------------------------------------------------------------

EYES_1 = {(23, 9): (236, 44, 56), (24, 9): (236, 44, 56),
          (28, 10): (236, 44, 56), (29, 10): (236, 44, 56)}
MOUTH_1 = {(23, 18): (226, 56, 72), (24, 17): (236, 80, 96), (23, 17): (150, 24, 44)}

EYES_2 = {(23, 9): (255, 240, 170), (24, 9): (255, 214, 110),
          (22, 9): (214, 60, 36), (25, 9): (214, 60, 36),
          (28, 10): (255, 214, 110), (29, 10): (255, 240, 170),
          (27, 10): (214, 60, 36), (30, 10): (214, 60, 36)}
MOUTH_2 = {(23, 18): (255, 120, 60), (24, 17): (255, 190, 100), (23, 17): (214, 60, 36)}
CRACKS_2 = {(31, 21): (214, 70, 34), (31, 22): (255, 150, 60), (32, 23): (214, 70, 34),
            (32, 24): (255, 214, 120), (33, 25): (255, 150, 60), (33, 26): (214, 70, 34),
            (34, 27): (255, 150, 60), (31, 25): (214, 70, 34), (30, 26): (255, 150, 60),
            (44, 15): (214, 70, 34), (45, 16): (255, 150, 60), (44, 17): (214, 70, 34)}


def paint(img, pixels, only_solid=False):
    a = np.array(img)
    for (x, y), colour in pixels.items():
        if only_solid and a[y, x, 3] == 0:
            continue
        a[y, x] = colour + (255,)
    return Image.fromarray(a)


def enrage(img):
    """Phase 2 colours: brown fur turns crimson. Bone horns, steel and cloth keep their look."""
    hsv = np.array(img.convert("RGB").convert("HSV")).astype(np.float32)
    alpha = np.array(img)[..., 3]
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    furry = (hue < 30) & (sat > 60)                                   # orange/brown hues
    bright = np.clip((val - 150) / 70.0, 0, 1)                        # bright pixels = horns, keep them pale
    hue = np.where(furry, hue - 15.0 * (1 - bright) + 0, hue)
    sat = np.where(furry, np.clip(sat * (1.12 + 0.1 * (1 - bright)), 0, 255), sat)
    val = np.where(furry, val * (0.92 + 0.08 * bright), val)
    hsv = np.stack([np.mod(hue, 256), sat, val], -1).astype(np.uint8)
    out = np.array(Image.fromarray(hsv, "HSV").convert("RGB"))
    out = np.dstack([out, alpha])
    return Image.fromarray(out)


def sink(img, seam=40):
    """Frame B: everything above `seam` drops one pixel; hooves stay planted."""
    a = np.array(img)
    b = np.zeros_like(a)
    b[1:seam + 1] = a[0:seam]
    b[seam + 1:] = a[seam + 1:]
    return Image.fromarray(b)


# ---------------------------------------------------------------------------
# 6. poses: rotate the arms of the painting around the shoulders
# ---------------------------------------------------------------------------

LEFT_ARM = [(60, 100), (128, 90), (168, 92), (190, 110), (186, 142), (150, 150), (112, 166), (60, 166)]
RIGHT_ARM = [(286, 92), (330, 90), (356, 108), (362, 152), (354, 198), (316, 200), (302, 178), (288, 140), (272, 112)]
LEFT_SHOULDER, RIGHT_SHOULDER = (176, 118), (290, 104)
POSES = {                       # name: (left arm degrees, right arm degrees); positive = anticlockwise
    "raise": (-44, 112),        # both fists overhead
    "cast": (-26, 84),          # arms flung wide
}


def make_pose(template, left_degrees, right_degrees):
    import cv2
    from PIL import ImageDraw
    a = np.array(template.convert("RGBA"))
    h, w = a.shape[:2]

    def region(points):
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).polygon(points, fill=255)
        return (np.array(mask) > 0) & (a[..., 3] > 0)

    left, right = region(LEFT_ARM), region(RIGHT_ARM)
    body = a.copy()
    body[left | right, 3] = 0
    yy, xx = np.mgrid[0:h, 0:w]
    socket = ((((xx - LEFT_SHOULDER[0]) ** 2 + (yy - LEFT_SHOULDER[1]) ** 2 <= 34 ** 2) & left)
              | (((xx - RIGHT_SHOULDER[0]) ** 2 + (yy - RIGHT_SHOULDER[1]) ** 2 <= 30 ** 2) & right))
    filled = cv2.inpaint(np.ascontiguousarray(body[..., :3]), socket.astype(np.uint8) * 255, 9, cv2.INPAINT_TELEA)
    body[socket, :3] = filled[socket]
    body[socket, 3] = 255
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for mask, pivot, degrees in ((left, LEFT_SHOULDER, left_degrees), (right, RIGHT_SHOULDER, right_degrees)):
        layer = a.copy()
        layer[~mask, 3] = 0
        out.alpha_composite(Image.fromarray(layer).rotate(degrees, resample=Image.NEAREST, center=pivot))
    out.alpha_composite(Image.fromarray(body))          # the body is drawn over the arms: they come from behind the shoulders
    return _drop_specks(out)


def _drop_specks(img, smallest=60):
    a = np.array(img)
    solid = a[..., 3] > 0
    h, w = solid.shape
    label = np.zeros((h, w), int)
    sizes, count = {}, 0
    for y in range(h):
        for x in range(w):
            if solid[y, x] and not label[y, x]:
                count += 1
                label[y, x] = count
                queue, size = deque([(y, x)]), 0
                while queue:
                    cy, cx = queue.popleft()
                    size += 1
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and solid[ny, nx] and not label[ny, nx]:
                                label[ny, nx] = count
                                queue.append((ny, nx))
                sizes[count] = size
    a[np.isin(label, [k for k, v in sizes.items() if v < smallest]), 3] = 0
    return Image.fromarray(a)


CHEST_CRACKS_2 = {k: v for k, v in CRACKS_2.items() if k[0] < 40}      # the arm cracks only fit the idle pose

# ---------------------------------------------------------------------------
# 7. walking: each leg of the painting swings from its hip and lifts
# ---------------------------------------------------------------------------

LEG_LEFT = [(116, 176), (148, 141), (174, 147), (174, 180), (178, 214), (184, 244), (170, 288), (106, 288), (100, 236), (112, 200)]
LEG_RIGHT = [(236, 168), (300, 172), (326, 205), (322, 250), (300, 292), (244, 292), (246, 240), (238, 200)]
HIP_LEFT, HIP_RIGHT = (176, 162), (256, 186)
WALK_FRAMES = 8
WALK_SWING = 11           # degrees the legs swing forwards and backwards
WALK_LIFT = 15            # painting pixels a foot lifts while it swings forward


def make_walk_frame(template, index, frames=WALK_FRAMES):
    """
    Frame `index` of the walk cycle. Frame 0 = left foot planted forward and right foot back
    (the 'contact' pose), frame frames/4 = legs under him with the right foot lifting, and so on.
    """
    import cv2
    from PIL import ImageDraw
    a = np.array(template.convert("RGBA"))
    h, w = a.shape[:2]

    def region(points):
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).polygon(points, fill=255)
        return np.array(mask) > 0

    cloth = (a[..., 2].astype(int) > a[..., 0].astype(int) + 8) & (a[..., 2] > 60)     # the blue loincloth stays on the body
    solid = a[..., 3] > 0
    r, g, b = (a[..., i].astype(int) for i in range(3))
    emblem = region(EMBLEM_AREA) & ((np.abs(r - g) < 28) & (np.abs(g - b) < 38) & (np.maximum(np.maximum(r, g), b) > 75))
    left = region(LEG_LEFT) & solid & ~cloth & ~emblem          # the skull belt-emblem stays on the body
    right = region(LEG_RIGHT) & solid & ~cloth
    body = a.copy()
    body[left | right, 3] = 0
    yy, xx = np.mgrid[0:h, 0:w]
    hips = ((((xx - HIP_LEFT[0]) ** 2 + (yy - HIP_LEFT[1]) ** 2 <= 34 ** 2) & left)
            | (((xx - HIP_RIGHT[0]) ** 2 + (yy - HIP_RIGHT[1]) ** 2 <= 32 ** 2) & right))
    filled = cv2.inpaint(np.ascontiguousarray(body[..., :3]), hips.astype(np.uint8) * 255, 11, cv2.INPAINT_TELEA)
    body[hips, :3] = filled[hips]
    body[hips, 3] = 255

    def moved(mask, pivot, degrees, lift):
        layer = a.copy()
        layer[~mask, 3] = 0
        picture = Image.fromarray(layer).convert("RGBa")                # premultiplied, so soft edges stay clean
        picture = picture.rotate(degrees, resample=Image.BICUBIC, center=pivot, translate=(0, -lift))
        return picture.convert("RGBA")

    phi = math.tau * index / frames
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(moved(left, HIP_LEFT, -WALK_SWING * math.cos(phi), WALK_LIFT * max(0.0, -math.sin(phi))))
    out.alpha_composite(moved(right, HIP_RIGHT, WALK_SWING * math.cos(phi), WALK_LIFT * max(0.0, math.sin(phi))))
    out.alpha_composite(Image.fromarray(body))                         # the body hides the tops of the legs
    return _drop_specks(out)


# ---------------------------------------------------------------------------
# 8. back view (approximation made from the front art)
# ---------------------------------------------------------------------------

FACE_AREA = [(165, 42), (238, 38), (252, 70), (240, 110), (205, 120), (170, 114), (158, 80)]
EMBLEM_AREA = [(176, 134), (228, 134), (230, 176), (178, 176)]


def make_back(img):
    """The same pose seen from behind: no face, no belt emblem, darker, with a mane of fur tufts."""
    import cv2
    from PIL import ImageDraw
    a = np.array(img.convert("RGBA"))
    h, w = a.shape[:2]
    r, g, b, alpha = (a[..., i].astype(int) for i in range(4))

    def region(points):
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).polygon(points, fill=255)
        return np.array(mask) > 0

    dark = (np.maximum(np.maximum(r, g), b) < 80)
    red = (r > 150) & (g < 95) & (b < 125)
    pale = (np.minimum(np.minimum(r, g), b) > 140) & ((np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)) < 45)
    face = region(FACE_AREA) & (alpha > 0) & (dark | red | pale)
    emblem = region(EMBLEM_AREA) & (alpha > 0) & ((np.abs(r - g) < 28) & (np.abs(g - b) < 38) & (np.maximum(np.maximum(r, g), b) > 75))
    for mask in (face, emblem):
        grown = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        grown &= alpha > 0
        filled = cv2.inpaint(np.ascontiguousarray(a[..., :3]), grown.astype(np.uint8) * 255, 7, cv2.INPAINT_TELEA)
        a[grown, :3] = filled[grown]

    horn = (r > 190) & (g > 120) & (alpha > 0)                        # keep the horns bright
    a[..., :3] = np.where(horn[..., None], a[..., :3], (a[..., :3] * 0.80).astype(np.uint8))

    rng = np.random.RandomState(7)                                    # fur tufts along the spine and neck
    ys, xs = np.where((alpha > 0) & ~horn & region([(150, 60), (250, 60), (262, 170), (170, 176)]))
    for _ in range(260):
        i = rng.randint(len(xs))
        x, y = xs[i], ys[i]
        shade = (34, 20, 20) if rng.rand() < 0.65 else (150, 92, 62)
        for k in range(rng.randint(5, 11)):
            if 0 <= y + k < h and a[y + k, x, 3] > 0:
                a[y + k, x, :3] = shade
    return Image.fromarray(a)


def _pixelize(images, box, palette, phase, front, details):
    """Shrinks full-size images to sprites. Phase 2 gets the enraged colours and cracks."""
    out = []
    for image in images:
        sprite, _ = shrink_to_sprite(image, box, palette)
        if phase == 2:
            sprite = enrage(sprite)
        if front:
            eyes, mouth = (EYES_1, MOUTH_1) if phase == 1 else (EYES_2, MOUTH_2)
            extra = CHEST_CRACKS_2 if phase == 2 else {}
            sprite = paint(sprite, {**eyes, **mouth, **extra, **details}, only_solid=True)
        out.append(sprite)
    return out


def _sheet_of(sprites):
    sheet = Image.new("RGBA", (SIZE * len(sprites), SIZE), (0, 0, 0, 0))
    for i, sprite in enumerate(sprites):
        sheet.paste(sprite, (i * SIZE, 0))
    return sheet


def build():
    template = remove_axe()
    box = template.getchannel("A").getbbox()
    base, palette = shrink_to_sprite(template, box)
    phase1 = paint(base, {**EYES_1, **MOUTH_1})
    phase2 = paint(enrage(base), {**EYES_2, **MOUTH_2, **CRACKS_2})
    frames = {
        "body_phase1_a.png": phase1, "body_phase1_b.png": sink(phase1),
        "body_phase2_a.png": phase2, "body_phase2_b.png": sink(phase2),
    }
    posed = {name: make_pose(template, left, right) for name, (left, right) in POSES.items()}
    walk = [make_walk_frame(template, k) for k in range(WALK_FRAMES)]
    for phase in (1, 2):
        for name, image in posed.items():
            frames[f"pose_{name}_phase{phase}.png"] = _pixelize([image], box, palette, phase, True, {})[0]
            frames[f"pose_{name}_back_phase{phase}.png"] = _pixelize([make_back(image)], box, palette, phase, False, {})[0]
        frames[f"back_phase{phase}.png"] = _pixelize([make_back(template)], box, palette, phase, False, {})[0]
        frames[f"walk_phase{phase}.png"] = _sheet_of(_pixelize(walk, box, palette, phase, True, {}))
        frames[f"walk_back_phase{phase}.png"] = _sheet_of(_pixelize([make_back(f) for f in walk], box, palette, phase, False, {}))
    return frames


def make_sheet(frames, scale=5, floor=(33, 29, 46)):
    """Review picture: single frames in a grid, then every walk sheet as a row."""
    singles = sorted(name for name, im in frames.items() if im.width == SIZE)
    walks = sorted(name for name, im in frames.items() if im.width > SIZE)
    columns = 6
    rows = (len(singles) + columns - 1) // columns
    cell = SIZE * scale + 10
    width = max(cell * columns, (SIZE * scale) * WALK_FRAMES // 2 + 10)
    sheet = Image.new("RGBA", (width + 10, cell * rows + (SIZE * scale // 2 + 10) * len(walks) + 10), floor + (255,))
    for i, name in enumerate(singles):
        big = frames[name].resize((SIZE * scale, SIZE * scale), Image.NEAREST)
        sheet.alpha_composite(big, (10 + (i % columns) * cell, 10 + (i // columns) * cell))
    y = 10 + rows * cell
    for name in walks:
        strip = frames[name].resize((frames[name].width * scale // 2, SIZE * scale // 2), Image.NEAREST)
        sheet.alpha_composite(strip, (10, y))
        y += SIZE * scale // 2 + 10
    return sheet


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    frames = build()
    for name, image in frames.items():
        image.save(os.path.join(OUT_DIR, name))
        print("wrote", name, image.size)
    with open(os.path.join(OUT_DIR, "sprite.json"), "w", encoding="utf-8") as handle:
        json.dump(SPRITE_JSON, handle, indent=2)
        handle.write("\n")
    print("wrote sprite.json")
    if "--sheet" in sys.argv:
        path = os.path.join(HERE, "minotaur_sheet.png")
        make_sheet(frames).save(path)
        print("wrote", path)


if __name__ == "__main__":
    main()
