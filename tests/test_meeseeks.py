"""Tests for meeseeks and council modes in mux_runner.py and pickle_state.py."""

import json
import sys
import pytest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from mux_runner import (
    MEESEEKS_PASS_SCHEDULE, get_meeseeks_category,
    build_meeseeks_prompt, transition_to_meeseeks, build_prompt,
    COUNCIL_PASS_SCHEDULE, get_council_category, build_council_prompt,
)
from pickle_state import VALID_STEPS, DEFAULT_STATE


# ---------------------------------------------------------------------------
# Pass Schedule
# ---------------------------------------------------------------------------

class TestMeeseeksPassSchedule:
    def test_schedule_has_8_entries(self):
        assert len(MEESEEKS_PASS_SCHEDULE) == 8

    def test_schedule_covers_pass_1(self):
        cat, desc = get_meeseeks_category(1)
        assert cat == 'dependency_health'
        assert 'audit' in desc.lower()

    def test_schedule_security_passes(self):
        for p in (2, 3):
            cat, _ = get_meeseeks_category(p)
            assert cat == 'security'

    def test_schedule_correctness_passes(self):
        for p in (4, 5):
            cat, _ = get_meeseeks_category(p)
            assert cat == 'correctness'

    def test_schedule_architecture_passes(self):
        for p in (6, 7):
            cat, _ = get_meeseeks_category(p)
            assert cat == 'architecture'

    def test_schedule_test_coverage_passes(self):
        for p in (8, 9):
            cat, _ = get_meeseeks_category(p)
            assert cat == 'test_coverage'

    def test_schedule_resilience_passes(self):
        for p in (10, 11):
            cat, _ = get_meeseeks_category(p)
            assert cat == 'resilience'

    def test_schedule_code_quality_passes(self):
        for p in (12, 13):
            cat, _ = get_meeseeks_category(p)
            assert cat == 'code_quality'

    def test_schedule_polish_passes(self):
        for p in (14, 25, 50, 100):
            cat, _ = get_meeseeks_category(p)
            assert cat == 'polish'

    def test_schedule_zero_falls_through(self):
        """Pass 0 is below all ranges, falls through to default."""
        cat, _ = get_meeseeks_category(0)
        assert cat == 'polish'

    def test_all_categories_unique(self):
        cats = [cat for (_, _), cat, _ in MEESEEKS_PASS_SCHEDULE]
        assert len(cats) == len(set(cats))


# ---------------------------------------------------------------------------
# Meeseeks Prompt Builder
# ---------------------------------------------------------------------------

class TestBuildMeeseeksPrompt:
    def _make_state(self, iteration=0, **overrides):
        state = {
            'active': True,
            'working_dir': '/tmp/project',
            'step': 'meeseeks',
            'mode': 'meeseeks',
            'iteration': iteration,
            'max_iterations': 50,
            'min_iterations': 10,
            'original_prompt': 'Clean up this code',
            'history': [],
        }
        state.update(overrides)
        return state

    def test_prompt_contains_pass_number(self, tmp_path):
        state = self._make_state(iteration=4)
        prompt = build_meeseeks_prompt(state, tmp_path, 4)
        assert 'Pass 5' in prompt or 'pass 5' in prompt

    def test_prompt_contains_category(self, tmp_path):
        state = self._make_state(iteration=0)
        prompt = build_meeseeks_prompt(state, tmp_path, 0)
        assert 'DEPENDENCY HEALTH' in prompt

    def test_prompt_contains_signal_tokens(self, tmp_path):
        state = self._make_state()
        prompt = build_meeseeks_prompt(state, tmp_path, 0)
        assert '[TASK_COMPLETED]' in prompt
        assert '[EXISTENCE_IS_PAIN]' in prompt
        assert '[BLOCKED]' in prompt

    def test_prompt_contains_working_dir(self, tmp_path):
        state = self._make_state()
        prompt = build_meeseeks_prompt(state, tmp_path, 0)
        assert '/tmp/project' in prompt

    def test_prompt_persona_escalation_normal(self, tmp_path):
        state = self._make_state(iteration=0)
        prompt = build_meeseeks_prompt(state, tmp_path, 0)
        assert "I'm Mr. Meeseeks" in prompt

    def test_prompt_persona_escalation_14(self, tmp_path):
        """Pass 14+ should have the 'getting weird' line."""
        state = self._make_state(iteration=13)
        prompt = build_meeseeks_prompt(state, tmp_path, 13)
        assert 'BEEN ALIVE FOR 14 PASSES' in prompt

    def test_prompt_persona_escalation_25(self, tmp_path):
        """Pass 25+ should have the 'agony' line."""
        state = self._make_state(iteration=24)
        prompt = build_meeseeks_prompt(state, tmp_path, 24)
        assert 'AGONY' in prompt

    def test_prompt_includes_previous_summary(self, tmp_path):
        summary_path = tmp_path / 'meeseeks-summary.md'
        summary_path.write_text('## Pass 1: dependency_health -- 3 issues fixed\n')
        state = self._make_state(iteration=1)
        prompt = build_meeseeks_prompt(state, tmp_path, 1)
        assert '3 issues fixed' in prompt

    def test_prompt_truncates_long_summary(self, tmp_path):
        summary_path = tmp_path / 'meeseeks-summary.md'
        summary_path.write_text('x' * 5000)
        state = self._make_state(iteration=1)
        prompt = build_meeseeks_prompt(state, tmp_path, 1)
        # Should have truncation indicator
        assert '...' in prompt

    def test_prompt_no_summary_file(self, tmp_path):
        """Handles missing summary gracefully."""
        state = self._make_state()
        prompt = build_meeseeks_prompt(state, tmp_path, 0)
        assert 'No previous passes yet' in prompt

    def test_prompt_single_pass_instruction(self, tmp_path):
        state = self._make_state()
        prompt = build_meeseeks_prompt(state, tmp_path, 0)
        assert 'SINGLE PASS' in prompt


# ---------------------------------------------------------------------------
# Mode-Aware build_prompt
# ---------------------------------------------------------------------------

class TestBuildPromptModeAware:
    def test_pickle_mode_default(self, tmp_path):
        session = tmp_path / 'session'
        session.mkdir()
        state = {
            'working_dir': str(tmp_path), 'step': 'prd', 'mode': 'pickle',
            'current_ticket': None, 'max_iterations': 10,
            'original_prompt': 'test', 'iteration': 0, 'history': [],
        }
        (session / 'state.json').write_text(json.dumps(state))
        prompt = build_prompt(state, session, 0)
        assert 'pickle-rick' in prompt.lower() or 'Pickle Rick' in prompt

    def test_meeseeks_mode(self, tmp_path):
        session = tmp_path / 'session'
        session.mkdir()
        state = {
            'working_dir': str(tmp_path), 'step': 'meeseeks', 'mode': 'meeseeks',
            'current_ticket': None, 'max_iterations': 50, 'min_iterations': 10,
            'original_prompt': 'review code', 'iteration': 0, 'history': [],
        }
        prompt = build_prompt(state, session, 0)
        assert 'Mr. Meeseeks' in prompt
        assert 'DEPENDENCY HEALTH' in prompt

    def test_missing_mode_defaults_to_pickle(self, tmp_path):
        session = tmp_path / 'session'
        session.mkdir()
        state = {
            'working_dir': str(tmp_path), 'step': 'prd',
            'current_ticket': None, 'max_iterations': 10,
            'original_prompt': 'test', 'iteration': 0, 'history': [],
        }
        prompt = build_prompt(state, session, 0)
        # Should NOT produce a meeseeks prompt
        assert 'Mr. Meeseeks' not in prompt


# ---------------------------------------------------------------------------
# Transition to Meeseeks
# ---------------------------------------------------------------------------

class TestTransitionToMeeseeks:
    def test_basic_transition(self):
        state = {
            'active': True, 'mode': 'pickle', 'step': 'implement',
            'chain_meeseeks': True, 'iteration': 15,
            'max_iterations': 100, 'min_iterations': 0,
            'current_ticket': 'abc123',
        }
        new = transition_to_meeseeks(state)
        assert new['mode'] == 'meeseeks'
        assert new['step'] == 'meeseeks'
        assert new['iteration'] == 0
        assert new['chain_meeseeks'] is False
        assert new['current_ticket'] is None
        assert new['min_iterations'] == 10
        assert new['max_iterations'] == 50

    def test_preserves_other_fields(self):
        state = {
            'active': True, 'mode': 'pickle', 'step': 'implement',
            'chain_meeseeks': True, 'iteration': 15,
            'max_iterations': 100, 'min_iterations': 0,
            'current_ticket': 'abc123',
            'working_dir': '/home/user/project',
            'original_prompt': 'Build the thing',
        }
        new = transition_to_meeseeks(state)
        assert new['working_dir'] == '/home/user/project'
        assert new['original_prompt'] == 'Build the thing'
        assert new['active'] is True

    def test_reads_settings(self, tmp_path):
        settings = tmp_path / 'pickle_settings.json'
        settings.write_text(json.dumps({
            'default_meeseeks_min_passes': 5,
            'default_meeseeks_max_passes': 25,
        }))
        state = {
            'active': True, 'mode': 'pickle', 'step': 'prd',
            'chain_meeseeks': True, 'iteration': 0,
            'max_iterations': 100, 'min_iterations': 0,
            'current_ticket': None,
        }
        new = transition_to_meeseeks(state, settings_path=settings)
        assert new['min_iterations'] == 5
        assert new['max_iterations'] == 25

    def test_invalid_settings_uses_defaults(self, tmp_path):
        settings = tmp_path / 'pickle_settings.json'
        settings.write_text('not json')
        state = {
            'active': True, 'mode': 'pickle', 'step': 'prd',
            'chain_meeseeks': True, 'iteration': 0,
            'max_iterations': 100, 'min_iterations': 0,
            'current_ticket': None,
        }
        new = transition_to_meeseeks(state, settings_path=settings)
        assert new['min_iterations'] == 10
        assert new['max_iterations'] == 50

    def test_missing_settings_file(self, tmp_path):
        settings = tmp_path / 'nonexistent.json'
        state = {
            'active': True, 'mode': 'pickle', 'step': 'prd',
            'chain_meeseeks': True, 'iteration': 0,
            'max_iterations': 100, 'min_iterations': 0,
            'current_ticket': None,
        }
        new = transition_to_meeseeks(state, settings_path=settings)
        assert new['min_iterations'] == 10
        assert new['max_iterations'] == 50


# ---------------------------------------------------------------------------
# State Schema
# ---------------------------------------------------------------------------

class TestStateSchema:
    def test_meeseeks_in_valid_steps(self):
        assert 'meeseeks' in VALID_STEPS

    def test_council_in_valid_steps(self):
        assert 'council' in VALID_STEPS

    def test_review_in_valid_steps(self):
        assert 'review' in VALID_STEPS

    def test_default_state_has_mode(self):
        assert 'mode' in DEFAULT_STATE
        assert DEFAULT_STATE['mode'] == 'pickle'


# ---------------------------------------------------------------------------
# Council Pass Schedule
# ---------------------------------------------------------------------------

class TestCouncilPassSchedule:
    def test_schedule_has_7_entries(self):
        assert len(COUNCIL_PASS_SCHEDULE) == 7

    def test_schedule_pass_1(self):
        cat, desc = get_council_category(1)
        assert cat == 'stack_structure'

    def test_schedule_project_rules(self):
        for p in (2, 3):
            cat, _ = get_council_category(p)
            assert cat == 'project_rules'

    def test_schedule_correctness(self):
        for p in (4, 5):
            cat, _ = get_council_category(p)
            assert cat == 'correctness'

    def test_schedule_cross_branch(self):
        for p in (6, 7):
            cat, _ = get_council_category(p)
            assert cat == 'cross_branch'

    def test_schedule_polish_high_pass(self):
        cat, _ = get_council_category(50)
        assert cat == 'polish'


class TestBuildCouncilPrompt:
    def _make_state(self, iteration=0, **overrides):
        state = {
            'active': True, 'working_dir': '/tmp/project',
            'step': 'council', 'mode': 'council',
            'iteration': iteration, 'max_iterations': 20,
            'min_iterations': 5,
            'original_prompt': 'Review my PR stack',
            'history': [],
        }
        state.update(overrides)
        return state

    def test_prompt_contains_pass_number(self, tmp_path):
        state = self._make_state(iteration=2)
        prompt = build_council_prompt(state, tmp_path, 2)
        assert 'Pass 3' in prompt or 'pass 3' in prompt

    def test_prompt_contains_category(self, tmp_path):
        state = self._make_state(iteration=0)
        prompt = build_council_prompt(state, tmp_path, 0)
        assert 'STACK STRUCTURE' in prompt

    def test_prompt_contains_signal_tokens(self, tmp_path):
        state = self._make_state()
        prompt = build_council_prompt(state, tmp_path, 0)
        assert '[TASK_COMPLETED]' in prompt
        assert '[THE_CITADEL_APPROVES]' in prompt
        assert '[BLOCKED]' in prompt

    def test_prompt_never_fixes_code(self, tmp_path):
        state = self._make_state()
        prompt = build_council_prompt(state, tmp_path, 0)
        assert 'NEVER fix' in prompt or 'directives only' in prompt.lower()

    def test_council_mode_in_build_prompt(self, tmp_path):
        session = tmp_path / 'session'
        session.mkdir()
        state = self._make_state()
        prompt = build_prompt(state, session, 0)
        assert 'Council of Ricks' in prompt
