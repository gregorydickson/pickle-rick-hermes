#!/usr/bin/env python3
"""
Pickle Jar — Batch Job Queue for Pickle Rick.

Queue tasks for sequential autonomous execution.

Usage:
    python3 pickle_jar.py add --task "Build auth system" --working-dir ~/project
    python3 pickle_jar.py add --task "Add API endpoints" --working-dir ~/project --chain-meeseeks
    python3 pickle_jar.py list
    python3 pickle_jar.py run
    python3 pickle_jar.py remove --id abc12345
"""

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

JAR_ROOT = Path.home() / '.pickle-rick' / 'jar'
MANIFEST_PATH = JAR_ROOT / 'jar_manifest.json'
SCRIPTS_DIR = Path(__file__).parent


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {'created': datetime.datetime.now().isoformat(), 'tasks': []}


def save_manifest(manifest: dict) -> None:
    JAR_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(manifest, indent=2))
    try:
        os.rename(str(tmp), str(MANIFEST_PATH))
    except OSError:
        tmp.unlink(missing_ok=True)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))


def cmd_add(args):
    manifest = load_manifest()
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    task_id = hashlib.md5(f"{ts}{args.task}".encode()).hexdigest()[:8]
    
    task_dir = JAR_ROOT / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    
    entry = {
        'id': task_id,
        'task': args.task,
        'working_dir': os.path.abspath(args.working_dir or os.getcwd()),
        'max_iterations': args.max_iterations,
        'status': 'queued',
        'added_at': datetime.datetime.now().isoformat(),
        'completed_at': None,
        'session_dir': None,
        'chain_meeseeks': args.chain_meeseeks,
    }
    
    manifest['tasks'].append(entry)
    save_manifest(manifest)
    
    print(f"Added to jar: {task_id}")
    print(f"  Task: {args.task}")
    print(f"  Dir: {entry['working_dir']}")
    print(f"  Jar size: {len(manifest['tasks'])} tasks")


def cmd_list(args):
    manifest = load_manifest()
    tasks = manifest.get('tasks', [])
    if not tasks:
        print("Pickle Jar is empty.")
        return
    
    print(f"Pickle Jar: {len(tasks)} tasks")
    print(f"{'=' * 60}")
    for i, t in enumerate(tasks, 1):
        status_icon = {'queued': '[ ]', 'running': '[>]', 'done': '[x]', 
                       'failed': '[!]', 'skipped': '[-]'}.get(t['status'], '[?]')
        print(f"  {status_icon} {i}. [{t['id']}] {t['task']}")
        print(f"       Dir: {t['working_dir']} | Max: {t['max_iterations']} iter")
        if t.get('chain_meeseeks'):
            print(f"       + Meeseeks chained")
        if t.get('session_dir'):
            print(f"       Session: {t['session_dir']}")


def cmd_remove(args):
    manifest = load_manifest()
    manifest['tasks'] = [t for t in manifest['tasks'] if t['id'] != args.id]
    save_manifest(manifest)
    print(f"Removed {args.id} from jar")


def cmd_run(args):
    manifest = load_manifest()
    queued = [t for t in manifest['tasks'] if t['status'] == 'queued']
    
    if not queued:
        print("No queued tasks in the jar.")
        return
    
    print(f"Opening the Pickle Jar: {len(queued)} tasks to process")
    print(f"{'=' * 60}")
    
    results = []
    
    for i, task in enumerate(queued, 1):
        print(f"\n--- Task {i}/{len(queued)}: {task['task']} ---")
        task['status'] = 'running'
        save_manifest(manifest)
        
        cmd = [
            sys.executable, str(SCRIPTS_DIR / 'mux_runner.py'),
            '--task', task['task'],
            '--working-dir', task['working_dir'],
            '--max-iterations', str(task['max_iterations']),
        ]
        
        try:
            result = subprocess.run(cmd, timeout=task['max_iterations'] * 120)
            
            if result.returncode == 0:
                task['status'] = 'done'
                results.append(('done', task['task']))
            else:
                task['status'] = 'failed'
                results.append(('failed', task['task']))
        except subprocess.TimeoutExpired:
            task['status'] = 'failed'
            results.append(('timeout', task['task']))
        except KeyboardInterrupt:
            task['status'] = 'queued'
            save_manifest(manifest)
            print("\nJar interrupted. Remaining tasks stay queued.")
            break
        
        task['completed_at'] = datetime.datetime.now().isoformat()
        save_manifest(manifest)
    
    print(f"\n{'=' * 60}")
    print(f"Pickle Jar Summary:")
    for status, name in results:
        icon = {'done': 'OK', 'failed': 'FAIL', 'timeout': 'TIMEOUT'}[status]
        print(f"  [{icon}] {name}")


def main():
    parser = argparse.ArgumentParser(description='Pickle Jar')
    sub = parser.add_subparsers(dest='command', required=True)
    
    p_add = sub.add_parser('add')
    p_add.add_argument('--task', '-t', required=True)
    p_add.add_argument('--working-dir', '-w')
    p_add.add_argument('--max-iterations', type=int, default=100)
    p_add.add_argument('--chain-meeseeks', action='store_true')
    
    sub.add_parser('list')
    
    p_remove = sub.add_parser('remove')
    p_remove.add_argument('--id', required=True)
    
    sub.add_parser('run')
    
    args = parser.parse_args()
    {'add': cmd_add, 'list': cmd_list, 'remove': cmd_remove, 'run': cmd_run}[args.command](args)


if __name__ == '__main__':
    main()
