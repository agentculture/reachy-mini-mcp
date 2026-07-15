#!/usr/bin/env bash
#
# ask-colleague — hand a scoped repo task to colleague (a different engine/mind).
#
# Colleague's engine is not necessarily stronger than the calling agent; it is
# a *different* mind, and diversity helps — which is why `review` is the headline
# verb. Three verbs drive `colleague drive` and print the result:
#
#   ask-colleague explore "<question or area>"   read-only investigation -> findings
#   ask-colleague review  "<what to focus on>"   diverse second-opinion on the diff
#   ask-colleague write   "<task>" [--apply]     implement a change (preview by default)
#   ask-colleague feedback <id|last> --rating N  grade a past drive (ROI loop); no rating -> show
#   ask-colleague feedback list                  list every recorded drive by request + grade
#   ask-colleague clean                          reap stale colleague/* branches + artifacts (#162)
#
# explore/review run in a throwaway `git worktree` at HEAD, so they can never
# touch your working tree or branch (any stray write is discarded). write also
# previews in a throwaway worktree by default (reporting what it WOULD change);
# pass --apply to land a drive branch in place, or --pr to push + open a PR.
#
# explore/review are read-only probes: they preserve their artifact but do NOT
# move the `last` pointer (issue #132), so `feedback last` stays aimed at the
# most recent consequential write. Grade a probe by its printed task-id (every
# drive prints `task:` and a `grade:` hint), or find it with `feedback list`.
#
# A crashed/interrupted `write --apply` can leave a dangling colleague/<id>
# branch (and 0-byte .colleague/ artifacts) that breaks `git fetch`. The
# EXIT-trap cleanup below only reaps the *current* read-only run's worktree, not
# a *prior* crashed run — `ask-colleague clean` (which shells out to `colleague
# clean`) reaps those, scoped strictly to colleague/* so an unrelated branch is
# never touched.
#
# Exit-code policy (matches colleague's CLI contract, #161): 0 success · 1
# user-input error (bad/missing verb, flag, arg, or path; dirty-tree state guard
# — same class as the runtime's EXIT_USER_ERROR guard) · 2 environment/setup
# error (missing required tool, colleague CLI not found, missing prompt template).
#
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPTS_DIR="$SKILL_DIR/prompts"

# ── resolve the colleague CLI (installed, then local-dev fallback) ─────────
COLLEAGUE=()

_pyproject_is_colleague() {
    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" == 'name = "colleague"'* ]] && return 0
    done < "$1"
    return 1
}

_colleague_via_uv() {
    local dir="$1"
    while [[ -n "$dir" ]] && [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/pyproject.toml" ]] \
            && _pyproject_is_colleague "$dir/pyproject.toml"; then
            command -v uv >/dev/null 2>&1 || return 1
            COLLEAGUE=(uv run --project "$dir" colleague)
            return 0
        fi
        dir=$(dirname "$dir")
    done
    return 1
}

resolve_colleague() {
    if command -v colleague >/dev/null 2>&1; then
        COLLEAGUE=(colleague)        # installed tool — the normal case
        return 0
    fi
    _colleague_via_uv "$PWD"  && return 0
    _colleague_via_uv "$REPO" && return 0
    cat >&2 <<'EOF'
error: colleague CLI not found.
hint: install it with `uv tool install colleague` (or `pipx install colleague`),
      or run from inside the colleague checkout with `uv` available.
      https://github.com/agentculture/colleague
EOF
    return 1
}

usage() {
    cat <<'EOF'
ask-colleague — hand a scoped repo task to colleague (a different engine/mind).

Usage:
  ask-colleague explore "<question or area>"     Read-only investigation -> findings (no side effects)
  ask-colleague review  "<what to focus on>"     Diverse second-opinion on the committed diff (no side effects)
  ask-colleague write   "<task>" [--apply|--pr]  Implement a change (preview by default; --apply lands it)
  ask-colleague plan    "<task>" [--no-workforce] Colleague PLANS a complex task (spec -> plan -> subagent workforce)
  ask-colleague feedback <id|last> [--rating N]  Grade a past drive (ROI loop); with --rating records, without shows
  ask-colleague feedback list                    List every recorded drive by request + grade (find one by its request)
  ask-colleague clean [--dry-run]                Reap stale/corrupt colleague/* branches + orphaned .colleague/ artifacts (#162)
  ask-colleague monitor <task-id>                Stream a running flight's live feed (--follow)
  ask-colleague guide   <task-id> "<msg>"         Send mid-flight guidance to a running flight
  ask-colleague stop    <task-id>                Ask a running flight to stop (cooperative)

Options:
  --repo PATH        Target repo (default: .)
  --dry-run          (clean) report what would be reaped without changing anything
  --base BRANCH      Base for `review` diff (default: main)
  --engine NAME      Backend plugin (default: $COLLEAGUE_ENGINE or vllm-openai)
  --model NAME       Model (default: $COLLEAGUE_MODEL or sakamakismile/Qwen3.6-27B-Text-NVFP4-MTP)
  --role NAME        Typed subagent role (e.g. explorer, reviewer, writer)
  --base-url URL     OpenAI base URL (default: $COLLEAGUE_BASE_URL or http://localhost:8001/v1)
  --max-steps N      Loop step budget (default: 20; explore/review default from
                     colleague's own "explore"/"review" mode profile, today 30 —
                     an explicit --max-steps always overrides, lower or higher)
  --timeout N        Per-request timeout, seconds (default: $COLLEAGUE_TIMEOUT or 300)
  --no-workforce     (plan) deliver the spec+plan only, skip the workforce fan-out (#215)
  --quick / --no-spec (plan) skip the spec stage, plan directly from the request (#199)
  --apply            (write) apply the change in place (drive branch) instead of previewing
  --allow-dirty      (write) allow running on a dirty tree (only with --apply/--pr)
  --pr               (write) push + open a PR instead of a local drive branch (implies --apply)
  --rating N         (feedback) record a 1-5 quality rating for the drive
  --notes "..."      (feedback) free-text notes to store with the rating
  --by NAME          (feedback) who is grading (default: colleague's resolved identity)
  --watch            (explore/review/write) arm a flight so you can monitor/guide/stop it
  --json             Machine-readable output: stdout carries only the result JSON,
                     every diagnostic/digest line goes to stderr (any verb)

explore/review run in a throwaway git worktree at HEAD — they cannot touch your
working tree or branch. review compares <base>...HEAD (committed changes only).
write previews in a throwaway worktree too unless --apply (or --pr) is given.
feedback grades a finished drive: stats (in the artifact) say what it cost,
feedback says how good it was — together, the ROI of outsourcing. explore/review
do not move `last` (they are read-only) — grade them by their printed task-id, or
run `ask-colleague feedback list` to find a drive by its request.
clean recovers a repo a crashed run wedged: it reaps stale/corrupt colleague/*
branches + orphaned .colleague/ artifacts (scoped to colleague/* only). For the
full flag set (--merged / --older-than) call `colleague clean` directly.
EOF
}

# ── parse the verb ──────────────────────────────────────────────────────────
VERB="${1:-}"
case "$VERB" in
    explore | review | write | plan | feedback | clean | monitor | guide | stop) shift ;;
    -h | --help) usage; exit 0 ;;
    "") usage >&2; exit 1 ;;  # missing arg -> user-input error (#161)
    *)
        echo "error: unknown verb '$VERB' (expected explore|review|write|plan|feedback|clean|monitor|guide|stop)" >&2
        echo "hint: run 'ask-colleague --help'" >&2
        exit 1  # bad verb -> user-input error (#161)
        ;;
esac

# Verify the external tools a given verb path actually needs are on PATH — fail
# fast with a clear message, not an opaque mid-run error. The required set is
# verb-specific (the caller passes it once the verb + flags are known, below):
# feedback/clean are thin pass-throughs to `colleague` plus the shared git
# work-tree guard, so they need only git; the drive verbs (explore/review/write)
# also render a prompt and parse colleague's --json result via python3, and the
# worktree-isolated paths additionally need mktemp.
require_tools() {  # $@ = tool names this verb path needs
    local missing=() t
    for t in "$@"; do
        command -v "$t" >/dev/null 2>&1 || missing+=("$t")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "error: missing required tool(s): ${missing[*]}" >&2
        echo "hint: '$VERB' needs these on PATH: $*" >&2
        exit 2
    fi
}

# Guard a value-taking flag: a trailing flag with no value would otherwise
# dereference an unset $2 and abort under `set -u`.
need_value() {  # $1 = remaining arg count ($#), $2 = flag name
    [[ "$1" -ge 2 ]] || {
        echo "error: $2 requires a value" >&2
        echo "hint: run 'ask-colleague --help'" >&2
        exit 1  # missing flag value -> user-input error (#161)
    }
}

# ── defaults + flag parsing ─────────────────────────────────────────────────
REPO="."
BASE="main"
# COLLEAGUE_* wins; the legacy CONVERTIBLE_* names are honored as a deprecated fallback.
ENGINE="${COLLEAGUE_ENGINE:-${CONVERTIBLE_ENGINE:-vllm-openai}}"
MODEL="${COLLEAGUE_MODEL:-${CONVERTIBLE_MODEL:-sakamakismile/Qwen3.6-27B-Text-NVFP4-MTP}}"
BASE_URL="${COLLEAGUE_BASE_URL:-${CONVERTIBLE_BASE_URL:-http://localhost:8001/v1}}"
MAX_STEPS=20
MAX_STEPS_EXPLICIT=0
TIMEOUT="${COLLEAGUE_TIMEOUT:-${CONVERTIBLE_TIMEOUT:-300}}"
ALLOW_DIRTY=0
APPLY=0
OPEN_PR=0
DRY_RUN=0
WATCH=0
RATING=""
NOTES=""
BY=""
ARG=""
JSON_OUT=0
ROLE=""
QUICK=0
NO_WORKFORCE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo) need_value "$#" "$1"; REPO="$2"; shift 2 ;;
        --base) need_value "$#" "$1"; BASE="$2"; shift 2 ;;
        --engine) need_value "$#" "$1"; ENGINE="$2"; shift 2 ;;
        --model) need_value "$#" "$1"; MODEL="$2"; shift 2 ;;
        --role) need_value "$#" "$1"; ROLE="$2"; shift 2 ;;
        --base-url) need_value "$#" "$1"; BASE_URL="$2"; shift 2 ;;
        --max-steps) need_value "$#" "$1"; MAX_STEPS="$2"; MAX_STEPS_EXPLICIT=1; shift 2 ;;
        --timeout) need_value "$#" "$1"; TIMEOUT="$2"; shift 2 ;;
        --apply) APPLY=1; shift ;;
        --watch) WATCH=1; shift ;;
        --allow-dirty) ALLOW_DIRTY=1; shift ;;
        --pr) OPEN_PR=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --quick | --no-spec) QUICK=1; shift ;;       # plan: skip the spec stage (#199)
        --no-workforce) NO_WORKFORCE=1; shift ;;     # plan: deliver spec+plan only (#215)
        --rating) need_value "$#" "$1"; RATING="$2"; shift 2 ;;
        --notes) need_value "$#" "$1"; NOTES="$2"; shift 2 ;;
        --by) need_value "$#" "$1"; BY="$2"; shift 2 ;;
        --json) JSON_OUT=1; shift ;;
        -h | --help) usage; exit 0 ;;
        --) shift; while [[ $# -gt 0 ]]; do ARG="${ARG:+$ARG }$1"; shift; done ;;
        # unknown option -> user-input error (#161)
        -*) echo "error: unknown option '$1'" >&2; echo "hint: run 'ask-colleague --help'" >&2; exit 1 ;;
        *) ARG="${ARG:+$ARG }$1"; shift ;;
    esac
done

# Per-verb default: explore and review get a modest higher budget (30) for wider
# surveys and read-heavy diffs; write keeps the global default (20). Only apply
# when the user did NOT pass an explicit --max-steps.
#
# t4/spec R1: this number now ALSO matches colleague's own native "explore"/
# "review" mode profile (colleague/profiles.py), which is what actually drives
# the step budget at runtime once `--mode` is selected below — this wrapper-side
# value survives only so the "widen --max-steps" re-run hint (print_result)
# still names the right number; whether --max-steps is actually FORWARDED to
# colleague is decided later, once mode support is known.
if [[ ( "$VERB" == "explore" || "$VERB" == "review" ) && "$MAX_STEPS_EXPLICIT" -eq 0 ]]; then
    MAX_STEPS=30
fi

# Now that the verb and its flags are known, require only the tools THIS path
# uses. feedback/clean shell straight to `colleague` (+ the git work-tree guard
# below), so they need only git — not python3/mktemp (qodo: the old blanket check
# failed those verbs in minimal envs). write --apply/--pr lands in place with no
# throwaway worktree, so it needs no mktemp either.
case "$VERB" in
    feedback | clean | plan) require_tools git ;;
    monitor | guide | stop) : ;;
    write)
        if [[ "$APPLY" -eq 1 || "$OPEN_PR" -eq 1 ]]; then
            require_tools git python3
        else
            require_tools git python3 mktemp  # preview runs in a throwaway worktree
        fi
        ;;
    *) require_tools git python3 mktemp ;;  # explore / review
esac

# clean takes no description argument; every other verb requires one. (All of the
# guards below are user-input errors -> exit 1, per the policy comment at the top.)
if [[ "$VERB" == "clean" ]]; then
    [[ -z "$ARG" ]] || { echo "error: clean takes no description argument" >&2; exit 1; }
else
    [[ -n "$ARG" ]] || { echo "error: $VERB needs a description argument" >&2; usage >&2; exit 1; }
fi
[[ -d "$REPO" ]] || { echo "error: --repo is not a directory: $REPO" >&2; exit 1; }
REPO="$(cd "$REPO" && pwd)"

# One git-repo guard for every verb: --repo is a runtime target like `git -C`, but
# it must at least be a real git work tree. Fail fast with a clear message instead
# of an opaque mid-drive error (read-only verbs add a worktree, write commits a
# drive branch, clean reaps colleague/* refs).
# The pilot verbs (monitor/guide/stop) are pure .colleague/flight/ file I/O — they
# need no git work tree, so they are exempt from this fail-fast guard.
case "$VERB" in
    monitor | guide | stop) : ;;
    *)
        git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
            || { echo "error: --repo is not a git repository: $REPO" >&2; exit 1; }
        ;;
esac

# review interpolates --base into the LLM instruction ("git diff $BASE...HEAD"),
# so reject a value that is not a real commit/ref before it is rendered into the
# prompt — fail fast rather than hand the model a bogus (or injected) ref.
if [[ "$VERB" == "review" ]]; then
    git -C "$REPO" rev-parse --verify --quiet "${BASE}^{commit}" >/dev/null 2>&1 \
        || { echo "error: --base is not a valid commit/ref in $REPO: $BASE" >&2; exit 1; }
fi

resolve_colleague || exit 2

# Per-request timeout is config (no drive flag); EngineConfig reads it from env.
# A local model can be slow on a growing context, so default generously.
export COLLEAGUE_TIMEOUT="$TIMEOUT"

# ── plan: colleague does the planning (the inverse of /think) ────────────────
# plan delegates the WHOLE planning arc to colleague via the `colleague plan`
# verb — no throwaway worktree, no prompt template. Gated non-interactively
# (--yes) so a delegating agent can hand off the arc and read the
# spec -> plan -> workforce result. colleague is the planning mind; /think keeps
# Claude as the planner (same arc, a different mind).
if [[ "$VERB" == "plan" ]]; then
    plan_flags=(--repo "$REPO" --engine "$ENGINE" --model "$MODEL" --base-url "$BASE_URL" --yes)
    # --quick skips the spec stage (#199); --no-workforce delivers spec+plan only,
    # skipping the timeout-prone fan-out (#215). --timeout already applies via the
    # COLLEAGUE_TIMEOUT export above. These are forwarded, never auto-applied.
    [[ "$QUICK" -eq 1 ]] && plan_flags+=(--quick)
    [[ "$NO_WORKFORCE" -eq 1 ]] && plan_flags+=(--no-workforce)
    [[ "${JSON_OUT:-0}" -eq 1 ]] && plan_flags+=(--json)
    plan_rc=0
    "${COLLEAGUE[@]}" plan run "$ARG" "${plan_flags[@]}" || plan_rc=$?
    # No silent auto-degrade: name the recovery levers (those not already set) and
    # let the caller choose. Human hints are TEXT-mode only — in --json mode the
    # consumer is a machine and colleague's own structured {code,message,remediation}
    # error already went to stderr, so suppress the prose there (Qodo #230 F4).
    if [[ "$plan_rc" -ne 0 && "${JSON_OUT:-0}" -ne 1 ]]; then
        echo "hint: plan mode did not complete on this backend. Recovery options (no auto-degrade):" >&2
        [[ "$NO_WORKFORCE" -eq 0 ]] && echo "hint:   --no-workforce  deliver the spec+plan only, skip the timeout-prone workforce fan-out (#215)" >&2
        [[ "$QUICK" -eq 0 ]] && echo "hint:   --quick         skip the spec stage, plan directly from the request (#199)" >&2
        echo "hint:   --timeout N     widen the per-request window (currently ${TIMEOUT}s)" >&2
    fi
    exit "$plan_rc"
fi

# ── explore/review adopt colleague's native mode profile (t4/spec R1) ───────
# explore/review's step budget + synthesis-reserve tail used to be caller-side
# overrides baked into this script (a fixed --max-steps 30 plus an exported
# COLLEAGUE_SYNTHESIS_RESERVE_STEPS=3). Those numbers now live in colleague's
# own mode-profile catalog (colleague/profiles.py "explore"/"review") and are
# applied runtime-side by `colleague work --mode explore|review`
# (colleague/config.py apply_mode_profile) — so this wrapper's job shrinks to
# "select the mode" instead of re-deriving the profile's numbers itself; a
# future retune of the profile then reaches this wrapper for free.
#
# Honest limit: this wrapper prefers an installed `colleague` on PATH ahead of
# a local checkout, and an installed CLI can be older than the one this repo
# ships (it can predate --mode entirely). Detect that cheaply by checking the
# resolved CLI's OWN --help text for the literal flag with a plain bash
# substring match (no external text-search tool — the resolver stays as
# dependency-free as the uv-fallback path above, #190); fall back to the old
# caller-side defaults when --mode isn't there, so the wrapper keeps working
# unmodified against a stale CLI.
#
# NOTE: the substring must be anchored past the flag name — "--mode" is
# itself a literal prefix of "--model" (already a flag on every version), so
# a naive `*--mode*` match false-positives on a stale --help that only has
# --model. Requiring the next character NOT be a letter (or end-of-string)
# distinguishes a genuine "--mode ..."/"--mode]" occurrence from "--model".
MODE_SUPPORTED=0
if [[ "$VERB" == "explore" || "$VERB" == "review" ]]; then
    help_out="$("${COLLEAGUE[@]}" work --help 2>/dev/null)" || help_out=""
    if [[ "$help_out" == *"--mode"[!a-zA-Z]* || "$help_out" == *--mode ]]; then
        MODE_SUPPORTED=1
    fi
fi

if [[ ( "$VERB" == "explore" || "$VERB" == "review" ) && "$MODE_SUPPORTED" -eq 0 ]]; then
    # Legacy fallback (stale CLI without --mode): reserve a few steps for the
    # final verdict turn so a big-diff review/explore yields findings instead
    # of dying mid-read (#197). Caller env wins.
    : "${COLLEAGUE_SYNTHESIS_RESERVE_STEPS:=3}"
    export COLLEAGUE_SYNTHESIS_RESERVE_STEPS
fi

COMMON_FLAGS=(--engine "$ENGINE" --model "$MODEL" --base-url "$BASE_URL" --json)
# --max-steps: forwarded unless this is a native-mode-capable explore/review run
# with no explicit --max-steps — then the flag is withheld so colleague's own
# mode profile supplies the step budget as a DEFAULT at runtime. An explicit
# --max-steps always wins, in EITHER direction (lower or higher than the
# profile's own number): it is still forwarded here, and the runtime resolves
# an explicit flag ahead of any profile default (colleague/config.py
# apply_mode_profile's explicit-knobs precedence).
if [[ "$MAX_STEPS_EXPLICIT" -eq 1 || "$MODE_SUPPORTED" -eq 0 || ( "$VERB" != "explore" && "$VERB" != "review" ) ]]; then
    COMMON_FLAGS+=(--max-steps "$MAX_STEPS")
fi
# --mode: select colleague's native explore/review constraint profile when the
# resolved CLI supports it (detected above). write carries no --mode — its
# profile is behavior-neutral (identical to no mode at all), so the numbers
# stay exactly as documented (--max-steps 20 default, no reserve override).
if [[ "$MODE_SUPPORTED" -eq 1 && ( "$VERB" == "explore" || "$VERB" == "review" ) ]]; then
    COMMON_FLAGS+=(--mode "$VERB")
fi
# --watch arms a flight for EVERY drive verb (explore/review/write), so it lives on
# the shared flag list — not inside one verb's path — so monitor/guide/stop work.
[[ "${WATCH:-0}" -eq 1 ]] && COMMON_FLAGS+=(--watch)
# --role forwards a typed-subagent role to the work item.
[[ -n "${ROLE:-}" ]] && COMMON_FLAGS+=(--role "$ROLE")

# ── render an instruction from a prompt template ────────────────────────────
render_prompt() {
    local file="$PROMPTS_DIR/$1.md"
    [[ -f "$file" ]] || { echo "error: missing prompt template: $file" >&2; exit 2; }
    # Single-pass substitution: doing `.replace("$ARGUMENTS", ARG).replace("$BASE",
    # BASE)` in two passes lets a literal "$BASE" *inside* the user's argument get
    # clobbered by the second pass. One re.sub never re-scans already-substituted
    # text, so injected tokens survive verbatim.
    ARG="$ARG" BASE="$BASE" python3 - "$file" <<'PY'
import os, re, sys
tpl = open(sys.argv[1], encoding="utf-8").read()
repl = {"$ARGUMENTS": os.environ["ARG"], "$BASE": os.environ["BASE"]}
sys.stdout.write(re.compile(r"\$ARGUMENTS|\$BASE").sub(lambda m: repl[m.group(0)], tpl))
PY
}

# ── print the TaskResult that colleague emitted as JSON on stdout ─────────
# Reads JSON on stdin; prints a human/agent-readable digest — to stdout on
# success, to stderr on failure so a caller can script on a clean stdout — and
# exits non-zero if the drive failed.
print_result() {
    # NOTE: must be `python3 -c`, not `python3 - <<HEREDOC`: a heredoc becomes
    # python's stdin (the script source), which would shadow the piped JSON and
    # leave sys.stdin.read() empty. The script body uses no single quotes.
    #
    # $1 (optional): the real artifact directory. When the drive ran in a
    # throwaway worktree (read-only verbs), the JSON's artifacts_path points into
    # that soon-deleted worktree; pass the real repo's .colleague/ so the
    # printed path names the preserved copy instead. Empty -> print as-is.
    # $2 (optional): "1" when the drive is gradable (its artifact survives in the
    # real repo) -> print a copy-paste `grade:` hint with the explicit task-id, so
    # the caller never has to rely on `last` (issue #132). A preview leaves it
    # empty (its artifact was discarded with the worktree, so it is not gradable).
    # $3 (optional): exit code from the colleague drive command, propagated to
    # the caller when the drive itself failed.
    ASK_COLLEAGUE_REAL_ARTIFACT_DIR="${1:-}" ASK_COLLEAGUE_GRADABLE="${2:-}" ASK_COLLEAGUE_DRIVE_RC="${3:-}" ASK_COLLEAGUE_JSON="${JSON_OUT:-0}" ASK_COLLEAGUE_MAX_STEPS="${MAX_STEPS:-20}" python3 -c '
import sys, json, os
raw = sys.stdin.read().strip()
json_mode = os.environ.get("ASK_COLLEAGUE_JSON") == "1"
def _fail(code, message, remediation, detail=None):
    # #226: in --json mode emit a structured {code, message, remediation} object
    # on stderr (matching colleague CliError shape) so a machine consumer parses
    # a failure the same way it parses success; in text mode keep the standard
    # error:/hint: contract. stdout stays clean (no result) on every path.
    if json_mode:
        obj = {"code": code, "message": message, "remediation": remediation}
        if detail is not None:
            obj["detail"] = detail
        sys.stderr.write(json.dumps(obj) + "\n")
    else:
        sys.stderr.write("error: " + message + "\n")
        if detail is not None:
            sys.stderr.write(detail + "\n")
        if remediation:
            sys.stderr.write("hint: " + remediation + "\n")
    sys.exit(code)
if not raw:
    _fail(2, "colleague produced no result on stdout (see diagnostics above)",
          "re-run; if it persists, check the backend with colleague doctor --probe")
try:
    d = json.loads(raw)
except Exception:
    _fail(2, "could not parse colleague --json output",
          "the backend may have emitted non-JSON; see the raw output and diagnostics above",
          detail=raw[:2000])
ok = d.get("status") == "ok"
inc = d.get("incompletion") if isinstance(d.get("incompletion"), dict) else None
tid = d.get("task_id") or ""
# Resolve the artifact path to the preserved copy when the drive ran in a
# throwaway worktree (read-only verbs); the raw JSON points into the now-deleted
# worktree, so both the digest and the --json output report the real location.
ap = d.get("artifacts_path")
real_dir = os.environ.get("ASK_COLLEAGUE_REAL_ARTIFACT_DIR") or ""
if ap and real_dir:
    ap = os.path.join(real_dir, os.path.basename(ap))
# A drive that stopped without calling finish (colleague#142) or exhausted its
# step budget did NOT deliver an authoritative result — its summary is the model
# trailing off mid-task. Warn so the caller treats it as a partial, not a verdict.
# The warning is a DIAGNOSTIC -> always stderr (never stdout), so both the digest
# and --json keep a clean, machine-readable stdout (no single quotes in this body).
# Enriched partial warnings: include reached step count and a concrete larger
# --max-steps to retry with, so the hint is actionable (#194).
max_steps = int(os.environ.get("ASK_COLLEAGUE_MAX_STEPS", "20"))
stats = d.get("stats") or {}
model_turns = stats.get("model_turns")
step_count = stats.get("step_count")
if d.get("stopped_without_finish"):
    reached = model_turns if model_turns is not None else step_count
    if reached is not None:
        print(f"warning: drive ended without calling finish (reached {reached} model turns of {max_steps}) — re-run with --max-steps {2 * max_steps} to go deeper.", file=sys.stderr)
    else:
        print("warning: drive ended without calling finish — treat the summary as a", file=sys.stderr)
        print("         partial (the model stopped mid-task), not an authoritative result.", file=sys.stderr)
elif d.get("not_finished"):
    reached = model_turns if model_turns is not None else step_count
    if reached is not None:
        print(f"warning: drive ran out of steps without finishing (reached {reached} model turns of {max_steps}) — re-run with --max-steps {2 * max_steps} to go deeper.", file=sys.stderr)
    else:
        print("warning: drive ran out of steps without finishing — summary is partial.", file=sys.stderr)
# No-result sentinel: the drive produced nothing actionable (#192).
summary = d.get("summary") or ""
if summary == "__COLLEAGUE_NO_RESULT_PRODUCED__":
    print("warning: no result produced — widen --max-steps or narrow the scope.", file=sys.stderr)
# Incompletion: when the run did NOT deliver (status != "ok") and colleague
# carried an incompletion record, surface it as a diagnostic to stderr so the
# delegating caller knows WHY the run failed and what to do next. Always stderr
# (never stdout) so --json stdout stays pure.
if not ok and inc:
    reason = inc.get("reason", "")
    recommendation = inc.get("recommendation", "")
    print(f"incomplete: {reason} — {recommendation}", file=sys.stderr)
if json_mode:
    # --json contract: stdout carries ONLY the TaskResult JSON; every
    # human/diagnostic line already went to stderr above. The exit code still
    # reflects drive success/failure.
    #
    # artifacts_path mirrors the digest gate (ASK_COLLEAGUE_GRADABLE): it is only
    # meaningful when the artifact SURVIVES. A preview (run_preview passes empty
    # gradable) drives in a throwaway worktree the EXIT trap deletes, so the raw
    # path points at a dir that is gone by the time the caller reads it — drop it
    # rather than hand a machine consumer a dead path (#186 qodo finding-3). When
    # gradable, rewrite it to the preserved copy in the real repo.
    gradable = os.environ.get("ASK_COLLEAGUE_GRADABLE") == "1"
    if not gradable:
        d.pop("artifacts_path", None)
    elif ap:
        d["artifacts_path"] = ap
    json.dump(d, sys.stdout)
    sys.stdout.write("\n")
    # The task:/grade: hints are diagnostics -> stderr (stdout stays pure JSON).
    # task_id is already in the payload, but echoing the copy-paste grade hint
    # keeps the convention every work item follows (rule 907536) without breaking
    # the stdout contract. Gated on gradable, exactly like the digest below.
    # Skip the grade hint for the no-result sentinel (#192). A FAILED/incomplete but
    # gradable drive still gets the hint — a failure rated 1/5 is the ROI signal
    # (#139); the incompletion diagnostic above already says it did not succeed.
    if tid and gradable and summary != "__COLLEAGUE_NO_RESULT_PRODUCED__":
        print("task:", tid, file=sys.stderr)
        print("grade:", "ask-colleague feedback", tid, "--rating N", file=sys.stderr)
else:
    out = sys.stdout if ok else sys.stderr
    print("status:", d.get("status"), file=out)
    if tid:
        print("task:", tid, file=out)
    print(file=out)
    print((d.get("summary") or "").rstrip(), file=out)
    cf = d.get("changed_files") or []
    if cf:
        print("\nchanged files:", ", ".join(cf), file=out)
    if d.get("branch"):
        print("drive branch:", d["branch"], file=out)
    if ap and os.environ.get("ASK_COLLEAGUE_GRADABLE") == "1":
        print("artifact:", ap, file=out)
    # A drive is gradable whenever its artifact survives — including a FAILED
    # drive (colleague writes an artifact on failure too, h5): a failure rated
    # 1/5 is exactly the ROI signal, so the hint must not be gated on `ok` (#139
    # qodo). It prints to `out` (stderr on failure), matching the failure digest.
    # Skip the grade footer for the no-result sentinel (#192): a drive that
    # produced nothing is not worth grading.
    summary = d.get("summary") or ""
    if tid and os.environ.get("ASK_COLLEAGUE_GRADABLE") == "1" and summary != "__COLLEAGUE_NO_RESULT_PRODUCED__":
        print("grade:", "ask-colleague feedback", tid, "--rating N", file=out)
if ok:
    sys.exit(0)
else:
    rc = os.environ.get("ASK_COLLEAGUE_DRIVE_RC")
    if rc in ("1", "2"):
        sys.exit(int(rc))
    else:
        sys.exit(1)
'
}

# ── read-only verbs: isolate the drive in a throwaway worktree at HEAD ──────
# Worktree state is module-global, not a function local: the EXIT trap fires
# *after* run_readonly returns, so under `set -u` a local would be unbound.
_WT=""
_DRIVE_BRANCH=""

_cleanup_worktree() {
    [[ -n "$_WT" ]] || return 0
    git -C "$REPO" worktree remove --force "$_WT" >/dev/null 2>&1 || true
    rm -rf "$_WT" >/dev/null 2>&1 || true
    # Only ever delete the ephemeral drive branch colleague names
    # (colleague/<task_id>) — never an unrelated local branch, even if the
    # JSON `branch` value were unexpected.
    if [[ "$_DRIVE_BRANCH" == colleague/* ]]; then
        git -C "$REPO" branch -D "$_DRIVE_BRANCH" >/dev/null 2>&1 || true
    fi
    # Defensive: clear the handles so a re-entry is a clean no-op. The EXIT trap
    # fires once today, but this keeps cleanup idempotent against future refactors
    # (dogfood-review suggestion, #61).
    _WT=""
    _DRIVE_BRANCH=""
}

# Extract the drive branch (colleague/<id>) from a TaskResult JSON on stdin.
_extract_branch() {
    python3 -c 'import sys, json
try:
    print(json.load(sys.stdin).get("branch") or "")
except Exception:
    print("")' 2>/dev/null || true
}

# Extract the task id from a TaskResult JSON on stdin.
_extract_task_id() {
    python3 -c 'import sys, json
try:
    print(json.load(sys.stdin).get("task_id") or "")
except Exception:
    print("")' 2>/dev/null || true
}

# Extract the artifact filename (basename of artifacts_path) from a TaskResult
# JSON on stdin. The runtime names artifacts <task_id>.<slug>.json (slugged) or
# <task_id>.json (bare), so the skill must copy the file the drive actually
# reported rather than reconstruct a name. os.path.basename strips any directory
# component, so a hostile artifacts_path can never point the copy outside .colleague/.
_extract_artifact_name() {
    python3 -c 'import sys, json, os
try:
    print(os.path.basename(json.load(sys.stdin).get("artifacts_path") or ""))
except Exception:
    print("")' 2>/dev/null || true
}

# A copied filename must be a single safe path segment before it is joined into a
# copy destination (mirrors colleague/feedback.py's _validate_task_id: allow
# [A-Za-z0-9][A-Za-z0-9._-]*, reject "."/".." and any path separator). The name
# comes from colleague's own TaskResult basename, but validating it keeps the
# write strictly inside $REPO/.colleague/ even for a malformed/hostile result.
_valid_segment() {
    [[ "$1" != "." && "$1" != ".." && "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]
}

# Read-only verbs drive in a throwaway worktree that _cleanup_worktree deletes, so
# the artifact written under <worktree>/.colleague/ would vanish with it. Copy it
# back to the real repo's .colleague/ so the drive can still be graded afterwards
# by its task-id (`ask-colleague feedback <id>` / `ask-colleague feedback list`).
#
# Deliberately does NOT write a last_drive pointer (issue #132): explore/review
# are read-only probes and must not move `last`, or a later probe would steal a
# grade meant for a consequential write. `last` stays aimed at the most recent
# write; a probe is graded by its printed task-id.
#
# Writes only the gitignored .colleague/ bookkeeping dir — never the tracked tree.
# $1 is the artifact basename (<task_id>.<slug>.json or <task_id>.json) from the
# drive's reported artifacts_path. Returns non-zero when the name is unsafe or the
# copy fails, so run_readonly never reports a preserved path that isn't there.
_preserve_artifact() {
    local art_name="$1"
    [[ -n "$art_name" && -n "$_WT" ]] || return 1
    if ! _valid_segment "$art_name"; then
        printf 'error: refusing to preserve unsafe artifact name %q\n' "$art_name" >&2
        return 1
    fi
    local src="$_WT/.colleague"
    local dst="$REPO/.colleague"
    [[ -f "$src/$art_name" ]] || return 1
    mkdir -p "$dst" || return 1
    # The JSON artifact is the record of the drive — surface a copy failure rather
    # than swallow it, so the caller can fall back to honest path reporting.
    if ! cp -f "$src/$art_name" "$dst/$art_name"; then
        printf 'error: could not preserve artifact %s\n' "$art_name" >&2
        return 1
    fi
    # The trace shares the artifact stem (.json -> .trace.jsonl); a best-effort
    # copy is fine — it is optional context, not the record of the drive.
    local trace_name="${art_name%.json}.trace.jsonl"
    if [[ -f "$src/$trace_name" ]]; then
        cp -f "$src/$trace_name" "$dst/$trace_name" 2>/dev/null || true
    fi
}

# Spin up a throwaway detached worktree at HEAD (the isolation both read-only
# verbs and the write preview share). `mktemp -d` is given an explicit template:
# GNU mktemp tolerates a bare `-d`, but BSD/macOS mktemp requires one.
_add_worktree() {
    _WT="$(mktemp -d "${TMPDIR:-/tmp}/ask-colleague.XXXXXX")"
    trap _cleanup_worktree EXIT
    git -C "$REPO" worktree add -q --detach "$_WT" HEAD
}

run_readonly() {
    local instruction="$1"
    _add_worktree
    local out rc=0
    out="$("${COLLEAGUE[@]}" drive "$instruction" --repo "$_WT" --no-pr "${COMMON_FLAGS[@]}")" || rc=$?
    _DRIVE_BRANCH="$(printf '%s' "$out" | _extract_branch)"
    # Preserve the artifact to the real repo BEFORE the EXIT trap removes the
    # worktree, so the drive can be graded by its task-id (`ask-colleague feedback
    # <id>`). Only point print_result at the real repo — and mark the drive
    # gradable — when the copy actually landed; otherwise the printed `artifact:`
    # would name a file preservation never wrote, and the grade hint would point
    # at an artifact that isn't there.
    local art_name real_dir="" gradable=""
    art_name="$(printf '%s' "$out" | _extract_artifact_name)"
    if _preserve_artifact "$art_name"; then
        real_dir="$REPO/.colleague"
        gradable="1"
    fi
    printf '%s' "$out" | print_result "$real_dir" "$gradable" "$rc"
}

# ── write preview (default): drive in a throwaway worktree, show the would-be ──
# change, then discard. Nothing reaches the real working tree or branch — pass
# --apply (or --pr) to land it for real.
run_preview() {
    local instruction="$1"
    _add_worktree
    local out rc=0
    out="$("${COLLEAGUE[@]}" drive "$instruction" --repo "$_WT" --no-pr "${COMMON_FLAGS[@]}")" || rc=$?
    _DRIVE_BRANCH="$(printf '%s' "$out" | _extract_branch)"

    # Capture the would-be patch before _cleanup_worktree deletes the drive branch.
    local patch=""
    if [[ "$_DRIVE_BRANCH" == colleague/* ]]; then
        patch="$(git -C "$REPO" diff "HEAD..$_DRIVE_BRANCH" 2>/dev/null || true)"
    fi

    local prc=0
    printf '%s' "$out" | print_result "" "" "$rc" || prc=$?
    if [[ "$prc" -eq 0 ]]; then
        # In --json mode stdout is reserved for the result JSON print_result just
        # emitted, so the would-be patch is a diagnostic -> stderr (fd 2).
        local diff_fd=1
        [[ "$JSON_OUT" -eq 1 ]] && diff_fd=2
        if [[ -n "$patch" ]]; then
            printf '\n--- preview diff (NOT applied — pass --apply to land it) ---\n' >&"$diff_fd"
            printf '%s\n' "$patch" >&"$diff_fd"
        else
            printf '\n(preview: no file changes reported; NOT applied)\n' >&"$diff_fd"
        fi
    fi
    return "$prc"
}

# ── write verb: preview by default; --apply lands a drive branch; --pr opens a ─
# PR (implies apply). The dirty-tree guard only matters when applying in place —
# a preview runs in an isolated worktree and never touches the working tree.
run_write() {
    local instruction="$1"
    if [[ "$APPLY" -eq 0 && "$OPEN_PR" -eq 0 ]]; then
        run_preview "$instruction"
        return
    fi
    if [[ "$ALLOW_DIRTY" -eq 0 ]] \
        && [[ -n "$(git -C "$REPO" status --porcelain --untracked-files=no 2>/dev/null)" ]]; then
        echo "error: working tree is dirty — commit/stash first, or pass --allow-dirty" >&2
        echo "hint: 'colleague drive --no-pr' commits uncommitted edits onto the drive branch" >&2
        # User-fixable state guard -> exit 1, matching the runtime's own
        # dirty-tree guard (colleague/handoff.py _guard_clean_tree =
        # EXIT_USER_ERROR), not exit 2 (#161).
        exit 1
    fi
    # The runtime now enforces its own dirty-tree guard (colleague#149); pass
    # --allow-dirty through so an operator opt-in here isn't re-refused by the
    # CLI. Append to the always-non-empty COMMON_FLAGS (not the global one at the
    # top — read-only/preview verbs run in a clean worktree and must not get it),
    # which sidesteps the `set -u` empty-array expansion hazard.
    [[ "$ALLOW_DIRTY" -eq 1 ]] && COMMON_FLAGS+=(--allow-dirty)
    # `|| rc=$?`: a failed drive (`colleague drive` exits non-zero, printing the
    # result JSON to stdout) must still flow into print_result so the digest is
    # emitted (to stderr) and the wrapper propagates the drive's real exit code.
    # The rc is captured (declaration split from the assignment so `local` doesn't
    # mask it) rather than discarded with `|| true`, which would have collapsed the
    # tri-state rc; `set -e` does not abort at the assignment. Matches the
    # read-only / preview paths, which guard this way.
    local out rc=0
    if [[ "$OPEN_PR" -eq 1 ]]; then
        out="$("${COLLEAGUE[@]}" drive "$instruction" --repo "$REPO" "${COMMON_FLAGS[@]}")" || rc=$?
    else
        out="$("${COLLEAGUE[@]}" drive "$instruction" --repo "$REPO" --no-pr "${COMMON_FLAGS[@]}")" || rc=$?
    fi
    # A landed write persists its artifact in the real repo and moves `last`, so it
    # is gradable — print the `grade:` hint (with the explicit task-id).
    printf '%s' "$out" | print_result "" "1" "$rc"
}

# ── feedback verb: grade a finished drive (the ROI loop) ────────────────────
# A thin pass-through to `colleague feedback`: `list` lists every recorded drive
# by request + grade; with --rating it records a 1-5 grade + notes; without, it
# shows the drive's existing feedback. The ref is the drive's task-id, `last` for
# the most recent consequential drive in --repo, or the literal `list`. No
# worktree, no engine — colleague owns the store and its own stdout/stderr/exit.
run_feedback() {
    local ref="$1"
    # Build one command array (never empty) so we don't expand an empty array
    # under `set -u` — the optional --by is appended only when set.
    local cmd=("${COLLEAGUE[@]}" feedback)
    if [[ "$ref" == "list" ]]; then
        cmd+=(list)
    elif [[ -n "$RATING" ]]; then
        cmd+=(record "$ref" --rating "$RATING" --notes "$NOTES")
        [[ -n "$BY" ]] && cmd+=(--by "$BY")
    else
        cmd+=(show "$ref")
    fi
    cmd+=(--repo "$REPO")
    # colleague feedback supports --json natively; forward the operator's request
    # so stdout stays machine-readable end-to-end.
    [[ "$JSON_OUT" -eq 1 ]] && cmd+=(--json)
    "${cmd[@]}"
}

# ── clean verb: recover a repo a crashed run wedged (#162) ──────────────────
# A thin pass-through to `colleague clean`: the runtime reaps stale/corrupt
# colleague/* branches + orphaned .colleague/ artifacts, scoped strictly to
# colleague/* (so an unrelated branch is never touched) and conservative with
# .git/objects. No worktree, no engine — colleague owns the reap + its own
# stdout/stderr/exit. The full flag set (--merged / --older-than) lives on
# `colleague clean`; the skill forwards the common --dry-run.
run_clean() {
    local cmd=("${COLLEAGUE[@]}" clean --repo "$REPO")
    [[ "$DRY_RUN" -eq 1 ]] && cmd+=(--dry-run)
    # colleague clean supports --json natively; forward it for machine-readable output.
    [[ "$JSON_OUT" -eq 1 ]] && cmd+=(--json)
    "${cmd[@]}"
}

# ── front-load a filtered, capped diff into the review instruction ──────────
# Issue #220a: print a diffstat + filtered diff body so the model does not waste
# turns running `git diff` itself. Lockfile/vendored noise is excluded; the body
# is capped at ${COLLEAGUE_MAX_OUTPUT_CHARS:-100000} characters.
front_load_review_diff() {
    local cap="${COLLEAGUE_MAX_OUTPUT_CHARS:-100000}"
    printf '%s\n' "--- DIFF UNDER REVIEW (filtered + capped; read specific files for more) ---"
    git -C "$REPO" diff "$BASE"...HEAD --stat
    printf '\n'
    local diff_body
    diff_body="$(git -C "$REPO" diff "$BASE"...HEAD -- . ':(exclude)*.lock' ':(exclude)**/*.lock' ':(exclude)package-lock.json' ':(exclude)**/package-lock.json' ':(exclude)*.min.js' ':(exclude)**/*.min.js' 2>/dev/null || true)"
    if [[ "${#diff_body}" -gt "$cap" ]]; then
        printf '%s\n' "${diff_body:0:$cap}"
        printf '%s\n' "[... diff body truncated at ${cap} chars; read specific files for the rest ...]"
    else
        printf '%s\n' "$diff_body"
    fi
}

# ── piloting verbs: thin passthroughs to the `colleague flight` noun ─────────
_flight_json_flag() { [[ "$JSON_OUT" -eq 1 ]] && printf -- '--json'; }

run_monitor() {
    local fid="${ARG%% *}"
    [[ -z "$fid" ]] && { echo "error: monitor needs a flight task-id" >&2; exit 1; }
    "${COLLEAGUE[@]}" flight status "$fid" --repo "$REPO" --follow $(_flight_json_flag)
}

run_stop() {
    local fid="${ARG%% *}"
    [[ -z "$fid" ]] && { echo "error: stop needs a flight task-id" >&2; exit 1; }
    "${COLLEAGUE[@]}" flight stop "$fid" --repo "$REPO" $(_flight_json_flag)
}

run_guide() {
    local fid="${ARG%% *}"
    local msg="${ARG#* }"
    [[ -z "$fid" || "$msg" == "$fid" ]] && { echo "error: guide needs <task-id> <message>" >&2; exit 1; }
    "${COLLEAGUE[@]}" flight guide "$fid" "$msg" --repo "$REPO" $(_flight_json_flag)
}

case "$VERB" in
    explore) run_readonly "$(render_prompt explore)" ;;
    review) run_readonly "$(render_prompt review)"$'\n\n'"$(front_load_review_diff)" ;;
    write) run_write "$(render_prompt write)" ;;
    feedback) run_feedback "$ARG" ;;
    clean) run_clean ;;
    monitor) run_monitor ;;
    guide) run_guide ;;
    stop) run_stop ;;
esac
