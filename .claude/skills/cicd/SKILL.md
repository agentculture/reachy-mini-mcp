---
name: cicd
type: command
description: >
  reachy-mini-mcp's CI/CD lane, layered on `devex pr`. Delegates lint / open /
  read / reply / delta to devex; adds two extensions — `status`
  (SonarCloud quality gate + hotspots + unresolved-thread tally) and
  `await` (read --wait + status with non-zero exit on Sonar ERROR or
  unresolved threads). Use when: creating PRs in reachy-mini-mcp, handling
  review feedback, polling CI status, or the user says "create PR",
  "review comments", "address feedback", "resolve threads". Renamed
  from `pr-review` in steward 0.7.0; rebased on devex in 0.12.0.
---

# CI/CD — reachy-mini-mcp edition

`devex pr` (in `agentculture/devex`) is the upstream for the
five core PR-lifecycle verbs — `lint`, `open`, `read`, `reply`,
`delta`. Steward used to vendor parallel scripts for each; in 0.12.0
those vendored copies were dropped in favor of delegating to `devex`.
What's left in this skill is **the steward-specific gating layer**:

- `status` — SonarCloud quality gate, OPEN issues, hotspots, deploy
  preview URL, unresolved-inline-thread tally.
- `await` — composes `devex pr read --wait` with `status` and gates on
  Sonar `ERROR` / unresolved threads. The single command to run after
  pushing a fix when you want "wake me when this PR is triage-able."

Those two are the steward unique surface today. The `await` combo verb
landed natively in devex
([devex#41](https://github.com/agentculture/devex/issues/41), now
closed); the gate extras that aren't yet native — SonarCloud hotspots,
deploy-preview URL, an explicit resolved/unresolved thread tally — are
tracked upstream in
[devex#52](https://github.com/agentculture/devex/issues/52) and
migrate out of this skill once they land.

The workflow is encapsulated in `scripts/workflow.sh` — follow that
(or call `devex pr` directly).

## The devex inversion (upstream-as-consumer)

One consumer is special: **devex itself**, the repo that owns `devex pr`.
Vendoring this skill there verbatim would re-vendor bash that just wraps the
Python devex already ships, so devex vendors it **adapted-thin**
([devex#53](https://github.com/agentculture/devex/pull/53)):
`workflow.sh` is the only script and it forwards
`lint | open | read | reply | delta | await` straight to the native
`devex pr <verb>` — including the native `devex pr await` combo verb (devex
0.21.0). The steward `status` / `await` shell extensions and the vendored
helpers (`pr-reply.sh`, `_resolve-nick.sh`, `portability-lint.sh`) are all
redundant there, each superseded by a native verb. For that one consumer the
skill collapses to a **pure delegate**.

The only gate bits not yet native are SonarCloud **hotspots**, the
**deploy-preview URL**, and an explicit **resolved/unresolved thread tally** —
tracked upstream in
[devex#52](https://github.com/agentculture/devex/issues/52). Once those
land, steward retires `pr-status.sh` too and `workflow.sh status/await`
delegates to native `devex pr` everywhere.

**For broadcasts:** a skill-update brief to devex should expect this thin
`workflow.sh`-only shape, not steward's five-file layout. (Ref:
[steward#53](https://github.com/agentculture/steward/issues/53).)

## Prerequisites

Hard requirements: `devex` (>=0.21), `gh` (GitHub CLI), `jq`, `bash`,
`python3` (stdlib only), `curl` (used by `pr-status.sh`).

Install devex once:

```bash
uv tool install devex   # or: pip install --user devex
```

Soft requirement: `PyYAML` is needed **only for suffix mode** of the
sibling `agent-config` skill, where it parses Culture's server
manifest. Every `cicd` script works without it; suffix mode prints a
clear install hint when invoked without it.

Per-machine paths (sibling-project layout) live in
`.claude/skills.local.yaml`; see the committed `.example` for the
schema. `devex pr delta` reads the same file.

## How to run

`scripts/workflow.sh` is the entry point. Subcommands:

| Command | What it does |
|---------|--------------|
| `workflow.sh lint` | `devex pr lint --exit-on-violation` — portability + alignment-trigger check. |
| `workflow.sh open [gh-flags]` | `devex pr open --delayed-read`. Creates the PR, then polls 180s for an initial briefing. `--title TITLE` required; body via `--body-file PATH` or stdin. |
| `workflow.sh read [PR] [--wait N]` | `devex pr read`. One-shot briefing (CI checks, SonarCloud gate + new issues, all comments, next-step footer). Pass `--wait N` to poll up to N seconds for required reviewers. |
| `workflow.sh reply <PR>` | `devex pr reply <PR>` — batch JSONL replies (stdin) + thread resolve. devex auto-signs from `culture.yaml`. |
| `workflow.sh delta` | `devex pr delta` — sibling alignment dump. |
| `workflow.sh status <PR>` | **Steward extension.** `pr-status.sh` — Sonar gate, OPEN issues, hotspots, unresolved-thread breakdown, deploy preview URL. Authoritative gate for `await`. |
| `workflow.sh await <PR>` | **Steward extension.** `devex pr read --wait` then `status`. Exits non-zero on Sonar ERROR or unresolved threads. Tunables: `STEWARD_PR_AWAIT_WAIT` (default 1800s passed to `--wait`), `STEWARD_PR_AWAIT_SECONDS` (legacy fixed pre-sleep, deprecated). |
| `workflow.sh help` | Print the list. |

You can also call `devex pr <verb>` directly — `workflow.sh` is a
typing-saver around the same verbs. The steward `status` and `await`
extensions only have shell entry points.

The vendored single-comment helper `pr-reply.sh` (plus its
`_resolve-nick.sh` dependency) is still shipped — pinned by
`tests/test_pr_reply_signature.py` and `tests/test_resolve_nick.py`,
and useful when a one-off reply doesn't merit batch JSONL. It is not
called by `workflow.sh` anymore. The vendored `portability-lint.sh`
is also still shipped — `steward doctor`'s portability check runs it
directly against target repos. Both are scheduled for follow-up
migration to devex.

## Long waits (background polling)

`devex pr read --wait N` polls in-session for up to N seconds. The
Anthropic prompt cache has a 5-minute TTL; sleeping past it burns
context every cache miss. Two ways to drive the wait:

- **Synchronous** — `workflow.sh await <PR>` after `gh pr create` /
  `workflow.sh open`. Fine when readiness is expected within ~5
  minutes.
- **Asynchronous** — for longer waits, run `devex pr read --wait NNN`
  inside a background subagent (Agent tool, `run_in_background: true`)
  so the main session only pays the cache cost when readiness fires.
  The subagent's only job is to invoke `devex pr read --wait` and echo
  its headline back. The parent triages with `workflow.sh await`
  when the notification arrives. The user can interrupt with
  TaskStop.

This pattern was originally borrowed from sibling repo
[`agentculture/cfafi`](https://github.com/agentculture/cfafi)'s `poll`
skill. The async guidance is also filed upstream
([devex#41](https://github.com/agentculture/devex/issues/41)).

## Conventions

`devex pr` emits a **"Next step:"** footer at the end of every command
that names the right next verb (the same chain `devex learn cicd`
documents) — follow that rather than memorizing an order. `workflow.sh
help` mirrors the verb table when you need the steward-flavored
extensions (`status`, `await`) on top.

Branch naming: `fix/<desc>`, `feat/<desc>`, `docs/<desc>`,
`skill/<name>`. PR / comment signature: `- <nick> (Claude)`, where
`<nick>` is resolved by `devex` from the agent's own `culture.yaml`
(first agent's `suffix`), falling back to the git-repo basename. devex
auto-appends the signature on `pr open` and `pr reply` only when the
body isn't already signed.

## Finishing a branch

When implementation on a branch is complete and tests pass, go straight
to `workflow.sh open` (push the branch + open the PR). Do **not** stop to
present a *merge / PR / keep / discard* menu and wait for a choice — in
AgentCulture the standing default is **always "push and create a Pull
Request."** This overrides the Superpowers `finishing-a-development-branch`
skill's interactive menu, which otherwise pauses the flow at the moment
work is ready to integrate. Merge-locally, keep-as-is, and discard happen
only when the user explicitly asks for one of them.

## Triage rules

For every comment, decide **FIX** or **PUSHBACK** with reasoning.

Default to **FIX** for: portability complaints (always valid for
Steward — recurring bug class), test or doc requests, style nits
aligned with workspace conventions.

Default to **PUSHBACK** for: architecture opinions that conflict with
workspace `CLAUDE.md` or the all-backends rule; greenfield
false-positives (e.g. "add tests" before there's any source — defer
to a later PR, don't refuse).

### Alignment-delta rule

If the PR touches `CLAUDE.md`, `culture.yaml`, or anything under
`.claude/skills/`, run `workflow.sh delta` **before** declaring FIX or
PUSHBACK on each comment. Note any sibling that needs a follow-up PR
and mention it in your reply.

## Greenfield-aware steps

The lint and the workflow script are always-on. Stack-specific steps
are conditional and currently no-op (greenfield repo):

```bash
[ -d tests ] && [ -f pyproject.toml ] && uv run pytest tests/ -x -q
[ -f pyproject.toml ] && bump_version_per_project_convention   # see project README
[ -f .markdownlint-cli2.yaml ] && markdownlint-cli2 "$(git diff --name-only --cached '*.md')"
```

Revisit each line as the corresponding stack element actually lands.
A `pr lint --extra=tests,version,markdown` ask is filed upstream
([devex#41](https://github.com/agentculture/devex/issues/41)).

## Reply etiquette

Every comment must get a reply — no silent fixes. `devex pr reply`
includes thread-resolve by default. Reference the review-comment IDs
in the fix-up commit message.

The `status` extension queries SonarCloud directly (it predates the
upstream Sonar integration in `devex pr read`). Both surfaces are
trustworthy — `devex pr read` for display in the briefing, `status` for
the gate. Steward isn't yet a registered mesh agent, so the
post-merge IRC ping that Culture's `pr-review` includes is still
skipped — that returns when Steward joins the mesh.
