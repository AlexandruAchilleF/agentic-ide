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
| D7 | Use an existing agent harness; our modules become MCP tools | Proposed | This file; ADR-0003 to follow |
| D8 | Which harness we use | Open | This file |
| D9 | Do we build our own interface on top of the harness | Open | This file |

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
- Text search with ripgrep for requests that only have a `query`.
- An import graph between the project's own files (no external libraries,
  no call graph).
- Fixed ranking weights (target, then imports, then text matches) and greedy
  selection under the token budget.

Left out until the MVP works end to end: LSP diagnostics, SQLite storage,
real incremental re-indexing, a call graph and semantic search. SQLite can
later replace the in-memory index behind the same interface.

Why: the end-of-December deadline. We cut features, not tests or review.

## D7. Use an existing agent harness; our modules become MCP tools

Status: Proposed, waiting for team agreement. The full ADR (ADR-0003) will
follow once the team agrees.

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
  delivery does.
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

## Open questions

- D8: which harness we use. It must support MCP servers and, if D9 is
  accepted, a headless mode the backend can drive.
- D9: do we build our own UI, or use the harness's interface for the MVP.
- How the work of the orchestrator and sandbox owners is redistributed
  after D7.
- The real token budget of each agent role (from ADR-0002).
