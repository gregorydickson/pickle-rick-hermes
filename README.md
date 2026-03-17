# Pickle Rick — Hermes Agent Plugin

Autonomous engineering toolbelt for [Hermes Agent](https://github.com/NousResearch/hermes-agent). Full port of [pickle-rick-claude](https://github.com/ATheorical/pickle-rick-claude).

## What It Does

7 skills that give Hermes autonomous engineering superpowers:

| Skill | Description |
|-------|-------------|
| **pickle-rick** | PRD → Breakdown → Implement → Review → Ship autonomous loop |
| **pickle-rick-meeseeks** | Iterative code review (10-50 passes, 7 focus categories) |
| **pickle-rick-microverse** | Optimize a metric through convergence (auto-revert regressions) |
| **pickle-rick-portal-gun** | Transplant patterns from donor repos into your project |
| **pickle-rick-council** | PR stack review → agent-executable fix directives |
| **pickle-rick-jar** | Batch queue: add tasks now, run them later |
| **pickle-rick-morty** | Worker lifecycle: Research → Plan → Implement → Verify → Review → Simplify |

Plus a **pickle-rick-help** skill to list everything.

## Install

```bash
git clone <this-repo>
cd pickle-rick-hermes
./install.sh
```

## Quick Start

**In any Hermes session:**
```
> Run pickle rick: build a REST API for user management
> Run meeseeks on this codebase
> Microverse: optimize test coverage using pytest --cov
> Portal gun: steal the auth pattern from github.com/owner/repo
> Council of ricks: review my PR stack
```

**CLI orchestrators (long-running / overnight):**
```bash
# Autonomous implementation loop
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/mux_runner.py \
  --task "Build user auth" --working-dir ~/project --max-iterations 20

# Metric convergence
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/microverse_runner.py \
  --metric "pytest --cov | tail -1" --task "90% coverage" --working-dir ~/project

# Batch execution
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_jar.py add \
  --task "Build auth" --working-dir ~/project
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_jar.py run
```

**Utilities:**
```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_utils.py status
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_utils.py standup --days 1
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_utils.py metrics --days 7
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_utils.py cancel
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
                │  pickle-rick-morty   │  Research → Plan → Code → Test
                └─────────────────────┘
```

### vs. Claude Code Version

| Feature | Claude Code | Hermes Port |
|---------|-------------|-------------|
| Loop mechanism | stop-hook traps agent | External Python orchestrator |
| Worker spawning | `spawn-morty.ts` → `claude` | `delegate_task` subagents |
| State management | TypeScript + locks | Python + fcntl locks |
| Commands | Slash commands | Skills (SKILL.md) |
| Circuit breaker | TypeScript | Python |
| Metric optimization | `microverse-runner.ts` | `microverse_runner.py` |
| Job queue | `jar-runner.ts` | `pickle_jar.py` |

## Components

### Skills (8 total)

| Path | Lines | Purpose |
|------|-------|---------|
| `skills/pickle-rick/SKILL.md` | ~180 | Core autonomous loop |
| `skills/pickle-rick-meeseeks/SKILL.md` | ~180 | Iterative code review |
| `skills/pickle-rick-microverse/SKILL.md` | ~140 | Convergence optimization |
| `skills/pickle-rick-portal-gun/SKILL.md` | ~160 | Pattern transplantation |
| `skills/pickle-rick-council/SKILL.md` | ~130 | PR stack review |
| `skills/pickle-rick-jar/SKILL.md` | ~100 | Batch job queue |
| `skills/pickle-rick-morty/SKILL.md` | ~170 | Worker lifecycle |
| `skills/pickle-rick-help/SKILL.md` | ~80 | Help / command list |

### Scripts

| Path | Lines | Purpose |
|------|-------|---------|
| `scripts/pickle_state.py` | ~295 | Session state management |
| `scripts/circuit_breaker.py` | ~250 | 3-state circuit breaker |
| `scripts/mux_runner.py` | ~405 | Main loop orchestrator |
| `scripts/microverse_runner.py` | ~320 | Convergence orchestrator |
| `scripts/pickle_jar.py` | ~180 | Batch job queue runner |
| `scripts/pickle_utils.py` | ~290 | Status, cancel, standup, metrics |

### Templates & References

| Path | Purpose |
|------|---------|
| `templates/prd.md` | PRD template |
| `templates/ticket.md` | Ticket template with frontmatter |
| `references/persona.md` | Pickle Rick voice rules |
| `references/architecture.md` | Architecture overview |

## Session Data

```
~/.pickle-rick/
  sessions/<timestamp>_<hash>/
    state.json              # Session state machine
    circuit_breaker.json    # Circuit breaker state
    microverse.json         # Microverse convergence state
    prd.md                  # Product requirements
    tickets/<hash>/         # Per-ticket artifacts
    activity.jsonl          # Event log
    iteration_N.log         # Per-iteration logs
  jar/
    jar_manifest.json       # Batch queue
  pickle_settings.json      # Global defaults
```

## Feature Parity

### Fully Ported ✅
- [x] Ralph Wiggum Loop (autonomous iteration)
- [x] State machine with file locking
- [x] Circuit breaker (CLOSED → HALF_OPEN → OPEN)
- [x] Manager/Worker delegation (Rick/Morty)
- [x] PRD + ticket templates
- [x] Signal protocol
- [x] Activity logging
- [x] Rate limit detection & backoff
- [x] Mr. Meeseeks review (7 focus categories)
- [x] Microverse convergence (command + LLM-judged metrics)
- [x] Portal Gun (pattern transplantation)
- [x] Council of Ricks (PR stack review → directives)
- [x] Pickle Jar (batch job queue)
- [x] Morty worker lifecycle
- [x] Status / Cancel / Standup / Metrics utilities
- [x] Configurable settings

### Planned 🔜
- [ ] Tmux monitor dashboard (live session view)
- [ ] Zellij layout support
- [ ] Pattern library persistence (Portal Gun cache)
- [ ] GitNexus integration (Council of Ricks)

## License

Apache-2.0

## Credits

- **Original**: [Gal Zahavi](https://github.com/ATheorical) — pickle-rick-claude
- **Hermes Port**: Gregory Dickson
