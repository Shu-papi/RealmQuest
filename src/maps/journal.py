"""
journal.py - the hero's journal (Tab / L): quests and discovered lore.

    j = Journal(save, quest_book)
    j.handle_key(key)   -> False once closed
    j.draw(screen, t)
"""
from __future__ import annotations

import math

import pygame

try:
    from . import npc_art, quests, story, world_lore
except ImportError:
    import npc_art
    import quests
    import story
    import world_lore

GOLD = (255, 214, 110)
INK = (236, 230, 214)
DIM = (130, 126, 118)
PANEL = (18, 15, 20)


def _check(surf, x, y, col):
    pygame.draw.lines(surf, col, False, [(x, y + 5), (x + 4, y + 9), (x + 11, y)], 3)


def lore_entries(save):
    """[(title, colour, lines)] for everything the hero has read or found, plus the undiscovered count."""
    f = save.flags
    out, missing = [], 0
    for i, (_x, _y, name, col) in enumerate(world_lore.SHRINES):
        if "got_shrine_%d" % i in f:
            out.append((name, col, world_lore.SHRINE_VERSES[i]))
        else:
            missing += 1
    if "seen_memorial" in f:
        out.append(("The Wall of Names", (170, 200, 255), world_lore.MEMORIAL_LINES))
    else:
        missing += 1
    names = {"goblin": "Goblin Dungeon", "berserker": "Berserker Warriors Dungeon", "lich": "Lich King Dungeon"}
    for sid, pages in story.LORE.items():
        for fl, lines in enumerate(pages, 1):
            if "lore_%s_%d" % (sid, fl) in f:
                out.append(("%s, floor %d" % (names[sid], fl), (190, 200, 230), lines))
            else:
                missing += 1
    for sid, (name, lines) in story.KEEPSAKES.items():
        if sid in save.keepsakes:
            out.append((name, (255, 220, 150), lines))
        else:
            missing += 1
    return out, missing


class Journal:
    def __init__(self, save, book, sfx=None):
        self.save, self.book, self.sfx = save, book, sfx
        self.tab = 0
        self.sel = 0
        self.scroll = 0
        self.open = True
        self._portraits = {}
        self.f_title = pygame.font.Font(None, 44)
        self.f_head = pygame.font.Font(None, 30)
        self.f_text = pygame.font.Font(None, 24)
        self.f_small = pygame.font.Font(None, 21)

    def _play(self, n):
        if self.sfx:
            self.sfx.play(n)

    def handle_key(self, key):
        if key in (pygame.K_ESCAPE, pygame.K_TAB, pygame.K_l, pygame.K_BACKSPACE):
            self.open = False
            self._play("blip")
        elif key in (pygame.K_a, pygame.K_d, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_q):
            self.tab = 1 - self.tab
            self.sel = 0
            self._play("blip")
        elif key in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN):
            n = len(lore_entries(self.save)[0]) if self.tab == 1 else len(self.quest_entries())
            if n:
                self.sel = (self.sel + (1 if key in (pygame.K_s, pygame.K_DOWN) else -1)) % n
                self._play("blip")
        return self.open

    # ---- drawing ------------------------------------------------------------------
    def _wrap(self, text, font, width):
        out, cur = [], ""
        for w in text.split(" "):
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= width:
                cur = test
            else:
                out.append(cur)
                cur = w
        out.append(cur)
        return out

    def _text(self, surf, s, font, col, x, y):
        surf.blit(font.render(s, True, (0, 0, 0)), (x + 1, y + 1))
        surf.blit(font.render(s, True, col), (x, y))

    def draw(self, surf, t):
        W, H = surf.get_size()
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 170))
        surf.blit(veil, (0, 0))
        box = pygame.Rect(60, 40, W - 120, H - 80)
        pygame.draw.rect(surf, PANEL, box, border_radius=12)
        pygame.draw.rect(surf, (214, 176, 84), box, 3, border_radius=12)
        pygame.draw.rect(surf, (90, 70, 40), box.inflate(-12, -12), 1, border_radius=9)
        self._text(surf, "Journal", self.f_title, (250, 240, 220), box.x + 28, box.y + 18)
        tx = box.x + 200
        for i, name in enumerate(("Quests", "Lore")):
            img = self.f_head.render(name, True, GOLD if i == self.tab else DIM)
            r = pygame.Rect(tx, box.y + 22, img.get_width() + 28, 34)
            if i == self.tab:
                pygame.draw.rect(surf, (60, 48, 30), r, border_radius=7)
                pygame.draw.rect(surf, GOLD, r, 2, border_radius=7)
            surf.blit(img, (r.x + 14, r.y + 7))
            tx = r.right + 12
        foot = "A / D: switch tab     W / S: choose     Tab / Esc: close"
        img = self.f_small.render(foot, True, (190, 186, 170))
        surf.blit(img, (box.centerx - img.get_width() // 2, box.bottom - 30))
        body = pygame.Rect(box.x + 28, box.y + 72, box.w - 56, box.h - 112)
        pygame.draw.line(surf, (90, 70, 40), (body.x, body.y - 6), (body.right, body.y - 6), 1)
        if self.tab == 0:
            self._draw_quests(surf, body, t)
        else:
            self._draw_lore(surf, body, t)

    # ---- quests tab: list on the left, details on the right ---------------------------
    def quest_entries(self):
        """Selectable entries: the main quest, then accepted, finished and offered side quests."""
        book = self.book
        out = [("main", None)]
        for st in (("ready", "active"), ("done",), ("available",)):
            out += [("side", q) for q in quests.SIDE if book.state(q) in st]
        return out

    def _rows(self, entries):
        """List rows with section headers: (kind, label, entry index or None)."""
        book, rows, last = self.book, [], None
        names = {"main": "MAIN QUEST", "ready": "ACCEPTED", "active": "ACCEPTED", "done": "COMPLETED",
                 "available": "NOT YET ACCEPTED"}
        for i, (kind, q) in enumerate(entries):
            sec = names["main"] if kind == "main" else names[book.state(q)]
            if sec != last:
                n = sum(1 for k, qq in entries if k == "side" and names[book.state(qq)] == sec)
                rows.append(("head", sec + ("  (%d)" % n if kind != "main" else ""), None))
                last = sec
            rows.append(("item", None, i))
        return rows

    def _portrait(self, look):
        if look not in self._portraits:
            img = npc_art.portrait(look)
            k = 104 / img.get_height()
            self._portraits[look] = pygame.transform.smoothscale(img, (int(img.get_width() * k), int(img.get_height() * k)))
        return self._portraits[look]

    def _draw_quests(self, surf, body, t):
        book = self.book
        entries = self.quest_entries()
        self.sel = min(self.sel, len(entries) - 1)
        rows = self._rows(entries)
        listw, rh = 340, 28
        visible = (body.h - 10) // rh
        sel_row = next(r for r, row in enumerate(rows) if row[2] == self.sel)
        if sel_row < self.scroll + 1:
            self.scroll = max(0, sel_row - 1)
        elif sel_row >= self.scroll + visible:
            self.scroll = sel_row - visible + 1
        x, y = body.x, body.y
        for kind, label, idx in rows[self.scroll:self.scroll + visible]:
            if kind == "head":
                self._text(surf, label, self.f_small, (170, 150, 110), x + 4, y + 8)
                pygame.draw.line(surf, (70, 56, 36), (x + 4, y + 25), (x + listw, y + 25), 1)
                y += rh
                continue
            ek, q = entries[idx]
            r = pygame.Rect(x, y + 1, listw, rh - 3)
            if idx == self.sel:
                pygame.draw.rect(surf, (60, 48, 30), r, border_radius=6)
                pygame.draw.rect(surf, GOLD, r, 1, border_radius=6)
            if ek == "main":
                ms = book.main_step()
                label, col, right = quests.MAIN_TITLE, GOLD, (ms[1].split(" - ")[0] if ms else "done")
                icon = "main" if ms else "done"
            else:
                st = book.state(q)
                label, right = q["title"], ""
                col = {"ready": GOLD, "active": (150, 210, 255), "done": (140, 146, 134),
                       "available": (170, 160, 130)}[st]
                icon = st
                if st == "ready":
                    right = "hand in!"
                elif st == "active" and q["need"] > 1:
                    right = "%d/%d" % (book.count(q), q["need"])
            cy = r.centery
            if icon == "done":
                _check(surf, x + 8, cy - 5, (120, 200, 120))
            elif icon == "available":
                pygame.draw.circle(surf, (120, 112, 96), (x + 14, cy), 4, 1)
            else:
                k = 4 if icon != "ready" else 5 + int(math.sin(t * 6) > 0)
                c = GOLD if icon in ("main", "ready") else (150, 210, 255)
                pygame.draw.polygon(surf, c, [(x + 14, cy - k), (x + 14 + k, cy), (x + 14, cy + k), (x + 14 - k, cy)])
            self._text(surf, label, self.f_small, col, x + 28, cy - 8)
            if right:
                img = self.f_small.render(right, True, col)
                surf.blit(img, (r.right - img.get_width() - 10, cy - 8))
            y += rh
        if self.scroll > 0:
            pygame.draw.polygon(surf, DIM, [(x + listw - 14, body.y - 2), (x + listw - 6, body.y - 2), (x + listw - 10, body.y - 8)])
        if self.scroll + visible < len(rows):
            by = body.y + visible * rh + 2
            pygame.draw.polygon(surf, DIM, [(x + listw - 14, by), (x + listw - 6, by), (x + listw - 10, by + 6)])

        px = body.x + listw + 30
        pygame.draw.line(surf, (70, 56, 36), (px - 15, body.y), (px - 15, body.bottom - 6), 1)
        pane = pygame.Rect(px, body.y, body.right - px, body.h)
        kind, q = entries[self.sel]
        if kind == "main":
            self._draw_main(surf, pane, t)
        else:
            self._draw_side(surf, pane, q)

    def _draw_main(self, surf, pane, t):
        s, book = self.save, self.book
        x, y, w = pane.x, pane.y, pane.w
        self._text(surf, quests.MAIN_TITLE, self.f_head, GOLD, x, y)
        y += 36
        cur = book.main_step()
        for ci, (title, col, steps) in enumerate(quests.MAIN):
            if cur and ci > cur[0]:
                self._text(surf, "???", self.f_text, DIM, x, y)
                y += 26
                continue
            if all(st["done"](s) for st in steps):
                _check(surf, x, y + 3, (120, 200, 120))
                self._text(surf, title, self.f_text, (150, 160, 146), x + 20, y)
                y += 28
                continue
            self._text(surf, title, self.f_text, col, x, y)
            y += 28
            for st in steps:
                ok = st["done"](s)
                is_cur = cur is not None and st is cur[3]
                if ok:
                    _check(surf, x + 8, y + 1, (120, 200, 120))
                elif is_cur:
                    k = 0.6 + 0.4 * math.sin(t * 4)
                    pygame.draw.polygon(surf, (int(255 * k), int(214 * k), int(110 * k)),
                                        [(x + 9, y + 2), (x + 17, y + 7), (x + 9, y + 12)])
                else:
                    pygame.draw.circle(surf, DIM, (x + 13, y + 7), 3)
                for ln in self._wrap(st["text"], self.f_small, w - 30):
                    self._text(surf, ln, self.f_small, INK if is_cur else ((150, 160, 146) if ok else DIM), x + 28, y)
                    y += 20
                y += 4
            y += 8
        if cur is None:
            self._text(surf, "The Veil has fallen. Beyond the mountains, the story continues...", self.f_small, GOLD, x, y)

    def _draw_side(self, surf, pane, q):
        book = self.book
        st = book.state(q)
        x, y, w = pane.x, pane.y, pane.w
        img = self._portrait(q["giver"])
        frame = pygame.Rect(pane.right - img.get_width() - 16, y, img.get_width() + 12, img.get_height() + 12)
        pygame.draw.rect(surf, (28, 26, 36), frame, border_radius=6)
        pygame.draw.rect(surf, (120, 96, 56), frame, 1, border_radius=6)
        surf.blit(img, (frame.x + 6, frame.y + 6))
        tw = frame.x - x - 16
        self._text(surf, q["title"], self.f_head, GOLD if st != "done" else (170, 176, 160), x, y)
        y += 34
        giver = story.NPC_NAMES.get(q["giver"], story.SURVIVOR)
        self._text(surf, "From " + giver, self.f_small, (150, 210, 150), x, y)
        y += 24
        status = {"ready": ("Ready to hand in: " + book.progress_text(q), GOLD),
                  "active": ("Accepted - in progress", (150, 210, 255)),
                  "done": ("Completed", (120, 200, 120)),
                  "available": ("Not accepted yet - talk to %s" % giver.split(" the ")[0], (190, 170, 120))}[st]
        self._text(surf, status[0], self.f_small, status[1], x, y)
        y += 34
        if st != "available":
            quote = q["offer"][0][1]
            for ln in self._wrap('"%s"' % quote, self.f_small, tw):
                self._text(surf, ln, self.f_small, (176, 170, 156), x, y)
                y += 20
            y += 14
            y = max(y, frame.bottom + 10)
            self._text(surf, "Objective", self.f_text, INK, x, y)
            y += 26
            for ln in self._wrap(q["goal"], self.f_small, w - 10):
                self._text(surf, ln, self.f_small, (210, 210, 200), x + 10, y)
                y += 20
            if q["need"] > 1 and st != "done":
                n = book.count(q)
                bw = 220
                pygame.draw.rect(surf, (40, 36, 30), (x + 10, y + 8, bw, 12), border_radius=5)
                pygame.draw.rect(surf, (230, 180, 80), (x + 10, y + 8, int(bw * n / q["need"]), 12), border_radius=5)
                self._text(surf, "%d / %d" % (n, q["need"]), self.f_small, INK, x + 20 + bw, y + 4)
                y += 28
            y += 16
        self._text(surf, "Reward", self.f_text, INK, x, y)
        y += 26
        self._text(surf, quests.reward_text(q), self.f_small, (255, 226, 140), x + 10, y)

    def _draw_lore(self, surf, body, t):
        entries, missing = lore_entries(self.save)
        x, y = body.x, body.y
        listw = 330
        if not entries:
            self._text(surf, "Nothing yet. Read tablets in the dungeons and visit the old places of the realm.",
                       self.f_text, DIM, x, y)
            return
        self.sel = min(self.sel, len(entries) - 1)
        for i, (title, col, _lines) in enumerate(entries):
            r = pygame.Rect(x, y, listw, 26)
            if i == self.sel:
                pygame.draw.rect(surf, (60, 48, 30), r, border_radius=6)
                pygame.draw.rect(surf, GOLD, r, 1, border_radius=6)
            self._text(surf, title, self.f_small, col if i == self.sel else (200, 196, 184), x + 10, y + 5)
            y += 29
            if y > body.bottom - 40:
                break
        self._text(surf, "%d still undiscovered" % missing, self.f_small, DIM, x + 10, body.bottom - 22)
        # the selected entry
        title, col, lines = entries[self.sel]
        px = body.x + listw + 30
        pygame.draw.line(surf, (70, 56, 36), (px - 15, body.y), (px - 15, body.bottom - 6), 1)
        y = body.y
        self._text(surf, title, self.f_head, col, px, y)
        y += 38
        width = body.right - px
        for who, text in lines:
            hero = who == story.HERO
            for ln in self._wrap(text, self.f_text, width):
                self._text(surf, ln, self.f_text, GOLD if hero else INK, px, y)
                y += 24
            y += 10
