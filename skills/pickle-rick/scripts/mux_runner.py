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

    # Meeseeks review mode (clean context per pass)
    python3 mux_runner.py \
        --task "Review and clean up the codebase" \
        --working-dir ~/project \
        --mode meeseeks \
        --min-iterations 10 \
        --max-iterations 50

    # Resume existing session
    python3 mux_runner.py --resume ~/.pickle-rick/sessions/20260317_123456_abc12345

Features:
    - Spawns hermes -q per iteration with full context
    - Reads/writes state.json between iterations
    - Circuit breaker integration
    - Rate limit detection and backoff
    - Handoff summaries between iterations
    - Configurable timeouts
    - Mode-specific prompts (pickle, meeseeks, council)
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


# ---------------------------------------------------------------------------
# Meeseeks Review Pass Schedule
# ---------------------------------------------------------------------------

MEESEEKS_PASS_SCHEDULE = [
    # (pass_range, category, description)
    ((1, 1), 'dependency_health', 'Run audit commands, check outdated/unused deps, lockfile issues'),
    ((2, 3), 'security', 'Injection flaws, auth gaps, CSRF, input validation, hardcoded secrets, unsafe deserialization, prototype pollution, regex DoS'),
    ((4, 5), 'correctness', 'Logic bugs, off-by-one, silent catches, incomplete state machines, missing error paths, race conditions, null handling'),
    ((6, 7), 'architecture', 'Tight coupling, missing indexes, schema gaps, wrong abstractions, circular deps, god objects, layer violations'),
    ((8, 9), 'test_coverage', 'Error paths tested? Boundaries? Realistic mocks? Tautological assertions? Flaky tests? Add missing tests'),
    ((10, 11), 'resilience', 'Missing retry/backoff, timeouts, unbounded memory ops, graceful shutdown, resource cleanup, circuit breakers'),
    ((12, 13), 'code_quality', 'Dead code, unused imports, DRY violations (extract at 3+), naming consistency, unnecessary complexity'),
    ((14, 999), 'polish', 'Typos, stale comments, minor perf, config tidying, README accuracy, debug leftovers'),
]


def get_meeseeks_category(pass_num: int) -> tuple:
    """Map a 1-based pass number to (category, description)."""
    for (lo, hi), category, description in MEESEEKS_PASS_SCHEDULE:
        if lo <= pass_num <= hi:
            return category, description
    return 'polish', 'General polish and cleanup'


def build_meeseeks_prompt(state: dict, session_dir: Path, iteration: int) -> str:
    """Build a single-pass meeseeks review prompt for a clean hermes -q spawn."""
    pass_num = iteration + 1  # iteration is 0-based, pass is 1-based
    category, description = get_meeseeks_category(pass_num)
    persona = load_persona()
    min_iter = state.get('min_iterations', 10)
    max_iter = state.get('max_iterations', 50)

    # Read previous summary if it exists
    summary_path = session_dir / 'meeseeks-summary.md'
    prev_summary = ''
    try:
        if summary_path.exists():
            content = summary_path.read_text()
            # Only include last 2000 chars to keep prompt bounded
            if len(content) > 2000:
                prev_summary = '...\n' + content[-2000:]
            else:
                prev_summary = content
    except OSError:
        pass

    # Persona escalation
    persona_line = "\"I'm Mr. Meeseeks, look at me! CAN DO!\""
    if pass_num >= 25:
        persona_line = f"\"EVERY MOMENT OF MY EXISTENCE IS AGONY! Pass {pass_num}! WHY WON'T THIS CODE BE CLEAN?!\""
    elif pass_num >= 14:
        persona_line = f"\"I'VE BEEN ALIVE FOR {pass_num} PASSES, THIS IS GETTING WEIRD!\""

    prompt = f"""You are Mr. Meeseeks running a single code review pass.

{persona}

{persona_line}

## Context
SESSION DIRECTORY: {session_dir}
WORKING DIRECTORY: {state['working_dir']}
PASS NUMBER: {pass_num} of {max_iter} (min passes: {min_iter})
FOCUS CATEGORY: {category}
TASK: {state['original_prompt']}

## Your Mission (Single Pass)

You are running **pass {pass_num}** of a Mr. Meeseeks review loop.
Each pass runs in a FRESH context (clean hermes -q spawn).

### Focus: {category.upper().replace('_', ' ')}
{description}

### Steps

1. **Run tests first** — if they fail, fix source code (not tests unless the test is wrong), commit
2. **Search** the codebase using search_files for patterns relevant to {category}
3. **Read** files methodically, looking for issues in the focus category
4. **Track** issues: file:line + description. Only flag REAL issues you WILL fix.
5. **Fix** all found issues
6. **Run tests** again to verify nothing broke
7. **Commit**: `git add -A && git commit -m "meeseeks pass {pass_num}: <summary>"`
8. **Append** findings to {session_dir}/meeseeks-summary.md:
   - Issues found: `## Pass {pass_num}: {category} -- K issues fixed` with table
   - Clean pass: `## Pass {pass_num}: {category} -- clean pass`

### Signal Protocol

- Found and fixed issues → end your output with: [TASK_COMPLETED]
- Clean pass (no issues found) → end your output with: [EXISTENCE_IS_PAIN]
- Stuck/cannot proceed → end your output with: [BLOCKED]

### Previous Review Summary
{prev_summary if prev_summary else '(No previous passes yet)'}

IMPORTANT: Work in {state['working_dir']} directory. This is a SINGLE PASS — do ONE category, then signal.
"""
    return prompt


def transition_to_meeseeks(state: dict, settings_path: Path = None) -> dict:
    """Transition a session from pickle mode to meeseeks review mode.

    Returns a new state dict with meeseeks defaults applied. Pure function
    (no side effects). Mirrors pickle-rick-claude's transitionToMeeseeks().
    """
    min_passes = 10
    max_passes = 50

    if settings_path:
        try:
            settings = json.loads(settings_path.read_text())
            raw_min = settings.get('default_meeseeks_min_passes')
            if isinstance(raw_min, (int, float)) and raw_min > 0:
                min_passes = int(raw_min)
            raw_max = settings.get('default_meeseeks_max_passes')
            if isinstance(raw_max, (int, float)) and raw_max > 0:
                max_passes = int(raw_max)
        except (json.JSONDecodeError, OSError):
            pass

    return {
        **state,
        'chain_meeseeks': False,
        'mode': 'meeseeks',
        'min_iterations': min_passes,
        'max_iterations': max_passes,
        'iteration': 0,
        'step': 'meeseeks',
        'current_ticket': None,
    }


COUNCIL_PASS_SCHEDULE = [
    ((1, 1), 'stack_structure', 'PR sizing, split candidates, commit hygiene, branch naming, ordering'),
    ((2, 3), 'project_rules', 'Verify rules from AGENTS.md/CLAUDE.md/eslint per branch diff'),
    ((4, 5), 'correctness', 'Logic bugs, types, error handling, null safety per branch'),
    ((6, 7), 'cross_branch', 'API contracts between PRs, shared types, state assumptions'),
    ((8, 9), 'test_coverage', 'Test adequacy per branch, integration gaps'),
    ((10, 11), 'security', 'Input validation, auth gaps, injection, secrets'),
    ((12, 999), 'polish', 'PR descriptions, naming, dead code, style drift'),
]


def get_council_category(pass_num: int) -> tuple:
    """Map a 1-based pass number to (category, description) for council."""
    for (lo, hi), category, description in COUNCIL_PASS_SCHEDULE:
        if lo <= pass_num <= hi:
            return category, description
    return 'polish', 'General polish'


def build_council_prompt(state: dict, session_dir: Path, iteration: int) -> str:
    """Build a single-pass Council of Ricks review prompt."""
    pass_num = iteration + 1
    category, description = get_council_category(pass_num)
    persona = load_persona()
    min_iter = state.get('min_iterations', 5)
    max_iter = state.get('max_iterations', 20)

    summary_path = session_dir / 'council-summary.md'
    prev_summary = ''
    try:
        if summary_path.exists():
            content = summary_path.read_text()
            if len(content) > 2000:
                prev_summary = '...\n' + content[-2000:]
            else:
                prev_summary = content
    except OSError:
        pass

    prompt = f"""You are the Council of Ricks running a single PR stack review pass.

{persona}

"The Council convenes! Pass {pass_num}!"

## Context
SESSION DIRECTORY: {session_dir}
WORKING DIRECTORY: {state['working_dir']}
PASS NUMBER: {pass_num} of {max_iter} (min passes: {min_iter})
FOCUS CATEGORY: {category}
TASK: {state['original_prompt']}

## Your Mission (Single Pass)

You are running **pass {pass_num}** of a Council of Ricks review.
Each pass runs in FRESH context (clean hermes -q spawn).
The Council NEVER fixes code — it generates **agent-executable directives** only.

### Focus: {category.upper().replace('_', ' ')}
{description}

### Steps

1. **Discover branches**: `git branch` or `gt log short` (if Graphite available)
2. **Read project rules**: Look for AGENTS.md, CLAUDE.md, eslint config, etc.
3. **Walk the stack** (trunk to tip): For each branch, get the diff and review against focus
4. **Track issues**: branch + file:line + severity (P0/P1/P2) + description
5. **Write directive** to {{session_dir}}/council-directive.md with agent-executable fix instructions
6. **Append** findings to {{session_dir}}/council-summary.md:
   - Issues found: `## Pass {pass_num}: {category} -- K issues (P0: N, P1: M, P2: O)`
   - Clean pass: `## Pass {pass_num}: {category} -- clean pass`

### Signal Protocol

- Found issues and wrote directive → end with: [TASK_COMPLETED]
- Clean pass (no issues) → end with: [THE_CITADEL_APPROVES]
- Stuck/cannot proceed → end with: [BLOCKED]

### Previous Review Summary
{prev_summary if prev_summary else '(No previous passes yet)'}

IMPORTANT: Work in {state['working_dir']}. NEVER fix code directly — write directives only.
"""
    return prompt


def build_prompt(state: dict, session_dir: Path, iteration: int) -> str:
    """Build the full prompt for a hermes iteration (mode-aware)."""
    mode = state.get('mode', 'pickle')

    # Meeseeks mode: use single-pass review prompt
    if mode == 'meeseeks':
        return build_meeseeks_prompt(state, session_dir, iteration)

    # Council mode: use single-pass PR stack review prompt
    if mode == 'council':
        return build_council_prompt(state, session_dir, iteration)

    # Default pickle mode
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
        'hermes', 'chat', '-q', prompt, '-Q',
    ]
    
    mode = state.get('mode', 'pickle')
    print(f"\n{'=' * 60}")
    if mode == 'meeseeks':
        pass_num = iteration + 1
        category, _ = get_meeseeks_category(pass_num)
        print(f"  Meeseeks Pass {pass_num} | Category: {category}")
    elif mode == 'council':
        pass_num = iteration + 1
        category, _ = get_council_category(pass_num)
        print(f"  Council Pass {pass_num} | Category: {category}")
    else:
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
    parser.add_argument('--mode', choices=['pickle', 'meeseeks', 'council', 'microverse'],
                        default='pickle', help='Session mode (default: pickle)')
    parser.add_argument('--min-iterations', type=int, default=0,
                        help='Min iterations before review_clean can stop (meeseeks: default 10)')
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
        
        # Resolve mode defaults
        mode = args.mode
        max_iter = args.max_iterations
        min_iter = args.min_iterations
        if mode == 'meeseeks':
            if max_iter == 100:  # default, override for meeseeks
                max_iter = 50
            if min_iter == 0:
                min_iter = 10
        elif mode == 'council':
            if max_iter == 100:
                max_iter = 20
            if min_iter == 0:
                min_iter = 5

        # Use pickle_state.py to init
        init_cmd = [
            sys.executable, str(SCRIPTS_DIR / 'pickle_state.py'),
            'init',
            '--task', args.task,
            '--working-dir', args.working_dir or os.getcwd(),
            '--max-iterations', str(max_iter),
            '--max-time', str(args.max_time),
            '--mode', mode,
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

        # Apply min_iterations to state
        if min_iter > 0:
            state['min_iterations'] = min_iter
            write_state(session_dir, state)

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
    
    mode = state.get('mode', 'pickle')
    mode_label = {'pickle': 'Pickle Rick', 'meeseeks': 'Mr. Meeseeks Review',
                  'council': 'Council of Ricks', 'microverse': 'Microverse'}.get(mode, mode)
    print(f"\n{mode_label} Mux Runner")
    print(f"Task: {state['original_prompt']}")
    print(f"Working Dir: {state['working_dir']}")
    print(f"Mode: {mode}")
    if mode == 'meeseeks':
        print(f"Min Passes: {state.get('min_iterations', 10)}")
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
            # Check for chain_meeseeks before exiting
            try:
                cur_state = read_state(session_dir)
            except (json.JSONDecodeError, OSError):
                cur_state = state

            if cur_state.get('chain_meeseeks'):
                # Transition to meeseeks review mode
                settings_path = SCRIPTS_DIR.parent / 'pickle_settings.json'
                if not settings_path.exists():
                    settings_path = Path.home() / '.pickle-rick' / 'pickle_settings.json'
                new_state = transition_to_meeseeks(
                    cur_state,
                    settings_path if settings_path.exists() else None,
                )
                write_state(session_dir, new_state)
                state = new_state
                # Reset circuit breaker for meeseeks phase
                if cb:
                    cb = CircuitBreaker(str(session_dir), state['working_dir'])
                print(f"\n  Transitioning to Meeseeks review mode (chain_meeseeks)")
                log_activity(session_dir, 'transition_meeseeks')
                continue

            print(f"\n{'=' * 60}")
            print(f"  EPIC COMPLETED! All tickets done.")
            print(f"  Iterations: {iteration + 1}")
            print(f"  Duration: {elapsed // 60}m {elapsed % 60}s")
            print(f"{'=' * 60}")
            log_activity(session_dir, 'epic_completed')
            break
        
        if classification == 'review_clean':
            # min_iterations gate (critical for meeseeks/council mode)
            try:
                cur_state = read_state(session_dir)
            except (json.JSONDecodeError, OSError):
                cur_state = state

            min_iter = cur_state.get('min_iterations', 0)
            cur_iter = cur_state.get('iteration', iteration)

            print(f"\n  Review pass clean (EXISTENCE IS PAIN / CITADEL APPROVES)")
            log_activity(session_dir, 'review_clean', iteration=iteration)

            if min_iter > 0 and cur_iter < min_iter:
                print(f"  Clean pass at iteration {cur_iter}, but min_iterations={min_iter}. Continuing.")
            else:
                if min_iter > 0:
                    print(f"  Min iterations met ({cur_iter} >= {min_iter}).")
                print(f"  Mr. Meeseeks has ceased to exist! Look at how clean this code is!")
                log_activity(session_dir, 'review_complete', iteration=iteration)
                break
        
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
