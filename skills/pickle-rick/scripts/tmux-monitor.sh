#!/bin/bash
# Pickle Rick tmux monitor layout (4-pane dashboard).
# Usage: tmux-monitor.sh <session-name> <session-root> [pickle|meeseeks|council|microverse]
set -e

NAME="$1"
SESSION_ROOT="$2"
MODE="${3:-pickle}"
SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$NAME" ] || [ -z "$SESSION_ROOT" ]; then
  echo "Usage: tmux-monitor.sh <session-name> <session-root> [pickle|meeseeks|council|microverse]" >&2
  exit 1
fi

# Create 2x2 grid:
#   ┌──────────────┬──────────────┐
#   │ 0: dashboard │ 1: logs      │  60%
#   ├──────────────┼──────────────┤
#   │ 2: activity  │ 3: tail      │  40%
#   └──────────────┴──────────────┘
tmux set-option -t "$NAME" mouse on 2>/dev/null || true

tmux new-window -t "$NAME" -n monitor
tmux split-window -v -t "$NAME:monitor" -l 40%
tmux split-window -h -t "$NAME:monitor.0"
tmux split-window -h -t "$NAME:monitor.2"

# Pane 0 = top-left (live dashboard)
tmux send-keys -t "$NAME:monitor.0" "python3 $SCRIPTS/monitor.py $SESSION_ROOT" Enter

# Pane 1 = top-right (iteration log tail)
tmux send-keys -t "$NAME:monitor.1" "tail -F $SESSION_ROOT/iteration_*.log 2>/dev/null || echo 'Waiting for logs...'; sleep 5; tail -F $SESSION_ROOT/iteration_*.log 2>/dev/null || tail -F $SESSION_ROOT/microverse_iter_*.log 2>/dev/null" Enter

# Pane 2 = bottom-left (activity log)
tmux send-keys -t "$NAME:monitor.2" "tail -F $SESSION_ROOT/activity.jsonl 2>/dev/null || echo 'Waiting for activity...'; sleep 5; tail -F $SESSION_ROOT/activity.jsonl" Enter

# Pane 3 = bottom-right (mode-specific)
case "$MODE" in
  meeseeks|council)
    tmux send-keys -t "$NAME:monitor.3" "tail -F $SESSION_ROOT/meeseeks-summary.md $SESSION_ROOT/council-summary.md 2>/dev/null || echo 'Waiting for review summary...'" Enter
    ;;
  microverse)
    tmux send-keys -t "$NAME:monitor.3" "watch -n 5 'python3 -c \"import json; m=json.load(open(\\\"$SESSION_ROOT/microverse.json\\\")); h=m[\\\"convergence\\\"][\\\"history\\\"][-5:] if m[\\\"convergence\\\"][\\\"history\\\"] else []; print(f\\\"Status: {m[\\\"status\\\"]}  Stall: {m[\\\"convergence\\\"][\\\"stall_counter\\\"]}/{m[\\\"convergence\\\"][\\\"stall_limit\\\"]}\\\"); [print(f\\\"  iter {e[\\\"iteration\\\"]}: score={e[\\\"score\\\"]} {e[\\\"action\\\"]}\\\") for e in h]\"'" Enter
    ;;
  *)
    tmux send-keys -t "$NAME:monitor.3" "python3 $SCRIPTS/pickle_utils.py status --active-only 2>/dev/null; echo '---'; watch -n 10 'python3 $SCRIPTS/pickle_utils.py status --active-only 2>/dev/null'" Enter
    ;;
esac

tmux select-pane -t "$NAME:monitor.0"
tmux select-window -t "$NAME:monitor"
