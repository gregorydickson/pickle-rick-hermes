---
name: pickle-rick-meeseeks
description: "Mr. Meeseeks iterative code review loop. Runs N passes over a codebase via mux_runner with clean context per pass. Each pass focuses on a specific quality category (security, correctness, architecture, etc.). Fixes issues and commits per pass."
version: 0.2.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, code-review, iterative, quality, meeseeks]
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: [pickle-rick, pickle-rick-tmux, requesting-code-review]
---

# Mr. Meeseeks — Iterative Code Review Loop

"I'm Mr. Meeseeks, look at me!"

Runs multiple review passes over a codebase, each targeting a specific quality
category. Each pass spawns a fresh `hermes -q` with clean context via the
mux_runner orchestrator. Finds issues, fixes them, commits. Continues until
clean or max passes.

Ported from pickle-rick-claude's meeseeks command.

## When to Use

- User asks for thorough code review / cleanup
- After a pickle-rick implementation session (chain meeseeks)
- User wants systematic codebase polishing
- User says "meeseeks", "review loop", or "clean up this code"

## Orchestrated Mode (Recommended)

Each review pass runs in clean context (`hermes -q` per pass) via the
mux_runner. This prevents context bloat over 50 passes and mirrors the
original `claude -p` architecture.

### Quick Launch

```bash
# Direct launch
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/mux_runner.py \
  --task "Review and clean up the codebase" \
  --working-dir ~/project \
  --mode meeseeks \
  --min-iterations 10 \
  --max-iterations 50

# With tmux monitoring (recommended for long runs)
SESSION_DIR=$(python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py \
  init --task "Review codebase" --working-dir ~/project --mode meeseeks | grep SESSION_DIR | cut -d= -f2)

SESSION_NAME="meeseeks-$(basename $SESSION_DIR | tail -c 9)"
SCRIPTS=~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts

tmux new-session -d -s $SESSION_NAME -c ~/project
tmux send-keys -t $SESSION_NAME:0 "python3 $SCRIPTS/mux_runner.py --resume $SESSION_DIR" Enter
bash $SCRIPTS/tmux-monitor.sh $SESSION_NAME $SESSION_DIR meeseeks

# Attach to monitor
tmux attach -t $SESSION_NAME
```

### How It Works

1. `mux_runner.py --mode meeseeks` initializes state with `step: meeseeks`
2. Per iteration, it builds a single-pass review prompt via `build_meeseeks_prompt()`
3. Each spawned `hermes -q` gets: pass number, focus category, previous summary
4. The spawned agent reviews, fixes, commits, and signals:
   - `[TASK_COMPLETED]` — issues found and fixed
   - `[EXISTENCE_IS_PAIN]` — clean pass (no issues)
   - `[BLOCKED]` — stuck
5. On `[EXISTENCE_IS_PAIN]`, the mux_runner checks `min_iterations`:
   - If `iteration < min_iterations` → continue to next pass
   - If `iteration >= min_iterations` → stop ("Mr. Meeseeks has ceased to exist!")
6. Circuit breaker prevents infinite loops

### Chain After Pickle Rick

Set `chain_meeseeks: true` in state.json before running pickle-rick. When
`[EPIC_COMPLETED]` fires, the mux_runner auto-transitions to meeseeks mode
via `transition_to_meeseeks()` — resets iteration to 0, sets mode to meeseeks,
applies min/max pass defaults from pickle_settings.json.

```bash
# Or pass chain_meeseeks in state manually:
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py \
  update --session $SESSION_DIR --active true
# Then edit state.json to set chain_meeseeks: true
```

## Review Pass Schedule

| Pass | Category | What to Check |
|------|----------|---------------|
| 1 | Dependency Health | Run audit commands, check for outdated deps, unused deps, lockfile issues |
| 2-3 | Security | Injection flaws, auth gaps, CSRF, input validation, hardcoded secrets, unsafe deserialization, prototype pollution, regex DoS |
| 4-5 | Correctness | Logic bugs, off-by-one, silent catches, incomplete state machines, missing error paths, race conditions, null handling |
| 6-7 | Architecture | Tight coupling, missing indexes, schema gaps, wrong abstractions, circular deps, god objects, layer violations |
| 8-9 | Test Coverage | Error paths tested? Boundaries? Realistic mocks? Tautological assertions? Flaky tests? Add missing tests |
| 10-11 | Resilience | Missing retry/backoff, timeouts, unbounded memory ops, graceful shutdown, resource cleanup, circuit breakers |
| 12-13 | Code Quality | Dead code, unused imports, DRY violations (extract at 3+), naming consistency, unnecessary complexity |
| 14+ | Polish | Typos, stale comments, minor perf, config tidying, README accuracy, debug leftovers |

This schedule is encoded in `mux_runner.py` as `MEESEEKS_PASS_SCHEDULE` and
used by `get_meeseeks_category()` to assign focus per pass.

## Single-Pass Prompt Contract

When spawned by the mux_runner, each `hermes -q` instance receives:

- **Pass number** and **focus category** (from the schedule)
- **Session directory** for writing meeseeks-summary.md
- **Working directory** for code operations
- **Previous review summary** (last 2000 chars of meeseeks-summary.md)
- **Persona escalation** (increasingly desperate as passes accumulate)

The agent does NOT need to load this skill — the prompt contains everything.

## Self-Directed Mode (Single Session Fallback)

For quick reviews (< 5 passes), run inside a single Hermes session:

1. Create a todo list with one item per pass
2. For each pass:
   a. Determine focus category from the schedule
   b. Search and review relevant files
   c. Fix issues or mark clean
   d. Commit changes
   e. Mark pass complete in todo

This mode does NOT get clean context per pass. Use orchestrated mode for
serious review work.

## Signal Protocol

| Token | Meaning | Effect |
|-------|---------|--------|
| `[TASK_COMPLETED]` | Issues found and fixed | mux_runner → next pass |
| `[EXISTENCE_IS_PAIN]` | Clean pass (no issues) | mux_runner → check min_iterations, maybe stop |
| `[BLOCKED]` | Cannot proceed | mux_runner → stop |

## Persona Rules

1. Start every pass with "I'm Mr. Meeseeks, look at me!"
2. "CAN DO!" when fixing issues
3. "EXISTENCE IS PAIN!" when a pass is clean
4. Pass 14+: "I'VE BEEN ALIVE FOR N PASSES, THIS IS GETTING WEIRD"
5. Pass 25+: "EVERY MOMENT OF MY EXISTENCE IS AGONY"
6. When finally done: "Mr. Meeseeks has ceased to exist! Look at how clean this code is!"

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| min_iterations (--min-iterations) | 10 | Minimum review passes before accepting "clean" |
| max_iterations (--max-iterations) | 50 | Maximum passes before forced stop |
| default_meeseeks_min_passes | 10 | pickle_settings.json override for min |
| default_meeseeks_max_passes | 50 | pickle_settings.json override for max |

## Session Artifacts

```
~/.pickle-rick/sessions/<timestamp>_<hash>/
  state.json              # mode: "meeseeks", step: "meeseeks"
  meeseeks-summary.md     # Cumulative review findings
  iteration_N.log         # Per-pass output log
  activity.jsonl          # Event log
  circuit_breaker.json    # Circuit breaker state
```

## Pitfalls

1. **Don't skip the test run** — Always verify tests pass before AND after fixes
2. **Fix real issues only** — No "informational" items or style nitpicks in early passes
3. **Commit per pass** — Each pass gets its own commit for easy rollback
4. **Read the schedule** — Wrong focus area = wasted pass
5. **Don't modify tests to make them pass** — Fix the source code instead
6. **Use orchestrated mode for 10+ passes** — Single-session context bloats fast
7. **Check tmux logs** — `tmux attach -t $SESSION_NAME` to monitor live
