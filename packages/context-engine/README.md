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

## Using the contract

The orchestrator depends only on the `ContextRetriever` protocol. Until the
real retriever lands, `MockRetriever` implements it with canned data.

```python
from context_engine import ContextRequest, ContextRetriever, MockRetriever, Target

retriever: ContextRetriever = MockRetriever()
request = ContextRequest(
    target=Target(path="src/app/main.py", symbol="run"),
    query="why does run() crash on empty input?",
    token_budget=4000,
)
response = await retriever.retrieve(request)
for item in response.items:
    print(item.path, item.start_line, item.end_line, item.reason)
```

| Model | Fields |
| --- | --- |
| `Target` | `path` (relative to the repo root), `symbol`, `line` |
| `ContextRequest` | `target` (optional), `query` (optional), `token_budget` (default 8000); at least one of `target` and `query` is required |
| `ContextItem` | `path`, `start_line`, `end_line`, `kind`, `content`, `score` (0..1), `reason` |
| `ContextResponse` | `items` (most relevant first), `tokens_used`, `truncated` |

A caller that does not know the relevant files yet, such as the planner at
the start of a task, sends only a query:

```python
request = ContextRequest(query="add a login endpoint")
```

The mock answers a query-only request with a placeholder item whose path is
`<mock>`.

Rules every implementation follows:

- Line numbers are 1-based and inclusive.
- `tokens_used` never exceeds `token_budget`; `truncated` is true when
  relevant code was left out to fit.
- Models are immutable and reject unknown fields, so a misspelled field in a
  JSON payload raises `pydantic.ValidationError` instead of being ignored.
- Token counts are estimates (about four characters per token).
- Content is read from the working tree, so uncommitted edits are visible.

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
