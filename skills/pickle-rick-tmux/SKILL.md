---
name: pickle-rick-tmux
description: "Launch Pickle Rick sessions in tmux with true context clearing between iterations — best for large epics with 8+ tasks. Supports pickle, meeseeks, microverse, and council modes."
version: 0.3.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: ['autonomous', 'tmux', 'session', 'launcher', 'monitor']
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: ['pickle-rick', 'pickle-rick-meeseeks', 'pickle-rick-microverse']
---

# Pickle Rick — Tmux

## When to Use

- User says "run in tmux", "pickle tmux", "with monitor"
- Long-running autonomous sessions that benefit from live monitoring
- User wants to detach and reattach later


Launch a Pickle Rick epic in tmux with true context clearing between iterations — best for large epics with 8+ tasks.

# pickle-rick-tmux


## Hermes Adaptation Notes

- **Session init**: Use `pickle_state.py init` instead of setup.js
- **State updates**: Use `pickle_state.py update` instead of update-state.js
- **Worker spawning**: Use `delegate_task` instead of spawning subprocesses
- **Orchestration**: Use `mux_runner.py` instead of mux-runner.js
- **Context clearing**: `hermes -q` per iteration instead of `claude -p`

## Step 1: Check tmux
Run `tmux -V`. If missing: "Install tmux: `brew install tmux` or `apt install tmux`, or use pickle-rick for interactive mode." Stop.

## Step 2: Session Setup
Extract flags from user input (`--resume <path>`, `--max-iterations <N>`, etc.). Pass flags before `--task`. Task text goes in `--task "..."`.

```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/setup.js" --tmux <FLAGS> --task "<TASK_TEXT>"
```
No flags: `pickle_state.py init --tmux --task "user input"`.
Resume example: `pickle_state.py init --tmux --resume /sessions/057f0263` (no --task needed).
Flags+task example: `pickle_state.py init --tmux --max-iterations 10 --task "refactor auth"`

Extract `SESSION_ROOT=<path>` and `working_dir` from output.

## Step 3: tmux Session
Session name: `pickle-<hash>` from SESSION_ROOT basename.
```bash
tmux new-session -d -s <name> -c <working_dir>
sleep 1
```
Print attach command immediately: `tmux attach -t <name>` (Window 1 "monitor" = 4-pane; Window 0 "runner" = background, Ctrl+B 0).

## Step 4: Launch Runner
```bash
tmux send-keys -t <name>:0 "python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/mux-runner.js <SESSION_ROOT>; echo ''; echo 'Runner finished.  Ctrl+B 1 → monitor  |  Ctrl+B D → detach'; read" Enter
```

## Step 5: Monitor (4-pane)
```bash
bash ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/tmux-monitor.sh" <name> <SESSION_ROOT> pickle
```

## Step 6: Report
Print: session name, `tmux attach -t <name>`, window layout (monitor: dashboard top-left / log-stream top-right / morty-logs bottom-left / raw-morty bottom-right; runner: Ctrl+B 0), cancel: `cd <working_dir> && eat-pickle`, emergency: `tmux kill-session -t <name>` then `python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/cancel.js`, state path: `<SESSION_ROOT>/state.json`.

Output: `[TASK_COMPLETED]`

## Pitfalls

1. **Multiplexer must be installed** — Check version before launching
2. **Session names must be unique** — Hash-based naming prevents conflicts
3. **Monitor panes are read-only** — Don't interact with monitor windows
