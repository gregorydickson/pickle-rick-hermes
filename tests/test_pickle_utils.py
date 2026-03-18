"""Tests for pickle_utils.py — status, cancel, standup, metrics, retry."""

import json
import sys
import subprocess
import pytest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))


class TestStatusCLI:
    def test_status_runs(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'), 'status'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_status_active_only(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'), 'status', '--active-only'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0


class TestCancelCLI:
    def test_cancel_no_sessions(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'), 'cancel'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_cancel_specific(self, tmp_session):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'),
             'cancel', '--session', tmp_session.name],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0


class TestStandupCLI:
    def test_standup_runs(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'), 'standup', '--days', '1'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_standup_custom_since(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'),
             'standup', '--since', '2026-01-01'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0


class TestMetricsCLI:
    def test_metrics_runs(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'), 'metrics', '--days', '7'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0


class TestRetryCLI:
    def test_retry_missing_session(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'),
             'retry', '--session', str(tmp_path / 'nonexistent'), '--ticket', 'abc'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0  # Prints error but doesn't crash
        assert 'No state.json' in result.stdout or 'not found' in result.stdout.lower()

    def test_retry_resets_ticket(self, tmp_session):
        # Create a ticket with "Done" status
        ticket_dir = tmp_session / 'tickets' / 'abc12345'
        ticket_dir.mkdir(parents=True)
        (ticket_dir / 'ticket.md').write_text(
            '---\nid: abc12345\ntitle: Test\nstatus: Done\n---\n# Test')
        
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'),
             'retry', '--session', str(tmp_session), '--ticket', 'abc12345'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        
        # Verify ticket reset
        content = (ticket_dir / 'ticket.md').read_text()
        assert 'status: Todo' in content
        
        # Verify state updated
        state = json.loads((tmp_session / 'state.json').read_text())
        assert state['current_ticket'] == 'abc12345'
        assert state['step'] == 'research'
        assert state['active'] is True
