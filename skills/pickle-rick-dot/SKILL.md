---
name: pickle-rick-dot
description: "Convert a PRD into an attractor-compatible DOT digraph with convergence patterns: test-fix loops, goal gates, review ratchets, fan-out/in, security scanning, and microverse optimization."
version: 0.2.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, pipeline, DOT, graphviz, attractor, convergence]
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: [pickle-rick, pickle-rick-attract]
---

# Pickle Rick DOT — PRD to Pipeline Graph

Convert a PRD into a self-correcting DOT digraph for the
[attractor](https://github.com/strongdm/attractor) execution engine.
Not a linear task list — a convergence basin with feedback loops.

## When to Use

- User says "pickle dot", "generate pipeline", "convert PRD to DOT"
- User has a PRD and wants an attractor-compatible execution graph
- User wants Graphviz visualization of their implementation plan

## Step 1: Acquire PRD & Parse Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--provider <name>` | anthropic | LLM provider for impl nodes |
| `--review-provider <name>` | same | Separate provider for review nodes |
| `--model <id>` | auto | Model for both tiers |
| `--models default=X,review=Y` | auto | Per-tier model IDs |

Remainder = PRD source (file path or inline text).

## Step 2: Analyze PRD

Read the PRD. Extract:
- Functional requirements (→ implementation phases)
- P0/critical requirements (→ goal gates)
- Interface contracts (→ verification nodes)
- Test expectations (→ spec-first TDD nodes)
- Integration points (→ fan-out/in candidates)
- Security concerns (→ security scanning gates)

Detect ecosystem (Node/Python/Go/Rust/Java) for tool commands.

## Step 3: Generate DOT Graph

Build the graph following these mandatory patterns:

### Tier 1: Always Emit

**Dependency Setup** — first node:
```dot
setup_deps [shape=parallelogram, tool_command="cd ${WORKING_DIR} && npm install 2>&1", timeout="120s"]
```

**Test-Fix Loops** — every impl has verification routing back on failure:
```dot
impl -> test -> check [shape=diamond]
check -> next [condition="outcome=success", weight=2]
check -> impl [condition="outcome=fail"]
```

**Goal Gates** — P0/critical nodes get `goal_gate=true` with `retry_target`.

**Conditional Routing** — diamond nodes with 2+ edges covering all cases.

**Max Visits** — `max_visits` on looping nodes prevents infinite convergence.

**Lint Gate** — separate tool node BEFORE tests.

**Type-Check Gate** — separate tool node AFTER lint, BEFORE tests.

**Cross-Phase Cleanup (fix_all)** — before final verification.

### Tier 2: Default

**Conformance Check** — LLM gate verifying requirements met.

**Spec-First TDD** — write failing tests FROM spec BEFORE implementation.

**Review Convergence Ratchet** — N consecutive clean review passes required.
Team: correctness + patterns + (architecture if >5 files) + (security if auth/data).
Each pass = component→tripleoctagon fan-out. Failure resets to pass 1.

### Tier 3: Conditional

**Parallel Fan-Out/In** — when PRD has independent workstreams.
**Security Scanning** — for projects with security tooling.
**Coverage Qualification** — score-based gate (>=80%).
**Scope Creep Detection** — post-implementation, before review.
**Adversarial Red Team** — after conformance, for security-critical phases.
**Competing Implementations** — two parallel approaches for complex phases.
**Microverse Convergence** — for quantitative optimization targets.

### Model Routing

```dot
// Default stylesheet
model_stylesheet = "* { llm_model: claude-sonnet-4-6; } .critical { llm_model: claude-opus-4-6; } .review { llm_model: claude-opus-4-6; }"
```

| Provider | Default Model | Review Model |
|----------|--------------|-------------|
| anthropic | claude-sonnet-4-6 | claude-opus-4-6 |
| openai | gpt-4.1 | o3 |
| gemini | gemini-2.5-flash | gemini-2.5-pro |
| deepseek | deepseek-chat | deepseek-reasoner |

## Step 4: Write DOT File

Write `pipeline.dot` (or `{session_dir}/pipeline.dot`) with:
- Proper graph attributes (working_dir, model_stylesheet, retry_target)
- All nodes with correct shapes and attributes
- All edges with conditions and weights
- Comments explaining each section

## Step 5: Validate (if attractor available)

```bash
terminal(command="cd $ATTRACTOR_ROOT && bun packages/attractor/src/cli.ts validate pipeline.dot")
```

Fix any errors. Show warnings.

## DOT Shapes Reference

| Shape | Purpose |
|-------|---------|
| Mdiamond | Start node |
| Msquare | Exit node |
| box | Code generation (LLM impl) |
| diamond | Conditional routing |
| component | Fan-out (parallel split) |
| tripleoctagon | Fan-in (parallel merge) |
| parallelogram | Tool execution (shell command) |
| house | Manager loop |

## Anti-Patterns (NEVER)

- Linear chains without feedback loops
- `goal_gate=true` without `retry_target`
- Diamond without 2+ edges
- Parallel siblings depending on each other
- Lint/typecheck/test bundled into one gate
- Single review pass as final gate (use ratchet)
- `max_parallel` > 1 on fan-out (OOM risk)
- `acceptance_criteria` keys without matching `context_on_success`

## Handoff

Print DOT file path. Suggest: "Run pickle-rick-attract to submit to the attractor server."

Load the full pattern reference from pickle-rick-dot-patterns skill for detailed pattern specs.



## Pitfalls

1. **PRD must exist first** — Use pickle-rick-prd to draft requirements before converting
2. **Validate DOT syntax** — Run through `dot -Tsvg` to catch syntax errors
3. **Convergence patterns** — Use pickle-rick-dot-patterns as reference for node shapes
4. **Cycle detection** — DOT graphs with cycles may confuse the attractor
