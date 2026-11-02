# ADR-0001: Monorepo with one package per module

- Status: Proposed (waiting for team agreement)
- Date: 2026-10-27
- Author: Alexandru Achille Flueraru

## Context

Four people build four modules of the same product: the orchestrator and core
runtime, the sandboxed execution engine, the context engine, and the IDE
interface. The modules talk to each other through defined interfaces, but each
one has its own dependencies and its own owner.

We need a layout that keeps the modules separate, lets each person work
without breaking the others, and still lets us run everything together.

## Decision

We use a single repository (monorepo) with one directory per module under
`packages/`:

| Directory | Module | Owner | Language |
| --- | --- | --- | --- |
| `packages/orchestrator/` | Agent orchestration and core runtime | David | Python |
| `packages/sandbox/` | Sandboxed execution and tool calling | Radu | Python |
| `packages/context-engine/` | Deep context engine and code intelligence | Alexandru | Python |
| `packages/ui/` | IDE interface | Otniel | TypeScript |

Each Python package is self-contained: its own `pyproject.toml`, `src/`
layout and `tests/`. Shared documentation and decision records live in
`docs/`.

Rules for everyone:

- `main` is protected: changes land only through reviewed Pull Requests with
  passing CI.
- Branches are short-lived and named `feature/...`, `fix/...`, `docs/...` or
  `chore/...`.
- Commit messages follow Conventional Commits.

## Alternatives considered

- **One repository per module.** Clean separation, but changing an interface
  needs coordinated PRs in several repositories, and running the whole system
  locally means cloning and wiring four projects.
- **A single Python package for everything.** Simplest to start, but the
  modules share one dependency list and the boundaries between owners blur.

## Consequences

- One place to clone, one CI configuration, one issue tracker.
- Interfaces between modules stay visible in code review.
- CI must run only the checks of the packages a PR touches, or it slows down as
  the project grows.
- If several Python packages need to depend on each other locally, we can
  later group them in a uv workspace.
