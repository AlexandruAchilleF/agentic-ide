# ADR-0002: Agent workflow and user-triggered QA

- Status: Proposed (waiting for team agreement)
- Date: 2026-11-03
- Author: David Gaina

## Context

The orchestrator coordinates the agents that turn a user's request into code.
We need to decide which agents exist, how work is handed from one to the
next, and how the result is checked, before the orchestrator code is written.

Two forces pull against each other:

- **Verification.** LLM agents make mistakes, and in a multi-agent pipeline
  small mistakes add up from step to step.
- **Simplicity and cost.** Every extra review round costs tokens and time, and
  every extra path in the workflow is more code to build, test and explain.

## Decision

### Agents

We use three agents, each with a different job and a model chosen for that
job:

| Agent | Job | Model requirement | Default |
| --- | --- | --- | --- |
| Planner | Reasons about the architecture, edge cases and the simplest solution that holds up long-term | Strongest reasoning | Opus 5.5, high effort |
| Coder | Implements the plan quickly and follows instructions closely | Fast, good at following instructions | Sonnet 5.5, medium or high effort |
| QA | Reviews the code, finds bugs and uncovered cases, runs tests | Good reasoning at moderate cost | Opus 5.5 or Sonnet 5.5, medium effort |

The model and effort of each agent are configuration, not code, so they can
change when better or cheaper models come out.

### Workflow

```
Task -> Planner -> Coder -> commit
                              |
                    user presses "QA"
                              |
                              v
                       QA (full review) -> findings
                              |
               +--------------+---------------+
               |                              |
          small bugs                 bugs that touch the
               |                       architecture
               v                              v
             Coder                  Planner -> Coder
               |                              |
               +--------------+---------------+
                              v
                 QA (second pass, serious bugs only)
```

1. The Planner turns the task into a plan; the Coder implements it and the
   result is committed.
2. **QA runs only when the user presses the QA button.** Our target user is an
   experienced developer who reviews AI changes and decides when a deeper
   review is needed.
3. QA's first pass is a full review. Each finding is labelled as either a
   small, local bug or one that touches the architecture.
4. Small bugs go straight to the Coder. Bugs that touch the architecture go
   to the Planner first, which decides on a smaller architecture change or a
   bug fix and hands it to the Coder.
5. QA's second pass checks only serious bugs, to avoid an over-engineered,
   endless review.

Because QA is started by the user, the workflow never loops on its own: the
user is the termination condition.

### Context engine

The orchestrator calls the context engine **in-process** (it imports
`context_engine`): one process is easier to debug and avoids running a second
server with network errors and timeouts. The contract models serialize to
JSON, so moving the engine behind HTTP later only adds a server layer.

The Planner starts a task with only the task text, so its first request
carries a `query` and no `target`; the engine finds the relevant files
itself (#5). The engine reads content from the working tree, so QA sees the
Coder's uncommitted edits.

Each agent gets its own token budget, set by the orchestrator from that
agent's model and job: the Planner needs broad context, the Coder a narrow
slice. The engine's default budget is only a fallback.

## Alternatives considered

- **QA always runs.** Every change is reviewed, but simple changes pay the
  full cost of a review, and the workflow needs automatic stop rules.
- **The Planner decides whether QA runs, or how much effort it gets.**
  Rejected: the agent whose work is being checked would control the check. A
  Planner that misjudges a change as simple would also give that mistake the
  weakest review.
- **Fixed round limits** (two QA rounds for important changes, one for simple
  ones). Not needed while the user triggers QA; we can bring it back if QA
  becomes automatic.
- **A codebase-memory MCP server for indexing.** Not in the MVP: it would
  replace the context engine's indexer, search and graph, and it adds a
  second server, against the in-process decision above. It can be added
  later as an optional source behind the same `ContextRetriever` protocol.

## Consequences

- The workflow is simple: one path from task to commit, and no automatic
  loop that can run forever.
- **Unreviewed code can reach the repository** when the user does not press
  QA. We accept this because our target user is experienced and it keeps the
  system cheap and simple.
- QA findings need a structured format (at least a severity and a
  local/architecture label) so the orchestrator can route them and the second
  pass can filter them.
- QA can mislabel an architecture problem as a small bug, so the Coder only
  fixes the symptom.

## Planned extension

An **auto-QA setting** that the user controls: when it is off, the user
triggers QA with the button; when it is on, QA runs automatically after every
change. The user, not an agent, owns this switch, so an agent can never turn
off the review of its own work.

## Open questions

- After QA reports findings, does the routing start automatically, or does
  the user choose what happens?
- Do tests run automatically on every change, even without the QA button?
  Running tests is the sandbox's job. Proposal from the context engine
  review: tests run in the sandbox before the commit, so a commit happens
  only when they pass. To be confirmed with the sandbox owner.
- The real token budget of each agent, from each model's context window.
  The context engine needs these numbers for the retriever.
- Does QA's second pass only check that the earlier serious bugs were fixed,
  or does it also look for new serious bugs (regressions) the fix introduced?
- Can the Coder send a finding back to the Planner when the fix turns out not
  to be local?
- Which fields does a QA finding have?
