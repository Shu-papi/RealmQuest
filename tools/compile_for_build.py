"""
compile_for_build.py - compiles the few Python files the built game loads from disk (instead of shipping
their readable source): build_exe.bat runs this for hero_sprites' three teammate files.

    python tools/compile_for_build.py OUT_DIR  SRC_FILE:REL_DIR  [SRC_FILE:REL_DIR ...]

  e.g.  python tools/compile_for_build.py dist/RealmQuest  src/characters/player.py:src/characters

writes OUT_DIR/REL_DIR/player.pyc (optimisation level 2: no docstrings, no asserts).
"""
import os
import py_compile
import sys


def main(argv):
    out = argv[1]
    for pair in argv[2:]:
        src, rel = pair.rsplit(":", 1)
        dst_dir = os.path.join(out, rel)
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, os.path.splitext(os.path.basename(src))[0] + ".pyc")
        py_compile.compile(src, cfile=dst, doraise=True, optimize=2)
        print("compiled", src, "->", dst)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
