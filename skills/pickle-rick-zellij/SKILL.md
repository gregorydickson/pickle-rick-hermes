---
name: pickle-rick-zellij
description: "Launch Pickle Rick sessions in Zellij with KDL layouts and true context clearing between iterations. Alternative to tmux mode for Zellij users."
version: 0.3.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, zellij, session, launcher, monitor]
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: [pickle-rick, pickle-rick-tmux, pickle-rick-meeseeks]
---

# Pickle Rick Zellij — Zellij Session Launcher

Launch Pickle Rick sessions in Zellij with KDL layouts and true context clearing.

## When to Use

- User says "pickle zellij", "run in zellij"
- User prefers Zellij over tmux for terminal multiplexing
- User wants context clearing with Zellij KDL layouts

Launch a Pickle Rick epic in Zellij with KDL layouts and true context clearing between iterations — best for large epics with 8+ tasks.

# pickle-rick-zellij


## Hermes Adaptation Notes

- **Session init**: Use `pickle_state.py init` instead of setup.js
- **State updates**: Use `pickle_state.py update` instead of update-state.js
- **Worker spawning**: Use `delegate_task` instead of spawning subprocesses
- **Orchestration**: Use `mux_runner.py` instead of mux-runner.js
- **Context clearing**: `hermes -q` per iteration instead of `claude -p`

## Step 1: Check Zellij

Run `zellij --version`. If missing: "Install Zellij: `cargo install zellij` or `brew install zellij`, or use pickle-rick-tmux (tmux) or pickle-rick (interactive mode) instead." Stop.

Parse the version string to verify >= 0.40.0:
```bash
ZELLIJ_RAW=$(zellij --version 2>/dev/null || echo "")
ZELLIJ_VER=$(echo "$ZELLIJ_RAW" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
if [ -z "$ZELLIJ_VER" ]; then
  echo "Zellij not found. Install: cargo install zellij / brew install zellij"
  echo "Alternatives: pickle-rick-tmux (tmux) or pickle-rick (interactive)"
  exit 1
fi
IFS='.' read -r ZMJ ZMN ZPT <<< "$ZELLIJ_VER"
if [ "$ZMJ" -lt 0 ] || { [ "$ZMJ" -eq 0 ] && [ "$ZMN" -lt 40 ]; }; then
  echo "Zellij $ZELLIJ_VER too old — need >= 0.40.0. Run: cargo install zellij"
  exit 1
fi
echo "Zellij $ZELLIJ_VER OK"
```

If `$ZELLIJ` env var is set, warn: "Nested Zellij session detected — this may cause issues. Consider running from a non-Zellij terminal." Continue (non-fatal).

## Step 2: Session Setup
Extract flags from user input (`--resume <path>`, `--max-iterations <N>`, etc.). Pass flags before `--task`. Task text goes in `--task "..."`.

```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py init --tmux <FLAGS> --task "<TASK_TEXT>"
```
No flags: `pickle_state.py init --tmux --task "user input"`.
Flags+task example: `pickle_state.py init --tmux --max-iterations 10 --task "refactor auth"`

Extract `SESSION_ROOT=<path>` and `working_dir` from output.

To resume an existing session, skip init and pass `--resume <SESSION_ROOT>` directly to the runner (e.g. `mux_runner.py --resume <SESSION_ROOT>`).

## Step 3: Create Zellij Session
Session name: `pickle-<hash>` from SESSION_ROOT basename.

Pre-clean ghost sessions:
```bash
zellij delete-session pickle-<hash> 2>/dev/null || true
```

Export env vars for the KDL layout:
```bash
export PICKLE_SESSION_ROOT=<SESSION_ROOT>
export PICKLE_CWD=<working_dir>
export PICKLE_EXTENSION_ROOT=~/.pickle-rick
```

**Three-tier session creation** — try each approach in order, use the first that succeeds:

**(A) Preferred — `--new-session-with-layout` (Zellij >= 0.41):**
```bash
zellij --new-session-with-layout ~/.pickle-rick/layouts/monitor-pickle.kdl \
  attach --create-background pickle-<hash>
```

**(B) Fallback — `--layout` flag:**
```bash
zellij --layout ~/.pickle-rick/layouts/monitor-pickle.kdl \
  attach --create-background pickle-<hash>
```

**(C) Two-step fallback — create then apply layout:**
```bash
zellij attach --create-background pickle-<hash>
ZELLIJ_SESSION_NAME=pickle-<hash> zellij action new-tab --layout ~/.pickle-rick/layouts/monitor-pickle.kdl
# Remove the empty default tab created by attach
ZELLIJ_SESSION_NAME=pickle-<hash> zellij action go-to-previous-tab
ZELLIJ_SESSION_NAME=pickle-<hash> zellij action close-tab
```

The KDL layout (`monitor-pickle.kdl`) creates both tabs automatically:
- **runner** tab: mux_runner.py (background orchestrator)
- **monitor** tab (focused): dashboard top-left, log-stream top-right, morty-watcher bottom

## Step 4: Report
Print: session name, `zellij attach pickle-<hash>`, tab layout (monitor: dashboard top-left / log-stream top-right / morty-logs bottom; runner: switch tabs with Zellij keybinds), cancel: `python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_utils.py cancel --session <SESSION_ROOT>` (graceful), emergency: `zellij delete-session pickle-<hash>` then `python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_utils.py cancel --session <SESSION_ROOT>`, state path: `<SESSION_ROOT>/state.json`.

Output: `[TASK_COMPLETED]`


## Pitfalls

1. **Zellij >= 0.40.0 required** — KDL layouts need recent version
2. **KDL layout files** — Must be generated or copied to session dir
3. **Alternative to tmux** — Same functionality, different multiplexer
