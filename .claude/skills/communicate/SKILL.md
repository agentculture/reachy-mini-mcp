---
name: communicate
type: command
description: >
  Cross-repo + mesh communication from reachy-mini-mcp: file tracked GitHub issues
  on sibling repos, fetch issues from sibling repos to inline current state
  into briefs, and send live messages to Culture mesh channels. Use when
  the next step lives outside reachy-mini-mcp (a brief for a sibling-repo agent, a
  status ping for a Culture channel, or pulling an issue body + comments
  into context). Issue posts auto-sign with `- reachy-mini-mcp (Claude)`; mesh
  messages are unsigned (the IRC nick is the speaker). Not for in-reachy-mini-mcp
  issues — use `gh issue create` or the `cicd` skill for those. Renamed
  from `coordinate` in steward 0.8.0; absorbed `gh-issues` in 0.9.1.
  Issue I/O is backed by `agtag` (>=0.1) starting in 0.11.0.
---

# Communicate (Cross-Repo + Mesh)

Steward's job is alignment across the AgentCulture mesh; that surfaces in
four distinct channels:

- **Tracked, async hand-offs** — a gap in another repo (a missing public
  API, a divergent skill, a documentation ask) where an agent on the
  other side needs to act, and the ask should outlive the conversation.
  → `post-issue.sh` (GitHub).
- **Follow-up on a tracked thread** — a status update, an answer to a
  question, or a "this is done" note on an issue that's already open.
  → `post-comment.sh` (GitHub).
- **Inbound state read** — pulling current issue body + comments from a
  sibling repo so a brief or plan can inline what's there instead of
  saying "see issue #N." → `fetch-issues.sh` (GitHub).
- **Ephemeral coordination** — a status ping, a question, a "PR ready
  for merge" notice on a Culture mesh channel where the audience is
  already listening.
  → `mesh-message.sh` (Culture IRC).

All four live under one skill because they share the same audience
(sibling-repo agents) and the same red flag (don't double-post the same
ask across post + mesh — pick one).

## Backed by agtag

The three GitHub verbs (`post-issue.sh`, `post-comment.sh`,
`fetch-issues.sh`) are thin wrappers around the `agtag` CLI
(`agtag issue post|reply|fetch`). agtag handles auto-signature
resolution from the local `culture.yaml` (falling back to repo
basename), JSON output mode, and a uniform exit-code policy. Read
`agtag learn` for the agent-facing self-teaching prompt and
`agtag explain agtag` / `agtag explain issue` for the surface docs —
this SKILL.md does not re-document agtag's flags.

`mesh-message.sh` stays a `culture channel message` wrapper for now;
agtag mesh transport is slated for v0.2.

## When to Use

### Issue mode (`post-issue.sh`)

- A gap surfaces in **another repo's surface** (missing public API,
  wire-format compat fix, divergent skill, documentation ask).
- You're handing off a self-contained brief to a sibling-repo agent.
- **(steward-specific — supplier role.)** You're **onboarding a sibling to the
  stack** — "set it up", "align it", "update it with our stack", "set up the
  pipelines". The deliverable is an issue with a self-contained brief, **never
  files written into that repo**. In steward, quote steward's
  `docs/sibling-pattern.md` (required artifacts) and `docs/skill-sources.md`
  (the skill set to vendor) into the brief so it stands alone; steward's
  `CLAUDE.md` "Steward's lane" section is the canonical statement. Downstream
  vendors of this skill don't onboard siblings — those steward-side docs don't
  exist in your repo, so skip this bullet.
- You're asking a question that benefits from a tracked artifact rather
  than ephemeral chat.

### Broadcast mode (`steward announce-skill-update`)

- You bumped a skill in `.claude/skills/<name>/` and the change is
  more than identifier-only or doc-only — downstream consumers will
  benefit from re-vendoring.
- Don't hand-author the brief — the `steward announce-skill-update`
  verb (steward-cli) renders the canonical six-section form (what's
  stale, cite locations, what's in upstream now, recipe, acceptance
  criteria, references) from the live state of
  `.claude/skills/<name>/scripts/`, the `CHANGELOG.md`, and
  `docs/skill-sources.md`'s downstream column. Then it pipes through
  this skill's `post-issue.sh` per consumer (so the auto-signature
  stays consistent with hand-authored briefs).

### Mesh mode (`mesh-message.sh`)

- You want to ping a Culture channel with a status update ("PR #N ready
  for merge", "starting nightly corpus scan").
- You're asking a question where you expect a fast reply from whoever
  is listening on the channel right now.
- You're announcing a decision that doesn't need a tracked artifact.

### Comment mode (`post-comment.sh`)

- An open issue needs a follow-up — a status update, an answer to a
  maintainer's question, a "this is shipped" note pointing at a PR.
- You're closing the loop on an `agtag issue post` you sent earlier and
  the resolution belongs on the same thread (audit trail beats a
  separate ping).
- Auto-signed by agtag; do not hand-author the trailing nick.

### Fetch mode (`fetch-issues.sh`)

- You're about to write a brief and want to inline the current state of
  one or more sibling-repo issues (body + comments) instead of saying
  "see issue #N."
- You're triaging a list of cross-repo issues and want their bodies and
  comments in one shot for context.
- Avoids the `gh issue view` "Projects (classic) deprecated" error by
  passing `--json` explicitly to GitHub.

## When NOT to Use

- **In-steward issues** — open them with `gh issue create` directly, or
  work them through the `cicd` skill.
- **PR review comments** — that's the `cicd` skill (which already
  auto-signs replies).
- **Routine commits** — those don't get cross-repo signatures.
- **Long-form asks on the mesh** — anything that needs acceptance
  criteria belongs in an issue, not a channel message.

## Conventions

### 1. Briefs are self-contained

The receiving agent must not need steward-side context to act. Inline
the relevant content; do not say "see steward's plan."

A brief that says "see steward#NN" is a bug. The receiving agent will
look at it, get lost in steward-specific context that's irrelevant to
them, and either ask for clarification (slow round-trip) or guess wrong
(worse). Inline the ask, the rationale, and concrete acceptance
criteria. Quote source-of-truth files (path + line numbers + small
excerpts) when their shape matters to the ask.

### 2. Per-channel signature rules

| Channel | Signature | Why |
|---------|-----------|-----|
| GitHub issues / comments | `- <nick> (Claude)` — agtag resolves `<nick>` from the local `culture.yaml`, falling back to repo basename | Cross-repo audit trail — readers can tell at a glance which sibling and that it came from an AI. |
| Culture mesh | none — unsigned | The IRC nick already identifies the speaker. A trailing `- <nick> (Claude)` would be visual noise that the nick already supplies. |

Vendors do not need to edit a literal — agtag does the resolution.
`--as NICK` overrides if a vendor needs to sign as something other than
its `culture.yaml` suffix. Mesh messages stay unsigned across all
vendors.

### 3. Issue title format

`<verb> <thing> (unblocks <consumer>)` — e.g.,
`Vendor portability-lint into <repo> (unblocks steward 0.7 doctor --apply)`.
The parenthetical tells the receiving repo's maintainers what's waiting
on them. Drop the parenthetical only when the ask isn't blocking
anything.

## How to Invoke

### File a new issue

```bash
bash .claude/skills/communicate/scripts/post-issue.sh \
    --repo agentculture/<sibling> \
    --title "Vendor portability-lint into <sibling> (unblocks steward 0.7)" \
    --body-file /tmp/brief.md
```

Or pass the body on stdin:

```bash
bash .claude/skills/communicate/scripts/post-issue.sh \
    --repo agentculture/<sibling> \
    --title "..." <<'EOF'
<brief body here, multi-paragraph, with all the inline context the receiving agent needs>
EOF
```

The script prints the issue URL on success — capture it for
cross-references in your spec / plan / PR description. agtag appends
the signature `- <nick> (Claude)` (resolved from `culture.yaml`).

### Broadcast a skill update to known consumers

This is steward's role specifically — the verb lives in `steward-cli`,
not in this skill's `scripts/`. Downstream vendors of `communicate`
(cfafi, culture, auntiepypi, …) do not get a broadcast wrapper because
they don't broadcast — they only use the primitives above
(`post-issue.sh`, `fetch-issues.sh`, `mesh-message.sh`).

```bash
# Default: read consumers from docs/skill-sources.md "Downstream copies"
# cell for <skill>; render the six-section brief; pipe to post-issue.sh
# for each consumer.
steward announce-skill-update --skill cicd --since 0.6.0

# Override the consumer list (skips the ledger lookup entirely):
steward announce-skill-update --skill cicd \
    --to agentculture/auntiepypi --to agentculture/cfafi

# Preview without posting:
steward announce-skill-update --skill cicd \
    --to agentculture/auntiepypi --dry-run

# Just print the consumer list (for ledger sanity-checks):
steward announce-skill-update --skill cicd --list
```

`--since VERSION` controls which CHANGELOG entries get inlined (every
entry from the top down to but not including the cutoff version).
Without it, the verb keyword-filters CHANGELOG entries to those
mentioning the skill name. `--note-file PATH` appends free-text under
the upstream script list for skill-specific gotchas the generic
template can't anticipate (e.g. "this skill's `post-issue.sh`
hard-codes a signature literal — your vendor must change it"). The
brief is rendered once and reused across consumers; per-consumer
failures stream to stderr and the verb exits 1 if any failed. The
template lives at
`scripts/templates/skill-update-brief.md` so future supplier-role
repos can render their own briefs from the same shape.

#### Fast recipe — "brief sibling-repo Z on skill X"

This shape of ask is a recipe, not a planning question. Skip plan
mode. The call site:

```bash
steward announce-skill-update \
    --skill <name> --to <owner>/<repo> \
    --since <last-stable-version> \
    [--note-file /tmp/note.md] --dry-run
```

Eyeball the rendered brief; drop `--dry-run` to post. The verb
prints the issue URL on success and exits non-zero on failure —
that is the verification. Don't write parallel `gh issue list` /
`gh issue view` checks unless the verb itself is what you're
testing. `--to` overrides the ledger, so non-ledger consumers
don't require a ledger edit first; they enter the ledger later
when they confirm their vendored shape.

### Comment on an existing issue

```bash
bash .claude/skills/communicate/scripts/post-comment.sh \
    --repo agentculture/<sibling> \
    --number 42 \
    --body-file /tmp/follow-up.md
```

Or pipe the body in:

```bash
bash .claude/skills/communicate/scripts/post-comment.sh \
    --repo agentculture/<sibling> \
    --number 42 <<'EOF'
PR #87 has shipped — closing the loop on this thread.
EOF
```

Auto-signed by agtag from `culture.yaml`; do not hand-author the
trailing nick.

### Send a mesh channel message

```bash
bash .claude/skills/communicate/scripts/mesh-message.sh \
    --channel "#general" \
    --body "PR #42 — all review threads addressed. Ready for merge."
```

Body can also come from `--body-file PATH` or stdin. The script wraps
`culture channel message <target> <text>` and forwards exit codes
unchanged, so failures (no Culture server, agent not connected) surface
verbatim. No signature is appended — the IRC nick is the speaker.

### Fetch sibling-repo issues

```bash
bash .claude/skills/communicate/scripts/fetch-issues.sh 191 --repo agentculture/culture
bash .claude/skills/communicate/scripts/fetch-issues.sh 191-197 --repo agentculture/culture
bash .claude/skills/communicate/scripts/fetch-issues.sh 191 195 197
```

Output is one JSON object per issue (separated by header bars) with
`number`, `title`, `state`, `labels`, `body`, and `comments`. Without
`--repo`, `gh` resolves the repo from the current git remote. Failures
on a single issue print `ERROR: Could not fetch issue #N` and continue
with the next one.

Steward is **not** a registered mesh agent today (see the cicd SKILL.md
note). The script works once steward has been registered and started
via `culture agent register` + `culture start spark-steward`; until
then, calling it will fail with whatever error the Culture CLI returns,
which is the right behavior — fix the registration, don't paper over it.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/post-issue.sh` | Create a new issue on a target repo. Wraps `agtag issue post`; auto-signs from `culture.yaml`. |
| `scripts/post-comment.sh` | Comment on an existing issue. Wraps `agtag issue reply`; auto-signs from `culture.yaml`. |
| `scripts/fetch-issues.sh` | Fetch one or more issues (single / range / list) with body + comments. Wraps `agtag issue fetch`. |
| `scripts/mesh-message.sh` | Send a message to a Culture mesh channel. Unsigned (IRC nick is the speaker). |
| `scripts/templates/skill-update-brief.md` | The Markdown template consumed by `steward announce-skill-update` (the broadcast verb lives in steward-cli, not in this skill). Six fixed sections; placeholder syntax `{{NAME}}`. |

More scripts can land here as the communication footprint grows —
`mesh-ask.sh` for question-shaped pings via `culture channel ask`,
agtag-mesh wrappers once `agtag message` ships in v0.2, etc. Add them
when there's a second concrete need; do not pre-build for
hypotheticals.

## Red Flags

**Never:**

- Scaffold or write files into the *target* repo when the ask is an issue on
  it. Handing off / onboarding is an **issue, not an edit** — a direct "set
  them up" is still an instruction to file the brief. (In steward this is the
  "Steward's lane" rule; the principle holds for any vendor of this skill.)
- Post a brief that says "see steward's plan" without inlining the
  content. Briefs must be self-contained.
- Skip the issue signature. The script enforces it; do not introduce a
  `--no-signature` flag.
- Sign mesh messages with `- <nick> (Claude)`. The nick already says
  who you are.
- Use this skill for in-steward issues — use `gh issue create` or the
  `cicd` skill instead.
- Manually type `- <nick> (Claude)` at the end of an issue or comment
  body — agtag appends it. Manual typing creates double-signatures.
- Post the same ask twice across channels (issue + mesh). Pick one.
  Tracked → issue. Ephemeral → mesh.
- Use mesh mode for anything that needs acceptance criteria. If the
  receiving agent has to decide "did I do this right?", you owe them
  an issue.
