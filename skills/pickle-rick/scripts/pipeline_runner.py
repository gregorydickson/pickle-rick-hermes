#!/usr/bin/env python3
"""
Pickle Rick Pipeline Runner for Hermes Agent.

Ported from pickle-rick-claude v1.44.2 pipeline-runner.js (commit 2da7fe5).
Orchestrates sequential phases: pickle -> anatomy-park -> szechuan-sauce.
Each phase runs as a child process with state reset and artifact archival.
Pipeline stops on first phase failure (matching JS behavior).

Usage:
    python3 pipeline_runner.py \
        --task "Build feature X" \
        --working-dir ~/project \
        --phases pickle,anatomy-park,szechuan-sauce \
        --max-time 720 \
        --max-iterations 100
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from pickle_state import locked_read, locked_write
try:
    from scope_resolver import resolve_scope, refresh_scope
except ImportError:
    resolve_scope = None
    refresh_scope = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PHASES = ['pickle', 'anatomy-park', 'szechuan-sauce']
PHASE_TIMEOUT_DEFAULT = 1200  # 20 minutes per phase iteration

# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------

def parse_pipeline_config(phases_str: str) -> List[str]:
    """Parse comma-separated phase string into validated list."""
    phases = [p.strip() for p in phases_str.split(',') if p.strip()]
    valid = {'pickle', 'anatomy-park', 'szechuan-sauce'}
    return [p for p in phases if p in valid]


def archive_phase_artifacts(session_dir: Path, phase: str) -> None:
    """Archive previous phase artifacts into a timestamped subdir."""
    archive_dir = session_dir / 'archive' / f"{phase}_{int(time.time())}"
    try:
        archive_dir.mkdir(parents=True, exist_ok=True)
        # Copy iteration logs
        for log in session_dir.glob('iteration_*.log'):
            try:
                dest = archive_dir / log.name
                dest.write_text(log.read_text())
                log.unlink()
            except OSError:
                pass
        # Copy microverse logs if present
        for log in session_dir.glob('microverse_iter_*.log'):
            try:
                dest = archive_dir / log.name
                dest.write_text(log.read_text())
                log.unlink()
            except OSError:
                pass
        # Write archive manifest
        manifest = archive_dir / 'manifest.json'
        manifest.write_text(json.dumps({
            'phase': phase,
            'archived_at': int(time.time()),
            'session_dir': str(session_dir),
        }, indent=2))
    except OSError:
        pass


def clean_phase_artifacts(session_dir: Path) -> None:
    """Remove stale context files that could pollute the next phase."""
    stale = ['TASK_NOTES.md', 'gap_analysis.md', 'handoff.txt',
             'council-directive.md', 'council-summary.md',
             'meeseeks-summary.md']
    for name in stale:
        try:
            (session_dir / name).unlink(missing_ok=True)
        except OSError:
            pass


def reset_state_for_phase(session_dir: Path, phase: str) -> None:
    """Reset state for the next phase. Matches JS resetStateForPhase."""
    state_path = session_dir / 'state.json'
    try:
        state = locked_read(state_path)
        state['iteration'] = 0
        state['active'] = True
        state['current_ticket'] = None
        state['start_time_epoch'] = int(time.time())
        state['chain_meeseeks'] = False
        state['tmux_mode'] = True
        if phase == 'pickle':
            state['mode'] = 'pickle'
            state['command_template'] = None
            state['step'] = 'prd'
            state['max_iterations'] = state.get('max_iterations', 100)
        elif phase == 'anatomy-park':
            state['mode'] = 'microverse'
            state['command_template'] = 'anatomy-park'
            state['step'] = 'review'
            state['max_iterations'] = state.get('max_iterations', 100)
        elif phase == 'szechuan-sauce':
            state['mode'] = 'microverse'
            state['command_template'] = 'szechuan-sauce'
            state['step'] = 'review'
            state['max_iterations'] = state.get('max_iterations', 50)
        locked_write(state_path, state)
    except (OSError, json.JSONDecodeError):
        pass


def discover_subsystems(working_dir: str) -> List[str]:
    """
    Scan immediate subdirectories for subsystems.
    A subsystem is a direct child directory with 3+ source files.
    Exclude: node_modules, dist, build, .next, coverage, __pycache__, .git.
    """
    wd = Path(working_dir)
    exclude = {'node_modules', 'dist', 'build', '.next', 'coverage',
               '__pycache__', '.git', 'venv', '.venv'}
    source_exts = {'.ts', '.js', '.py', '.go', '.rs', '.java',
                   '.tsx', '.jsx'}
    subsystems = []
    for child in wd.iterdir():
        if not child.is_dir() or child.name in exclude:
            continue
        source_count = sum(
            1 for f in child.rglob('*')
            if f.is_file() and f.suffix in source_exts
        )
        if source_count >= 3:
            subsystems.append(str(child.relative_to(wd)))
    return subsystems


def has_source_files(working_dir: str) -> bool:
    """Check if working_dir contains any source files."""
    wd = Path(working_dir)
    source_exts = {'.ts', '.js', '.py', '.go', '.rs', '.java',
                   '.tsx', '.jsx'}
    for f in wd.rglob('*'):
        if f.is_file() and f.suffix in source_exts:
            return True
    return False


def setup_phase_config(session_dir: Path, phase: str, working_dir: str) -> bool:
    """
    Set up phase-specific config. Return True if phase should proceed,
    False if it should be skipped.
    """
    if phase == 'anatomy-park':
        subsystems = discover_subsystems(working_dir)
        if not subsystems:
            print(f"  Skipping anatomy-park: no subsystems found")
            return False
        anatomy_state = {
            'subsystems': subsystems,
            'current_index': 0,
            'pass_counts': {},
            'consecutive_clean': {},
            'stall_counts': {},
            'stall_limit': 3,
            'findings_history': {},
            'trap_doors_added': [],
            'trap_doors_committed': [],
        }
        try:
            (session_dir / 'anatomy-park.json').write_text(
                json.dumps(anatomy_state, indent=2)
            )
        except OSError:
            pass
    elif phase == 'szechuan-sauce':
        if not has_source_files(working_dir):
            print(f"  Skipping szechuan-sauce: no source files found")
            return False
    return True


def warn_dirty_working_tree(working_dir: str) -> None:
    """Warn if working tree has uncommitted changes."""
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=working_dir, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            print("WARNING: Working tree is dirty. Uncommitted changes may be lost.")
    except (subprocess.TimeoutExpired, OSError):
        pass


def write_pipeline_status(session_dir: Path, status: str,
                          current_phase: str = None,
                          overall_exit_code: int = 0) -> None:
    path = session_dir / 'pipeline-status.json'
    data = {
        'status': status,
        'current_phase': current_phase,
        'overall_exit_code': overall_exit_code,
        'updated_at': int(time.time()),
    }
    tmp = path.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp), str(path))
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Pickle Rick Pipeline Runner \u2014 sequential phase orchestration'
    )
    parser.add_argument('--task', '-t',
                        help='Task description (for new sessions)')
    parser.add_argument('--working-dir', '-w',
                        help='Working directory (default: cwd)')
    parser.add_argument('--phases', default='pickle,anatomy-park,szechuan-sauce',
                        help='Comma-separated phase list')
    parser.add_argument('--max-time', type=int, default=720,
                        help='Max total time in minutes')
    parser.add_argument('--max-iterations', type=int, default=100,
                        help='Max iterations per phase')
    parser.add_argument('--resume', help='Resume existing session directory')
    parser.add_argument('--timeout', type=int, default=PHASE_TIMEOUT_DEFAULT,
                        help='Per-phase timeout in seconds')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print phase plan without executing')
    parser.add_argument('--scope', default=None,
                        help='Scope flag for scoped pipeline runs (e.g. branch:strict, diff:main)')

    args = parser.parse_args()

    if not args.resume and not args.task:
        parser.error('the following arguments are required: --task/-t')

    if args.dry_run:
        phases = parse_pipeline_config(args.phases)
        print(f"Dry run: would execute phases in order:")
        for i, phase in enumerate(phases, 1):
            print(f"  {i}. {phase}")
        sys.exit(0)

    phases = parse_pipeline_config(args.phases)
    if not phases:
        print("ERROR: No valid phases specified")
        sys.exit(1)

    # Initialize or resume session
    if args.resume:
        session_dir = Path(args.resume)
        if not (session_dir / 'state.json').exists():
            print(f"ERROR: No state.json found at {session_dir}")
            sys.exit(1)
        try:
            state = locked_read(session_dir / 'state.json')
        except (OSError, json.JSONDecodeError) as e:
            print(f"ERROR: Failed to read state: {e}")
            sys.exit(1)
        working_dir = state.get('working_dir', os.getcwd())
        print(f"Resuming pipeline session: {session_dir}")
    else:
        working_dir = os.path.abspath(args.working_dir or os.getcwd())

        # Force chain_meeseeks off before pickle phase to prevent unwanted
        # transitions during pipeline orchestration.
        init_cmd = [
            sys.executable, str(SCRIPTS_DIR / 'pickle_state.py'),
            'init',
            '--task', args.task,
            '--working-dir', working_dir,
            '--max-iterations', str(args.max_iterations),
            '--max-time', str(args.max_time),
            '--mode', 'pickle',
        ]
        result = subprocess.run(init_cmd, capture_output=True, text=True,
                                timeout=30)
        if result.returncode != 0:
            print(f"ERROR: Failed to initialize session:\n{result.stderr}")
            sys.exit(1)

        for line in result.stdout.strip().split('\n'):
            if line.startswith('SESSION_DIR='):
                session_dir = Path(line.split('=', 1)[1])
                break
        else:
            print("ERROR: Could not parse SESSION_DIR from init output")
            sys.exit(1)

        # Force chain_meeseeks off — pipeline controls transitions, not mux_runner
        try:
            state = locked_read(session_dir / 'state.json')
            state['chain_meeseeks'] = False
            locked_write(session_dir / 'state.json', state)
        except (OSError, json.JSONDecodeError):
            pass

        print(f"New pipeline session: {session_dir}")

    warn_dirty_working_tree(working_dir)

    # Scope setup (no-op stub if scope_resolver not fully ported)
    if args.scope and resolve_scope is not None:
        try:
            resolve_scope(
                scope_flag=args.scope,
                session_root=str(session_dir),
                repo_root=working_dir,
            )
            print(f"  Scope resolved: {args.scope}")
        except Exception as e:
            print(f"WARNING: Scope resolution failed: {e}")

    # Signal handling: write .cancel marker and let child handle cleanup
    cancel_path = session_dir / '.cancel'
    shutdown = False
    active_child = None

    def handle_signal(signum, frame):
        nonlocal shutdown
        shutdown = True
        print(f"\nSignal {signum} received. Writing cancel marker...")
        try:
            cancel_path.write_text(str(signum))
        except OSError:
            pass
        # Delegate cleanup to child process
        if active_child and active_child.poll() is None:
            try:
                active_child.send_signal(signum)
            except OSError:
                pass

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, handle_signal)

    start_epoch = int(time.time())
    max_time_seconds = args.max_time * 60
    overall_exit_code = 0

    write_pipeline_status(session_dir, 'running')

    print(f"\nPipeline Runner")
    print(f"Task: {args.task if not args.resume else state.get('original_prompt', '')}")
    print(f"Phases: {' -> '.join(phases)}")
    print(f"Max time: {args.max_time}m")
    print(f"{'=' * 60}")

    for phase in phases:
        if shutdown:
            print(f"\nShutdown requested. Skipping remaining phases.")
            break

        elapsed = int(time.time()) - start_epoch
        if elapsed >= max_time_seconds:
            print(f"\nTime limit reached ({elapsed // 60}m). Stopping.")
            overall_exit_code = 1
            break

        # Archive artifacts from previous phase
        archive_phase_artifacts(session_dir, phase)

        # Clean stale context files
        clean_phase_artifacts(session_dir)

        # Reset state for this phase
        reset_state_for_phase(session_dir, phase)

        # Per-phase scope refresh (no-op if scope_resolver is stub)
        if args.scope and refresh_scope is not None:
            try:
                refreshed = refresh_scope(str(session_dir), phase)
                if refreshed:
                    print(f"  Scope refreshed for {phase}: {len(refreshed.allowed_paths)} paths")
            except Exception as e:
                print(f"WARNING: Scope refresh failed for {phase}: {e}")

        # Setup phase config and skip if no work
        if not setup_phase_config(session_dir, phase, working_dir):
            print(f"  Phase {phase} skipped")
            continue

        # Run the phase
        active_child = None
        if phase == 'pickle':
            cmd = [sys.executable, str(SCRIPTS_DIR / 'mux_runner.py'),
                   '--resume', str(session_dir)]
        elif phase in ('anatomy-park', 'szechuan-sauce'):
            cmd = [sys.executable, str(SCRIPTS_DIR / 'microverse_runner.py'),
                   '--resume', str(session_dir)]
        else:
            continue

        env = {**os.environ, 'PICKLE_SESSION': str(session_dir),
               'PICKLE_PHASE': phase}

        print(f"\n--- Phase: {phase} ---")

        write_pipeline_status(session_dir, 'running', phase)

        phase_log = session_dir / f'phase_{phase}.log'
        try:
            active_child = subprocess.Popen(
                cmd, cwd=working_dir, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            stdout, _ = active_child.communicate(timeout=args.timeout)
            phase_log.write_bytes(stdout)
            sys.stdout.buffer.write(stdout)
            exit_code = active_child.returncode
        except subprocess.TimeoutExpired:
            print(f"WARNING: Phase {phase} timed out after {args.timeout}s")
            if active_child and active_child.poll() is None:
                active_child.terminate()
                try:
                    active_child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    active_child.kill()
            exit_code = 1
        except FileNotFoundError:
            print(f"ERROR: Command not found for phase {phase}")
            exit_code = 1
        finally:
            active_child = None

        if exit_code != 0:
            print(f"Phase {phase} failed with exit code {exit_code}. Stopping pipeline.")
            overall_exit_code = exit_code
            break

        print(f"Phase {phase} complete (exit code: {exit_code})")

    # Final cleanup
    if cancel_path.exists() and not shutdown:
        try:
            cancel_path.unlink()
        except OSError:
            pass

    write_pipeline_status(session_dir, 'complete', overall_exit_code=overall_exit_code)

    elapsed = int(time.time()) - start_epoch
    print(f"\n{'=' * 60}")
    print(f"  Pipeline Complete")
    print(f"  Duration: {elapsed // 60}m {elapsed % 60}s")
    print(f"  Session: {session_dir}")
    print(f"  Overall exit code: {overall_exit_code}")
    print(f"{'=' * 60}")

    sys.exit(overall_exit_code)


if __name__ == '__main__':
    main()
