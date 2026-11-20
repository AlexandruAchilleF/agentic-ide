# OrchestronAI — Agentic IDE

<p align="center">
  <strong>An intelligent, multi-agent integrated development environment built for the future of software engineering.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Status-In%20Development-blueviolet?style=for-the-badge" alt="Status: In Development" />
  <img src="https://img.shields.io/badge/Team-OrchestronAI-orange?style=for-the-badge" alt="Team: OrchestronAI" />
  <img src="https://img.shields.io/badge/Architecture-Multi--Agent-brightgreen?style=for-the-badge" alt="Architecture" />
</p>

---

## Overview

**OrchestronAI Agentic IDE** is an autonomous and collaborative coding environment where specialized AI agents operate alongside human developers. Rather than just offering autocomplete or passive chat suggestions, the IDE coordinates teams of autonomous agents that plan, write, test, debug, and refactor code directly inside your workspace.

---

## The Team — OrchestronAI

Developed with passion by **OrchestronAI**:

* **Alexandru Achille Flueraru**
* **David Gaina**
* **Otniel Balan**
* **Radu Chelu**

---

## Vision & Core Pillars

* **Multi-Agent Orchestration**: Coordinating specialized agent personas (Architect, Planner, Coder, Code Reviewer, QA/Tester) working synchronously and asynchronously.
* **Deep Context Engine**: Semantic indexing and repository-wide context graph for precise understanding of architecture and dependencies.
* **Sandboxed Autonomous Execution**: Safe tool execution environment (terminal commands, test suites, builds) with granular human-in-the-loop approvals.
* **Pair Programming Experience**: Seamless real-time collaboration between developers and AI agents with interactive diffs, previews, and feedback loops.

---

## Architecture

Proposed in [ADR-0003](docs/adr/0003-existing-harness-and-mcp-tools.md): instead of writing our own agent loop, we build on [OpenCode](https://opencode.ai), an open-source coding agent, and deliver our modules as MCP tools it calls.

```
Developer
   |
   v
OpenCode (terminal, or our UI through the SDK)
   |  agents: Planner, Coder, QA
   |
   |  MCP
   +---------------------------+
   v                           v
context-engine (MCP)        sandbox (MCP)
get_context, find_symbol    run_tests, run_command in Docker
```

| Package | Owner | Role |
| --- | --- | --- |
| [`context-engine`](packages/context-engine/) | Alexandru | Relevant code under a token budget |
| [`orchestrator`](packages/orchestrator/) | David | Integration: agents, OpenCode config, evaluation |
| [`sandbox`](packages/sandbox/) | Radu | Tests and commands in Docker |
| [`ui`](packages/ui/) | Otniel | Thin web UI over the OpenCode SDK |

All decisions and their status are listed in [docs/decisions.md](docs/decisions.md).

---

## Project Roadmap

Target: a working MVP by 2026-12-31.

- [x] Initial project setup & team alignment
- [x] Context engine contract (Pydantic models, `ContextRetriever` protocol, mock)
- [ ] Choice of harness and new architecture (ADR-0003)
- [ ] Walking skeleton: one MCP tool connected to OpenCode end to end
- [ ] Context engine: Python indexer, import graph, budgeted selection, MCP server
- [ ] Sandbox MCP server with Docker isolation
- [ ] Agent roles (Planner, Coder, QA) as OpenCode configuration
- [ ] Evaluation: agents with and without our tools
- [ ] Thin web UI

---

## License

The license will be added together with the first code release.
