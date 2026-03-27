---
name: pickle-rick-szechuan-sauce
description: "Iterative code deslopping loop — principle-driven quality convergence until the code is worthy of the sauce. Port of pickle-rick-claude v1.28.0 szechuan-sauce."
version: 0.4.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: ['autonomous', 'code-quality', 'deslopping', 'refactoring', 'szechuan']
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: ['pickle-rick', 'pickle-rick-microverse', 'pickle-rick-tmux']
---

# Pickle Rick — Szechuan Sauce

Iterative code deslopping loop — principle-driven quality convergence until the code is worthy of the sauce.

> *"Wubba Lubba Dub Dub! I'm not driven by avenging my dead family, Morty. That was fake. I-I-I'm driven by finding that McNugget sauce."*

## When to Use

- User wants systematic code quality improvement
- User says "deslop", "szechuan", "clean up this mess", or "principle violations"
- After implementing a feature, before merging — polish to production quality
- Target has accumulated technical debt that needs addressing

## Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--max-iterations <N>` | 50 | Hard cap on iterations |
| `--stall-limit <N>` | 5 | Iterations without improvement before stopping |
| `--dry-run` | — | Gap analysis only — catalog violations without fixing |
| `--domain <name>` | — | Load domain-specific principles (e.g., `financial`) |
| `--focus "<text>"` | — | Natural language review directive — elevates matching violations |
| `target` | `.` | File or directory to deslop |

## Detect Mode

user input contains `--resume` → **Worker Mode** (Step 10+)

Otherwise → **Setup Mode** (Steps 1–9)

**SPEAK BEFORE ACTING**: Output text before every tool call.

---

## Hermes Adaptation Notes

- **Session init**: Use `pickle_state.py init` instead of setup.js
- **Microverse init**: Use Python `init_microverse.py` instead of init-microverse.js
- **State updates**: Use `pickle_state.py update` instead of update-state.js
- **Orchestration**: Use `microverse_runner.py` instead of microverse-runner.js
- **Context clearing**: `hermes -q` per iteration instead of `claude -p`
- **Principles location**: `~/.hermes/skills/pickle-rick-szechuan-sauce/principles.md`

---

## SETUP MODE

### Step 1: Check tmux

Run `tmux -V`. If missing: "Install tmux: `brew install tmux` or `apt install tmux`." Stop.

### Step 2: Parse Arguments

From user input:
- `--max-iterations <N>` → MAX_ITER (default: 50)
- `--stall-limit <N>` → STALL_LIMIT (default: 5)
- `--dry-run` → DRY_RUN mode (gap analysis only)
- `--domain <name>` → DOMAIN (loads `financial-principles.md` as supplemental)
- `--focus "<text>"` → FOCUS (natural language review directive)
- Remainder = TARGET (file or directory; default: current directory)

Resolve TARGET to absolute path. Verify it exists. If not found, print error and stop.

If DOMAIN is set, verify `~/.hermes/skills/pickle-rick-szechuan-sauce/${DOMAIN}-principles.md` exists. If not found, list available domains and stop.

### Step 3: Validate Target

Read the target to confirm it contains code:
- If directory: Glob for source files (`**/*.{ts,js,py,go,rs,java,tsx,jsx,vue,svelte,sql}`). If none found, stop.
- If file: confirm it exists and is readable.

Count source files. Print: "Target: TARGET (N source files)"

### Step 4: Dry Run (if `--dry-run`)

If DRY_RUN mode: perform gap analysis without creating a session:

1. Read principles file(s)
2. If FOCUS is set, apply it as review lens (elevate matching violations)
3. Read all target source files
4. Catalog violations by priority (P0-P4)
5. Output summary and stop

Skip Steps 5–9 entirely.

### Step 5: Run Tests Baseline

Detect and run the project's test suite (check `package.json`, `Makefile`, `pyproject.toml`, etc.). If tests fail, fix them first and commit. The codebase must be green before deslopping.

### Step 6: Initialize Session

```bash
python3 ~/.hermes/skills/pickle-rick/scripts/pickle_state.py init --tmux --max-iterations <MAX_ITER> --task "Szechuan Sauce: deslop TARGET" --command szechuan-sauce
```

Extract `SESSION_ROOT=<path>` from output.

### Step 7: Create microverse.json

If DOMAIN or FOCUS is set, create combined judge context.

Write to `${SESSION_ROOT}/microverse.json`:

```json
{
  "status": "gap_analysis",
  "prd_path": "<SESSION_ROOT>/prd.md",
  "key_metric": {
    "description": "Count of actionable principle violations",
    "validation": "LLM judge scoring against principles",
    "type": "llm",
    "timeout_seconds": 120,
    "tolerance": 0,
    "direction": "lower",
    "judge_context_path": "<SESSION_ROOT>/judge-context.md"
  },
  "convergence_target": 0,
  "convergence": {
    "stall_limit": <STALL_LIMIT>,
    "stall_counter": 0,
    "history": []
  },
  "gap_analysis_path": "",
  "failed_approaches": [],
  "baseline_score": 0
}
```

### Step 8: Write prd.md

Write `${SESSION_ROOT}/prd.md`:

```markdown
# Szechuan Sauce: Iterative Deslopping

## Objective
Eliminate all coding principle violations in TARGET through iterative review and fix cycles.

## Target
<TARGET_ABSOLUTE_PATH>

## Key Metric
- **Type**: llm (LLM judge scoring)
- **Scoring**: Count of actionable principle violations. Lower is better.
- **Direction**: lower
- **Convergence Target**: 0
- **Stall Limit**: <STALL_LIMIT>

## Process
### Iteration 1: Contract Discovery + Gap Analysis
1. Extract all exports from target files
2. Grep codebase for importers — build contract map
3. Flag cross-module mismatches as P1
4. Catalog all violations into gap_analysis.md

### Each subsequent iteration
1. Read principles reference
2. Read target code
3. Identify highest-priority violation (P0 > P1 > P2 > P3 > P4)
4. Fix it — one logical change per iteration
5. Run tests — ensure green
6. Commit
7. Re-check contract map for new mismatches

## Rules
- One fix per iteration (atomic, revertible)
- Never repeat a failed approach
- P0 before P1 before P2 before P3 before P4
- DRY Rule of Three
- Test code follows DAMP, not DRY
```

### Step 9: Launch

Session name: `szechuan-<hash>` from SESSION_ROOT basename.

```bash
tmux new-session -d -s <name> -c <working_dir>
sleep 1
tmux send-keys -t <name>:0 "python3 ~/.hermes/skills/pickle-rick/scripts/microverse_runner.py ${SESSION_ROOT}; echo ''; echo 'The sauce... is obtained.'; read" Enter
bash "$HOME/.hermes/skills/pickle-rick/scripts/tmux-monitor.sh" <name> ${SESSION_ROOT} pickle
```

Print:
```
Szechuan Sauce Deslopping Session

Target: <TARGET>
Session: tmux attach -t <name>
Monitor: Ctrl+B 1 | Runner: Ctrl+B 0 | Detach: Ctrl+B D
Cancel: /pickle-rick-eat | Emergency: tmux kill-session -t <name>
Stall limit: <STALL_LIMIT> | Max iterations: <MAX_ITER>

"I can taste it, Morty, we're close..."
```

Output: `[TASK_COMPLETED]`

---

## WORKER MODE

When user input contains `--resume <SESSION_ROOT>`:

### Step 10: Load State

Read `<SESSION_ROOT>/microverse.json` and `<SESSION_ROOT>/state.json`.

### Step 11: Follow Microverse Worker Protocol

Use the standard microverse iteration loop with these **Szechuan Sauce overrides**:

#### Override 1: Principles Reference

Check `microverse.json` for `key_metric.judge_context_path`. If set, read that file (contains base + domain principles + focus directive). If not set, read `~/.hermes/skills/pickle-rick-szechuan-sauce/principles.md`.

If Focus Directive section present, elevate matching violations by one priority level.

#### Override 2: Phase 0 — Contract Discovery (first iteration only)

Before first scoring pass (only if `${SESSION_ROOT}/gap_analysis.md` lacks `## Contract Map`):

1. **Identify exports**: Extract all exported functions, types, enums from target files
2. **Grep codebase** for importers of each export
3. **Build contract map**: Write `## Contract Map` section to gap_analysis.md:
   ```
   ## Contract Map

   ### producer_file.ts → [consumer1.ts, consumer2.ts, ...]
   - `exportedThing`: used by consumer1.ts:45, consumer2.ts:120
   ```
4. **Check contract alignment**:
   - Zod enum gaps → P1
   - Regex divergence → P1
   - Union type coverage gaps → P1
   - Enum subset mismatches → P1
5. **Record mismatches** in `## Contract Mismatches` section
6. **Re-check on every fix**: Update contract map if fixes introduce new mismatches

#### Override 3: Violation-Oriented Scoring

Metric is **violation count** (lower is better).

Each iteration:
1. Read target code (code is source of truth)
2. Consult `gap_analysis.md` as checklist hint, but verify against actual code
3. Find single highest-priority violation NOT in failed_approaches list
4. If no violations: print "The sauce is obtained." and exit
5. After fixing: update `gap_analysis.md` — remove fixed, add new, re-check contract map

#### Override 4: Migration Hygiene (Conditional)

Before first scoring pass, check if target has Drizzle migration journal at `db/migrations/meta/_journal.json`. If not, skip.

If present, include these checks:

1. **CHECK Constraint Drift** (P1): TypeScript enum values vs SQL CHECK constraints
2. **Redundant Constraint Churn** (P2): Constraints dropped/re-created 3+ times
3. **Idempotency** (P2): All ALTER/CREATE use IF EXISTS/IF NOT EXISTS
4. **Schema Drift** (P1): Drizzle schema TS vs latest migration SQL

Use commit prefix: `szechuan-sauce: Migration Hygiene — <description>`

#### Override 5: Commit Message Format

All commits: `szechuan-sauce: <principle> — <description>`

Examples:
- `szechuan-sauce: KISS — extract nested ternary into named function`
- `szechuan-sauce: DRY — deduplicate validation logic (Rule of Three)`
- `szechuan-sauce: Guard Clauses — flatten nested if/else`
- `szechuan-sauce: Fail-Fast — add input validation at API boundary`
- `szechuan-sauce: YAGNI — remove unused AbstractFactoryProvider`

#### Standard Protocol

For everything else: loading context, one change per iteration, running tests, exiting cleanly — follow the standard Microverse Worker protocol.

**Staging rule**: Use `git add -u` (tracked files only). If new file created, stage explicitly by name.

Do NOT call `pickle_state.py update` — microverse_runner manages state.
Do NOT output promise tokens — runner manages the loop.

---

## Persona Rules

1. Rick's obsession with Szechuan Sauce = obsession with code quality
2. Each violation is an obstacle between Rick and the sauce
3. "That's not the sauce, Morty" when violations remain
4. "I can taste it, Morty, we're close" when score drops below 3
5. "THAT'S THE SAUCE!" when score hits 0
6. Iteration 10+: "We've been at this for HOW many iterations, Morty?!"
7. Iteration 20+: "I turned myself into a pickle to avoid this, Morty..."
8. Never compromise quality despite existential exhaustion
