"""
make_icon.py - builds the game's window / .exe icon from the Knight's idle frame (pygame only).

    python tools/make_icon.py        -> assets/ui/icon.png (window icon) and assets/ui/icon.ico (the .exe)

The .ico holds PNG images (16-256 px), which Windows has read since Vista.
"""
import io
import os
import struct
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "assets", "characters", "knight_idle.png")
OUT = os.path.join(REPO, "assets", "ui")
SIZES = (16, 24, 32, 48, 64, 128, 256)


def knight_frame():
    sheet = pygame.image.load(SRC)
    h = sheet.get_height()
    frame = sheet.subsurface((0, 0, min(h, sheet.get_width()), h)).copy()
    box = frame.get_bounding_rect()                       # trim the empty border
    return frame.subsurface(box).copy()


def icon(size, art):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    pad = max(1, size // 16)
    pygame.draw.circle(s, (34, 30, 52, 255), (size // 2, size // 2), size // 2)           # dark medallion
    pygame.draw.circle(s, (214, 170, 80, 255), (size // 2, size // 2), size // 2, max(1, size // 20))
    inner = size - 4 * pad
    k = min(inner / art.get_width(), inner / art.get_height())
    w, h = max(1, int(art.get_width() * k)), max(1, int(art.get_height() * k))
    img = pygame.transform.scale(art, (w, h)) if size < 64 else pygame.transform.smoothscale(art, (w, h))
    s.blit(img, ((size - w) // 2, (size - h) // 2 + pad // 2))
    return s


def png_bytes(surf):
    buf = io.BytesIO()
    pygame.image.save(surf, buf, "icon.png")
    return buf.getvalue()


def write_ico(path, images):
    header = struct.pack("<HHH", 0, 1, len(images))
    entries, blobs = b"", b""
    offset = 6 + 16 * len(images)
    for size, data in images:
        b = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", b, b, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    with open(path, "wb") as f:
        f.write(header + entries + blobs)


def main():
    pygame.init()
    pygame.display.set_mode((8, 8))
    art = knight_frame()
    os.makedirs(OUT, exist_ok=True)
    pygame.image.save(icon(64, art), os.path.join(OUT, "icon.png"))
    write_ico(os.path.join(OUT, "icon.ico"), [(n, png_bytes(icon(n, art))) for n in SIZES])
    print("wrote assets/ui/icon.png and assets/ui/icon.ico")
    return 0


if __name__ == "__main__":
    sys.exit(main())
