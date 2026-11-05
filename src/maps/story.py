from __future__ import annotations

import pygame

# ---------------------------------------------------------------------------
# Story text
# Each line is (speaker, text).
#
# THE STORY IN SHORT  (RealmQuest: Beyond the Veil)
#   Oakwood Vale is sealed inside the Veil, a shimmering barrier no one can
#   cross. Three Veil Anchors hold it up, each guarded by a boss deep in a
#   dungeon: the Goblin King (Anchor of Thorns), the Berserkers' Minotaur
#   (Anchor of Blood) and the Lich King (Anchor of Bone). The anchors also
#   breed the monsters that raid Oakwood every night.
#
#   Merlin the Great Sage holds a ward over the village each night, but he is
#   old and his strength is fading. With the last of it he performed a
#   summoning, and the hero Himmel woke in the plaza's stone circle.
#
#   Defeat the three bosses, shatter the three anchors, and the Veil falls.
#   Threads left open for later: who cast the Veil (the "Veilwright", who is
#   still out there), and what Merlin is not telling Himmel about his past.
# ---------------------------------------------------------------------------

HERO = "Himmel"
MERLIN = "Merlin"
MERLIN_STONE = "Merlin (Speaking Stone)"   # Merlin's voice when he isn't there in person
MAREN = "Elder Maren"
TORVIN = "Torvin"
WREN = "Wren"
PIP = "Pip"
HALE = "Captain Hale"
BRAM = "Old Bram"
LISBET = "Lisbet"

INTRO_LINES = [
    (MERLIN, "...Breathe. Slowly. The summoning circle is still warm, and so are you."),
    (HERO, "Where... am I? I don't remember anything before the light."),
    (MERLIN, "You are in Oakwood, Himmel. I am Merlin. Some still call me the Great Sage, though I am mostly just old now."),
    (MERLIN, "I spent the last of my strength calling you here. This valley needs a hero, and I am no longer enough."),
    (MAREN, "Look up, child. That shimmer across the sky is the Veil. No one has left this valley in eleven years."),
    (MERLIN, "Three anchors hold it up, each one buried in a dungeon and guarded by a monster lord."),
    (MERLIN, "And every night the anchors spit out their creatures to claw at our homes. My ward over the plaza is all that stops them."),
    (HERO, "Then the anchors have to break. Where do I start?"),
    (MERLIN, "The Goblin Dungeon, down the west road. Its king guards the Anchor of Thorns. The other two gates won't open until it shatters."),
    (MERLIN, "But the dungeon seals only yield to the strong. Train first: the little caves south-west of here, then the wilds across the river."),
    (MERLIN, "And the Deep Forest in the east... only when you're ready. It's crawling with things that hunt."),
    (MAREN, "See Torvin and Wren first. Gold buys steel and medicine, and you'll need both."),
    (MERLIN, "I can't leave the ward, so take this: a Speaking Stone. Wherever you go, I'll be with you through it."),
    (MERLIN, "And when you need advice, come and find me here by the plaza. Now go, Himmel."),
]

BOSS_DIALOGS = {
    "goblin_archvizier": [
        (HERO, "The Archvizier. I expected a grand strategist. You're mostly hat and bad decisions."),
        ("Goblin Archvizier", "Insults? How quaint. I have calculated eleven thousand ways to end you."),
        (HERO, "Did any of them include ducking? Because your hat is enormous."),
        ("Goblin Archvizier", "Mock me again and I'll have you buried in paperwork before the stabbing!"),
        (HERO, "I'd rather be stabbed. Let's get this over with."),
    ],
    "goblin_warlord": [
        (HERO, "So you're the Goblin Warlord. Do you lead an army, or just yell at smaller goblins?"),
        ("Goblin Warlord", "I conquered these halls with my axe! My troops fear me!"),
        (HERO, "They look less afraid and more like they're waiting for you to finish talking."),
        ("Goblin Warlord", "I'll split you in half and use the pieces as morale posters!"),
        (HERO, "Finally, a plan with fewer words."),
    ],
    "goblin_king": [
        ("Goblin King", "A new one! The old wizard finally found himself a shiny little hero!"),
        (HERO, "You're the one sending goblins into Oakwood every night."),
        ("Goblin King", "The Anchor gives, Valdur takes! Every night it hums, and every night my boys get hungry for village chickens."),
        (MERLIN_STONE, "Careful, Himmel. The anchor is feeding him. Look how the thorns grow out of his throne."),
        (HERO, "Then I'll cut through both of them."),
    ],
    "minotaur": [
        ("Minotaur", "The thorn-anchor broke. I felt it in my horns. So you are the summoned one."),
        (HERO, "Your Berserkers burn the farms outside Oakwood every night. It stops today."),
        ("Minotaur", "The Veil is a pen and we are the wolves inside it. Why would wolves want the gate open?"),
        (MERLIN_STONE, "The Anchor of Blood sits behind him. Every scar on his hide is a ward-mark. Strike where the marks are dark."),
        (HERO, "Wolf or not, you're standing between me and that anchor."),
    ],
    "ragecaller": [
        (HERO, "Ragecaller. You shout so much I thought the dungeon was having a tantrum."),
        ("Ragecaller", "The war gods answer every scream I unleash!"),
        (HERO, "Have you tried asking them to lower the volume?"),
        ("Ragecaller", "I will drown your jokes in a river of rage!"),
        (HERO, "Good. Maybe it'll finally wash that face clean."),
    ],
    "bloodreaver": [
        (HERO, "Bloodreaver. Is the name a warning, or did you just run out of hobbies?"),
        ("Bloodreaver", "My blade has drunk the blood of a thousand warriors!"),
        (HERO, "And somehow it still hasn't learned table manners."),
        ("Bloodreaver", "I'll carve your words into the floor with your own teeth!"),
        (HERO, "That's a lot of work. You should stretch first."),
    ],
    "berserker_king": [
        (HERO, "The Berserker King. Let me guess: your royal decree is 'hit it until it stops moving.'"),
        ("Berserker King", "It is the only decree that matters! Strength is law!"),
        (HERO, "And indoor voices are apparently treason."),
        ("Berserker King", "I will crush you, then crush the memory of you!"),
        (HERO, "You can barely manage a sentence. Let's see you manage a sword."),
    ],
    "dread_marshal": [
        (HERO, "The Dread Marshal. I was expecting a terrifying commander. You look like a haunted coat rack."),
        ("Dread Marshal", "I have marched a million dead souls into battle."),
        (HERO, "And not one of them suggested a better outfit?"),
        ("Dread Marshal", "Your mockery will end when your heart stops!"),
        (HERO, "That would be more convincing if you had a heart to compare."),
    ],
    "eternal_hierophant": [
        (HERO, "The Eternal Hierophant. Keeper of the Final Gate. Do you get dental with that title?"),
        ("Eternal Hierophant", "I guard the sacred threshold between life and oblivion."),
        (HERO, "So, no dental."),
        ("Eternal Hierophant", "I shall erase your soul from the ledger of existence!"),
        (HERO, "Please do. The paperwork sounds awful."),
    ],
    "lich": [
        ("The Lich King", "Merlin. You look old. Older than the last time you tried to break my anchor."),
        (MERLIN_STONE, "And you look exactly the same, which is the saddest thing I can say about anyone."),
        (HERO, "You two know each other?"),
        ("The Lich King", "Ask him who taught the Veilwright to weave barriers, little hero. Ask him why he never left the valley himself."),
        (MERLIN_STONE, "...Later, Himmel. Please. The Anchor of Bone first."),
        ("The Lich King", "Come, then. The last anchor, the last night, the last of you."),
    ],
}

OUTRO_DIALOGS = {
    "goblin_archvizier": [("Goblin Archvizier", "My calculations... did not account for... your face."), (HERO, "One goblin down. Two more crowns to knock crooked."), (HERO, "The portal is open. Onward.")],
    "goblin_warlord": [("Goblin Warlord", "My army... will avenge... my excellent leadership!"), (HERO, "Tell them to put it in writing. I'm not reading it."), (HERO, "The Goblin King is next.")],
    "goblin_king": [
        ("Goblin King", "No more shinies... no more chickens... the anchor will just make another king..."),
        (MERLIN_STONE, "Not if it's in pieces. Quickly, Himmel. The Anchor of Thorns is exposed where he fell."),
    ],
    "minotaur": [
        ("Minotaur", "When the Veil falls... you'll see what was kept out... not just what was kept in..."),
        (HERO, "What does that mean?"),
        (MERLIN_STONE, "It means he's frightened. Shatter the Anchor of Blood, then we talk."),
    ],
    "ragecaller": [("Ragecaller", "The war gods... are silent..."), (HERO, "Maybe they finally got some peace and quiet."), (HERO, "Bloodreaver is next.")],
    "bloodreaver": [("Bloodreaver", "My blade... never failed..."), (HERO, "It failed to hit me. That's a pretty important job."), (HERO, "The Berserker King awaits.")],
    "berserker_king": [("Berserker King", "Only... strength... matters..."), (HERO, "Turns out patience and a sharp sword matter too."), (HERO, "The dead lands are next.")],
    "dread_marshal": [("Dread Marshal", "The dead... will march... without me..."), (HERO, "They deserve a day off."), (HERO, "The Eternal Hierophant guards the final gate.")],
    "eternal_hierophant": [("Eternal Hierophant", "The final gate... stands unguarded..."), (HERO, "Good. I hate waiting in lines."), (HERO, "Now, Lich King. No more servants. No more excuses.")],
    "lich": [
        ("The Lich King", "The Veilwright... will know... the cage is open..."),
        (HERO, "Let them know."),
        (MERLIN_STONE, "The Anchor of Bone, Himmel. The last one. End this."),
    ],
}

BOSS_SPEAKERS = {
    "goblin_archvizier": "Goblin Archvizier", "goblin_warlord": "Goblin Warlord",
    "goblin_king": "Goblin King", "ragecaller": "Ragecaller", "bloodreaver": "Bloodreaver",
    "berserker_king": "Berserker King", "dread_marshal": "Dread Marshal",
    "eternal_hierophant": "Eternal Hierophant", "minotaur": "Minotaur",
    "lich": "The Lich King",
}

# ---------------------------------------------------------------------------
# Lore tablets: one on floor 1 and one on floor 2 of every dungeon.
# Keyed by surface dungeon id -> [floor-1 lines, floor-2 lines]
# ---------------------------------------------------------------------------
TABLET = "Old Tablet"
NOTE = "Scrawled Note"
LEDGER = "Torn Ledger"

LORE = {
    "goblin": [
        [(NOTE, "DA RULES (by order of King Valdur): when da Anchor hums, we go up. Take chickens. Take pots. Run before da wizard-light."),
         (NOTE, "Nobody touch da Anchor. Grubb touched da Anchor. Now Grubb is a tree."),
         (MERLIN_STONE, "So the anchor calls them out at night. That's why the raids always come at the same hour.")],
        [(TABLET, "Carved in an older hand than the goblins': 'Three stones to hold the sky. Thorn, Blood and Bone.'"),
         (TABLET, "'Let the valley be a garden walled from the world, and let the gardener keep the key.'"),
         (HERO, "A garden walled from the world... someone built the Veil on purpose."),
         (MERLIN_STONE, "Yes. Someone did.")],
    ],
    "berserker": [
        [(LEDGER, "TALLY OF NIGHTS: 4,015. Farms burned: many. Gate opened: never."),
         (LEDGER, "The Anchor of Blood feeds the fury. Without it, we would only be men. Do not let it break."),
         (HERO, "Four thousand nights... Oakwood has been fighting this for eleven years."),
         (MERLIN_STONE, "And I have held the ward for every one of them.")],
        [(NOTE, "The horned one says the Veilwright promised us the valley forever, if we keep the stones safe."),
         (NOTE, "Forever is a long time to be angry."),
         (HERO, "The Veilwright again. Merlin, who is that?"),
         (MERLIN_STONE, "Someone I trusted once. Let's keep moving.")],
    ],
    "lich": [
        [(TABLET, "Frost has etched words into the black stone: 'The Bone Anchor is the keystone. Break it last, or the sky will fall unevenly.'"),
         (TABLET, "'Two masters wove the Veil. One stayed to guard it. One stayed to watch it.'"),
         (HERO, "One stayed to watch it... Merlin?"),
         (MERLIN_STONE, "...I have never lied to you, Himmel. I have only been slow to tell the truth.")],
        [(NOTE, "A spidery hand: 'The old sage summoned a hero at last. Good. Let him break the stones.'"),
         (NOTE, "'When the Veil falls, I will see what the valley has grown into. - V.'"),
         (HERO, "The Veilwright wants us to break the Veil?"),
         (MERLIN_STONE, "Or wants us to think so. Either way, Oakwood cannot live one more decade in a cage.")],
    ],
}

# The thing that appears where each boss falls. Internally still called "keepsakes"
# (the save keeps the same ids); in the story they are the three Veil Anchors.
KEEPSAKES = {
    "goblin": ("Anchor of Thorns", [
        (HERO, "The Anchor of Thorns. It's... humming. Like it's alive."),
        (MERLIN_STONE, "Strike it with everything you have. Now!"),
        (HERO, "It shattered! The sky over the west just flickered."),
        (MERLIN_STONE, "One down. Did you feel that? The Veil is thinner already."),
    ]),
    "berserker": ("Anchor of Blood", [
        (HERO, "The Anchor of Blood. It's warm, like a heartbeat."),
        (MERLIN_STONE, "That's the fury it feeds them. Break it, and the Berserkers will just be tired men far from home."),
        (HERO, "...Done. It cracked like ice."),
        (MERLIN_STONE, "Two anchors. Only the keystone left."),
    ]),
    "lich": ("Anchor of Bone", [
        (HERO, "The last anchor. The keystone."),
        (MERLIN_STONE, "When it breaks, the Veil comes down all at once. Whatever happens next, Himmel... thank you."),
        (HERO, "Merlin, what are you not telling me?"),
        (MERLIN_STONE, "Break it. Then I'll tell you everything. I promise."),
    ]),
}

# ---------------------------------------------------------------------------
# Story beats when the hero walks back into Oakwood after a dungeon.
# ---------------------------------------------------------------------------
RETURN_BEATS = {
    "goblin": [
        (MAREN, "You're back! And Pip swears the sky went pale in the west the moment you broke something down there."),
        (HERO, "The Anchor of Thorns is gone. No more goblins at night."),
        (MERLIN, "The goblin raids will stop. But the Berserkers' anchor still burns in the east, and their gate is open now."),
        (MAREN, "The east farms take the worst of the red-eyed raids. Bless you, both of you."),
        (MERLIN, "Rest tonight, Himmel. Tomorrow, the Anchor of Blood."),
    ],
    "berserker": [
        (HALE, "The east road's quiet for the first time in eleven years. That was your doing?"),
        (HERO, "The Anchor of Blood is broken. The Berserkers fought like men, not monsters, at the end."),
        (MERLIN, "The north gate is open now. The Lich King holds the keystone, the Anchor of Bone."),
        (HERO, "He knew you, Merlin. One of the notes said two masters wove the Veil."),
        (MERLIN, "...When the last anchor breaks, I'll tell you the whole story. You have my word as a sage."),
    ],
    "lich": [],
}

EPILOGUE_LINES = [
    (MAREN, "Look. Look at the sky. It's just... blue. Plain, ordinary blue."),
    (PIP, "There's MORE world out there?! How much more?"),
    (HERO, "Merlin. You promised."),
    (MERLIN, "I did. Long ago, the Veilwright and I wove the Veil together, to hide this valley from a war that was burning the world."),
    (MERLIN, "The war ended. The Veilwright did not want to let go. I stayed to protect Oakwood from the cage I helped build."),
    (MERLIN, "And now the cage is open, and somewhere beyond those mountains, my old friend has noticed."),
    (HERO, "Then we'll be ready. Together."),
    (MAREN, "Tonight, for the first time in eleven years, nobody in Oakwood has to watch the woods."),
    (MERLIN, "Sleep well, Himmel. Tomorrow, the world."),
]

# ---------------------------------------------------------------------------
# Oakwood villagers. NPC_LINES[npc_id][stage] where stage = dungeons cleared (0-3).
# ---------------------------------------------------------------------------
NPC_NAMES = {
    "maren": MAREN, "torvin": TORVIN + " the Blacksmith", "wren": WREN + " the Herbalist",
    "pip": PIP, "hale": HALE, "bram": BRAM, "lisbet": LISBET, "merlin": MERLIN + " the Great Sage",
}

NPC_LINES = {
    "maren": [
        [(MAREN, "The Goblin Dungeon is down the west road. Look for the green fire."),
         (MAREN, "Break their pots and crates. Goblins hide coin everywhere, and Torvin doesn't work for free.")],
        [(MAREN, "The east gate is open. The Berserkers fight in a frenzy, so don't trade blows. Dash past and strike."),
         (MAREN, "Merlin looks lighter since the first anchor broke. Like a weight came off him.")],
        [(MAREN, "The north... I can feel the cold from here. The Lich King's anchor is the last one."),
         (MAREN, "Whatever Merlin isn't saying, he summoned you to save us. Hold on to that.")],
        [(MAREN, "Eleven years under that shimmer, and now a plain blue sky. I keep looking up.")],
    ],
    "torvin": [
        [(TORVIN, "So you're the one Merlin pulled out of thin air. Bring me gold and I'll make you steel worth summoning.")],
        [(TORVIN, "Goblin King's dead? Ha! I owe you a drink. Here, look at what I've forged.")],
        [(TORVIN, "Berserker steel melts nicely. I've been reworking a few of their blades. Have a look.")],
        [(TORVIN, "No more raids, eh? Then I'll start making ploughs. The east farms need rebuilding.")],
    ],
    "wren": [
        [(WREN, "Potions, herbs, and something for the nerves. Night raids are hard on everyone's nerves.")],
        [(WREN, "You came back smelling like goblin. Try my mending herbs, they make every potion stronger.")],
        [(WREN, "Frostroot grows wild near the north gate now. It's a bad sign. Stock up before you go.")],
        [(WREN, "I'm brewing tea instead of medicine for the night watch. Have a cup, on the house. ...Then buy something.")],
    ],
    "pip": [
        [(PIP, "You're the summoned hero?! Did it hurt? Were you made of light? Can Merlin summon ME a dragon?")],
        [(PIP, "You beat the Goblin King! I made a crown out of leaves. I'M the Goblin King now. Raaah!")],
        [(PIP, "Captain Hale says you're the bravest person in the whole valley. I'm the second bravest.")],
        [(PIP, "When we go see the rest of the world, I'm coming. I already packed. It's mostly rocks.")],
    ],
    "hale": [
        [(HALE, "North gate's sealed, east gate's sealed. Only the west road is open, and it's full of goblins."),
         (HALE, "When the horn sounds at night, get to the road they're coming from. Merlin's ward can't hold forever.")],
        [(HALE, "Berserkers rush you when the room seals. Don't get caught against a wall. Keep moving.")],
        [(HALE, "The Lich King's halls are full of lava and bone. Don't stand still, and don't look down.")],
        [(HALE, "For the first time in eleven years, I'm guarding a gate against nothing. It's wonderful.")],
    ],
    "bram": [
        [(BRAM, "Goblins took three of my hens last night. Three! The ward can't stop a goblin that wants a hen.")],
        [(BRAM, "No goblins last night. My hens stayed put. Well, mostly.")],
        [(BRAM, "No red-eyed brutes in the fields either? I'll sleep with both eyes closed tonight. First time in years.")],
        [(BRAM, "A world past the Veil. I wonder if they have better chickens out there.")],
    ],
    "lisbet": [
        [(LISBET, "My Aldric walked into the Veil eleven years ago. He said he'd find a way out and come back for me.")],
        [(LISBET, "One anchor gone. I keep looking at the shimmer, as if he'll just walk back through it.")],
        [(LISBET, "Be careful in the north. Please. We can't lose anyone else to that sky.")],
        [(LISBET, "The Veil's gone. If Aldric is out there, he'll see the blue sky too. Thank you.")],
    ],
    "merlin": [
        [(MERLIN, "The Goblin Dungeon lies west. Floors one and two each hide a key to the stairs. Floor three, the king himself."),
         (MERLIN, "At night, listen for the horn. If a raid comes, meet it on the road before it reaches my ward.")],
        [(MERLIN, "The east gate stands open. Berserkers hit hard and fast. Keep your potions close and your feet moving."),
         (MERLIN, "And Himmel... thank you. I haven't felt this light in years.")],
        [(MERLIN, "The north. The Lich King holds the keystone. He will try to turn you against me with half-truths."),
         (MERLIN, "When it's done, I'll tell you the whole of it. I promise.")],
        [(MERLIN, "Beyond the mountains, the Veilwright is waking up to an open cage. We have a little time. Rest while you can.")],
    ],
}

# The families from the outlying farms, burned out by the raids, now camping in Oakwood.
SURVIVOR = "Farmstead Folk"
REFUGEE_LINES = [
    [(SURVIVOR, "Our farm was the last one on the east road. The red-eyed ones burned it the night the goblin anchor broke."),
     (SURVIVOR, "Merlin says the anchors drop shards of ward-glass when they crack. If we had enough, his ward could cover the farms too.")],
    [(SURVIVOR, "When the Veil comes down, the first thing I'm doing is planting barley somewhere nobody's ever burned."),
     (SURVIVOR, "Then I'm sleeping for a week.")],
]

SHOP_INTRO = {
    "torvin": "Torvin's Forge",
    "wren": "Wren's Remedies",
}

# Overworld places you can read (see world_lore.py)
SHRINE = "Wayshrine"
MEMORIAL = "The Wall of Names"
BOARD = "Notice Board"

# Short lines villagers say out loud when you walk past: (min stage, max stage, text)
NPC_BARKS = {
    "maren": [(0, 3, "The old songs never lie."), (0, 0, "Mind the west road."), (1, 2, "The Veil is thinning..."),
              (3, 3, "Such a blue sky.")],
    "torvin": [(0, 3, "*clang* *clang*"), (0, 3, "Fresh steel! Sharp as gossip!"), (1, 3, "Goblin iron. Ugh."),
               (0, 2, "Need a blade for tonight?")],
    "wren": [(0, 3, "Mint, sage, nettle..."), (0, 3, "Potions! Red ones only!"), (1, 3, "Where are my moonpetals..."),
             (0, 2, "Bandages for the night watch...")],
    "pip": [(0, 3, "Hyah! Take that, goblin!"), (0, 0, "Where's my sword..."), (1, 3, "I'm the Goblin King now!"),
            (0, 3, "Merlin can do REAL magic!")],
    "hale": [(0, 3, "All quiet. For now."), (0, 2, "Eyes on the road."), (1, 2, "Tamsin... Orrin... Fenn..."),
             (0, 2, "Horn's ready for tonight."), (3, 3, "Peace suits this valley.")],
    "bram": [(0, 3, "Back in my day..."), (0, 0, "Gertrude? Mabel? Duchess?"), (0, 3, "My knees say rain."),
             (2, 3, "Chickens are laying again.")],
    "lisbet": [(0, 3, "La la la..."), (0, 1, "Apples, fresh apples!"), (0, 3, "Aldric loved this tune."),
               (2, 3, "Welcome, farm folk.")],
    "refugee": [(1, 3, "Warm fire. Thank you, Oakwood."), (1, 3, "We'll rebuild. Somehow."), (1, 3, "No raid tonight, please...")],
    "merlin": [(0, 3, "Hmm."), (0, 2, "The Veil hums tonight."), (0, 3, "Mind your footing."),
               (0, 2, "My ward holds. For now."), (3, 3, "Blue. I'd forgotten.")],
}

# Merlin's lines when a night raid starts and ends (he says them in the plaza)
MERLIN_BARKS = {
    "raid":        ["The horn! Quickly, to the road!", "Here they come. I'll hold the ward, you hold the road!"],
    "raid_won":    ["They're running! Oakwood stands another night.", "Well fought. The ward barely felt a scratch."],
    "raid_lost":   ["Enough! *BOOM* ...They're gone. But that cost me. Rest, Himmel.",
                    "I've driven them off, but the ward is cracked. We'll do better tomorrow."],
}

# First-raid tutorial
RAID_INTRO = [
    (MERLIN, "Himmel! The horn! The anchor's creatures are coming down the road."),
    (MERLIN, "My ward covers the plaza, but every claw that reaches it weakens it. Meet them on the road!"),
    (MERLIN, "Space or a click to strike. H to drink a potion. Go!"),
]

NAME_COLORS = {HERO: (255, 226, 140), MERLIN: (150, 190, 255), MERLIN_STONE: (150, 190, 255)}
for _n in (MAREN, TORVIN, WREN, PIP, HALE, BRAM, LISBET, SURVIVOR):
    NAME_COLORS[_n] = (140, 220, 150)
for _n in (TABLET, NOTE, LEDGER, SHRINE, MEMORIAL, BOARD):
    NAME_COLORS[_n] = (190, 200, 230)
ENEMY_NAME_COLOR = (255, 110, 100)


def _fit(img, max_w, max_h):
    """Scale a sprite to fit the portrait frame (crisp when enlarging)."""
    w, h = img.get_size()
    k = min(max_w / w, max_h / h)
    if k >= 1:
        k = int(k)
        return pygame.transform.scale(img, (w * k, h * k))
    return pygame.transform.smoothscale(img, (max(1, int(w * k)), max(1, int(h * k))))


class Dialog:
    """Typewriter dialog box.

    lines     : list of (speaker, text) or plain strings (spoken by the Hero)
    portraits : {speaker: pygame.Surface}
    Controls  : advance() = next line (finishes typing first), skip() = close.
    """

    def __init__(self, lines=INTRO_LINES, portraits=None, cps=48.0):
        self.lines = [(HERO, ln) if isinstance(ln, str) else tuple(ln) for ln in lines]
        self.cps = cps
        self.idx = 0
        self.shown = 0.0
        self.done = False
        self.font = pygame.font.Font(None, 32)
        self.small = pygame.font.Font(None, 22)
        self.name_font = pygame.font.Font(None, 30)
        self.portraits = {}
        self.standing = {}            # big character portraits shown above the box
        for who, img in (portraits or {}).items():
            if img is None:
                continue
            if img.get_height() >= 200:
                self.standing[who] = img
            else:
                self.portraits[who] = _fit(img, 104, 136)

    @property
    def active(self):
        return not self.done

    def _text(self):
        return self.lines[self.idx][1]

    def update(self, dt):
        if not self.done:
            self.shown = min(len(self._text()), self.shown + dt * self.cps)

    def advance(self):
        if self.done:
            return
        if self.shown < len(self._text()):
            self.shown = len(self._text())
            return
        self.idx += 1
        self.shown = 0.0
        if self.idx >= len(self.lines):
            self.done = True

    def skip(self):
        self.done = True

    def wrap(self, text, width):
        words, out, cur = text.split(" "), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if self.font.size(test)[0] <= width:
                cur = test
            else:
                out.append(cur)
                cur = w
        out.append(cur)
        return out

    def draw(self, surf, t):
        if self.done:
            return
        speaker, line = self.lines[self.idx]
        W, H = surf.get_size()
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 175))
        surf.blit(veil, (0, 0))

        box = pygame.Rect(60, H - 250, W - 120, 200)
        big = self.standing.get(speaker)
        if big:      # the speaker stands above the left of the box, feet tucked behind it
            surf.blit(big, (box.x + 14, box.y - big.get_height() + 36))
        pygame.draw.rect(surf, (14, 14, 22), box, border_radius=10)
        pygame.draw.rect(surf, (214, 176, 84), box, 3, border_radius=10)
        pygame.draw.rect(surf, (96, 76, 40), box.inflate(-10, -10), 1, border_radius=7)

        tx = box.x + 28
        portrait = self.portraits.get(speaker)
        if portrait:
            frame = pygame.Rect(box.x + 24, box.y + 24, 120, 152)
            pygame.draw.rect(surf, (24, 24, 36), frame, border_radius=6)
            pygame.draw.rect(surf, (214, 176, 84), frame, 2, border_radius=6)
            surf.blit(portrait, portrait.get_rect(center=frame.center))
            tx = frame.right + 28

        col = NAME_COLORS.get(speaker, ENEMY_NAME_COLOR)
        surf.blit(self.name_font.render(speaker, True, col), (tx, box.y + 18))

        # wrap the full line first so words don't jump while typing, then cut by chars
        full = self.wrap(line, box.right - tx - 28)
        left = int(self.shown)
        y = box.y + 56
        for ln in full:
            part = ln[:max(0, left)]
            left -= len(ln) + 1
            if part:
                surf.blit(self.font.render(part, True, (240, 240, 244)), (tx, y))
            y += 34

        if self.shown >= len(line) and int(t * 2) % 2 == 0:
            p = self.small.render("ENTER / SPACE  >", True, (255, 226, 140))
            surf.blit(p, (box.right - p.get_width() - 22, box.bottom - 30))
        info = self.small.render(f"{self.idx + 1}/{len(self.lines)}   Esc: skip", True, (150, 150, 162))
        surf.blit(info, (tx, box.bottom - 30))
