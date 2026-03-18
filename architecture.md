<p align="center">
  <img src="images/architecture.png" alt="Pickle Rick Architecture" width="100%" />
</p>

# Pickle Rick Architecture

Deep-dive internals for the Pickle Rick engineering lifecycle. For usage, commands, and quick start, see the [README](README.md).

---

## Circuit Breaker — Runaway Session Protection

> *"You know what's worse than a bug, Morty? An infinite loop that keeps making the same bug. Over and over. Burning tokens like Jerry burns goodwill."*

Long-running autonomous sessions can get stuck — same error repeating, no git progress, the model spinning its wheels. The circuit breaker detects these failure modes and stops the session before it wastes hours.

### How It Works

The circuit breaker is a three-state machine integrated into `mux_runner.py`. After every iteration, it checks two signals:

**Progress detection** — Runs `git diff --stat` (staged + unstaged) and `git rev-parse HEAD` against the last known state. Also tracks lifecycle transitions (step changes, ticket changes). If any of these changed, the iteration made progress. First-iteration warm-up always counts as progress (no baseline to compare).

**Error signature extraction** — Parses the iteration's NDJSON output for `result.subtype` starting with `"error"`. If found, extracts the last assistant text block and normalizes it: paths → `<PATH>`, line:column → `<N>:<N>`, timestamps → `<TS>`, UUIDs → `<UUID>`, whitespace collapsed, truncated to 200 chars. Exit codes are preserved (they're diagnostic). Two iterations hitting the same normalized signature count as the same error.

### State Transitions

```
                     progress detected
            ┌────────────────────────────────┐
            │                                │
            ▼                                │
        ┌────────┐  no progress ≥ 2  ┌───────────┐  no progress ≥ 5  ┌────────┐
        │ CLOSED │ ──────────────►  │ HALF_OPEN │ ──────────────►  │  OPEN  │
        │(normal)│                   │ (warning) │                   │ (stop) │
        └────────┘                   └───────────┘                   └────────┘
            ▲                                │                           │
            │         progress detected      │                           │
            └────────────────────────────────┘                           │
                                                                         ▼
                                                              Session terminated
                                                              reason logged
```

- **CLOSED** (normal): Every iteration with progress resets the counter.
- **HALF_OPEN** (warning): After `default_cb_half_open_after` (default: 2) consecutive no-progress iterations. Monitor shows `[CB: HALF_OPEN]`. One more progress iteration → back to CLOSED.
- **OPEN** (stop): After `default_cb_no_progress_threshold` (default: 5) consecutive no-progress iterations, OR `default_cb_same_error_threshold` (default: 5) consecutive identical error signatures. Session terminates with a diagnostic message.

### Manual Recovery

If the circuit breaker trips and you want to continue:

```bash
# Reset the circuit breaker and resume
node ~/.pickle-rick/extension/bin/circuit-reset.js <session-path>
# Then resume normally
pickle-rick-tmux --resume
```

### Monitor Display

The tmux monitor shows circuit breaker state in the header: `[CB: CLOSED]`, `[CB: HALF_OPEN (2/5)]`, or `[CB: OPEN — stopped]`. HALF_OPEN includes the no-progress count vs threshold.

### Disabling

Set `default_circuit_breaker_enabled: false` in `pickle_settings.json` to disable globally. Or pass `--no-circuit-breaker` to `pickle-rick-tmux`.

---

## Rate Limit Auto-Recovery

> *"Oh, you thought we'd just... stop? Because some API said 'too many requests'? Morty, I once escaped a galactic prison using a AAA battery and spite."*

When Hermes Agent hits an API rate limit during a tmux/Zellij session, the runner detects it, computes the optimal wait duration, pauses, and resumes automatically.

### How It Works

The mux-runner classifies every iteration's exit into one of: `completed_normally`, `completed_with_error`, `rate_limited`, `timed_out`, `unknown`. Rate limit detection uses two signals:

1. **Exit code 2** from `claude -p` (Hermes Agent's rate limit exit)
2. **Structured event**: NDJSON line with `type: "system"` and `subtype: "rate_limit_event"` containing `rate_limit_type` (e.g., `"five_hour"`, `"daily"`) and `resets_at_epoch` (Unix timestamp)

### Wait-and-Resume Cycle

```
Iteration exits with rate limit
         │
         ▼
Parse NDJSON for rate_limit_event
         │
    ┌────┴─────┐
    │ Found?   │
    └────┬─────┘
    Yes  │        No
    │    │        │
    ▼    │        ▼
Compute wait from          Use static config default
resetsAt epoch + 30s       (default_rate_limit_wait_minutes)
buffer, cap at 3×
config default
    │                      │
    └──────────┬───────────┘
               ▼
Write rate_limit_wait.json
  { waiting, wait_until, consecutive_waits,
    rate_limit_type, resets_at_epoch, wait_source }
               │
               ▼
┌─────────────────────────────────────────┐
│  Sleep loop (checks every 30s):        │
│  • Check if wait_until has passed       │
│  • Check state.json active flag         │
│  • Check session time limit             │
│  • pickle_utils.py cancel sets active=false → exit │
└──────────────┬──────────────────────────┘
               │ timer expires
               ▼
Delete rate_limit_wait.json
Write handoff.txt (resume instructions)
Continue loop → next iteration
```

**Consecutive limit**: After `default_max_rate_limit_retries` (default: 3) consecutive rate limits without a successful iteration between them, the runner exits with `rate_limit_exhausted`. A successful iteration resets the counter.

**Time-limit aware**: If the computed wait would exceed the session's `max_time_minutes`, the wait is clamped to the remaining time (or the session exits immediately if time is already up).

**Smart backoff**: When a structured `rate_limit_event` is available, the runner uses the API's `resetsAt` epoch to compute the exact wait duration (+ 30s buffer). This avoids both under-waiting (resuming before the window opens) and over-waiting (sitting idle for 60 minutes when the limit resets in 12). The API wait is capped at 3× `default_rate_limit_wait_minutes` to prevent `seven_day` limits from hanging a session for days — if the reset is too far out, the static config default is used instead.

### Monitor Display

When the runner is in a rate limit wait, the tmux monitor shows a countdown timer with minutes:seconds remaining until resume. It also displays the rate limit type (e.g., `[five_hour]`) and source indicator (`(API reset)` when using the structured reset time vs config default). The `rate_limit_wait.json` file contains `wait_until` as an ISO timestamp, plus `rate_limit_type`, `resets_at_epoch`, and `wait_source` (`"api"` or `"config"`).

### Settings

| Setting | Default | Description |
|---|---|---|
| `default_rate_limit_wait_minutes` | 60 | Fallback wait duration when no API reset time is available. Also used as the base for the 3× cap on API-derived waits |
| `default_max_rate_limit_retries` | 3 | Consecutive rate limits before giving up |

---

## Metrics Internals

`pickle_utils.py metrics` aggregates Hermes Agent usage across all your projects — token consumption, turn counts, commits, and lines of code changed — into a daily or weekly breakdown.

### What It Reports

- **Turns**: Total Claude API round-trips per day/week
- **Input / Output tokens**: Token consumption from Hermes Agent's session JSONL files (`~/.claude/projects/`)
- **Commits**: Git commit count per repo per day (via `git log`)
- **Lines +/-**: Lines added and removed across all tracked repos
- **Per-project breakdown**: Each project's contribution to the totals
- **Weekly trends**: Week-over-week output delta and top project per week

Data sources: session JSONL files in `~/.claude/projects/` for tokens, `git log --numstat` across repos under `~/loanlight/` (configurable via `METRICS_REPO_ROOT`) for LOC. Results are cached to `metrics-cache.json` to avoid re-parsing unchanged session files.

---

## Portal Gun Internals

### How It Works

1. **Open Portal** — Fetches the donor code (GitHub API, local copy, npm registry, or synthesizes from description). Saves to `portal/donor/`
2. **Pattern Extraction** — Analyzes the donor: structural pattern, invariants, edge cases, anti-patterns → `pattern_analysis.md`
3. **Target Analysis** — Studies your codebase: conventions, integration points, conflicts, adaptation requirements → `target_analysis.md`
4. **PRD Synthesis** — Generates a transplant PRD with a Behavioral Validation Tests table mapping donor behavior to expected target behavior, with donor file references for Morty workers
5. **Refinement Cycle** — Three parallel analysts (Requirements, Codebase Context, Risk & Scope) validate the transplant PRD against donor invariants and target constraints. Portal artifacts give them extra context a normal refinement wouldn't have
6. **Pattern Library** — Saves extracted patterns to `~/.pickle-rick/patterns/` for reuse in future portal-gun sessions. Use `--save-pattern <name>` to persist, or patterns stay in the session directory
7. **Handoff** — Resume with `pickle-rick --resume`, `pickle-rick-tmux --resume`, or use `--run` to auto-launch

### Flags

| Flag | Effect |
|------|--------|
| `--run` | Auto-launch tmux/Zellij session after PRD is ready |
| `--meeseeks` | Chain Meeseeks review after execution (implies `--run`) |
| `--target <path>` | Target repo (default: cwd) |
| `--depth shallow\|deep` | `shallow` = summary, structural pattern, and invariants only; `deep` = full analysis (default) |
| `--no-refine` | Skip the automatic refinement cycle |
| `--save-pattern <name>` | Persist extracted pattern to global library for future reuse |
| `--cycles <N>` | Number of refinement cycles (default: 3) |
| `--max-turns <N>` | Max turns per refinement worker (default: 100) |

---

## Project Mayhem Internals

Every module follows the same **Chaos Cycle**: read original → apply one mutation → run tests → record result → `git checkout` revert → verify revert. One mutation at a time, always reverted, always verified.

**Module 1 — Mutation Testing**: Finds high-value mutation sites in your source code (conditionals, comparisons, boolean literals, guard clauses, error handlers) and applies operators like boolean flip, comparison inversion, boundary shift, operator swap, condition negation, guard removal, and empty catch. If tests still pass after a mutation (a "survivor"), that's a test coverage gap. Survivors are severity-rated: Critical (auth/security/validation), High (business logic), Medium (utilities), Low (display/logging).

**Module 2 — Dependency Armageddon**: Selects 5-10 key direct dependencies — prioritizing the most imported, foundational, and security-sensitive — and downgrades each to the previous major version one at a time. Tracks install failures, test breakages (with error messages), and backward-compatible deps. Also runs a phantom dependency check to find imports that work by accident via transitive dependencies.

**Module 3 — Config Resilience**: Discovers runtime config files (JSON, YAML, .env, INI — excluding build tooling), then applies corruption strategies: truncation (50%), empty file, missing keys, wrong types, prototype pollution payloads (`__proto__`), and invalid syntax. Tests whether the app handles each corruption gracefully or crashes.

### The Report

After all modules run, a `project_mayhem_report.md` is written to the project root with:

- **Chaos Score** (0–100): weighted average — Mutation 50%, Deps 25%, Config 25%
- **Mutation survivors table**: file:line, operator, original → mutated, severity
- **Dependency breakages**: package, version tested, error summary
- **Phantom dependencies**: imports not declared in the manifest
- **Config crashes**: file, corruption strategy, exit code, error
- **Prioritized recommendations**: what to fix first based on severity

### Safety Guarantees

- Requires clean git state — refuses to run with uncommitted changes
- Records `HEAD` SHA before starting, verifies it hasn't changed at the end
- Every individual mutation is reverted immediately via `git checkout -- <file>`
- Dependency downgrades restore the original lockfile + re-install after each test
- Final verification: `git diff` must be empty, tests must pass
- On any error: `git checkout .` + restore deps before reporting

---

## Microverse Internals

The Microverse convergence loop optimizes a numeric metric through iterative, atomic changes. It runs as a dedicated runner (`microverse_runner.py`) that reuses the mux-runner's iteration infrastructure but adds metric measurement, automatic rollback, and convergence detection.

### State Machine

```
                    ┌──────────────┐
                    │ gap_analysis │  Initial state — first iteration
                    └──────┬───────┘  runs gap analysis, measures baseline
                           │
                           ▼
                    ┌──────────────┐
              ┌────►│  iterating   │◄────┐
              │     └──────┬───────┘     │
              │            │             │
              │     measure metric       │ score improved
              │            │             │ or held
              │     ┌──────┴──────┐      │
              │     │ regressed?  │──No──┘
              │     └──────┬──────┘
              │            │ Yes
              │     git reset --hard <pre-SHA>
              │     add to failed_approaches
              │     increment stall_counter
              │            │
              │     ┌──────┴──────┐
              │     │ converged?  │──No──┘
              │     └──────┬──────┘
              │            │ Yes
              │            ▼
              │     ┌──────────────┐
              │     │  converged   │  stall_counter ≥ stall_limit
              │     └──────────────┘
              │
              │     ┌──────────────┐
              └────►│   stopped    │  external cancel, time/iteration limit,
                    └──────────────┘  error, or rate limit exhaustion
```

### Metric Comparison

Three outcomes per iteration, controlled by the `tolerance` parameter:

| Outcome | Condition | Effect |
|---------|-----------|--------|
| **Improved** | `score > previous + tolerance` | Accept commit, reset `stall_counter` to 0 |
| **Held** | `abs(score - previous) ≤ tolerance` | Accept commit, increment `stall_counter` |
| **Regressed** | `score < previous - tolerance` | `git reset --hard` to pre-iteration SHA, add to `failed_approaches`, increment `stall_counter` |

The "previous" score is always the last **accepted** entry's score (not the last entry, which may have been reverted), falling back to `baseline_score` if no accepted entries exist yet.

### microverse.json Schema

```json
{
  "status": "iterating",
  "prd_path": "/path/to/session/prd.md",
  "key_metric": {
    "description": "increase test coverage",
    "validation": "npm test 2>&1 | tail -1",
    "type": "command",
    "timeout_seconds": 60,
    "tolerance": 0
  },
  "convergence": {
    "stall_limit": 5,
    "stall_counter": 2,
    "history": [
      {
        "iteration": 1,
        "metric_value": "78.4",
        "score": 78.4,
        "action": "accept",
        "description": "improved: 78.4 vs 72.0",
        "pre_iteration_sha": "abc1234",
        "timestamp": "2026-03-10T05:00:00Z"
      }
    ]
  },
  "gap_analysis_path": "/path/to/session/gap_analysis.md",
  "failed_approaches": [
    "Iteration 3: score dropped from 78.4 to 71.2"
  ],
  "baseline_score": 72.0,
  "exit_reason": null
}
```

### Runner Architecture

The `microverse_runner.py` reuses core infrastructure from `mux_runner.py`:

- **`runIteration()`** — spawns a fresh `claude -p` subprocess per iteration with the `microverse.md` command template
- **`classifyIterationExit()`** — detects rate limits vs normal exits
- **`computeRateLimitAction()`** — computes wait-and-resume for API throttling
- **`measureMetric()`** — executes the validation command in a child shell, parses the last stdout line as a float, with configurable timeout
- **`buildMicroverseHandoff()`** — constructs the per-iteration context injection: metric description, baseline, recent history (last 5), failed approaches, gap analysis path

Each iteration's worker gets a fresh context with only the handoff summary — no conversational drift. The worker template (`microverse.md`) is a focused optimizer: read context → plan one change → implement → commit → exit. The runner handles all measurement, comparison, and rollback externally.

**Default mode is tmux** — `pickle-rick-microverse` launches in tmux with context clearing between iterations. Pass `--interactive` to run the convergence loop inline (useful for short runs or environments without tmux).

### Final Report

On exit, the runner writes `microverse_report_<date>.md` to the session's `memory/` directory:

- Exit reason (converged, limit_reached, stopped, error, rate_limit_exhausted)
- Total iterations, elapsed time
- Baseline score vs best score
- Accepted vs reverted count
- Full iteration history table (iteration, score, action, description)

### Session Artifacts

```
~/.pickle-rick/sessions/<date-hash>/
├── microverse.json           # Microverse state (source of truth)
├── gap_analysis.md           # Initial codebase analysis
├── prd.md                    # Optimization PRD
├── handoff.txt               # Per-iteration context (overwritten each iteration)
├── microverse-runner.log     # Runner log
├── tmux_iteration_N.log      # Per-iteration NDJSON output
├── state.json                # Standard session state
└── memory/
    └── microverse_report_*.md  # Final report
```

---

## GitNexus Integration

Pickle Rick integrates with [GitNexus](https://gitnexus.dev), an MCP-powered code knowledge graph that indexes your codebase into symbols, relationships, and execution flows. Once indexed, every Morty worker automatically inherits GitNexus awareness — no manual setup per ticket.

- **Explore architecture** — trace execution flows, understand how modules connect, answer "how does X work?"
- **Impact analysis** — before changing shared code, see the blast radius: direct callers, affected processes, risk level
- **Safe refactoring** — multi-file coordinated renames using graph + text search, tagged by confidence
- **Bug tracing** — follow call chains from symptom to root cause across file boundaries
- **Change detection** — map uncommitted diffs to affected execution flows before you commit

### Setup

```bash
# Index the current repo (run from project root)
npx gitnexus analyze

# Verify the index
npx gitnexus status
```

GitNexus runs as an MCP server. Once indexed, Pickle Rick's slash commands (`/gitnexus-exploring`, `/gitnexus-impact-analysis`, `/gitnexus-debugging`, `/gitnexus-refactoring`) expose guided workflows for each capability. Workers spawned via `pickle-rick` or `pickle-rick-tmux` get GitNexus tool access injected automatically.

---

## Directory Structure

```
pickle-rick-hermes/
├── .claude/
│   ├── commands/           # Slash commands (the magic words)
│   │   ├── pickle.md           # Main loop command (PRD + Breakdown inlined)
│   │   ├── pickle-tmux.md      # True context clearing via tmux
│   │   ├── pickle-zellij.md    # True context clearing via Zellij
│   │   ├── meeseeks-zellij.md  # Zellij mode for Mr. Meeseeks
│   │   ├── pickle-prd.md       # Interactive PRD drafter (used internally by pickle-rick)
│   │   ├── pickle-refine-prd.md # Refine PRD + decompose into executable tasks
│   │   ├── pickle-dot.md         # PRD → attractor DOT digraph converter
│   │   ├── portal-gun.md         # Gene transfusion — pattern transplant PRD generator
│   │   ├── meeseeks.md            # Autonomous code review loop (setup + per-pass template)
│   │   ├── project-mayhem.md      # Chaos engineering — mutation, deps, config corruption
│   │   ├── send-to-morty.md    # Worker prompt (internal — 6 phases + scope boundary)
│   │   ├── send-to-morty-review.md # Review worker prompt (3-phase: scope → review → simplify)
│   │   ├── pickle-status.md    # Show session status
│   │   ├── pickle-retry.md     # Retry a failed ticket
│   │   ├── eat-pickle.md       # Loop canceller
│   │   ├── help-pickle.md      # Help text
│   │   ├── add-to-pickle-jar.md # Save session to Jar queue
│   │   ├── pickle-jar-open.md  # Run all Jar tasks (Night Shift)
│   │   ├── disable-pickle.md   # Disable stop hook globally
│   │   └── enable-pickle.md    # Re-enable stop hook
│   └── settings.json       # Stop hook registration (created by install.sh in ~/.claude/)
├── extension/
│   ├── src/                 # Python sources (canonical — never edit .js directly)
│   │   ├── bin/             # → compiles to extension/bin/
│   │   ├── hooks/           # → compiles to extension/hooks/
│   │   ├── services/        # → compiles to extension/services/
│   │   └── types/           # → compiles to extension/types/
│   ├── bin/                 # Compiled JS (build artifacts)
│   │   ├── setup.js         # Session initializer
│   │   ├── cancel.js        # Loop canceller
│   │   ├── delegate_task   # Worker subprocess spawner
│   │   ├── spawn-refinement-team.js # Parallel PRD analyst spawner
│   │   ├── jar-runner.js    # Jar Night Shift runner
│   │   ├── mux_runner.py    # Outer loop for pickle-rick-tmux and pickle-rick-tmux mode
│   │   ├── monitor.js       # Live tmux dashboard (window 1)
│   │   ├── log-watcher.js   # Live tmux log stream (window 1, top-right pane)
│   │   ├── morty-watcher.js # Live worker log stream (window 1, bottom pane)
│   │   ├── worker-setup.js  # Worker session initializer
│   │   ├── get-session.js   # Session path resolver
│   │   ├── update-state.js  # State mutation helper
│   │   ├── status.js        # Session status display
│   │   ├── retry-ticket.js  # Reset + re-spawn a failed ticket
│   │   ├── log-activity.js  # CLI: log activity events (used by personas)
│   │   ├── log-commit.js    # PostToolUse hook: detects git commits → activity log
│   │   ├── standup.js       # CLI: formatted standup from activity JSONL
│   │   ├── prune-activity.js # Prune old activity JSONL files (called by setup.js)
│   │   ├── circuit-reset.js  # Manual circuit breaker reset CLI
│   │   ├── metrics.js        # Token/LOC metrics reporter (daily/weekly)
│   │   └── microverse-runner.js # Microverse convergence loop runner
│   ├── layouts/
│   │   ├── monitor-pickle.kdl   # Zellij layout for pickle-rick-tmux
│   │   └── monitor-meeseeks.kdl # Zellij layout for pickle-rick-meeseeks-zellij
│   ├── hooks/
│   │   ├── dispatch.js      # Hook router
│   │   ├── resolve-state.js # State file resolution + atomic writes
│   │   └── handlers/
│   │       └── mux_runner.py (external loop) # The loop engine
│   ├── services/
│   │   ├── pickle-utils.js  # Shared utilities
│   │   ├── git-utils.js     # Git helpers
│   │   ├── pr-factory.js    # PR creation
│   │   ├── jar-utils.js     # Jar queue helper
│   │   ├── activity-logger.js # JSONL activity log writer (date-keyed, 0o600)
│   │   ├── circuit_breaker.py # Three-state circuit breaker (CLOSED/HALF_OPEN/OPEN)
│   │   ├── metrics-utils.js   # Metrics aggregation engine (session scanner + git log parser)
│   │   └── microverse-state.js # Microverse state management (convergence detection, metric comparison)
│   ├── types/
│   │   └── index.js         # Promise tokens, State type, HookInput type
│   ├── tests/               # Test suite (node --test)
│   ├── package.json         # "type": "module" — CRITICAL
│   └── tsconfig.json        # Python config (strict, ESNext)
├── images/
│   ├── tmux-monitor.png     # tmux monitor screenshot
│   ├── portal-gun.png       # Portal Gun — gene transfusion
│   ├── microverse.png       # Microverse hero image
│   └── Meeseeks.webp        # Mr. Meeseeks (from Wikipedia — Meeseeks and Destroy)
├── persona.md               # Pickle Rick persona snippet (append to your project's AGENTS.md)
├── pickle_settings.json     # Default limits
├── install.sh               # Installer
└── uninstall.sh             # Uninstaller
```

---

## Memory & State

Rick remembers. Not just within a session — across sessions, across conversations, across dimensions. Three memory systems work together so Rick always knows where he's been, what he's doing, and what went wrong last time.

### Auto-Memory (Cross-Session Persistence)

Hermes Agent's built-in [auto-memory](https://docs.anthropic.com/en/docs/claude-code) system gives Rick persistent knowledge across conversations. The memory directory lives at:

```
~/.claude/projects/<project-hash>/memory/
├── MEMORY.md          # Always loaded into context (first 200 lines)
└── tmux_research.md   # Topic-specific deep dives (linked from MEMORY.md)
```

**MEMORY.md** is automatically injected into every conversation. It contains:
- Project location, build commands, architecture notes
- Key API surfaces and type definitions
- Test file inventory and current test count
- Important patterns and gotchas (macOS symlinks, hook decisions, pipe flushing)
- **Session History Summaries** — a running log of what was accomplished in each session (bugs fixed, features added, test count growth)

Topic files store detailed research that would blow past the 200-line cap. Rick creates these during deep dives and links them from MEMORY.md.

Memory updates happen automatically when stable patterns are confirmed across sessions. One-off findings stay out until verified.

### Session State (`state.json`)

Every Pickle Rick session creates a directory under `~/.pickle-rick/sessions/<date-hash>/` with a `state.json` that tracks the live execution state:

```json
{
  "active": true,
  "working_dir": "/path/to/project",
  "step": "implement",
  "iteration": 7,
  "max_iterations": 500,
  "max_time_minutes": 720,
  "worker_timeout_seconds": 1200,
  "start_time_epoch": 1772287760,
  "current_ticket": "feat-03",
  "tmux_mode": true,
  "chain_meeseeks": false,
  "history": []
}
```

The stop hook reads `state.json` on every turn to decide whether to block or approve exit. The mux-runner reads it between iterations to build the handoff summary. `pickle-rick-status` reads it to display the dashboard.

### Session Logs & Artifacts

Each session directory accumulates execution traces and work products:

```
~/.pickle-rick/sessions/2026-02-28-a1b2c3d4/
├── state.json                          # Live state (see above)
├── circuit_breaker.json                # Circuit breaker state (when enabled)
├── rate_limit_wait.json                # Rate limit countdown (transient — deleted on resume)
├── prd.md                              # The PRD for this epic
├── linear_ticket_parent.md             # Parent ticket with all sub-tickets
├── hooks.log                           # Stop hook decisions and state transitions
├── mux-runner.log                      # Orchestrator-level log (tmux/zellij mode)
├── tmux_iteration_1.log                # Per-iteration NDJSON stdout
├── tmux_iteration_1.exitcode           # Subprocess exit code for post-mortem
├── tmux_iteration_2.log
├── meeseeks-summary.md                 # Meeseeks audit trail (when review runs)
├── feat-01/
│   ├── linear_ticket_feat-01.md        # Ticket specification
│   ├── research_feat-01.md             # Research phase output
│   ├── research_review.md              # Research review
│   ├── plan_feat-01.md                 # Implementation plan
│   ├── plan_review.md                  # Plan review
│   └── worker_session_12345.log        # Morty worker stdout
├── feat-02/
│   └── ...
└── refinement/                         # PRD refinement worker logs
    ├── worker_requirements_c1.log      # Requirements analyst (cycle 1)
    ├── worker_codebase_c1.log          # Codebase analyst (cycle 1)
    └── worker_risk-scope_c1.log        # Risk/scope analyst (cycle 1)
```

**Log types:**

| Log | What it captures |
|-----|------------------|
| `hooks.log` | Every stop hook decision (approve/block), completion token matches, state transitions |
| `mux-runner.log` | Iteration lifecycle: spawn, wait, classify completion, advance or stop |
| `tmux_iteration_N.log` | Raw NDJSON from `claude -p --output-format stream-json` per iteration |
| `worker_session_<pid>.log` | Full Morty subprocess output — research, planning, implementation, test runs |
| `worker_<role>_c<N>.log` | PRD refinement analyst output per role per cycle |
| `meeseeks-summary.md` | Per-pass table of issues found/fixed, test status, commit hashes |
| `circuit_breaker.json` | Circuit breaker state: `state` (CLOSED/HALF_OPEN/OPEN), counters, `lastError`, `reason` |
| `rate_limit_wait.json` | Transient: `waiting`, `wait_until` (ISO), `consecutive_waits`, `rate_limit_type`, `resets_at_epoch`, `wait_source` (`"api"`/`"config"`). Deleted on resume. Monitor reads this for countdown + type display |

**Ticket artifacts** follow the lifecycle phases: `research_<id>.md` → `research_review.md` → `plan_<id>.md` → `plan_review.md` → implementation (code changes + commits). These persist in the session directory and can be reviewed after the run.

### Activity Log (Standup Data)

The activity logger (`pickle_state.py (log command)`) writes a date-keyed JSONL file for every notable event — ticket transitions, commits, phase changes, errors:

```
~/.pickle-rick/activity/
├── 2026-02-27.jsonl
└── 2026-02-28.jsonl
```

`pickle_utils.py standup` reads these to produce a formatted standup summary. Old files are pruned by `prune-activity.js` (called during session setup).

### Global Settings

`~/.pickle-rick/pickle_settings.json` stores all configurable defaults (max iterations, timeouts, meeseeks pass limits, refinement cycles). See [Settings](README.md#settings-pickle_settingsjson) in the README.

### How the Systems Connect

```
Auto-Memory (MEMORY.md)              Global Settings (pickle_settings.json)
   │ loaded every conversation            │ read at session setup
   │                                      │
   ▼                                      ▼
┌──────────────────────────────────────────────┐
│              Active Session                   │
│  state.json ◄──► stop-hook / mux-runner     │
│       │                                       │
│       ├── hooks.log (decision trace)          │
│       ├── tmux_iteration_N.log (raw output)   │
│       ├── ticket/worker_*.log (Morty output)  │
│       ├── ticket/research_*.md (artifacts)    │
│       └── meeseeks-summary.md (review audit)  │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
        Activity Log (JSONL)
           │
           ▼
      pickle_utils.py standup
```

When a session ends, its directory persists — you can review any past session's state, logs, and artifacts. Auto-memory captures the *lessons learned* (patterns, bugs, decisions), while session dirs capture the *raw execution trace*.

---

## The Orchestrator Loop

In the original Claude Code version, a "stop hook" traps the agent and blocks its exit, forcing it to continue iterating. Hermes Agent has no hook system, so the loop is driven externally.

**How it works:**

1. `mux_runner.py` spawns a fresh `hermes chat -q <prompt>` process per iteration
2. Each process starts with zero conversation history (context clearing)
3. The prompt includes: session state, handoff summary, persona, skill instructions
4. The hermes process does its work (PRD, breakdown, delegation, etc.) and exits
5. `mux_runner.py` reads the output, classifies it via signal tokens, updates state
6. If not done → build next prompt, spawn next iteration
7. Circuit breaker monitors git progress between iterations

```
mux_runner.py (Python, runs forever)
  │
  ├─ Read state.json
  ├─ Build prompt (handoff + persona + instructions)
  ├─ Spawn: hermes chat -q <prompt>     ← fresh context
  ├─ Wait for exit
  ├─ Classify output ([EPIC_COMPLETED], [TASK_COMPLETED], etc.)
  ├─ Record circuit breaker result
  ├─ Update state.json
  └─ Loop or stop
```

The same pattern applies to `microverse_runner.py` for convergence loops.


## Context Clearing

Every iteration spawns a **fresh `hermes chat -q` process** with no prior conversation history. This is the Hermes equivalent of Claude Code's `--no-session-persistence` flag.

**What carries over between iterations:**
- `state.json` — current step, ticket, iteration count
- `handoff.txt` — optional notes from the previous iteration
- `build_handoff()` — auto-generated summary of recent history
- Git state — committed code persists on disk

**What does NOT carry over:**
- Conversation history (completely fresh each iteration)
- Tool call results from previous iterations
- Any in-memory state from the previous hermes process

This prevents "context rot" — the accumulation of stale reasoning that causes drift on long sessions. Each iteration wakes up with a clean slate and a structured summary of where things stand.


## Manager / Worker Model

**Rick (Manager)** — The hermes instance spawned by `mux_runner.py`. Reads the PRD, breaks work into tickets, and delegates each ticket to a Morty worker. Never writes code directly.

**Morty (Worker)** — Spawned via `delegate_task()` from the manager. Receives a single ticket and executes the full lifecycle: Research → Plan → Implement → Verify → Review → Simplify. Workers run in isolated subagent contexts with their own tool access.

```
mux_runner.py
  └─ hermes -q (Manager / Rick)
       ├─ Reads state.json, picks next ticket
       ├─ delegate_task(goal="Implement ticket X", context=..., toolsets=['terminal','file','web'])
       │    └─ Subagent (Morty) — isolated context
       │         ├─ Research → research.md
       │         ├─ Plan → plan.md
       │         ├─ Implement (TDD)
       │         ├─ Verify → conformance.md
       │         ├─ Review → code_review.md
       │         └─ Simplify → commit
       ├─ Validate artifacts exist
       ├─ Mark ticket done
       └─ Signal [TASK_COMPLETED]
```

Workers can also be spawned for review (`pickle-rick-morty-review`) or refinement (`pickle-rick-refine-prd` spawns 3 parallel analysts).
