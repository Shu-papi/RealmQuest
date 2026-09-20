import os

# ---------- Display ----------
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
TITLE = "Dungeon Beta"

# ---------- Colors ----------
WHITE = (255, 255, 255)
BLACK = (10, 10, 14)
RED = (220, 60, 60)
DARK_RED = (120, 20, 20)
GREEN = (60, 200, 90)
DARK_GREEN = (20, 90, 40)
BLUE = (70, 130, 220)
GOLD = (230, 190, 60)
GREY = (60, 60, 70)
LIGHT_GREY = (140, 140, 150)
PURPLE = (150, 80, 200)
CYAN = (110, 220, 230)
FLOOR_COLOR = (35, 33, 40)
WALL_COLOR = (18, 17, 22)
HUB_FLOOR_COLOR = (46, 40, 34)

# ---------- Controls ----------
# WASD move, SPACE dash, LEFT CLICK attack (hold = charge), Q ability, F interact/talk
import pygame
KEY_UP = pygame.K_w
KEY_DOWN = pygame.K_s
KEY_LEFT = pygame.K_a
KEY_RIGHT = pygame.K_d
KEY_DASH = pygame.K_SPACE
KEY_ABILITY = pygame.K_q
KEY_INTERACT = pygame.K_f
MOUSE_ATTACK_BUTTON = 1  # left click

# ---------- Paths ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(BASE_DIR, "assets")
SPRITE_DIR = os.path.join(ASSET_DIR, "sprites")
SFX_DIR = os.path.join(ASSET_DIR, "sfx")
MUSIC_DIR = os.path.join(ASSET_DIR, "music")

KNIGHT_SPRITE_DIR = os.path.join(SPRITE_DIR, "characters", "knight")
SLIME_SPRITE_DIR = os.path.join(SPRITE_DIR, "monsters", "slime")
KING_SLIME_SPRITE_DIR = os.path.join(SPRITE_DIR, "bosses", "king_slime")
HUB_MAP_DIR = os.path.join(SPRITE_DIR, "map", "hub")
DUNGEON_MAP_DIR = os.path.join(SPRITE_DIR, "map", "dungeon")
UI_SPRITE_DIR = os.path.join(SPRITE_DIR, "ui")

# ---------- UI bar sizes (used for both drawing and loading matching sprites) ----------
PLAYER_HP_BAR_SIZE = (260, 24)
PLAYER_ABILITY_BAR_SIZE = (260, 16)
ENEMY_MINI_BAR_SIZE = (36, 5)
BOSS_BAR_SIZE = (int(SCREEN_WIDTH * 0.6), 26)
CHARGE_BAR_SIZE = (46, 7)
BAR_FILL_PADDING = 2  # how far the fill sits inset from the frame's edge

# ---------- Knight tuning ----------
KNIGHT_SPEED = 260
KNIGHT_MAX_HEALTH = 100
KNIGHT_SLASH_DAMAGE = 12
KNIGHT_CHARGE_MAX_TIME = 1.2          # seconds held for a full charge
KNIGHT_CHARGE_MIN_DAMAGE = 12
KNIGHT_CHARGE_MAX_DAMAGE = 45
KNIGHT_ATTACK_RANGE = 72
KNIGHT_ATTACK_COOLDOWN = 0.35

KNIGHT_DASH_SPEED = 700
KNIGHT_DASH_TIME = 0.18
KNIGHT_DASH_COOLDOWN = 0.8

KNIGHT_ABILITY_RADIUS = 120
KNIGHT_ABILITY_DAMAGE = 30
KNIGHT_ABILITY_METER_MAX = 100
KNIGHT_ABILITY_METER_PER_HIT = 20     # meter only refills by landing hits

# ---------- Slime tuning ----------
SLIME_MAX_HEALTH = 30
SLIME_SPEED = 90
SLIME_CONTACT_DAMAGE = 8
SLIME_AGGRO_RANGE = 220
SLIME_CONTACT_COOLDOWN = 0.6

# ---------- King Slime tuning ----------
KING_SLIME_MAX_HEALTH = 400
KING_SLIME_SPEED = 70
KING_SLIME_CONTACT_DAMAGE = 10
KING_SLIME_JUMP_DAMAGE = 25
KING_SLIME_JUMP_TELEGRAPH = 0.8
KING_SLIME_JUMP_COOLDOWN = 2.6
KING_SLIME_JUMP_RADIUS = 95
