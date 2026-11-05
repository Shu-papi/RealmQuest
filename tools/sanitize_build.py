"""
sanitize_build.py - the last step before zipping the built game (build_exe.bat runs it).

    python tools/sanitize_build.py dist/RealmQuest

1. Cleans the text files the player can open: drops the "src/..." mentions from config headers and the
   "made_by" tool names from the sprite json files.
2. Then CHECKS the package and exits 1 (the build stops) if it still contains
   - Python source (.py), docs (.md), saves, tests, tools, build files, git files;
   - the author's name / email / repo name / local paths anywhere in the program or text files;
   - "src/", "tools/" or code file names in the config / text / json files.
"""
import json
import os
import re
import sys

MEDIA = {".png", ".wav", ".mp3", ".ogg", ".ttf", ".dll", ".pyd", ".bmp", ".ico"}
TEXT = {".toml", ".txt", ".json"}
IDENTITY = [b"Acer", b"canoyandriekoi", b"Shu-papi", b"C:\\Users", b"C:/Users", b"Downloads\\RealmQuest"]
CODE_WORDS = [b"src/", b"src\\", b"tools/", b"tools\\", b"balance.py", b"combat.py", b"dungeon_map", b".py"]
FORBIDDEN_NAMES = re.compile(r"(\.py$|\.md$|\.gitkeep$|\.gitignore$|\.spec$|\.bat$|savegame|crash\.log|smoke\.log)", re.I)
FORBIDDEN_DIRS = {"tests", "tools", ".git", "__pycache__", "dev"}


def clean(root):
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            ext = os.path.splitext(f)[1].lower()
            if ext == ".toml":
                text = open(p, encoding="utf-8", newline="").read()
                new = re.sub(r" \((?:src/[\w/.]*)\)", "", text)               # "A skeleton (src/monsters/)." -> "A skeleton."
                if new != text:
                    open(p, "w", encoding="utf-8", newline="").write(new)
            elif ext == ".json":
                try:
                    data = json.load(open(p, encoding="utf-8"))
                except ValueError:
                    continue
                if isinstance(data, dict) and "made_by" in data:
                    del data["made_by"]
                    json.dump(data, open(p, "w", encoding="utf-8"), indent=2)


def check(root):
    bad = []
    for dp, dn, fn in os.walk(root):
        rel_dir = os.path.relpath(dp, root)
        if any(part in FORBIDDEN_DIRS for part in rel_dir.split(os.sep)):
            bad.append("forbidden folder: " + rel_dir)
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root)
            ext = os.path.splitext(f)[1].lower()
            if FORBIDDEN_NAMES.search(f):
                bad.append("forbidden file: " + rel)
                continue
            if ext in MEDIA:
                continue
            data = open(p, "rb").read()
            for pat in IDENTITY:
                if pat in data:
                    bad.append("%r in %s" % (pat.decode(), rel))
            if ext in TEXT:
                for pat in CODE_WORDS:
                    if pat in data:
                        bad.append("%r in %s" % (pat.decode(), rel))
    return bad


def main(argv):
    root = argv[1]
    clean(root)
    bad = check(root)
    if bad:
        print("SANITY CHECK FAILED - the package must not contain:")
        for b in bad[:40]:
            print("  - " + b)
        return 1
    print("sanity check passed: no source, saves, docs or personal strings in " + root)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
