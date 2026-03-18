"""Tests for pickle_utils.py — status, cancel, standup, metrics, retry."""

import json
import os
import sys
import subprocess
import time
import pytest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def session_with_activity(tmp_session):
    """Session with realistic activity and ticket data."""
    # Add activity log entries
    activity = tmp_session / 'activity.jsonl'
    entries = [
        {'ts': '2026-03-17T12:00:00', 'event': 'session_start', 'source': 'pickle'},
        {'ts': '2026-03-17T12:01:00', 'event': 'iteration_start', 'source': 'pickle', 'iteration': 0},
        {'ts': '2026-03-17T12:02:00', 'event': 'ticket_completed', 'source': 'pickle', 'ticket': 'abc12345'},
        {'ts': '2026-03-17T12:03:00', 'event': 'iteration_end', 'source': 'pickle', 'iteration': 0},
    ]
    with open(activity, 'w') as f:
        for e in entries:
            f.write(json.dumps(e) + '\n')

    # Add a ticket
    ticket_dir = tmp_session / 'tickets' / 'abc12345'
    ticket_dir.mkdir(parents=True)
    (ticket_dir / 'ticket.md').write_text(
        '---\nid: abc12345\ntitle: Test Ticket\nstatus: Done\norder: 10\n---\n# Test Ticket\n')
    (ticket_dir / 'research.md').write_text('# Research\nDone.\n')
    (ticket_dir / 'plan.md').write_text('# Plan\nDone.\n')

    return tmp_session


# ---------------------------------------------------------------------------
# Status CLI
# ---------------------------------------------------------------------------

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

    def test_status_output_format(self):
        """Status output should not crash even with no sessions."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'), 'status'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        # Should print something (even "No sessions" or a header)
        assert len(result.stdout) > 0 or len(result.stderr) == 0


# ---------------------------------------------------------------------------
# Cancel CLI
# ---------------------------------------------------------------------------

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

    def test_cancel_nonexistent_session(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'),
             'cancel', '--session', 'nonexistent_session_xyz'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0  # graceful handling


# ---------------------------------------------------------------------------
# Standup CLI
# ---------------------------------------------------------------------------

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

    def test_standup_default_days(self):
        """Standup with just --days 0 should not crash."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'), 'standup', '--days', '0'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Metrics CLI
# ---------------------------------------------------------------------------

class TestMetricsCLI:
    def test_metrics_runs(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'), 'metrics', '--days', '7'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_metrics_short_window(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'), 'metrics', '--days', '0'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_metrics_long_window(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'), 'metrics', '--days', '365'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Retry CLI
# ---------------------------------------------------------------------------

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

    def test_retry_missing_ticket(self, tmp_session):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'),
             'retry', '--session', str(tmp_session), '--ticket', 'nonexistent'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert 'not found' in result.stdout.lower() or 'No ticket' in result.stdout

    def test_retry_activates_inactive_session(self, tmp_session):
        """Retry should set active=True even if session was deactivated."""
        state = json.loads((tmp_session / 'state.json').read_text())
        state['active'] = False
        (tmp_session / 'state.json').write_text(json.dumps(state))

        ticket_dir = tmp_session / 'tickets' / 'def67890'
        ticket_dir.mkdir(parents=True)
        (ticket_dir / 'ticket.md').write_text(
            '---\nid: def67890\ntitle: Retry Me\nstatus: Done\n---\n# Retry')

        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_utils.py'),
             'retry', '--session', str(tmp_session), '--ticket', 'def67890'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

        state = json.loads((tmp_session / 'state.json').read_text())
        assert state['active'] is True
