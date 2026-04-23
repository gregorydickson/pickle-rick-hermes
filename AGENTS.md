# Pickle Rick for Hermes Agent

PRD → Breakdown → Research → Plan → Implement → Verify → Review → Simplify.

## Documentation Rule

When adding, removing, or modifying skills (`skills/*/SKILL.md`) or scripts (`skills/pickle-rick/scripts/*.py`), update `README.md`. Docs drift = bugs.

## Source of Truth

Canonical → Deployed (`bash install.sh` copies to `~/.hermes/skills/`):
`skills/*/SKILL.md` → `~/.hermes/skills/autonomous-ai-agents/*/SKILL.md` | `skills/pickle-rick/scripts/*.py` → `~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/*.py` | `pickle_settings.json` → `~/.pickle-rick/pickle_settings.json` | `persona.md` → `~/.hermes/SOUL.md`

NEVER edit deployed files. Edit source, run `bash install.sh`.

## Build & Test

```bash
python3 -m pytest tests/ -v
```

Tests: `tests/test_*.py` via pytest. 480+ tests covering all 15 scripts + 22 skills.

## Required Patterns

State management: always use `pickle_state.py` (file locking via fcntl)
Atomic writes: `tmp + os.rename` with try/except fallback
Error handling: `except (json.JSONDecodeError, OSError) as e:`
Subprocess: always include `timeout=` parameter
Session path: `~/.pickle-rick/sessions/` (never `.claude`)
Skills path: `~/.hermes/skills/autonomous-ai-agents/pickle-rick/`

## Versioning

Semver `<Major>.<Minor>.<Patch>`:
**Major** = breaking (state schema, CLI args, signal protocol) | **Minor** = features (skills, scripts, flags) | **Patch** = fixes, refactors
Bump → commit `chore: bump version to X.Y.Z` → tag
Before tagging: `python3 -m pytest tests/ -q` must pass clean.

## Architecture

| Script | Role |
|--------|------|
| pickle_state.py | Session init (state.json, ticket dirs), CRUD, file locking |
| circuit_breaker.py | 3-state circuit breaker (CLOSED/HALF_OPEN/OPEN), reads settings |
| mux_runner.py | Context-clearing outer loop — spawns `hermes -q` per iteration |
| microverse_runner.py | Metric convergence loop: measure, compare, rollback, stall |
| init_microverse.py | Microverse session initialization |
| pickle_jar.py | Batch queue runner (add/list/run/remove) |
| pickle_utils.py | Status, cancel, standup, metrics, retry utilities |
| monitor.py | Live terminal dashboard (Matrix-styled, 2s refresh) |
| pipeline_runner.py | Pipeline execution with phase logging |
| pattern_library.py | Persistent pattern cache for portal-gun (save/search/get) |
| gitnexus_bridge.py | Code graph queries with grep fallback |
| tmux-monitor.sh | 4-pane tmux layout launcher |

| Skill | Role |
|-------|------|
| pickle-rick | Core autonomous loop — manager delegates to morty workers |
| pickle-rick-prd | Interactive PRD drafter with user interview |
| pickle-rick-refine-prd | 3 parallel analysts refine PRD + decompose tickets |
| pickle-rick-meeseeks | Iterative code review (10-50 passes, 7 categories) |
| pickle-rick-meeseeks-zellij | Meeseeks in Zellij layout |
| pickle-rick-microverse | Metric convergence optimization |
| pickle-rick-portal-gun | Pattern transplantation + persistent library |
| pickle-rick-council | PR stack review → agent-executable directives |
| pickle-rick-jar | Batch job queue |
| pickle-rick-morty | Worker lifecycle (research→plan→implement→verify→review→simplify) |
| pickle-rick-morty-review | Cross-ticket spec conformance review worker |
| pickle-rick-chaos | Project Mayhem chaos engineering |
| pickle-rick-dot | PRD to attractor DOT graph converter |
| pickle-rick-dot-patterns | DOT convergence pattern reference |
| pickle-rick-attract | Submit DOT to attractor server |
| pickle-rick-anatomy-park | Subsystem deep review with trap-door catalog |
| pickle-rick-szechuan-sauce | Principle-driven code quality convergence |
| pickle-rick-retry | Retry failed tickets |
| pickle-rick-standup | Standup summary from session activity |
| pickle-rick-tmux | tmux launcher with monitor dashboard |
| pickle-rick-zellij | Zellij launcher with KDL layouts |
| pickle-rick-help | Command reference |

## Signal Protocol

| Token | Meaning | Handled By |
|-------|---------|------------|
| `[EPIC_COMPLETED]` | All tickets done | mux_runner → stop |
| `[TASK_COMPLETED]` | Current ticket done | mux_runner → next ticket |
| `[PRD_COMPLETE]` | PRD drafted | mux_runner → breakdown phase |
| `[TICKET_SELECTED]` | Ticket picked | mux_runner → delegation |
| `[BLOCKED]` | Worker stuck | mux_runner → stop |
| `[EXISTENCE_IS_PAIN]` | Meeseeks clean pass | mux_runner → check min_iterations |
| `[THE_CITADEL_APPROVES]` | Council clean pass | mux_runner → check min_passes |

## Session Data Layout

```
~/.pickle-rick/
  sessions/<timestamp>_<hash>/
    state.json              # Session state machine (20 fields)
    circuit_breaker.json    # Circuit breaker state
    microverse.json         # Microverse convergence state
    prd.md                  # Product requirements
    parent_ticket.md        # Epic ticket
    tickets/<hash>/         # Per-ticket artifacts
      ticket.md             # Ticket spec
      research.md           # Research notes
      plan.md               # Implementation plan
      conformance.md        # Spec conformance report
      code_review.md        # Self-review
    handoff.txt             # Context bridge between iterations
    activity.jsonl          # Event log
    iteration_N.log         # Per-iteration output
  jar/
    jar_manifest.json       # Batch queue
  patterns/
    index.json              # Pattern library index
    <name>/pattern_analysis.md
  pickle_settings.json      # Global defaults
```
