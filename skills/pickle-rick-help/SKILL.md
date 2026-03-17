---
name: pickle-rick-help
description: "Display Pickle Rick for Hermes help — list all available commands, skills, and utilities."
version: 0.1.0
author: Gregory Dickson
license: Apache-2.0
metadata:
  hermes:
    tags: [help, pickle-rick, documentation]
    related_skills: [pickle-rick, pickle-rick-meeseeks, pickle-rick-microverse, pickle-rick-portal-gun, pickle-rick-council, pickle-rick-jar, pickle-rick-morty]
---

# Pickle Rick for Hermes — Help

## Skills (say the name to activate)

| Skill | What It Does |
|-------|-------------|
| **pickle-rick** | Core autonomous loop: PRD -> Breakdown -> Implement -> Review -> Ship |
| **pickle-rick-meeseeks** | Iterative code review (10-50 passes, 7 focus categories) |
| **pickle-rick-microverse** | Convergence optimization (metric-driven iterative improvement) |
| **pickle-rick-portal-gun** | Pattern transplantation from donor repos/packages |
| **pickle-rick-council** | PR stack review with agent-executable directives |
| **pickle-rick-jar** | Batch job queue for sequential task execution |
| **pickle-rick-morty** | Worker lifecycle instructions (used by subagents) |

## CLI Scripts

```bash
# State management
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py init --task "..." --working-dir .
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py read --session <path>

# Orchestrators
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/mux_runner.py --task "..." --working-dir .
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/microverse_runner.py --metric "..." --task "..."

# Circuit breaker
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/circuit_breaker.py status --session <path>
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/circuit_breaker.py reset --session <path>

# Pickle Jar
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_jar.py add --task "..." --working-dir .
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_jar.py list
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_jar.py run

# Utilities
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_utils.py status
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_utils.py cancel
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_utils.py standup --days 1
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_utils.py metrics --days 7
```

## Quick Examples

```
"Run pickle rick: build a REST API for user management"
"Run meeseeks on this codebase"
"Microverse: optimize test coverage using pytest --cov"
"Portal gun: steal the auth pattern from github.com/owner/repo"
"Council of ricks: review my PR stack"
"Add this to the pickle jar for later"
```

## Session Data

All sessions stored in `~/.pickle-rick/sessions/`.
Jar data in `~/.pickle-rick/jar/`.
