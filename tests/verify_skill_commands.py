#!/usr/bin/env python3
"""
Verify that all commands referenced in SKILL.md files point to real files.

Runs as a standalone script (no pytest required) for CI integration.
Usage:
    python3 tests/verify_skill_commands.py
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SKILLS_DIR = PROJECT_ROOT / 'skills'

# Patterns that reference script files
SCRIPT_PATTERNS = [
    re.compile(r'python3\s+([^\s\'`"]+\.py)'),
    re.compile(r'bash\s+([^\s\'`"]+\.sh)'),
    re.compile(r'source\s+([^\s\'`"]+\.sh)'),
]

# Commands that are expected to exist on PATH, not as project files
SYSTEM_COMMANDS = {'tmux', 'zellij', 'git', 'hermes', 'cargo', 'brew', 'apt'}


def extract_commands(skill_path: Path) -> list:
    """Extract potential file references from a SKILL.md."""
    refs = []
    content = skill_path.read_text()
    for pattern in SCRIPT_PATTERNS:
        for match in pattern.finditer(content):
            path_str = match.group(1)
            # Skip placeholder examples with < >
            if '<' in path_str or '>' in path_str:
                continue
            refs.append((path_str, skill_path))
    return refs


def resolve_path(path_str: str) -> Path:
    """Resolve a path string that may contain ~ or be relative."""
    # Map installed Hermes skill paths to local repo paths
    repo_root = PROJECT_ROOT
    if path_str.startswith('~/.hermes/skills/autonomous-ai-agents/pickle-rick/'):
        suffix = path_str.split('~/.hermes/skills/autonomous-ai-agents/pickle-rick/', 1)[1]
        return repo_root / 'skills' / 'pickle-rick' / suffix
    if path_str.startswith('~/.hermes/skills/pickle-rick/'):
        suffix = path_str.split('~/.hermes/skills/pickle-rick/', 1)[1]
        return repo_root / 'skills' / 'pickle-rick' / suffix
    if path_str.startswith('~/.hermes/skills/pickle-rick-szechuan-sauce/'):
        suffix = path_str.split('~/.hermes/skills/pickle-rick-szechuan-sauce/', 1)[1]
        return repo_root / 'skills' / 'pickle-rick-szechuan-sauce' / suffix
    if path_str.startswith('~'):
        path_str = str(Path.home()) + path_str[1:]
    p = Path(path_str)
    if p.is_absolute():
        return p
    # Try relative to project root
    return PROJECT_ROOT / p


# Paths that are relative to the skill directory in docs but need cross-skill resolution
SKILL_DIR_ALIASES = {
    'scripts/pickle_state.py': 'skills/pickle-rick/scripts/pickle_state.py',
    'scripts/mux_runner.py': 'skills/pickle-rick/scripts/mux_runner.py',
    'scripts/microverse_runner.py': 'skills/pickle-rick/scripts/microverse_runner.py',
    'scripts/circuit_breaker.py': 'skills/pickle-rick/scripts/circuit_breaker.py',
    'scripts/pickle_jar.py': 'skills/pickle-rick/scripts/pickle_jar.py',
    'scripts/pattern_library.py': 'skills/pickle-rick/scripts/pattern_library.py',
    'scripts/pickle_utils.py': 'skills/pickle-rick/scripts/pickle_utils.py',
    'scripts/monitor.py': 'skills/pickle-rick/scripts/monitor.py',
    'scripts/tmux-monitor.sh': 'skills/pickle-rick/scripts/tmux-monitor.sh',
    'scripts/init_microverse.py': 'skills/pickle-rick/scripts/microverse_runner.py',
}


def main() -> int:
    skill_files = list(SKILLS_DIR.rglob('SKILL.md'))
    if not skill_files:
        print(f"ERROR: No SKILL.md files found under {SKILLS_DIR}")
        return 1

    all_ok = True
    total_commands = 0

    for skill_path in sorted(skill_files):
        refs = extract_commands(skill_path)
        if not refs:
            continue

        rel_skill = skill_path.relative_to(PROJECT_ROOT)
        for path_str, src in refs:
            total_commands += 1
            resolved = resolve_path(path_str)
            if not resolved.exists():
                # Also check if it's a known system command
                cmd_name = Path(path_str).name
                if cmd_name in SYSTEM_COMMANDS:
                    continue
                # Check cross-skill aliases
                alias = SKILL_DIR_ALIASES.get(path_str)
                if alias:
                    alias_path = PROJECT_ROOT / alias
                    if alias_path.exists():
                        continue
                print(f"MISSING: {path_str}")
                print(f"  referenced in: {rel_skill}")
                all_ok = False

    if all_ok:
        print(f"OK: All {total_commands} script references in {len(skill_files)} SKILL.md files exist.")
        return 0
    else:
        print(f"\nFAIL: Some referenced scripts do not exist.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
