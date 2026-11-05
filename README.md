# RealmQuest
This repository contains a fantasy role-playing game developed as an educational project. It is intended to provide students with practical experience in software development, quality assurance, version control, collaborative teamwork, and DevOps practices. The project is created for learning purposes and is not intended for commercial use.

---

# RealmQuest: Beyond the Veil

A fantasy action RPG prototype in Pygame. Oakwood Vale is sealed inside **the Veil**, and monsters raid the village every night. You are **the hero you create** (your own name, and Warrior, Mage or Archer), summoned by **Merlin the Great Sage**, who guards the village and guides you from Oakwood. Explore the village, defend it at night, and fight through three dungeons to shatter the three **Veil Anchors** and free Oakwood.

See [CAMPAIGN_STORY.md](CAMPAIGN_STORY.md) for the story, the dungeon route and the villagers.

## Run the game
From the project root:

```bash
python -m pip install pygame-ce
python run_map.py            # or: python -m src.maps.dungeon_map
```

Progress is saved automatically to `savegame.json` in the project root:
- when you change floors,
- when you return to the village,
- after shopping,
- when you shatter an anchor,
- after a night raid.

## Home, your hero and the story
- **Home screen:** Continue (shown when there is a save, with your hero's name, class, level and anchors), New Game, Settings and Exit.
- **New Game:** type your hero's name (or press Tab / the dice for a random one), choose **Warrior**, **Mage** or **Archer**, and you are straight in Oakwood.
- **The story uses your name** everywhere: every dialog, the journal, toasts and the ending. (Saves from before this update load as Himmel the Warrior.)
- **Settings** (home screen or the pause menu): volumes, fullscreen and key bindings. They are saved to `.realmquest_settings.json` in your home folder.
- **Pause (Esc):** Resume, Settings, Save & Quit to Menu, Quit Game.

Delete `savegame.json` to reset.

## The three heroes
| | Warrior | Mage | Archer |
|---|---|---|---|
| HP | 48 | 34 | 40 |
| Bars | Stamina 100, Energy 100 | Mana 120, Stamina 80 | Stamina 110, Energy 100 |
| Basic attack | Sword (+1 damage) | Staff | Dagger (fastest) |
| K | Whirlwind: spin, hits all around | Fireball: explodes on impact | Arrow Volley: three arrows |
| U | Shield Bash: lunge, stuns | Frost Nova: ring that slows | Piercing Shot: goes through enemies |
| F (special) | Earthsplitter: huge cone slam | Meteor: falls where you face | Rain of Arrows: 3 s of arrows on an area |

- **Stamina** pays for the dash (25 each) and refills quickly.
- **Mana** (Mage) refills steadily. **Energy** (Warrior, Archer) refills slowly and also fills when your basic attacks land.
- Skills and the dash work **in the overworld and in every dungeon**. The skill bar (bottom right) shows cooldowns, costs and keys.
- The numbers live in `src/skills/classes.py` and `src/skills/skills.py`.

## Controls
- **WASD / Arrow keys:** move
- **Space / J / Left click:** basic attack (also breaks pots and crates)
- **K / U / F:** skill 1, skill 2, special
- **Shift:** dash (costs stamina)
- **H / P:** healing potion
- **E / Enter:** talk, open doors and gates, read tablets, drink from fonts, enter portals
- **Tab / L:** journal (quests and lore)
- **Q:** previous floor (on a first floor, back to Oakwood)
- **R:** retry the room after dying
- **M:** toggle minimap
- **Esc:** pause

## Quests and the world
- **Main quest** (*Beyond the Veil*): three chapters, one per dungeon. The current step is always shown in the tracker under your gold, with a gold diamond on the minimap.
- **Eight side quests** from the villagers. A gold **!** over someone means they have a quest; a gold **?** means you can hand one in. A white **!** means they just have news.

| Quest | Given by | What you do | Reward |
|---|---|---|---|
| Goblinbane | Pip | Find his wooden sword at the Old Mill | 40 gold |
| Runaway Hens | Old Bram | Catch 3 hens with red ribbons in the wilds | 50 gold, potion |
| Letters to the Lost | Lisbet | Leave her letter at the Wall of Names | +4 max HP |
| Scrap for the Forge | Torvin | 5 goblin scrap iron from the Goblin Dungeon | Free sword upgrade |
| Moonpetals | Wren (after dungeon 1) | Pick 5 flowers that only bloom at night | Free herb upgrade, 2 potions |
| The Old Wayshrines | Maren (after dungeon 1) | Visit the 4 ancient wayshrines | +6 max HP, 60 gold |
| The Missing Scouts | Captain Hale (after dungeon 1) | 3 scout badges from the Berserker Dungeon | Free armor upgrade |
| Shards for the Ward | Farmstead Folk (after dungeon 2) | 3 ward shards from the Lich King Dungeon | 180 gold, 2 potions |

- **Places to find:** four wayshrines that tell the valley's history, the Wall of Names at Veil's Edge on the eastern overlook, the ruined Old Mill in the Whisperwood, and a notice board in the plaza whose rumours change as the story moves on.
- **Named regions** (Whisperwood, Goblin Hollow, Red Ridge, The Barrowlands, Eastmarch Hills...) show a title banner when you walk in.
- **Villagers** chat in speech bubbles as you pass, and each has a hand-drawn portrait in the dialog box.
- **Journal (Tab):** every quest with progress, plus all the lore you've read (wayshrines, tablets, the Wall of Names, anchors).

## Growing stronger
Himmel earns **XP** from every monster he kills, from clearing mini dungeons, destroying lairs, winning night raids and finishing world events.
- **Each level:** +4 max HP, and +1 sword damage every third level. A level-up fully heals him.
- **The level badge and XP bar** sit next to the HP bar.
- **The main dungeons are sealed until Himmel is strong enough:**

| Dungeon | Needs |
|---|---|
| Goblin Dungeon | Level 3 |
| Berserker Warriors Dungeon | Level 7 (and the Goblin King defeated) |
| Lich King Dungeon | Level 12 (and the Berserkers defeated) |

- **Out of combat** in the overworld, Himmel slowly heals.
- **If he falls in the wilds,** Merlin carries him home, at a cost of 10% of his gold (at most 30).
- **Overworld XP is deliberately small** (monsters, lairs, events and raids give half as much as before). The mini dungeons and the main dungeons are the main way to level.

## The wider vale
The overworld is now about twice as big (4400 x 3200).
- **Roads:** grey cobbled roads run from Oakwood north to the Lich King and east to the Deep Forest. The **Kingsroad** runs south over the Silverrun River to the hamlet of **Millbrook** and its fields.
- **The river** can only be crossed at the **Silverrun Bridge** (stone) and the **Old Ford Bridge** (wooden).
- **Mini dungeons:** six caves, short and replayable. Each is one floor of 6–7 rooms ending in a **lair** with a mini-boss. Every visit is a new layout, with XP and gold each time, plus a bonus for the first clear.

| Mini dungeon | Where | Level |
|---|---|---|
| Mossy Burrow | South-west of Oakwood | 1-3 |
| Thornwood Den | Above the Old Ford Bridge | 2-4 |
| Old Watchtower | Across the river, west | 4-7 |
| Sunken Crypt | East of Millbrook | 5-8 |
| Ashen Pit | Deep Forest, north | 8-11 |
| Bone Hollow | Deep Forest, east | 9-12 |

- **The Deep Forest** (east) is swarming with roaming packs: wild boars at its edge, shadow stalkers and forest wraiths deeper in. Weaker packs (red, blue and green slimes, goblin scouts, bandits) roam the Thornwood and the Southfields. Packs chase you when you get close and come back a while after you wipe them out.
- **Monster lairs:** six hide tents (Slime Den, Goblin Camp, Bandit Camp, Boar Warren, Stalker Nest, Wraith Barrow). They keep sending out monsters while you're near. Destroy one for XP and gold; it's rebuilt a few minutes later.
- **World events,** every couple of minutes:
  - **A champion** roams somewhere for a while. Hunt it down for big XP and gold.
  - **A merchant caravan** is attacked on the Kingsroad. Save it for gold and a potion.
  - Events are marked on the minimap, with a timer at the bottom of the screen.
- **Your attacks, skills and dash work anywhere** in the overworld.
- **Champions:** Gloomgut the Great Slime, Black Tusk (a huge wild boar) and the Hollow Widow.

## Night raids
Every night at nightfall, if Himmel is near Oakwood, monsters come down the road from the dungeon you're working on. If he's away exploring, a distant horn sounds and Captain Hale's watch holds the village, with no reward and no penalty.
- **Merlin** holds his ward over the plaza. Every monster that reaches it weakens it.
- **Meet them on the road** with **Space / J / click**. There are 2–3 waves.
- **Win:** gold. **Lose** (the ward breaks or you fall): Merlin drives them off, you wake in the plaza, and it costs a little gold.
- **No game over.** Once all three anchors are shattered, the raids stop.

## Merlin
Merlin lives in Oakwood. He stays by his ward on the east side of the plaza; he doesn't follow Himmel.
- **Advice:** talk to him (E) for the next step. When you're under-levelled, he suggests a mini dungeon that suits you.
- **The Speaking Stone:** he gave Himmel a stone in the intro. In dungeons and at the wayshrines, his lines come through it as "Merlin (Speaking Stone)".
- **During raids:** he stands in the middle of the plaza holding the ward.

## Dungeons
Each dungeon has 3 floors, and **every visit generates new floors**. A floor is about 10 rooms: a main path from the entrance to the stairs (or the boss), with side branches, dead ends and the odd loop.

| Floor | To move on | Who holds it |
|---|---|---|
| X-1 | **Floor key** opens the locked stairs door | An elite pack in the **guard room**, somewhere down a side branch |
| X-2 | **Floor key** opens the locked stairs door | A **mini-boss**, reached through a spike-trap gauntlet |
| X-3 | **3 boss seals** open the boss gate | Two **seal rooms** and a **mini-boss**. The gate leads from the antechamber to the boss chamber, the biggest room on the floor |

- **Room types:** entrance, combat rooms (chambers, long halls), guard room, mini-boss arena, seal rooms, treasure vault (big chest), shrine (a healing font, one drink per visit), trap gauntlet, stairs, antechamber and the boss chamber.
- **Only rooms with monsters lock** when you walk in. Side branches you don't need can be skipped.
- **The map draws itself as you explore.** A floor starts blank apart from the entrance. Walking into a room inks the whole room in, corridors appear only where you walk, and doorways show a short stub so you know an exit is there. Once you've found every room on a floor you get a **"Floor mapped!" gold bonus**.
- **The minimap** marks the key, seals, shrines and the locked gate once you've discovered them. The HUD shows what you still need.
- **Going back up (Q)** finds the floor exactly as you left it. Leaving the dungeon and coming back gives brand-new floors.
- **Dying** restarts the room from the room you came from.

### The Goblin Dungeon's monsters
The Goblin Dungeon, its two goblin caves (Mossy Burrow, Thornwood Den) and the goblins' night raids use the monster sprites:
- **Goblin Shaman:** keeps its distance and throws fireballs.
- **Goblin War Boar:** the elite that guards the floor key.
- **General Grub:** the mini-boss.
- **Valdur, the Goblin King:** the boss of floor 1-3, with telegraphed attacks (the red area on the floor shows where his hit lands). Dash through it!

The Berserker and Lich King dungeons keep their own monsters.

## Music
Each place has its own track (files in `audio/music/`, chosen in `src/maps/music.py`):

| Where | Track |
|---|---|
| Home, name and class screens, ending | Fantasy Menu Theme |
| Oakwood by day | medieval |
| Shops | RPG For Wenches, Ale, and LOOT!! |
| The wilds by day | In Search of the Philosopher's Stone |
| The vale at night | Mysterious Calm |
| Night raids, champions, caravans | Battle Theme A |
| Goblin Dungeon and goblin caves | Mysterious Calm |
| Berserker ruins and caves | Ruins of Empire |
| Lich King's barrows and caves | Snow Theme |
| Boss fights | Battle Theme A |

### Inside the rooms
- **Room layouts** themed per region:
  - Forest: groves, ruins, ponds.
  - Ancient Ruins: pillared halls, crypts, collapsed halls.
  - Underworld: lava moats with bridges, bone pits, altars.
- **Boss rooms** are always a large open arena.
- **Pots and crates** break with the sword and drop gold (sometimes a potion).
- **Reward chests** in every monster room. They unlock once the room is cleared; walk into them to open. Vaults, mini-boss arenas and the boss chamber have big ones.
- **Spike traps** from floor 2 onward, and whole gauntlets of them in trap halls. They rattle before they rise.
- **Rune gates** glow on the doors while a room is locked.
- **Lore tablets** on floors 1 and 2, and the **Veil Anchor** in the boss room after the boss falls. Walk into it (or press E at the exit) to shatter it.

## Project layout
| Path | What it is |
|---|---|
| `src/maps/dungeon_map.py` | The `Game` (home screen, overworld/dungeon switching, HUD, skills, story flow) and the dungeon renderer |
| `src/maps/music.py` | Which music track plays where |
| `src/maps/surface_world.py` | The Oakwood overworld (portals, roads, houses, lighting, minimap) |
| `src/maps/village.py` | Overworld life: NPCs, critters, smoke, day/night, treasure, story scenery |
| `src/maps/npc_art.py` | Villager sprites and dialog portraits (pixel art, drawn in code) |
| `src/maps/quests.py` | Main quest steps, side quest data and the `QuestBook` (state lives in save flags) |
| `src/maps/world_lore.py` | Wayshrines, memorial, notice board, Old Mill, quest pickups, hens, region names |
| `src/maps/dungeon_gen.py` | Random floor layouts: room graph, room roles, corridor routes |
| `src/maps/room_features.py` | Room archetypes, pots, chests, spikes, tablets, anchors, keys, seals, gates, fonts, lock gates |
| `src/maps/night_raid.py` | Night atmosphere and the playable night raids |
| `src/maps/wilds.py` | Overworld packs, monster lairs and world events |
| `src/maps/minis.py` | The six mini dungeons |
| `src/maps/save_state.py` | Gold, XP and levels, upgrades, cleared dungeons, anchors (`keepsakes`), raids won, flags and the JSON save |
| `src/maps/story.py` | All dialogue and lore text, plus the `Dialog` box |
| `src/maps/shop.py` | The shop overlay and its item catalogue |
| `src/maps/journal.py` | The journal overlay (quests and lore) |
| `src/maps/combat.py` | Player combat and the monster `Encounters` hook (owned by the monster/boss team) |
| `src/bosses/goblin_king/` | Valdur, the Goblin King (`in_game.py` puts him in the dungeon; art in `assets/bosses/goblin_king/`) |
| `src/monsters/` | Slimes, wild boar, goblin shaman / general / war boar sprites (`game_sprites.py` puts them on the game's enemies) |
| `src/skills/` | The three classes and their skills |
| `src/ui/` | Home screen, name entry, class select, settings, pause, hero HUD |

## Notes for the monster and boss team
- **The `Encounters` contract at the top of `combat.py` is unchanged.** The map only reads `state`, `locked`, `exit_open()`, `dialog_request` and `outro_request`, and `dungeon.lock_rect`.
- **Room roles:** `dungeon.room_roles[k]` says what each room is: `start`, `combat`, `guard`, `seal`, `vault`, `miniboss`, `shrine`, `trap`, `stairs`, `antechamber` or `boss`. `Encounters` reads it:
  - Monster-free rooms start as `"safe"` and never lock.
  - Enemy counts depend on the role.
  - `miniboss` rooms spawn a mini-boss (`MINIBOSSES` in `combat.py`) with a name and HP bar. The Goblin Dungeon's is General Grub (sprite); the others are still shapes.
- **Sprites on enemies:** set `enemy.skin` to a key of `src/monsters/game_sprites.py` (`SKINS`); enemies without a skin are drawn as before.
- **Skills** hit anything with `x`, `y`, `radius`, `dead` and `take_damage(n)`; `stun_t` / `slow_t` are read by `Enemy.update`, `wilds.Mob.step` and `night_raid.RaidMonster.step`.
- **Keys and seals** drop when a guard, seal or mini-boss room's `state` becomes `"cleared"`. The map handles them, so any monster code that clears rooms works.
- **`exit_open()`:** on boss floors it is true once the boss room is cleared. On floors 1-2 it is always true, because the locked stairs door holds the player back.
- **Room centres stay clear.** Every room keeps a clear area of ±5 tiles around its centre, so monsters spawned near the centre always have floor to stand on.
- **Boss rooms** are still the last room of each `X-3` floor: large octagonal arenas with only a ring of decoration at the edge.
- **Boss dialogue keys** `goblin_king`, `minotaur` and `lich` drive the story. The other keys in `story.py` still exist if you need them.
- **Player upgrades** are applied through the existing `PlayerCombat` fields `max_hp`, `dmg_bonus` and `potions`.
- **Side-quest pickups** (scrap iron, scout badges, ward shards) are placed by `room_features.py` in normal rooms, away from room centres and never in the boss room. They don't touch `Encounters`.

The project is an educational prototype and is not intended for commercial use.
