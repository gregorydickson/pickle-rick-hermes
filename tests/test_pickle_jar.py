"""Tests for pickle_jar.py — batch job queue."""

import json
import os
import sys
import subprocess
import pytest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import pickle_jar
from pickle_jar import load_manifest, save_manifest


class TestManifest:
    def test_load_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pickle_jar, 'JAR_ROOT', tmp_path)
        monkeypatch.setattr(pickle_jar, 'MANIFEST_PATH', tmp_path / 'jar_manifest.json')
        m = load_manifest()
        assert 'tasks' in m
        assert len(m['tasks']) == 0

    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pickle_jar, 'JAR_ROOT', tmp_path)
        monkeypatch.setattr(pickle_jar, 'MANIFEST_PATH', tmp_path / 'jar_manifest.json')
        manifest = {'created': '2026-01-01', 'tasks': [
            {'id': 'abc', 'task': 'test', 'status': 'queued'}
        ]}
        save_manifest(manifest)
        loaded = load_manifest()
        assert len(loaded['tasks']) == 1
        assert loaded['tasks'][0]['id'] == 'abc'

    def test_save_creates_dir(self, tmp_path, monkeypatch):
        jar_dir = tmp_path / 'new_jar'
        monkeypatch.setattr(pickle_jar, 'JAR_ROOT', jar_dir)
        monkeypatch.setattr(pickle_jar, 'MANIFEST_PATH', jar_dir / 'jar_manifest.json')
        save_manifest({'created': '2026-01-01', 'tasks': []})
        assert jar_dir.exists()

    def test_corrupt_manifest_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pickle_jar, 'JAR_ROOT', tmp_path)
        mp = tmp_path / 'jar_manifest.json'
        monkeypatch.setattr(pickle_jar, 'MANIFEST_PATH', mp)
        mp.write_text('not json')
        m = load_manifest()
        assert len(m['tasks']) == 0


class TestCLI:
    def test_list(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pickle_jar.py'), 'list'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
