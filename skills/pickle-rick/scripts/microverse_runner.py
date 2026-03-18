#!/usr/bin/env python3
"""
Microverse Convergence Runner for Hermes Agent.

Ported from pickle-rick-claude's microverse-runner.ts.
Drives metric optimization by spawning hermes -q iterations,
measuring metrics, and auto-reverting regressions.

Usage:
    python3 microverse_runner.py \
        --metric "pytest --cov=src | tail -1" \
        --task "Improve test coverage to 90%" \
        --working-dir ~/project \
        --direction higher \
        --stall-limit 5
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

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from circuit_breaker import CircuitBreaker


def get_git_head(working_dir: str) -> str:
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True,
            cwd=working_dir, timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else ''
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ''


def git_reset_hard(working_dir: str, sha: str) -> bool:
    try:
        result = subprocess.run(
            ['git', 'reset', '--hard', sha],
            capture_output=True, text=True,
            cwd=working_dir, timeout=30
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def measure_metric(validation_cmd: str, working_dir: str, timeout: int = 60) -> float:
    """Run the metric command and parse the numeric score from the last line."""
    try:
        result = subprocess.run(
            ['bash', '-c', validation_cmd],
            capture_output=True, text=True,
            cwd=working_dir, timeout=timeout
        )
        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip()
        
        # Get last line
        last_line = output.strip().split('\n')[-1] if output else ''
        
        # Extract first number from last line
        numbers = re.findall(r'[\d.]+', last_line)
        if numbers:
            return float(numbers[0])
        return 0.0
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return 0.0


def compare_metric(current: float, previous: float, tolerance: float,
                   direction: str = 'higher') -> str:
    """Compare metrics respecting direction."""
    if direction == 'lower':
        if current < previous - tolerance:
            return 'improved'
        if current > previous + tolerance:
            return 'regressed'
        return 'held'
    else:
        if current > previous + tolerance:
            return 'improved'
        if current < previous - tolerance:
            return 'regressed'
        return 'held'


def read_microverse_state(session_dir: Path) -> dict:
    path = session_dir / 'microverse.json'
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise RuntimeError(f"Failed to read microverse.json: {e}") from e


def write_microverse_state(session_dir: Path, state: dict) -> None:
    path = session_dir / 'microverse.json'
    tmp = path.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps(state, indent=2))
        os.rename(str(tmp), str(path))
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        path.write_text(json.dumps(state, indent=2))


def build_handoff(mv_state: dict, session_dir: Path, iteration: int) -> str:
    """Build handoff context for the microverse worker."""
    metric = mv_state['key_metric']
    history = mv_state['convergence']['history']
    recent = history[-5:] if history else []
    failed = mv_state.get('failed_approaches', [])
    
    lines = [
        "# Microverse Handoff",
        "",
        f"## Metric",
        f"- Description: {metric['description']}",
        f"- Validation: {metric['validation']}",
        f"- Type: {metric['type']}",
        f"- Direction: {metric.get('direction', 'higher')} is better",
        f"- Tolerance: {metric.get('tolerance', 0)}",
        "",
        f"## State",
        f"- Status: {mv_state['status']}",
        f"- Iteration: {iteration}",
        f"- Baseline Score: {mv_state.get('baseline_score', 'N/A')}",
        f"- Stall Counter: {mv_state['convergence']['stall_counter']} / {mv_state['convergence']['stall_limit']}",
        "",
    ]
    
    if recent:
        lines.append("## Recent Metric History")
        for h in recent:
            lines.append(f"- Iter {h['iteration']}: score={h['score']} action={h['action']} — {h['description']}")
        lines.append("")
    
    if failed:
        lines.append("## Failed Approaches (DO NOT RETRY)")
        for f_item in failed[-10:]:
            lines.append(f"- {f_item}")
        lines.append("")
    
    if mv_state.get('gap_analysis_path'):
        lines.append(f"## Gap Analysis: {mv_state['gap_analysis_path']}")
    if mv_state.get('prd_path'):
        lines.append(f"## PRD: {mv_state['prd_path']}")
    
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


def run_worker(session_dir: Path, mv_state: dict, state: dict,
               iteration: int, timeout: int = 1200) -> str:
    """Spawn a hermes -q worker for one microverse iteration."""
    handoff = build_handoff(mv_state, session_dir, iteration)
    persona = load_persona()
    
    phase = "Gap Analysis" if mv_state['status'] == 'gap_analysis' else "Optimization"
    
    prompt = f"""You are a Microverse Worker running iteration {iteration} ({phase}).

{persona}

Load the pickle-rick-microverse skill: skill_view(name='pickle-rick-microverse')

SESSION: {session_dir}
WORKING DIRECTORY: {state['working_dir']}

{handoff}

INSTRUCTIONS:
{"Perform gap analysis: understand the codebase and metric, make initial improvements, commit." if mv_state['status'] == 'gap_analysis' else "Make ONE targeted improvement. Check failed approaches. Implement, commit. Do NOT run the metric command — the orchestrator measures after you."}

Signal completion with [TASK_COMPLETED] when done.
Signal [BLOCKED] if you cannot make progress.
"""
    
    cmd = ['hermes', 'chat', '-q', prompt]
    
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=state['working_dir']
        )
        output = result.stdout + result.stderr
        log_file = session_dir / f'microverse_iter_{iteration}.log'
        log_file.write_text(output)
        return output
    except subprocess.TimeoutExpired:
        return f"Iteration {iteration} timed out after {timeout}s"
    except FileNotFoundError:
        print("ERROR: 'hermes' command not found.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Microverse Convergence Runner')
    parser.add_argument('--metric', help='Shell command for metric (stdout last line = score)')
    parser.add_argument('--goal', help='Natural language goal for LLM judge')
    parser.add_argument('--task', '-t', help='Task description (what to optimize)')
    parser.add_argument('--working-dir', '-w', help='Working directory')
    parser.add_argument('--direction', default='higher', choices=['higher', 'lower'])
    parser.add_argument('--tolerance', type=float, default=0)
    parser.add_argument('--stall-limit', type=int, default=5)
    parser.add_argument('--max-iterations', type=int, default=500)
    parser.add_argument('--timeout', type=int, default=1200)
    parser.add_argument('--resume', help='Resume existing session')
    
    args = parser.parse_args()
    
    if args.resume:
        session_dir = Path(args.resume)
        try:
            state = json.loads((session_dir / 'state.json').read_text())
            mv_state = read_microverse_state(session_dir)
        except (json.JSONDecodeError, OSError, RuntimeError) as e:
            print(f"ERROR: Failed to read session state: {e}")
            sys.exit(1)
        print(f"Resuming microverse session: {session_dir}")
    else:
        if not args.task:
            print("ERROR: --task is required for new sessions")
            sys.exit(1)
        if not args.metric and not args.goal:
            print("ERROR: --metric or --goal is required")
            sys.exit(1)
        if args.metric and args.goal:
            print("ERROR: --metric and --goal are mutually exclusive")
            sys.exit(1)
        
        # Init session via pickle_state.py
        working_dir = args.working_dir or os.getcwd()
        init_cmd = [
            sys.executable, str(SCRIPTS_DIR / 'pickle_state.py'),
            'init', '--task', args.task,
            '--working-dir', working_dir,
            '--max-iterations', str(args.max_iterations),
        ]
        result = subprocess.run(init_cmd, capture_output=True, text=True, timeout=30)
        for line in result.stdout.strip().split('\n'):
            if line.startswith('SESSION_DIR='):
                session_dir = Path(line.split('=', 1)[1])
                break
        else:
            print(f"ERROR: Could not parse SESSION_DIR:\n{result.stdout}")
            sys.exit(1)
        
        try:
            state = json.loads((session_dir / 'state.json').read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"ERROR: Failed to read state after init: {e}")
            sys.exit(1)
        
        metric_type = 'command' if args.metric else 'llm'
        validation = args.metric or args.goal
        
        mv_state = {
            'status': 'gap_analysis',
            'prd_path': str(session_dir / 'prd.md'),
            'key_metric': {
                'description': args.task,
                'validation': validation,
                'type': metric_type,
                'timeout_seconds': 60,
                'tolerance': args.tolerance,
                'direction': args.direction,
            },
            'convergence': {
                'stall_limit': args.stall_limit,
                'stall_counter': 0,
                'history': [],
            },
            'gap_analysis_path': str(session_dir / 'gap_analysis.md'),
            'failed_approaches': [],
            'baseline_score': 0,
            'exit_reason': None,
        }
        
        # Write PRD
        prd_content = f"""# Microverse Optimization PRD

## Objective
{args.task}

## Key Metric
- **Type**: {metric_type}
- **Validation**: `{validation}`
- **Direction**: {args.direction} is better
- **Tolerance**: {args.tolerance}
- **Stall Limit**: {args.stall_limit}
"""
        (session_dir / 'prd.md').write_text(prd_content)
        write_microverse_state(session_dir, mv_state)
        print(f"New microverse session: {session_dir}")
    
    # Signal handling
    shutdown = False
    def handle_signal(signum, frame):
        nonlocal shutdown
        shutdown = True
        print("\nShutting down...")
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    working_dir = state['working_dir']
    metric_cmd = mv_state['key_metric']['validation']
    metric_type = mv_state['key_metric']['type']
    direction = mv_state['key_metric'].get('direction', 'higher')
    tolerance = mv_state['key_metric'].get('tolerance', 0)
    stall_limit = mv_state['convergence']['stall_limit']
    
    print(f"\nMicroverse Convergence Runner")
    print(f"Task: {mv_state['key_metric']['description']}")
    print(f"Metric: {metric_cmd}")
    print(f"Direction: {direction} is better")
    print(f"Stall limit: {stall_limit}")
    print(f"{'=' * 60}")
    
    # Measure baseline if new
    if mv_state['status'] == 'gap_analysis' and metric_type == 'command':
        baseline = measure_metric(metric_cmd, working_dir)
        mv_state['baseline_score'] = baseline
        write_microverse_state(session_dir, mv_state)
        print(f"Baseline score: {baseline}")
    
    iteration = state.get('iteration', 0)
    max_iter = args.max_iterations if not args.resume else state.get('max_iterations', 500)
    accepted = 0
    reverted = 0
    best_score = mv_state.get('baseline_score', 0)
    
    while not shutdown and iteration < max_iter:
        pre_sha = get_git_head(working_dir)
        
        print(f"\n--- Iteration {iteration} | Status: {mv_state['status']} | Stall: {mv_state['convergence']['stall_counter']}/{stall_limit} ---")
        
        # Run worker
        output = run_worker(session_dir, mv_state, state, iteration, args.timeout)
        
        if '[BLOCKED]' in output:
            print("Worker BLOCKED. Stopping.")
            mv_state['status'] = 'stopped'
            mv_state['exit_reason'] = 'blocked'
            break
        
        post_sha = get_git_head(working_dir)
        
        # Measure metric (only for command type)
        if metric_type == 'command':
            score = measure_metric(metric_cmd, working_dir,
                                   mv_state['key_metric'].get('timeout_seconds', 60))
        else:
            score = 0  # LLM judge would go here
        
        # Get previous score
        history = mv_state['convergence']['history']
        accepted_entries = [h for h in history if h['action'] == 'accept']
        prev_score = accepted_entries[-1]['score'] if accepted_entries else mv_state.get('baseline_score', 0)
        
        # Compare
        if mv_state['status'] == 'gap_analysis':
            # Gap analysis always accepted
            comparison = 'improved' if score > prev_score else 'held'
            mv_state['baseline_score'] = score if not accepted_entries else mv_state['baseline_score']
            mv_state['status'] = 'iterating'
            action = 'accept'
            print(f"  Gap analysis complete. Score: {score}")
        else:
            comparison = compare_metric(score, prev_score, tolerance, direction)
            
            if comparison == 'regressed':
                action = 'revert'
                if pre_sha and pre_sha != post_sha:
                    git_reset_hard(working_dir, pre_sha)
                description = f"Reverted (score {score} vs prev {prev_score})"
                mv_state['failed_approaches'].append(
                    f"Iter {iteration}: score went from {prev_score} to {score}"
                )
                mv_state['convergence']['stall_counter'] += 1
                reverted += 1
                print(f"  REGRESSED: {score} (was {prev_score}) — reverted")
            else:
                action = 'accept'
                if comparison == 'improved':
                    mv_state['convergence']['stall_counter'] = 0
                    if (direction == 'higher' and score > best_score) or \
                       (direction == 'lower' and score < best_score):
                        best_score = score
                    print(f"  IMPROVED: {score} (was {prev_score})")
                else:
                    mv_state['convergence']['stall_counter'] += 1
                    print(f"  HELD: {score} (was {prev_score})")
                accepted += 1
        
        # Record history
        entry = {
            'iteration': iteration,
            'metric_value': str(score),
            'score': score,
            'action': action,
            'description': f"Iteration {iteration}",
            'pre_iteration_sha': pre_sha,
            'timestamp': datetime.datetime.now().isoformat(),
        }
        mv_state['convergence']['history'].append(entry)
        write_microverse_state(session_dir, mv_state)
        
        # Check convergence
        if mv_state['convergence']['stall_counter'] >= stall_limit:
            mv_state['status'] = 'converged'
            mv_state['exit_reason'] = 'converged'
            print(f"\n  Converged after {iteration + 1} iterations (stall limit reached)")
            break
        
        iteration += 1
        state['iteration'] = iteration
        (session_dir / 'state.json').write_text(json.dumps(state, indent=2))
    
    if iteration >= max_iter:
        mv_state['status'] = 'stopped'
        mv_state['exit_reason'] = 'limit_reached'
    
    write_microverse_state(session_dir, mv_state)
    
    print(f"\n{'=' * 60}")
    print(f"  Microverse Complete")
    print(f"  Status: {mv_state['status']}")
    print(f"  Reason: {mv_state.get('exit_reason', 'N/A')}")
    print(f"  Iterations: {iteration}")
    print(f"  Baseline: {mv_state.get('baseline_score', 'N/A')}")
    print(f"  Best Score: {best_score}")
    print(f"  Accepted: {accepted} | Reverted: {reverted}")
    print(f"  Session: {session_dir}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
