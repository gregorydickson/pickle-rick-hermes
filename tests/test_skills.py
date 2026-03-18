"""Tests for SKILL.md files — frontmatter, structure, correctness."""

import re
import pytest
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent / 'skills'


def get_all_skills():
    """Return list of (skill_name, skill_path) tuples."""
    skills = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if d.is_dir() and (d / 'SKILL.md').exists():
            skills.append((d.name, d / 'SKILL.md'))
    return skills


ALL_SKILLS = get_all_skills()
SKILL_NAMES = [name for name, _ in ALL_SKILLS]


class TestSkillCount:
    def test_16_skills(self):
        assert len(ALL_SKILLS) == 16, f"Expected 16 skills, got {len(ALL_SKILLS)}: {SKILL_NAMES}"


class TestFrontmatter:
    @pytest.mark.parametrize("name,path", ALL_SKILLS, ids=SKILL_NAMES)
    def test_has_frontmatter(self, name, path):
        content = path.read_text()
        assert content.startswith('---'), f"{name}: missing YAML frontmatter"
        assert content.count('---') >= 2, f"{name}: incomplete frontmatter"

    @pytest.mark.parametrize("name,path", ALL_SKILLS, ids=SKILL_NAMES)
    def test_name_matches_directory(self, name, path):
        content = path.read_text()
        fm_name = re.search(r'^name:\s*(.+)$', content, re.MULTILINE)
        assert fm_name, f"{name}: missing name field"
        actual = fm_name.group(1).strip().strip('"').strip("'")
        assert actual == name, f"{name}: frontmatter name '{actual}' != directory '{name}'"

    @pytest.mark.parametrize("name,path", ALL_SKILLS, ids=SKILL_NAMES)
    def test_has_description(self, name, path):
        content = path.read_text()
        assert re.search(r'^description:', content, re.MULTILINE), f"{name}: missing description"

    @pytest.mark.parametrize("name,path", ALL_SKILLS, ids=SKILL_NAMES)
    def test_has_tags(self, name, path):
        content = path.read_text()
        assert 'tags:' in content, f"{name}: missing tags"


class TestStructure:
    @pytest.mark.parametrize("name,path", ALL_SKILLS, ids=SKILL_NAMES)
    def test_has_h1_title(self, name, path):
        content = path.read_text()
        # Find content after frontmatter
        parts = content.split('---', 2)
        body = parts[2] if len(parts) >= 3 else content
        assert re.search(r'^# .+', body, re.MULTILINE), f"{name}: missing H1 title"

    @pytest.mark.parametrize("name,path", ALL_SKILLS, ids=SKILL_NAMES)
    def test_has_when_to_use_or_exemption(self, name, path):
        """All skills should have 'When to Use' unless they're reference-only."""
        content = path.read_text()
        exemptions = ['pickle-rick-dot-patterns']  # Reference-only, loaded on demand
        if name in exemptions:
            return
        assert '## When to Use' in content or 'Load this skill on demand' in content, \
            f"{name}: missing 'When to Use' section"


class TestNoClaudioms:
    @pytest.mark.parametrize("name,path", ALL_SKILLS, ids=SKILL_NAMES) 
    def test_no_claude_cli_refs(self, name, path):
        content = path.read_text()
        # These patterns indicate Claude Code-specific instructions
        bad_patterns = [
            (r'node "\$HOME/\.claude/', 'References Claude Code CLI'),
            (r'--dangerously-skip', 'Uses Claude Code permission flag'),
            (r'hooks/.*stop-hook', 'References Claude Code hooks'),
            (r'extension/bin/setup\.js', 'References Claude Code setup script'),
            (r'extension/bin/update-state\.js', 'References Claude Code update script'),
        ]
        for pattern, msg in bad_patterns:
            assert not re.search(pattern, content), f"{name}: {msg}"

    @pytest.mark.parametrize("name,path", ALL_SKILLS, ids=SKILL_NAMES)
    def test_no_promise_xml_tags(self, name, path):
        """Signal tokens should use [TOKEN] format, not <promise> XML."""
        content = path.read_text()
        matches = re.findall(r'<promise>.*?</promise>', content)
        assert not matches, f"{name}: uses <promise> XML tags: {matches[:2]}"


class TestCrossReferences:
    def test_main_skill_references_all(self):
        """Main pickle-rick skill should reference all other skills."""
        main = (SKILLS_DIR / 'pickle-rick' / 'SKILL.md').read_text()
        for name in SKILL_NAMES:
            if name == 'pickle-rick':
                continue
            assert name in main, f"pickle-rick SKILL.md doesn't reference {name}"

    def test_help_lists_all(self):
        """Help skill should list all skills."""
        help_content = (SKILLS_DIR / 'pickle-rick-help' / 'SKILL.md').read_text()
        for name in SKILL_NAMES:
            if name == 'pickle-rick-help':
                continue
            assert name in help_content, f"pickle-rick-help doesn't mention {name}"

    @pytest.mark.parametrize("name,path", ALL_SKILLS, ids=SKILL_NAMES)
    def test_related_skills_exist(self, name, path):
        content = path.read_text()
        match = re.search(r'related_skills:\s*\[([^\]]+)\]', content)
        if not match:
            return
        refs = [s.strip().strip('"').strip("'") for s in match.group(1).split(',')]
        external = {'hermes-agent', 'subagent-driven-development',
                    'test-driven-development', 'writing-plans', 'requesting-code-review'}
        for ref in refs:
            assert ref in SKILL_NAMES or ref in external, \
                f"{name}: related_skill '{ref}' not found"


class TestSignalConsistency:
    VALID_TOKENS = [
        '[EPIC_COMPLETED]', '[TASK_COMPLETED]', '[PRD_COMPLETE]',
        '[TICKET_SELECTED]', '[BLOCKED]', '[EXISTENCE_IS_PAIN]',
        '[THE_CITADEL_APPROVES]',
    ]

    @pytest.mark.parametrize("name,path", ALL_SKILLS, ids=SKILL_NAMES)
    def test_signal_tokens_format(self, name, path):
        """Any signal tokens mentioned should use [TOKEN] format."""
        content = path.read_text()
        for token_name in ['EPIC_COMPLETED', 'TASK_COMPLETED', 'PRD_COMPLETE',
                           'TICKET_SELECTED', 'BLOCKED', 'EXISTENCE_IS_PAIN',
                           'THE_CITADEL_APPROVES']:
            if token_name in content:
                # Should appear in [TOKEN] format somewhere
                assert f'[{token_name}]' in content or f"'{token_name}'" in content, \
                    f"{name}: mentions {token_name} but not in [TOKEN] format"
