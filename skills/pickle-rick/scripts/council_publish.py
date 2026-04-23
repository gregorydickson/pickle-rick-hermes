#!/usr/bin/env python3
"""
Council Publish — auto-publish PR comments at Council of Ricks session end.

Ported from pickle-rick-claude v1.48.0 council-publish.ts.
Reads council-stack.json, council-of-ricks-summary.md, and council-directive.md
to compose per-branch PR comments, then posts them via `gh pr comment`.

Usage:
    python3 council_publish.py <SESSION_ROOT> [--dry-run]

Exit codes:
    0 — success (some comments may be skipped, see report)
    1 — fatal error (bad session, missing stack, gh unavailable)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


class CouncilPublishError(Exception):
    pass


class PublishResult:
    def __init__(self, branch: str, outcome: str, pr_number: Optional[int] = None,
                 error: Optional[str] = None, body_path: Optional[str] = None):
        self.branch = branch
        self.outcome = outcome
        self.pr_number = pr_number
        self.error = error
        self.body_path = body_path

    def to_dict(self) -> dict:
        d = {'branch': self.branch, 'outcome': self.outcome}
        if self.pr_number is not None:
            d['pr_number'] = self.pr_number
        if self.error is not None:
            d['error'] = self.error
        if self.body_path is not None:
            d['body_path'] = self.body_path
        return d


class PublishReport:
    def __init__(self, session_root: str, results: List[PublishResult]):
        self.session_root = session_root
        self.results = results
        self.posted = sum(1 for r in results if r.outcome == 'posted')
        self.skipped = sum(1 for r in results if r.outcome.startswith('skipped'))
        self.failed = sum(1 for r in results if r.outcome == 'failed')

    def to_dict(self) -> dict:
        return {
            'session_root': self.session_root,
            'results': [r.to_dict() for r in self.results],
            'posted': self.posted,
            'skipped': self.skipped,
            'failed': self.failed,
        }


def _safe_error_message(err) -> str:
    if isinstance(err, Exception):
        return str(err)
    return str(err)


def _slugify(branch: str) -> str:
    return branch.replace('/', '__')


def extract_pass_outcomes(summary_path: Path) -> List[str]:
    """Scan council-of-ricks-summary.md for `## Pass N:` headers."""
    if not summary_path.exists():
        return []
    try:
        content = summary_path.read_text()
        passes = []
        for line in content.split('\n'):
            m = re.match(r'^##\s+Pass\s+(\d+)\s*:\s*(.+?)\s*$', line, re.I)
            if m:
                passes.append(f"- Pass {m.group(1)}: {m.group(2).strip()}")
        return passes
    except OSError:
        return []


def read_latest_directive(directive_path: Path) -> str:
    """Read council-directive.md, return the LAST directive block."""
    if not directive_path.exists():
        return ''
    try:
        content = directive_path.read_text()
        markers = [m.start() for m in re.finditer(r'^# Council Directive', content, re.M)]
        if not markers:
            return content
        return content[markers[-1]:]
    except OSError:
        return ''


def findings_for_branch(directive: str, branch: str) -> List[str]:
    """Extract per-branch table rows from the latest directive."""
    if not directive:
        return []
    lines = directive.split('\n')
    rows = []
    header = None
    used_header = None
    branch_col = -1
    for raw in lines:
        line = raw.strip()
        if not line.startswith('|'):
            header = None
            branch_col = -1
            continue
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if header is None:
            try:
                branch_col = [c.lower() for c in cells].index('branch')
                header = cells
                used_header = cells
            except ValueError:
                pass
            continue
        if all(re.match(r'^:?-+:?$', c) for c in cells):
            continue
        if 0 <= branch_col < len(cells) and cells[branch_col] == branch:
            rows.append(line)
    if not rows or not used_header:
        return []
    sep = '| ' + ' | '.join(['---'] * len(used_header)) + ' |'
    return ['| ' + ' | '.join(used_header) + ' |', sep] + rows


def trap_doors_for_branch(directive: str, branch: str) -> str:
    """Extract ## Trap Doors section text, filtered to branch mentions."""
    if not directive:
        return ''
    lines = directive.split('\n')
    in_section = False
    collected = []
    for line in lines:
        if re.match(r'^##\s+Trap Doors', line, re.I):
            in_section = True
            continue
        if in_section and re.match(r'^##\s+', line):
            break
        if in_section:
            collected.append(line)
    body = '\n'.join(collected).strip()
    if not body:
        return ''
    kept = [
        l for l in body.split('\n')
        if l.strip() and (branch in l or not re.search(r'\bfeat/|\bfix/|\bchore/', l))
    ]
    return '\n'.join(kept).strip()


def compose_body(
    session_root: str,
    branch: str,
    final_pass: int,
    codex_enabled: bool,
    findings: List[str],
    trap_doors: str,
    pass_outcomes: List[str],
) -> str:
    session_name = Path(session_root).name
    codex_line = 'enabled: ran on this branch' if codex_enabled else 'disabled: not available'
    findings_block = '\n'.join(findings) if findings else 'No findings for this branch at session close.'
    trap_block = trap_doors if trap_doors else 'None catalogued.'
    pass_block = '\n'.join(pass_outcomes) if pass_outcomes else '- (no passes recorded)'
    return (
        '## Council of Ricks — Stack Review\n'
        '\n'
        '_Posted at session end. See the [Council skill](https://github.com/gregorydickson/pickle-rick-hermes) for the multi-pass review protocol._\n'
        '\n'
        f'**Session:** `{session_name}`\n'
        f'**Final pass:** {final_pass}\n'
        f'**Codex adversarial:** {codex_line}\n'
        '\n'
        '### Findings for this branch\n'
        '\n'
        f'{findings_block}\n'
        '\n'
        '### Trap Doors\n'
        '\n'
        f'{trap_block}\n'
        '\n'
        '### Pass outcomes (this session)\n'
        '\n'
        f'{pass_block}\n'
        '\n'
    )


def append_publish_log(log_path: Path, result: PublishResult) -> None:
    entry = {'ts': __import__('datetime').datetime.now().isoformat(), **result.to_dict()}
    with open(log_path, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def publish_council_stack(session_root: str, dry_run: bool = False,
                          gh_command: str = 'gh') -> PublishReport:
    root = Path(session_root)
    if not root.exists():
        raise CouncilPublishError(f'session_root does not exist: {session_root}')

    stack_path = root / 'council-stack.json'
    if not stack_path.exists():
        raise CouncilPublishError(f'not a council session: council-stack.json missing at {stack_path}')

    try:
        stack = json.loads(stack_path.read_text())
    except (json.JSONDecodeError, OSError) as err:
        raise CouncilPublishError(f'failed to parse council-stack.json: {_safe_error_message(err)}')

    branches = stack.get('branches')
    trunk = stack.get('trunk')
    repo_path = stack.get('repo_path')
    codex_enabled = stack.get('codex_enabled', False)

    if not isinstance(branches, list) or not isinstance(trunk, str) or not isinstance(repo_path, str):
        raise CouncilPublishError('council-stack.json missing required fields (branches, trunk, repo_path)')

    comments_dir = root / 'council-comments'
    comments_dir.mkdir(parents=True, exist_ok=True)
    published_dir = root / '.published'
    published_dir.mkdir(parents=True, exist_ok=True)
    log_path = root / 'publish.log'

    # gh availability check
    gh_available = True
    try:
        subprocess.run([gh_command, 'auth', 'status'],
                       capture_output=True, text=True, timeout=30, check=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        gh_available = False

    summary_path = root / 'council-of-ricks-summary.md'
    pass_outcomes = extract_pass_outcomes(summary_path)
    final_pass = len(pass_outcomes)
    directive_path = root / 'council-directive.md'
    directive = read_latest_directive(directive_path)

    results: List[PublishResult] = []
    for branch in branches:
        if branch == trunk:
            continue
        slug = _slugify(branch)
        body_path = comments_dir / f'{slug}.md'
        marker_path = published_dir / slug

        body = compose_body(
            session_root=str(root),
            branch=branch,
            final_pass=final_pass,
            codex_enabled=bool(codex_enabled),
            findings=findings_for_branch(directive, branch),
            trap_doors=trap_doors_for_branch(directive, branch),
            pass_outcomes=pass_outcomes,
        )
        body_path.write_text(body)

        if not gh_available:
            r = PublishResult(branch, 'skipped_no_gh', body_path=str(body_path))
            results.append(r)
            append_publish_log(log_path, r)
            continue

        if marker_path.exists():
            r = PublishResult(branch, 'skipped_already_published', body_path=str(body_path))
            results.append(r)
            append_publish_log(log_path, r)
            continue

        # Resolve PR number
        pr_number = None
        try:
            out = subprocess.run(
                [gh_command, 'pr', 'list', '--head', branch, '--json', 'number', '--jq', '.[0].number'],
                cwd=repo_path, capture_output=True, text=True, timeout=30,
            )
            pr_text = out.stdout.strip()
            if not pr_text or out.returncode != 0:
                r = PublishResult(branch, 'skipped_no_pr', body_path=str(body_path))
                results.append(r)
                append_publish_log(log_path, r)
                continue
            n = int(pr_text)
            if n <= 0:
                r = PublishResult(branch, 'skipped_no_pr', body_path=str(body_path))
                results.append(r)
                append_publish_log(log_path, r)
                continue
            pr_number = n
        except (ValueError, subprocess.TimeoutExpired, OSError) as err:
            r = PublishResult(branch, 'failed', error=f'pr list: {_safe_error_message(err)}', body_path=str(body_path))
            results.append(r)
            append_publish_log(log_path, r)
            continue

        if dry_run:
            r = PublishResult(branch, 'posted', pr_number=pr_number, body_path=str(body_path))
            results.append(r)
            append_publish_log(log_path, r)
            continue

        # Post the comment
        try:
            subprocess.run(
                [gh_command, 'pr', 'comment', str(pr_number), '--body-file', str(body_path)],
                cwd=repo_path, capture_output=True, text=True, timeout=60, check=True,
            )
            marker_path.write_text(__import__('datetime').datetime.now().isoformat())
            r = PublishResult(branch, 'posted', pr_number=pr_number, body_path=str(body_path))
            results.append(r)
            append_publish_log(log_path, r)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as err:
            r = PublishResult(branch, 'failed', pr_number=pr_number,
                              error=f'pr comment: {_safe_error_message(err)}', body_path=str(body_path))
            results.append(r)
            append_publish_log(log_path, r)

    return PublishReport(session_root=str(root), results=results)


def main():
    parser = argparse.ArgumentParser(description='Council Publish — auto-publish PR comments')
    parser.add_argument('session_root', help='Session root directory')
    parser.add_argument('--dry-run', action='store_true', help='Compose but do not post')
    parser.add_argument('--gh-command', default='gh', help='gh CLI command name/path')
    args = parser.parse_args()

    try:
        report = publish_council_stack(
            session_root=args.session_root,
            dry_run=args.dry_run,
            gh_command=args.gh_command,
        )
        print(json.dumps(report.to_dict(), indent=2))
        sys.exit(0 if report.failed == 0 else 1)
    except CouncilPublishError as err:
        print(f'council-publish: {err}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
