"""
Catches typos and broken imports in EVERY file, even code that only runs
on some machines or in rare moments (like a drawing effect).

  * every import must point at a real module / real name
  * no code may use a name that was never defined or imported
    (for example a forgotten  import math)

Run from the repo root:  python -m unittest discover -s src/bosses/tests
"""
import ast
import builtins
import importlib
import os
import sys
import symtable
import unittest

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    import pygame  # noqa: F401
except ImportError:
    from pygame_stub import install
    install()

BOSSES_DIR = os.path.join(SRC_DIR, "bosses")
ALWAYS_DEFINED = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__package__", "__spec__",
    "__loader__", "__builtins__"}


def python_files():
    for root, dirs, files in os.walk(BOSSES_DIR):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(files):
            if name.endswith(".py"):
                yield os.path.join(root, name)


def module_name(path):
    relative = os.path.relpath(path, SRC_DIR)[:-3].replace(os.sep, ".")
    is_package = relative.endswith(".__init__")
    if is_package:
        relative = relative[: -len(".__init__")]
    return relative, is_package


def undefined_names(source, filename):
    """Names that are used but never defined, imported, or built in."""
    top = symtable.symtable(source, filename, "exec")
    defined = set(ALWAYS_DEFINED)
    for sym in top.get_symbols():
        if sym.is_assigned() or sym.is_imported() or sym.is_namespace():
            defined.add(sym.get_name())

    def collect(table):
        for sym in table.get_symbols():
            if sym.is_declared_global() and sym.is_assigned():
                defined.add(sym.get_name())
        for child in table.get_children():
            collect(child)

    collect(top)
    problems = []

    def visit(table):
        for sym in table.get_symbols():
            if sym.is_referenced() and sym.is_global() and sym.get_name() not in defined:
                problems.append((sym.get_name(), table.get_name(), table.get_lineno()))
        for child in table.get_children():
            visit(child)

    visit(top)
    return problems


def import_targets(path):
    """Yields (line, module_to_import, [names]) for imports that belong to bosses."""
    name, is_package = module_name(path)
    package = name if is_package else name.rpartition(".")[0]
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), path)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                if node.level > 1:
                    parts = parts[: -(node.level - 1)]
                target = ".".join(parts) + ("." + node.module if node.module else "")
            else:
                target = node.module or ""
                if target != "bosses" and not target.startswith("bosses."):
                    continue
            yield node.lineno, target, [a.name for a in node.names]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "bosses" or alias.name.startswith("bosses."):
                    yield node.lineno, alias.name, []


class TestStaticChecks(unittest.TestCase):
    def test_every_import_points_at_something_real(self):
        for path in python_files():
            for line, target, names in import_targets(path):
                where = f"{os.path.relpath(path, SRC_DIR)}:{line}"
                with self.subTest(file=where):
                    try:
                        module = importlib.import_module(target)
                    except ImportError as error:
                        self.fail(f"{where}: cannot import '{target}' ({error})")
                    for item in names:
                        if item == "*" or hasattr(module, item):
                            continue
                        try:
                            importlib.import_module(f"{target}.{item}")
                        except ImportError:
                            self.fail(f"{where}: '{target}' has nothing called '{item}'")

    def test_no_undefined_names(self):
        for path in python_files():
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            for name, scope, line in undefined_names(source, path):
                with self.subTest(file=os.path.relpath(path, SRC_DIR), name=name):
                    self.fail(f"{os.path.relpath(path, SRC_DIR)}: '{name}' is used in "
                              f"'{scope}' (line {line}) but never defined or imported")


if __name__ == "__main__":
    unittest.main()
