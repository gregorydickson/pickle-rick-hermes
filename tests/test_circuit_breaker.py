"""Tests for circuit_breaker.py — three-state circuit breaker."""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch as mock_patch

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from circuit_breaker import CircuitBreaker


class TestCircuitBreakerInit:
    def test_starts_closed(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        assert cb.state['state'] == 'CLOSED'

    def test_creates_state_file(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        cb._save()
        assert (tmp_path / 'circuit_breaker.json').exists()

    def test_loads_existing_state(self, tmp_path):
        state = {
            'state': 'HALF_OPEN', 'consecutive_no_progress': 3,
            'consecutive_same_error': 0, 'last_error_signature': None,
            'last_known_head': '', 'last_known_step': None,
            'last_known_ticket': None, 'last_progress_iteration': 0,
            'total_opens': 1, 'reason': 'test', 'opened_at': None,
            'history': [], 'last_change': '2026-01-01',
        }
        (tmp_path / 'circuit_breaker.json').write_text(json.dumps(state))
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        assert cb.state['state'] == 'HALF_OPEN'

    def test_handles_corrupt_state(self, tmp_path):
        (tmp_path / 'circuit_breaker.json').write_text('not json')
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        assert cb.state['state'] == 'CLOSED'  # Falls back to fresh

    def test_reads_settings(self, tmp_path):
        """Verify thresholds come from settings file."""
        settings_dir = Path.home() / '.pickle-rick'
        settings_path = settings_dir / 'pickle_settings.json'
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
            cb = CircuitBreaker(str(tmp_path), str(tmp_path))
            assert cb.NO_PROGRESS_THRESHOLD == settings.get('default_cb_no_progress_threshold', 5)
            assert cb.SAME_ERROR_THRESHOLD == settings.get('default_cb_same_error_threshold', 5)


class TestCanExecute:
    def test_closed_allows(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        assert cb.can_execute() is True

    def test_open_blocks(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        cb.state['state'] = 'OPEN'
        assert cb.can_execute() is False

    def test_half_open_allows(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        cb.state['state'] = 'HALF_OPEN'
        assert cb.can_execute() is True

    def test_disabled_always_allows(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        cb.enabled = False
        cb.state['state'] = 'OPEN'
        assert cb.can_execute() is True


class TestRecordResult:
    def test_progress_resets_counters(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        cb.state['consecutive_no_progress'] = 4
        cb.state['consecutive_same_error'] = 2
        result = cb.record_result(has_progress=True, iteration=1)
        assert result == 'CLOSED'
        assert cb.state['consecutive_no_progress'] == 0
        assert cb.state['consecutive_same_error'] == 0

    def test_no_progress_increments(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        cb.record_result(has_progress=False, iteration=1)
        assert cb.state['consecutive_no_progress'] == 1

    def test_no_progress_threshold_opens_via_half_open(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        # First reach HALF_OPEN
        for i in range(cb.NO_PROGRESS_THRESHOLD):
            cb.record_result(has_progress=False, iteration=i)
        assert cb.state['state'] == 'HALF_OPEN'
        # Then OPEN
        cb.record_result(has_progress=False, iteration=cb.NO_PROGRESS_THRESHOLD)
        assert cb.state['state'] == 'OPEN'

    def test_same_error_threshold_opens(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        for i in range(cb.SAME_ERROR_THRESHOLD):
            cb.record_result(has_progress=False, error_signature='ERR_001', iteration=i)
        assert cb.state['state'] == 'OPEN'
        assert 'ERR_001' in cb.state['reason']

    def test_different_errors_dont_accumulate(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        cb.record_result(has_progress=False, error_signature='ERR_001', iteration=1)
        cb.record_result(has_progress=False, error_signature='ERR_002', iteration=2)
        assert cb.state['consecutive_same_error'] == 1  # Reset on different error

    def test_progress_recovers_from_half_open(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        cb.state['state'] = 'HALF_OPEN'
        result = cb.record_result(has_progress=True, iteration=5)
        assert result == 'CLOSED'

    def test_history_recorded(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        for i in range(cb.NO_PROGRESS_THRESHOLD):
            cb.record_result(has_progress=False, iteration=i)
        assert len(cb.state['history']) >= 1
        assert cb.state['history'][-1]['to'] == 'HALF_OPEN'

    def test_total_opens_tracked(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        # Drive to OPEN
        for i in range(cb.NO_PROGRESS_THRESHOLD + 1):
            cb.record_result(has_progress=False, iteration=i)
        assert cb.state['total_opens'] == 1


class TestReset:
    def test_reset_clears_state(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        cb.state['state'] = 'OPEN'
        cb.state['consecutive_no_progress'] = 10
        cb.reset()
        assert cb.state['state'] == 'CLOSED'
        assert cb.state['consecutive_no_progress'] == 0

    def test_reset_persists(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        cb.state['state'] = 'OPEN'
        cb.reset()
        cb2 = CircuitBreaker(str(tmp_path), str(tmp_path))
        assert cb2.state['state'] == 'CLOSED'


class TestGetStatus:
    def test_status_fields(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        status = cb.get_status()
        assert 'state' in status
        assert 'consecutive_no_progress' in status
        assert 'consecutive_same_error' in status
        assert 'total_opens' in status
        assert 'reason' in status
        assert 'last_progress_iteration' in status


class TestAtomicSave:
    def test_save_creates_valid_json(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        cb.record_result(has_progress=True, iteration=1)
        data = json.loads((tmp_path / 'circuit_breaker.json').read_text())
        assert data['state'] == 'CLOSED'

    def test_no_tmp_files_left(self, tmp_path):
        cb = CircuitBreaker(str(tmp_path), str(tmp_path))
        cb.record_result(has_progress=True, iteration=1)
        tmp_files = list(tmp_path.glob('*.tmp*'))
        assert len(tmp_files) == 0
