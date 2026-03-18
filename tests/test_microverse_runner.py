"""Tests for microverse_runner.py — convergence optimization loop."""

import json
import sys
import pytest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from microverse_runner import (
    compare_metric, read_microverse_state, write_microverse_state,
    build_handoff, measure_metric, get_git_head,
)


class TestCompareMetric:
    def test_higher_improved(self):
        assert compare_metric(85.0, 80.0, 0, 'higher') == 'improved'

    def test_higher_regressed(self):
        assert compare_metric(75.0, 80.0, 0, 'higher') == 'regressed'

    def test_higher_held(self):
        assert compare_metric(80.0, 80.0, 0, 'higher') == 'held'

    def test_lower_improved(self):
        assert compare_metric(75.0, 80.0, 0, 'lower') == 'improved'

    def test_lower_regressed(self):
        assert compare_metric(85.0, 80.0, 0, 'lower') == 'regressed'

    def test_lower_held(self):
        assert compare_metric(80.0, 80.0, 0, 'lower') == 'held'

    def test_tolerance_higher(self):
        assert compare_metric(81.0, 80.0, 2.0, 'higher') == 'held'
        assert compare_metric(83.0, 80.0, 2.0, 'higher') == 'improved'

    def test_tolerance_lower(self):
        assert compare_metric(79.0, 80.0, 2.0, 'lower') == 'held'
        assert compare_metric(77.0, 80.0, 2.0, 'lower') == 'improved'

    def test_default_direction_is_higher(self):
        assert compare_metric(85.0, 80.0, 0) == 'improved'
        assert compare_metric(75.0, 80.0, 0) == 'regressed'

    def test_zero_tolerance(self):
        assert compare_metric(80.001, 80.0, 0, 'higher') == 'improved'


class TestMicroverseState:
    def _make_state(self, tmp_path):
        mv = {
            'status': 'iterating',
            'prd_path': str(tmp_path / 'prd.md'),
            'key_metric': {
                'description': 'test coverage',
                'validation': 'pytest --cov',
                'type': 'command',
                'timeout_seconds': 60,
                'tolerance': 0,
                'direction': 'higher',
            },
            'convergence': {
                'stall_limit': 5,
                'stall_counter': 0,
                'history': [],
            },
            'gap_analysis_path': '',
            'failed_approaches': [],
            'baseline_score': 72.5,
            'exit_reason': None,
        }
        (tmp_path / 'microverse.json').write_text(json.dumps(mv))
        return mv

    def test_read_state(self, tmp_path):
        self._make_state(tmp_path)
        result = read_microverse_state(tmp_path)
        assert result['status'] == 'iterating'
        assert result['baseline_score'] == 72.5

    def test_write_state(self, tmp_path):
        self._make_state(tmp_path)
        mv = read_microverse_state(tmp_path)
        mv['status'] = 'converged'
        write_microverse_state(tmp_path, mv)
        reloaded = read_microverse_state(tmp_path)
        assert reloaded['status'] == 'converged'

    def test_read_missing(self, tmp_path):
        with pytest.raises(RuntimeError):
            read_microverse_state(tmp_path)

    def test_read_corrupt(self, tmp_path):
        (tmp_path / 'microverse.json').write_text('broken')
        with pytest.raises(RuntimeError):
            read_microverse_state(tmp_path)

    def test_write_atomic(self, tmp_path):
        self._make_state(tmp_path)
        mv = read_microverse_state(tmp_path)
        write_microverse_state(tmp_path, mv)
        tmp_files = list(tmp_path.glob('*.tmp'))
        assert len(tmp_files) == 0


class TestBuildHandoff:
    def test_basic(self, tmp_path):
        mv = {
            'status': 'iterating',
            'key_metric': {
                'description': 'coverage', 'validation': 'pytest',
                'type': 'command', 'direction': 'higher', 'tolerance': 0,
            },
            'convergence': {
                'stall_limit': 5, 'stall_counter': 2,
                'history': [
                    {'iteration': 0, 'score': 72, 'action': 'accept', 'description': 'init'},
                ],
            },
            'failed_approaches': ['tried X, regressed'],
            'gap_analysis_path': str(tmp_path / 'gap.md'),
            'prd_path': str(tmp_path / 'prd.md'),
            'baseline_score': 72,
        }
        handoff = build_handoff(mv, tmp_path, 3)
        assert 'coverage' in handoff
        assert 'Stall Counter: 2 / 5' in handoff
        assert 'tried X' in handoff
        assert 'Recent Metric History' in handoff

    def test_empty_history(self, tmp_path):
        mv = {
            'status': 'gap_analysis',
            'key_metric': {'description': 'x', 'validation': 'y', 'type': 'command',
                          'direction': 'higher', 'tolerance': 0},
            'convergence': {'stall_limit': 5, 'stall_counter': 0, 'history': []},
            'failed_approaches': [],
            'gap_analysis_path': '', 'prd_path': '', 'baseline_score': 0,
        }
        handoff = build_handoff(mv, tmp_path, 0)
        assert 'Recent Metric History' not in handoff


class TestMeasureMetric:
    def test_echo_number(self, tmp_path):
        score = measure_metric('echo 42', str(tmp_path))
        assert score == 42.0

    def test_multiline_last_line(self, tmp_path):
        score = measure_metric('echo "line1\nline2\n85.5"', str(tmp_path))
        assert score == 85.5

    def test_bad_command(self, tmp_path):
        score = measure_metric('false', str(tmp_path))
        assert score == 0.0

    def test_timeout(self, tmp_path):
        score = measure_metric('sleep 100', str(tmp_path), timeout=1)
        assert score == 0.0


class TestGetGitHead:
    def test_in_repo(self, tmp_git_repo):
        head = get_git_head(str(tmp_git_repo))
        assert len(head) == 40  # SHA1 hex

    def test_not_a_repo(self, tmp_path):
        head = get_git_head(str(tmp_path))
        assert head == ''
