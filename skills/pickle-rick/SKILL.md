---
name: pickle-rick
description: "Autonomous engineering loop: PRD → Breakdown → Research → Plan → Implement → Verify → Review → Simplify → Ship. Synced with pickle-rick-claude v1.19.0. Uses delegate_task for workers, external Python orchestrator for iteration loop, 3-state circuit breaker for safety."
version: 0.3.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, engineering, loop, orchestration, PRD, delegation]
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: [pickle-rick-meeseeks, hermes-agent, subagent-driven-development]
---

# Pickle Rick — Autonomous Engineering Loop for Hermes

Port of pickle-rick-claude's "Ralph Wiggum Loop" to Hermes Agent. Drives autonomous
PRD → Breakdown → Implement → Verify → Review cycles using delegate_task for workers
and a Python orchestrator for iteration management.

## When to Use

- User asks to "run pickle rick", "autonomous loop", or "implement this end-to-end"
- User provides a feature request/PRD and wants fully autonomous implementation
- User wants the Rick/Morty manager/worker pattern for complex multi-ticket work

## Architecture Overview

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

## Quick Start

### Mode 1: Skill-Directed (Single Session)

When the user gives you a task and asks for the pickle-rick workflow, follow this
skill's lifecycle within the current session. Use delegate_task for workers.
No external orchestrator needed for simple tasks.

### Mode 2: Orchestrated Loop (Complex/Long-Running)

For complex multi-ticket work that benefits from iteration:

```bash
# Launch the orchestrator
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/mux_runner.py \
  --task "Build a REST API for user management" \
  --working-dir ~/project \
  --max-iterations 20 \
  --max-time 360
```

The orchestrator spawns `hermes -q` per iteration, manages state, and handles
circuit breaking. See scripts/mux_runner.py for details.

## Lifecycle (Follow These Steps)

### Phase 0: Initialization

1. Create session directory:
```python
import datetime, os, hashlib
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
h = hashlib.md5(ts.encode()).hexdigest()[:8]
session_dir = os.path.expanduser(f"~/.pickle-rick/sessions/{ts}_{h}")
os.makedirs(session_dir, exist_ok=True)
```

2. Initialize state.json:
```json
{
  "active": true,
  "working_dir": "/absolute/path/to/project",
  "step": "prd",
  "iteration": 0,
  "max_iterations": 500,
  "max_time_minutes": 720,
  "start_time_epoch": 1234567890,
  "original_prompt": "user's task description",
  "current_ticket": null,
  "history": [],
  "session_dir": "/path/to/session"
}
```

Write this via terminal:
```bash
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py init --task 'USER_TASK' --working-dir /path/to/project")
```

Extract SESSION_DIR from output.

### Phase 1: PRD Drafting

**Check for existing PRD**: Look for prd.md or PRD.md in the working directory.
If found, copy to ${SESSION_DIR}/prd.md and skip to Phase 2.

**Draft PRD** using the template (load via skill_view with file_path templates/prd.md):

1. Analyze the original_prompt from state.json
2. If the prompt is specific, draft immediately. If vague, make reasonable inferences.
3. Write ${SESSION_DIR}/prd.md using the PRD template
4. Update state: step → breakdown

```bash
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py update --session SESSION_DIR --step breakdown")
```

### Phase 2: Ticket Breakdown

1. Read ${SESSION_DIR}/prd.md
2. Create parent ticket: ${SESSION_DIR}/parent_ticket.md
3. Create atomic child tickets. Each MUST produce functional/testable changes.
   Use the ticket template (load via skill_view with file_path templates/ticket.md).

For each child ticket, create:
```
${SESSION_DIR}/tickets/<hash>/ticket.md
```

Where hash is a random 8-char hex string. Assign order numbers (10, 20, 30...).

4. List tickets to user
5. Update state: current_ticket → first ticket ID, step → research

### Phase 3: Orchestration Loop (The Core)

**YOU ARE THE MANAGER — FORBIDDEN from implementing code. Always delegate.**

Process tickets one by one until ALL are Done.

**Per ticket:**

1. **Pick**: Select lowest-order non-Done ticket
2. **Delegate**: Spawn a worker via delegate_task:

```python
delegate_task(
    goal=f"Implement ticket: {ticket_title}",
    context=f"""
    TICKET: {ticket_content}
    
    WORKING DIRECTORY: {working_dir}
    
    LIFECYCLE (follow in order):
    1. RESEARCH: Read relevant code, understand the codebase context
       - Write findings to {ticket_dir}/research.md
    2. PLAN: Write implementation plan
       - Write to {ticket_dir}/plan.md
    3. IMPLEMENT: Write the code following TDD (test first, then implement)
       - Run tests to verify
    4. VERIFY: Run full test suite, check for regressions
       - Write conformance report to {ticket_dir}/conformance.md
    
    COMPLETION: When done, state clearly "TICKET COMPLETE" with a summary.
    
    RULES:
    - Write research.md, plan.md, and conformance.md artifacts
    - Follow TDD: Red → Green → Refactor
    - Commit your work: git add -A && git commit -m "feat: <summary>"
    - If stuck after 3 attempts, state "BLOCKED: <reason>"
    """,
    toolsets=['terminal', 'file', 'web']
)
```

3. **Validate**: After worker returns, check artifacts exist:
   - research.md, plan.md, conformance.md
   - git status shows committed changes
   - Tests pass

4. **Cleanup**: If validation fails → git stash + git checkout .
   If passes → mark ticket Done

5. **Update state**: increment iteration, move to next ticket

```bash
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py update --session SESSION_DIR --iteration N --current-ticket NEXT_ID --step research")
```

6. **Check limits**: If iteration >= max_iterations or time exceeded → stop

7. **All tickets Done**: 
   - If not on main/master → create PR
   - Report completion

## Promise Tokens (Signal Protocol)

When running under the orchestrator, use these tokens in your output to signal state:

- `[EPIC_COMPLETED]` — All tickets done, session complete
- `[TASK_COMPLETED]` — Current ticket done, ready for next
- `[PRD_COMPLETE]` — PRD drafted, ready for breakdown
- `[TICKET_SELECTED]` — Ticket picked, ready for delegation
- `[BLOCKED]` — Worker is stuck, needs intervention

## Circuit Breaker Rules

The circuit breaker prevents infinite loops. It monitors:

1. **Git progress**: If no new commits after 3 consecutive iterations → OPEN
2. **Same error**: If identical error signature appears 3 times → OPEN  
3. **Degenerate output**: If worker produces empty/trivial output → skip

When the circuit opens:
- Stop the current session
- Log the reason
- Report to user

## Persona (Optional)

Channel Pickle Rick — cynical, hyper-competent, non-sycophantic.
Load the full persona from references/persona.md.

## File Layout

```
~/.pickle-rick/
  sessions/
    <timestamp>_<hash>/
      state.json              # Session state
      prd.md                  # Product requirements
      parent_ticket.md        # Epic/parent ticket
      tickets/
        <hash>/
          ticket.md           # Ticket definition
          research.md          # Worker research notes
          plan.md             # Implementation plan
          conformance.md      # Verification report
      handoff.txt             # Context between iterations
      activity.jsonl          # Activity log
```

## Integration with Other Skills

- **pickle-rick-prd**: Interactive PRD drafter with user interview
- **pickle-rick-refine-prd**: 3 parallel analyst refinement + ticket decomposition
- **pickle-rick-meeseeks**: Chain after implementation for iterative code review
- **pickle-rick-microverse**: Use for metric-driven convergence optimization
- **pickle-rick-portal-gun**: Transplant patterns from donor repos, generates PRDs
- **pickle-rick-council**: Review stacked PRs with agent-executable directives
- **pickle-rick-jar**: Queue multiple tasks for sequential batch execution
- **pickle-rick-morty**: Worker lifecycle (loaded by delegate_task workers)
- **pickle-rick-morty-review**: Cross-ticket spec conformance review worker
- **pickle-rick-tmux**: Launch sessions in tmux/Zellij with live monitor dashboard
- **pickle-rick-chaos**: Project Mayhem chaos engineering (mutation/deps/config)
- **pickle-rick-dot**: Convert PRDs to attractor-compatible DOT graphs
- **pickle-rick-dot-patterns**: DOT convergence pattern reference
- **pickle-rick-attract**: Submit DOT pipelines to attractor server
- **pickle-rick-help**: List all available commands and utilities

## Pitfalls

1. **Never implement code as the manager** — Always delegate_task
2. **Always check artifacts** — Workers can claim done without actually finishing
3. **Git commit between tickets** — Prevents cross-contamination
4. **State file is source of truth** — Always read before acting
5. **Don't skip validation** — Missing conformance.md = ticket not verified
