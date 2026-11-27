# Sandbox

Sandboxed execution: an MCP server that runs tests and commands in a container
(Podman or Docker) and returns structured results (exit code, output, and the
failing tests or errors in a clear format).

Under [ADR-0003](../../docs/adr/0003-existing-harness-and-mcp-tools.md)
(Proposed) the agents' built-in shell tool is denied, so every command goes
through this server. Self-healing needs no separate loop: the harness already
shows the errors to the model, and the clearer the output, the better the fix.

## Tools

- `run_command(command, timeout_s=60)`: runs a shell command in `/work` (the
  mounted workspace) and returns `exit_code`, `stdout`, `stderr`, `duration_s`,
  `timed_out` and `truncated`.
- `run_tests(path="", timeout_s=120)`: runs pytest in the container and returns
  passed/failed/errors/skipped totals and, for each failure, `nodeid`, `file`,
  `line` and a short `message`.

Both return a readable summary first, then the full result as JSON.

## Running

```sh
uv sync --directory packages/sandbox
uv run --directory packages/sandbox python -m sandbox.server   # stdio MCP server
```

The image has to exist locally first (see the Dockerfile in this package).

## Environment variables

| Variable            | Default                      | Meaning                                    |
| ------------------- | ---------------------------- | ------------------------------------------ |
| `SANDBOX_WORKSPACE` | the server's working dir     | Host directory mounted at `/work`.         |
| `SANDBOX_IMAGE`     | `agentic-ide-sandbox:latest` | Image the commands run in.                 |
| `SANDBOX_RUNTIME`   | auto: `podman`, then `docker` | Container runtime; auto-detect uses `<runtime> info`. |

pytest writes its JUnit report to `<workspace>/.sandbox/report.xml`.

## Checks

```sh
cd packages/sandbox
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```

Owner: Radu Chelu

Status: in progress. The container start (`build_run_args` in
`src/sandbox/container.py`) and the Dockerfile are still to be written.
