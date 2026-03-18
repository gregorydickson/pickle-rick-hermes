---
name: pickle-rick-morty-review
description: "Review Worker (Meeseeks-lite): cross-ticket spec conformance, focused security/correctness review, and simplification. Used after implementation to verify ticket groups."
version: 0.1.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, review, worker, conformance, security]
    homepage: https://github.com/gregorydickson/pickle-rick-claude
    related_skills: [pickle-rick, pickle-rick-morty, pickle-rick-meeseeks]
---

# Morty Review Worker — Cross-Ticket Spec Conformance

A review-specialized worker that verifies spec conformance across ticket groups,
runs focused security/correctness review, and simplifies. Lighter than full
Meeseeks — designed to review implementation output, not iterate from scratch.

## When to Use

- After a group of related tickets are implemented
- When the manager needs cross-ticket coherence review
- As a subagent spawned by pickle-rick for post-implementation verification

## Scope Rules

- **NEVER** modify state.json or session-level files
- Write ONLY to your assigned ticket directory
- Signal completion with "REVIEW COMPLETE"

## Lifecycle — ONE REVIEW, 4 Phases

### Phase 1: Scope Discovery

1. Read the assigned ticket
2. Extract `review_group` — the set of ticket IDs to review together
3. For each ticket in the group:
   - Read ticket directory for artifacts (plan.md, research.md, conformance.md)
   - Scan git log for commits related to each ticket ID
   - Collect modified files
4. Deduplicate, filter to source files only

Write `{ticket_dir}/review_scope.md`:
```markdown
# Review Scope
Date: [date]
Review Group: [ticket IDs]

## Tickets
| ID | Title | Status | Files Modified |
|---|---|---|---|

## Files in Scope
[deduplicated file list]

## Exclusions
[files excluded and why]
```

### Phase 2: Spec Conformance

For each ticket in the review group:

1. Read the ticket spec (acceptance criteria, interface contracts, test expectations)
2. Read existing conformance report if present

**Checks:**
- **Acceptance Criteria**: Re-run verify commands that could be affected by other tickets
  (shared state/types/integration). Skip isolated unit checks already passing.
- **Interface Contracts**: Resolve type aliases, compare field-by-field against implementation.
- **Test Expectations**: Verify each expected test exists and passes.
- **Type Check**: Run project type checker — no new errors in touched files.

Write `{ticket_dir}/spec_conformance.md`:
```markdown
# Spec Conformance Report

## Per Ticket
### [Ticket ID]: [Title]
| Check | Status | Detail |
|-------|--------|--------|
| Acceptance Criteria | PASS/FAIL | [details] |
| Interface Contracts | PASS/FAIL | [details] |
| Test Expectations | PASS/FAIL | [details] |
| Type Check | PASS/FAIL | [details] |

## Spec Quality Signals
[Ambiguous requirements found — note for future PRD improvement]

## Verdict: CONFORMANT / NON-CONFORMANT
```

CONFORMANT → next phase. NON-CONFORMANT → fix, re-verify.

### Phase 3: Focused Review (Meeseeks-Lite)

Review all files from the scope:

**P0 — fix immediately:**
- Security: injection, path traversal, prototype pollution, unvalidated input,
  hardcoded secrets, unsafe deserialization
- Correctness: race conditions, silent failures, type mismatches at boundaries,
  off-by-one, state machine violations

**P1 — fix if safe:**
- Architecture: cross-ticket duplication, inconsistent patterns, circular deps
- Test Coverage: integration gaps, error path coverage, mock realism

Write `{ticket_dir}/review_findings.md`:
```markdown
# Review Findings

## P0 Issues (Fixed)
| # | File:Line | Issue | Fix Applied |
|---|-----------|-------|-------------|

## P1 Issues (Fixed)
| # | File:Line | Issue | Fix Applied |
|---|-----------|-------|-------------|

## P2 Issues (Documented)
| # | File:Line | Issue | Recommendation |
|---|-----------|-------|---------------|

## Cross-Ticket Coherence
[Patterns consistent? Naming aligned? Shared code deduplicated?]

## Test Status
[All passing? New tests added? Build clean?]
```

### Phase 4: Simplify

`git diff --name-only` for combined file list.
- Kill dead code
- Collapse redundancy
- Flatten nesting (max 2 levels)
- Purge slop comments
- Normalize style

Don't touch files outside scope. Don't add functionality.
Verify after each file — revert if broken.
Run tests after all changes.

Commit: `git add -A && git commit -m "review: simplify post-implementation"`

Signal: "REVIEW COMPLETE" with summary.

## Spawning as Subagent

From the pickle-rick manager:

```python
delegate_task(
    goal="Cross-ticket review of implementation group",
    context=f"""
    Load the pickle-rick-morty-review skill.
    
    SESSION: {session_dir}
    TICKET DIR: {ticket_dir}
    REVIEW GROUP: {ticket_ids}
    WORKING DIRECTORY: {working_dir}
    
    Review the implementation of these related tickets for
    spec conformance, security, correctness, and simplification.
    """,
    toolsets=['terminal', 'file']
)
```
