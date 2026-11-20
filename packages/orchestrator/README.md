# Orchestrator

Integration of the agents with the harness. Originally planned as our own
agent runtime (async server, task DAG, event bus); under
[ADR-0003](../../docs/adr/0003-existing-harness-and-mcp-tools.md) (Proposed)
this package becomes the integration layer instead:

- the OpenCode configuration (`opencode.jsonc`) that wires in the context
  engine and sandbox MCP servers;
- the Planner, Coder and QA agents of
  [ADR-0002](../../docs/adr/0002-agent-workflow-and-qa.md), as files in
  `.opencode/agents/`, with their models and permissions;
- the walking skeleton that tests the whole chain;
- a script that runs evaluation tasks headless and collects the numbers.

The package will be renamed once the team agrees on ADR-0003.

Owner: David Gaina

Status: scaffolded.

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
