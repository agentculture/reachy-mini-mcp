# Skill upstream sources

reachy-mini-mcp vendors its `.claude/skills/` from **guildmaster** — the
AgentCulture **skills supplier** after the steward → guildmaster cutover
(guildmaster 0.5.0, 2026-05-24). `steward` retains the **alignment** role
(`steward doctor`, the sibling-pattern baseline); only the skills-supplier role
moved. This file tracks provenance so re-syncs stay deterministic.

Three skills (`think`, `spec-to-plan`, `assign-to-workforce`) originate in
[`agentculture/devague`](https://github.com/agentculture/devague); one skill
(`outsource`) originates in
[`agentculture/convertible`](https://github.com/agentculture/convertible).
guildmaster only **re-broadcasts** these four. Cite guildmaster's copy; track
devague / convertible as the true origin.

Every vendored `SKILL.md` carries `type: command`. reachy-mini-mcp declares a
culture agent (`culture.yaml`, `backend: claude`), and `core.skill_loader`
silently skips any `SKILL.md` lacking `type:` — so the field is load-bearing,
even where guildmaster's upstream copy omits it. The field was added to the
seven skills whose guildmaster copy lacked it (`cicd`, `communicate`,
`doc-test-alignment`, `pypi-maintainer`, `run-tests`, `sonarclaude`,
`version-bump`); the other five already carried it upstream.

## Dormant skills

reachy-mini-mcp is a FastMCP server driven by `requirements.txt` — **not** a
Python package/CLI. Several kit skills assume a `pyproject.toml` / tests / PyPI /
SonarCloud project that does not exist here yet. They are vendored whole (the
canonical kit is vendored as a set, not curated) but are **dormant** until that
scaffolding lands: `version-bump`, `run-tests`, `sonarclaude`, `pypi-maintainer`,
and the SonarCloud/PyPI parts of `cicd`. The `cicd` PR lifecycle (`devex pr`),
`communicate`, `outsource`, `agent-config`, and the devague workflow trio work
today.

| Skill | Upstream | Origin | Notes | Last synced |
|-------|----------|--------|-------|-------------|
| `cicd` | `../guildmaster/.claude/skills/cicd/` | guildmaster | CI/CD lane layered on `devex pr`: the 5 thin scripts (`workflow.sh`, `pr-status.sh`, `pr-reply.sh`, `_resolve-nick.sh`, `portability-lint.sh`) delegate lint/open/read/reply/delta to `devex` and add the `status` / `await` SonarCloud-gating extensions. Consumer-identifying prose (`guildmaster` → `reachy-mini-mcp`) adapted in the description + heading; upstream history (`Renamed from pr-review in steward 0.7.0; rebased on devex in 0.12.0`) and env-var literals (`STEWARD_*`) kept verbatim. The PR signature resolves at runtime from `culture.yaml` via `_resolve-nick.sh` (→ `reachy-mini-mcp`). Requires `devex` on PATH. **SonarCloud `status`/`await` extensions are dormant** (no Sonar project yet). | 2026-06-02 (guildmaster 0.9.2, `851732a`) |
| `communicate` | `../guildmaster/.claude/skills/communicate/` | guildmaster | Cross-repo + mesh communication. Consumer-identifying prose adapted in the description (incl. the `- reachy-mini-mcp (Claude)` signature line). **No hard-coded signature literal in the scripts** — `post-issue.sh` is `agtag`-backed and resolves the signing nick from `culture.yaml`; requires `agtag` (>=0.1) on PATH. The supplier `scripts/templates/` (`skill-update-brief.md`) are kept verbatim — inert for a consumer (they cite guildmaster as upstream). Renamed from `coordinate` in steward 0.8.0; absorbed `gh-issues` in 0.9.1. | 2026-06-02 (guildmaster 0.9.2, `851732a`) |
| `version-bump` | `../guildmaster/.claude/skills/version-bump/` | guildmaster | Pure-Python, CWD-aware (`scripts/bump.py`). Verbatim except added `type: command`. **Dormant** — bumps `pyproject.toml`, which this repo does not have. | 2026-06-02 (guildmaster 0.9.2, `851732a`) |
| `agent-config` | `../guildmaster/.claude/skills/agent-config/` | guildmaster (origin steward) | Shows a Culture agent's full config; run `scripts/show.sh` directly (no `guild` binary required). `scripts/show.sh` + `data/backend-fingerprints.yaml` verbatim (already carried `type: command`). | 2026-06-02 (guildmaster 0.9.2, `851732a`) |
| `doc-test-alignment` | `../guildmaster/.claude/skills/doc-test-alignment/` | guildmaster | **STUB** — `scripts/check.sh` exits not-yet-implemented; the contract lives in SKILL.md. Verbatim except added `type: command`. | 2026-06-02 (guildmaster 0.9.2, `851732a`) |
| `pypi-maintainer` | `../guildmaster/.claude/skills/pypi-maintainer/` | guildmaster | Switch a package install between PyPI / TestPyPI / local editable (`scripts/switch-source.sh`). Verbatim except added `type: command`. **Dormant** — no PyPI package here. | 2026-06-02 (guildmaster 0.9.2, `851732a`) |
| `run-tests` | `../guildmaster/.claude/skills/run-tests/` | guildmaster | pytest + xdist + coverage (`scripts/test.sh`). Verbatim except added `type: command`. **Dormant** — no `tests/` / `pyproject.toml` yet. | 2026-06-02 (guildmaster 0.9.2, `851732a`) |
| `sonarclaude` | `../guildmaster/.claude/skills/sonarclaude/` | guildmaster | SonarCloud API queries (`scripts/sonar.sh`). Verbatim except added `type: command`. **Dormant** — no Sonar project yet. | 2026-06-02 (guildmaster 0.9.2, `851732a`) |
| `think` | `../guildmaster/.claude/skills/think/` | **devague** (re-broadcast via guildmaster) | idea→spec leg of the devague workflow chain. Verbatim (already carried `type: command`). Origin/broadcast prose left verbatim. | 2026-06-02 (guildmaster 0.9.2, `851732a`) |
| `spec-to-plan` | `../guildmaster/.claude/skills/spec-to-plan/` | **devague** (re-broadcast via guildmaster) | spec→plan leg of the devague workflow chain. Verbatim (already carried `type: command`). | 2026-06-02 (guildmaster 0.9.2, `851732a`) |
| `assign-to-workforce` | `../guildmaster/.claude/skills/assign-to-workforce/` | **devague** (re-broadcast via guildmaster) | plan→parallel-implementation leg of the devague workflow chain. Verbatim (already carried `type: command`). | 2026-06-02 (guildmaster 0.9.2, `851732a`) |
| `outsource` | `../guildmaster/.claude/skills/outsource/` | **convertible** (re-broadcast via guildmaster) | Hand a scoped task to convertible — a *different* engine/mind — via `explore` / `review` / `write`. `explore`/`review` run isolated in a throwaway `git worktree`; `write` refuses a dirty tree. Verbatim (already carried `type: command`; the only upstream divergence is guildmaster's re-broadcast-reframed Provenance paragraph, which we inherit as-is). Optional runtime dep: **`convertible`** on PATH. | 2026-06-02 (guildmaster 0.9.2, `851732a`) |

## Re-sync procedure

```bash
# Diff against upstream before pulling (example: cicd / communicate):
for s in cicd communicate; do
  diff -ru ../guildmaster/.claude/skills/$s .claude/skills/$s
done

# Pull a skill fresh (remove first so dropped scripts don't linger):
rm -rf .claude/skills/<skill>
cp -R ../guildmaster/.claude/skills/<skill> .claude/skills/

# Re-apply the identifier-only adaptations in SKILL.md:
#   - consumer-identifying prose: `guildmaster` → `reachy-mini-mcp` (NOT where
#     it cites guildmaster/steward/devague/convertible as the upstream/origin).
#   - add `type: command` to the frontmatter if guildmaster's copy omits it
#     (load-bearing for the culture/claude backend's core.skill_loader).
# No script bodies are edited (cite-don't-import). The communicate signature
# resolves from culture.yaml via agtag — no literal to patch.
```

Only `cicd/SKILL.md` and `communicate/SKILL.md` carry consumer-identifying prose;
the other ten skills are byte-for-byte identical to guildmaster except for the
`type: command` line added to the seven that lacked it. If a re-sync would lose a
reachy-mini-mcp adaptation, lift the change upstream into guildmaster first and
re-vendor.

## Tooling prerequisites

- **`devex`** (>=0.21) on PATH — `cicd` delegates the PR lifecycle to `devex pr`.
- **`agtag`** (>=0.1) on PATH — `communicate` issue I/O wraps `agtag issue`.

Both ship on PATH in the standard AgentCulture dev setup (installed per the
devex / agtag READMEs).

- **`convertible`** on PATH — *optional*; only the `outsource` skill needs it,
  and only when invoked (`uv tool install convertible-cli`). The wrapper exits
  with a clear install hint if it is absent, so the skill degrades gracefully
  rather than blocking a clone that never uses it. `outsource` also needs a
  reachable engine — a local vLLM by default, overridable via `--engine` /
  `--model` / `--base-url` or `CONVERTIBLE_*` env.
