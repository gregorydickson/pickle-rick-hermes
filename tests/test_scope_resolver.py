"""Tests for scope_resolver.py — no-op compat stub."""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from scope_resolver import (
    ParsedScope,
    ScopeJson,
    ScopeError,
    parse_scope,
    resolve_scope,
    refresh_scope,
    filter_by_paths,
    filter_by_subsystem,
    compute_one_hop,
    build_scope_v1_schema,
    SCOPE_BAD_FLAG,
)


class TestParseScope:
    def test_branch_strict(self):
        s = parse_scope('branch:strict')
        assert s.mode == 'branch'
        assert s.strategy == 'strict'
        assert s.base is None

    def test_branch_one_hop(self):
        s = parse_scope('branch:one-hop')
        assert s.mode == 'branch'
        assert s.strategy == 'one-hop'

    def test_diff_strict(self):
        s = parse_scope('diff:main')
        assert s.mode == 'diff'
        assert s.strategy == 'strict'
        assert s.base == 'main'

    def test_diff_one_hop(self):
        s = parse_scope('diff:main:one-hop')
        assert s.mode == 'diff'
        assert s.strategy == 'one-hop'
        assert s.base == 'main'

    def test_paths(self):
        s = parse_scope('paths:src/**/*.py')
        assert s.mode == 'paths'
        assert s.strategy == 'strict'
        assert s.base == 'src/**/*.py'

    def test_invalid_empty(self):
        with pytest.raises(ScopeError) as exc:
            parse_scope('')
        assert exc.value.code == SCOPE_BAD_FLAG

    def test_invalid_unknown(self):
        with pytest.raises(ScopeError) as exc:
            parse_scope('nonsense')
        assert exc.value.code == SCOPE_BAD_FLAG

    def test_malformed_diff(self):
        with pytest.raises(ScopeError) as exc:
            parse_scope('diff:')
        assert exc.value.code == SCOPE_BAD_FLAG

    def test_malformed_paths(self):
        with pytest.raises(ScopeError) as exc:
            parse_scope('paths:')
        assert exc.value.code == SCOPE_BAD_FLAG


class TestResolveScope:
    def test_writes_scope_json(self, tmp_path):
        session = tmp_path / 'session'
        session.mkdir()
        repo = tmp_path / 'repo'
        repo.mkdir()
        scope = resolve_scope('branch:strict', str(session), str(repo))
        assert (session / 'scope.json').exists()
        data = json.loads((session / 'scope.json').read_text())
        assert data['mode'] == 'branch'
        assert data['strategy'] == 'strict'
        assert data['allowed_paths'] == []

    def test_returns_scope_json_object(self, tmp_path):
        session = tmp_path / 'session'
        session.mkdir()
        repo = tmp_path / 'repo'
        repo.mkdir()
        scope = resolve_scope('diff:main', str(session), str(repo), scope_base='main')
        assert isinstance(scope, ScopeJson)
        assert scope.base_ref == 'main'


class TestRefreshScope:
    def test_missing_returns_none(self, tmp_path):
        assert refresh_scope(str(tmp_path), 'pickle') is None

    def test_reads_existing_stub(self, tmp_path):
        session = tmp_path / 'session'
        session.mkdir()
        (session / 'scope.json').write_text(json.dumps({
            'version': 1, 'mode': 'branch', 'strategy': 'strict',
            'base_ref': None, 'base_sha': None, 'head_sha': None,
            'allowed_paths': [], 'resolved_at': '', 'refresh_history': [],
        }))
        result = refresh_scope(str(session), 'pickle')
        assert isinstance(result, ScopeJson)
        assert result.mode == 'branch'


class TestFilterFunctions:
    def test_filter_by_paths_empty_allowed(self):
        assert filter_by_paths(['a.py', 'b.py'], [], '/repo') == ['a.py', 'b.py']

    def test_filter_by_subsystem_empty_allowed(self):
        assert filter_by_subsystem(['src', 'tests'], [], 'src', '/repo') == ['src', 'tests']

    def test_compute_one_hop_passthrough(self):
        assert compute_one_hop(['a.py', 'b.py'], '/repo') == ['a.py', 'b.py']


class TestSchema:
    def test_build_scope_v1_schema_structure(self):
        schema = build_scope_v1_schema()
        assert schema['$schema'].startswith('https://json-schema.org')
        assert 'version' in schema['required']
        assert 'allowed_paths' in schema['required']
