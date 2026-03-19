---
name: pickle-rick-help
description: "Display Pickle Rick for Hermes help — list all available commands, skills, and utilities. Synced with pickle-rick-claude v1.19.0."
version: 0.3.0
author: Gregory Dickson
license: Apache-2.0
metadata:
  hermes:
    tags: [help, pickle-rick, documentation]
    related_skills: [pickle-rick, pickle-rick-meeseeks, pickle-rick-microverse, pickle-rick-portal-gun, pickle-rick-council, pickle-rick-jar, pickle-rick-morty]
---

# Pickle Rick for Hermes — Help

## When to Use

- User says "help pickle", "pickle rick help", "what pickle commands are there"

## Skills (20 total)

| Skill | What It Does |
|-------|-------------|
| **pickle-rick** | Core autonomous loop: PRD -> Breakdown -> Implement -> Review -> Ship |
| **pickle-rick-prd** | Interactive PRD drafter with user interview and verification-first design |
| **pickle-rick-refine-prd** | 3 parallel analysts refine PRD + decompose into atomic tickets |
| **pickle-rick-meeseeks** | Iterative code review (10+ passes, 8 focus categories) |
| **pickle-rick-microverse** | Convergence optimization (metric-driven iterative improvement) |
| **pickle-rick-portal-gun** | Pattern transplantation v2: gene transfusion, import graph tracing, pattern library, convergence loop |
| **pickle-rick-council** | PR stack review with agent-executable directives |
| **pickle-rick-jar** | Batch job queue for sequential task execution |
| **pickle-rick-morty** | Worker lifecycle: Research -> Plan -> Implement -> Verify -> Review -> Simplify |
| **pickle-rick-morty-review** | Cross-ticket spec conformance + focused review worker |
| **pickle-rick-chaos** | Project Mayhem: mutation testing, dependency downgrades, config corruption |
| **pickle-rick-dot** | Convert PRDs to attractor-compatible DOT graphs with 5-layer quality gates |
| **pickle-rick-dot-patterns** | DOT pattern reference (22 convergence patterns, 3 tiers) |
| **pickle-rick-attract** | Submit DOT pipelines to attractor server with detach mode + checkpoints |
| **pickle-rick-tmux** | tmux launcher with live monitor dashboard |
| **pickle-rick-zellij** | Zellij launcher with KDL layouts |
| **pickle-rick-meeseeks-zellij** | Meeseeks review loop in Zellij |
| **pickle-rick-standup** | Activity log standup formatter (Slack-formatted) |
| **pickle-rick-retry** | Retry failed/timed-out tickets |
| **pickle-rick-help** | This help screen |

## CLI Scripts

```bash
# State management
python3 scripts/pickle_state.py init --task "..." --working-dir .
python3 scripts/pickle_state.py read --session <path>
python3 scripts/pickle_state.py update --session <path> --step breakdown

# Orchestrators
python3 scripts/mux_runner.py --task "..." --working-dir .
python3 scripts/microverse_runner.py --metric "..." --task "..."

# Circuit breaker
python3 scripts/circuit_breaker.py status --session <path>
python3 scripts/circuit_breaker.py reset --session <path>

# Pickle Jar
python3 scripts/pickle_jar.py add --task "..." --working-dir .
python3 scripts/pickle_jar.py list
python3 scripts/pickle_jar.py run

# Pattern library
python3 scripts/pattern_library.py list
python3 scripts/pattern_library.py search --query "auth"
python3 scripts/pattern_library.py save --name "pattern" --analysis analysis.md

# Utilities
python3 scripts/pickle_utils.py status
python3 scripts/pickle_utils.py cancel
python3 scripts/pickle_utils.py standup --days 1
python3 scripts/pickle_utils.py metrics --days 7
python3 scripts/pickle_utils.py retry --session <path> --ticket <id>

# Monitor
python3 scripts/monitor.py <session-dir>
bash scripts/tmux-monitor.sh <session-name> <session-dir> pickle
```

## Quick Examples

```
"Run pickle rick: build a REST API for user management"
"Draft a PRD for the auth module"
"Refine this PRD and break it into tickets"
"Run meeseeks on this codebase"
"Microverse: optimize test coverage using pytest --cov"
"Portal gun: steal the auth pattern from github.com/owner/repo"
"Council of ricks: review my PR stack"
"Project mayhem: stress test this project"
"Add this to the pickle jar for later"
"Generate a DOT pipeline from prd.md"
"Submit this DOT to the attractor server"
"Show me a standup of recent pickle work"
```

## Session Data

All sessions stored in `~/.pickle-rick/sessions/`.
Jar data in `~/.pickle-rick/jar/`.
Patterns in `~/.pickle-rick/patterns/`.
Settings in `~/.pickle-rick/pickle_settings.json`.

## Version

Synced with pickle-rick-claude v1.19.0 (March 2026).

## Pitfalls

1. **This is read-only** — Help lists commands but doesn't execute them
2. **Check skill versions** — If a command doesn't work, the skill may need updating
