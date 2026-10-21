"""
prepare_assets.py - Turn raw generated art (on a magenta background) into
clean game-ready PNGs in assets/ui/.

Needs Pillow (only for this tool, not for the game):   pip install pillow

Run from the repo root, giving whichever pictures you have:
    python src/ui/dev/prepare_assets.py --bg raw/background.png --buttons raw/buttons.png \
        --panel raw/panel.png --plate raw/title_plate.png --icons raw/icons.png

What it does
    1. Makes every magenta (#FF00FF-ish) pixel transparent.
    2. Cuts sheets into separate pieces (2 buttons, 9 icons) using the gaps between them.
    3. Trims the empty space and shrinks each piece to the size the game uses.
    4. Frame + sign only: darkens the wood to the deeper brown (see WOOD_BRIGHTNESS).

The ORDER of things in each picture matters:
    buttons: normal (left), selected (right)
    icons:   play, gear, sound, video, controls, exit, heart, shield, energy
    weapons: iron sword, battle axe, greatsword, apprentice staff, fire wand, short bow, crossbow
    slots:   normal (left), selected (right)
    badges:  warrior, mage, archer
"""
import argparse
import os

from PIL import Image, ImageChops, ImageFilter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DIR = os.path.join(REPO_ROOT, "assets", "ui")

ICON_NAMES = ["play", "gear", "sound", "video", "controls", "exit", "heart", "shield", "energy"]
# must match the weapon ids in src/inventory/weapons.py, in the order they appear in the picture
WEAPON_NAMES = ["iron_sword", "battle_axe", "greatsword", "apprentice_staff", "fire_wand",
                "short_bow", "crossbow"]
BADGE_NAMES = ["warrior", "mage", "archer"]

BG_SIZE = (960, 640)
BUTTON_HEIGHT = 64
PANEL_SIZE = 240
PLATE_HEIGHT = 56
ICON_SIZE = 32
SIGN_WIDTH = 400
WOOD_BRIGHTNESS = 0.55     # frame + sign wood: 1.0 = as generated, lower = darker brown
WOOD_HUE_SHIFT = 8         # degrees towards red (less yellow)
HERO_HEIGHT = 110
WEAPON_ICON_SIZE = 48
SLOT_SIZE = 64
BADGE_SIZE = 24
CHARACTER_HEIGHT = 200


def remove_magenta(image):
    """Every pixel that is clearly pink/magenta becomes transparent."""
    image = image.convert("RGBA")
    pixels = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if min(r, b) - g > 60:          # lots of red AND blue, little green = magenta
                pixels[x, y] = (0, 0, 0, 0)
    return image


def darken_wood(image, brightness=WOOD_BRIGHTNESS, hue_shift=WOOD_HUE_SHIFT):
    """
    Make light orange/yellow wood a darker, redder brown (like the title plate),
    WITHOUT touching leaves (green), the red banner, flowers, steel or bright brass.
    """
    import colorsys
    image = image.convert("RGBA")
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            hue = h * 360
            is_wood = 12 <= hue <= 40 and s > 0.45
            is_bright_brass = hue > 30 and v > 0.85
            if is_wood and not is_bright_brass:
                h = max(0.0, hue - hue_shift) / 360
                r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v * brightness)
                pixels[x, y] = (round(r2 * 255), round(g2 * 255), round(b2 * 255), a)
    return image


def split_columns(image, min_gap=12):
    """Cut a sheet into pieces wherever there is a fully transparent gap of columns."""
    alpha = image.getchannel("A")
    width, height = image.size
    used = [alpha.crop((x, 0, x + 1, height)).getbbox() is not None for x in range(width)]
    pieces, start, gap = [], None, 0
    for x, filled in enumerate(used + [False] * min_gap):
        if filled:
            if start is None:
                start = x
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                pieces.append(image.crop((start, 0, x - gap + 1, height)))
                start, gap = None, 0
    return [trim(p) for p in pieces]


def remove_plain_background(image, tolerance=40):
    """For pictures on a plain (non-magenta) background: erase the colour touching the edges."""
    from PIL import ImageDraw
    image = image.convert("RGBA")
    w, h = image.size
    edge_points = [(x, 0) for x in range(0, w, 8)] + [(x, h - 1) for x in range(0, w, 8)] + \
                  [(0, y) for y in range(0, h, 8)] + [(w - 1, y) for y in range(0, h, 8)]
    for point in edge_points:
        if image.getpixel(point)[3] != 0:
            ImageDraw.floodfill(image, point, (0, 0, 0, 0), thresh=tolerance)
    return image


def stamp_placeholder(image):
    """Write PLACEHOLDER across a picture, so nobody mistakes it for final art."""
    from PIL import ImageDraw, ImageFont
    image = image.copy()
    draw = ImageDraw.Draw(image)
    font_path = os.path.join(OUT_DIR, "fonts", "Silkscreen-Bold.ttf")
    font = ImageFont.truetype(font_path, max(10, image.width // 9)) if os.path.exists(font_path) \
        else ImageFont.load_default()
    band_h = max(14, image.height // 9)
    top = image.height // 2 - band_h // 2
    draw.rectangle([0, top, image.width, top + band_h], fill=(190, 30, 30, 235))
    draw.text((image.width // 2, top + band_h // 2), "PLACEHOLDER", font=font,
              fill=(255, 255, 255, 255), anchor="mm")
    return image


def split_shapes(image, expected, glue_small_bits=True):
    """
    Cut a sheet into separate pictures by finding shapes that touch each other
    (works even when things are drawn diagonally and overlap in columns).
    Small loose bits (sparks, flames) are added to the nearest big shape.
    Returns the pieces from left to right.
    """
    step = 4                                           # look at a smaller copy: much faster
    small = image.getchannel("A").resize((image.width // step, image.height // step))
    w, h = small.size
    filled = [[small.getpixel((x, y)) > 40 for x in range(w)] for y in range(h)]
    seen = [[False] * w for _ in range(h)]
    shapes = []
    for sy in range(h):
        for sx in range(w):
            if not filled[sy][sx] or seen[sy][sx]:
                continue
            stack, cells = [(sx, sy)], []
            seen[sy][sx] = True
            while stack:
                x, y = stack.pop()
                cells.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and filled[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            xs, ys = [c[0] for c in cells], [c[1] for c in cells]
            shapes.append({"size": len(cells), "cells": cells,
                           "box": [min(xs), min(ys), max(xs) + 1, max(ys) + 1]})

    shapes.sort(key=lambda s: -s["size"])
    big, small_bits = shapes[:expected], shapes[expected:]
    if not glue_small_bits:
        small_bits = []                                # throw loose bits away instead
    for bit in small_bits:                             # glue each loose bit to the closest shape
        bx = (bit["box"][0] + bit["box"][2]) / 2
        by = (bit["box"][1] + bit["box"][3]) / 2
        nearest = min(big, key=lambda s: ((s["box"][0] + s["box"][2]) / 2 - bx) ** 2 +
                                         ((s["box"][1] + s["box"][3]) / 2 - by) ** 2)
        box = nearest["box"]
        nearest["box"] = [min(box[0], bit["box"][0]), min(box[1], bit["box"][1]),
                          max(box[2], bit["box"][2]), max(box[3], bit["box"][3])]
        nearest["cells"] = nearest["cells"] + bit["cells"]

    big.sort(key=lambda s: s["box"][0])
    pieces = []
    for shape in big:
        # a mask with ONLY this shape's own pixels (a little wider, so edges aren't cut)
        mask = Image.new("L", (w, h), 0)
        for x, y in shape["cells"]:
            mask.putpixel((x, y), 255)
        mask = mask.filter(ImageFilter.MaxFilter(5)).resize(image.size, Image.NEAREST)
        alpha = ImageChops.multiply(image.getchannel("A"), mask)
        own = image.copy()
        own.putalpha(alpha)
        pieces.append(trim(own))
    return pieces


def trim(image):
    box = image.getchannel("A").getbbox()
    return image.crop(box) if box else image


def resize_to_height(image, height):
    width = max(1, round(image.width * height / image.height))
    return image.resize((width, height), Image.LANCZOS)


def fit_square(image, size):
    scale = size / max(image.size)
    small = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                         Image.LANCZOS)
    square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    square.paste(small, ((size - small.width) // 2, (size - small.height) // 2), small)
    return square


def save(image, name):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    image.save(path)
    print(f"  saved assets/ui/{name}  {image.size[0]}x{image.size[1]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bg")
    parser.add_argument("--buttons")
    parser.add_argument("--panel")
    parser.add_argument("--plate")
    parser.add_argument("--icons")
    parser.add_argument("--frame", help="screen border (wood + leaves), same 3:2 shape as the screen")
    parser.add_argument("--sign", help="wooden title sign")
    parser.add_argument("--hero", help="the small hero standing on the menu")
    parser.add_argument("--weapons", help="row of 7 weapon icons")
    parser.add_argument("--slots", help="weapon slot box: normal + selected")
    parser.add_argument("--badges", help="row of 3 class badges")
    parser.add_argument("--characters", help="row of 3 characters (front view) on a plain background")
    parser.add_argument("--character-order", default="mage,warrior,archer",
                        help="which class each character is, left to right")
    parser.add_argument("--placeholder", action="store_true",
                        help="stamp PLACEHOLDER across the characters (temporary art)")
    args = parser.parse_args()

    if args.weapons:
        pieces = split_shapes(remove_magenta(Image.open(args.weapons)), len(WEAPON_NAMES))
        if len(pieces) != len(WEAPON_NAMES):
            raise SystemExit(f"Expected {len(WEAPON_NAMES)} weapons, found {len(pieces)}.")
        for name, piece in zip(WEAPON_NAMES, pieces):
            save(fit_square(piece, WEAPON_ICON_SIZE), f"weapon_{name}.png")

    if args.characters:
        sheet = remove_plain_background(Image.open(args.characters))
        names = args.character_order.split(",")
        pieces = split_shapes(sheet, len(names), glue_small_bits=False)
        for name, piece in zip(names, pieces):
            piece = resize_to_height(piece, CHARACTER_HEIGHT) if piece.height > CHARACTER_HEIGHT else piece
            if args.placeholder:
                piece = stamp_placeholder(piece)
            save(piece, f"class_{name.strip()}.png")

    if args.slots:
        pieces = split_columns(remove_magenta(Image.open(args.slots)))
        if len(pieces) != 2:
            raise SystemExit(f"Expected 2 slots, found {len(pieces)}.")
        save(pieces[0].resize((SLOT_SIZE, SLOT_SIZE), Image.LANCZOS), "slot.png")
        save(pieces[1].resize((SLOT_SIZE, SLOT_SIZE), Image.LANCZOS), "slot_selected.png")

    if args.badges:
        pieces = split_columns(remove_magenta(Image.open(args.badges)))
        if len(pieces) != len(BADGE_NAMES):
            raise SystemExit(f"Expected {len(BADGE_NAMES)} badges, found {len(pieces)}.")
        for name, piece in zip(BADGE_NAMES, pieces):
            save(fit_square(piece, BADGE_SIZE), f"badge_{name}.png")

    if args.frame:   # NOT trimmed: it must line up with the edges of the screen
        frame = darken_wood(remove_magenta(Image.open(args.frame)))
        save(frame.resize(BG_SIZE, Image.LANCZOS), "screen_frame.png")

    if args.sign:
        sign = darken_wood(trim(remove_magenta(Image.open(args.sign))))
        save(sign.resize((SIGN_WIDTH, round(sign.height * SIGN_WIDTH / sign.width)), Image.LANCZOS),
             "title_sign.png")

    if args.hero:
        save(resize_to_height(trim(remove_magenta(Image.open(args.hero))), HERO_HEIGHT), "hero.png")

    if args.bg:
        save(Image.open(args.bg).convert("RGB").resize(BG_SIZE, Image.LANCZOS), "menu_bg.png")

    if args.buttons:
        pieces = split_columns(remove_magenta(Image.open(args.buttons)))
        if len(pieces) != 2:
            raise SystemExit(f"Expected 2 buttons, found {len(pieces)}. Is the gap between them clear?")
        save(resize_to_height(pieces[0], BUTTON_HEIGHT), "button.png")
        save(resize_to_height(pieces[1], BUTTON_HEIGHT), "button_selected.png")

    if args.panel:
        panel = trim(remove_magenta(Image.open(args.panel)))
        save(panel.resize((PANEL_SIZE, PANEL_SIZE), Image.LANCZOS), "panel.png")

    if args.plate:
        save(resize_to_height(trim(remove_magenta(Image.open(args.plate))), PLATE_HEIGHT),
             "title_plate.png")

    if args.icons:
        pieces = split_columns(remove_magenta(Image.open(args.icons)))
        if len(pieces) != len(ICON_NAMES):
            raise SystemExit(f"Expected {len(ICON_NAMES)} icons, found {len(pieces)}.")
        for name, piece in zip(ICON_NAMES, pieces):
            save(fit_square(piece, ICON_SIZE), f"icon_{name}.png")


if __name__ == "__main__":
    main()
