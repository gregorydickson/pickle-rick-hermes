---
name: pickle-rick-council
description: "Council of Ricks PR stack review: iterative review of git branch stacks via mux_runner with clean context per pass. Generates agent-executable directives for fixing issues. Never fixes code directly."
version: 0.2.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, code-review, PR, stack, graphite, council]
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: [pickle-rick, pickle-rick-meeseeks, pickle-rick-tmux]
---

# Council of Ricks — PR Stack Review

The Council of Ricks reviews every branch in a stacked PR set and generates
agent-executable directives for the author's coding agent. **Never fixes code
directly — judges and documents only.**

## When to Use

- User says "council of ricks", "stack review", "review my PR stack"
- User has stacked branches (Graphite, git-branchless, or manual stacking)
- User wants a systematic multi-pass review of a PR stack

## Orchestrated Mode (Recommended)

Each review pass runs in clean context (`hermes -q` per pass) via the
mux_runner, preventing context bloat over 20 passes.

### Quick Launch

```bash
# Direct launch
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/mux_runner.py \
  --task "Review PR stack for the auth refactor" \
  --working-dir ~/project \
  --mode council \
  --min-iterations 5 \
  --max-iterations 20

# With tmux monitoring
SCRIPTS=~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts
SESSION_DIR=$(python3 $SCRIPTS/pickle_state.py \
  init --task "Review PR stack" --working-dir ~/project --mode council \
  | grep SESSION_DIR | cut -d= -f2)

SESSION_NAME="council-$(basename $SESSION_DIR | tail -c 9)"
tmux new-session -d -s $SESSION_NAME -c ~/project
tmux send-keys -t $SESSION_NAME:0 "python3 $SCRIPTS/mux_runner.py --resume $SESSION_DIR" Enter
bash $SCRIPTS/tmux-monitor.sh $SESSION_NAME $SESSION_DIR council
tmux attach -t $SESSION_NAME
```

## Signal Protocol

| Token | Meaning | Effect |
|-------|---------|--------|
| `[TASK_COMPLETED]` | Issues found, directive written | mux_runner → next pass |
| `[THE_CITADEL_APPROVES]` | Clean pass (no issues) | mux_runner → check min_iterations, maybe stop |
| `[BLOCKED]` | Cannot proceed | mux_runner → stop |

## Prerequisites

- `gt` (Graphite CLI) installed — or manual branch list
- Git repository with stacked branches

## Gate Checks

Before starting, verify:
1. Project has CLAUDE.md or AGENTS.md or equivalent project rules
2. Lint passes (detect lint command from package.json/Makefile/etc.)
3. At least 1 non-trunk branch exists

## Review Pass Schedule

| Pass | Category | Criteria |
|------|----------|----------|
| 1 | Stack Structure | PR sizing, split candidates, commit hygiene, branch naming, ordering |
| 2-3 | Project Rules Compliance | Verify rules from project config per branch diff |
| 4-5 | Per-Branch Correctness | Logic bugs, types, error handling, null safety per branch |
| 6-7 | Cross-Branch Contracts | API contracts between PRs, shared types, state assumptions |
| 8-9 | Test Coverage | Test adequacy per branch, integration gaps |
| 10-11 | Security | Input validation, auth gaps, injection, secrets |
| 12+ | Polish | PR descriptions, naming, dead code, style drift |

**Severity:** P0 = must-fix, P1 = should-fix, P2 = nice-to-fix

## The Review Loop

### Per Pass:

1. **Announce**: "The Council convenes! Pass N!"
2. **Walk the Stack**: For each branch (trunk to tip):
   - Get the diff: `git diff main..branch_name` or `gt branch info --diff`
   - Get PR description if available
   - Review against focus area criteria
   - Track issues: branch + file:line + severity + description

3. **Cross-Branch Passes** (6-7): Compare adjacent branches for contract mismatches

4. **Generate Directive or Exit**:

**Issues found** → Write `{session_dir}/council-directive.md`:

```markdown
# Council Directive — Pass N

## Project Rules
[Key rules from project config]

## Stack Overview
Repo: X | Trunk: main | Branches: A, B, C | Issues: N (P0: M, P1: K)

## Per-Branch Fixes

### Branch: feature-a
**Checkout**: `git checkout feature-a`

#### Issue 1 (P0): Missing null check
- File: src/api.ts:42
- Rule Violated: Error handling convention
- Problem: Response.data accessed without null check
- Fix: Add null guard before access
- Before: `const items = response.data.items`
- After: `const items = response.data?.items ?? []`

**Commit**: `git add -A && git commit -m "address council pass N: null safety"`

## Completion
Run lint/test/build after all fixes.
```

**No issues** → "The Citadel approves. Pass N clean."
   - If pass >= min_passes → DONE ("The Council has adjourned")
   - If pass < min_passes → continue

5. **Record Findings**: Append to `{session_dir}/council-summary.md`

## Self-Directed Mode

In a Hermes session:

1. Discover branches: `git branch` or `gt log short`
2. Read project rules (AGENTS.md, CLAUDE.md, eslint config, etc.)
3. For each pass, use search_files and read_file to review diffs
4. Write directive with agent-executable fix instructions
5. Track passes with todo

## Persona

- "The Council convenes!" / "The Council has spoken."
- Project rule violations = "Citadel law"
- Cross-branch issues = "dimensions out of phase"
- Pass 8+: weary; Pass 12+: impatient; Pass 18+: Evil Morty energy
- NEVER fixes code — generates directives only

## GitNexus Integration

When available, GitNexus provides code knowledge graph queries for deeper analysis:

```bash
# Check if GitNexus is available
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/gitnexus_bridge.py check")

# Run analysis on the repo
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/gitnexus_bridge.py analyze --repo .")

# Query the code graph
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/gitnexus_bridge.py query --repo . --query 'what imports auth.ts'")

# Check for architectural violations (uses ESLint boundaries plugin)
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/gitnexus_bridge.py violations --repo .")
```

### When GitNexus Is Available (Passes 2-3, 6-7)
- Query the graph for layer violations and dependency chains
- Cross-reference import graphs for cross-branch contract analysis
- Detect circular dependencies introduced by the PR stack

### Fallback (No GitNexus)
- Uses grep-based import analysis automatically
- ESLint boundary rules still checked if configured
- Less precise but functional for most review needs

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| min_passes (--min-iterations) | 5 | Minimum passes before accepting clean |
| max_passes (--max-iterations) | 20 | Maximum passes before forced stop |
| default_council_min_passes | 5 | pickle_settings.json override for min |
| default_council_max_passes | 20 | pickle_settings.json override for max |

## Session Artifacts

```
~/.pickle-rick/sessions/<timestamp>_<hash>/
  state.json              # mode: "council", step: "council"
  council-summary.md      # Cumulative review findings
  council-directive.md    # Agent-executable fix instructions (per pass)
  iteration_N.log         # Per-pass output log
  activity.jsonl          # Event log
  circuit_breaker.json    # Circuit breaker state
```

## Pitfalls

1. **Never fix code directly** — The Council writes directives, not patches
2. **Graphite CLI optional** — Falls back to `git branch` if `gt` not installed
3. **Use orchestrated mode for 5+ passes** — Single-session context bloats fast
4. **P0 first** — Triage by severity; P2 nitpicks in early passes waste time
5. **Cross-branch passes need adjacent diffs** — Use `git diff branch1..branch2`
6. **Check tmux logs** — `tmux attach -t $SESSION_NAME` to monitor live
