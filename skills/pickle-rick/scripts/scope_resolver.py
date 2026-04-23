#!/usr/bin/env python3
"""
Scope Resolver — NO-OP COMPAT STUB for pickle-rick-hermes.

This module provides the same API surface as pickle-rick-claude's
scope-resolver.ts (v1.45.0+) but with passthrough / no-op behavior.

Full scope-resolver port (git-backed one-hop importer walk, schema
validation, per-phase refresh) is deferred to a dedicated sync cycle.
This stub prevents pipeline_runner and other consumers from breaking
when scope flags are present.

Usage:
    from scope_resolver import parse_scope, resolve_scope, refresh_scope
    parsed = parse_scope("branch:strict")  # OK, returns stub
    scope = resolve_scope(args)             # OK, writes empty scope.json
    refreshed = refresh_scope(root, phase)  # OK, returns None (no-op)
"""

import argparse
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any


# ---------------------------------------------------------------------------
# Types (compatible with TS interfaces)
# ---------------------------------------------------------------------------

ScopeMode = str  # 'branch' | 'diff' | 'paths'
ScopeStrategy = str  # 'strict' | 'one-hop'
ScopeErrorCode = str


class ScopeError(Exception):
    """Scope resolution error with machine-readable code."""
    def __init__(self, code: ScopeErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.name = 'ScopeError'


class ParsedScope:
    def __init__(self, mode: ScopeMode, strategy: ScopeStrategy, base: Optional[str]):
        self.mode = mode
        self.strategy = strategy
        self.base = base

    def to_dict(self) -> dict:
        return {'mode': self.mode, 'strategy': self.strategy, 'base': self.base}


class ScopeJson:
    def __init__(self, allowed_paths: List[str], **kwargs):
        self.version = 1
        self.mode = kwargs.get('mode', 'branch')
        self.strategy = kwargs.get('strategy', 'strict')
        self.base_ref = kwargs.get('base_ref')
        self.base_sha = kwargs.get('base_sha')
        self.head_sha = kwargs.get('head_sha')
        self.allowed_paths = allowed_paths
        self.resolved_at = kwargs.get('resolved_at', '')
        self.refresh_history = kwargs.get('refresh_history', [])

    def to_dict(self) -> dict:
        return {
            'version': self.version,
            'mode': self.mode,
            'strategy': self.strategy,
            'base_ref': self.base_ref,
            'base_sha': self.base_sha,
            'head_sha': self.head_sha,
            'allowed_paths': self.allowed_paths,
            'resolved_at': self.resolved_at,
            'refresh_history': self.refresh_history,
        }


# ---------------------------------------------------------------------------
# Error codes (mirror TS enum)
# ---------------------------------------------------------------------------

SCOPE_EMPTY_DIFF = 'SCOPE_EMPTY_DIFF'
SCOPE_EMPTY_PATHS = 'SCOPE_EMPTY_PATHS'
SCOPE_NOT_A_REPO = 'SCOPE_NOT_A_REPO'
SCOPE_BASE_MISSING = 'SCOPE_BASE_MISSING'
SCOPE_BAD_FLAG = 'SCOPE_BAD_FLAG'
SCOPE_ONE_HOP_TOO_LARGE = 'SCOPE_ONE_HOP_TOO_LARGE'
SCOPE_EMPTY_POST_BUILD = 'SCOPE_EMPTY_POST_BUILD'
SCOPE_ARCHIVE_EXISTS = 'SCOPE_ARCHIVE_EXISTS'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_scope(flag: str) -> ParsedScope:
    """
    Parse the raw --scope <flag> into {mode, strategy, base}.
    Stub: accepts all valid forms, returns passthrough objects.
    """
    if not isinstance(flag, str) or not flag:
        raise ScopeError(SCOPE_BAD_FLAG, f'Unrecognized --scope value: {flag!r}')
    if flag == 'branch' or flag == 'branch:strict':
        return ParsedScope('branch', 'strict', None)
    if flag == 'branch:one-hop':
        return ParsedScope('branch', 'one-hop', None)
    if flag.startswith('diff:'):
        parts = flag.split(':')
        if len(parts) == 2 and parts[1]:
            return ParsedScope('diff', 'strict', parts[1])
        if len(parts) == 3 and parts[1] and parts[2] == 'one-hop':
            return ParsedScope('diff', 'one-hop', parts[1])
        raise ScopeError(SCOPE_BAD_FLAG, f'Malformed --scope diff form: {flag}')
    if flag.startswith('paths:'):
        rest = flag[len('paths:'):]
        if not rest:
            raise ScopeError(SCOPE_BAD_FLAG, '--scope paths: requires at least one glob')
        return ParsedScope('paths', 'strict', rest)
    raise ScopeError(SCOPE_BAD_FLAG, f'Unrecognized --scope value: {flag}')


def resolve_scope(
    scope_flag: str,
    session_root: str,
    repo_root: str,
    scope_base: Optional[str] = None,
    target: Optional[str] = None,
) -> ScopeJson:
    """
    Resolve scope and persist scope.json at session_root.
    Stub: writes an empty allowed_paths list so downstream consumers
    see "everything allowed" (passthrough behavior).
    """
    parsed = parse_scope(scope_flag)

    # No-op: empty allowed_paths means "no restriction" for filter_by_paths
    scope = ScopeJson(
        allowed_paths=[],
        mode=parsed.mode,
        strategy=parsed.strategy,
        base_ref=scope_base or parsed.base,
        base_sha=None,
        head_sha=None,
        resolved_at='',  # empty = stub marker
        refresh_history=[],
    )

    scope_path = Path(session_root) / 'scope.json'
    _write_scope_json(scope_path, scope.to_dict())
    return scope


def refresh_scope(
    session_root: str,
    phase: str,
    repo_root: Optional[str] = None,
    log: Optional[Any] = None,
) -> Optional[ScopeJson]:
    """
    Per-phase scope refresh. Stub: returns None (no scope configured).
    """
    scope_path = Path(session_root) / 'scope.json'
    if not scope_path.exists():
        return None

    # Read existing stub, return as-is (no-op refresh)
    try:
        data = json.loads(scope_path.read_text())
        return ScopeJson(
            allowed_paths=data.get('allowed_paths', []),
            mode=data.get('mode', 'branch'),
            strategy=data.get('strategy', 'strict'),
            base_ref=data.get('base_ref'),
            base_sha=data.get('base_sha'),
            head_sha=data.get('head_sha'),
            resolved_at=data.get('resolved_at', ''),
            refresh_history=data.get('refresh_history', []),
        )
    except (json.JSONDecodeError, OSError):
        return None


def filter_by_subsystem(
    subsystems: List[str],
    allowed_paths: List[str],
    target: str,
    repo_root: str,
) -> List[str]:
    """
    Narrow subsystem list to those intersecting allowed_paths.
    Stub: if allowed_paths is empty (no-op mode), returns all subsystems.
    """
    if not allowed_paths:
        return sorted(set(subsystems))
    # Real implementation would check path prefixes
    return sorted(set(subsystems))


def filter_by_paths(
    globbed_files: List[str],
    allowed_paths: List[str],
    repo_root: str,
) -> List[str]:
    """
    Filter globbed files to those in allowed_paths.
    Stub: if allowed_paths is empty, returns all files.
    """
    if not allowed_paths:
        return list(globbed_files)
    # Real implementation would check membership
    return list(globbed_files)


def compute_one_hop(diff_files: List[str], repo_root: str) -> List[str]:
    """
    One-hop importer expansion. Stub: returns input unchanged.
    """
    return list(diff_files)


def build_scope_v1_schema() -> dict:
    """Canonical JSON Schema for ScopeJson."""
    return {
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        '$id': 'https://pickle-rick/schemas/scope-v1.json',
        'title': 'ScopeJson',
        'type': 'object',
        'additionalProperties': False,
        'required': [
            'version', 'mode', 'strategy', 'base_ref', 'base_sha',
            'head_sha', 'allowed_paths', 'resolved_at', 'refresh_history',
        ],
        'properties': {
            'version': {'const': 1},
            'mode': {'type': 'string', 'enum': ['branch', 'diff', 'paths']},
            'strategy': {'type': 'string', 'enum': ['strict', 'one-hop']},
            'base_ref': {'type': ['string', 'null']},
            'base_sha': {'type': ['string', 'null']},
            'head_sha': {'type': ['string', 'null']},
            'allowed_paths': {
                'type': 'array',
                'items': {'type': 'string'},
            },
            'resolved_at': {'type': 'string'},
            'refresh_history': {
                'type': 'array',
                'maxItems': 16,
                'items': {
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['phase', 'head_sha', 'resolved_at'],
                    'properties': {
                        'phase': {'type': 'string'},
                        'head_sha': {'type': ['string', 'null']},
                        'resolved_at': {'type': 'string'},
                    },
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_scope_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(f'.tmp.{os.getpid()}')
    try:
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp), str(path))
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            path.write_text(json.dumps(data, indent=2))
        except OSError:
            pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Scope Resolver — NO-OP stub')
    parser.add_argument('scope_flag', help='Scope flag (e.g. branch:strict)')
    parser.add_argument('--session-root', required=True)
    parser.add_argument('--repo-root', required=True)
    parser.add_argument('--scope-base', default=None)
    parser.add_argument('--target', default=None)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    scope = resolve_scope(
        scope_flag=args.scope_flag,
        session_root=args.session_root,
        repo_root=args.repo_root,
        scope_base=args.scope_base,
        target=args.target,
    )

    if args.dry_run:
        print(json.dumps(scope.to_dict(), indent=2))
    else:
        print(f"scope-resolver (stub): wrote {args.session_root}/scope.json")
        print(f"  mode={scope.mode}, strategy={scope.strategy}, allowed_paths={len(scope.allowed_paths)} entries")


if __name__ == '__main__':
    main()
