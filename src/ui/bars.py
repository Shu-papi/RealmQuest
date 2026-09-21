"""
All HP/ability/charge bars are drawn from two sprites each: a "frame"
(background + border, always fully visible) and a "fill" (the colored
bar that drains). The fill is cropped horizontally to match the current
percentage instead of being stretched, so any fill art you drop in keeps
its own detail/gradient instead of getting squashed.

To reskin any bar: just overwrite the matching PNG in
assets/sprites/ui/ — no code changes needed. Sizes are defined once in
src/settings.py (PLAYER_HP_BAR_SIZE, ENEMY_MINI_BAR_SIZE, etc.) so your
frame/fill art should match those pixel dimensions (or be any size —
it'll be scaled to fit).
"""
import os
import pygame
from src import settings as s
from src.utils import load_image


def _load_bar_sprites(filename_prefix, size, frame_color, fill_color):
    frame = load_image(
        os.path.join(s.UI_SPRITE_DIR, f"{filename_prefix}_frame.png"), size,
        fallback_color=frame_color)
    fill = load_image(
        os.path.join(s.UI_SPRITE_DIR, f"{filename_prefix}_fill.png"), size,
        fallback_color=fill_color)
    return frame, fill


# Loaded once and cached (load_image itself caches by path+size).
PLAYER_HP_FRAME, PLAYER_HP_FILL = _load_bar_sprites(
    "player_hp", s.PLAYER_HP_BAR_SIZE, (30, 15, 15), s.RED)
ABILITY_FRAME, ABILITY_FILL = _load_bar_sprites(
    "ability", s.PLAYER_ABILITY_BAR_SIZE, (15, 20, 35), s.BLUE)
ABILITY_FILL_READY = load_image(
    os.path.join(s.UI_SPRITE_DIR, "ability_fill_ready.png"), s.PLAYER_ABILITY_BAR_SIZE,
    fallback_color=s.CYAN)
ENEMY_MINI_FRAME, ENEMY_MINI_FILL = _load_bar_sprites(
    "enemy_mini_hp", s.ENEMY_MINI_BAR_SIZE, (0, 0, 0), s.GREEN)
BOSS_FRAME, BOSS_FILL = _load_bar_sprites(
    "boss_hp", s.BOSS_BAR_SIZE, (30, 15, 15), s.RED)
CHARGE_FRAME, CHARGE_FILL = _load_bar_sprites(
    "charge", s.CHARGE_BAR_SIZE, (0, 0, 0), s.GOLD)


def _draw_cropped_bar(surface, x, y, size, pct, frame_img, fill_img, padding=0):
    """Draws frame_img at (x, y), then fill_img cropped to `pct` width on top,
    inset by `padding` px so it sits inside the frame's border."""
    width, height = size
    surface.blit(frame_img, (x, y))

    pct = max(0.0, min(1.0, pct))
    inner_w = max(0, width - padding * 2)
    inner_h = max(0, height - padding * 2)
    fill_w = max(0, int(inner_w * pct))
    if fill_w <= 0 or inner_h <= 0:
        return

    fill_scaled = pygame.transform.smoothscale(fill_img, (inner_w, inner_h))
    fill_crop = fill_scaled.subsurface(pygame.Rect(0, 0, fill_w, inner_h))
    surface.blit(fill_crop, (x + padding, y + padding))


def draw_mini_healthbar(surface, world_x, world_y, current, maximum, width=None, height=None):
    """Small, stylish healthbar floating above a regular enemy's head."""
    if current <= 0:
        return
    size = s.ENEMY_MINI_BAR_SIZE if width is None else (width, height)
    x = world_x - size[0] // 2
    y = world_y
    pct = current / maximum
    _draw_cropped_bar(surface, x, y, size, pct, ENEMY_MINI_FRAME, ENEMY_MINI_FILL,
                       padding=1)


def draw_boss_healthbar(surface, name, current, maximum):
    """Full-width bar at the bottom of the screen, reserved for bosses."""
    size = s.BOSS_BAR_SIZE
    x = (s.SCREEN_WIDTH - size[0]) // 2
    y = s.SCREEN_HEIGHT - 60
    pct = current / maximum

    font = pygame.font.Font(None, 26)
    label = font.render(name, True, s.WHITE)
    surface.blit(label, (x, y - 26))

    _draw_cropped_bar(surface, x, y, size, pct, BOSS_FRAME, BOSS_FILL,
                       padding=s.BAR_FILL_PADDING)


def draw_player_hud(surface, player):
    x, y = 24, 24
    hp_pct = player.health / player.max_health
    _draw_cropped_bar(surface, x, y, s.PLAYER_HP_BAR_SIZE, hp_pct,
                       PLAYER_HP_FRAME, PLAYER_HP_FILL, padding=s.BAR_FILL_PADDING)

    font = pygame.font.Font(None, 22)
    hp_text = font.render(f"{int(player.health)}/{player.max_health}", True, s.WHITE)
    bw, bh = s.PLAYER_HP_BAR_SIZE
    surface.blit(hp_text, (x + bw // 2 - hp_text.get_width() // 2, y + 2))

    # Ability meter (below health bar) - Q ability
    ay = y + bh + 10
    apct = player.ability_meter / s.KNIGHT_ABILITY_METER_MAX
    fill_sprite = ABILITY_FILL_READY if apct >= 1.0 else ABILITY_FILL
    _draw_cropped_bar(surface, x, ay, s.PLAYER_ABILITY_BAR_SIZE, apct,
                       ABILITY_FRAME, fill_sprite, padding=s.BAR_FILL_PADDING)

    aw, ah = s.PLAYER_ABILITY_BAR_SIZE
    label = font.render("Q - Ability" + ("  READY" if apct >= 1.0 else ""), True, s.WHITE)
    surface.blit(label, (x, ay + ah + 4))


def draw_charge_bar(surface, world_x, world_y, charge_pct):
    """Charge meter that pops up above the player's head while charging a slash."""
    size = s.CHARGE_BAR_SIZE
    x = world_x - size[0] // 2
    y = world_y - 46
    _draw_cropped_bar(surface, x, y, size, charge_pct, CHARGE_FRAME, CHARGE_FILL, padding=1)
