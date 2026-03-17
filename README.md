# Pickle Rick — Hermes Agent Plugin

Autonomous engineering loop for [Hermes Agent](https://github.com/NousResearch/hermes-agent). Ported from [pickle-rick-claude](https://github.com/ATheorical/pickle-rick-claude).

## What It Does

Drives fully autonomous **PRD → Breakdown → Implement → Verify → Review** cycles:

- **Rick (Manager)** reads your task, drafts a PRD, breaks it into tickets
- **Morty (Workers)** implement each ticket via `delegate_task` subagents
- **Circuit Breaker** prevents infinite loops (monitors git progress)
- **Mr. Meeseeks** runs iterative code review passes after implementation

## Quick Start

### Install

```bash
./install.sh
```

This copies the skills into `~/.hermes/skills/autonomous-ai-agents/`.

### Use

**In a Hermes session:**
```
> Run pickle rick on this project: build a REST API for user management
```

Hermes loads the skill automatically and follows the lifecycle.

**Orchestrated loop (long-running):**
```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/mux_runner.py \
  --task "Build a REST API for user management" \
  --working-dir ~/project \
  --max-iterations 20
```

**Code review:**
```
> Run meeseeks on this codebase
```

## Architecture

```
                ┌─────────────────────┐
                │  mux_runner.py       │  External Python loop
                │  (orchestrator)      │  Spawns hermes -q per iteration
                └─────────┬───────────┘
                          │
                ┌─────────▼───────────┐
                │  Hermes (Manager)    │  Rick — reads state, delegates
                │  pickle-rick skill   │  Never writes code directly
                └─────────┬───────────┘
                          │ delegate_task
                ┌─────────▼───────────┐
                │  Hermes (Worker)     │  Morty — implements tickets
                │  subagent            │  Research → Plan → Code → Test
                └─────────────────────┘
```

### Key Difference from Claude Code Version

Claude Code uses a **stop-hook** to trap the agent and force iteration. Hermes has no hook system, so we use an **external Python orchestrator** that spawns `hermes -q` per iteration and manages state between runs.

## Components

| File | Lines | Purpose |
|------|-------|---------|
| `skills/pickle-rick/SKILL.md` | ~180 | Core skill — lifecycle, delegation, signals |
| `skills/pickle-rick/scripts/pickle_state.py` | 294 | Session state management |
| `skills/pickle-rick/scripts/circuit_breaker.py` | 248 | 3-state circuit breaker |
| `skills/pickle-rick/scripts/mux_runner.py` | 404 | External orchestrator loop |
| `skills/pickle-rick/templates/prd.md` | 71 | PRD template |
| `skills/pickle-rick/templates/ticket.md` | 36 | Ticket template |
| `skills/pickle-rick/references/persona.md` | 24 | Pickle Rick voice rules |
| `skills/pickle-rick/references/architecture.md` | 65 | Architecture docs |
| `skills/pickle-rick-meeseeks/SKILL.md` | 179 | Meeseeks review loop |

## Session Data

Sessions are stored in `~/.pickle-rick/sessions/<timestamp>_<hash>/`:

```
state.json              # Session state machine
circuit_breaker.json    # Circuit breaker state
prd.md                  # Product requirements
tickets/<hash>/
  ticket.md             # Ticket definition
  research.md           # Worker research
  plan.md               # Implementation plan
  conformance.md        # Verification report
activity.jsonl          # Activity event log
iteration_N.log         # Per-iteration logs
```

## Status

### Ported
- [x] Ralph Wiggum Loop (autonomous iteration)
- [x] State machine (state.json with file locking)
- [x] Circuit breaker (CLOSED → HALF_OPEN → OPEN)
- [x] Manager/Worker delegation
- [x] PRD + ticket templates
- [x] Signal protocol
- [x] Activity logging
- [x] Rate limit detection & backoff
- [x] Mr. Meeseeks review loop

### Not Yet Ported
- [ ] Portal Gun (pattern transplantation from donor repos)
- [ ] Council of Ricks (multi-agent consensus)
- [ ] Pickle Jar (job queue for batch PRDs)
- [ ] Microverse (convergence optimization loop)
- [ ] Tmux monitor dashboard
- [ ] Standup report generator

## License

Apache-2.0 (same as original pickle-rick-claude)

## Credits

- **Original**: [Gal Zahavi](https://github.com/ATheorical) — pickle-rick-claude
- **Hermes Port**: Gregory Dickson
