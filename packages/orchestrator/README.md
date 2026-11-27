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

Status: walking skeleton. The default agent is the `planner`: it reads the
code, writes a plan and hands it to the `coder` subagent. The Planner cannot
edit files or run shell commands. Both agents can call a stub `find_symbol`
MCP tool (`src/orchestrator/stub_mcp.py`) that returns a fixed answer.

## Walking skeleton

Requires OpenCode 1.19.6 (`npm i -g opencode-ai@1.19.6`) and uv. From the repo
root:

```bash
opencode mcp list   # context-engine should be "connected"
opencode run -m opencode/deepseek-v4.1-flash-free "Where is the Python class Target defined?"
opencode stats      # token usage and tool calls, for the evaluation
```

The free `opencode/*-free` models may keep prompts, so only use them on this
public repository. GitHub Copilot (`opencode providers login`) is the
preferred model source (ADR-0003).

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
