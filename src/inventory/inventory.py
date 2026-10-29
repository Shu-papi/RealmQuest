"""
inventory.py - The player's weapon slots (like Soul Knight).

    from inventory import Inventory, make_weapon

    inv = Inventory("warrior")              # starts holding the warrior's starter weapon
    inv.pick_up(make_weapon("battle_axe"))  # goes into a free slot
    inv.switch_next()                       # e.g. on the Q key
    inv.current                             # the weapon in the player's hands

HOW IT WORKS
  * At least 3 slots (the game plan's minimum). One slot is "current".
  * A character can only pick up weapons of their own class.
  * If every slot is full, picking up a weapon SWAPS it with the one in
    your hands, and the old weapon is returned so the game can drop it
    on the floor (that's how Soul Knight does it).

This file has NO pygame in it on purpose: it's pure logic, so it is easy
to test. Drawing the slots on screen is the UI's job (src/ui/).
"""
from .weapons import CLASSES, STARTING_WEAPONS, make_weapon

DEFAULT_SLOTS = 3


class Inventory:
    def __init__(self, character_class, slot_count=DEFAULT_SLOTS, give_starter=True):
        if character_class not in CLASSES:
            raise ValueError(f"character_class must be one of {CLASSES}, got {character_class!r}")
        if slot_count < 1:
            raise ValueError("slot_count must be at least 1")

        self.character_class = character_class
        self.slots = [None] * slot_count    # None means an empty slot
        self.current_index = 0

        if give_starter:
            self.slots[0] = make_weapon(STARTING_WEAPONS[character_class])

    # ---------- looking at the inventory ----------

    @property
    def current(self):
        """The weapon in the player's hands (None if that slot is empty)."""
        return self.slots[self.current_index]

    def weapons(self):
        """All weapons held, skipping empty slots."""
        return [w for w in self.slots if w is not None]

    def is_full(self):
        return None not in self.slots

    def can_use(self, weapon):
        return weapon.usable_by(self.character_class)

    # ---------- changing the inventory ----------

    def pick_up(self, weapon):
        """
        Try to pick up a weapon from the floor.

        Returns (picked_up, dropped):
          picked_up  True if the weapon is now in the inventory
          dropped    the weapon the player let go of (put it on the floor),
                     or None
        """
        if not self.can_use(weapon):
            return False, None

        if not self.is_full():
            free = self.slots.index(None)
            self.slots[free] = weapon
            self.current_index = free       # switch to the new weapon right away
            return True, None

        dropped = self.current
        self.slots[self.current_index] = weapon
        return True, dropped

    def drop_current(self):
        """Throw away the weapon in your hands. Returns it (or None)."""
        dropped = self.current
        self.slots[self.current_index] = None
        return dropped

    def switch_next(self):
        """Move to the next slot that has a weapon. Returns the new current weapon."""
        return self._switch(+1)

    def switch_prev(self):
        return self._switch(-1)

    def select_slot(self, index):
        """Jump straight to a slot (e.g. number keys 1, 2, 3). Empty slots are ignored."""
        if 0 <= index < len(self.slots) and self.slots[index] is not None:
            self.current_index = index
        return self.current

    def _switch(self, step):
        count = len(self.slots)
        for i in range(1, count + 1):
            index = (self.current_index + step * i) % count
            if self.slots[index] is not None:
                self.current_index = index
                break
        return self.current

    def __repr__(self):
        names = [w.name if w else "-" for w in self.slots]
        return f"Inventory({self.character_class}, slots={names}, current={self.current_index})"
