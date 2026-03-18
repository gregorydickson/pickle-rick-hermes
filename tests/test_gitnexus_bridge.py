"""Tests for gitnexus_bridge.py — code graph queries."""

import json
import sys
import subprocess
import pytest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from gitnexus_bridge import is_available, analyze, query_graph, check_violations


class TestIsAvailable:
    def test_returns_bool(self):
        result = is_available()
        assert isinstance(result, bool)


class TestAnalyze:
    def test_analyze_fallback(self, tmp_git_repo):
        """When GitNexus is not installed, uses grep fallback."""
        result = analyze(str(tmp_git_repo))
        assert 'method' in result
        assert result['method'] in ('gitnexus', 'grep-fallback')
        assert 'data' in result

    def test_analyze_nonexistent_dir(self, tmp_path):
        result = analyze(str(tmp_path / 'nonexistent'))
        assert 'method' in result


class TestQueryGraph:
    def test_query_fallback(self, tmp_git_repo):
        # Create a file to search
        (tmp_git_repo / 'auth.ts').write_text('export function validate() {}')
        result = query_graph(str(tmp_git_repo), 'what uses auth.ts')
        assert 'results' in result

    def test_query_empty(self, tmp_git_repo):
        result = query_graph(str(tmp_git_repo), 'nonexistent_symbol_xyz')
        assert 'results' in result


class TestCheckViolations:
    def test_no_eslint(self, tmp_git_repo):
        result = check_violations(str(tmp_git_repo))
        assert 'violations' in result
        assert 'total_violations' in result
        assert result['eslint_config_found'] is False

    def test_with_eslint_config(self, tmp_git_repo):
        (tmp_git_repo / '.eslintrc.json').write_text('{}')
        result = check_violations(str(tmp_git_repo))
        assert result['eslint_config_found'] is True


class TestCLI:
    def test_check(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'gitnexus_bridge.py'), 'check'],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        assert 'GITNEXUS_AVAILABLE=' in result.stdout
