"""Tests for pipeline_runner.py — sequential phase orchestration."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from pipeline_runner import (
    parse_pipeline_config,
    archive_phase_artifacts,
    reset_state_for_phase,
    clean_phase_artifacts,
    discover_subsystems,
    setup_phase_config,
)


class TestParsePipelineConfig:
    def test_default_phases(self):
        result = parse_pipeline_config('pickle,anatomy-park,szechuan-sauce')
        assert result == ['pickle', 'anatomy-park', 'szechuan-sauce']

    def test_single_phase(self):
        result = parse_pipeline_config('pickle')
        assert result == ['pickle']

    def test_invalid_phases_filtered(self):
        result = parse_pipeline_config('pickle,invalid,szechuan-sauce')
        assert result == ['pickle', 'szechuan-sauce']

    def test_empty_returns_empty(self):
        result = parse_pipeline_config('')
        assert result == []

    def test_whitespace_trimmed(self):
        result = parse_pipeline_config(' pickle , anatomy-park ')
        assert result == ['pickle', 'anatomy-park']


class TestArchivePhaseArtifacts:
    def test_archives_iteration_logs(self, tmp_path):
        session_dir = tmp_path / 'session'
        session_dir.mkdir()
        (session_dir / 'iteration_0.log').write_text('log0')
        (session_dir / 'iteration_1.log').write_text('log1')
        (session_dir / 'microverse_iter_0.log').write_text('mv0')

        archive_phase_artifacts(session_dir, 'pickle')

        archive_dirs = list((session_dir / 'archive').iterdir())
        assert len(archive_dirs) == 1
        archived = archive_dirs[0]
        assert (archived / 'iteration_0.log').exists()
        assert (archived / 'iteration_1.log').exists()
        assert (archived / 'microverse_iter_0.log').exists()
        assert (archived / 'manifest.json').exists()
        # Originals removed
        assert not (session_dir / 'iteration_0.log').exists()

    def test_no_logs_no_crash(self, tmp_path):
        session_dir = tmp_path / 'session'
        session_dir.mkdir()
        archive_phase_artifacts(session_dir, 'pickle')
        assert (session_dir / 'archive').exists()


class TestCleanPhaseArtifacts:
    def test_removes_stale_files(self, tmp_path):
        session_dir = tmp_path / 'session'
        session_dir.mkdir()
        (session_dir / 'handoff.txt').write_text('stale')
        (session_dir / 'gap_analysis.md').write_text('stale')
        (session_dir / 'council-summary.md').write_text('stale')
        (session_dir / 'state.json').write_text('{}')  # not stale

        clean_phase_artifacts(session_dir)

        assert not (session_dir / 'handoff.txt').exists()
        assert not (session_dir / 'gap_analysis.md').exists()
        assert not (session_dir / 'council-summary.md').exists()
        assert (session_dir / 'state.json').exists()


class TestResetStateForPhase:
    def test_resets_iteration_and_mode(self, tmp_session):
        from pickle_state import locked_read, locked_write
        state_path = tmp_session / 'state.json'
        state = locked_read(state_path)
        state['iteration'] = 42
        state['mode'] = 'pickle'
        locked_write(state_path, state)

        reset_state_for_phase(tmp_session, 'anatomy-park')

        state = locked_read(state_path)
        assert state['iteration'] == 0
        assert state['mode'] == 'microverse'
        assert state['command_template'] == 'anatomy-park'

    def test_reset_szechuan_sauce(self, tmp_session):
        from pickle_state import locked_read, locked_write
        state_path = tmp_session / 'state.json'
        state = locked_read(state_path)
        state['iteration'] = 10
        locked_write(state_path, state)

        reset_state_for_phase(tmp_session, 'szechuan-sauce')

        state = locked_read(state_path)
        assert state['iteration'] == 0
        assert state['mode'] == 'microverse'
        assert state['command_template'] == 'szechuan-sauce'

    def test_reset_pickles(self, tmp_session):
        from pickle_state import locked_read, locked_write
        state_path = tmp_session / 'state.json'
        state = locked_read(state_path)
        state['iteration'] = 5
        state['mode'] = 'microverse'
        state['command_template'] = 'anatomy-park'
        locked_write(state_path, state)

        reset_state_for_phase(tmp_session, 'pickle')

        state = locked_read(state_path)
        assert state['iteration'] == 0
        assert state['mode'] == 'pickle'
        assert state['command_template'] is None

    def test_reset_state_comprehensive(self, tmp_session):
        from pickle_state import locked_read, locked_write
        state_path = tmp_session / 'state.json'
        state = locked_read(state_path)
        state['iteration'] = 42
        state['active'] = False
        state['current_ticket'] = 'abc123'
        state['chain_meeseeks'] = True
        state['mode'] = 'pickle'
        locked_write(state_path, state)

        reset_state_for_phase(tmp_session, 'anatomy-park')

        state = locked_read(state_path)
        assert state['iteration'] == 0
        assert state['active'] is True
        assert state['current_ticket'] is None
        assert state['chain_meeseeks'] is False
        assert state['mode'] == 'microverse'
        assert state['command_template'] == 'anatomy-park'
        assert state['step'] == 'review'


class TestDiscoverSubsystems:
    def test_finds_valid_dirs(self, tmp_path):
        (tmp_path / 'src').mkdir()
        (tmp_path / 'src' / 'a.py').write_text('x')
        (tmp_path / 'src' / 'b.py').write_text('x')
        (tmp_path / 'src' / 'c.py').write_text('x')
        result = discover_subsystems(str(tmp_path))
        assert 'src' in result

    def test_excludes_node_modules(self, tmp_path):
        (tmp_path / 'node_modules').mkdir()
        (tmp_path / 'node_modules' / 'a.js').write_text('x')
        result = discover_subsystems(str(tmp_path))
        assert 'node_modules' not in result

    def test_skips_empty_dirs(self, tmp_path):
        (tmp_path / 'empty').mkdir()
        result = discover_subsystems(str(tmp_path))
        assert result == []


class TestSetupPhaseConfig:
    def test_skips_empty_anatomy(self, tmp_path):
        session_dir = tmp_path / 'session'
        session_dir.mkdir()
        wd = tmp_path / 'wd'
        wd.mkdir()
        result = setup_phase_config(session_dir, 'anatomy-park', str(wd))
        assert result is False

    def test_proceeds_with_subsystems(self, tmp_path):
        session_dir = tmp_path / 'session'
        session_dir.mkdir()
        wd = tmp_path / 'wd'
        wd.mkdir()
        (wd / 'src').mkdir()
        for i in range(3):
            (wd / 'src' / f'{i}.py').write_text('x')
        result = setup_phase_config(session_dir, 'anatomy-park', str(wd))
        assert result is True
        assert (session_dir / 'anatomy-park.json').exists()


class TestMainExitCode:
    def test_main_exits_nonzero_on_invalid_session(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pipeline_runner.py'),
             '--resume', str(tmp_path / 'nonexistent')],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0


class TestSignalCancelMarker:
    def test_sigint_writes_cancel_marker(self, tmp_path):
        """Verify that sending SIGINT to pipeline_runner writes .cancel marker."""
        session_dir = tmp_path / 'session'
        session_dir.mkdir()
        (session_dir / 'state.json').write_text(json.dumps({
            'working_dir': str(tmp_path),
            'original_prompt': 'test',
            'iteration': 0,
            'max_iterations': 100,
            'max_time_minutes': 720,
            'start_time_epoch': int(time.time()),
        }))

        # Create a fake hermes that sleeps long enough for the signal test
        hermes_fake = tmp_path / 'hermes'
        hermes_fake.write_text('#!/bin/bash\nsleep 2\n')
        hermes_fake.chmod(0o755)
        env = {**os.environ, 'PATH': f"{tmp_path}:{os.environ.get('PATH', '')}"}

        proc = subprocess.Popen(
            [sys.executable, str(SCRIPTS / 'pipeline_runner.py'),
             '--resume', str(session_dir), '--phases', 'pickle',
             '--timeout', '300'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=env,
        )
        time.sleep(0.5)
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        assert (session_dir / '.cancel').exists()


class TestSkippedPhase:
    def test_skipped_phase_not_failure(self, tmp_path):
        """A phase with no work should return exit 0, not fail the pipeline."""
        wd = tmp_path / 'wd'
        wd.mkdir()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pipeline_runner.py'),
             '--task', 'test', '--working-dir', str(wd),
             '--phases', 'anatomy-park', '--timeout', '5'],
            capture_output=True, text=True, timeout=30,
        )
        # Should complete without hard crash; may skip or exit 0
        assert result.returncode == 0 or 'skip' in result.stdout.lower()


class TestPhaseOrder:
    def test_phase_order_dry_run(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pipeline_runner.py'),
             '--task', 'test', '--working-dir', str(tmp_path),
             '--phases', 'pickle,anatomy-park,szechuan-sauce',
             '--dry-run'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert 'pickle' in result.stdout
        assert 'anatomy-park' in result.stdout
        assert 'szechuan-sauce' in result.stdout
        # Verify order by position
        pickle_pos = result.stdout.find('pickle')
        anatomy_pos = result.stdout.find('anatomy-park')
        szechuan_pos = result.stdout.find('szechuan-sauce')
        assert pickle_pos < anatomy_pos < szechuan_pos


class TestChainMeeseeksLockout:
    def test_init_forces_chain_meeseeks_false(self, tmp_path):
        """Verify that new sessions force chain_meeseeks=False."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pipeline_runner.py'),
             '--task', 'test pipeline', '--working-dir', str(tmp_path),
             '--phases', 'pickle', '--max-time', '1', '--timeout', '5'],
            capture_output=True, text=True, timeout=30,
        )
        # Even though the phase will fail (no hermes), init should succeed
        # and we can verify the session was created with chain_meeseeks=False
        if 'SESSION_DIR=' in result.stdout:
            for line in result.stdout.strip().split('\n'):
                if line.startswith('SESSION_DIR='):
                    session_dir = Path(line.split('=', 1)[1])
                    state = json.loads((session_dir / 'state.json').read_text())
                    assert state.get('chain_meeseeks') is False
                    break


class TestCLIVerification:
    def test_parse_pipeline_config_exported(self):
        # parse_pipeline_config is importable and callable
        assert callable(parse_pipeline_config)

    def test_cli_help(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pipeline_runner.py'), '--help'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert '--task' in result.stdout
        assert '--phases' in result.stdout
        assert '--resume' in result.stdout
