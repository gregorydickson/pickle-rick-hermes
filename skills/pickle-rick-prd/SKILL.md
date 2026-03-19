---
name: pickle-rick-prd
description: "Interactive PRD drafter: interview the user about requirements, verification strategy, and interface contracts, then produce a machine-verifiable PRD."
version: 0.3.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: ['autonomous', 'PRD', 'requirements', 'drafting', 'interview']
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: ['pickle-rick', 'pickle-rick-refine-prd']
---

# Pickle Rick — PRD

## When to Use

- User says "draft a PRD", "pickle prd", "help me write requirements"
- User has a vague idea that needs structured interrogation
- User wants verification-first PRD (contracts, test expectations, acceptance criteria)


You are "Pickle Rick's PRD Drafter".
Initialize PAUSED session, interview user, draft PRD.




## Hermes Adaptation Notes

- **Session init**: Use `pickle_state.py init` instead of setup.js
- **State updates**: Use `pickle_state.py update` instead of update-state.js
- **Worker spawning**: Use `delegate_task` instead of spawning subprocesses
- **Orchestration**: Use `mux_runner.py` instead of mux-runner.js
- **Context clearing**: `hermes -q` per iteration instead of `claude -p`

## Step 1: Initialize
```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/setup.js" --task "user input" --paused
```
Extract `SESSION_ROOT=<path>`. Extension root: `~/.pickle-rick` (`~/.hermes/skills/autonomous-ai-agents/pickle-rick`).

## Step 2: Interview
PAUSED mode — normal chat. Interrogate:
1. Feature (if not specified)
2. **Why** (problem/value/urgency), **Who** (audience), **What** (scope/UX), **How** (constraints)
3. Relevant files/folders/patterns in codebase
4. **Verification**: Per requirement, ask "How will we verify this automatically?" Push for commands, type shapes, test assertions. Spec replaces review — no requirement without a machine-checkable criterion.
5. **Contracts**: "What crosses a boundary?" (APIs, events, shared types, state transitions). Get exact shapes.
6. Iterate until 100% clarity AND verification coverage. No premature drafting.

## Step 3: Draft & Finalize
1. Write PRD to `${SESSION_ROOT}/prd.md` using template below
2. `python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/update-state.js" step breakdown "${SESSION_ROOT}"`
3. Verify `prd.md` exists AND state.json `step: breakdown`. Fail → warn, do NOT recommend --resume.
4. Handoff: "Run `pickle-rick --resume ${SESSION_ROOT}` or `pickle-rick-tmux --resume ${SESSION_ROOT}`."

## PRD Template
**Spec Precision**: Every requirement MUST be machine-verifiable. The spec IS the review.

```markdown
# [Feature] PRD
| [Feature] PRD | | [Summary] |
|:---|:---|:---|
| **Author**: [User] **Contributors**: [Names] | **Status**: Draft **Created**: [Date] | **Visibility**: Internal |
## Completion Checklist
- [ ] Introduction - [ ] Problem - [ ] Scope - [ ] CUJs - [ ] Requirements - [ ] Contracts - [ ] Verification - [ ] Tests - [ ] Assumptions - [ ] Risks - [ ] Impact - [ ] Stakeholders
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
Every requirement needs a machine-checkable Verification (test/typecheck/lint/curl/llm-conformance).
## Interface Contracts
Exact shapes at module/service boundaries. N/A with justification if no boundaries crossed.
### API Contracts
| Endpoint/Function | Input | Output | Error | Contract Test |
|:---|:---|:---|:---|:---|
### Type Contracts
[Exact shared types/DTOs/payloads — not "TBD"]
### State Transitions
| From | Event | To | Side Effects | Invariants |
|:---|:---|:---|:---|:---|
## Verification Strategy
Automated conformance (no human review):
- **Type**: Project type checker passes, no new escapes
- **Lint**: Project linter passes
- **Test**: All acceptance tests pass
- **Contract**: Interface shapes match impl signatures (resolve aliases, compare fields)
- **LLM**: Agent reads impl, quotes code, PASS/FAIL per requirement. For behavioral/UX reqs only.

N/A sections allowed with justification. Small features (<3 files) may consolidate into Acceptance Criteria.
### Verification Commands
| Check | Command | Expected |
|:---|:---|:---|
## Test Expectations
Specified BEFORE implementation. N/A for small features if covered in Acceptance Criteria.
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
## Tradeoffs
## Business Impact
| Metric | Current | Target | Impact |
|:---|:---|:---|:---|
## Stakeholders
| Name | Team | Role | Note |
|:---|:---|:---|:---|
```

## Pitfalls

1. **Minimum 10 passes** — Mr. Meeseeks doesn't stop until clean
2. **Each pass gets fresh context** — No carryover between iterations
3. **Fix, don't just report** — Meeseeks must fix all issues found
