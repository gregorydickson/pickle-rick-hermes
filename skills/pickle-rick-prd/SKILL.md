---
name: pickle-rick-prd
description: "Interactive PRD drafter: interview the user about requirements, verification strategy, and interface contracts, then produce a machine-verifiable PRD."
version: 0.1.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, PRD, requirements, interview, verification]
    homepage: https://github.com/gregorydickson/pickle-rick-claude
    related_skills: [pickle-rick, pickle-rick-refine-prd]
---

# Pickle Rick PRD Drafter — Interactive Mode

Initialize a paused session, interview the user about requirements, then draft
a machine-verifiable PRD. The spec IS the review — no requirement survives
without a machine-checkable criterion.

## When to Use

- User says "draft a PRD", "pickle prd", "help me write requirements"
- User has a vague idea that needs structured interrogation
- User wants verification-first PRD (contracts, test expectations, acceptance criteria)

## Step 1: Initialize Session

```bash
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py init --task 'PRD: USER_TASK' --working-dir .")
```

Extract SESSION_DIR. Session starts paused — normal chat mode.

## Step 2: Interview

PAUSED mode — have a conversation. Interrogate systematically:

1. **Feature** — What are we building? (if not already specified)
2. **Why** — Problem, value, urgency
3. **Who** — Target audience, user types
4. **What** — Scope, UX expectations, boundaries
5. **How** — Technical constraints, dependencies, existing code
6. **Files** — Relevant files/folders/patterns in the codebase (use search_files to help)
7. **Verification** — Per requirement, ask: "How will we verify this automatically?"
   Push for: commands, type shapes, test assertions. No requirement without a machine-checkable criterion.
8. **Contracts** — "What crosses a boundary?" APIs, events, shared types, state transitions. Get exact shapes.

Iterate until 100% clarity AND verification coverage. No premature drafting.

## Step 3: Draft PRD

Write PRD to `{SESSION_DIR}/prd.md` using the enhanced template:

```markdown
# [Feature] PRD
| [Feature] PRD | | [Summary] |
|:---|:---|:---|
| **Author**: [User] | **Status**: Draft **Created**: [Date] | **Visibility**: Internal |

## Completion Checklist
- [ ] Introduction - [ ] Problem - [ ] Scope - [ ] CUJs - [ ] Requirements
- [ ] Contracts - [ ] Verification - [ ] Tests - [ ] Assumptions - [ ] Risks

## Introduction
## Problem Statement
**Current Process**: | **Users**: | **Pain Points**: | **Importance**:

## Objective & Scope
**Objective**: | **Ideal Outcome**:
### In-scope / ### Not-in-scope

## Product Requirements
### Critical User Journeys (CUJs)
### Functional Requirements
| Priority | Requirement | User Story | Verification |
|:---|:---|:---|:---|
Every requirement needs a machine-checkable Verification column.

## Interface Contracts
Exact shapes at module/service boundaries.

### API Contracts
| Endpoint/Function | Input | Output | Error | Contract Test |
|:---|:---|:---|:---|:---|

### Type Contracts
[Exact shared types/DTOs — not "TBD"]

### State Transitions
| From | Event | To | Side Effects | Invariants |
|:---|:---|:---|:---|:---|

## Verification Strategy
- **Type**: Project type checker passes
- **Lint**: Project linter passes
- **Test**: All acceptance tests pass
- **Contract**: Interface shapes match impl signatures
- **LLM**: Agent reads impl, PASS/FAIL per requirement (behavioral/UX only)

### Verification Commands
| Check | Command | Expected |
|:---|:---|:---|

## Test Expectations
### Unit Tests
| Requirement | Test File | Description | Assertion |
|:---|:---|:---|:---|
### Integration Tests
| CUJ | Test File | Scenario | Expected |
|:---|:---|:---|:---|
### Edge Cases
| Condition | Behavior | Test |
|:---|:---|:---|

## Assumptions
## Risks & Mitigations
## Business Impact
```

## Step 4: Finalize

1. Update state: `step -> breakdown`
2. Verify prd.md exists and state is correct
3. Handoff: "Run `pickle-rick` with `--resume SESSION_DIR` or start a new session pointing at this PRD."

## Rules

1. **Never draft prematurely** — interview until crystal clear
2. **Every requirement needs verification** — no subjective criteria
3. **Contracts are mandatory** — exact shapes, not prose
4. **Test expectations before implementation** — spec drives tests
5. **Use clarify tool** — ask the user questions interactively
