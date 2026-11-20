# ADR-0003: Build on OpenCode; our modules become MCP tools

- Status: Proposed (waiting for team agreement)
- Date: 2026-11-20
- Author: Alexandru Achille Flueraru
- Supersedes, if accepted: the in-process context engine and the default
  models in [ADR-0002](0002-agent-workflow-and-qa.md)

## Context

At the course lab in mid-November 2026 the professor recommended that we do
not build our own agent harness, but build on an existing one. A harness is
the loop that turns a model into an agent: it sends the request to the
model, runs the tools the model asks for, returns the results and repeats.
Our planned orchestrator (async server, task DAG, event bus) was such a
loop. Existing harnesses already do this well, and writing another one
would take most of the time we have until the end of December.

Constraints:

- **Free.** We are four students without a budget for API usage.
- **Open source**, so we can read how the loop works and explain it.
- **MCP support**, so our modules plug in as tools.
- **Configurable agents**, for the Planner, Coder and QA roles of ADR-0002.
- **Headless mode and an API**, so a script can run evaluation tasks and a
  UI can show what the agents do.

## Decision

### Harness: OpenCode

We use [OpenCode](https://opencode.ai), an MIT-licensed coding agent. It
meets every constraint above:

- MCP servers are declared in `opencode.jsonc` under `mcp.servers`.
- Agents are Markdown files in `.opencode/agents/<name>.md`: the body is
  the system prompt, and the front matter sets the model and the
  permissions (allow, ask or deny per tool). The Planner, Coder and QA roles
  become three such files.
- `opencode run "<prompt>"` runs a task without the terminal interface.
- The TypeScript SDK (`@opencode/sdk`) runs OpenCode inside a program and
  streams its events, which is what a UI needs.

We pin the OpenCode version in the setup instructions, because its
configuration format changed between major versions.

### Models

The model of each role is configuration, so it can change without code.
In order of preference:

1. **GitHub Copilot** through the GitHub Student Developer Pack, which is
   free for verified students. OpenCode connects to it with "Login with
   GitHub Copilot", without an API key.
2. **Free models listed by OpenCode.** Most are free for a limited time,
   and some keep prompts or use them for training. We only send them code
   from this public repository, never personal data.
3. **Local models through Ollama**, for offline work.

### Our modules become tools

```
Developer
   |
   v
OpenCode (terminal, or our UI through the SDK)
   |  agents: Planner, Coder, QA (.opencode/agents/)
   |
   |  MCP
   +---------------------------+
   v                           v
context-engine (MCP)        sandbox (MCP)
get_context, find_symbol    run_tests, run_command in Docker
```

- **Context engine.** A thin MCP server over the existing
  `ContextRetriever`. It complements OpenCode's own read, grep and glob
  tools and exposes only what text search does poorly: the exact lines of a
  symbol, import relations and context selected under a token budget.
- **Sandbox.** An MCP server that runs tests and commands in Docker and
  returns structured results. The agents' built-in shell tool is denied in
  their permissions, so every command goes through the sandbox.
- **Self-healing.** No separate module: the harness loop already shows tool
  errors to the model, which then fixes the code.
- **UI.** Optional second layer, built only after the whole chain works. It
  drives OpenCode through the SDK and contains no agent logic.

## Alternatives considered

- **Our own harness (the original plan).** Full control, but most of the
  time would go into a loop that existing tools already provide.
- **Claude Agent SDK.** A good library, but usage needs a paid API key or a
  paid Claude plan.
- **Gemini CLI.** Open source with MCP and a headless mode, but its free tier
  changed in 2026 and the public reports about what is still free conflict.
- **GitHub Copilot CLI alone.** Free for students, but closed source and
  harder to drive from our own UI.
- **No harness: a script that calls the model once.** Not an agent: no tool
  loop and no reaction to failing tests.

## Consequences

- The orchestrator package changes the most: its work moves to integration
  (OpenCode configuration, agent roles, MCP wiring) and to the evaluation
  runs. Its directory will be renamed.
- The context engine's core does not change; only its delivery does. The
  in-process call of ADR-0002 is replaced by MCP.
- The default models of ADR-0002 (Opus and Sonnet) are replaced by the
  models available for free. The three roles and the user-triggered QA stay.
- We depend on an external tool. Its updates can break our configuration,
  so we pin its version. Free model offers can end, so every role must work
  with at least two of the three model sources.
- First step: a walking skeleton. One MCP tool that returns a fixed answer,
  connected to OpenCode, used by one agent, so the whole chain is tested
  before the real logic is ready.
- The project's claim must be measured: we compare the agents with and
  without our tools on a few real tasks (tokens, tool calls, task solved).
