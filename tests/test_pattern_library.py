"""Tests for pattern_library.py — pattern persistence."""

import json
import sys
import subprocess
import pytest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import pattern_library
from pattern_library import load_index, save_index, slugify


class TestSlugify:
    def test_simple(self):
        assert slugify('auth-pattern') == 'auth-pattern'

    def test_spaces(self):
        assert slugify('my cool pattern') == 'my-cool-pattern'

    def test_special_chars(self):
        assert slugify('auth/jwt.v2') == 'auth-jwt-v2'

    def test_uppercase(self):
        assert slugify('MyPattern') == 'mypattern'

    def test_empty(self):
        assert slugify('') == 'pattern'

    def test_multiple_dashes(self):
        assert slugify('a---b') == 'a-b'


class TestIndex:
    def test_load_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pattern_library, 'PATTERNS_ROOT', tmp_path / 'patterns')
        monkeypatch.setattr(pattern_library, 'INDEX_PATH', tmp_path / 'patterns' / 'index.json')
        idx = load_index()
        assert 'patterns' in idx
        assert len(idx['patterns']) == 0

    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pattern_library, 'PATTERNS_ROOT', tmp_path / 'patterns')
        monkeypatch.setattr(pattern_library, 'INDEX_PATH', tmp_path / 'patterns' / 'index.json')
        idx = {'patterns': [{'name': 'test', 'source': 'local', 'date': '2026-01-01',
                             'summary': 'A test', 'analysis_path': '/tmp/a.md',
                             'saved_at': '2026-01-01'}], 'created': '2026-01-01'}
        save_index(idx)
        loaded = load_index()
        assert len(loaded['patterns']) == 1
        assert loaded['patterns'][0]['name'] == 'test'

    def test_save_creates_markdown_index(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pattern_library, 'PATTERNS_ROOT', tmp_path / 'patterns')
        monkeypatch.setattr(pattern_library, 'INDEX_PATH', tmp_path / 'patterns' / 'index.json')
        save_index({'patterns': [{'name': 'x', 'source': 's', 'date': 'd', 'summary': 'sum',
                                  'analysis_path': 'p', 'saved_at': 'sa'}], 'created': 'c'})
        md = (tmp_path / 'patterns' / 'index.md').read_text()
        assert '# Pattern Library' in md
        assert '| x |' in md

    def test_corrupt_index(self, tmp_path, monkeypatch):
        pdir = tmp_path / 'patterns'
        pdir.mkdir()
        monkeypatch.setattr(pattern_library, 'PATTERNS_ROOT', pdir)
        monkeypatch.setattr(pattern_library, 'INDEX_PATH', pdir / 'index.json')
        (pdir / 'index.json').write_text('broken')
        idx = load_index()
        assert len(idx['patterns']) == 0


class TestCLI:
    def test_list_empty(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pattern_library.py'), 'list'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_search_no_results(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pattern_library.py'),
             'search', '--query', 'nonexistent_xyz'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert 'No patterns' in result.stdout

    def test_get_nonexistent(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pattern_library.py'),
             'get', '--name', 'nonexistent_xyz'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0
