#!/usr/bin/env python3
"""
Pickle Rick State Management for Hermes Agent.

Manages session state (state.json) for the autonomous engineering loop.
Ported from pickle-rick-claude's state-manager.ts.

Usage:
    python3 pickle_state.py init --task "Build a REST API" --working-dir ~/project
    python3 pickle_state.py update --session <path> --step breakdown
    python3 pickle_state.py update --session <path> --iteration 5 --current-ticket abc123
    python3 pickle_state.py read --session <path>
    python3 pickle_state.py deactivate --session <path>
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
import time
import fcntl
from pathlib import Path
from typing import Optional, Dict, Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STEPS = ['prd', 'breakdown', 'research', 'plan', 'implement', 'refactor', 'review', 'meeseeks', 'council']
SESSIONS_ROOT = Path.home() / '.pickle-rick' / 'sessions'
SCHEMA_VERSION = 1

DEFAULT_STATE = {
    'active': True,
    'working_dir': '',
    'step': 'prd',
    'mode': 'pickle',
    'iteration': 0,
    'max_iterations': 100,
    'max_time_minutes': 720,
    'worker_timeout_seconds': 1200,
    'start_time_epoch': 0,
    'completion_promise': None,
    'original_prompt': '',
    'current_ticket': None,
    'history': [],
    'started_at': '',
    'session_dir': '',
    'tmux_mode': False,
    'min_iterations': 0,
    'command_template': None,
    'chain_meeseeks': False,
    'pid': None,
    'schema_version': SCHEMA_VERSION,
}

# ---------------------------------------------------------------------------
# File locking (ported from state-manager.ts)
# ---------------------------------------------------------------------------

class StateLockError(Exception):
    pass

def locked_read(state_path: Path) -> Dict[str, Any]:
    """Read state.json with a shared lock."""
    with open(state_path, 'r') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def locked_write(state_path: Path, state: Dict[str, Any]) -> None:
    """Write state.json with an exclusive lock (atomic via tmp + rename)."""
    tmp_path = state_path.with_suffix(f'.tmp.{os.getpid()}.{int(time.time() * 1000)}')
    try:
        with open(tmp_path, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(state, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.rename(str(tmp_path), str(state_path))
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

def locked_update(state_path: Path, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Read-modify-write with exclusive lock."""
    lock_path = state_path.with_suffix('.lock')
    with open(lock_path, 'w') as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            try:
                state = json.loads(state_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                print(f"WARNING: Could not read state at {state_path}: {e}. Using default state.", file=sys.stderr)
                state = dict(DEFAULT_STATE)
            # Record history for step/ticket changes
            if 'step' in updates and updates['step'] != state.get('step'):
                state.setdefault('history', []).append({
                    'step': updates['step'],
                    'ticket': updates.get('current_ticket', state.get('current_ticket')),
                    'timestamp': datetime.datetime.now().isoformat(),
                })
            state.update(updates)
            tmp_path = state_path.with_suffix(f'.tmp.{os.getpid()}')
            tmp_path.write_text(json.dumps(state, indent=2))
            try:
                os.replace(str(tmp_path), str(state_path))
            except OSError:
                tmp_path.unlink(missing_ok=True)
                state_path.write_text(json.dumps(state, indent=2))
            return state
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def locked_append_activity_log(activity_log: Path, log_entry: Dict[str, Any]) -> None:
    """Append to activity.jsonl with an exclusive lock."""
    with open(activity_log, 'a') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(log_entry) + '\n')
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def cmd_init(args) -> None:
    """Initialize a new session."""
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    h = hashlib.md5(f"{ts}{os.getpid()}".encode()).hexdigest()[:8]
    session_dir = SESSIONS_ROOT / f"{ts}_{h}"
    session_dir.mkdir(parents=True, exist_ok=True)

    working_dir = os.path.abspath(args.working_dir or os.getcwd())

    mode = getattr(args, 'mode', 'pickle') or 'pickle'
    state = dict(DEFAULT_STATE)
    state.update({
        'working_dir': working_dir,
        'mode': mode,
        'step': mode if mode in ('meeseeks', 'council') else 'prd',
        'start_time_epoch': int(time.time()),
        'original_prompt': args.task or '',
        'started_at': datetime.datetime.now().isoformat(),
        'session_dir': str(session_dir),
        'max_iterations': args.max_iterations or 100,
        'max_time_minutes': args.max_time or 720,
    })

    if getattr(args, 'command_template', None):
        state['command_template'] = args.command_template
    if getattr(args, 'tmux', False):
        state['tmux_mode'] = True
        state['active'] = False

    state_path = session_dir / 'state.json'
    locked_write(state_path, state)

    # Create subdirectories
    (session_dir / 'tickets').mkdir(exist_ok=True)

    # Write activity log header
    activity_log = session_dir / 'activity.jsonl'
    log_entry = {
        'ts': datetime.datetime.now().isoformat(),
        'event': 'session_start',
        'source': 'pickle',
        'session': session_dir.name,
        'original_prompt': args.task or '',
    }
    locked_append_activity_log(activity_log, log_entry)

    print(f"SESSION_DIR={session_dir}")
    print(f"STATE_FILE={state_path}")
    print(f"WORKING_DIR={working_dir}")


def cmd_read(args) -> None:
    """Read and display current state."""
    session_dir = Path(args.session)
    state_path = session_dir / 'state.json'
    if not state_path.exists():
        print(f"ERROR: No state.json found at {state_path}", file=sys.stderr)
        sys.exit(1)
    state = locked_read(state_path)
    if args.field:
        val = state.get(args.field)
        print(json.dumps(val) if isinstance(val, (dict, list)) else str(val))
    else:
        print(json.dumps(state, indent=2))


def cmd_update(args) -> None:
    """Update state fields."""
    session_dir = Path(args.session)
    state_path = session_dir / 'state.json'
    if not state_path.exists():
        print(f"ERROR: No state.json found at {state_path}", file=sys.stderr)
        sys.exit(1)

    updates = {}
    if args.step:
        if args.step not in VALID_STEPS:
            print(f"ERROR: Invalid step '{args.step}'. Valid: {VALID_STEPS}", file=sys.stderr)
            sys.exit(1)
        updates['step'] = args.step
    if args.iteration is not None:
        updates['iteration'] = args.iteration
    if args.current_ticket is not None:
        updates['current_ticket'] = args.current_ticket if args.current_ticket != 'null' else None
    if args.active is not None:
        updates['active'] = args.active.lower() == 'true'

    if not updates:
        print("WARNING: No updates specified", file=sys.stderr)
        return

    state = locked_update(state_path, updates)
    print(json.dumps(state, indent=2))


def cmd_deactivate(args) -> None:
    """Deactivate session."""
    session_dir = Path(args.session)
    state_path = session_dir / 'state.json'
    if not state_path.exists():
        print(f"WARNING: No state.json found at {state_path}", file=sys.stderr)
        return
    state = locked_update(state_path, {'active': False})

    # Log session end
    elapsed = int(time.time()) - state.get('start_time_epoch', 0)
    log_entry = {
        'ts': datetime.datetime.now().isoformat(),
        'event': 'session_end',
        'source': 'pickle',
        'session': session_dir.name,
        'duration_min': round(elapsed / 60),
    }
    activity_log = session_dir / 'activity.jsonl'
    locked_append_activity_log(activity_log, log_entry)

    print(f"Session deactivated. Duration: {elapsed // 60}m {elapsed % 60}s")


def cmd_log(args) -> None:
    """Log an activity event."""
    session_dir = Path(args.session)
    activity_log = session_dir / 'activity.jsonl'
    log_entry = {
        'ts': datetime.datetime.now().isoformat(),
        'event': args.event,
        'source': 'pickle',
        'session': session_dir.name,
    }
    if args.ticket:
        log_entry['ticket'] = args.ticket
    if args.description:
        log_entry['title'] = args.description
    locked_append_activity_log(activity_log, log_entry)
    print(f"Logged: {args.event}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Pickle Rick State Manager')
    sub = parser.add_subparsers(dest='command', required=True)

    # init
    p_init = sub.add_parser('init', help='Initialize new session')
    p_init.add_argument('--task', '-t', required=True, help='Task description')
    p_init.add_argument('--working-dir', '-w', help='Working directory (default: cwd)')
    p_init.add_argument('--max-iterations', type=int, default=100)
    p_init.add_argument('--max-time', type=int, default=720, help='Max time in minutes')
    p_init.add_argument('--mode', choices=['pickle', 'meeseeks', 'council', 'microverse'],
                        default='pickle', help='Session mode (default: pickle)')
    p_init.add_argument('--command-template', help='Skill template name (e.g. microverse, anatomy-park)')
    p_init.add_argument('--tmux', action='store_true', help='Mark session for tmux mode (sets active=false for runner ownership)')

    # read
    p_read = sub.add_parser('read', help='Read session state')
    p_read.add_argument('--session', '-s', required=True, help='Session directory')
    p_read.add_argument('--field', '-f', help='Read specific field')

    # update
    p_update = sub.add_parser('update', help='Update session state')
    p_update.add_argument('--session', '-s', required=True, help='Session directory')
    p_update.add_argument('--step', help='New step value')
    p_update.add_argument('--iteration', type=int, help='New iteration count')
    p_update.add_argument('--current-ticket', help='Current ticket ID (use "null" to clear)')
    p_update.add_argument('--active', help='Set active state (true/false)')

    # deactivate
    p_deact = sub.add_parser('deactivate', help='Deactivate session')
    p_deact.add_argument('--session', '-s', required=True, help='Session directory')

    # log
    p_log = sub.add_parser('log', help='Log activity event')
    p_log.add_argument('--session', '-s', required=True, help='Session directory')
    p_log.add_argument('--event', '-e', required=True,
                       choices=['ticket_completed', 'epic_completed', 'commit',
                                'research', 'bug_fix', 'feature', 'refactor', 'review',
                                'circuit_open', 'circuit_recovery'])
    p_log.add_argument('--ticket', help='Ticket ID')
    p_log.add_argument('--description', '-d', help='Event description')

    args = parser.parse_args()
    {
        'init': cmd_init,
        'read': cmd_read,
        'update': cmd_update,
        'deactivate': cmd_deactivate,
        'log': cmd_log,
    }[args.command](args)


if __name__ == '__main__':
    main()
