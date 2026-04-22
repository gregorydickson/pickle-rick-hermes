# Pickle Rick Hermes — Claude v1.44.x Sync PRD

## Problem

The Hermes port (v0.4.0, last synced to Claude v1.28.0) is now 16 minor versions behind Claude (v1.44.2). Three critical features from the Claude side are missing, causing real operational issues:

1. **Ghost tickets** — Workers mark tickets Done despite silent subprocess failures (auth/network/rate-limit before first token) because `mux_runner.py` lacks the role-aware artifact classifier that validates ticket completion.
2. **No pipeline orchestration** — The `/pickle-pipeline` feature (sequential pickle → anatomy-park → szechuan-sauce phases) doesn't exist in Hermes, forcing manual handoffs between modes.
3. **Broken resume in skill docs** — The tmux/zellij SKILL.md files reference `--resume` on `pickle_state.py init`, which that script doesn't support, causing user confusion.

## Goal

Port the remaining v1.44.x features into Hermes v0.5.0 so that tmux loop sessions are robust against ghost tickets, pipeline orchestration is available, and all SKILL.md instructions are executable.

---

## Scope

### In
- Port `classifyTicketCompletion` with lifecycle artifact detection to `mux_runner.py`
- Port `pipeline-runner.py` as `pipeline_runner.py` with Python 3.9+ compatibility
- Add `--resume` flag to `pickle_state.py init` (or remove the reference from docs)
- Update all affected SKILL.md files with correct commands
- Comprehensive tests for all new code

### Out
- Porting the full `spawn-morty.ts` rewrite (Claude-specific StateManager)
- Porting `plumbus-frame-analyzer` or other v1.44.x features unrelated to loop correctness
- Breaking changes to state schema or signal protocol

---

## Baseline State (DO NOT REPEAT WORK ALREADY DONE)

**Current HEAD:** `d790bb3` on `main`

**Already completed (commit `d775e18`):**
- Fixed all stale `.js` references in 3 SKILL.md files:
  - `skills/pickle-rick-tmux/SKILL.md`
  - `skills/pickle-rick-zellij/SKILL.md`
  - `skills/pickle-rick-microverse/SKILL.md`
- Added exit code tracking to `mux_runner.py` — returns `sys.exit(1)` on failure, `0` on success
- Added `--command-template` and `--tmux` flags to `pickle_state.py init`
- All 31 mux_runner tests + 24 pickle_state tests pass

**Pre-existing issues NOT introduced by this work:**
- If `hermes` binary is missing, `run_iteration()` calls `sys.exit(1)` directly, skipping session deactivation
- Unexpected exceptions inside the main loop bypass teardown logic
- 4 test failures in full suite (anatomy-park cross-reference + gitnexus timeout) — unrelated

---

## Claude Commits to Port

Clone the Claude repo for reference:
```bash
cd /tmp && git clone --depth=50 https://github.com/gregorydickson/pickle-rick-claude.git pr-claude
```

### Commit 1: `48ea2c9` — Ghost-ticket fix (CRITICAL)
```
fix(spawn-morty,mux-runner): role-aware artifact checks prevent ghost tickets
```
**Files changed:**
- `extension/bin/mux-runner.js` — `classifyTicketCompletion` function (lines ~218-260)
- `extension/bin/spawn-morty.js` — success validation (lines ~361+)
- `extension/src/types/index.ts` — `ARTIFACT_PREFIXES` + `hasLifecycleArtifact`

**Key change:** `classifyTicketCompletion` now requires:
1. `TASK_COMPLETED` token in iteration log, OR
2. Ticket-scoped lifecycle artifact in ticket directory (not unscoped git diff)
3. New params: `ticketDir`, `role` ('implementation' | 'review')

**The function to port (from Claude JS → Python):**
```javascript
// Claude v1.44.2 mux-runner.js
export function classifyTicketCompletion(iterLogFile, workingDir, ticketDir, role = 'implementation') {
    try {
        const logContent = fs.readFileSync(iterLogFile, 'utf-8');
        const assistantContent = extractAssistantContent(logContent);
        if (hasToken(assistantContent, PromiseTokens.TASK_COMPLETED))
            return 'completed';
    } catch { /* fall through */ }
    if (!ticketDir) return 'skipped';
    let files;
    try { files = fs.readdirSync(ticketDir); }
    catch { return 'skipped'; }
    if (!hasLifecycleArtifact(files, role)) return 'skipped';
    // Artifact exists — corroborate with git diff
    try {
        const uncommitted = runCmd(['git', 'diff', '--stat'], { cwd: workingDir, check: false });
        if (uncommitted.length > 0) return 'completed';
        const staged = runCmd(['git', 'diff', '--cached', '--stat'], { cwd: workingDir, check: false });
        if (staged.length > 0) return 'completed';
    } catch { /* artifact alone suffices */ }
    return 'completed';
}
```

**Lifecycle artifact prefixes (from `types/index.ts`):**
```javascript
const ARTIFACT_PREFIXES = {
    implementation: ['research_', 'plan_', 'conformance_', 'code_review_'],
    review: ['review_scope.md', 'review_findings.md', 'spec_conformance.md'],
};
```

### Commit 2: `2da7fe5` — Pipeline runner
```
feat: add /pickle-pipeline — full build→review→deslop lifecycle in one tmux session
```
**Files changed:**
- `extension/bin/pipeline-runner.js` — 511 lines (NEW)
- `extension/bin/mux-runner.js` — 4 lines (exit code)
- `.claude/commands/pickle-pipeline.md` — 116 lines (skill doc)

**Key behaviors:**
- Sequential phases: pickle (mux-runner) → anatomy-park (microverse-runner) → szechuan-sauce (microverse-runner)
- Each phase runs as child process with state reset, artifact archival, config setup
- Skipped phases don't count as failures
- Signal handler writes cancel marker, delegates cleanup to child
- `chain_meeseeks` forced off before pickle phase
- `parsePipelineConfig` exported with `Number.isFinite` guards

### Commit 3: `3081474` — Monitor preservation
```
fix: preserve tmux monitor across pipeline phases
```
**Files changed:**
- `extension/bin/monitor.js` — 80 lines
- `extension/bin/pipeline-runner.js` — 60 lines
- Keeps tmux monitor alive between phase transitions

---

## Architecture: Claude vs Hermes

| Aspect | Claude (JS) | Hermes (Py) |
|--------|-------------|-------------|
| Orchestration | `mux-runner.js` | `mux_runner.py` |
| Session init | `setup.js` | `pickle_state.py init` |
| Context clearing | `claude -p` | `hermes -q` |
| Subprocess | `spawn('claude', cmdArgs)` | `subprocess.Popen(['hermes', 'chat', '-q', ...])` |
| State manager | `StateManager` class (file locking) | `read_state`/`write_state` with tmp+rename |
| Worker delegation | Built into Claude | `hermes` subprocess per iteration |
| Ticket validation | `classifyTicketCompletion` | **NEEDS PORTING** |
| Pipeline | `pipeline-runner.js` | **NEEDS PORTING** |
| Cancel | `cancel.js` / `eat-pickle` | `pickle_utils.py cancel --session` |

**Path mapping:**
- `extension/bin/mux-runner.js` → `skills/pickle-rick/scripts/mux_runner.py`
- `extension/bin/pipeline-runner.js` → `skills/pickle-rick/scripts/pipeline_runner.py`
- `extension/bin/setup.js` → `skills/pickle-rick/scripts/pickle_state.py init`
- `extension/bin/cancel.js` → `skills/pickle-rick/scripts/pickle_utils.py cancel --session`
- `extension/bin/update-state.js` → `skills/pickle-rick/scripts/pickle_state.py update`

---

## Requirements

| Priority | Requirement | Verification |
|:---------|:------------|:-------------|
| P0 | `mux_runner.py` validates ticket completion via ticket-scoped lifecycle artifacts before marking Done | `python3 -m pytest tests/test_mux_runner.py::TestGhostTicketPrevention -v` |
| P0 | `mux_runner.py` exits non-zero on failure (ALREADY DONE in d775e18) | `python3 -m pytest tests/test_mux_runner.py -q` passes |
| P1 | `pipeline_runner.py` orchestrates pickle → anatomy-park → szechuan-sauce sequentially | `python3 -m pytest tests/test_pipeline_runner.py -v` |
| P1 | Skipped phases (no subsystems) don't count as failures | Test: `test_skipped_phase_not_failure` |
| P1 | Signal handler writes cancel marker and delegates cleanup to child | Test: `test_signal_cancel_marker` |
| P1 | `chain_meeseeks` forced off before pickle phase to prevent transition | Test: `test_chain_meeseeks_forced_off` |
| P2 | `pickle_state.py init --resume <path>` works or docs don't reference it | `python3 -m pytest tests/test_pickle_state.py::TestCLI::test_init_resume -v` |
| P2 | All SKILL.md commands are syntactically valid and reference existing scripts | `python3 tests/verify_skill_commands.py` (new) |
| P2 | Python 3.9 compatibility: no `X \| None`, no match/case, no asyncio in subprocess context | `python3.9 -m py_compile skills/pickle-rick/scripts/*.py` |

---

## Context

### Key files (Hermes repo)
- `skills/pickle-rick/scripts/mux_runner.py` — Main orchestrator (876 lines, HAS exit code fix)
- `skills/pickle-rick/scripts/pickle_state.py` — Session init (HAS `--command-template`, `--tmux`, MISSING `--resume`)
- `skills/pickle-rick/scripts/microverse_runner.py` — Convergence loop (accepts `--resume`)
- `skills/pickle-rick/scripts/pickle_utils.py` — Cancel/standup utilities
- `skills/pickle-rick/scripts/tmux-monitor.sh` — 4-pane monitor (shell, shared)
- `skills/pickle-rick/scripts/circuit_breaker.py` — 3-state CB
- `skills/pickle-rick-tmux/SKILL.md` — Tmux launcher docs (FIXED, needs verification)
- `skills/pickle-rick-zellij/SKILL.md` — Zellij launcher docs (FIXED, needs verification)
- `skills/pickle-rick-microverse/SKILL.md` — Microverse docs (FIXED, needs verification)

### Session data layout
```
~/.pickle-rick/sessions/<timestamp>_<hash>/
  state.json              # 20-field session state machine
  circuit_breaker.json    # CB state
  microverse.json         # Microverse convergence state
  prd.md                  # Product requirements
  parent_ticket.md        # Epic ticket
  tickets/<hash>/         # Per-ticket artifacts
    ticket.md
    research.md
    plan.md
    conformance.md
    code_review.md
  handoff.txt             # Context bridge between iterations
  activity.jsonl          # Event log
  iteration_N.log         # Per-iteration output
```

### Signal tokens (DO NOT CHANGE)
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

### Patterns to follow
- Atomic writes: `tmp + os.rename` with try/except fallback
- Error handling: `except (json.JSONDecodeError, OSError) as e:`
- Subprocess: always include `timeout=` parameter
- State management: `pickle_state.py` file locking via `fcntl`
- Tests: pytest, minimum 80% coverage for new modules
- Python 3.9: Use `Optional[X]` not `X | None`, use `if/elif` not match/case

---

## Technical Constraints

- Python 3.9+ compatibility (no `X | None`, no match/case)
- No StateManager class from Claude — workers update state.json directly via pickle_state.py
- `tmux-monitor.sh` is shell, stays shell, both repos share the same script
- Do NOT port `spawn-morty.ts` StateManager logic — Hermes uses direct state.json updates
- Do NOT port `collectTickets`/`markTicketDone` — Claude-specific helpers

---

## Implementation Plan

### Ticket 1: Ghost-ticket classifier (P0)

**Where to add:** `skills/pickle-rick/scripts/mux_runner.py`

**Step 1:** Add lifecycle artifact prefixes
```python
ARTIFACT_PREFIXES = {
    'implementation': ['research_', 'plan_', 'conformance_', 'code_review_'],
    'review': ['review_scope.md', 'review_findings.md', 'spec_conformance.md'],
}

def has_lifecycle_artifact(files: list, role: str = 'implementation') -> bool:
    """Check if any file in the list matches role-specific artifact prefixes."""
    prefixes = ARTIFACT_PREFIXES.get(role, ARTIFACT_PREFIXES['implementation'])
    for f in files:
        for prefix in prefixes:
            if f.startswith(prefix) or f == prefix:
                return True
    return False
```

**Step 2:** Port `classify_ticket_completion`
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

**Step 3:** Wire into main loop drift scenario
Look for the drift scenario comment in `main()` around iteration handling. After the `extract_assistant_content` check, add:
```python
# Drift scenario: model changed current_ticket without following protocol
prev_ticket_dir = session_dir / previous_ticket
prev_role = prev_ticket_info.get('type') if prev_ticket_info else 'implementation'
if prev_role == 'review':
    prev_role = 'review'
else:
    prev_role = 'implementation'
verdict = classify_ticket_completion(
    iter_log_file, ticket_working_dir, prev_ticket_dir, prev_role
)
if verdict == 'completed':
    # mark done logic...
```

**Step 4:** Add tests in `tests/test_mux_runner.py`
```python
class TestGhostTicketPrevention:
    def test_token_present_returns_completed(self, tmp_path):
        log = tmp_path / 'iter.log'
        log.write_text('some output\n[TASK_COMPLETED]\n')
        assert classify_ticket_completion(log, str(tmp_path), tmp_path) == 'completed'

    def test_no_artifact_returns_skipped(self, tmp_path):
        log = tmp_path / 'iter.log'
        log.write_text('some output\n')
        assert classify_ticket_completion(log, str(tmp_path), tmp_path) == 'skipped'

    def test_implementation_artifact_returns_completed(self, tmp_path):
        log = tmp_path / 'iter.log'
        log.write_text('some output\n')
        (tmp_path / 'research_notes.md').write_text('notes')
        assert classify_ticket_completion(log, str(tmp_path), tmp_path, 'implementation') == 'completed'

    def test_review_artifact_returns_completed(self, tmp_path):
        log = tmp_path / 'iter.log'
        log.write_text('some output\n')
        (tmp_path / 'review_scope.md').write_text('scope')
        assert classify_ticket_completion(log, str(tmp_path), tmp_path, 'review') == 'completed'
```

### Ticket 2: Pipeline runner (P1)

**New file:** `skills/pickle-rick/scripts/pipeline_runner.py`

**Key behaviors to port from `pipeline-runner.js`:**
1. Parse phase config with safe defaults
2. Run each phase as subprocess with proper env setup
3. Between phases: reset state, archive artifacts, setup config
4. Handle skipped phases (no subsystems for anatomy-park)
5. Signal handler: write `.cancel` marker, let child handle cleanup
6. Force `chain_meeseeks = False` before pickle phase

**CLI signature:**
```python
parser.add_argument('--task', '-t', required=True)
parser.add_argument('--working-dir', '-w')
parser.add_argument('--phases', default='pickle,anatomy-park,szechuan-sauce')
parser.add_argument('--max-time', type=int, default=720)
parser.add_argument('--max-iterations', type=int, default=100)
```

**Phase runner pattern:**
```python
def run_phase(phase: str, session_dir: Path, working_dir: str) -> int:
    if phase == 'pickle':
        cmd = [sys.executable, str(SCRIPTS_DIR / 'mux_runner.py'), '--resume', str(session_dir)]
    elif phase in ('anatomy-park', 'szechuan-sauce'):
        cmd = [sys.executable, str(SCRIPTS_DIR / 'microverse_runner.py'), '--resume', str(session_dir)]
    else:
        return 0  # unknown phase = skip
    result = subprocess.run(cmd, cwd=working_dir, timeout=...)
    return result.returncode
```

### Ticket 3: Resume flag consistency (P2)

**Option A:** Add `--resume` to `pickle_state.py init`
```python
p_init.add_argument('--resume', help='Resume existing session directory')
```
In `cmd_init`, if `--resume` is provided, read the existing state and return it instead of creating new.

**Option B:** Remove `--resume` references from SKILL.mds and document that resume is done at the runner level (`mux_runner.py --resume`, `microverse_runner.py --resume`).

**Recommendation:** Option B is simpler and matches current architecture. The init command creates sessions; runners resume them. Update docs accordingly.

---

## Test Expectations

| Requirement | Test File | Description | Assertion |
|:------------|:----------|:------------|:----------|
| Ghost token present | `tests/test_mux_runner.py` | `[TASK_COMPLETED]` in log → completed | `assert classify_ticket_completion(...) == 'completed'` |
| Ghost no artifact | `tests/test_mux_runner.py` | No token, no artifact → skipped | `assert classify_ticket_completion(...) == 'skipped'` |
| Ghost impl artifact | `tests/test_mux_runner.py` | `research_` file exists → completed | `assert classify_ticket_completion(...) == 'completed'` |
| Ghost review artifact | `tests/test_mux_runner.py` | `review_scope.md` exists → completed | `assert classify_ticket_completion(...) == 'completed'` |
| Pipeline order | `tests/test_pipeline_runner.py` | Phases execute sequentially | `assert phase_order == ['pickle', 'anatomy-park', 'szechuan-sauce']` |
| Pipeline skip | `tests/test_pipeline_runner.py` | No subsystems → skip, exit 0 | `assert exit_code == 0` |
| Pipeline signal | `tests/test_pipeline_runner.py` | SIGINT writes `.cancel` | `assert (session_dir / '.cancel').exists()` |
| Pipeline meeseeks lockout | `tests/test_pipeline_runner.py` | `chain_meeseeks` forced False | `assert state['chain_meeseeks'] == False` |
| Skill command validation | `tests/verify_skill_commands.py` | All SKILL.md commands reference real files | `assert all(cmd_exists(c) for c in commands)` |

---

## Pitfalls (from Claude → Hermes sync experience)

1. **Don't port StateManager** — Hermes doesn't use Claude's StateManager. Workers update state.json directly via pickle_state.py.
2. **Stream-json format** — `extract_assistant_content` in mux_runner.py already handles both stream-json and plain text. Don't break it.
3. **Settings paths differ** — Claude uses `extensionRoot/pickle_settings.json`, Hermes uses `~/.pickle-rick/pickle_settings.json`.
4. **Rate limit time formula** — Use `max_time_seconds - (int(time.time()) - start_epoch)` NOT `max_time_seconds - int(time.time()) + start_epoch`.
5. **macOS detection** — Use `platform.system() == 'Darwin'` NOT `os.uname().sysname`.
6. **`hangGuard` units** — Claude uses `setTimeout(ms)`, Python uses `threading.Timer(seconds)`.
7. **Always compile-check before pytest** — `python3 -m py_compile <file>` catches syntax errors from botched patches.
8. **Function signature drift** — After patching, verify no function definitions got merged into other functions.
9. **Duplicate imports** — Watch for `import threading` appearing both at module level and inside functions.
10. **Backward-compat aliases** — Tests may import `classify_output` as old name. Don't rename without updating tests.

---

## Verification Strategy

1. **Type**: `python3 -m py_compile` on all modified `.py` files
2. **Test**: `python3 -m pytest tests/test_mux_runner.py tests/test_pipeline_runner.py tests/test_pickle_state.py -v`
3. **Contract**: Verify `classify_ticket_completion` returns only `'completed'` or `'skipped'`
4. **Integration**: Run `bash install.sh` then verify SKILL.md commands execute without `FileNotFoundError`

---

## Rollback Plan

If pipeline_runner.py introduces regressions:
```bash
git revert <commit-with-pipeline>
# Or simply remove skills/pickle-rick/scripts/pipeline_runner.py
# mux_runner.py and pickle_state.py changes are independent and safe
```

---

## Assumptions / Risks

- **Assumption**: Claude's `pipeline-runner.js` logic maps cleanly to Python subprocess orchestration
- **Risk**: Anatomy-park and szechuan-sauce runners may need minor signature changes to work with pipeline orchestration
- **Impact**: Medium — pipeline is a convenience feature; ghost-ticket fix is critical for long-running sessions
- **Risk**: Adding `classify_ticket_completion` may slow down the loop by ~50ms per iteration (file reads). Acceptable.
