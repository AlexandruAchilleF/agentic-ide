# Sandbox

Sandboxed execution: an MCP server that runs tests and commands in a Docker
container and returns structured results (exit code, output, and the failing
tests or errors in a clear format).

Under [ADR-0003](../../docs/adr/0003-existing-harness-and-mcp-tools.md)
(Proposed) the agents' built-in shell tool is denied, so every command goes
through this server. Self-healing needs no separate loop: the harness already
shows the errors to the model, and the clearer the output, the better the fix.

Planned tools: `run_tests`, `run_command`.

Owner: Radu Chelu

Status: not started.
