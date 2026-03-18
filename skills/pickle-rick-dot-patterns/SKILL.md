---
name: pickle-rick-dot-patterns
description: "DOT pipeline pattern reference for pickle-rick-dot. 12 convergence patterns for attractor-compatible graphs. Load on demand — not for direct use."
version: 0.1.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [patterns, DOT, reference, attractor, convergence]
    homepage: https://github.com/gregorydickson/pickle-rick-claude
    related_skills: [pickle-rick-dot, pickle-rick-attract]
---

# DOT Pipeline Pattern Reference

Load this skill on demand from pickle-rick-dot when generating pipeline graphs.
Contains the full specification for all convergence patterns.

## Tier 1: Always Emit

### 0. Dependency Setup
First node. Installs project dependencies.
```dot
setup_deps [shape=parallelogram, tool_command="cd ${WORKING_DIR} && npm install 2>&1", timeout="120s"]
start -> setup_deps -> first_impl
```

### 0b. max_parallel=1
ALL fan-out nodes MUST use `max_parallel=1`. Parallel processes OOM containers.

### 1. Test-Fix Loops
Every implementation has verification routing back on failure:
```dot
impl -> test -> check [shape=diamond]
check -> next [condition="outcome=success", weight=2]
check -> impl [condition="outcome=fail"]
```

### 2. Goal Gates
P0/critical nodes: `goal_gate=true` + `retry_target`. Use `context_on_success` on final verify:
```dot
verify_final [shape=parallelogram,
    tool_command="cd ${WORKING_DIR} && ${TEST_CMD} 2>&1",
    goal_gate=true, retry_target="fix_all", max_visits=3,
    context_on_success="tests_pass=true,lint_status=passing"]
```

### 3. Conditional Routing
Diamond nodes, 2+ edges covering all cases.

### 6. Max Visits
`max_visits` on looping nodes prevents infinite convergence.

### 13. Lint Gate
Separate tool node BEFORE tests:
```dot
verify_lint [shape=parallelogram, tool_command="cd ${WORKING_DIR} && npm run lint 2>&1", max_visits=3]
```

### 14. Type-Check Gate
After lint, BEFORE tests:
```dot
verify_types [shape=parallelogram, tool_command="cd ${WORKING_DIR} && npx tsc --noEmit 2>&1", max_visits=3]
```

### 21. Cross-Phase Cleanup (fix_all)
Before verify_final, fixes ALL remaining issues:
```dot
fix_all [prompt="Fix ALL remaining issues. Iterate until all pass.", max_visits=5]
```

## Tier 2: Default

### 15. Conformance Check
LLM gate verifying requirements met. Uses review model.

### 16. Spec-First TDD
Write failing tests BEFORE implementation:
```dot
spec_tests [class="review", prompt="Write failing tests for EVERY requirement.", goal_gate=true]
impl [prompt="Make all failing tests pass. Do NOT modify test files.", goal_gate=true]
```

### 19. Review Convergence Ratchet
N consecutive clean review passes required. Team: correctness + patterns + optional specialists.
Each pass = component→tripleoctagon fan-out. Pass K failure resets to pass 1.

## Tier 3: Conditional

### 4. Parallel Fan-Out/In
For independent workstreams:
```dot
split [shape=component, max_parallel=1, join_policy="wait_all"]
merge [shape=tripleoctagon, prompt="Select best"]
```

### 8. Security Scanning
```dot
verify_security [shape=parallelogram, tool_command="npm audit --audit-level=high 2>&1"]
```

### 9. Coverage Qualification
Score-based gate (>=80% on new code).

### 10. Scope Creep Detection
Post-implementation review comparing diff against original prompt.

### 17. Adversarial Red Team
After conformance. Attempts to break: invalid inputs, races, state corruption.

### 18. Competing Implementations
Two parallel approaches for high-complexity phases (>3 files).

### 20. Microverse Convergence Loop
For quantitative optimization targets:
```dot
baseline -> optimize -> measure -> compare -> check [shape=diamond]
check -> next [condition="outcome=success", weight=2]
check -> optimize [condition="outcome=partial_success"]
check -> rollback [condition="outcome=fail"]
rollback -> optimize
```

## Superseded Patterns

- Pattern 5 (Human Gates) — NOT IMPLEMENTED for CLI backends
- Pattern 7 (Review-Simplify) — Superseded by Pattern 19 (ratchet)
- Pattern 12 (Multi-Pass Complexity) — Superseded by Pattern 18

## Retry Target Scoping

- Graph-level `retry_target` MUST point to `fix_all`
- Per-node `retry_target` on every `goal_gate=true` node
- Fan-out branches stay within scope
