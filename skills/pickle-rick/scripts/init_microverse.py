#!/usr/bin/env python3
"""
Initialize microverse.json for convergence optimization sessions.

Ported from pickle-rick-claude's init-microverse.js (v1.28.0).
Used by szechuan-sauce and microverse skills.

Usage:
    python3 init_microverse.py <session-dir> <target-path> [--stall-limit N] [--convergence-target N] [--judge-context PATH]

Example:
    python3 init_microverse.py ~/.pickle-rick/sessions/20260115_120000_abc123 ./src --stall-limit 5 --convergence-target 0
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any


DEFAULT_METRIC = {
    'description': 'Number of coding principle violations (lower is better)',
    'validation': 'Review the code at the target path for violations of established coding principles (KISS, YAGNI, DRY, SOLID, Small Functions, Guard Clauses, Cognitive Load, Self-Documenting Code, Encapsulation, Fail-Fast, etc). Count only REAL, actionable violations — not style nitpicks. A violation must be fixable and must clearly hurt readability, maintainability, or correctness. Score = number of violations found.',
    'type': 'llm',
    'timeout_seconds': 300,
    'tolerance': 0,
    'direction': 'lower',
    'judge_model': 'claude-sonnet-4-6',
}


def create_microverse_state(
    prd_path: str,
    metric: Dict[str, Any],
    stall_limit: int,
    convergence_target: Optional[int] = None
) -> Dict[str, Any]:
    """Create a fresh microverse state object."""
    if not isinstance(stall_limit, int) or stall_limit < 1:
        raise ValueError(f'stall_limit must be a positive integer, got {stall_limit}')

    tolerance = metric.get('tolerance', 0)
    if not isinstance(tolerance, (int, float)) or tolerance < 0:
        raise ValueError(f'tolerance must be a non-negative number, got {tolerance}')

    state = {
        'status': 'gap_analysis',
        'prd_path': prd_path,
        'key_metric': {
            **metric,
            'direction': metric.get('direction', 'higher'),
        },
        'convergence': {
            'stall_limit': stall_limit,
            'stall_counter': 0,
            'history': [],
        },
        'gap_analysis_path': '',
        'failed_approaches': [],
        'baseline_score': 0,
    }

    if convergence_target is not None:
        state['convergence_target'] = convergence_target

    return state


def write_microverse_state(session_dir: Path, state: Dict[str, Any]) -> None:
    """Write microverse.json to the session directory atomically."""
    microverse_path = session_dir / 'microverse.json'
    tmp_path = session_dir / f'microverse.json.tmp.{os.getpid()}'
    tmp_path.write_text(json.dumps(state, indent=2))
    os.replace(str(tmp_path), str(microverse_path))


def parse_metric_json(json_str: str) -> Dict[str, Any]:
    """Parse metric JSON, falling back to defaults for missing fields."""
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid JSON in --metric-json: {e}')

    # Merge with defaults for any missing fields
    return {**DEFAULT_METRIC, **parsed}


def main():
    parser = argparse.ArgumentParser(
        description='Initialize microverse.json for convergence optimization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Environment:
    SESSIONS_ROOT defaults to ~/.pickle-rick/sessions

Returns:
    Exits with 0 on success, 1 on error. Prints "microverse.json created" on success.
'''
    )

    parser.add_argument('session_dir', help='Session directory path')
    parser.add_argument('target_path', help='Target file/directory to optimize')
    parser.add_argument('--stall-limit', type=int, default=5,
                        help='Stall limit (default: 5)')
    parser.add_argument('--convergence-target', type=float,
                        help='Convergence target value (optional)')
    parser.add_argument('--metric-json', type=str,
                        help='JSON string for custom metric definition (merged with defaults)')
    parser.add_argument('--judge-context', type=str,
                        help='Path to judge context/principles file')

    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    if not session_dir.exists():
        print(f'ERROR: Session directory does not exist: {session_dir}', file=sys.stderr)
        sys.exit(1)

    target_path = Path(args.target_path)
    if not target_path.exists():
        print(f'ERROR: Target path does not exist: {target_path}', file=sys.stderr)
        sys.exit(1)

    # Determine metric to use
    if args.metric_json:
        try:
            metric = parse_metric_json(args.metric_json)
        except ValueError as e:
            print(f'ERROR: {e}', file=sys.stderr)
            sys.exit(1)
    else:
        metric = DEFAULT_METRIC.copy()

    # Ensure direction is set
    if 'direction' not in metric:
        metric['direction'] = 'higher'

    # Create state
    try:
        convergence_target = args.convergence_target if args.convergence_target is not None else None
        state = create_microverse_state(
            prd_path=str(target_path.resolve()),
            metric=metric,
            stall_limit=args.stall_limit,
            convergence_target=convergence_target
        )

        # Set gap analysis path
        state['gap_analysis_path'] = str(session_dir / 'gap_analysis.md')

        # Set judge context path if provided
        if args.judge_context:
            state['key_metric']['judge_context_path'] = args.judge_context

        write_microverse_state(session_dir, state)
        print('microverse.json created')

    except ValueError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'ERROR: Failed to create microverse.json: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
