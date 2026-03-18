---
name: pickle-rick-microverse
description: "Convergence optimization loop: optimize a metric through targeted, incremental changes. Each iteration spawns a fresh hermes -q, measures the metric between spawns, accepts improvements, auto-reverts regressions. Supports command-based and LLM-judged metrics."
version: 0.2.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, optimization, convergence, metrics, microverse]
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: [pickle-rick, pickle-rick-meeseeks, pickle-rick-tmux]
---

# Microverse — Convergence Optimization Loop

> *"I put a universe inside a box, Morty, and it powers my car battery."*

Optimize a numeric metric through targeted, incremental changes. Each iteration
spawns a fresh `hermes -q` with clean context, then the orchestrator measures
the metric, compares scores, and auto-reverts regressions. Converges when no
improvement is found for N consecutive iterations.

## When to Use

- User wants to optimize a measurable metric (test coverage, performance, bundle size, etc.)
- User says "microverse", "optimize", "converge", or "improve this metric"
- User provides a metric command and a task description

## Architecture

Unlike meeseeks (which uses mux_runner.py), microverse has its **own dedicated
orchestrator** — `microverse_runner.py`. This is because the orchestrator must
measure metrics and do git reverts BETWEEN spawned hermes processes, which
doesn't fit the generic signal-based mux_runner pattern.

```
┌──────────────────────────────────────┐
│  microverse_runner.py (orchestrator) │  Python loop
│  - Measures metric between iterations│
│  - Compares scores (direction-aware) │
│  - Auto-reverts regressions via git  │
│  - Tracks failed approaches          │
│  - Manages stall counter / convergence│
└──────────────┬───────────────────────┘
               │ spawns per iteration
┌──────────────▼───────────────────────┐
│  hermes -q (worker)                  │  Fresh context each time
│  - Reads microverse.json handoff     │
│  - Makes ONE targeted change         │
│  - Commits                           │
│  - Signals [TASK_COMPLETED]          │
│  - Does NOT measure the metric       │
└──────────────────────────────────────┘
```

## Quick Start

### CLI Orchestrator (recommended)

```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/microverse_runner.py \
  --metric "pytest --cov=src --cov-report=term | tail -1" \
  --task "Improve test coverage to 90%+" \
  --working-dir ~/project \
  --direction higher \
  --stall-limit 5
```

### With tmux Monitoring (recommended for long runs)

```bash
SCRIPTS=~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts

# Initialize session
SESSION_DIR=$(python3 $SCRIPTS/pickle_state.py \
  init --task "Improve test coverage" --working-dir ~/project --mode microverse \
  | grep SESSION_DIR | cut -d= -f2)

SESSION_NAME="microverse-$(basename $SESSION_DIR | tail -c 9)"

# Create tmux session with runner in window 0
tmux new-session -d -s $SESSION_NAME -c ~/project
tmux send-keys -t $SESSION_NAME:0 \
  "python3 $SCRIPTS/microverse_runner.py \
    --resume $SESSION_DIR \
    --metric 'pytest --cov=src | tail -1' \
    --direction higher --stall-limit 5" Enter

# Launch 4-pane monitor dashboard in window 1
bash $SCRIPTS/tmux-monitor.sh $SESSION_NAME $SESSION_DIR microverse

# Attach
tmux attach -t $SESSION_NAME
```

The microverse monitor layout shows convergence history in pane 3 —
live-updating score, stall counter, and recent accept/revert actions.

### In a Hermes Session (single-context fallback)

```
> Run microverse: optimize test coverage. Metric: pytest --cov=src --cov-report=term | tail -1
```

Note: single-session mode does NOT get clean context per iteration.
Use the orchestrator for serious optimization work.

## Metric Types

### Command-Based (--metric)
A shell command whose last stdout line is a numeric score.
```
--metric "npm run test:coverage 2>&1 | grep 'All files' | awk '{print $10}'"
--metric "pytest --tb=no -q 2>&1 | tail -1 | grep -oP '\\d+'"
--metric "npx lighthouse http://localhost:3000 --output=json | jq '.categories.performance.score'"
```

### LLM-Judged (--goal)
Natural language goal scored by an LLM judge (0-100).
```
--goal "Code readability and documentation quality"
--goal "API error handling completeness"
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| --direction | higher | Whether higher or lower scores are better |
| --tolerance | 0 | Score delta within which changes count as "held" |
| --stall-limit | 5 | Non-improving iterations before convergence |
| --max-iterations | 500 | Hard cap on total iterations |
| --timeout | 1200 | Per-iteration worker timeout (seconds) |
| --resume | — | Resume existing session directory |

## The Convergence Loop

### Phase 1: Gap Analysis (Iteration 0)

First iteration — understand the codebase and metric:

1. Orchestrator measures baseline score
2. Worker reads PRD/task, analyzes codebase, writes gap_analysis.md
3. Worker makes initial improvements if obvious quick wins exist
4. Worker commits: `git add -A && git commit -m "microverse: gap analysis"`
5. Orchestrator measures again, records as baseline

### Phase 2: Optimization Loop

Repeat until converged or max iterations:

1. Orchestrator records pre-iteration git SHA
2. Spawns a fresh `hermes -q` worker with handoff context:
   - Current metric state, recent history, failed approaches
   - Worker makes ONE targeted change, commits
   - Worker does NOT run the metric — orchestrator handles that
3. Orchestrator measures the metric
4. Compares to previous score (direction-aware):

   **direction=higher:**
   - score > previous + tolerance → IMPROVED (accept, reset stall counter)
   - within tolerance → HELD (accept, increment stall counter)
   - score < previous - tolerance → REGRESSED (revert to pre-SHA, add to failed_approaches)

   **direction=lower:**
   - score < previous - tolerance → IMPROVED (accept, reset stall counter)
   - within tolerance → HELD (accept, increment stall counter)
   - score > previous + tolerance → REGRESSED (revert to pre-SHA, add to failed_approaches)

5. Updates microverse.json with history entry
6. If stall_counter >= stall_limit → CONVERGED, stop
7. If iteration >= max_iterations → STOPPED, stop

### Phase 3: Finalize

Report: total iterations, baseline score, best score, exit reason,
accepted/reverted counts.

## microverse.json Schema

```json
{
  "status": "gap_analysis|iterating|converged|stopped",
  "prd_path": "path/to/prd.md",
  "key_metric": {
    "description": "what we're optimizing",
    "validation": "metric command or goal text",
    "type": "command|llm",
    "timeout_seconds": 60,
    "tolerance": 0,
    "direction": "higher|lower"
  },
  "convergence": {
    "stall_limit": 5,
    "stall_counter": 0,
    "history": [
      {
        "iteration": 1,
        "metric_value": "85.2%",
        "score": 85.2,
        "action": "accept|revert",
        "description": "what was changed",
        "pre_iteration_sha": "abc123",
        "timestamp": "2026-03-17T12:00:00Z"
      }
    ]
  },
  "gap_analysis_path": "path/to/gap_analysis.md",
  "failed_approaches": ["approach that was reverted"],
  "baseline_score": 72.5,
  "exit_reason": null
}
```

## Session Artifacts

```
~/.pickle-rick/sessions/<timestamp>_<hash>/
  state.json              # Session state
  microverse.json         # Convergence state, metric history
  prd.md                  # Optimization PRD
  gap_analysis.md         # Initial codebase analysis
  microverse_iter_N.log   # Per-iteration worker output
  activity.jsonl          # Event log
```

## Signal Protocol

| Token | Meaning | Effect |
|-------|---------|--------|
| `[TASK_COMPLETED]` | Worker finished one change | Orchestrator measures metric |
| `[BLOCKED]` | Worker cannot make progress | Orchestrator stops |

## Rules

1. **One change per iteration** — atomic, revertible
2. **Never repeat failed approaches** — always check failed_approaches list
3. **Always commit before returning** — uncommitted changes are invisible to metric
4. **Don't run the metric in the worker** — the orchestrator handles measurement
5. **microverse.json is source of truth** — orchestrator updates after every iteration
6. **Direction matters** — higher isn't always better (latency, bundle size, etc.)

## Pitfalls

1. **Metric command must output a number on the last line** — parse errors → score 0.0
2. **Don't skip the commit** — git reset --hard reverts uncommitted AND committed work to pre-SHA
3. **Stall limit too low = premature convergence** — use 5+ for serious optimization
4. **LLM judge mode is not yet implemented** — use command metrics for now
5. **Use tmux for long runs** — `tmux attach -t $SESSION_NAME` to monitor live
6. **Worker doesn't measure** — if the worker runs the metric, the orchestrator re-measures anyway
