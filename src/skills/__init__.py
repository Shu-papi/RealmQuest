"""RealmQuest hero classes and skills.

classes.py  balance numbers for Warrior / Mage / Archer (HP, speed, resource bars)
skills.py   two skills + a special per class, their cooldowns, costs and effects
"""
from .classes import CLASS_ORDER, CLASS_STATS, DASH_STAMINA, BAR_COLORS, stats
from .skills import (SLOTS, CLASS_SKILLS, SkillDef, Pools, SkillCaster, SkillFX, skills_for)
