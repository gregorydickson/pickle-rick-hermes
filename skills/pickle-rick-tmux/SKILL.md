---
name: pickle-rick-tmux
description: "Launch Pickle Rick sessions in tmux or Zellij with a 4-pane live monitor dashboard. Supports pickle, meeseeks, microverse, and council modes."
version: 0.1.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [tmux, zellij, monitor, dashboard, terminal-multiplexer]
    homepage: https://github.com/ATheorical/pickle-rick-claude
    related_skills: [pickle-rick, pickle-rick-meeseeks, pickle-rick-microverse]
---

# Pickle Rick tmux/Zellij Launcher

Launch Pickle Rick sessions with a live 4-pane monitor dashboard in tmux or Zellij.

## When to Use

- User says "run in tmux", "pickle tmux", "with monitor"
- Long-running autonomous sessions that benefit from live monitoring
- User wants to detach and reattach later

## Dashboard Layout

```
┌──────────────────┬──────────────────┐
│ 0: Dashboard     │ 1: Log Stream    │  60%
│ (live state)     │ (iteration tail) │
├──────────────────┼──────────────────┤
│ 2: Activity/     │ 3: Mode-specific │  40%
│    Workers       │    (status/etc)  │
└──────────────────┴──────────────────┘
```

Pane 3 varies by mode:
- **pickle**: Session status
- **meeseeks/council**: Review summary
- **microverse**: Convergence history

## tmux Mode

### Prerequisites
```bash
tmux -V  # Must be installed
```

### Launch

1. Initialize session:
```bash
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py init --task 'YOUR TASK' --working-dir .")
```
Extract SESSION_DIR from output.

2. Create tmux session and launch runner:
```bash
SESSION_NAME="pickle-$(basename SESSION_DIR | tail -c 9)"

tmux new-session -d -s $SESSION_NAME -c WORKING_DIR
sleep 1

# Runner in window 0
tmux send-keys -t $SESSION_NAME:0 "python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/mux_runner.py --resume SESSION_DIR; echo 'Done'; read" Enter

# Monitor in window 1
bash ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/tmux-monitor.sh $SESSION_NAME SESSION_DIR pickle
```

3. Report to user:
```
Session: $SESSION_NAME
Attach:  tmux attach -t $SESSION_NAME
Monitor: Ctrl+B 1 (monitor) | Ctrl+B 0 (runner)
Cancel:  python3 scripts/pickle_utils.py cancel
Kill:    tmux kill-session -t $SESSION_NAME
```

### Modes

```bash
# Pickle (default)
bash tmux-monitor.sh $NAME $SESSION pickle

# Meeseeks
bash tmux-monitor.sh $NAME $SESSION meeseeks

# Council
bash tmux-monitor.sh $NAME $SESSION council

# Microverse
bash tmux-monitor.sh $NAME $SESSION microverse
```

## Zellij Mode

### Prerequisites
```bash
zellij --version  # >= 0.40.0
```

### Launch

```bash
SESSION_NAME="pickle-$(basename SESSION_DIR | tail -c 9)"

export PICKLE_SESSION_ROOT=SESSION_DIR
export PICKLE_CWD=WORKING_DIR
export PICKLE_SCRIPTS=~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts

# Try approaches in order
zellij --new-session-with-layout LAYOUT.kdl attach --create-background $SESSION_NAME 2>/dev/null || \
zellij --layout LAYOUT.kdl attach --create-background $SESSION_NAME 2>/dev/null || \
{ zellij attach --create-background $SESSION_NAME; ZELLIJ_SESSION_NAME=$SESSION_NAME zellij action new-tab --layout LAYOUT.kdl; }
```

Layouts available:
- `layouts/monitor-pickle.kdl` — Standard loop
- `layouts/monitor-meeseeks.kdl` — Review mode
- `layouts/monitor-microverse.kdl` — Convergence mode

### Report
```
Session: $SESSION_NAME
Attach:  zellij attach $SESSION_NAME
Kill:    zellij delete-session $SESSION_NAME
```

## Standalone Monitor

Run the dashboard without tmux/zellij against any active session:

```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/monitor.py SESSION_DIR
```

Refreshes every 2s. Shows: state, tickets, circuit breaker, microverse progress, recent output.
Ctrl+C to exit.

## Pitfalls

1. **Check tmux/zellij is installed** before launching
2. **Nested Zellij warning** — don't launch inside an existing Zellij session
3. **Mouse mode enabled** — tmux sessions get mouse on for scrollback
4. **Session names** — derived from session dir hash, max 8 chars
