#!/usr/bin/env python3
"""
GitNexus Bridge for Pickle Rick Council of Ricks.

Provides code knowledge graph queries for architectural review.
GitNexus builds a graph of code relationships (imports, dependencies,
layer boundaries) that the Council uses for cross-branch analysis.

If GitNexus is not available, gracefully degrades to grep-based analysis.

Usage:
    python3 gitnexus_bridge.py analyze --repo ~/project
    python3 gitnexus_bridge.py query --repo ~/project --query "what imports auth.ts"
    python3 gitnexus_bridge.py check --repo ~/project
    python3 gitnexus_bridge.py violations --repo ~/project --rules rules.json
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def is_available() -> bool:
    """Check if GitNexus CLI is installed."""
    try:
        result = subprocess.run(
            ['npx', 'gitnexus', '--version'],
            capture_output=True, text=True, timeout=15
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def analyze(repo_path: str) -> dict:
    """Run GitNexus analysis on a repo. Falls back to basic analysis if unavailable."""
    result = {'available': False, 'method': 'fallback', 'data': {}}
    
    if is_available():
        try:
            proc = subprocess.run(
                ['npx', 'gitnexus', 'analyze', '--json'],
                capture_output=True, text=True,
                cwd=repo_path, timeout=120
            )
            if proc.returncode == 0:
                result['available'] = True
                result['method'] = 'gitnexus'
                try:
                    result['data'] = json.loads(proc.stdout)
                except json.JSONDecodeError:
                    result['data'] = {'raw_output': proc.stdout}
                return result
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    # Fallback: basic import analysis using grep
    result['method'] = 'grep-fallback'
    imports = {}
    
    for ext in ['*.ts', '*.tsx', '*.js', '*.jsx', '*.py']:
        try:
            proc = subprocess.run(
                ['grep', '-rn', '--include', ext,
                 '-E', r"^(import |from |require\(|export .* from )",
                 '.'],
                capture_output=True, text=True,
                cwd=repo_path, timeout=30
            )
            for line in proc.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    file_path = parts[0]
                    imports.setdefault(file_path, []).append(parts[2].strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    
    result['data'] = {
        'files_analyzed': len(imports),
        'import_map': imports,
        'note': 'GitNexus not available, using grep-based import analysis'
    }
    return result


def query_graph(repo_path: str, query: str) -> dict:
    """Query the code graph. Falls back to grep if GitNexus unavailable."""
    if is_available():
        try:
            proc = subprocess.run(
                ['npx', 'gitnexus', 'query', query, '--json'],
                capture_output=True, text=True,
                cwd=repo_path, timeout=60
            )
            if proc.returncode == 0:
                try:
                    return {'available': True, 'results': json.loads(proc.stdout)}
                except json.JSONDecodeError:
                    return {'available': True, 'results': proc.stdout}
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    # Fallback: try to answer common queries with grep
    result = {'available': False, 'method': 'grep-fallback', 'results': []}
    
    # Parse simple "what imports X" or "who uses X" queries  
    search_term = query.split()[-1] if query.split() else ''
    if search_term:
        try:
            proc = subprocess.run(
                ['grep', '-rn', '--include', '*.ts', '--include', '*.tsx',
                 '--include', '*.js', '--include', '*.py',
                 search_term, '.'],
                capture_output=True, text=True,
                cwd=repo_path, timeout=30
            )
            for line in proc.stdout.strip().split('\n')[:20]:
                if line.strip():
                    result['results'].append(line)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    return result


def check_violations(repo_path: str, rules_file: str = None) -> dict:
    """Check for architectural violations. Uses ESLint boundaries if available."""
    violations = []
    
    # Check if ESLint with boundaries plugin exists
    eslint_config = None
    for name in ['.eslintrc.json', '.eslintrc.js', '.eslintrc.yml', 'eslint.config.js', 'eslint.config.mjs']:
        p = Path(repo_path) / name
        if p.exists():
            eslint_config = p
            break
    
    # Try running ESLint for boundary violations
    if eslint_config:
        try:
            proc = subprocess.run(
                ['npx', 'eslint', '.', '--format', 'json', '--quiet'],
                capture_output=True, text=True,
                cwd=repo_path, timeout=120,
            )
            if proc.stdout:
                try:
                    eslint_results = json.loads(proc.stdout)
                    for file_result in eslint_results:
                        for msg in file_result.get('messages', []):
                            rule = msg.get('ruleId', '')
                            if any(kw in rule for kw in ['boundaries', 'import', 'restricted']):
                                violations.append({
                                    'file': file_result.get('filePath', ''),
                                    'line': msg.get('line', 0),
                                    'rule': rule,
                                    'message': msg.get('message', ''),
                                    'severity': 'error' if msg.get('severity') == 2 else 'warning',
                                })
                except json.JSONDecodeError:
                    pass
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    # Load custom rules if provided
    custom_rules = []
    if rules_file and Path(rules_file).exists():
        try:
            custom_rules = json.loads(Path(rules_file).read_text()).get('rules', [])
        except (json.JSONDecodeError, OSError):
            pass
    
    return {
        'eslint_config_found': eslint_config is not None,
        'violations': violations,
        'custom_rules_loaded': len(custom_rules),
        'total_violations': len(violations),
    }


def cmd_analyze(args):
    result = analyze(args.repo)
    print(json.dumps(result, indent=2, default=str))


def cmd_query(args):
    result = query_graph(args.repo, args.query)
    print(json.dumps(result, indent=2, default=str))


def cmd_check(args):
    available = is_available()
    print(f"GITNEXUS_AVAILABLE={'true' if available else 'false'}")
    if available:
        print("GitNexus is installed and ready.")
    else:
        print("GitNexus not found. Council will use grep-based fallback analysis.")
        print("Install: npm install -g gitnexus")


def cmd_violations(args):
    result = check_violations(args.repo, args.rules)
    print(json.dumps(result, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description='GitNexus Bridge')
    sub = parser.add_subparsers(dest='command', required=True)
    
    p_analyze = sub.add_parser('analyze')
    p_analyze.add_argument('--repo', '-r', default='.', help='Repository path')
    
    p_query = sub.add_parser('query')
    p_query.add_argument('--repo', '-r', default='.', help='Repository path')
    p_query.add_argument('--query', '-q', required=True)
    
    p_check = sub.add_parser('check')
    
    p_viol = sub.add_parser('violations')
    p_viol.add_argument('--repo', '-r', default='.', help='Repository path')
    p_viol.add_argument('--rules', help='Custom rules JSON file')
    
    args = parser.parse_args()
    {'analyze': cmd_analyze, 'query': cmd_query,
     'check': cmd_check, 'violations': cmd_violations}[args.command](args)


if __name__ == '__main__':
    main()
