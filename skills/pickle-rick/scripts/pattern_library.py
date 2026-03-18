#!/usr/bin/env python3
"""
Pattern Library for Pickle Rick Portal Gun.

Persistent storage for extracted code patterns, enabling reuse across
portal-gun sessions. Patterns are indexed and searchable.

Usage:
    python3 pattern_library.py save --name "auth-pattern" --source "github.com/owner/repo" \
        --analysis /path/to/pattern_analysis.md --summary "JWT auth with refresh tokens"
    
    python3 pattern_library.py search --query "auth"
    python3 pattern_library.py list
    python3 pattern_library.py get --name "auth-pattern"
    python3 pattern_library.py remove --name "auth-pattern"
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path

PATTERNS_ROOT = Path.home() / '.pickle-rick' / 'patterns'
INDEX_PATH = PATTERNS_ROOT / 'index.json'


def load_index() -> dict:
    """Load the pattern index."""
    if INDEX_PATH.exists():
        try:
            return json.loads(INDEX_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {'patterns': [], 'created': datetime.datetime.now().isoformat()}


def save_index(index: dict) -> None:
    """Save the pattern index."""
    PATTERNS_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = INDEX_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(index, indent=2))
    os.rename(str(tmp), str(INDEX_PATH))
    
    # Also write a human-readable index.md
    md_path = PATTERNS_ROOT / 'index.md'
    lines = [
        '# Pattern Library',
        'Extracted patterns available for future portal-gun sessions.',
        '',
        '| Pattern | Source | Date | Summary |',
        '|:---|:---|:---|:---|',
    ]
    for p in index['patterns']:
        lines.append(f"| {p['name']} | {p['source']} | {p['date']} | {p['summary']} |")
    md_path.write_text('\n'.join(lines) + '\n')


def slugify(name: str) -> str:
    """Convert name to a safe slug."""
    slug = re.sub(r'[^a-zA-Z0-9_-]', '-', name.lower())
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug or 'pattern'


def cmd_save(args):
    """Save a pattern to the library."""
    index = load_index()
    name = slugify(args.name)
    
    # Check for existing
    existing = [p for p in index['patterns'] if p['name'] == name]
    if existing and not args.force:
        print(f"Pattern '{name}' already exists. Use --force to overwrite.")
        sys.exit(1)
    
    # Copy analysis file
    PATTERNS_ROOT.mkdir(parents=True, exist_ok=True)
    pattern_dir = PATTERNS_ROOT / name
    pattern_dir.mkdir(exist_ok=True)
    
    analysis_path = Path(args.analysis)
    if analysis_path.exists():
        shutil.copy2(str(analysis_path), str(pattern_dir / 'pattern_analysis.md'))
    else:
        print(f"Warning: Analysis file not found: {analysis_path}")
    
    # Update index
    entry = {
        'name': name,
        'source': args.source or 'unknown',
        'date': datetime.datetime.now().strftime('%Y-%m-%d'),
        'summary': args.summary or '',
        'analysis_path': str(pattern_dir / 'pattern_analysis.md'),
        'saved_at': datetime.datetime.now().isoformat(),
    }
    
    if existing:
        index['patterns'] = [p for p in index['patterns'] if p['name'] != name]
    index['patterns'].append(entry)
    save_index(index)
    
    print(f"Saved pattern: {name}")
    print(f"  Source: {entry['source']}")
    print(f"  Path:   {pattern_dir / 'pattern_analysis.md'}")


def cmd_search(args):
    """Search patterns by query."""
    index = load_index()
    query = args.query.lower()
    
    matches = []
    for p in index['patterns']:
        if (query in p['name'].lower() or 
            query in p.get('source', '').lower() or
            query in p.get('summary', '').lower()):
            matches.append(p)
    
    if not matches:
        print(f"No patterns matching '{args.query}'")
        return
    
    print(f"Found {len(matches)} pattern(s):")
    for p in matches:
        print(f"  {p['name']}: {p['summary']}")
        print(f"    Source: {p['source']} | Saved: {p['date']}")


def cmd_list(args):
    """List all patterns."""
    index = load_index()
    patterns = index.get('patterns', [])
    
    if not patterns:
        print("Pattern library is empty.")
        return
    
    print(f"Pattern Library: {len(patterns)} patterns")
    print(f"{'=' * 60}")
    for p in patterns:
        print(f"  {p['name']}")
        print(f"    Source:  {p['source']}")
        print(f"    Summary: {p['summary']}")
        print(f"    Saved:   {p['date']}")
        
        # Check if analysis file exists
        ap = Path(p.get('analysis_path', ''))
        if ap.exists():
            size = ap.stat().st_size
            print(f"    File:    {ap} ({size} bytes)")
        else:
            print(f"    File:    MISSING")
        print()


def cmd_get(args):
    """Get a specific pattern's analysis."""
    index = load_index()
    name = slugify(args.name)
    
    matching = [p for p in index['patterns'] if p['name'] == name]
    if not matching:
        print(f"Pattern '{name}' not found.")
        sys.exit(1)
    
    p = matching[0]
    ap = Path(p.get('analysis_path', ''))
    
    print(f"Pattern: {p['name']}")
    print(f"Source:  {p['source']}")
    print(f"Summary: {p['summary']}")
    print(f"Saved:   {p['date']}")
    print(f"{'=' * 60}")
    
    if ap.exists():
        print(ap.read_text())
    else:
        print(f"Analysis file not found: {ap}")


def cmd_remove(args):
    """Remove a pattern."""
    index = load_index()
    name = slugify(args.name)
    
    before = len(index['patterns'])
    index['patterns'] = [p for p in index['patterns'] if p['name'] != name]
    
    if len(index['patterns']) == before:
        print(f"Pattern '{name}' not found.")
        return
    
    # Remove pattern directory
    pattern_dir = PATTERNS_ROOT / name
    if pattern_dir.exists():
        shutil.rmtree(str(pattern_dir))
    
    save_index(index)
    print(f"Removed pattern: {name}")


def main():
    parser = argparse.ArgumentParser(description='Pickle Rick Pattern Library')
    sub = parser.add_subparsers(dest='command', required=True)
    
    p_save = sub.add_parser('save')
    p_save.add_argument('--name', '-n', required=True)
    p_save.add_argument('--source', '-s', help='Source URL/path')
    p_save.add_argument('--analysis', '-a', required=True, help='Path to pattern_analysis.md')
    p_save.add_argument('--summary', help='Brief summary')
    p_save.add_argument('--force', action='store_true', help='Overwrite existing')
    
    p_search = sub.add_parser('search')
    p_search.add_argument('--query', '-q', required=True)
    
    sub.add_parser('list')
    
    p_get = sub.add_parser('get')
    p_get.add_argument('--name', '-n', required=True)
    
    p_remove = sub.add_parser('remove')
    p_remove.add_argument('--name', '-n', required=True)
    
    args = parser.parse_args()
    {
        'save': cmd_save, 'search': cmd_search,
        'list': cmd_list, 'get': cmd_get, 'remove': cmd_remove,
    }[args.command](args)


if __name__ == '__main__':
    main()
