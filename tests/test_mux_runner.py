"""Tests for mux_runner.py — main orchestration loop."""

import json
import sys
import pytest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from mux_runner import (
    SIGNAL_TOKENS, classify_output, detect_rate_limit,
    build_handoff, build_prompt, load_persona,
    read_state, write_state, log_activity,
    has_lifecycle_artifact, classify_ticket_completion,
)


class TestSignalTokens:
    def test_all_tokens_present(self):
        expected = ['EPIC_COMPLETED', 'TASK_COMPLETED', 'PRD_COMPLETE',
                     'TICKET_SELECTED', 'BLOCKED', 'EXISTENCE_IS_PAIN',
                     'THE_CITADEL_APPROVES']
        for token in expected:
            assert token in SIGNAL_TOKENS

    def test_token_format(self):
        for name, token in SIGNAL_TOKENS.items():
            assert token.startswith('[')
            assert token.endswith(']')
            assert name in token


class TestClassifyOutput:
    def test_epic_completed(self):
        assert classify_output('All done [EPIC_COMPLETED]') == 'epic_completed'

    def test_task_completed(self):
        assert classify_output('Ticket done [TASK_COMPLETED]') == 'task_completed'

    def test_prd_complete(self):
        assert classify_output('PRD written [PRD_COMPLETE]') == 'prd_complete'

    def test_ticket_selected(self):
        assert classify_output('Picked [TICKET_SELECTED]') == 'ticket_selected'

    def test_blocked(self):
        assert classify_output('Cannot proceed [BLOCKED]') == 'blocked'

    def test_existence_is_pain(self):
        assert classify_output('Clean pass [EXISTENCE_IS_PAIN]') == 'review_clean'

    def test_citadel_approves(self):
        assert classify_output('[THE_CITADEL_APPROVES]') == 'review_clean'

    def test_continue(self):
        assert classify_output('Still working on it...') == 'continue'

    def test_empty(self):
        assert classify_output('') == 'continue'

    def test_priority_epic_over_task(self):
        """EPIC_COMPLETED takes priority over TASK_COMPLETED."""
        assert classify_output('[EPIC_COMPLETED] [TASK_COMPLETED]') == 'epic_completed'

    def test_priority_review_clean_over_task(self):
        """EXISTENCE_IS_PAIN before TASK_COMPLETED in check order."""
        output = '[EXISTENCE_IS_PAIN] [TASK_COMPLETED]'
        result = classify_output(output)
        assert result == 'review_clean'


class TestDetectRateLimit:
    def test_rate_limit_detected(self):
        assert detect_rate_limit('Error: rate limit exceeded') is True

    def test_usage_limit(self):
        assert detect_rate_limit('Usage limit reached, try back later') is True

    def test_out_of_usage(self):
        assert detect_rate_limit('Out of usage for this period') is True

    def test_429(self):
        assert detect_rate_limit('HTTP 429 Too Many Requests') is True

    def test_normal_output(self):
        assert detect_rate_limit('All tests passed') is False

    def test_empty(self):
        assert detect_rate_limit('') is False


class TestBuildHandoff:
    def test_basic_handoff(self, tmp_session):
        state = json.loads((tmp_session / 'state.json').read_text())
        handoff = build_handoff(state, tmp_session, 3)
        assert 'Iteration 3' in handoff
        assert 'prd' in handoff
        assert str(tmp_session) in handoff

    def test_handoff_includes_history(self, tmp_session):
        state = json.loads((tmp_session / 'state.json').read_text())
        state['history'] = [{'step': 'prd', 'ticket': None, 'timestamp': '2026-01-01'}]
        (tmp_session / 'state.json').write_text(json.dumps(state))
        state = json.loads((tmp_session / 'state.json').read_text())
        handoff = build_handoff(state, tmp_session, 1)
        assert 'Recent History' in handoff

    def test_handoff_consumes_handoff_file(self, tmp_session):
        (tmp_session / 'handoff.txt').write_text('Custom handoff notes')
        state = json.loads((tmp_session / 'state.json').read_text())
        handoff = build_handoff(state, tmp_session, 1)
        assert 'Custom handoff notes' in handoff
        assert not (tmp_session / 'handoff.txt').exists()


class TestReadWriteState:
    def test_read_state(self, tmp_session):
        state = read_state(tmp_session)
        assert state['step'] == 'prd'
        assert state['active'] is True

    def test_write_state(self, tmp_session):
        state = read_state(tmp_session)
        state['iteration'] = 42
        write_state(tmp_session, state)
        reloaded = read_state(tmp_session)
        assert reloaded['iteration'] == 42

    def test_read_corrupt(self, tmp_session):
        (tmp_session / 'state.json').write_text('broken')
        with pytest.raises(RuntimeError):
            read_state(tmp_session)

    def test_read_missing(self, tmp_path):
        with pytest.raises(RuntimeError):
            read_state(tmp_path / 'nonexistent')


class TestPersona:
    def test_load_persona(self):
        persona = load_persona()
        assert 'Pickle Rick' in persona
        assert 'Voice' in persona
        assert 'Coding Philosophy' in persona

    def test_persona_in_prompt(self, tmp_session):
        state = read_state(tmp_session)
        prompt = build_prompt(state, tmp_session, 0)
        assert 'Pickle Rick' in prompt
        assert 'hyper-competent' in prompt

    def test_persona_not_required(self, tmp_path):
        """Prompt works even if persona file is missing."""
        # build_prompt needs a valid state, not a persona file
        session = tmp_path / 'session'
        session.mkdir()
        state = {
            'working_dir': str(tmp_path), 'step': 'prd',
            'current_ticket': None, 'max_iterations': 10,
            'original_prompt': 'test', 'iteration': 0,
            'history': [],
        }
        (session / 'state.json').write_text(__import__('json').dumps(state))
        prompt = build_prompt(state, session, 0)
        assert 'Pickle Rick autonomous engineering loop' in prompt


class TestGhostTicketPrevention:
    def test_token_present_returns_completed(self, tmp_path):
        log = tmp_path / 'iter.log'
        log.write_text('some output\n[TASK_COMPLETED]\n')
        assert classify_ticket_completion(log, str(tmp_path), tmp_path) == 'completed'

    def test_no_artifact_returns_skipped(self, tmp_path):
        log = tmp_path / 'iter.log'
        log.write_text('some output\n')
        assert classify_ticket_completion(log, str(tmp_path), tmp_path) == 'skipped'

    def test_implementation_artifact_returns_completed(self, tmp_path):
        log = tmp_path / 'iter.log'
        log.write_text('some output\n')
        (tmp_path / 'research_notes.md').write_text('notes')
        assert classify_ticket_completion(log, str(tmp_path), tmp_path, 'implementation') == 'completed'

    def test_review_artifact_returns_completed(self, tmp_path):
        log = tmp_path / 'iter.log'
        log.write_text('some output\n')
        (tmp_path / 'review_scope.md').write_text('scope')
        assert classify_ticket_completion(log, str(tmp_path), tmp_path, 'review') == 'completed'

    def test_git_diff_corroboration(self, tmp_git_repo):
        log = tmp_git_repo / 'iter.log'
        log.write_text('some output\n')
        # Artifact exists; git diff corroboration is attempted
        (tmp_git_repo / 'new_file.txt').write_text('new content')
        ticket_dir = tmp_git_repo / 'tickets' / 'abc123'
        ticket_dir.mkdir(parents=True)
        (ticket_dir / 'research_notes.md').write_text('notes')
        assert classify_ticket_completion(log, str(tmp_git_repo), ticket_dir, 'implementation') == 'completed'

    def test_missing_ticket_dir_returns_skipped(self, tmp_path):
        log = tmp_path / 'iter.log'
        log.write_text('some output\n')
        assert classify_ticket_completion(log, str(tmp_path), tmp_path / 'nonexistent') == 'skipped'

    def test_has_lifecycle_artifact_implementation(self):
        assert has_lifecycle_artifact(['research_notes.md', 'plan.md'], 'implementation') is True
        assert has_lifecycle_artifact(['random.txt'], 'implementation') is False

    def test_has_lifecycle_artifact_review(self):
        assert has_lifecycle_artifact(['review_scope.md'], 'review') is True
        assert has_lifecycle_artifact(['research_notes.md'], 'review') is False

    def test_classify_fails_safe_on_exception(self, tmp_path):
        # Pass a directory as iter_log_file to trigger OSError on read_text
        assert classify_ticket_completion(tmp_path, str(tmp_path), tmp_path) == 'skipped'

    def test_classify_ticket_completion_git_permission_error(self, tmp_path, monkeypatch):
        """Simulate PermissionError from subprocess.run (e.g. git not executable)."""
        import subprocess
        log = tmp_path / 'iter.log'
        log.write_text('some output\n')
        (tmp_path / 'research_notes.md').write_text('notes')
        
        def mock_run(*args, **kwargs):
            raise PermissionError(13, 'Permission denied')
        monkeypatch.setattr(subprocess, 'run', mock_run)
        
        # Should still return 'completed' because artifact exists
        assert classify_ticket_completion(log, str(tmp_path), tmp_path) == 'completed'


class TestLogActivity:
    def test_log_creates_file(self, tmp_session):
        log_activity(tmp_session, 'test_event', detail='hello')
        log_path = tmp_session / 'activity.jsonl'
        assert log_path.exists()
        lines = log_path.read_text().strip().split('\n')
        last = json.loads(lines[-1])
        assert last['event'] == 'test_event'
        assert last['detail'] == 'hello'

    def test_log_appends(self, tmp_session):
        log_activity(tmp_session, 'event1')
        log_activity(tmp_session, 'event2')
        lines = (tmp_session / 'activity.jsonl').read_text().strip().split('\n')
        assert len(lines) >= 2
