"""Tests for pickle_state.py — session state management."""

import json
import os
import subprocess
import sys
import pytest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from pickle_state import (
    VALID_STEPS, DEFAULT_STATE, SCHEMA_VERSION,
    locked_read, locked_write, locked_update,
)


class TestValidSteps:
    def test_all_steps_present(self):
        expected = ['prd', 'breakdown', 'research', 'plan', 'implement', 'refactor', 'review', 'meeseeks']
        assert VALID_STEPS == expected

    def test_step_count(self):
        assert len(VALID_STEPS) == 8


class TestDefaultState:
    def test_required_fields(self):
        required = ['active', 'working_dir', 'step', 'iteration', 'max_iterations',
                     'max_time_minutes', 'worker_timeout_seconds', 'start_time_epoch',
                     'completion_promise', 'original_prompt', 'current_ticket',
                     'history', 'started_at', 'session_dir', 'schema_version']
        for field in required:
            assert field in DEFAULT_STATE, f"Missing field: {field}"

    def test_optional_fields(self):
        optional = ['tmux_mode', 'min_iterations', 'command_template', 'chain_meeseeks', 'pid']
        for field in optional:
            assert field in DEFAULT_STATE, f"Missing optional field: {field}"

    def test_defaults(self):
        assert DEFAULT_STATE['active'] is True
        assert DEFAULT_STATE['step'] == 'prd'
        assert DEFAULT_STATE['iteration'] == 0
        assert DEFAULT_STATE['max_iterations'] == 100
        assert DEFAULT_STATE['schema_version'] == SCHEMA_VERSION

    def test_total_field_count(self):
        assert len(DEFAULT_STATE) == 21  # includes 'mode' field


class TestLockedReadWrite:
    def test_write_and_read(self, tmp_path):
        state_path = tmp_path / 'state.json'
        state = {'active': True, 'step': 'prd', 'iteration': 0}
        locked_write(state_path, state)
        result = locked_read(state_path)
        assert result == state

    def test_write_creates_file(self, tmp_path):
        state_path = tmp_path / 'state.json'
        assert not state_path.exists()
        locked_write(state_path, {'test': True})
        assert state_path.exists()

    def test_write_overwrites(self, tmp_path):
        state_path = tmp_path / 'state.json'
        locked_write(state_path, {'version': 1})
        locked_write(state_path, {'version': 2})
        result = locked_read(state_path)
        assert result['version'] == 2

    def test_read_missing_file(self, tmp_path):
        state_path = tmp_path / 'nonexistent.json'
        with pytest.raises(FileNotFoundError):
            locked_read(state_path)

    def test_write_atomic(self, tmp_path):
        """Verify no .tmp files are left behind."""
        state_path = tmp_path / 'state.json'
        locked_write(state_path, {'test': True})
        tmp_files = list(tmp_path.glob('*.tmp*'))
        assert len(tmp_files) == 0


class TestLockedUpdate:
    def test_update_step(self, tmp_session):
        state_path = tmp_session / 'state.json'
        result = locked_update(state_path, {'step': 'breakdown'})
        assert result['step'] == 'breakdown'

    def test_update_records_history(self, tmp_session):
        state_path = tmp_session / 'state.json'
        result = locked_update(state_path, {'step': 'breakdown'})
        assert len(result['history']) == 1
        assert result['history'][0]['step'] == 'breakdown'

    def test_update_multiple_fields(self, tmp_session):
        state_path = tmp_session / 'state.json'
        result = locked_update(state_path, {
            'step': 'research',
            'current_ticket': 'abc123',
            'iteration': 5,
        })
        assert result['step'] == 'research'
        assert result['current_ticket'] == 'abc123'
        assert result['iteration'] == 5

    def test_update_preserves_existing(self, tmp_session):
        state_path = tmp_session / 'state.json'
        result = locked_update(state_path, {'step': 'breakdown'})
        assert result['active'] is True
        assert result['original_prompt'] == 'Test task'

    def test_update_no_history_for_same_step(self, tmp_session):
        state_path = tmp_session / 'state.json'
        locked_update(state_path, {'iteration': 5})
        result = locked_read(state_path)
        assert len(result['history']) == 0

    def test_update_corrupt_file(self, tmp_session):
        state_path = tmp_session / 'state.json'
        state_path.write_text('not json')
        with pytest.raises(json.JSONDecodeError):
            locked_update(state_path, {'step': 'breakdown'})


class TestCLI:
    """Test the pickle_state.py CLI commands."""

    def test_init(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_state.py'),
             'init', '--task', 'CLI test', '--working-dir', str(tmp_path)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert 'SESSION_DIR=' in result.stdout

        # Parse session dir and verify state
        for line in result.stdout.strip().split('\n'):
            if line.startswith('SESSION_DIR='):
                session_dir = Path(line.split('=', 1)[1])
                break
        state = json.loads((session_dir / 'state.json').read_text())
        assert state['active'] is True
        assert state['original_prompt'] == 'CLI test'
        assert state['working_dir'] == str(tmp_path)
        assert (session_dir / 'tickets').is_dir()
        assert (session_dir / 'activity.jsonl').exists()

    def test_read(self, tmp_session):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_state.py'),
             'read', '--session', str(tmp_session)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        state = json.loads(result.stdout)
        assert state['step'] == 'prd'

    def test_read_field(self, tmp_session):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_state.py'),
             'read', '--session', str(tmp_session), '--field', 'step'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == 'prd'

    def test_update(self, tmp_session):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_state.py'),
             'update', '--session', str(tmp_session), '--step', 'breakdown'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        state = json.loads(result.stdout)
        assert state['step'] == 'breakdown'

    def test_update_invalid_step(self, tmp_session):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_state.py'),
             'update', '--session', str(tmp_session), '--step', 'invalid'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0

    def test_deactivate(self, tmp_session):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_state.py'),
             'deactivate', '--session', str(tmp_session)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        state = json.loads((tmp_session / 'state.json').read_text())
        assert state['active'] is False

    def test_log_event(self, tmp_session):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_state.py'),
             'log', '--session', str(tmp_session),
             '--event', 'feature', '--description', 'test event'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        log = (tmp_session / 'activity.jsonl').read_text()
        assert 'test event' in log
