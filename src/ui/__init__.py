"""
RealmQuest UI package (HUD, menus, settings, mini-map).

    from ui import HUD

    hud = HUD()
    hud.update(dt, player)      # every frame
    hud.draw(screen)

    from ui import MainMenu
    menu = MainMenu()
    action = menu.handle_event(event)   # "new_game", "settings", "exit" or None
    menu.draw(screen)

    from ui import Settings, SettingsScreen
    settings = Settings.load()           # volumes, fullscreen, key bindings (saved to disk)
    settings.key_for("attack")           # other teams read keys and volumes from here

    from ui import WeaponBar
    bar = WeaponBar(inventory, settings)  # the 3 weapon slots in the bottom-right corner

    from ui import ClassSelect, InventoryScreen
    picker = ClassSelect()                # after New Game: choose Warrior / Mage / Archer
    window = InventoryScreen(inventory, player)   # during a run, e.g. on the I key

Try them on their own:
    python src/ui/dev/game_preview.py     <- the whole flow: menu, class select, run, inventory
    python src/ui/dev/hud_preview.py
    python src/ui/dev/menu_preview.py
    python src/ui/dev/weapon_preview.py
Run the tests:
    python -m unittest discover -s src/ui/tests
"""
from .hud import HUD, StatBar
from .menu import MainMenu, NEW_GAME, SETTINGS, EXIT
from .settings_data import Settings
from .settings_screen import SettingsScreen
from .weapon_bar import WeaponBar
from .class_select import ClassSelect
from .inventory_screen import InventoryScreen
