#!/usr/bin/env python3
"""
Pickle Rick Live Monitor Dashboard.

Renders a real-time terminal dashboard showing session state, tickets,
circuit breaker status, and recent iteration output. Refreshes every 2s.

Ported from pickle-rick-claude's monitor.ts.

Usage:
    python3 monitor.py <session-dir>
"""

import json
import os
import signal
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional


# ANSI styles (Matrix theme from original)
class MX:
    GREEN = '\033[32m'
    BRIGHT = '\033[1;32m'
    DIM = '\033[2;32m'
    CYAN = '\033[36m'
    WARN = '\033[33m'
    ERR = '\033[31m'
    R = '\033[0m'


def format_time(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h{m:02d}m{s:02d}s"
    return f"{m}m{s:02d}s"


def sparkline(values: list) -> str:
    """Unicode sparkline from a sequence of numbers (ported from CL monitor.js)."""
    if not values:
        return ''
    blocks = '▁▂▃▄▅▆▇█'
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val or 1
    return ''.join(
        blocks[min(len(blocks) - 1, round(((v - min_val) / range_val) * (len(blocks) - 1)))]
        for v in values
    )


def render_microverse_trend(mv: dict, width: int) -> list:
    """Render compact microverse convergence trend section with sparkline."""
    out = []
    sep = f"{MX.DIM}{'─' * width}{MX.R}"
    history = mv.get('convergence', {}).get('history', [])
    direction = mv.get('key_metric', {}).get('direction', 'higher')
    target_label = str(mv.get('convergence_target', '—'))

    out.append(f'\n{sep}\n{MX.BRIGHT}Metric Trend{MX.R} {MX.DIM}({direction} is better, target: {target_label}){MX.R}\n')

    if not history:
        out.append(f'  {MX.DIM}No measurements yet{MX.R}\n')
        return out

    scores = [h['score'] for h in history]
    spark = sparkline(scores)
    latest = scores[-1]
    latest_action = history[-1].get('action', 'accept')
    latest_color = MX.GREEN if latest_action == 'accept' else MX.ERR

    out.append(f'  {MX.DIM}Score:{MX.R} {latest_color}{latest}{MX.R}  {MX.GREEN}{spark}{MX.R}\n')

    tail = history[-8:]  # Last 8 entries
    entries = []
    for h in tail:
        sym = '✓' if h.get('action') == 'accept' else '✗'
        color = MX.GREEN if h.get('action') == 'accept' else MX.ERR
        entries.append(f"{color}{h['iteration']}:{h['score']}{sym}{MX.R}")
    out.append(f'  {" ".join(entries)}\n')

    stall_counter = mv.get('convergence', {}).get('stall_counter', 0)
    stall_limit = mv.get('convergence', {}).get('stall_limit', 5)
    if stall_counter > 0:
        stall_color = MX.ERR if stall_counter >= stall_limit - 1 else MX.WARN
        out.append(f'  {stall_color}Stall: {stall_counter}/{stall_limit}{MX.R}\n')

    status = mv.get('status', 'unknown')
    if status == 'converged':
        out.append(f'  {MX.BRIGHT}{MX.GREEN}◆ CONVERGED{MX.R}\n')
    elif status == 'stopped':
        reason = mv.get('exit_reason', '')
        out.append(f'  {MX.WARN}◇ STOPPED ({reason}){MX.R}\n')

    return out


def status_symbol(status: str) -> str:
    s = (status or '').lower()
    if s == 'done':
        return '[x]'
    elif s == 'in progress':
        return '[>]'
    elif s == 'skipped':
        return '[!]'
    elif s == 'todo':
        return '[ ]'
    return '[?]'


def collect_tickets(session_dir: Path) -> list:
    """Collect ticket info from session dir."""
    tickets_dir = session_dir / 'tickets'
    if not tickets_dir.exists():
        return []
    
    tickets = []
    for d in sorted(tickets_dir.iterdir()):
        if not d.is_dir():
            continue
        ticket_file = d / 'ticket.md'
        if not ticket_file.exists():
            continue
        try:
            content = ticket_file.read_text()
            # Parse frontmatter
            info = {'id': d.name, 'title': d.name, 'status': 'Todo', 'order': 999}
            if content.startswith('---'):
                end = content.find('---', 3)
                if end > 0:
                    fm = content[3:end]
                    for line in fm.strip().split('\n'):
                        if ':' in line:
                            k, v = line.split(':', 1)
                            k, v = k.strip(), v.strip()
                            if k == 'title':
                                info['title'] = v
                            elif k == 'status':
                                info['status'] = v
                            elif k == 'order':
                                try:
                                    info['order'] = int(v)
                                except ValueError:
                                    pass
            tickets.append(info)
        except OSError:
            continue
    
    tickets.sort(key=lambda t: t.get('order', 999))
    return tickets


def latest_iteration_log(session_dir: Path) -> 'Optional[Path]':
    """Find the most recent iteration log file."""
    logs = sorted(session_dir.glob('iteration_*.log'), reverse=True)
    if not logs:
        logs = sorted(session_dir.glob('tmux_iteration_*.log'), reverse=True)
    if not logs:
        logs = sorted(session_dir.glob('microverse_iter_*.log'), reverse=True)
    return logs[0] if logs else None


def render(session_dir: Path) -> bool:
    """Render the dashboard. Returns True if session is active."""
    if not session_dir.exists():
        return False
    
    state_path = session_dir / 'state.json'
    try:
        state = json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        sys.stdout.write(f'\033[2J\033[H{MX.DIM}Awaiting signal...{MX.R}\n')
        sys.stdout.flush()
        return True
    
    width = min(os.get_terminal_size().columns - 4, 90) if sys.stdout.isatty() else 80
    sep = f"{MX.DIM}{'─' * width}{MX.R}"
    
    start_epoch = state.get('start_time_epoch', 0)
    elapsed = max(0, int(time.time()) - start_epoch) if start_epoch > 0 else 0
    tickets = collect_tickets(session_dir)
    max_iter = state.get('max_iterations', 0)
    max_time = state.get('max_time_minutes', 0)
    
    iter_str = f"{state.get('iteration', 0)} / {max_iter}" if max_iter else str(state.get('iteration', 0))
    time_str = f"{format_time(elapsed)} / {max_time}m" if max_time else format_time(elapsed)
    
    work_dir = state.get('working_dir', '')
    project = os.path.basename(work_dir) if work_dir else 'unknown'
    task = state.get('original_prompt', '')
    if len(task) > width - 20:
        task = task[:width - 23] + '...'
    
    mode = state.get('mode', 'pickle')
    mode_labels = {'pickle': '🥒 pickle', 'meeseeks': '👋 meeseeks',
                   'council': '🏛️ council', 'microverse': '🔬 microverse'}
    mode_display = mode_labels.get(mode, mode)
    fields = [
        ('Project', f"{MX.BRIGHT}{project}{MX.R}"),
        ('Task', f"{MX.GREEN}{task or 'none'}{MX.R}"),
        ('Mode', f"{MX.CYAN}{mode_display}{MX.R}"),
        ('Phase', f"{MX.CYAN}{state.get('step', 'unknown')}{MX.R}"),
        ('Iteration', f"{MX.GREEN}{iter_str}{MX.R}"),
        ('Elapsed', f"{MX.GREEN}{time_str}{MX.R}"),
        ('Current', f"{MX.BRIGHT}{state.get('current_ticket', 'none')}{MX.R}"),
        ('Active', f"{MX.BRIGHT}▣ ONLINE{MX.R}" if state.get('active') else f"{MX.ERR}▢ OFFLINE{MX.R}"),
    ]
    
    # Circuit breaker
    cb_path = session_dir / 'circuit_breaker.json'
    if cb_path.exists():
        try:
            cb = json.loads(cb_path.read_text())
            cb_state = cb.get('state', 'CLOSED')
            if cb_state == 'CLOSED':
                fields.append(('Circuit', f"{MX.GREEN}CLOSED{MX.R}"))
            elif cb_state == 'HALF_OPEN':
                fields.append(('Circuit', f"{MX.WARN}HALF_OPEN ({cb.get('reason', '')}){MX.R}"))
            elif cb_state == 'OPEN':
                fields.append(('Circuit', f"{MX.ERR}OPEN ({cb.get('reason', '')}){MX.R}"))
        except (json.JSONDecodeError, OSError):
            pass
    
    # Microverse state with sparkline trend
    out = []
    mv_path = session_dir / 'microverse.json'
    if mv_path.exists():
        try:
            mv = json.loads(mv_path.read_text())
            # Use new detailed trend rendering when in microverse/szechuan mode
            if mv.get('convergence', {}).get('history'):
                out.extend(render_microverse_trend(mv, width))
            else:
                # Fallback to compact one-liner
                status = mv.get('status', '?')
                stall = mv.get('convergence', {}).get('stall_counter', 0)
                limit = mv.get('convergence', {}).get('stall_limit', 5)
                history = mv.get('convergence', {}).get('history', [])
                best = max((h['score'] for h in history if h.get('action') == 'accept'), default=0)
                fields.append(('Microverse', f"{MX.CYAN}{status} | stall {stall}/{limit} | best {best}{MX.R}"))
        except (json.JSONDecodeError, OSError):
            pass
    
    key_width = max(len(k) for k, v in fields) + 1
    
    out = ['\033[2J\033[H'] + out
    out.append(f'\n{MX.BRIGHT}◤ PICKLE RICK — LIVE MONITOR ◢{MX.R}\n')
    out.append(f'{sep}\n')
    for k, v in fields:
        out.append(f'  {MX.DIM}{k + ":"}{" " * (key_width - len(k))}{MX.R} {v}\n')
    
    # Tickets
    if tickets:
        out.append(f'\n{sep}\n{MX.BRIGHT}Tickets:{MX.R}\n')
        for t in tickets:
            status = t.get('status', '').lower()
            sym = status_symbol(t['status'])
            is_current = t['id'] == state.get('current_ticket')
            
            if status == 'done':
                color_sym = f"{MX.GREEN}{sym}{MX.R}"
            elif status == 'in progress':
                color_sym = f"{MX.WARN}{sym}{MX.R}"
            else:
                color_sym = f"{MX.DIM}{sym}{MX.R}"
            
            prefix = f"{MX.BRIGHT}▸{MX.R}" if is_current else ' '
            title = f"{MX.BRIGHT}{t['title']}{MX.R}" if is_current else f"{MX.GREEN}{t['title']}{MX.R}"
            out.append(f'{prefix} {color_sym} {MX.DIM}{t["id"]}:{MX.R} {title}\n')
    
    # Recent log output
    log_path = latest_iteration_log(session_dir)
    if log_path and log_path.exists():
        try:
            content = log_path.read_text()
            lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
            recent = lines[-5:]
            if recent:
                out.append(f'\n{sep}\n{MX.DIM}Recent output:{MX.R}\n')
                for line in recent:
                    truncated = line[:width - 5] + '...' if len(line) > width - 2 else line
                    out.append(f'{MX.GREEN}  {truncated}{MX.R}\n')
        except OSError:
            pass
    
    out.append(f'\n{MX.DIM}Refreshing every 2s  •  Ctrl+C to exit{MX.R}\n')
    sys.stdout.write(''.join(out))
    sys.stdout.flush()
    return state.get('active', False)


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 monitor.py <session-dir>')
        sys.exit(1)
    
    session_dir = Path(sys.argv[1])
    if not session_dir.exists():
        print(f'Session directory not found: {session_dir}')
        sys.exit(1)
    
    def handle_sigint(signum, frame):
        sys.stdout.write(f'\033[2J\033[H{MX.DIM}Monitor detached.{MX.R}\n')
        sys.stdout.flush()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_sigint)
    
    while True:
        active = render(session_dir)
        if not active:
            time.sleep(3)
            still_inactive = not render(session_dir)
            if still_inactive:
                sys.stdout.write(f'\n{MX.BRIGHT}◤ SESSION COMPLETE ◢{MX.R}\n')
                break
        time.sleep(2)


if __name__ == '__main__':
    main()
