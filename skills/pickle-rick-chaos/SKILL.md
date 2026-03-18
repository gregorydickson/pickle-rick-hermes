---
name: pickle-rick-chaos
description: "Project Mayhem chaos engineering: mutation testing, dependency downgrades, config corruption. Non-destructive, language-agnostic, produces a Chaos Score report."
version: 0.2.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [chaos-engineering, mutation-testing, security, resilience, testing]
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: [pickle-rick, pickle-rick-meeseeks]
---

# Project Mayhem — Chaos Engineering

> "You want to know how tough your code is, Morty? You break it. On purpose. Scientifically."

Stress-test any project through three modules — **mutation testing**, **dependency
downgrades**, and **config corruption** — then produce a comprehensive report with
a Chaos Score (0-100). Non-destructive: every mutation is reverted immediately.

## When to Use

- User says "project mayhem", "chaos engineering", "mutation testing", "stress test"
- User wants to find test gaps, fragile dependencies, or config vulnerabilities
- After implementation, before shipping

## Prerequisites

- Clean git state (`git status --porcelain` must be empty)
- Working test suite
- Git repository

## Step 0: Parse Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--mutation-only` | all modules | Only run mutation testing |
| `--deps-only` | all modules | Only run dependency testing |
| `--config-only` | all modules | Only run config testing |
| `--max-mutations N` | 20 | Max mutation sites to test |
| `--test-cmd "..."` | auto-detect | Override test command |

## Step 1: Ecosystem Detection

Auto-detect via marker files:

| Marker | Test Command | Package Manager |
|--------|-------------|-----------------|
| `package.json` | `npm test` | npm/yarn/pnpm |
| `Cargo.toml` | `cargo test` | cargo |
| `pyproject.toml`/`setup.py` | `pytest` | pip/poetry |
| `go.mod` | `go test ./...` | go |
| `Makefile` with `test:` | `make test` | make |

Use clarify to confirm ecosystem and test command with user.

## Step 2: Safety Check

```bash
# Must be clean git state
terminal(command="git status --porcelain")  # Must be empty
terminal(command="git rev-parse HEAD")       # Record SAFETY_SHA

# Run baseline tests
terminal(command="TEST_CMD", timeout=300)    # Record baseline time + pass/fail
```

If tests fail: warn user, ask continue/abort via clarify.

## Step 3: Module 1 — Mutation Testing

### 3a: Select Targets

Use search_files to find source files. Exclude tests, configs, generated code,
node_modules, vendor, dist, build.

For each file, search for mutation sites:
- Conditionals: `if`, `else`, ternary, `switch`
- Comparisons: `===`, `!==`, `>`, `<`, `>=`, `<=`
- Booleans: `true`, `false`
- Early returns, error handling (`catch`, `except`)

Sample up to MAX_MUTATIONS sites, prioritizing diversity across files.

### 3b: Mutation Operators

| Operator | Example |
|----------|---------|
| Boolean flip | `true` → `false` |
| Comparison flip | `===` → `!==` |
| Boundary shift | `<` → `<=` |
| Operator swap | `+` → `-` |
| Negate condition | `if (x)` → `if (!x)` |
| Remove guard | `if (bad) return;` → removed |
| Empty catch | `catch (e) { handle(e) }` → `catch (e) { }` |

### 3c: Execute (per mutation)

1. **Read** original file content
2. **Patch** one mutation using the patch tool
3. **Run** test command (timeout = baseline_time × 3, min 30s, max 300s)
4. **Record**: Tests failed → KILLED (good). Tests passed → SURVIVED (test gap!)
5. **Revert**: `terminal(command="git checkout -- FILE")`
6. **Verify**: re-read file to confirm revert

Severity of survivors:
- **Critical**: auth/security/validation code
- **High**: business logic
- **Medium**: utilities
- **Low**: logging/display

### 3d: Aggregate

`KILL_RATE = killed / total × 100`. Group survivors by file and type.

## Step 4: Module 2 — Dependency Armageddon

### 4a: Identify Dependencies

Read package manifest. Select 5-10 key deps (most imported, foundational, security-sensitive). Skip devDependencies.

### 4b: Downgrade Testing (per dependency)

1. Pin previous major version in manifest
2. Install: `terminal(command="npm install")` (or equivalent)
3. Run tests
4. Record: COMPATIBLE / BROKEN / INSTALL_FAILED
5. Revert: `terminal(command="git checkout -- package.json package-lock.json && npm install")`

### 4c: Phantom Dependencies

Scan imports not listed in manifest. Use search_files to find import statements,
cross-reference against package manifest.

### 4d: Aggregate

`RESILIENCE_RATE = compatible / total × 100`. Flag tightly-coupled deps.

## Step 5: Module 3 — Config Resilience

### 5a: Discover Configs

Search for runtime config files (*.json, *.yaml, *.yml, .env, *.ini).
Exclude package.json, tsconfig, node_modules, .git.

Use clarify to confirm config list with user.

### 5b: Corruption Strategies

| Strategy | Description |
|----------|-------------|
| Truncation | Keep first 50% of file |
| Empty file | Replace with empty content |
| Missing keys | Remove 1-3 top-level keys |
| Wrong types | Swap string↔number↔bool (JSON) |
| Invalid syntax | Remove closing brace, trailing comma |

### 5c: Execute (per config × strategy)

1. Read original
2. Write corrupted version
3. Run start command or test command (10s timeout)
4. Record: SURVIVED (app didn't crash — bad) / CRASHED (good — caught it)
5. Revert file

### 5d: Aggregate

`CONFIG_RESILIENCE = survived / total × 100`. Flag fragile files.

## Step 6: Write Report

Write `project_mayhem_report.md` in working directory:

```markdown
# Project Mayhem Report
Date: [date] | Project: [name] | Ecosystem: [ecosystem]

## Chaos Score: [0-100]
Weighted: Mutation 50% + Dependencies 25% + Config 25%

## Module 1: Mutation Testing
Kill Rate: [N]%
### Survivors (Test Gaps)
| File:Line | Operator | Original → Mutated | Severity |
|-----------|----------|-------------------|----------|

## Module 2: Dependency Armageddon
Resilience Rate: [N]%
### Breakages
| Package | Current → Tested | Result | Error |
|---------|------------------|--------|-------|
### Phantom Dependencies
| Import | Used In | Not In Manifest |
|--------|---------|-----------------|

## Module 3: Config Resilience
Resilience Rate: [N]%
### Crashes (Good)
| Config | Strategy | Exit Code | Error |
|--------|----------|-----------|-------|
### Survivors (Bad — app didn't notice corruption)
| Config | Strategy | Concern |
|--------|----------|---------|

## Recommendations
[Prioritized by severity: Critical → Low]
```

## Step 7: Final Verification

```bash
terminal(command="git diff")           # Must be empty
terminal(command="git rev-parse HEAD") # Must equal SAFETY_SHA
terminal(command="TEST_CMD")           # Must pass
```

If any fail: `git checkout .`, restore deps, warn user.

## Safety Rules

1. **NEVER** commit mutated code — apply, test, revert only
2. **NEVER** proceed without clean git state
3. **ALWAYS** revert after each chaos cycle
4. **ALWAYS** verify revert succeeded before next cycle
5. **CONFIRM** ecosystem and configs with user before starting



## Pitfalls

1. **Run on a branch** — Never run mutation testing on main/master
2. **Commit clean first** — Ensure no uncommitted changes before starting chaos
3. **Review mutations** — Not all surviving mutants indicate real bugs
4. **Config chaos is destructive** — Always have a git checkpoint to revert to
5. **Dependency chaos may break lockfiles** — Re-install after reverting
