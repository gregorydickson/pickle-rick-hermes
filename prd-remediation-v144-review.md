# Pickle Rick Hermes — Post-Sync Review Remediation PRD

## Context

This PRD captures all issues found by a three-agent review of the Claude v1.44.x sync implementation. The sync work was completed and all 80 targeted tests passed, but independent reviewers uncovered critical gaps in pipeline_runner.py, medium gaps in mux_runner.py, and test quality issues.

**Baseline state:** The sync PRD implemented three features:
1. Ghost-ticket classifier in mux_runner.py (classify_ticket_completion + has_lifecycle_artifact)
2. Pipeline runner (pipeline_runner.py — NEW file)
3. SKILL.md doc fixes (removed --resume from pickle_state.py init references)

**Files that exist at baseline:**
- skills/pickle-rick/scripts/mux_runner.py (974 lines, 36209 bytes)
- skills/pickle-rick/scripts/pipeline_runner.py (338 lines, 12252 bytes — NEW)
- skills/pickle-rick/scripts/pickle_state.py (317 lines, 11639 bytes)
- skills/pickle-rick/scripts/microverse_runner.py (469 lines, 17212 bytes)
- tests/test_mux_runner.py (238 lines)
- tests/test_pipeline_runner.py (211 lines)
- tests/verify_skill_commands.py (standalone script, 2654 bytes)
- tests/conftest.py (shared fixtures)

**State schema (state.json fields):**
```
active, working_dir, step, mode, iteration, max_iterations, max_time_minutes,
worker_timeout_seconds, start_time_epoch, completion_promise, original_prompt,
current_ticket, history, started_at, session_dir, tmux_mode, min_iterations,
command_template, chain_meeseeks, pid, schema_version
```

**Signal tokens (DO NOT CHANGE):**
```python
SIGNAL_TOKENS = {
    'EPIC_COMPLETED': '[EPIC_COMPLETED]',
    'TASK_COMPLETED': '[TASK_COMPLETED]',
    'PRD_COMPLETE': '[PRD_COMPLETE]',
    'TICKET_SELECTED': '[TICKET_SELECTED]',
    'BLOCKED': '[BLOCKED]',
    'EXISTENCE_IS_PAIN': '[EXISTENCE_IS_PAIN]',
    'THE_CITADEL_APPROVES': '[THE_CITADEL_APPROVES]',
}
```

**Artifact prefixes (lifecycle artifacts):**
```python
ARTIFACT_PREFIXES = {
    'implementation': ['research_', 'plan_', 'conformance_', 'code_review_'],
    'review': ['review_scope.md', 'review_findings.md', 'spec_conformance.md'],
}
```

---

## Problem

The v1.44.x sync implementation has functional and quality gaps:

1. **pipeline_runner.py has dead code and incomplete state reset** — a never-called `run_phase()` function duplicates inline logic, and state fields leak between phases.
2. **Ghost-ticket classifier exception handling is too narrow** — `PermissionError` propagates, breaking the "never throws" contract.
3. **Tests have weak assertions and missing coverage** — tautological assertions, missing skip-phase tests, and no integration test for the main-loop downgrade.

---

## Goal

Fix all CRITICAL and MEDIUM issues. Fix LOW issues where the effort is trivial. Leave LOW cosmetic issues if they require structural changes.

---

## Scope

### In

| Priority | File | Issue | PRD Section |
|:---------|:-----|:------|:------------|
| CRITICAL | pipeline_runner.py | Remove dead `run_phase()` or wire into `main()` | Ticket 1 |
| CRITICAL | pipeline_runner.py | Expand `reset_state_for_phase()` to match JS: reset `active`, `current_ticket`, `start_time_epoch`, `step`, `chain_meeseeks`, `tmux_mode`, `max_iterations` | Ticket 1 |
| CRITICAL | pipeline_runner.py | Add inter-phase artifact cleanup (`TASK_NOTES.md`, `gap_analysis.md`, `handoff.txt`) | Ticket 1 |
| CRITICAL | pipeline_runner.py | Add phase-setup / skip logic (subsystem discovery, `anatomy-park.json` creation) | Ticket 1 |
| CRITICAL | pipeline_runner.py | Align failure behavior with JS (break on non-zero) or document divergence | Ticket 1 |
| MEDIUM | mux_runner.py | Broaden `classify_ticket_completion` git-diff exception catch to `OSError` | Ticket 2 |
| MEDIUM | mux_runner.py | Fix `ticket_dir: Path` type hint → `Optional[Path]` | Ticket 2 |
| MEDIUM | tests/test_pipeline_runner.py | Fix tautological assertion in `test_run_phase_pickles_with_missing_mux_runner` | Ticket 3 |
| MEDIUM | tests/test_pipeline_runner.py | Strengthen `test_sigint_writes_cancel_marker` to assert `.cancel` exists | Ticket 3 |
| MEDIUM | tests/test_pipeline_runner.py | Add `test_skipped_phase_not_failure` (PRD P1 requirement) | Ticket 3 |
| MEDIUM | tests/test_pipeline_runner.py | Add explicit sequential-phase-order test | Ticket 3 |
| LOW | pipeline_runner.py | Add `SIGHUP` handler or document omission | Ticket 4 |
| LOW | pipeline_runner.py | Add `assertCleanWorkingTree` pre-flight guard | Ticket 4 |
| LOW | pipeline_runner.py | Add `pipeline-status.json` for external monitoring | Ticket 4 |
| LOW | mux_runner.py | Simplify redundant `f.startswith(prefix) or f == prefix` | Ticket 4 |
| LOW | tests/test_mux_runner.py | Fix misleading comment in `test_git_diff_corroboration` | Ticket 4 |

### Out
- Porting `spawn-morty.ts` StateManager
- Porting `plumbus-frame-analyzer`
- Any new features not listed above

---

## Technical Constraints

- Python 3.9+ compatibility (no `X | None`, no match/case)
- Atomic writes: `tmp + os.rename` with try/except fallback
- Error handling: `except (json.JSONDecodeError, OSError) as e:`
- Subprocess: always include `timeout=` parameter
- Tests: pytest, maintain 80%+ coverage for modified modules
- No breaking changes to state schema or signal protocol

---

## Current Code (Baseline — DO NOT REPEAT WORK)

### Current mux_runner.py — classify_ticket_completion (lines 241-280)

```python
def classify_ticket_completion(iter_log_file: Path, working_dir: str,
                                ticket_dir: Path, role: str = 'implementation') -> str:
    """
    Post-hoc safety net: validates whether a ticket was actually completed
    before marking it Done. TASK_COMPLETED token is strong evidence. Otherwise
    require a ticket-scoped lifecycle artifact.
    Never throws — fails safe to 'skipped'.
    """
    try:
        log_content = iter_log_file.read_text()
        assistant_content = extract_assistant_content(log_content)
        if SIGNAL_TOKENS['TASK_COMPLETED'] in assistant_content:
            return 'completed'
    except OSError:
        pass
    if not ticket_dir or not ticket_dir.exists():
        return 'skipped'
    try:
        files = os.listdir(ticket_dir)
    except OSError:
        return 'skipped'
    if not has_lifecycle_artifact(files, role):
        return 'skipped'
    # Artifact exists — corroborate with git diff
    try:
        result = subprocess.run(
            ['git', 'diff', '--stat'],
            cwd=working_dir, capture_output=True, text=True, timeout=30
        )
        if result.stdout.strip():
            return 'completed'
        result = subprocess.run(
            ['git', 'diff', '--cached', '--stat'],
            cwd=working_dir, capture_output=True, text=True, timeout=30
        )
        if result.stdout.strip():
            return 'completed'
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return 'completed'
```

### Current mux_runner.py — has_lifecycle_artifact (lines 231-238)

```python
def has_lifecycle_artifact(files: list, role: str = 'implementation') -> bool:
    """Check if any file in the list matches role-specific artifact prefixes."""
    prefixes = ARTIFACT_PREFIXES.get(role, ARTIFACT_PREFIXES['implementation'])
    for f in files:
        for prefix in prefixes:
            if f.startswith(prefix) or f == prefix:
                return True
    return False
```

### Current pipeline_runner.py — run_phase (lines 107-140)

```python
def run_phase(phase: str, session_dir: Path, working_dir: str,
              timeout: int = PHASE_TIMEOUT_DEFAULT) -> int:
    """Run a single pipeline phase as a subprocess. Returns exit code."""
    if phase == 'pickle':
        cmd = [sys.executable, str(SCRIPTS_DIR / 'mux_runner.py'),
               '--resume', str(session_dir)]
    elif phase in ('anatomy-park', 'szechuan-sauce'):
        cmd = [sys.executable, str(SCRIPTS_DIR / 'microverse_runner.py'),
               '--resume', str(session_dir)]
    else:
        print(f"WARNING: Unknown phase '{phase}' — skipping")
        return 0

    env = {**os.environ, 'PICKLE_SESSION': str(session_dir),
           'PICKLE_PHASE': phase}

    print(f"\n{'=' * 60}")
    print(f"  Starting phase: {phase}")
    print(f"  Session: {session_dir}")
    print(f"{'=' * 60}")

    try:
        result = subprocess.run(
            cmd, cwd=working_dir, env=env,
            timeout=timeout,
        )
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"WARNING: Phase {phase} timed out after {timeout}s")
        return 1
    except FileNotFoundError:
        print(f"ERROR: Command not found for phase {phase}")
        return 1
```

### Current pipeline_runner.py — reset_state_for_phase (lines 83-100)

```python
def reset_state_for_phase(session_dir: Path, phase: str) -> None:
    """Reset iteration counter and update mode for the next phase."""
    state_path = session_dir / 'state.json'
    try:
        state = locked_read(state_path)
        state['iteration'] = 0
        if phase == 'anatomy-park':
            state['mode'] = 'microverse'
            state['command_template'] = 'anatomy-park'
        elif phase == 'szechuan-sauce':
            state['mode'] = 'microverse'
            state['command_template'] = 'szechuan-sauce'
        elif phase == 'pickle':
            state['mode'] = 'pickle'
            state['command_template'] = None
        locked_write(state_path, state)
    except (OSError, json.JSONDecodeError):
        pass
```

### Current pipeline_runner.py — main() phase execution block (lines 255-317)

```python
    for phase in phases:
        if shutdown:
            print(f"\nShutdown requested. Skipping remaining phases.")
            break

        elapsed = int(time.time()) - start_epoch
        if elapsed >= max_time_seconds:
            print(f"\nTime limit reached ({elapsed // 60}m). Stopping.")
            overall_exit_code = 1
            break

        # Reset state for this phase
        reset_state_for_phase(session_dir, phase)

        # Archive artifacts from previous phase if any
        archive_phase_artifacts(session_dir, phase)

        # Run the phase
        active_child = None
        if phase == 'pickle':
            cmd = [sys.executable, str(SCRIPTS_DIR / 'mux_runner.py'),
                   '--resume', str(session_dir)]
        elif phase in ('anatomy-park', 'szechuan-sauce'):
            cmd = [sys.executable, str(SCRIPTS_DIR / 'microverse_runner.py'),
                   '--resume', str(session_dir)]
        else:
            continue

        env = {**os.environ, 'PICKLE_SESSION': str(session_dir),
               'PICKLE_PHASE': phase}

        print(f"\n--- Phase: {phase} ---")
        try:
            active_child = subprocess.Popen(
                cmd, cwd=working_dir, env=env,
            )
            exit_code = active_child.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print(f"WARNING: Phase {phase} timed out after {args.timeout}s")
            if active_child and active_child.poll() is None:
                active_child.terminate()
                try:
                    active_child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    active_child.kill()
            exit_code = 1
        except FileNotFoundError:
            print(f"ERROR: Command not found for phase {phase}")
            exit_code = 1
        finally:
            active_child = None

        # Skipped phases (no valid work / zero exit) don't count as failures
        if exit_code != 0:
            print(f"Phase {phase} exited with code {exit_code}")
            overall_exit_code = exit_code
            # Continue to next phase unless it's a hard failure
            # (pipeline philosophy: partial success is acceptable)

        print(f"Phase {phase} complete (exit code: {exit_code})")
```

### Current tests/test_pipeline_runner.py — imports (lines 16-21)

```python
from pipeline_runner import (
    parse_pipeline_config,
    archive_phase_artifacts,
    reset_state_for_phase,
    run_phase,
)
```

### Current tests/test_pipeline_runner.py — TestRunPhase (lines 120-139)

```python
class TestRunPhase:
    def test_unknown_phase_returns_zero(self, tmp_path):
        result = run_phase('unknown', tmp_path, str(tmp_path))
        assert result == 0

    def test_run_phase_pickles_with_missing_mux_runner(self, tmp_path):
        session_dir = tmp_path / 'session'
        session_dir.mkdir()
        (session_dir / 'state.json').write_text(json.dumps({
            'working_dir': str(tmp_path),
            'iteration': 0,
            'max_iterations': 1,
            'max_time_minutes': 1,
            'start_time_epoch': int(time.time()),
        }))
        result = run_phase('pickle', session_dir, str(tmp_path), timeout=5)
        assert result != 0 or result == 0  # We just care it doesn't crash
```

### Current tests/test_pipeline_runner.py — TestSignalCancelMarker (lines 142-175)

```python
class TestSignalCancelMarker:
    def test_sigint_writes_cancel_marker(self, tmp_path):
        session_dir = tmp_path / 'session'
        session_dir.mkdir()
        (session_dir / 'state.json').write_text(json.dumps({
            'working_dir': str(tmp_path),
            'original_prompt': 'test',
            'iteration': 0,
            'max_iterations': 100,
            'max_time_minutes': 720,
            'start_time_epoch': int(time.time()),
        }))
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPTS / 'pipeline_runner.py'),
             '--resume', str(session_dir), '--phases', 'pickle',
             '--timeout', '300'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        time.sleep(0.5)
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        assert True  # Reaching here means no unhandled exception crashed the process
```

### Current tests/test_mux_runner.py — test_git_diff_corroboration comment (line ~183)

```python
    def test_git_diff_corroboration(self, tmp_git_repo):
        log = tmp_git_repo / 'iter.log'
        log.write_text('some output\n')
        # No artifact, but git diff exists   <-- THIS COMMENT IS WRONG
        (tmp_git_repo / 'new_file.txt').write_text('new content')
```

---

## Ticket 1: pipeline_runner.py — Dead Code, State Reset, Cleanup, Skip Logic

### 1.1 Remove Dead `run_phase()`

**Problem:** `run_phase()` (lines 107-140) is defined but never called by `main()`. `main()` duplicates the same logic inline with `subprocess.Popen`/`wait` (lines 274-305). Tests import `run_phase` but it is dead code in production.

**Decision:** Remove `run_phase()` entirely. Update test imports and tests that reference it.

**Implementation:**
- Delete lines 107-140 (the entire `run_phase` function)
- In tests/test_pipeline_runner.py, remove `run_phase` from the import list
- Remove `TestRunPhase` class entirely (both tests reference `run_phase`)
- Add `test_main_exits_nonzero_on_invalid_session` as replacement (see Ticket 3.1)

### 1.2 Expand `reset_state_for_phase()`

**Problem:** Current implementation only resets `iteration`, `mode`, and `command_template`. The JS original also resets `active`, `current_ticket`, `start_time_epoch`, `step`, `chain_meeseeks`, `tmux_mode`, and `max_iterations`.

**Required implementation (replace lines 83-100):**

```python
def reset_state_for_phase(session_dir: Path, phase: str) -> None:
    """Reset state for the next phase. Matches JS resetStateForPhase."""
    state_path = session_dir / 'state.json'
    try:
        state = locked_read(state_path)
        state['iteration'] = 0
        state['active'] = True
        state['current_ticket'] = None
        state['start_time_epoch'] = int(time.time())
        state['chain_meeseeks'] = False
        state['tmux_mode'] = True
        if phase == 'pickle':
            state['mode'] = 'pickle'
            state['command_template'] = None
            state['step'] = 'prd'
            state['max_iterations'] = state.get('max_iterations', 100)
        elif phase == 'anatomy-park':
            state['mode'] = 'microverse'
            state['command_template'] = 'anatomy-park'
            state['step'] = 'review'
            state['max_iterations'] = state.get('max_iterations', 100)
        elif phase == 'szechuan-sauce':
            state['mode'] = 'microverse'
            state['command_template'] = 'szechuan-sauce'
            state['step'] = 'review'
            state['max_iterations'] = state.get('max_iterations', 50)
        locked_write(state_path, state)
    except (OSError, json.JSONDecodeError):
        pass
```

**Test:** Add `test_reset_state_comprehensive` to `TestResetStateForPhase`:

```python
    def test_reset_state_comprehensive(self, tmp_session):
        from pickle_state import locked_read, locked_write
        state_path = tmp_session / 'state.json'
        state = locked_read(state_path)
        state['iteration'] = 42
        state['active'] = False
        state['current_ticket'] = 'abc123'
        state['chain_meeseeks'] = True
        state['mode'] = 'pickle'
        locked_write(state_path, state)

        reset_state_for_phase(tmp_session, 'anatomy-park')

        state = locked_read(state_path)
        assert state['iteration'] == 0
        assert state['active'] is True
        assert state['current_ticket'] is None
        assert state['chain_meeseeks'] is False
        assert state['mode'] == 'microverse'
        assert state['command_template'] == 'anatomy-park'
        assert state['step'] == 'review'
```

### 1.3 Add Inter-Phase Artifact Cleanup

**Problem:** Stale context files (`TASK_NOTES.md`, `gap_analysis.md`, `handoff.txt`, etc.) from one phase can pollute the next phase.

**New function (insert after `archive_phase_artifacts`, before `reset_state_for_phase`):**

```python
def clean_phase_artifacts(session_dir: Path) -> None:
    """Remove stale context files that could pollute the next phase."""
    stale = ['TASK_NOTES.md', 'gap_analysis.md', 'handoff.txt',
             'council-directive.md', 'council-summary.md',
             'meeseeks-summary.md']
    for name in stale:
        try:
            (session_dir / name).unlink(missing_ok=True)
        except OSError:
            pass
```

**Call site:** In `main()`, between `archive_phase_artifacts()` and `reset_state_for_phase()`:

```python
        # Archive artifacts from previous phase
        archive_phase_artifacts(session_dir, phase)

        # Clean stale context files
        clean_phase_artifacts(session_dir)

        # Reset state for this phase
        reset_state_for_phase(session_dir, phase)
```

**Test:** Add `test_clean_phase_artifacts_removes_stale_files`:

```python
class TestCleanPhaseArtifacts:
    def test_removes_stale_files(self, tmp_path):
        session_dir = tmp_path / 'session'
        session_dir.mkdir()
        (session_dir / 'handoff.txt').write_text('stale')
        (session_dir / 'gap_analysis.md').write_text('stale')
        (session_dir / 'council-summary.md').write_text('stale')
        (session_dir / 'state.json').write_text('{}')  # not stale

        clean_phase_artifacts(session_dir)

        assert not (session_dir / 'handoff.txt').exists()
        assert not (session_dir / 'gap_analysis.md').exists()
        assert not (session_dir / 'council-summary.md').exists()
        assert (session_dir / 'state.json').exists()
```

### 1.4 Add Phase-Setup / Skip Logic

**Problem:** No mechanism to skip anatomy-park when there are no subsystems, or szechuan-sauce when there are no source files.

**New helper `discover_subsystems()` (insert before `main()`):**

```python
def discover_subsystems(working_dir: str) -> List[str]:
    """
    Scan immediate subdirectories for subsystems.
    A subsystem is a direct child directory with 3+ source files.
    Exclude: node_modules, dist, build, .next, coverage, __pycache__, .git.
    """
    wd = Path(working_dir)
    exclude = {'node_modules', 'dist', 'build', '.next', 'coverage',
               '__pycache__', '.git', 'venv', '.venv'}
    source_exts = {'.ts', '.js', '.py', '.go', '.rs', '.java',
                   '.tsx', '.jsx'}
    subsystems = []
    for child in wd.iterdir():
        if not child.is_dir() or child.name in exclude:
            continue
        source_count = sum(
            1 for f in child.rglob('*')
            if f.is_file() and f.suffix in source_exts
        )
        if source_count >= 3:
            subsystems.append(str(child.relative_to(wd)))
    return subsystems
```

**New helper `has_source_files()` (insert before `main()`):**

```python
def has_source_files(working_dir: str) -> bool:
    """Check if working_dir contains any source files."""
    wd = Path(working_dir)
    source_exts = {'.ts', '.js', '.py', '.go', '.rs', '.java',
                   '.tsx', '.jsx'}
    for f in wd.rglob('*'):
        if f.is_file() and f.suffix in source_exts:
            return True
    return False
```

**New function `setup_phase_config()` (insert before `main()`):**

```python
def setup_phase_config(session_dir: Path, phase: str, working_dir: str) -> bool:
    """
    Set up phase-specific config. Return True if phase should proceed,
    False if it should be skipped.
    """
    if phase == 'anatomy-park':
        subsystems = discover_subsystems(working_dir)
        if not subsystems:
            print(f"  Skipping anatomy-park: no subsystems found")
            return False
        anatomy_state = {
            'subsystems': subsystems,
            'current_index': 0,
            'pass_counts': {},
            'consecutive_clean': {},
            'stall_counts': {},
            'stall_limit': 3,
            'findings_history': {},
            'trap_doors_added': [],
            'trap_doors_committed': [],
        }
        try:
            (session_dir / 'anatomy-park.json').write_text(
                json.dumps(anatomy_state, indent=2)
            )
        except OSError:
            pass
    elif phase == 'szechuan-sauce':
        if not has_source_files(working_dir):
            print(f"  Skipping szechuan-sauce: no source files found")
            return False
    return True
```

**Call site:** In `main()`, after state reset, before running the phase:

```python
        # Reset state for this phase
        reset_state_for_phase(session_dir, phase)

        # Setup phase config and skip if no work
        if not setup_phase_config(session_dir, phase, working_dir):
            print(f"  Phase {phase} skipped")
            continue
```

**Tests:**

```python
class TestDiscoverSubsystems:
    def test_finds_valid_dirs(self, tmp_path):
        (tmp_path / 'src').mkdir()
        (tmp_path / 'src' / 'a.py').write_text('x')
        (tmp_path / 'src' / 'b.py').write_text('x')
        (tmp_path / 'src' / 'c.py').write_text('x')
        result = discover_subsystems(str(tmp_path))
        assert 'src' in result

    def test_excludes_node_modules(self, tmp_path):
        (tmp_path / 'node_modules').mkdir()
        (tmp_path / 'node_modules' / 'a.js').write_text('x')
        result = discover_subsystems(str(tmp_path))
        assert 'node_modules' not in result

    def test_skips_empty_dirs(self, tmp_path):
        (tmp_path / 'empty').mkdir()
        result = discover_subsystems(str(tmp_path))
        assert result == []

class TestSetupPhaseConfig:
    def test_skips_empty_anatomy(self, tmp_path):
        session_dir = tmp_path / 'session'
        session_dir.mkdir()
        wd = tmp_path / 'wd'
        wd.mkdir()
        result = setup_phase_config(session_dir, 'anatomy-park', str(wd))
        assert result is False

    def test_proceeds_with_subsystems(self, tmp_path):
        session_dir = tmp_path / 'session'
        session_dir.mkdir()
        wd = tmp_path / 'wd'
        wd.mkdir()
        (wd / 'src').mkdir()
        for i in range(3):
            (wd / 'src' / f'{i}.py').write_text('x')
        result = setup_phase_config(session_dir, 'anatomy-park', str(wd))
        assert result is True
        assert (session_dir / 'anatomy-park.json').exists()
```

### 1.5 Align Failure Behavior with JS

**Problem:** Current code continues to next phase on non-zero exit. JS original breaks the pipeline.

**Change in main() phase execution block (replace the `if exit_code != 0:` section):**

```python
        if exit_code != 0:
            print(f"Phase {phase} failed with exit code {exit_code}. Stopping pipeline.")
            overall_exit_code = exit_code
            break  # STOP — do not continue to next phase
```

**Document in module docstring (update the top-level docstring):**

Add line: "Pipeline stops on first phase failure (matching JS behavior)."

---

## Ticket 2: mux_runner.py — Exception Handling + Type Hint

### 2.1 Broaden Exception Catch

**Problem:** `except (subprocess.TimeoutExpired, FileNotFoundError)` does not catch `PermissionError`, `NotADirectoryError`, `ProcessLookupError`, etc. This breaks the "Never throws — fails safe to 'skipped'" contract.

**Change (line 278):**

```python
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
```

**To:**

```python
    except (subprocess.TimeoutExpired, OSError):
        pass
```

**Test:** Add to `TestGhostTicketPrevention`:

```python
    def test_classify_ticket_completion_git_permission_error(self, tmp_path, monkeypatch):
        """Simulate PermissionError from subprocess.run (e.g. git not executable)."""
        import subprocess
        log = tmp_path / 'iter.log'
        log.write_text('some output\n')
        (tmp_path / 'research_notes.md').write_text('notes')
        
        def mock_run(*args, **kwargs):
            raise PermissionError(13, 'Permission denied')
        monkeypatch.setattr(subprocess, 'run', mock_run)
        
        # Should still return 'completed' because artifact exists
        assert classify_ticket_completion(log, str(tmp_path), tmp_path) == 'completed'
```

### 2.2 Fix Type Hint

**Problem:** `ticket_dir: Path` but caller passes `None` when `current_ticket` is absent.

**Change (line 241-242):**

```python
def classify_ticket_completion(iter_log_file: Path, working_dir: str,
                                ticket_dir: Path, role: str = 'implementation') -> str:
```

**To:**

```python
def classify_ticket_completion(iter_log_file: Path, working_dir: str,
                                ticket_dir: Optional[Path], role: str = 'implementation') -> str:
```

Ensure `Optional` is imported from `typing` (should already be present at line 46: `from typing import Optional, List`).

---

## Ticket 3: Test Fixes and Gaps

### 3.1 Fix Tautological Assertion

**File:** tests/test_pipeline_runner.py
**Current (lines 125-139):** `TestRunPhase` class with tautological `assert result != 0 or result == 0`

**Action:** Remove `TestRunPhase` class entirely (it tests the dead `run_phase` function). Replace with:

```python
class TestMainExitCode:
    def test_main_exits_nonzero_on_invalid_session(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pipeline_runner.py'),
             '--resume', str(tmp_path / 'nonexistent')],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0
```

### 3.2 Strengthen Signal Test

**File:** tests/test_pipeline_runner.py
**Current (lines 142-175):** `test_sigint_writes_cancel_marker` asserts `assert True`

**Replace with:**

```python
class TestSignalCancelMarker:
    def test_sigint_writes_cancel_marker(self, tmp_path):
        session_dir = tmp_path / 'session'
        session_dir.mkdir()
        (session_dir / 'state.json').write_text(json.dumps({
            'working_dir': str(tmp_path),
            'original_prompt': 'test',
            'iteration': 0,
            'max_iterations': 100,
            'max_time_minutes': 720,
            'start_time_epoch': int(time.time()),
        }))
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPTS / 'pipeline_runner.py'),
             '--resume', str(session_dir), '--phases', 'pickle',
             '--timeout', '300'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        time.sleep(0.5)
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        assert (session_dir / '.cancel').exists()
```

### 3.3 Add Skipped Phase Test

**File:** tests/test_pipeline_runner.py
**New test class:**

```python
class TestSkippedPhase:
    def test_skipped_phase_not_failure(self, tmp_path):
        """A phase with no work should return exit 0, not fail the pipeline."""
        wd = tmp_path / 'wd'
        wd.mkdir()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pipeline_runner.py'),
             '--task', 'test', '--working-dir', str(wd),
             '--phases', 'anatomy-park', '--timeout', '5'],
            capture_output=True, text=True, timeout=30,
        )
        # Should complete without hard crash; may skip or exit 0
        assert result.returncode == 0 or 'skip' in result.stdout.lower()
```

### 3.4 Add Sequential Phase Order Test

**File:** tests/test_pipeline_runner.py and pipeline_runner.py

**First, add --dry-run flag to pipeline_runner.py (add to argparse):**

```python
    parser.add_argument('--dry-run', action='store_true',
                        help='Print phase plan without executing')
```

**Add dry-run handling in main() (after arg parsing, before session init):**

```python
    if args.dry_run:
        phases = parse_pipeline_config(args.phases)
        print(f"Dry run: would execute phases in order:")
        for i, phase in enumerate(phases, 1):
            print(f"  {i}. {phase}")
        sys.exit(0)
```

**Then add test:**

```python
class TestPhaseOrder:
    def test_phase_order_dry_run(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'pipeline_runner.py'),
             '--task', 'test', '--working-dir', str(tmp_path),
             '--phases', 'pickle,anatomy-park,szechuan-sauce',
             '--dry-run'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert 'pickle' in result.stdout
        assert 'anatomy-park' in result.stdout
        assert 'szechuan-sauce' in result.stdout
        # Verify order by position
        pickle_pos = result.stdout.find('pickle')
        anatomy_pos = result.stdout.find('anatomy-park')
        szechuan_pos = result.stdout.find('szechuan-sauce')
        assert pickle_pos < anatomy_pos < szechuan_pos
```

---

## Ticket 4: LOW Priority — Nice-to-Have Fixes

### 4.1 Simplify Redundant Check

**File:** mux_runner.py, line 236
**Current:** `if f.startswith(prefix) or f == prefix:`
**Fix:** `if f.startswith(prefix):`
(Equality is redundant because `startswith` covers it for non-empty prefix strings.)

### 4.2 Fix Test Comment

**File:** tests/test_mux_runner.py, test_git_diff_corroboration
**Current comment:** `# No artifact, but git diff exists`
**Fix:** `# Artifact exists; git diff corroboration is attempted`

### 4.3 Add SIGHUP Handler

**File:** pipeline_runner.py, after line 243
**Add:**

```python
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, handle_signal)
```

### 4.4 Add Clean Working Tree Pre-Flight

**File:** pipeline_runner.py, insert before main() loop
**New function:**

```python
def warn_dirty_working_tree(working_dir: str) -> None:
    """Warn if working tree has uncommitted changes."""
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=working_dir, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            print("WARNING: Working tree is dirty. Uncommitted changes may be lost.")
    except (subprocess.TimeoutExpired, OSError):
        pass
```

**Call site:** In `main()`, after determining `working_dir`:

```python
    warn_dirty_working_tree(working_dir)
```

### 4.5 Add pipeline-status.json

**File:** pipeline_runner.py, insert before main()
**New function:**

```python
def write_pipeline_status(session_dir: Path, status: str,
                          current_phase: str = None,
                          overall_exit_code: int = 0) -> None:
    path = session_dir / 'pipeline-status.json'
    data = {
        'status': status,
        'current_phase': current_phase,
        'overall_exit_code': overall_exit_code,
        'updated_at': int(time.time()),
    }
    tmp = path.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp), str(path))
    except OSError:
        pass
```

**Call sites in main():**
- After session init/resume: `write_pipeline_status(session_dir, 'running')`
- Before each phase loop iteration: `write_pipeline_status(session_dir, 'running', phase)`
- Before final sys.exit: `write_pipeline_status(session_dir, 'complete', overall_exit_code=overall_exit_code)`

---

## Verification Strategy

1. **Compile:** `python3 -m py_compile` on all modified `.py` files
2. **Unit tests:** `python3 -m pytest tests/test_mux_runner.py tests/test_pipeline_runner.py tests/test_pickle_state.py -v`
3. **Skill commands:** `python3 tests/verify_skill_commands.py`
4. **Contract:** `classify_ticket_completion` never throws for any input
5. **Integration:** Run pipeline_runner.py --dry-run and verify output order

---

## Rollback Plan

If any fix introduces regressions, revert individual files:
```bash
git checkout -- skills/pickle-rick/scripts/pipeline_runner.py
# or
git checkout -- skills/pickle-rick/scripts/mux_runner.py
# or
git checkout -- tests/test_pipeline_runner.py
```

All changes are additive or tightening — no schema changes, no signal protocol changes.

---

## Test Expectations (Post-Fix)

| Requirement | Test File | Test Name |
|:------------|:----------|:----------|
| Reset all state fields | tests/test_pipeline_runner.py | test_reset_state_comprehensive |
| Clean stale artifacts | tests/test_pipeline_runner.py | test_clean_phase_artifacts_removes_stale_files |
| Skip empty anatomy-park | tests/test_pipeline_runner.py | test_skips_empty_anatomy |
| Discover subsystems | tests/test_pipeline_runner.py | test_finds_valid_dirs |
| Phase order preserved | tests/test_pipeline_runner.py | test_phase_order_dry_run |
| Pipeline stops on failure | tests/test_pipeline_runner.py | test_main_exits_nonzero_on_invalid_session |
| Signal writes .cancel | tests/test_pipeline_runner.py | test_sigint_writes_cancel_marker |
| Git PermissionError safe | tests/test_mux_runner.py | test_classify_ticket_completion_git_permission_error |
| Type hint correct | (py_compile) | classify_ticket_completion compiles |
