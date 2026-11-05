"""
tester.py - TESTER MODE: open every door in the game without playing for hours.

    python run_map.py --tester                       # a maxed Level-20 hero in Oakwood, everything unlocked
    python run_map.py --tester --class mage          # warrior (default) / mage / archer
    python run_map.py --tester --floor 3-3           # start on that floor
    python run_map.py --tester --floor 3-3 --boss    # ...and walk straight into its boss room
    python run_map.py --tester --continue            # keep the previous tester save

It never touches your real save: the tester plays on `savegame_tester.json`.

In the game press F1 for the TESTER MENU (the game stops while it is open):
    Up / Down  choose     Enter / Right  select     Left / Esc / Backspace  back     F1  close

    Toggles   God mode, one-hit kills, infinite stamina / mana / energy, fast hero, unlock every portal
    Warp      any floor of the 3 dungeons and the 6 mini dungeons, or back to Oakwood
    Bosses    fight the Goblin King, the Minotaur or the Lich King right now (a fresh fight each time)
    Floor     kill everything, open the gate, clear the floor, jump to the exit / start / boss room, reveal the map
    Hero      level 20, gold, potions, shop upgrades, switch class
    Gear      best gear for the class, a bag full of items
    Story     mark dungeons cleared, open the shops, replay every story scene and the ending

Everything here works by calling the same Game methods the real game uses, so what you see is what a player would get.
"""
from __future__ import annotations

import math
import random

import pygame

try:
    from . import combat, minis, story
    from .night_raid import WARD_CENTER
    from .save_state import LEVEL_XP, MAX_LEVEL
except ImportError:                                   # run from inside src/maps
    import combat
    import minis
    import story
    from night_raid import WARD_CENTER
    from save_state import LEVEL_XP, MAX_LEVEL

from inventory.gear import BASES, SLOTS, Gear, Item   # noqa: E402  (combat.py put src/ on the import path)

TILE = combat.TILE
TESTER_SAVE = "savegame_tester.json"
DUNGEON_NAMES = {1: "Goblin Dungeon", 2: "Berserker Dungeon", 3: "Lich King Dungeon"}
BOSSES = (("Valdur, the Goblin King", "1-3"), ("The Minotaur", "2-3"), ("The Lich King", "3-3"))
ALL_DUNGEONS = ("goblin", "berserker", "lich")
ROWS = 15                                             # menu lines shown at once
FAST = 1.6                                            # "fast hero" speed multiplier


def floor_label(name):
    num, floor = (int(v) for v in name.split("-"))
    if num in DUNGEON_NAMES:
        return "%s  -  floor %d%s" % (DUNGEON_NAMES[num], floor, "  (boss)" if floor == 3 else "")
    mini = minis.MINI_BY_NUM.get(num)
    return "%s  (mini dungeon)" % (mini["name"] if mini else name)


def all_floors():
    out = ["%d-%d" % (d, f) for d in (1, 2, 3) for f in (1, 2, 3)]
    out += ["%d-1" % m["num"] for m in minis.MINIS]
    return out


class Tester:
    def __init__(self, game):
        self.g = game
        self.open = False
        self.stack = []                               # [[title, builder, selected, first visible row], ...]
        self.god = True
        self.one_hit = False
        self.infinite = True
        self.fast = False
        self.unlock_all = True
        self.hitboxes = False                         # draw every hit circle and the sword cone
        self.font = pygame.font.Font(None, 26)
        self.title_font = pygame.font.Font(None, 34)
        self.note = ""                                # last thing the menu did
        self.note_t = 0.0

    # ---- starting -------------------------------------------------------------------
    def start(self, hero_class="warrior", floor=None, boss=False, keep_save=False):
        """Skip the home screen: a new maxed hero (or the previous tester save) in the world."""
        g = self.g
        if keep_save and g.can_continue():
            g.begin_game(new=False)
        else:
            g.begin_game(new=True, name="Tester", hero_class=hero_class)
            self.max_out()
        g.dialog, g.after_dialog = None, None
        self.apply_toggles()
        if floor:
            self.warp(floor, boss=boss)

    def max_out(self):
        """Level 20, gold, potions, every shop upgrade and the best gear."""
        s = self.g.save
        s.xp = LEVEL_XP[MAX_LEVEL - 1]
        s.gold = max(s.gold, 9999)
        s.sword_lv = s.armor_lv = s.boots_lv = s.herb_lv = 3
        s.potions = combat.POTION_MAX
        self.equip_best()
        self.sync(heal=True)

    # ---- every frame ------------------------------------------------------------------
    def apply_toggles(self):
        g = self.g
        g.pc.god, g.pc.one_hit = self.god, self.one_hit
        prog = g.surface.progress
        if self.unlock_all:
            prog.is_unlocked = lambda d: True         # (instance attribute: shadows the real method)
            g.is_dungeon_unlocked = lambda dungeon_id: True
        else:
            prog.__dict__.pop("is_unlocked", None)
            g.__dict__.pop("is_dungeon_unlocked", None)

    def update(self, dt):
        g = self.g
        if g.state != "playing":
            return
        self.note_t = max(0.0, self.note_t - dt)
        g.pc.god, g.pc.one_hit = self.god, self.one_hit
        if self.infinite:
            g.pc.pools.refill()
            g.pc.dash_cd = 0.0
        want = g.pc.speed_k * (FAST if self.fast else 1.0)
        for p in (g.player, g.surface.player):
            if getattr(p, "speed_k", want) != want:
                p.speed_k = want

    # ---- input ---------------------------------------------------------------------------
    def handle_event(self, event):
        """True when the tester used the event (the game must not see it)."""
        if event.type != pygame.KEYDOWN:
            return self.open and event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)
        key = event.key
        if key == pygame.K_F1:
            self.toggle()
            return True
        if not self.open:
            return False
        page = self.stack[-1]
        entries = self.entries()
        if key in (pygame.K_UP, pygame.K_w):
            page[2] = (page[2] - 1) % len(entries)
        elif key in (pygame.K_DOWN, pygame.K_s):
            page[2] = (page[2] + 1) % len(entries)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_RIGHT, pygame.K_d):
            self.choose(entries[page[2]])
        elif key in (pygame.K_LEFT, pygame.K_a, pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.back()
        page = self.stack[-1] if self.stack else page
        page[3] = max(0, min(page[2], max(page[3], page[2] - ROWS + 1)))
        return True

    def toggle(self):
        self.open = not self.open
        if self.open:
            self.stack = [["TESTER", self.main_page, 0, 0]]

    def back(self):
        if len(self.stack) > 1:
            self.stack.pop()
        else:
            self.open = False

    def entries(self):
        return self.stack[-1][1]()

    def choose(self, entry):
        kind, payload = entry[1], entry[2]
        if kind == "sub":
            self.stack.append([payload.__name__.replace("_page", "").title(), payload, 0, 0])
        elif kind == "toggle":
            setattr(self, payload, not getattr(self, payload))
            self.apply_toggles()
        elif kind == "do":
            result = payload()
            if isinstance(result, str):
                self.say(result)

    def say(self, text):
        self.note, self.note_t = text, 4.0
        self.g.toast(text, (150, 255, 190))

    # ---- the pages ---------------------------------------------------------------------------
    # an entry is (label, kind, payload[, shown value]):  "sub" opens a page, "toggle" flips self.<name>, "do" runs it
    def main_page(self):
        g = self.g
        where = ("floor " + g.floor_name) if g.mode == "dungeon" else "Oakwood and the vale"
        return [
            ("God mode (cannot be hurt)", "toggle", "god"),
            ("One-hit kills", "toggle", "one_hit"),
            ("Infinite stamina / mana / energy", "toggle", "infinite"),
            ("Fast hero (x%.1f)" % FAST, "toggle", "fast"),
            ("Every portal unlocked", "toggle", "unlock_all"),
            ("Show hitboxes", "toggle", "hitboxes"),
            ("Heal and refill everything", "do", self.refill),
            ("Warp to a floor        (now: %s)" % where, "sub", self.warp_page),
            ("Boss fights", "sub", self.boss_page),
            ("This floor", "sub", self.floor_page),
            ("Hero", "sub", self.hero_page),
            ("Gear", "sub", self.gear_page),
            ("Story and shops", "sub", self.story_page),
        ]

    def warp_page(self):
        out = [("Oakwood (the overworld)", "do", self.to_village)]
        out += [(floor_label(f) + "   [%s]" % f, "do", lambda f=f: self.warp(f)) for f in all_floors()]
        return out

    def boss_page(self):
        return [(name + "   [%s]" % floor, "do", lambda f=floor: self.warp(f, boss=True, fresh=True))
                for name, floor in BOSSES]

    def floor_page(self):
        if self.g.mode != "dungeon":
            return [("(enter a dungeon first: use Warp)", "do", lambda: None)]
        return [
            ("Kill everything in this room", "do", self.kill_all),
            ("Open this floor's gate (key / seals)", "do", self.open_gate),
            ("Clear the whole floor and open the exit", "do", self.clear_floor),
            ("Go to the boss / last room", "do", self.go_boss_room),
            ("Go to the exit", "do", self.go_exit),
            ("Go to the start", "do", self.go_start),
            ("Reveal the whole map", "do", self.reveal_map),
            ("Light every checkpoint", "do", self.light_checkpoints),
            ("Next floor", "do", lambda: self.step_floor(1)),
            ("Previous floor", "do", lambda: self.step_floor(-1)),
        ]

    def hero_page(self):
        return [
            ("Level 20 (max)", "do", self.max_level),
            ("Level +1", "do", lambda: self.add_level(1)),
            ("+5000 gold", "do", self.add_gold),
            ("Full potions", "do", self.full_potions),
            ("Every shop upgrade (max)", "do", self.max_upgrades),
            ("Become a Warrior", "do", lambda: self.set_class("warrior")),
            ("Become a Mage", "do", lambda: self.set_class("mage")),
            ("Become an Archer", "do", lambda: self.set_class("archer")),
            ("Give back all stat points", "do", self.reset_points),
        ]

    def gear_page(self):
        return [
            ("Wear the best gear (Legendary)", "do", self.wear_best),
            ("Fill the bag: one of every item for my class (Epic)", "do", self.fill_bag),
            ("Empty the bag", "do", self.empty_bag),
        ]

    def story_page(self):
        out = [
            ("Mark all three dungeons cleared", "do", self.mark_cleared),
            ("Un-clear all dungeons", "do", self.unclear),
            ("Start the Lich raid now (skeletons on the north road)", "do", self.lich_raid),
            ("Open Torvin's shop", "do", lambda: self.shop("torvin")),
            ("Open Wren's shop", "do", lambda: self.shop("wren")),
            ("Scene: the opening", "do", lambda: self.scene(story.INTRO_LINES)),
        ]
        for kind in story.BOSS_DIALOGS:
            out.append(("Scene: %s - before the fight" % kind, "do",
                        lambda k=kind: self.scene(story.BOSS_DIALOGS[k], k)))
        for kind in story.OUTRO_DIALOGS:
            out.append(("Scene: %s - after the fight" % kind, "do",
                        lambda k=kind: self.scene(story.OUTRO_DIALOGS[k], k)))
        out.append(("Scene: the ending (and the victory screen)", "do",
                    lambda: self.scene(story.EPILOGUE_LINES, after=self.g.finish_game)))
        return out

    # ---- actions: the hero ---------------------------------------------------------------------
    def sync(self, heal=False):
        """Push the save's numbers onto the hero after a cheat changed them."""
        g = self.g
        g.save.apply_to(g.pc)
        g.refresh_stats()
        if heal:
            g.pc.reset()
        g.autosave()

    def refill(self):
        g = self.g
        g.pc.hp, g.pc.dead = g.pc.max_hp, False
        g.pc.pools.refill()
        g.pc.potions = combat.POTION_MAX
        g.save.potions = g.pc.potions
        return "Healed. Potions full."

    def max_level(self):
        self.g.save.xp = LEVEL_XP[MAX_LEVEL - 1]
        self.sync(heal=True)
        return "Level %d." % self.g.save.level

    def add_level(self, n):
        s = self.g.save
        s.xp = LEVEL_XP[min(MAX_LEVEL, s.level + n) - 1]
        self.sync(heal=True)
        return "Level %d." % s.level

    def add_gold(self):
        self.g.save.gold += 5000
        return "Gold: %d" % self.g.save.gold

    def full_potions(self):
        g = self.g
        g.pc.potions = g.save.potions = combat.POTION_MAX
        return "Potions: %d" % g.pc.potions

    def max_upgrades(self):
        s = self.g.save
        s.sword_lv = s.armor_lv = s.boots_lv = s.herb_lv = 3
        self.sync()
        return "Sword, armor, boots and herbs at level 3."

    def set_class(self, hero_class):
        g = self.g
        g.save.hero_class = hero_class
        g.save.gear = Gear(hero_class)
        g.save.alloc.clear()
        self.equip_best()
        g.apply_hero()
        self.sync(heal=True)
        return "You are now a %s." % hero_class

    def reset_points(self):
        self.g.save.reset_points()
        self.sync()
        return "%d stat points to spend (press I)." % self.g.save.stat_points

    # ---- actions: gear ------------------------------------------------------------------------
    def class_items(self, tier=None):
        cls = self.g.save.hero_class
        return [b for b, row in BASES.items() if row[2] in (None, cls) and (tier is None or row[4] == tier)]

    def equip_best(self):
        gear = self.g.save.gear
        gear.character_class = self.g.save.hero_class
        for slot in SLOTS:
            best = [b for b in self.class_items(tier=4) if BASES[b][1] == slot]
            if best:
                gear.equipped[slot] = Item(best[0], 4)

    def wear_best(self):
        self.equip_best()
        self.sync()
        return "Wearing the best gear."

    def fill_bag(self):
        gear = self.g.save.gear
        added = 0
        for base in self.class_items():
            if gear.add(Item(base, 3)):
                added += 1
        self.g.autosave()
        return "Added %d items to the bag%s." % (added, " (it is full)" if gear.full else "")

    def empty_bag(self):
        self.g.save.gear.bag.clear()
        self.g.autosave()
        return "The bag is empty."

    # ---- actions: story --------------------------------------------------------------------------
    def mark_cleared(self):
        s = self.g.save
        s.cleared.update(ALL_DUNGEONS)
        s.keepsakes.update(ALL_DUNGEONS)
        self.g.autosave()
        return "All three dungeons are cleared."

    def unclear(self):
        s = self.g.save
        s.cleared.clear()
        s.keepsakes.clear()
        self.g.autosave()
        return "No dungeon is cleared any more."

    def lich_raid(self):
        """Night falls in Oakwood and the Lich King's skeletons come down the north road (whatever is cleared)."""
        g = self.g
        if g.mode != "village":
            self.to_village()
        night = g.night
        if night.active:
            night.end_raid(True)
        dn = g.surface.daynight
        dn.t = 0.75 * dn.PERIOD                      # night (a raid ends at daybreak)
        night.prev_phase = dn.phase
        night.current_source = lambda: "lich"        # (instance attribute: the raid order is skipped)
        try:
            started = night.start_raid()
        finally:
            night.__dict__.pop("current_source", None)
        p = g.surface.player
        p.x, p.y = WARD_CENTER[0], WARD_CENTER[1] - 120
        g.snap_camera()
        self.open = False
        return "The Lich raid begins!" if started else "Could not start the raid."

    def shop(self, shop_id):
        self.open = False
        self.g.open_shop(shop_id)

    def scene(self, lines, kind=None, after=None):
        self.open = False
        self.g.open_dialog(lines, kind, after=after)

    # ---- actions: moving around ----------------------------------------------------------------------
    def warp(self, floor, boss=False, fresh=False):
        """Go to a floor of a dungeon. boss=True: walk straight into its last room (the fight starts)."""
        g = self.g
        if floor not in all_floors():
            return "No such floor."
        g.dialog = g.shop = g.journal = g.sheet = None
        g.paused = False
        if g.mode == "village":
            g.night.abort()
            g.wilds.calm()
            g.run_seed = random.getrandbits(30)
            g.floors.clear()
        if fresh:
            g.floors.pop(floor, None)
        had, g.is_dungeon_unlocked = g.__dict__.get("is_dungeon_unlocked"), (lambda dungeon_id: True)
        try:
            g.change_floor(floor)
        finally:
            if had is None:
                g.__dict__.pop("is_dungeon_unlocked", None)
            else:
                g.is_dungeon_unlocked = had
        if g.mode != "dungeon" or g.floor_name != floor:
            return "Could not open %s." % floor
        g.fade, g.fade_dir = 0.0, 0
        if boss:
            self.go_boss_room()
        g.snap_camera()
        self.open = False
        return "Floor %s%s." % (floor, " - the boss room" if boss else "")

    def to_village(self):
        g = self.g
        if g.mode == "village":
            self.open = False
            return "You are in Oakwood."
        g.return_to_surface(int(g.floor_name.split("-")[0]))
        self.open = False
        return "Back in Oakwood."

    def step_floor(self, step):
        num, floor = (int(v) for v in self.g.floor_name.split("-"))
        floors = all_floors()
        name = "%d-%d" % (num, floor + step)
        return self.warp(name) if name in floors else "No floor there."

    def go_boss_room(self):
        g = self.g
        room = g.dungeon.rooms[len(g.dungeon.rooms) - 1]
        g.player.place(room.centerx * TILE, (room.bottom - 4) * TILE)
        g.snap_camera()
        self.open = False
        return "In the last room."

    def go_exit(self):
        g = self.g
        x, y = g.dungeon.exit_pos
        g.player.place(x, y + TILE * 3)
        g.snap_camera()
        self.open = False
        return "At the exit."

    def go_start(self):
        g = self.g
        g.player.place(*g.dungeon.spawn)
        g.snap_camera()
        self.open = False
        return "At the start."

    # ---- actions: the floor ----------------------------------------------------------------------------
    @staticmethod
    def kill(enemy):
        inner = getattr(enemy, "boss", None)
        if hasattr(enemy, "minion"):                  # one of the Lich King's skeletons
            enemy.minion.hp = 0
        elif hasattr(enemy, "monster"):               # a skeleton in a room or a raid
            enemy.monster.kill()
        elif inner is None:
            enemy.hp = 0
        else:                                         # a boss: the arena bosses die with their animation
            inner.hp = 0
            if hasattr(inner, "on_death"):
                inner.on_death()

    def kill_all(self):
        n = 0
        for enemy in self.g.enc.enemies:
            if not enemy.dead and getattr(enemy, "hp", 1) > 0:
                self.kill(enemy)
                n += 1
        self.open = False
        return "Killed %d." % n

    def open_gate(self):
        it = self.g.interact
        if not it.gate or it.gate["open"]:
            return "There is no closed gate on this floor."
        it.keys = max(it.keys, 1)
        it.seals = max(it.seals, it.need)
        it.open_gate()
        return "The gate is open."

    def clear_floor(self):
        enc = self.g.enc
        for enemy in enc.enemies:
            if not enemy.dead:
                self.kill(enemy)
        enc.state = ["cleared" if s != "safe" else s for s in enc.state]
        enc.active = None
        self.g.dungeon.lock_rect = None
        enc.exit_ready = True
        if self.g.interact.gate and not self.g.interact.gate["open"]:
            self.open_gate()
        return "The floor is cleared. Use the exit."

    def light_checkpoints(self):
        inter = self.g.interact
        n = sum(inter.light_checkpoint(c, quiet=True) for c in inter.checkpoints)
        return "%d checkpoint%s lit (%d on this floor)." % (n, "" if n == 1 else "s", len(inter.checkpoints))

    def draw_hitboxes(self, surf, cam_x, cam_y):
        """Show hitboxes: every monster's hit circle (red), the hero's point (cyan) and the
        sword's reach / cone (yellow) the way combat.sword_hits measures them."""
        if not self.hitboxes:
            return
        g = self.g
        if g.mode == "dungeon":
            enemies = list(getattr(g.enc, "enemies", []))
            hx, hy = g.player.x, g.player.y
        else:
            enemies = list(g.wilds.enemies()) + list(getattr(g.night, "monsters", []))
            hx, hy = g.surface.player.x, g.surface.player.y
        for e in enemies:
            if getattr(e, "dead", False):
                continue
            x, y, r = int(e.x - cam_x), int(e.y - cam_y), int(getattr(e, "radius", 12))
            pygame.draw.circle(surf, (255, 70, 70), (x, y), max(2, r), 1)
            pygame.draw.circle(surf, (255, 70, 70), (x, y), 2)
            reach = r + combat.CONTACT_REACH
            pygame.draw.circle(surf, (255, 150, 60), (x, y), reach, 1)      # its bite / punch
        px, py = int(hx - cam_x), int(hy - cam_y)
        pygame.draw.circle(surf, (80, 230, 255), (px, py), 4, 1)
        pc = g.pc
        dx, dy = pc.swing_dir if getattr(pc, "swing_dir", None) else (0.0, 1.0)
        half = math.acos(combat.SWORD_ARC)
        base = math.atan2(dy, dx)
        reach = combat.SWORD_REACH
        pts = [(px, py)] + [(px + math.cos(base + a) * reach, py + math.sin(base + a) * reach)
                            for a in [(-half + 2 * half * k / 12) for k in range(13)]]
        pygame.draw.lines(surf, (255, 230, 90), True, pts, 1)

    def reveal_map(self):
        mm, d = self.g.minimap, self.g.dungeon
        for i in range(len(mm.seen)):
            mm.seen[i] = 1
            col = mm.colors.get(d.tiles[i])
            if col:
                mm.raw.set_at((i % combat.MAP_W, i // combat.MAP_W), col)
        mm.room_seen = [True] * len(d.rooms)
        mm.dirty = True
        return "The map is revealed."

    # ---- drawing ------------------------------------------------------------------------------------------
    def chips(self):
        return [name for name, on in (("GOD", self.god), ("1-HIT", self.one_hit), ("INF", self.infinite),
                                      ("FAST", self.fast), ("UNLOCKED", self.unlock_all)) if on]

    def draw(self, surf):
        g = self.g
        if g.state != "playing":
            return
        text = "TESTER   F1 menu   " + " ".join(self.chips())
        img = self.font.render(text, True, (150, 255, 190))
        surf.fill((0, 0, 0), (surf.get_width() // 2 - img.get_width() // 2 - 8, 0, img.get_width() + 16, 22))
        surf.blit(img, (surf.get_width() // 2 - img.get_width() // 2, 3))
        if not self.open:
            return
        title, _builder, sel, top = self.stack[-1]
        entries = self.entries()
        sel = min(sel, len(entries) - 1)
        rows = entries[top:top + ROWS]
        w, row_h = 640, 28
        h = 78 + row_h * len(rows) + 34
        x, y = 36, 56
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((14, 12, 24, 232))
        pygame.draw.rect(panel, (150, 255, 190), panel.get_rect(), 2)
        surf.blit(panel, (x, y))
        path = " > ".join(p[0] for p in self.stack)
        surf.blit(self.title_font.render(path, True, (255, 232, 160)), (x + 18, y + 12))
        for i, entry in enumerate(rows):
            k = top + i
            yy = y + 58 + i * row_h
            on = k == sel
            if on:
                pygame.draw.rect(surf, (52, 70, 62), (x + 10, yy - 3, w - 20, row_h - 2))
            label = entry[0]
            if entry[1] == "toggle":
                label = "[%s]  %s" % ("ON " if getattr(self, entry[2]) else "off", label)
            elif entry[1] == "sub":
                label += "   >"
            col = (255, 255, 255) if on else (205, 205, 215)
            surf.blit(self.font.render(label, True, col), (x + 20, yy))
        if top > 0:
            surf.blit(self.font.render("^", True, (255, 232, 160)), (x + w - 28, y + 58))
        if top + ROWS < len(entries):
            surf.blit(self.font.render("v", True, (255, 232, 160)), (x + w - 28, y + h - 52))
        hint = "Up/Down choose   Enter select   Esc back   F1 close"
        surf.blit(self.font.render(hint, True, (160, 170, 190)), (x + 18, y + h - 28))
