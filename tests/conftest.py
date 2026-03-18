"""Shared fixtures for pickle-rick-hermes tests."""

import json
import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path

# Add scripts to path
SCRIPTS_DIR = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def tmp_session(tmp_path):
    """Create a temporary session directory with valid state.json."""
    session_dir = tmp_path / 'session_test'
    session_dir.mkdir()
    (session_dir / 'tickets').mkdir()

    state = {
        'active': True,
        'working_dir': str(tmp_path),
        'step': 'prd',
        'mode': 'pickle',
        'iteration': 0,
        'max_iterations': 100,
        'max_time_minutes': 720,
        'worker_timeout_seconds': 1200,
        'start_time_epoch': 1700000000,
        'completion_promise': None,
        'original_prompt': 'Test task',
        'current_ticket': None,
        'history': [],
        'started_at': '2026-03-17T12:00:00',
        'session_dir': str(session_dir),
        'tmux_mode': False,
        'min_iterations': 0,
        'command_template': None,
        'chain_meeseeks': False,
        'pid': None,
        'schema_version': 1,
    }
    (session_dir / 'state.json').write_text(json.dumps(state, indent=2))
    return session_dir


@pytest.fixture
def tmp_settings(tmp_path):
    """Create a temporary pickle_settings.json."""
    settings = {
        'default_max_iterations': 500,
        'default_cb_no_progress_threshold': 5,
        'default_cb_same_error_threshold': 5,
        'default_cb_half_open_after': 2,
        'default_circuit_breaker_enabled': True,
        'default_rate_limit_wait_minutes': 60,
        'default_max_rate_limit_retries': 3,
    }
    settings_path = tmp_path / 'pickle_settings.json'
    settings_path.write_text(json.dumps(settings))
    return settings_path


@pytest.fixture
def tmp_git_repo(tmp_path):
    """Create a temporary git repository."""
    repo = tmp_path / 'repo'
    repo.mkdir()
    os.system(f'cd {repo} && git init -q && git config user.email "test@test.com" && git config user.name "Test" && touch README.md && git add . && git commit -q -m "init"')
    return repo
