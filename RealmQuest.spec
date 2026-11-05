# PyInstaller spec for RealmQuest (a folder build: dist/RealmQuest/RealmQuest.exe + _internal/).
# Build with build_exe.bat (it also copies assets/, audio/music/, config/ next to the .exe).
#
# The game's packages live in src/ and import each other as top-level names (maps, bosses, monsters ...),
# so src/ is on the search path and those packages are collected whole. Their modules land in
# _internal/<package>/, which makes "two folders above me" (how every module finds the repo root)
# the folder of RealmQuest.exe - that is where build_exe.bat puts the data.
from PyInstaller.utils.hooks import collect_submodules

PACKAGES = ["maps", "bosses", "monsters", "skills", "ui", "audio", "inventory"]


def _game_only(name):
    return not any(part in name for part in (".tests", ".dev", "make_monsters", "monster_viewer", ".preview"))


hidden = ["balance", "app_paths", "characters.hero_sprites",
          # used by files loaded by path at run time (src/characters/player.py, kendi_sprites.py, the elf config)
          "statistics", "dataclasses", "typing", "re", "json", "math", "tomllib"]
for _pkg in PACKAGES:
    hidden += collect_submodules(_pkg, filter=_game_only)

a = Analysis(
    ["run_map.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["src", "numpy", "scipy", "PIL", "tkinter", "unittest", "pytest", "pydoc"],
    noarchive=False,
    optimize=2,                    # compiled without docstrings / asserts: less readable text in the package
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RealmQuest",
    icon="assets/ui/icon.ico",
    console=False,
    debug=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="RealmQuest")
