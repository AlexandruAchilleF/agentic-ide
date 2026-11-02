# Context Engine

Deep context engine and code intelligence. Given a file or a function, it
returns only the code that is relevant to it, within a token budget, so agents
do not work blind.

Owner: Alexandru Achille Flueraru

## Planned components

- Tree-sitter indexer: symbols (functions, classes, calls) stored in SQLite
- Dependency graph of the workspace (imports and module relations)
- Lexical search with ripgrep
- `ContextRetriever`: the API the orchestrator calls
- LSP integration for diagnostics, definitions and references

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd packages/context-engine
uv sync                    # create .venv and install pinned dependencies
uv run pre-commit install  # once per clone: run the checks on every commit
uv run pytest              # run the tests
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy                # type check (strict)
```

CI runs the same checks on every pull request that touches this package.
