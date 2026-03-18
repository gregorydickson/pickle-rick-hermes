"""Tests for pickle_jar.py — batch job queue."""

import json
import os
import sys
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch as mock_patch, MagicMock
from argparse import Namespace

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import pickle_jar
from pickle_jar import load_manifest, save_manifest, cmd_add, cmd_remove, cmd_list, cmd_run


@pytest.fixture
def jar_env(tmp_path, monkeypatch):
    """Set up isolated jar environment."""
    monkeypatch.setattr(pickle_jar, 'JAR_ROOT', tmp_path)
    monkeypatch.setattr(pickle_jar, 'MANIFEST_PATH', tmp_path / 'jar_manifest.json')
    return tmp_path


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------

class TestManifest:
    def test_load_empty(self, jar_env):
        m = load_manifest()
        assert 'tasks' in m
        assert len(m['tasks']) == 0

    def test_save_and_load(self, jar_env):
        manifest = {'created': '2026-01-01', 'tasks': [
            {'id': 'abc', 'task': 'test', 'status': 'queued'}
        ]}
        save_manifest(manifest)
        loaded = load_manifest()
        assert len(loaded['tasks']) == 1
        assert loaded['tasks'][0]['id'] == 'abc'

    def test_save_creates_dir(self, tmp_path, monkeypatch):
        jar_dir = tmp_path / 'new_jar'
        monkeypatch.setattr(pickle_jar, 'JAR_ROOT', jar_dir)
        monkeypatch.setattr(pickle_jar, 'MANIFEST_PATH', jar_dir / 'jar_manifest.json')
        save_manifest({'created': '2026-01-01', 'tasks': []})
        assert jar_dir.exists()

    def test_corrupt_manifest_returns_empty(self, jar_env):
        (jar_env / 'jar_manifest.json').write_text('not json')
        m = load_manifest()
        assert len(m['tasks']) == 0

    def test_save_atomic_write(self, jar_env):
        """save_manifest uses tmp+rename for atomicity."""
        save_manifest({'created': '2026-01-01', 'tasks': []})
        # Verify manifest exists and no tmp files linger
        assert (jar_env / 'jar_manifest.json').exists()
        tmps = list(jar_env.glob('*.tmp'))
        assert len(tmps) == 0

    def test_round_trip_preserves_all_fields(self, jar_env):
        task = {
            'id': 'x1', 'task': 'do stuff', 'working_dir': '/tmp',
            'max_iterations': 50, 'mode': 'meeseeks', 'status': 'queued',
            'chain_meeseeks': True, 'added_at': '2026-01-01', 'completed_at': None,
            'session_dir': None,
        }
        save_manifest({'created': '2026-01-01', 'tasks': [task]})
        loaded = load_manifest()
        t = loaded['tasks'][0]
        assert t['mode'] == 'meeseeks'
        assert t['chain_meeseeks'] is True
        assert t['max_iterations'] == 50


# ---------------------------------------------------------------------------
# cmd_add
# ---------------------------------------------------------------------------

class TestCmdAdd:
    def test_add_basic(self, jar_env, capsys):
        args = Namespace(task='Build auth', working_dir='/tmp/project',
                         max_iterations=100, mode='pickle', chain_meeseeks=False)
        cmd_add(args)
        m = load_manifest()
        assert len(m['tasks']) == 1
        t = m['tasks'][0]
        assert t['task'] == 'Build auth'
        assert t['status'] == 'queued'
        assert t['mode'] == 'pickle'
        assert t['chain_meeseeks'] is False
        out = capsys.readouterr().out
        assert 'Added to jar' in out

    def test_add_with_mode(self, jar_env, capsys):
        args = Namespace(task='Review code', working_dir='/tmp/project',
                         max_iterations=50, mode='meeseeks', chain_meeseeks=False)
        cmd_add(args)
        t = load_manifest()['tasks'][0]
        assert t['mode'] == 'meeseeks'
        assert t['max_iterations'] == 50

    def test_add_with_chain_meeseeks(self, jar_env, capsys):
        args = Namespace(task='Build and review', working_dir='/tmp',
                         max_iterations=100, mode='pickle', chain_meeseeks=True)
        cmd_add(args)
        t = load_manifest()['tasks'][0]
        assert t['chain_meeseeks'] is True

    def test_add_multiple(self, jar_env, capsys):
        for i in range(3):
            args = Namespace(task=f'Task {i}', working_dir='/tmp',
                             max_iterations=100, mode='pickle', chain_meeseeks=False)
            cmd_add(args)
        m = load_manifest()
        assert len(m['tasks']) == 3
        assert capsys.readouterr().out.count('Jar size: 3') == 1

    def test_add_creates_task_dir(self, jar_env):
        args = Namespace(task='Build thing', working_dir='/tmp',
                         max_iterations=100, mode='pickle', chain_meeseeks=False)
        cmd_add(args)
        t = load_manifest()['tasks'][0]
        assert (jar_env / t['id']).is_dir()

    def test_add_default_mode(self, jar_env, capsys):
        """Mode defaults to 'pickle' when not set."""
        args = Namespace(task='test', working_dir='/tmp',
                         max_iterations=100, chain_meeseeks=False)
        # Simulate missing mode attribute
        cmd_add(args)
        t = load_manifest()['tasks'][0]
        assert t['mode'] == 'pickle'


# ---------------------------------------------------------------------------
# cmd_remove
# ---------------------------------------------------------------------------

class TestCmdRemove:
    def test_remove_existing(self, jar_env, capsys):
        save_manifest({'created': 'x', 'tasks': [
            {'id': 'keep', 'task': 'keep me', 'status': 'queued'},
            {'id': 'drop', 'task': 'drop me', 'status': 'queued'},
        ]})
        args = Namespace(id='drop')
        cmd_remove(args)
        m = load_manifest()
        assert len(m['tasks']) == 1
        assert m['tasks'][0]['id'] == 'keep'

    def test_remove_nonexistent(self, jar_env, capsys):
        save_manifest({'created': 'x', 'tasks': [
            {'id': 'abc', 'task': 'test', 'status': 'queued'},
        ]})
        args = Namespace(id='nonexistent')
        cmd_remove(args)
        m = load_manifest()
        assert len(m['tasks']) == 1  # unchanged


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------

class TestCmdList:
    def test_list_empty(self, jar_env, capsys):
        cmd_list(Namespace())
        assert 'empty' in capsys.readouterr().out.lower()

    def test_list_shows_tasks(self, jar_env, capsys):
        save_manifest({'created': 'x', 'tasks': [
            {'id': 'abc', 'task': 'Build auth', 'status': 'queued',
             'working_dir': '/tmp', 'max_iterations': 100, 'mode': 'pickle',
             'chain_meeseeks': False, 'session_dir': None},
        ]})
        cmd_list(Namespace())
        out = capsys.readouterr().out
        assert 'Build auth' in out
        assert 'abc' in out
        assert 'Mode: pickle' in out

    def test_list_shows_mode(self, jar_env, capsys):
        save_manifest({'created': 'x', 'tasks': [
            {'id': 'x1', 'task': 'Review', 'status': 'queued',
             'working_dir': '/tmp', 'max_iterations': 50, 'mode': 'meeseeks',
             'chain_meeseeks': False, 'session_dir': None},
        ]})
        cmd_list(Namespace())
        assert 'Mode: meeseeks' in capsys.readouterr().out

    def test_list_shows_chain_meeseeks(self, jar_env, capsys):
        save_manifest({'created': 'x', 'tasks': [
            {'id': 'x1', 'task': 'Build', 'status': 'queued',
             'working_dir': '/tmp', 'max_iterations': 100, 'mode': 'pickle',
             'chain_meeseeks': True, 'session_dir': None},
        ]})
        cmd_list(Namespace())
        assert 'Meeseeks chained' in capsys.readouterr().out

    def test_list_status_icons(self, jar_env, capsys):
        save_manifest({'created': 'x', 'tasks': [
            {'id': 'a', 'task': 'q', 'status': 'queued', 'working_dir': '/t', 'max_iterations': 1, 'chain_meeseeks': False, 'session_dir': None},
            {'id': 'b', 'task': 'd', 'status': 'done', 'working_dir': '/t', 'max_iterations': 1, 'chain_meeseeks': False, 'session_dir': None},
            {'id': 'c', 'task': 'f', 'status': 'failed', 'working_dir': '/t', 'max_iterations': 1, 'chain_meeseeks': False, 'session_dir': None},
        ]})
        cmd_list(Namespace())
        out = capsys.readouterr().out
        assert '[ ]' in out  # queued
        assert '[x]' in out  # done
        assert '[!]' in out  # failed


# ---------------------------------------------------------------------------
# cmd_run (mock subprocess)
# ---------------------------------------------------------------------------

class TestCmdRun:
    def test_run_empty_jar(self, jar_env, capsys):
        cmd_run(Namespace())
        assert 'No queued tasks' in capsys.readouterr().out

    def test_run_builds_correct_cmd(self, jar_env, capsys):
        save_manifest({'created': 'x', 'tasks': [
            {'id': 'x1', 'task': 'Build auth', 'status': 'queued',
             'working_dir': '/tmp/proj', 'max_iterations': 50, 'mode': 'meeseeks',
             'chain_meeseeks': False, 'session_dir': None},
        ]})
        with mock_patch('pickle_jar.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cmd_run(Namespace())
            call_args = mock_run.call_args[0][0]
            assert '--mode' in call_args
            mode_idx = call_args.index('--mode')
            assert call_args[mode_idx + 1] == 'meeseeks'
            assert '--task' in call_args
            assert 'Build auth' in call_args

    def test_run_marks_done_on_success(self, jar_env, capsys):
        save_manifest({'created': 'x', 'tasks': [
            {'id': 'x1', 'task': 'test', 'status': 'queued',
             'working_dir': '/tmp', 'max_iterations': 10, 'mode': 'pickle',
             'chain_meeseeks': False, 'session_dir': None},
        ]})
        with mock_patch('pickle_jar.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cmd_run(Namespace())
        m = load_manifest()
        assert m['tasks'][0]['status'] == 'done'
        assert m['tasks'][0]['completed_at'] is not None

    def test_run_marks_failed_on_error(self, jar_env, capsys):
        save_manifest({'created': 'x', 'tasks': [
            {'id': 'x1', 'task': 'test', 'status': 'queued',
             'working_dir': '/tmp', 'max_iterations': 10, 'mode': 'pickle',
             'chain_meeseeks': False, 'session_dir': None},
        ]})
        with mock_patch('pickle_jar.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            cmd_run(Namespace())
        assert load_manifest()['tasks'][0]['status'] == 'failed'

    def test_run_marks_failed_on_timeout(self, jar_env, capsys):
        save_manifest({'created': 'x', 'tasks': [
            {'id': 'x1', 'task': 'test', 'status': 'queued',
             'working_dir': '/tmp', 'max_iterations': 10, 'mode': 'pickle',
             'chain_meeseeks': False, 'session_dir': None},
        ]})
        with mock_patch('pickle_jar.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd='x', timeout=10)
            cmd_run(Namespace())
        assert load_manifest()['tasks'][0]['status'] == 'failed'

    def test_run_skips_non_queued(self, jar_env, capsys):
        save_manifest({'created': 'x', 'tasks': [
            {'id': 'done1', 'task': 'already done', 'status': 'done',
             'working_dir': '/tmp', 'max_iterations': 10, 'mode': 'pickle',
             'chain_meeseeks': False, 'session_dir': None},
            {'id': 'q1', 'task': 'run me', 'status': 'queued',
             'working_dir': '/tmp', 'max_iterations': 10, 'mode': 'pickle',
             'chain_meeseeks': False, 'session_dir': None},
        ]})
        with mock_patch('pickle_jar.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cmd_run(Namespace())
            assert mock_run.call_count == 1  # only the queued one


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------

class TestCLI:
    def test_list(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_jar.py'), 'list'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_add_cli(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_jar.py'), 'add',
             '--task', 'CLI test', '--working-dir', '/tmp', '--mode', 'meeseeks'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert 'Added to jar' in result.stdout
