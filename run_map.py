"""Run RealmQuest.

    python run_map.py                              # the game
    python run_map.py --tester                     # TESTER MODE: everything unlocked, F1 menu (see src/maps/tester.py)
    python run_map.py --tester --floor 3-3 --boss  # straight into the Lich King's room
    python run_map.py --smoke 600                  # self-test: a fresh hero (temp save) plays 600 frames in the
                                                   # village and a dungeon, then quits (exit code 0 = fine)

The built game (RealmQuest.exe, see build_exe.bat) runs this same file. There, saves and the crash log go to
%APPDATA%\\RealmQuest, and tester mode is off unless REALMQUEST_DEV=1 is set.
"""
import argparse
import os
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:                 # the game's packages (maps, bosses, monsters, ...) live in src/
    sys.path.insert(0, str(SRC))

import app_paths  # noqa: E402


def _dpi_aware():
    """Windows: draw at the real pixel size (no blurry stretching at 125% / 150% display scaling)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)          # per-monitor
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _crash_report(exc_type, exc, tb):
    """Write the error to crash.log (next to the save) and tell the player where it is."""
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    path = app_paths.user_dir() / "crash.log"
    try:
        path.write_text(text, encoding="utf-8")
    except OSError:
        path = None
    if sys.stderr:
        sys.stderr.write(text)
    if app_paths.frozen() and sys.platform == "win32":
        try:
            import ctypes
            msg = "RealmQuest stopped because of an error.\n\n%s: %s\n\nDetails were saved to:\n%s" % (
                exc_type.__name__, exc, path or "(could not write the log)")
            ctypes.windll.user32.MessageBoxW(None, msg, "RealmQuest", 0x10)
        except Exception:
            pass


def _set_icon():
    try:
        import pygame
        icon = app_paths.game_dir() / "assets" / "ui" / "icon.png"
        if icon.is_file():
            pygame.display.set_icon(pygame.image.load(str(icon)))
    except Exception:
        pass


def _smoke(game, frames, hero_class="warrior"):
    """Drive the real game loop: village for the first half, a dungeon floor for the second, then quit."""
    import pygame
    game.begin_game(True, "Smoke", hero_class)
    game.dialog = None
    game.is_dungeon_unlocked = lambda dungeon_id: True
    count = {"n": 0}
    check = game.check_config

    def tick(now=None):
        count["n"] += 1
        n = count["n"]
        if game.dialog is not None:
            game.dialog = None
        if n == frames // 2:
            game.change_floor("1-1")
            game.fade, game.fade_dir = 0.0, 0
        if n == frames:
            line = "[smoke] ok: %d frames, mode=%s floor=%s hp=%s\n" % (n, game.mode, game.floor_name, game.pc.hp)
            try:
                (app_paths.user_dir() / "smoke.log").write_text(line, encoding="utf-8")
            except OSError:
                pass
            if sys.stdout:
                sys.stdout.write(line)
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        return check(now)

    game.check_config = tick


def main(argv=None):
    parser = argparse.ArgumentParser(description="RealmQuest")
    parser.add_argument("--tester", action="store_true",
                        help="tester mode: a maxed hero, every portal open, F1 menu; uses savegame_tester.json")
    parser.add_argument("--class", dest="hero_class", choices=("warrior", "mage", "archer"), default="warrior",
                        help="tester mode: the hero's class (default warrior)")
    parser.add_argument("--floor", help="tester mode: start on this floor, e.g. 1-1, 2-3, 3-3, 11-1")
    parser.add_argument("--boss", action="store_true", help="tester mode: with --floor, walk into the last room")
    parser.add_argument("--continue", dest="keep_save", action="store_true",
                        help="tester mode: keep the previous tester save instead of a fresh maxed hero")
    parser.add_argument("--smoke", type=int, metavar="FRAMES", help="self-test: play this many frames and quit")
    args = parser.parse_args(argv)

    if app_paths.frozen() and not os.environ.get("REALMQUEST_DEV"):
        args.tester = False                  # the shipped game has no cheat menu
    if args.smoke:                           # never touch a real save
        os.environ["REALMQUEST_SAVE"] = str(Path(tempfile.mkdtemp()) / "smoke_save.json")
    elif args.tester:                        # before the game loads: the tester never touches the real savegame.json
        os.environ.setdefault("REALMQUEST_SAVE", str(app_paths.user_dir() / "savegame_tester.json"))

    _dpi_aware()
    from maps.dungeon_map import Game

    game = Game(tester=args.tester)
    _set_icon()
    if args.smoke:
        _smoke(game, args.smoke, args.hero_class)
    elif args.tester:
        game.tester.start(args.hero_class, floor=args.floor, boss=args.boss, keep_save=args.keep_save)
    return game.run()


if __name__ == "__main__":
    sys.excepthook = _crash_report
    raise SystemExit(main())
