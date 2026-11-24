"""Tests for the Tree-sitter symbol indexer."""

import os
from pathlib import Path

import pytest

from context_engine.indexer import PythonIndexer, Symbol, extract_symbols

SAMPLE = b'''\
"""A module."""

import functools


def top_level():
    def local_helper():
        pass
    return local_helper


class Greeter:
    """Says hello."""

    @functools.cache
    def greet(self, name):
        return f"hello {name}"

    class Inner:
        def run(self):
            pass


if True:
    def conditional():
        pass
'''


def names(symbols: list[Symbol]) -> list[tuple[str, str]]:
    return [(s.name, s.kind) for s in symbols]


def test_finds_functions_classes_and_methods_in_file_order() -> None:
    symbols = extract_symbols(SAMPLE, "sample.py")

    assert names(symbols) == [
        ("top_level", "function"),
        ("Greeter", "class"),
        ("Greeter.greet", "method"),
        ("Greeter.Inner", "class"),
        ("Greeter.Inner.run", "method"),
        ("conditional", "function"),
    ]


def test_line_ranges_are_one_based_and_inclusive() -> None:
    symbols = {s.name: s for s in extract_symbols(SAMPLE, "sample.py")}

    assert symbols["top_level"] == Symbol(
        name="top_level", kind="function", path="sample.py", start_line=6, end_line=9
    )
    assert (symbols["Greeter"].start_line, symbols["Greeter"].end_line) == (12, 21)


def test_decorated_range_starts_at_the_decorator() -> None:
    symbols = {s.name: s for s in extract_symbols(SAMPLE, "sample.py")}

    greet = symbols["Greeter.greet"]
    assert (greet.start_line, greet.end_line) == (15, 17)


def test_nested_functions_are_not_indexed() -> None:
    symbols = extract_symbols(SAMPLE, "sample.py")

    assert all("local_helper" not in s.name for s in symbols)


def test_syntax_errors_keep_the_valid_symbols() -> None:
    source = b"def ok():\n    pass\n\ndef broken(:\n    pass\n"

    assert [s.name for s in extract_symbols(source, "bad.py")] == ["ok", "broken"]


def test_empty_file_has_no_symbols() -> None:
    assert extract_symbols(b"", "empty.py") == []


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_bytes(SAMPLE)
    (tmp_path / "notes.txt").write_text("not python")
    for skipped in (".venv", "__pycache__"):
        (tmp_path / skipped).mkdir()
        (tmp_path / skipped / "ignored.py").write_text("def x(): pass\n")
    return tmp_path


def test_find_returns_a_symbol_by_qualified_name(repo: Path) -> None:
    indexer = PythonIndexer(repo)

    found = indexer.find("pkg/mod.py", "Greeter.greet")

    assert found is not None
    assert found.kind == "method"
    assert indexer.find("pkg/mod.py", "missing") is None


def test_symbol_at_returns_the_innermost_symbol(repo: Path) -> None:
    indexer = PythonIndexer(repo)

    method = indexer.symbol_at("pkg/mod.py", 17)
    assert method is not None
    assert method.name == "Greeter.greet"

    cls = indexer.symbol_at("pkg/mod.py", 13)  # the class docstring
    assert cls is not None
    assert cls.name == "Greeter"

    assert indexer.symbol_at("pkg/mod.py", 3) is None  # the import line


def test_reindexes_a_file_when_its_mtime_changes(repo: Path) -> None:
    indexer = PythonIndexer(repo)
    file = repo / "pkg" / "mod.py"
    first = indexer.symbols_in("pkg/mod.py")

    # Unchanged file: the cached list is returned as is.
    assert indexer.symbols_in("pkg/mod.py") is first

    file.write_text("def replaced():\n    pass\n")
    # Force a different mtime; two writes within the clock's resolution
    # could otherwise share one and hide the change.
    stat = file.stat()
    os.utime(file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

    assert [s.name for s in indexer.symbols_in("pkg/mod.py")] == ["replaced"]


def test_deleted_file_raises_and_leaves_the_cache(repo: Path) -> None:
    indexer = PythonIndexer(repo)
    indexer.symbols_in("pkg/mod.py")
    (repo / "pkg" / "mod.py").unlink()

    with pytest.raises(FileNotFoundError):
        indexer.symbols_in("pkg/mod.py")


def test_python_files_skips_hidden_and_build_directories(repo: Path) -> None:
    assert list(PythonIndexer(repo).python_files()) == ["pkg/mod.py"]
