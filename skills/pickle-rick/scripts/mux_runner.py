#!/usr/bin/env python3
"""
Pickle Rick Mux Runner for Hermes Agent.

External orchestrator that drives the autonomous loop by spawning
`hermes chat -q` instances per iteration. Equivalent to pickle-rick-claude's
mux-runner.ts but adapted for Hermes.

Usage:
    python3 mux_runner.py \
        --task "Build a REST API for user management" \
        --working-dir ~/project \
        --max-iterations 20 \
        --max-time 360

    # Resume existing session
    python3 mux_runner.py --resume ~/.pickle-rick/sessions/20260317_123456_abc12345

Features:
    - Spawns hermes -q per iteration with full context
    - Reads/writes state.json between iterations
    - Circuit breaker integration
    - Rate limit detection and backoff
    - Handoff summaries between iterations
    - Configurable timeouts
"""

import argparse
import datetime
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

# Add scripts dir to path for imports
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from circuit_breaker import CircuitBreaker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIGNAL_TOKENS = {
    'EPIC_COMPLETED': '[EPIC_COMPLETED]',
    'TASK_COMPLETED': '[TASK_COMPLETED]',
    'PRD_COMPLETE': '[PRD_COMPLETE]',
    'TICKET_SELECTED': '[TICKET_SELECTED]',
    'BLOCKED': '[BLOCKED]',
    'EXISTENCE_IS_PAIN': '[EXISTENCE_IS_PAIN]',
    'THE_CITADEL_APPROVES': '[THE_CITADEL_APPROVES]',
}

DEFAULT_WORKER_TIMEOUT = 1200  # 20 minutes per iteration
MAX_RATE_LIMIT_RETRIES = 3
RATE_LIMIT_WAIT_MINUTES = 60

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_state(session_dir: Path) -> dict:
    state_path = session_dir / 'state.json'
    try:
        return json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise RuntimeError(f"Failed to read state.json: {e}") from e


def write_state(session_dir: Path, state: dict) -> None:
    state_path = session_dir / 'state.json'
    tmp_path = state_path.with_suffix(f'.tmp.{os.getpid()}')
    try:
        tmp_path.write_text(json.dumps(state, indent=2))
        os.rename(str(tmp_path), str(state_path))
    except OSError:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        # Fallback: direct write
        state_path.write_text(json.dumps(state, indent=2))


def log_activity(session_dir: Path, event: str, **kwargs) -> None:
    activity_log = session_dir / 'activity.jsonl'
    entry = {
        'ts': datetime.datetime.now().isoformat(),
        'event': event,
        'source': 'mux_runner',
        'session': session_dir.name,
        **kwargs,
    }
    with open(activity_log, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def classify_output(output: str) -> str:
    """Classify iteration output by checking for signal tokens."""
    if SIGNAL_TOKENS['EPIC_COMPLETED'] in output:
        return 'epic_completed'
    if SIGNAL_TOKENS['EXISTENCE_IS_PAIN'] in output:
        return 'review_clean'
    if SIGNAL_TOKENS['THE_CITADEL_APPROVES'] in output:
        return 'review_clean'
    if SIGNAL_TOKENS['TASK_COMPLETED'] in output:
        return 'task_completed'
    if SIGNAL_TOKENS['PRD_COMPLETE'] in output:
        return 'prd_complete'
    if SIGNAL_TOKENS['TICKET_SELECTED'] in output:
        return 'ticket_selected'
    if SIGNAL_TOKENS['BLOCKED'] in output:
        return 'blocked'
    return 'continue'


def detect_rate_limit(output: str) -> bool:
    """Check if output indicates a rate limit."""
    patterns = [
        r'rate.?limit',
        r'usage.*limit.*reached',
        r'out of.*usage',
        r'too many requests',
        r'429',
    ]
    lower = output.lower()
    return any(re.search(p, lower) for p in patterns)


def build_handoff(state: dict, session_dir: Path, iteration: int) -> str:
    """Build handoff context for the next iteration."""
    lines = [
        f"# Handoff — Iteration {iteration}",
        f"",
        f"Session: {session_dir}",
        f"Step: {state['step']}",
        f"Current Ticket: {state.get('current_ticket', 'none')}",
        f"Iteration: {iteration} / {state['max_iterations']}",
        f"",
    ]
    
    # Include recent history
    history = state.get('history', [])
    if history:
        lines.append("## Recent History")
        for h in history[-5:]:
            lines.append(f"- {h.get('timestamp', '?')}: step={h.get('step', '?')}, ticket={h.get('ticket', 'n/a')}")
        lines.append("")
    
    # Check for handoff file
    handoff_path = session_dir / 'handoff.txt'
    if handoff_path.exists():
        try:
            content = handoff_path.read_text()
            lines.append("## Previous Iteration Notes")
            lines.append(content)
            handoff_path.unlink()
        except OSError:
            pass
    
    return '\n'.join(lines)


def load_persona() -> str:
    """Load the Pickle Rick persona from the skill's references directory."""
    persona_paths = [
        SCRIPTS_DIR / '..' / 'references' / 'persona.md',
        Path.home() / '.hermes' / 'skills' / 'autonomous-ai-agents' / 'pickle-rick' / 'references' / 'persona.md',
    ]
    for p in persona_paths:
        try:
            return p.resolve().read_text()
        except OSError:
            continue
    return ''


def build_prompt(state: dict, session_dir: Path, iteration: int) -> str:
    """Build the full prompt for a hermes iteration."""
    handoff = build_handoff(state, session_dir, iteration)
    persona = load_persona()
    
    prompt = f"""You are running the Pickle Rick autonomous engineering loop.

{persona}

Load the pickle-rick skill for full instructions: skill_view(name='pickle-rick')

SESSION DIRECTORY: {session_dir}
WORKING DIRECTORY: {state['working_dir']}
CURRENT STEP: {state['step']}
CURRENT TICKET: {state.get('current_ticket') or 'none'}
ITERATION: {iteration} / {state['max_iterations']}
ORIGINAL TASK: {state['original_prompt']}

{handoff}

INSTRUCTIONS:
- Read state.json from {session_dir}/state.json
- Based on the current step, execute the appropriate phase
- Use delegate_task for implementation work (you are the MANAGER)
- Signal completion with the appropriate token:
  [EPIC_COMPLETED] - All tickets done
  [TASK_COMPLETED] - Current ticket done
  [PRD_COMPLETE] - PRD drafted
  [TICKET_SELECTED] - Ticket picked for work
  [BLOCKED] - Cannot proceed

IMPORTANT: Work in {state['working_dir']} directory.
"""
    return prompt


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

def run_iteration(session_dir: Path, state: dict, iteration: int,
                  timeout: int = DEFAULT_WORKER_TIMEOUT) -> tuple:
    """
    Run a single iteration by spawning hermes -q.
    Returns (output: str, exit_code: int).
    """
    prompt = build_prompt(state, session_dir, iteration)
    log_file = session_dir / f'iteration_{iteration}.log'
    
    cmd = [
        'hermes', 'chat', '-q', prompt,
    ]
    
    print(f"\n{'=' * 60}")
    print(f"  Iteration {iteration} | Step: {state['step']} | Ticket: {state.get('current_ticket', 'none')}")
    print(f"{'=' * 60}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=state['working_dir'],
            env={**os.environ, 'PICKLE_SESSION': str(session_dir)},
        )
        output = result.stdout + result.stderr
        log_file.write_text(output)
        return output, result.returncode
    except subprocess.TimeoutExpired:
        msg = f"Iteration {iteration} timed out after {timeout}s"
        print(f"WARNING: {msg}")
        log_file.write_text(msg)
        return msg, 1
    except FileNotFoundError:
        print("ERROR: 'hermes' command not found. Is Hermes Agent installed?")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Pickle Rick Mux Runner for Hermes')
    parser.add_argument('--task', '-t', help='Task description (for new sessions)')
    parser.add_argument('--working-dir', '-w', help='Working directory')
    parser.add_argument('--max-iterations', type=int, default=100)
    parser.add_argument('--max-time', type=int, default=720, help='Max time in minutes')
    parser.add_argument('--resume', help='Resume existing session directory')
    parser.add_argument('--timeout', type=int, default=DEFAULT_WORKER_TIMEOUT,
                        help='Per-iteration timeout in seconds')
    parser.add_argument('--no-circuit-breaker', action='store_true')
    
    args = parser.parse_args()
    
    # Initialize or resume session
    if args.resume:
        session_dir = Path(args.resume)
        if not (session_dir / 'state.json').exists():
            print(f"ERROR: No state.json found at {session_dir}")
            sys.exit(1)
        state = read_state(session_dir)
        print(f"Resuming session: {session_dir}")
    else:
        if not args.task:
            print("ERROR: --task is required for new sessions")
            sys.exit(1)
        
        # Use pickle_state.py to init
        init_cmd = [
            sys.executable, str(SCRIPTS_DIR / 'pickle_state.py'),
            'init',
            '--task', args.task,
            '--working-dir', args.working_dir or os.getcwd(),
            '--max-iterations', str(args.max_iterations),
            '--max-time', str(args.max_time),
        ]
        result = subprocess.run(init_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"ERROR: Failed to initialize session:\n{result.stderr}")
            sys.exit(1)
        
        # Parse session dir from output
        for line in result.stdout.strip().split('\n'):
            if line.startswith('SESSION_DIR='):
                session_dir = Path(line.split('=', 1)[1])
                break
        else:
            print("ERROR: Could not parse SESSION_DIR from init output")
            sys.exit(1)
        
        state = read_state(session_dir)
        print(f"New session: {session_dir}")
    
    # Circuit breaker
    cb = None
    if not args.no_circuit_breaker:
        cb = CircuitBreaker(str(session_dir), state['working_dir'])
    
    # Signal handling for graceful shutdown
    shutdown = False
    def handle_signal(signum, frame):
        nonlocal shutdown
        shutdown = True
        print("\nShutting down gracefully...")
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    start_time = state.get('start_time_epoch', int(time.time()))
    max_time_seconds = state.get('max_time_minutes', args.max_time) * 60
    consecutive_rate_limits = 0
    
    print(f"\nPickle Rick Mux Runner")
    print(f"Task: {state['original_prompt']}")
    print(f"Working Dir: {state['working_dir']}")
    print(f"Max Iterations: {state['max_iterations']}")
    print(f"Max Time: {state.get('max_time_minutes', args.max_time)}m")
    print(f"{'=' * 60}")
    
    while not shutdown:
        iteration = state['iteration']
        
        # Check limits
        if iteration >= state['max_iterations']:
            print(f"\nMax iterations reached ({iteration})")
            break
        
        elapsed = int(time.time()) - start_time
        if elapsed >= max_time_seconds:
            print(f"\nTime limit reached ({elapsed // 60}m)")
            break
        
        # Check circuit breaker
        if cb and not cb.can_execute():
            status = cb.get_status()
            print(f"\nCircuit breaker OPEN: {status['reason']}")
            log_activity(session_dir, 'circuit_open', reason=status['reason'])
            break
        
        # Run iteration
        log_activity(session_dir, 'iteration_start', iteration=iteration)
        output, exit_code = run_iteration(session_dir, state, iteration, args.timeout)
        
        # Classify output
        classification = classify_output(output)
        print(f"  Result: {classification}")
        
        # Check for rate limits
        if detect_rate_limit(output):
            consecutive_rate_limits += 1
            if consecutive_rate_limits >= MAX_RATE_LIMIT_RETRIES:
                print(f"\nRate limit reached {consecutive_rate_limits} times. Stopping.")
                log_activity(session_dir, 'rate_limit_exhausted')
                break
            wait_time = RATE_LIMIT_WAIT_MINUTES * 60
            print(f"  Rate limited. Waiting {RATE_LIMIT_WAIT_MINUTES}m (attempt {consecutive_rate_limits}/{MAX_RATE_LIMIT_RETRIES})")
            log_activity(session_dir, 'rate_limit_wait', wait_minutes=RATE_LIMIT_WAIT_MINUTES)
            time.sleep(wait_time)
            continue
        else:
            consecutive_rate_limits = 0
        
        # Update circuit breaker
        has_progress = classification in ('task_completed', 'prd_complete', 'ticket_selected')
        if cb:
            cb_state = cb.record_result(
                has_progress=has_progress,
                error_signature=f"exit_{exit_code}" if exit_code != 0 else None,
                iteration=iteration,
            )
            if cb_state == 'OPEN':
                print(f"\nCircuit breaker tripped: {cb.get_status()['reason']}")
                break
        
        # Handle classification
        if classification == 'epic_completed':
            print(f"\n{'=' * 60}")
            print(f"  EPIC COMPLETED! All tickets done.")
            print(f"  Iterations: {iteration + 1}")
            print(f"  Duration: {elapsed // 60}m {elapsed % 60}s")
            print(f"{'=' * 60}")
            log_activity(session_dir, 'epic_completed')
            break
        
        if classification == 'review_clean':
            print(f"\n  Review pass clean (EXISTENCE IS PAIN / CITADEL APPROVES)")
            log_activity(session_dir, 'review_clean', iteration=iteration)
            # In meeseeks/council mode, clean pass may end the session
            # if we've hit min_iterations (handled by the skill instructions)
        
        if classification == 'blocked':
            print(f"\n  Worker is BLOCKED. Check iteration log for details.")
            print(f"  Log: {session_dir}/iteration_{iteration}.log")
            log_activity(session_dir, 'blocked', iteration=iteration)
            break
        
        # Increment iteration
        state['iteration'] = iteration + 1
        log_activity(session_dir, 'iteration_end', iteration=iteration, classification=classification)
        
        # Re-read state (worker may have updated it)
        try:
            state = read_state(session_dir)
            state['iteration'] = max(state['iteration'], iteration + 1)
            write_state(session_dir, state)
        except (json.JSONDecodeError, OSError) as e:
            print(f"WARNING: Could not re-read state: {e}")
    
    # Deactivate session
    try:
        state = read_state(session_dir)
        state['active'] = False
        write_state(session_dir, state)
    except (json.JSONDecodeError, OSError):
        pass
    
    elapsed = int(time.time()) - start_time
    log_activity(session_dir, 'session_end', duration_min=round(elapsed / 60))
    print(f"\nSession ended. Duration: {elapsed // 60}m {elapsed % 60}s")
    print(f"Session dir: {session_dir}")


if __name__ == '__main__':
    main()
