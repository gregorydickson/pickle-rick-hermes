#!/usr/bin/env python3
"""
Pickle Rick Utilities — metrics, standup, status, cancel.

Usage:
    python3 pickle_utils.py status [--working-dir .]
    python3 pickle_utils.py cancel [--working-dir .]
    python3 pickle_utils.py standup [--days 1] [--since 2026-03-15]
    python3 pickle_utils.py metrics [--days 7] [--session SESSION_DIR]
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from collections import defaultdict

import pickle_state

SESSIONS_ROOT = Path.home() / '.pickle-rick' / 'sessions'


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def cmd_status(args):
    """Show status of active sessions."""
    if not SESSIONS_ROOT.exists():
        print("No pickle-rick sessions found.")
        return
    
    sessions = sorted(SESSIONS_ROOT.iterdir(), reverse=True)
    active = []
    recent = []
    
    for s in sessions[:20]:
        state_path = s / 'state.json'
        if not state_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        
        if state.get('active'):
            active.append((s, state))
        else:
            recent.append((s, state))
    
    if active:
        print(f"Active Sessions ({len(active)}):")
        print(f"{'=' * 60}")
        for s, state in active:
            elapsed = int(datetime.datetime.now().timestamp()) - state.get('start_time_epoch', 0)
            print(f"  {s.name}")
            print(f"    Step: {state.get('step', '?')} | Iter: {state.get('iteration', 0)}/{state.get('max_iterations', '?')}")
            print(f"    Ticket: {state.get('current_ticket', 'none')}")
            print(f"    Dir: {state.get('working_dir', '?')}")
            print(f"    Elapsed: {elapsed // 60}m {elapsed % 60}s")
            
            # Check circuit breaker
            cb_path = s / 'circuit_breaker.json'
            if cb_path.exists():
                try:
                    cb = json.loads(cb_path.read_text())
                    if cb.get('state') != 'CLOSED':
                        print(f"    Circuit: {cb['state']} — {cb.get('reason', '')}")
                except (json.JSONDecodeError, OSError):
                    pass
            print()
    else:
        print("No active sessions.")
    
    if recent and not args.active_only:
        print(f"\nRecent Sessions ({min(len(recent), 5)}):")
        print(f"{'-' * 60}")
        for s, state in recent[:5]:
            print(f"  {s.name} | {state.get('step', '?')} | iter {state.get('iteration', 0)}")


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

def cmd_cancel(args):
    """Cancel active sessions."""
    if not SESSIONS_ROOT.exists():
        print("No sessions found.")
        return
    
    cancelled = 0
    for s in sorted(SESSIONS_ROOT.iterdir(), reverse=True):
        state_path = s / 'state.json'
        if not state_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        
        if state.get('active'):
            if args.session and s.name != args.session:
                continue
            pickle_state.locked_update(state_path, {'active': False})
            print(f"Cancelled: {s.name}")
            cancelled += 1
    
    if cancelled == 0:
        print("No active sessions to cancel.")
    else:
        print(f"\nCancelled {cancelled} session(s).")


# ---------------------------------------------------------------------------
# Standup
# ---------------------------------------------------------------------------

def cmd_standup(args):
    """Generate standup report from activity logs."""
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=args.days)
    since = since.replace(tzinfo=None)
    if args.since:
        since = datetime.datetime.fromisoformat(args.since).replace(tzinfo=datetime.timezone.utc).replace(tzinfo=None)
    
    events = []
    
    if not SESSIONS_ROOT.exists():
        print("No sessions found.")
        return
    
    for s in SESSIONS_ROOT.iterdir():
        log_path = s / 'activity.jsonl'
        if not log_path.exists():
            continue
        try:
            for line in log_path.read_text().strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    ts = datetime.datetime.fromisoformat(entry['ts'].replace('Z', '+00:00'))
                    if ts >= since:
                        events.append(entry)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        except OSError:
            continue
    
    if not events:
        print(f"No activity since {since.strftime('%Y-%m-%d %H:%M')}")
        return
    
    events.sort(key=lambda e: e.get('ts', ''))
    
    # Group by event type
    by_type = defaultdict(list)
    for e in events:
        by_type[e.get('event', 'unknown')].append(e)
    
    print(f"Standup Report — Since {since.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'=' * 60}")
    print(f"Total events: {len(events)}")
    print()
    
    # Sessions
    starts = by_type.get('session_start', [])
    ends = by_type.get('session_end', [])
    if starts:
        print(f"Sessions: {len(starts)} started, {len(ends)} completed")
        for s in starts:
            prompt = s.get('original_prompt', 'N/A')
            if len(prompt) > 60:
                prompt = prompt[:57] + '...'
            print(f"  - {s.get('ts', '?')[:16]}: {prompt}")
    
    # Tickets
    tickets = by_type.get('ticket_completed', [])
    if tickets:
        print(f"\nTickets Completed: {len(tickets)}")
        for t in tickets:
            print(f"  - {t.get('ticket', '?')}: {t.get('title', 'N/A')}")
    
    # Other events
    for event_type in ['feature', 'bug_fix', 'refactor', 'review', 'research']:
        items = by_type.get(event_type, [])
        if items:
            print(f"\n{event_type.replace('_', ' ').title()}: {len(items)}")
            for item in items[:10]:
                print(f"  - {item.get('title', item.get('description', 'N/A'))}")
    
    # Circuit breaker events
    opens = by_type.get('circuit_open', [])
    if opens:
        print(f"\nCircuit Breaker Opens: {len(opens)}")
        for o in opens:
            print(f"  - {o.get('ts', '?')[:16]}: {o.get('reason', 'N/A')}")
    
    # Git stats
    try:
        git_log = subprocess.run(
            ['git', 'log', f'--since={since.strftime("%Y-%m-%d")}',
             '--oneline', '--no-merges'],
            capture_output=True, text=True, timeout=10,
            cwd=os.getcwd()
        )
        commits = [l for l in git_log.stdout.strip().split('\n') if l.strip()]
        if commits:
            print(f"\nGit Commits (this repo): {len(commits)}")
            for c in commits[:10]:
                print(f"  - {c}")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def cmd_metrics(args):
    """Show session metrics."""
    if args.session:
        session_dir = Path(args.session)
        sessions = [session_dir] if session_dir.exists() else []
    else:
        if not SESSIONS_ROOT.exists():
            print("No sessions found.")
            return
        sessions = sorted(SESSIONS_ROOT.iterdir(), reverse=True)[:args.days * 5]
    
    since = datetime.datetime.now() - datetime.timedelta(days=args.days)
    
    total_iterations = 0
    total_sessions = 0
    total_duration = 0
    total_tickets = 0
    
    for s in sessions:
        state_path = s / 'state.json'
        if not state_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        
        started = state.get('started_at', '')
        if started:
            try:
                start_dt = datetime.datetime.fromisoformat(started)
                if start_dt < since:
                    continue
            except ValueError:
                pass
        
        total_sessions += 1
        total_iterations += state.get('iteration', 0)
        
        start_epoch = state.get('start_time_epoch', 0)
        if start_epoch > 0:
            if state.get('active'):
                duration = int(datetime.datetime.now().timestamp()) - start_epoch
            else:
                # Estimate from activity log
                log_path = s / 'activity.jsonl'
                duration = state.get('max_time_minutes', 0) * 60
                try:
                    lines = log_path.read_text().strip().split('\n')
                    for line in reversed(lines):
                        if not line.strip():
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if entry.get('event') == 'session_end':
                            duration = entry.get('duration_min', 0) * 60
                            break
                except OSError:
                    pass
            total_duration += duration
        
        # Count tickets (directories only)
        tickets_dir = s / 'tickets'
        if tickets_dir.exists():
            total_tickets += len([d for d in tickets_dir.iterdir() if d.is_dir()])
    
    print(f"Pickle Rick Metrics — Last {args.days} days")
    print(f"{'=' * 60}")
    print(f"  Sessions:    {total_sessions}")
    print(f"  Iterations:  {total_iterations}")
    print(f"  Tickets:     {total_tickets}")
    print(f"  Total Time:  {total_duration // 3600}h {(total_duration % 3600) // 60}m")
    if total_sessions > 0:
        print(f"  Avg Iter/Session: {total_iterations / total_sessions:.1f}")


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------

def cmd_retry(args):
    """Retry a failed or skipped ticket."""
    session_dir = Path(args.session)
    state_path = session_dir / 'state.json'
    if not state_path.exists():
        print(f"No state.json found at {session_dir}")
        return
    
    try:
        state = json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        print("Could not read state.json")
        return
    
    ticket_dir = session_dir / 'tickets' / args.ticket
    ticket_file = ticket_dir / 'ticket.md'
    if not ticket_file.exists():
        print(f"Ticket {args.ticket} not found in {ticket_dir}")
        return
    
    # Reset ticket status to Todo
    content = ticket_file.read_text()
    content = re.sub(r'^status:\s*(Done|Skipped|Failed)', 'status: Todo', content, flags=re.IGNORECASE | re.MULTILINE)
    ticket_file.write_text(content)
    
    # Update state to point to this ticket
    pickle_state.locked_update(state_path, {
        'current_ticket': args.ticket,
        'step': 'research',
        'active': True,
    })
    
    print(f"Ticket {args.ticket} reset to Todo")
    print(f"Session reactivated at step: research")
    print(f"Run the orchestrator to continue: mux_runner.py --resume {session_dir}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Pickle Rick Utilities')
    sub = parser.add_subparsers(dest='command', required=True)
    
    p_status = sub.add_parser('status')
    p_status.add_argument('--active-only', action='store_true')
    
    p_cancel = sub.add_parser('cancel')
    p_cancel.add_argument('--session', help='Specific session name to cancel')
    
    p_standup = sub.add_parser('standup')
    p_standup.add_argument('--days', type=int, default=1)
    p_standup.add_argument('--since', help='ISO date (YYYY-MM-DD)')
    
    p_metrics = sub.add_parser('metrics')
    p_metrics.add_argument('--days', type=int, default=7)
    p_metrics.add_argument('--session', help='Specific session directory')
    
    p_retry = sub.add_parser('retry', help='Retry a failed/skipped ticket')
    p_retry.add_argument('--session', '-s', required=True, help='Session directory')
    p_retry.add_argument('--ticket', '-t', required=True, help='Ticket ID to retry')
    
    args = parser.parse_args()
    {'status': cmd_status, 'cancel': cmd_cancel,
     'standup': cmd_standup, 'metrics': cmd_metrics,
     'retry': cmd_retry}[args.command](args)


if __name__ == '__main__':
    main()
