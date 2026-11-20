"""Python symbol indexer built on Tree-sitter.

Finds the classes, functions and methods in Python files and remembers where
each one starts and ends. The future ContextRetriever uses it to turn a
``Target(path, symbol)`` or ``Target(path, line)`` into an exact line range,
so it can return one function instead of a whole file.

The index lives in memory (a dict keyed by path). It stores only names and
line ranges, never file content: the retriever reads content from disk on
every request, so uncommitted edits are always visible. A file is parsed
again only when its modification time changes.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import tree_sitter_python
from tree_sitter import Language, Node, Parser

type SymbolKind = Literal["class", "function", "method"]
"""The subset of ``ItemKind`` that names a whole symbol."""

# Building the Language and Parser is not free, so we do it once per process.
# Language wraps the compiled Python grammar shipped by tree-sitter-python;
# the Parser uses it to turn source bytes into a syntax tree.
_PYTHON = Language(tree_sitter_python.language())
_PARSER = Parser(_PYTHON)

# Directories that never hold project code; skipping them keeps a full scan
# fast and stops us from indexing third-party packages in a virtualenv.
_SKIPPED_DIRS = frozenset({"__pycache__", "node_modules", "build", "dist"})


# A dataclass instead of a Pydantic model: Symbol is internal and built only by
# our own code from a trusted parse tree, so it needs no input validation.
# frozen=True makes instances immutable (safe to cache and share); slots=True
# saves memory, which matters when a repository has thousands of symbols.
@dataclass(frozen=True, slots=True)
class Symbol:
    """A class, function or method found in a Python file.

    ``name`` is qualified with the enclosing classes, e.g. ``Outer.Inner.run``.
    ``start_line`` includes the decorators, because a function without its
    ``@property`` or ``@pytest.fixture`` line reads differently. Lines are
    1-based and inclusive, like in ``ContextItem``.
    """

    name: str
    kind: SymbolKind
    path: str
    start_line: int
    end_line: int


def extract_symbols(source: bytes, path: str) -> list[Symbol]:
    """Return every class, function and method in ``source``, in file order.

    ``path`` is only copied into the results. Functions nested inside other
    functions are skipped: they are local helpers that callers cannot name.
    Files with syntax errors still yield the symbols Tree-sitter could
    recover, because the parser keeps going past errors.
    """
    tree = _PARSER.parse(source)
    symbols: list[Symbol] = []
    _collect(tree.root_node, path, scope=(), in_class=False, out=symbols)
    return symbols


def _collect(
    node: Node,
    path: str,
    scope: tuple[str, ...],
    in_class: bool,
    out: list[Symbol],
) -> None:
    """Walk the children of ``node`` and append the symbols found to ``out``.

    ``scope`` holds the names of the enclosing classes and ``in_class`` says
    whether we are directly inside a class body. Both are needed because the
    same ``function_definition`` node is a method in a class and a plain
    function elsewhere; the tree alone does not label it.
    """
    for child in node.named_children:
        # "@decorator\ndef f(): ..." parses as a decorated_definition that wraps
        # the real definition. We read the name from the inner node but keep
        # the outer one's range so the decorator lines are included.
        definition = child
        if child.type == "decorated_definition":
            inner = child.child_by_field_name("definition")
            if inner is None:
                continue
            definition = inner

        if definition.type == "function_definition":
            name = _name_of(definition)
            if name is not None:
                kind: SymbolKind = "method" if in_class else "function"
                out.append(_make_symbol(child, (*scope, name), kind, path))
            # Do not descend: nested functions are local, see extract_symbols.
        elif definition.type == "class_definition":
            name = _name_of(definition)
            if name is not None:
                out.append(_make_symbol(child, (*scope, name), "class", path))
                body = definition.child_by_field_name("body")
                if body is not None:
                    _collect(body, path, (*scope, name), in_class=True, out=out)
        else:
            # Any other statement (if, try, with, ...) may still contain
            # definitions, e.g. "if TYPE_CHECKING:". Descend without changing
            # the scope. in_class stays as it was: a def inside an "if" in a
            # class body is still a method.
            _collect(child, path, scope, in_class, out)


def _name_of(definition: Node) -> str | None:
    """Return the name of a function or class node, or None if it is missing.

    The name can be missing in a file with syntax errors, like ``def (x):``.
    """
    name_node = definition.child_by_field_name("name")
    if name_node is None or name_node.text is None:
        return None
    return name_node.text.decode("utf-8", errors="replace")


def _make_symbol(
    node: Node, qualified: tuple[str, ...], kind: SymbolKind, path: str
) -> Symbol:
    # Tree-sitter rows are 0-based; the contract uses 1-based lines.
    return Symbol(
        name=".".join(qualified),
        kind=kind,
        path=path,
        start_line=node.start_point.row + 1,
        end_line=node.end_point.row + 1,
    )


@dataclass(slots=True)
class _CacheEntry:
    """The symbols of one file and the mtime they were extracted at."""

    mtime_ns: int
    symbols: list[Symbol]


class PythonIndexer:
    """Lazily indexes the Python files under a repository root.

    Paths given to and returned by the indexer are relative to ``root`` and
    use forward slashes, like ``Target.path``. Nothing is parsed up front:
    a file is parsed the first time it is asked for, and again only after
    its modification time changes.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._cache: dict[str, _CacheEntry] = {}

    def symbols_in(self, path: str) -> list[Symbol]:
        """Return the symbols in one file, re-parsing it if it changed.

        Raises FileNotFoundError if the file does not exist; a deleted file
        is also dropped from the cache.
        """
        file = self.root / path
        try:
            # st_mtime_ns is an exact integer; the float st_mtime can lose
            # precision and miss two edits made close together.
            mtime_ns = file.stat().st_mtime_ns
        except FileNotFoundError:
            self._cache.pop(path, None)
            raise

        entry = self._cache.get(path)
        if entry is None or entry.mtime_ns != mtime_ns:
            symbols = extract_symbols(file.read_bytes(), path)
            entry = _CacheEntry(mtime_ns, symbols)
            self._cache[path] = entry
        return entry.symbols

    def find(self, path: str, name: str) -> Symbol | None:
        """Return the symbol called ``name`` in ``path``, or None.

        ``name`` is qualified for methods (``Parser.parse``). If a name is
        defined twice, e.g. in both branches of an ``if``, the first wins.
        """
        return next((s for s in self.symbols_in(path) if s.name == name), None)

    def symbol_at(self, path: str, line: int) -> Symbol | None:
        """Return the innermost symbol that contains ``line``, or None.

        For a line inside a method this is the method, not its class.
        """
        containing = [
            s for s in self.symbols_in(path) if s.start_line <= line <= s.end_line
        ]
        # The innermost symbol is the one with the smallest range.
        return min(containing, key=lambda s: s.end_line - s.start_line, default=None)

    def python_files(self) -> Iterator[str]:
        """Yield the relative path of every Python file under the root.

        Hidden directories (``.git``, ``.venv``) and build output are skipped.
        """
        # os.walk lets us prune directories in place, which Path.rglob cannot:
        # without pruning we would walk all of .venv just to ignore it.
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Sorting makes the order the same on every OS and every run.
            dirnames[:] = sorted(
                d for d in dirnames if not d.startswith(".") and d not in _SKIPPED_DIRS
            )
            for filename in sorted(filenames):
                if filename.endswith(".py"):
                    full = Path(dirpath) / filename
                    yield full.relative_to(self.root).as_posix()
