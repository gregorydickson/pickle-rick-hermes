#!/usr/bin/env python3
"""
Circuit Breaker for Pickle Rick Autonomous Loop.

Ported from pickle-rick-claude's circuit-breaker.ts.
Monitors git progress and error signatures to prevent infinite loops.

Three states: CLOSED (normal) -> HALF_OPEN (testing) -> OPEN (stopped)

Usage:
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker(session_dir, working_dir)
    if not cb.can_execute():
        print("Circuit OPEN -- stopping")
        sys.exit(1)
    
    # ... run iteration ...
    
    cb.record_result(has_progress=True, error_signature=None)
"""

import json
import os
import subprocess
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


class CircuitBreaker:
    """
    Three-state circuit breaker that monitors iteration progress.
    
    CLOSED:    Normal operation. Tracks consecutive no-progress iterations.
    HALF_OPEN: One test iteration allowed after cool-down.
    OPEN:      Session stopped. No iterations allowed.
    """
    
    # Thresholds
    NO_PROGRESS_THRESHOLD = 3
    SAME_ERROR_THRESHOLD = 3
    HALF_OPEN_AFTER_ITERATIONS = 2
    
    def __init__(self, session_dir: str, working_dir: str):
        self.session_dir = Path(session_dir)
        self.working_dir = Path(working_dir)
        self.state_file = self.session_dir / 'circuit_breaker.json'
        self.state = self._load_or_init()
    
    def _load_or_init(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return self._fresh_state()
    
    def _fresh_state(self) -> Dict[str, Any]:
        return {
            'state': 'CLOSED',
            'last_change': datetime.datetime.now().isoformat(),
            'consecutive_no_progress': 0,
            'consecutive_same_error': 0,
            'last_error_signature': None,
            'last_known_head': self._get_git_head(),
            'last_known_step': None,
            'last_known_ticket': None,
            'last_progress_iteration': 0,
            'total_opens': 0,
            'reason': '',
            'opened_at': None,
            'history': [],
        }
    
    def _save(self) -> None:
        self.state_file.write_text(json.dumps(self.state, indent=2))
    
    def _get_git_head(self) -> str:
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True, text=True,
                cwd=str(self.working_dir), timeout=10
            )
            return result.stdout.strip() if result.returncode == 0 else ''
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ''
    
    def _detect_progress(self, current_step: Optional[str] = None,
                         current_ticket: Optional[str] = None) -> Dict[str, Any]:
        current_head = self._get_git_head()
        
        files_changed = 0
        try:
            for cmd in [['git', 'diff', '--stat'], ['git', 'diff', '--stat', '--cached']]:
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    cwd=str(self.working_dir), timeout=10
                )
                if result.stdout.strip():
                    files_changed += len([l for l in result.stdout.strip().split('\n') if l.strip()])
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        has_progress = (
            current_head != self.state['last_known_head'] or
            files_changed > 0 or
            (current_step and current_step != self.state.get('last_known_step')) or
            (current_ticket and current_ticket != self.state.get('last_known_ticket'))
        )
        
        return {
            'has_progress': has_progress,
            'current_head': current_head,
            'files_changed': files_changed,
            'step_changed': current_step != self.state.get('last_known_step') if current_step else False,
            'ticket_changed': current_ticket != self.state.get('last_known_ticket') if current_ticket else False,
        }
    
    def _transition(self, new_state: str, reason: str, iteration: int = 0) -> None:
        old_state = self.state['state']
        self.state['history'].append({
            'timestamp': datetime.datetime.now().isoformat(),
            'iteration': iteration,
            'from': old_state,
            'to': new_state,
            'reason': reason,
        })
        self.state['state'] = new_state
        self.state['last_change'] = datetime.datetime.now().isoformat()
        self.state['reason'] = reason
        
        if new_state == 'OPEN':
            self.state['total_opens'] += 1
            self.state['opened_at'] = datetime.datetime.now().isoformat()
    
    def can_execute(self) -> bool:
        if self.state['state'] == 'OPEN':
            return False
        return True
    
    def record_result(self, has_progress: bool, error_signature: Optional[str] = None,
                      iteration: int = 0,
                      current_step: Optional[str] = None,
                      current_ticket: Optional[str] = None) -> str:
        current_state = self.state['state']
        
        if has_progress:
            self.state['consecutive_no_progress'] = 0
            self.state['consecutive_same_error'] = 0
            self.state['last_error_signature'] = None
            self.state['last_progress_iteration'] = iteration
            self.state['last_known_head'] = self._get_git_head()
            
            if current_step:
                self.state['last_known_step'] = current_step
            if current_ticket:
                self.state['last_known_ticket'] = current_ticket
            
            if current_state != 'CLOSED':
                self._transition('CLOSED', 'Progress detected -- circuit recovered', iteration)
        else:
            self.state['consecutive_no_progress'] += 1
            
            if error_signature:
                if error_signature == self.state.get('last_error_signature'):
                    self.state['consecutive_same_error'] += 1
                else:
                    self.state['consecutive_same_error'] = 1
                    self.state['last_error_signature'] = error_signature
            
            if self.state['consecutive_same_error'] >= self.SAME_ERROR_THRESHOLD:
                self._transition('OPEN',
                    f"Same error repeated {self.state['consecutive_same_error']} times: {error_signature}",
                    iteration)
            elif self.state['consecutive_no_progress'] >= self.NO_PROGRESS_THRESHOLD:
                if current_state == 'HALF_OPEN':
                    self._transition('OPEN',
                        f"No progress after {self.state['consecutive_no_progress']} iterations (HALF_OPEN test failed)",
                        iteration)
                elif current_state == 'CLOSED':
                    self._transition('HALF_OPEN',
                        f"No progress for {self.state['consecutive_no_progress']} iterations -- testing",
                        iteration)
        
        self._save()
        return self.state['state']
    
    def reset(self) -> None:
        self.state = self._fresh_state()
        self._save()
    
    def get_status(self) -> Dict[str, Any]:
        return {
            'state': self.state['state'],
            'consecutive_no_progress': self.state['consecutive_no_progress'],
            'consecutive_same_error': self.state['consecutive_same_error'],
            'total_opens': self.state['total_opens'],
            'reason': self.state['reason'],
            'last_progress_iteration': self.state['last_progress_iteration'],
        }


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Pickle Rick Circuit Breaker')
    parser.add_argument('action', choices=['status', 'reset', 'check', 'record'])
    parser.add_argument('--session', '-s', required=True, help='Session directory')
    parser.add_argument('--working-dir', '-w', help='Working directory')
    parser.add_argument('--progress', action='store_true', help='For record: had progress')
    parser.add_argument('--error', help='For record: error signature')
    parser.add_argument('--iteration', type=int, default=0)
    
    args = parser.parse_args()
    
    session = Path(args.session)
    working_dir = args.working_dir or str(session)
    
    state_path = session / 'state.json'
    if state_path.exists() and not args.working_dir:
        try:
            state = json.loads(state_path.read_text())
            working_dir = state.get('working_dir', working_dir)
        except (json.JSONDecodeError, OSError):
            pass
    
    cb = CircuitBreaker(str(session), working_dir)
    
    if args.action == 'status':
        status = cb.get_status()
        print(json.dumps(status, indent=2))
    elif args.action == 'reset':
        cb.reset()
        print("Circuit breaker reset to CLOSED")
    elif args.action == 'check':
        can_run = cb.can_execute()
        print(f"CAN_EXECUTE={'true' if can_run else 'false'}")
        if not can_run:
            print(f"REASON={cb.state['reason']}")
    elif args.action == 'record':
        new_state = cb.record_result(
            has_progress=args.progress,
            error_signature=args.error,
            iteration=args.iteration,
        )
        print(f"CIRCUIT_STATE={new_state}")
