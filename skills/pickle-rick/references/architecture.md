# Pickle Rick Hermes Plugin — Architecture

## Origin

Ported from pickle-rick-claude (v1.11.0) by Gal Zahavi.
Original: https://github.com/ATheorical/pickle-rick-claude

## Key Differences from Claude Code Version

| Component | Claude Code | Hermes Port |
|---|---|---|
| Loop mechanism | stop-hook.ts traps agent exit | External Python orchestrator (mux_runner.py) |
| Worker spawning | spawn-morty.ts -> `claude` CLI | delegate_task subagents |
| State management | TypeScript + file locks | Python + fcntl locks |
| Commands | /pickle, /meeseeks (slash commands) | Skills (SKILL.md) |
| Circuit breaker | circuit-breaker.ts | circuit_breaker.py |
| Templates | .claude/commands/*.md | Skill templates/ dir |

## The Ralph Wiggum Loop

The core pattern (named after the "i'm in danger" meme) forces autonomous
iteration through a lifecycle:

```
    Research -> Plan -> Implement -> Verify -> Review -> Simplify
         ^                                          |
         +---------- iterate until done ------------+
```

Each iteration:
1. Reads state.json for current step/ticket
2. Executes the appropriate phase
3. Signals completion via tokens
4. Orchestrator handles state transitions

## State Machine

```
    prd -> breakdown -> research -> plan -> implement -> refactor -> review
                          ^                                          |
                          +-------- next ticket ---------------------+
```

## Manager/Worker Pattern

- **Rick (Manager)**: Reads PRD, breaks into tickets, delegates to workers.
  Never writes code directly.
- **Morty (Worker)**: Receives a ticket via delegate_task. Researches,
  plans, implements, and verifies. Produces artifacts.

## Circuit Breaker

Three-state machine: CLOSED -> HALF_OPEN -> OPEN

Monitors: git progress, error signatures, degenerate output.

## Signal Protocol

| Token | Meaning |
|---|---|
| [EPIC_COMPLETED] | All tickets done |
| [TASK_COMPLETED] | Current ticket done |
| [PRD_COMPLETE] | PRD drafted |
| [TICKET_SELECTED] | Ticket picked |
| [BLOCKED] | Worker stuck |
