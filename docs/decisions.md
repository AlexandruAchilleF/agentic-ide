# Decision log

A short index of the project's decisions: what we decided, its status, and
where the full reasoning lives. Large decisions get an ADR in `docs/adr/`;
this file only summarizes them and records the smaller ones that do not need
a full ADR.

Statuses:

- **Accepted**: agreed by the team and in effect.
- **Proposed**: written down, waiting for team agreement.
- **Open**: not decided yet.
- **Superseded**: replaced by a later decision (linked).

## Summary

| ID | Decision | Status | Source |
| --- | --- | --- | --- |
| D1 | Monorepo with one package per module | Proposed | [ADR-0001](adr/0001-monorepo-layout.md) |
| D2 | Planner, Coder and QA agents; QA triggered by the user | Proposed | [ADR-0002](adr/0002-agent-workflow-and-qa.md) |
| D3 | Orchestrator imports the context engine in-process | Superseded by D7 if D7 is accepted | ADR-0002, PR #3 |
| D4 | Context engine contract: Pydantic models and a `ContextRetriever` protocol | Accepted | PR #3, PR #5 |
| D5 | A context request needs a `target`, a `query`, or both | Accepted | PR #5 |
| D6 | Reduced MVP scope for the context engine | Accepted | This file |
| D7 | Use an existing agent harness; our modules become MCP tools | Proposed | This file, [ADR-0003](adr/0003-existing-harness-and-mcp-tools.md) |
| D8 | OpenCode as the harness, with free model access | Proposed | This file, ADR-0003 |
| D9 | A thin UI of our own, built after the walking skeleton | Proposed | This file, ADR-0003 |
| D10 | New split of the work between the four members | Proposed | This file |

## D4. Context engine contract

The engine is called with a `ContextRequest(target, query, token_budget)`
and returns a `ContextResponse(items, tokens_used, truncated)`. Each
`ContextItem` carries a path, a 1-based inclusive line range, the content,
a score and a human-readable `reason`. The engine's default budget (8000
tokens) is only a fallback; the caller sets the budget per agent.

Why: a typed contract lets the context engine and its callers be built in
parallel against a mock (`MockRetriever`) before the real engine exists.

## D6. Reduced MVP scope for the context engine

In the MVP the context engine supports:

- Python only, indexed with Tree-sitter (functions, classes, methods).
- An in-memory index. File content is read from disk on every request, and a
  file is re-indexed when its modification time changes, so uncommitted
  edits are always visible.
- Text search with ripgrep, used only inside `get_context` as a source of
  candidates for requests that only have a `query`. It is not exposed as a
  separate tool, because agent harnesses already ship a ripgrep-based search
  tool (see D7).
- An import graph between the project's own files (no external libraries,
  no call graph).
- Fixed ranking weights (target, then imports, then text matches) and greedy
  selection under the token budget.

Left out until the MVP works end to end: LSP diagnostics, SQLite storage,
real incremental re-indexing, a call graph and semantic search. SQLite can
later replace the in-memory index behind the same interface.

Why: the end-of-December deadline. We cut features, not tests or review.

Revised on 2026-11-20, after D7: an agent in an existing harness can
already search the code itself with its built-in tools (read, grep, glob).
The engine is only worth having if it beats that, so we measure it early
instead of only at the final demo:

- Right after the indexer is merged, a rough evaluation on 3 to 5 tasks
  from a real repository: the agent without our tools versus the agent
  with them.
- Measured: tokens used, number of tool calls, and whether the task was
  solved.
- The text search phase is reduced to the internal use above; the time
  saved goes to the import graph and the evaluation.

## D7. Use an existing agent harness; our modules become MCP tools

Status: Proposed, waiting for team agreement. The full reasoning, together
with D8 and D9, is in
[ADR-0003](adr/0003-existing-harness-and-mcp-tools.md), also Proposed.

### Context

At the course lab in mid-November 2026, the professor recommended that we
do not build our own agent harness and instead build on top of an existing
one.

A harness is the loop that turns a model into an agent: it sends the
request to the model, runs the tools the model asks for, returns the
results and repeats until the task is done. It also handles permissions,
the conversation context and retries. Our planned orchestrator (async
server, task DAG, event bus) was a harness of our own. Existing harnesses
already do this well, so writing another one would cost most of our time
and still produce a weaker result.

### Decision

We do not write the agent loop. We write the tools the loop calls, exposed
through MCP (Model Context Protocol, the standard way to give an agent
external tools).

```
Developer
   |
   v
Existing harness (one, chosen by the team)
   |  + instruction file, for example:
   |    "call get_context before reading files;
   |     call run_tests after editing"
   |
   |  MCP
   +--------------------------+
   v                          v
context-engine (MCP)       sandbox (MCP)
get_context, find_symbol   run_tests, run_command in Docker
```

- **Context engine**: a thin MCP server over the existing `ContextRetriever`.
  The indexer, search, graph and selection logic do not change; only the
  delivery does. It complements the harness's built-in file tools instead
  of replacing them: it exposes only what text search does poorly (the
  exact lines of a symbol, the symbol at a given line, import relations,
  and context selected under a token budget).
- **Sandbox**: an MCP server that runs commands and tests in Docker and
  returns their output, errors and diagnostics in a clear format.
- **Self-healing**: no separate module. When a tool returns an error, the
  model sees it and fixes the code; this is what the harness loop already
  does. Our part is clear error output and an instruction in the prompt.
- **Agent roles** (Planner, Coder, QA from ADR-0002): defined as
  configuration of the harness (prompts, subagents, model per role) instead
  of orchestrator code.

### Optional second layer: our own interface

If we also want our own interface (D9), it sits on top without changing the
tools:

```
UI --WebSocket--> thin backend --> harness run headless
                                      |  MCP
                                      v
                             the same MCP servers
```

The backend only starts the harness and forwards its events to the UI; it
contains no agent logic. We build this layer only after the minimal version
works end to end.

### Alternatives considered

- **Our own harness (the original plan).** Full control, but most of the
  team's time would go into a loop that existing tools already provide.
- **No harness at all: a script that calls the model API once.** Simplest,
  but it is not an agent: no tool loop, no way to react to test failures.

### Consequences

- D3 (in-process import) is superseded: the harness reaches the context
  engine through MCP, in a separate process.
- The context engine's core is unaffected, because callers depend on the
  `ContextRetriever` protocol and not on how it is delivered.
- The orchestrator package shrinks the most. Its owner's work moves to
  integration (harness configuration, MCP wiring, agent roles) and to the
  evaluation that compares the harness with and without our tools.
- We depend on an external tool: its updates can change behavior, and some
  harnesses need a paid account.
- First step: a "walking skeleton", one MCP tool that returns a fixed
  answer, connected to the chosen harness, to test the whole chain before
  the real logic is ready.

## D8. OpenCode as the harness, with free model access

Status: Proposed. Full reasoning in
[ADR-0003](adr/0003-existing-harness-and-mcp-tools.md).

Requirements: free for a student team, open source (so we can read how
the loop works), MCP support, configurable agents (for the roles in
ADR-0002), a headless mode, and an API a UI can drive.

Proposal: [OpenCode](https://opencode.ai) (MIT license). Models, in order
of preference:

1. GitHub Copilot through the free GitHub Student Developer Pack, connected
   with "Login with GitHub Copilot" in OpenCode.
2. The free models listed by OpenCode. Some of them keep prompts or use
   them for training, so we send them only code from this public repository.
3. Local models through Ollama, for offline work. Weaker, and slow on a
   laptop.

Rejected: Claude Agent SDK (needs a paid API key or a paid plan), Gemini
CLI (its free tier changed in 2026 and the reports conflict), our own
harness (D7).

## D9. A thin UI of our own, built after the walking skeleton

Status: Proposed.

For the MVP the team works in the OpenCode terminal interface. Once the
whole chain works, the UI owner builds a small web UI on the OpenCode
TypeScript SDK: a prompt box, the timeline of agent events, the diff of the
changes, the QA button from ADR-0002 and a panel that shows what context
the context engine chose and why. The UI contains no agent logic.

## D10. New split of the work

Status: Proposed, to be confirmed by each member for their own part.

| Member | Package | MVP work |
| --- | --- | --- |
| Alexandru | `context-engine` | Indexer, import graph and budgeted selection behind an MCP server (`get_context`, `find_symbol`); the evaluation of the engine (D6). |
| David | `orchestrator` (to be renamed) | Integration: OpenCode config in `.opencode/` (Planner, Coder and QA agents from ADR-0002, permissions, MCP servers); the walking skeleton; a script that runs evaluation tasks headless and collects the numbers. |
| Radu | `sandbox` | MCP server that runs tests and commands in Docker and returns structured results. The agents' own shell tool is denied, so every command goes through the sandbox. |
| Otniel | `ui` | The thin UI from D9, on the OpenCode SDK. Until the skeleton works: a static mock of the screens. |

Self-healing (from the original sandbox scope) needs no separate code: the
harness loop already shows test errors to the model. Its quality depends on
how clear the sandbox's error output is.

## Open questions

- Does the GitHub Copilot student plan work inside OpenCode for all four
  members, and with which models? To check in the walking skeleton.
- Which free fallback model is good enough for the Coder role?
- Does `opencode run` report token usage per run? The evaluation needs it.
- The new name of `packages/orchestrator` (for example `integration`).
- The real token budget of each agent role (from ADR-0002).
