---
name: pickle-rick-microverse
description: "Convergence optimization loop: optimize a metric through targeted, incremental changes. Measures, accepts improvements, auto-reverts regressions. Supports command-based and LLM-judged metrics."
version: 0.1.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, optimization, convergence, metrics, microverse]
    homepage: https://github.com/ATheorical/pickle-rick-claude
    related_skills: [pickle-rick, pickle-rick-meeseeks]
---

# Microverse — Convergence Optimization Loop

Optimize a numeric metric through targeted, incremental changes. Each iteration:
make one change, measure the metric, accept if improved, revert if regressed.
Converges when no improvement is found for N consecutive iterations.

## When to Use

- User wants to optimize a measurable metric (test coverage, performance, bundle size, etc.)
- User says "microverse", "optimize", "converge", or "improve this metric"
- User provides a metric command and a task description

## Quick Start

```
> Run microverse: optimize test coverage. Metric: pytest --cov=src --cov-report=term | tail -1
```

Or with the orchestrator:
```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/microverse_runner.py \
  --metric "pytest --cov=src --cov-report=term | tail -1" \
  --task "Improve test coverage to 90%+" \
  --working-dir ~/project \
  --direction higher \
  --stall-limit 5
```

## Metric Types

### Command-Based (--metric)
A shell command whose last stdout line is a numeric score.
```
--metric "npm run test:coverage 2>&1 | grep 'All files' | awk '{print $10}'"
--metric "pytest --tb=no -q 2>&1 | tail -1 | grep -oP '\d+'"
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
| direction | higher | Whether higher or lower scores are better |
| tolerance | 0 | Score delta within which changes count as "held" |
| stall_limit | 5 | Non-improving iterations before convergence |
| max_iterations | 500 | Hard cap on total iterations |

## The Convergence Loop

### Phase 1: Gap Analysis (Iteration 0)

First iteration — understand the codebase and metric:

1. Read the PRD/task description
2. Run the metric to get baseline score
3. Analyze the codebase with search_files and read_file
4. Write gap analysis to {session_dir}/gap_analysis.md
5. Make initial improvements if obvious quick wins exist
6. Commit: `git add -A && git commit -m "microverse: gap analysis"`
7. Measure metric again, record as baseline

### Phase 2: Optimization Loop

Repeat until converged or max iterations:

1. Read microverse.json for current state
2. Record pre-iteration git SHA
3. Plan ONE targeted change:
   - Check failed_approaches — never repeat what was reverted
   - Review recent history for trends
   - Pick a focused, atomic improvement
4. Implement the change
5. Commit: `git add -A && git commit -m "microverse: <description>"`
6. Measure the metric
7. Compare to previous score (direction-aware):

   **direction=higher:**
   - score > previous + tolerance → IMPROVED (accept, reset stall counter)
   - within tolerance → HELD (accept, increment stall counter)
   - score < previous - tolerance → REGRESSED (revert to pre-SHA, add to failed_approaches)

   **direction=lower:**
   - score < previous - tolerance → IMPROVED (accept, reset stall counter)
   - within tolerance → HELD (accept, increment stall counter)
   - score > previous + tolerance → REGRESSED (revert to pre-SHA, add to failed_approaches)

8. Update microverse.json with history entry
9. If stall_counter >= stall_limit → CONVERGED, stop
10. If iteration >= max_iterations → STOPPED, stop

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

## Self-Directed Mode (In-Session)

When running in a single Hermes session without the orchestrator:

1. Initialize session and microverse.json
2. Run gap analysis
3. Enter a loop using todo tracking:
   - For each iteration, plan one change, implement, measure, accept/revert
   - Update microverse.json after each iteration
   - Stop when converged

## Rules

1. **One change per iteration** — atomic, revertible
2. **Never repeat failed approaches** — always check failed_approaches
3. **Always commit before measuring** — uncommitted changes are invisible
4. **Don't run the metric in the worker** — the orchestrator handles measurement
5. **microverse.json is source of truth** — update after every state change
6. **Direction matters** — higher isn't always better (latency, bundle size, etc.)
