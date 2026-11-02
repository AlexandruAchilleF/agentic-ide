# Orchestrator

Agent orchestration and core runtime: the central asynchronous server, the task
DAG and the event bus that connects agents and the other modules.

Owner: David Gaina

Status: scaffolded. See [ADR-0001](../../docs/adr/0001-monorepo-layout.md) for
the repository layout.

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd packages/orchestrator
uv sync                    # create .venv and install pinned dependencies
uv run pre-commit install  # once per clone: run the checks on every commit
uv run pytest              # run the tests
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy                # type check (strict)
```

CI runs the same checks on every pull request that touches this package.
