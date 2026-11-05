"""
quests.py - the main quest and the villagers' side quests.

All quest state lives in SaveState.flags, so old saves keep working:
    q_<id>         quest accepted
    qdone_<id>     quest handed in
    got_<item>_*   one flag per quest item collected (count = number of flags)

    book = QuestBook(save)
    book.marker("pip")        -> "ready" | "quest" | None   (the "?" / "!" over a villager)
    book.state(q)             -> "locked" | "available" | "active" | "ready" | "done"
    book.main_step()          -> the current main-quest step, or None when the story is over
"""
from __future__ import annotations

try:
    from . import story
    from .shop import CATALOG
    from . import combat as _combat
except ImportError:
    import story
    from shop import CATALOG
    import combat as _combat

H = story.HERO
MAREN, TORVIN, WREN, PIP = story.MAREN, story.TORVIN, story.WREN, story.PIP
HALE, BRAM, LISBET, SURVIVOR = story.HALE, story.BRAM, story.LISBET, story.SURVIVOR
MERLIN = story.MERLIN

MAX_LV = {it["attr"]: len(it["prices"]) for shop in CATALOG.values() for it in shop["items"] if "attr" in it}
UPGRADE_NAMES = {it["attr"]: it["name"] for shop in CATALOG.values() for it in shop["items"] if "attr" in it}

# --------------------------------------------------------------------------- #
#  main quest: steps are checked in order; the first one not done is current
# --------------------------------------------------------------------------- #
MAIN_TITLE = "Beyond the Veil"
MAIN = [
    ("Chapter I - The Anchor of Thorns", (138, 214, 120), [
        dict(text="Defeat the Goblin King in the Goblin Dungeon (west road)",
             done=lambda s: "goblin" in s.cleared, where="portal:goblin"),
        dict(text="Shatter the Anchor of Thorns where the Goblin King fell",
             done=lambda s: "goblin" in s.keepsakes, where="portal:goblin"),
        dict(text="Return to Oakwood and tell Elder Maren",
             done=lambda s: "beat_goblin" in s.flags, where="npc:maren"),
    ]),
    ("Chapter II - The Anchor of Blood", (240, 120, 90), [
        dict(text="Defeat the Berserkers' Minotaur (east road)",
             done=lambda s: "berserker" in s.cleared, where="portal:berserker"),
        dict(text="Shatter the Anchor of Blood in the Berserker hall",
             done=lambda s: "berserker" in s.keepsakes, where="portal:berserker"),
        dict(text="Return to Oakwood and report to Maren",
             done=lambda s: "beat_berserker" in s.flags, where="npc:maren"),
    ]),
    ("Chapter III - The Anchor of Bone", (190, 140, 255), [
        dict(text="Defeat the Lich King in the north",
             done=lambda s: "lich" in s.cleared, where="portal:lich"),
        dict(text="Shatter the Anchor of Bone, the keystone of the Veil",
             done=lambda s: "lich" in s.keepsakes, where="portal:lich"),
        dict(text="Return to Oakwood and see the sky",
             done=lambda s: "finished" in s.flags, where="npc:maren"),
    ]),
]

# --------------------------------------------------------------------------- #
#  side quests
#    item      : flag prefix of the things to collect (got_<item>_...)
#    need      : how many
#    where     : "landmark:<kind>" | "portal:<dungeon id>" for map markers
#    dungeon   : (dungeon id, items per floor) when the items are found in a dungeon
#    reward    : gold / potions / upgrade (shop attr) / hp (SaveState.BONUS_HP flag)
# --------------------------------------------------------------------------- #
SIDE = [
    dict(id="pip_sword", giver="pip", title="Goblinbane", min_stage=0,
         item="sword", need=1, where="landmark:sword", item_name="Pip's wooden sword",
         hint="Search the Old Mill, west in the Whisperwood",
         goal="Find Pip's wooden sword at the Old Mill, in the Whisperwood west of the village",
         offer=[(PIP, "Psst! Can you keep a secret? I went to the Old Mill. In the Whisperwood. Alone."),
                (PIP, "I was hunting goblins with Goblinbane, that's my sword, and then a crow screamed and I ran and I... dropped it."),
                (PIP, "Mum says if I go back there she'll feed me to the sheep. Could you get it? Please?"),
                (H, "A goblin hunter shouldn't be without his sword. I'll look for it.")],
         remind=[(PIP, "Goblinbane is still out at the Old Mill. West, through the trees. Past the scary crows.")],
         turnin=[(PIP, "GOBLINBANE! You found it! Did you see any goblins? Did you fight them?"),
                 (H, "Just one very rude crow."),
                 (PIP, "I knew it. Here, I've been saving these for a real hero. Don't tell Mum where I keep them.")],
         reward=dict(gold=40)),
    dict(id="bram_hens", giver="bram", title="Runaway Hens", min_stage=0,
         item="hen", need=3, where="landmark:hen", item_name="runaway hens",
         goal="Catch Old Bram's three runaway hens (red ribbons) in the wilds",
         offer=[(BRAM, "Three of my hens bolted when last night's raid came through. Best layers I ever had."),
                (BRAM, "Gertrude, Mabel and Duchess. Red ribbons round their necks, so you'll know them."),
                (BRAM, "My knees can't chase hens through the woods any more. Shoo them home for me, would you?"),
                (H, "Gertrude, Mabel and Duchess. Got it.")],
         remind=[(BRAM, "Still missing a hen or three. They like open ground, away from the village. Look for the red ribbons.")],
         turnin=[(BRAM, "All three home and fussing like nothing happened. Duchess even laid an egg out of spite."),
                 (BRAM, "Here. It isn't much, but a summoned hero shouldn't walk into a goblin den without a potion in their pocket.")],
         reward=dict(gold=50, potions=1)),
    dict(id="lisbet_letter", giver="lisbet", title="Letters to the Lost", min_stage=0,
         item="letter", need=1, where="landmark:memorial", item_name="Lisbet's letter",
         hint="Take the letter to the Wall of Names, far east",
         goal="Lay Lisbet's letter at the Wall of Names on the eastern overlook, where the Veil is closest",
         offer=[(LISBET, "On the eastern overlook there's a stone wall where we carve the names of everyone we've lost. To the raids, or to the Veil."),
                (LISBET, "Aldric's name is there. My husband. He walked into the Veil eleven years ago, swearing he'd find a way through."),
                (LISBET, "I write him a letter every year, but I can't make myself walk up there any more. Would you leave this one for me?"),
                (H, "I'll take it to him.")],
         remind=[(LISBET, "The Wall of Names is east of the village, past the end of the south-east road. Thank you for doing this.")],
         turnin=[(H, "I left it under a stone so the wind won't take it. The Veil was so close I could hear it humming."),
                 (LISBET, "...Thank you. I feel lighter, somehow."),
                 (LISBET, "Take this. My grandmother wove it for luck. I think you need it more than I do.")],
         reward=dict(hp="hp_charm", text="Lisbet's Charm: +4 max HP")),
    dict(id="torvin_scrap", giver="torvin", title="Scrap for the Forge", min_stage=0,
         item="scrap", need=5, where="portal:goblin", item_name="Goblin scrap iron",
         dungeon=("goblin", (2, 2, 2)),
         goal="Bring Torvin 5 pieces of goblin scrap iron from the Goblin Dungeon",
         offer=[(TORVIN, "Iron's scarce. Nothing comes through the Veil, not even ore. But goblins hoard everything. Pots, nails, half a plough."),
                (TORVIN, "Bring me five lumps of their scrap iron and I'll fold it into your blade. No charge."),
                (H, "Scrap iron from a goblin den. Sounds like a fair trade.")],
         remind=[(TORVIN, "Scrap iron. Five pieces. The goblins leave it lying about in their rooms. Look for the rusty glint.")],
         turnin=[(TORVIN, "Ha! Good, heavy stuff. Goblins steal well, I'll give them that."),
                 (TORVIN, "Hand me your sword. ...There. Folded twice and honed. Merlin chose well when he summoned you.")],
         reward=dict(upgrade="sword_lv", gold_if_max=120)),
    dict(id="wren_moonpetal", giver="wren", title="Moonpetals", min_stage=1,
         item="petal", need=5, where="landmark:petal", item_name="Moonpetals",
         goal="Gather 5 Moonpetals. They only bloom after dusk",
         offer=[(WREN, "Moonpetals. Silver flowers that only open at night, when the raids come. Crushed into a potion, they knit flesh twice as fast."),
                (WREN, "They grow wild around the meadows south of the north road. But they close up tight in daylight."),
                (WREN, "Pick me five after dusk and I'll brew you something special."),
                (H, "Flower picking in the dark. Sure, why not.")],
         remind=[(WREN, "Five Moonpetals. Wait for dusk, then look for the silver glow in the grass.")],
         turnin=[(WREN, "Oh, they're perfect. Still glowing."),
                 (WREN, "I've folded them into my mending herbs. Every potion you drink will hit harder now. And take two for the road.")],
         reward=dict(upgrade="herb_lv", gold_if_max=100, potions=2)),
    dict(id="maren_shrines", giver="maren", title="The Old Wayshrines", min_stage=1,
         item="shrine", need=4, where="landmark:shrine", item_name="wayshrines visited",
         goal="Visit the four ancient wayshrines hidden around the vale",
         offer=[(MAREN, "Four standing stones ring this valley. The wayshrines. They were here before the Veil, before Oakwood even."),
                (MAREN, "Merlin won't speak of how the Veil was made. But the stones remember. Visit them. Read what's carved there."),
                (MAREN, "If we're to live beyond the Veil one day, we should know why it was raised."),
                (H, "Four stones. I'll find them.")],
         remind=[(MAREN, "Four wayshrines: one in the deep west woods, one on the eastern hills, one near the red ridge, one at the edge of the barrows.")],
         turnin=[(H, "The stones tell the same story. The Veil was raised by two masters, to hide this valley from a great war."),
                 (MAREN, "Two? Then one of them was surely our Merlin. And the other..."),
                 (MAREN, "Kneel. ...There. An old blessing, from an old woman. May the vale keep you as you keep it.")],
         reward=dict(hp="hp_blessing", gold=60, text="Vale's Blessing: +6 max HP")),
    dict(id="hale_scouts", giver="hale", title="The Missing Scouts", min_stage=1,
         item="badge", need=3, where="portal:berserker", item_name="scout badges",
         dungeon=("berserker", (1, 1, 1)),
         goal="Recover the 3 lost scouts' badges in the Berserker Warriors Dungeon",
         offer=[(HALE, "I sent three scouts east to follow a raid back to its den. Tamsin, Orrin, and young Fenn."),
                (HALE, "None came back. If they fell in that place, their badges will be there. One on each level, if I know them."),
                (HALE, "I'd like their families to have something to hold. Bring the badges home."),
                (H, "I'll bring them home, Captain.")],
         remind=[(HALE, "Three badges. Silver, with Oakwood's acorn. Tamsin, Orrin, Fenn. Look on every level of the Berserker hall.")],
         turnin=[(HALE, "Tamsin's. Orrin's. And Fenn's... he was barely older than Pip."),
                 (HALE, "...Thank you. Their families will sleep easier."),
                 (HALE, "Torvin forged this mail for Fenn. It was too big for him. It isn't too big for you.")],
         reward=dict(upgrade="armor_lv", gold_if_max=150)),
    dict(id="survivor_embers", giver="refugee", title="Shards for the Ward", min_stage=2,
         item="shard", need=3, where="portal:lich", item_name="ward shards",
         dungeon=("lich", (1, 1, 1)),
         goal="Find 3 ward shards in the Lich King Dungeon so Merlin's ward can cover the farms",
         offer=[(SURVIVOR, "Our farms sit outside Merlin's ward. Every raid, we lose another barn, another field."),
                (SURVIVOR, "He says the Lich's halls are full of ward-glass, chipped off the Anchor of Bone. With enough of it he could stretch the ward over us."),
                (SURVIVOR, "Find them for us. One on each level, maybe. Please."),
                (H, "I'll bring back every shard I find.")],
         remind=[(SURVIVOR, "Three ward shards. They glow, Merlin says. Like a candle behind blue glass.")],
         turnin=[(SURVIVOR, "They're glowing! Merlin! Merlin, come and look!"),
                 (MERLIN, "Oh, that will do nicely. The farms will sleep under the ward tonight."),
                 (SURVIVOR, "We've been saving what coin the raids didn't take. It's yours. Every bit of it.")],
         reward=dict(gold=180, potions=2)),
]
SIDE_BY_ID = {q["id"]: q for q in SIDE}
ITEM_SPECS = {q["item"]: q for q in SIDE}


def reward_text(q):
    r = q["reward"]
    parts = []
    if r.get("upgrade"):
        parts.append("%s upgrade" % UPGRADE_NAMES.get(r["upgrade"], r["upgrade"]))
    if r.get("text"):
        parts.append(r["text"])
    if r.get("gold"):
        parts.append("%d gold" % r["gold"])
    if r.get("potions"):
        parts.append("%d potion%s" % (r["potions"], "s" if r["potions"] > 1 else ""))
    return ", ".join(parts)


def count_items(flags, item):
    p = "got_%s_" % item
    return sum(1 for f in flags if f.startswith(p))


class QuestBook:
    def __init__(self, save):
        self.save = save

    # ---- state ------------------------------------------------------------------
    def state(self, q):
        f = self.save.flags
        if "qdone_" + q["id"] in f:
            return "done"
        if "q_" + q["id"] in f:
            return "ready" if self.count(q) >= q["need"] else "active"
        if self.save.stage >= q["min_stage"]:
            return "available"
        return "locked"

    def count(self, q):
        return min(q["need"], count_items(self.save.flags, q["item"]))

    def active(self, q_or_item):
        q = ITEM_SPECS.get(q_or_item) if isinstance(q_or_item, str) else q_or_item
        return q is not None and self.state(q) == "active"

    def for_npc(self, npc_id):
        return [q for q in SIDE if q["giver"] == npc_id]

    def marker(self, npc_id):
        states = [self.state(q) for q in self.for_npc(npc_id)]
        if "ready" in states:
            return "ready"
        if "available" in states:
            return "quest"
        return None

    def tracked(self):
        """Side quests in progress (accepted, not handed in)."""
        return [q for q in SIDE if self.state(q) in ("active", "ready")]

    def dungeon_quests(self, sid):
        return [q for q in SIDE if q.get("dungeon") and q["dungeon"][0] == sid and self.state(q) == "active"]

    def main_step(self):
        """(chapter index, chapter title, colour, step) for the current step, or None."""
        for ci, (title, col, steps) in enumerate(MAIN):
            for st in steps:
                if not st["done"](self.save):
                    return ci, title, col, st
        return None

    # ---- changes ------------------------------------------------------------------
    def accept(self, q):
        self.save.flags.add("q_" + q["id"])

    def complete(self, q, pc=None):
        """Hand the quest in and pay the reward. Returns a short reward summary."""
        s = self.save
        if pc is not None:
            s.pull_from(pc)
        s.flags.add("qdone_" + q["id"])
        r = q["reward"]
        parts = []
        attr = r.get("upgrade")
        if attr:
            if getattr(s, attr) < MAX_LV.get(attr, 0):
                setattr(s, attr, getattr(s, attr) + 1)
                parts.append("%s +1" % UPGRADE_NAMES.get(attr, attr))
            else:
                s.gold += r.get("gold_if_max", 0)
                parts.append("+%d gold" % r.get("gold_if_max", 0))
        if r.get("hp"):
            s.flags.add(r["hp"])
            parts.append(r.get("text", "max HP up"))
        if r.get("gold"):
            s.gold += r["gold"]
            parts.append("+%d gold" % r["gold"])
        if r.get("potions"):
            got = min(r["potions"], _combat.POTION_MAX - s.potions)
            if got > 0:
                s.potions += got
                parts.append("+%d potion%s" % (got, "s" if got > 1 else ""))
            else:
                s.gold += 15 * r["potions"]
                parts.append("+%d gold" % (15 * r["potions"]))
        if pc is not None:
            s.apply_to(pc)
            if r.get("hp") or attr == "armor_lv":
                pc.hp = pc.max_hp
        return ", ".join(parts)

    def collect(self, item, key):
        """Record one quest item. Returns (count, need, quest) or None if already had."""
        flag = "got_%s_%s" % (item, key)
        if flag in self.save.flags:
            return None
        self.save.flags.add(flag)
        q = ITEM_SPECS[item]
        return self.count(q), q["need"], q

    def progress_text(self, q):
        st = self.state(q)
        if st == "ready":
            return "Return to %s" % story.NPC_NAMES.get(q["giver"], story.SURVIVOR).split(" the ")[0]
        if q["need"] > 1:
            return "%s  %d/%d" % (q["item_name"].capitalize(), self.count(q), q["need"])
        return q.get("hint", q["goal"])
