---
name: pickle-rick-retry
description: "Retry a failed or timed-out Pickle Rick ticket. Resets ticket state and re-enters the orchestration loop."
version: 0.3.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, retry, recovery, tickets]
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: [pickle-rick, pickle-rick-tmux]
---

# Pickle Rick Retry — Retry Failed Tickets

Retry a failed or timed-out Pickle Rick ticket.

## When to Use

- User says "retry ticket", "pickle retry"
- A ticket failed or timed out during autonomous execution
- User wants to re-attempt a specific ticket

You are retrying a failed or timed-out Pickle Rick ticket.

Run the retry script with the ticket ID:
```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_utils.py retry user input
```

After the script runs:
1. Read the printed `pickle_state.py init` command from the output.
2. Run `git status` — if there are uncommitted changes, stash them with `git stash`.
3. Execute the printed spawn-morty command exactly as shown.
4. After Morty outputs `[I AM DONE]`, proceed with the standard validation and commit flow (audit docs, check git diff, run tests, commit if passing, mark ticket Done).


## Pitfalls

1. **Ticket must exist** — Check session state before retrying
2. **Git state matters** — Failed ticket may have left dirty working tree
3. **Circuit breaker** — Multiple retries may trip the circuit breaker
