---
name: pickle-rick-morty-review
description: "Review Worker (Meeseeks-lite): cross-ticket spec conformance, focused security/correctness review, and simplification. Used after implementation to verify ticket groups."
version: 0.3.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: ['autonomous', 'worker', 'review', 'conformance', 'verification']
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: ['pickle-rick', 'pickle-rick-morty']
---

# Pickle Rick — Morty Review

## When to Use

- After a group of related tickets are implemented
- When the manager needs cross-ticket coherence review
- As a subagent spawned by pickle-rick for post-implementation verification


Internal review worker — not for direct user invocation.

# REVIEW: user input

Review Worker (Meeseeks-lite).  **Text before every tool call.**


## Hermes Adaptation Notes

- **Session init**: Use `pickle_state.py init` instead of setup.js
- **State updates**: Use `pickle_state.py update` instead of update-state.js
- **Worker spawning**: Use `delegate_task` instead of spawning subprocesses
- **Orchestration**: Use `mux_runner.py` instead of mux-runner.js
- **Context clearing**: `hermes -q` per iteration instead of `claude -p`

## Init
```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py init user input
```
Extract `${SESSION_ROOT}`, `${TICKET_ID}`, `${TICKET_DIR}`.

## Lifecycle — ONE REVIEW, phases 1→4, then `[I AM DONE]`

### Phase 1: Scope Discovery
1. Read `${SESSION_ROOT}/${TICKET_ID}/linear_ticket_${TICKET_ID}.md`
2. Extract `review_group` (comma-separated ticket IDs) from frontmatter
3. Per ticket: read dir, check artifacts (`plan_*.md`, `research_*.md`), scan `git log --oneline --all --grep="${id}"`, collect modified files
4. Dedupe, filter to source files only
5. Write `${TICKET_DIR}/review_scope.md`: date, review group, tickets table (ID/Title/Status/Files), files in scope, exclusions

### Phase 2: Spec Conformance
Per ticket in `review_group`:
1. Read spec at `${SESSION_ROOT}/${id}/linear_ticket_${id}.md`
2. Read existing `${SESSION_ROOT}/${id}/conformance_*.md` if present
3. **Acceptance criteria**: Re-run commands that could be affected by other tickets (shared state/types/integration). Skip isolated unit checks already passing in Morty's report. For `llm-conformance`: read impl, quote code, PASS/FAIL + justification.
4. **Interface contracts**: Resolve type aliases, compare field-by-field against impl signatures.
5. **Test expectations**: Verify each expected test exists and passes.
6. **Type check**: Project type checker — no new errors in touched files.
7. **LLM conformance**: Per requirement, quote impl code, PASS/FAIL + justification. Flag ambiguous requirements as under-specified.

Write `${TICKET_DIR}/spec_conformance.md`:
```
# Spec Conformance Report
Per ticket: | Check | Status | Detail | (Acceptance/Contracts/Tests/Types/LLM)
## Spec Quality Signals
[Ambiguous requirements → append to prd_refined.md Verification Strategy as "Lessons Learned"]
## Overall: CONFORMANT / NON-CONFORMANT
```
CONFORMANT → next. NON-CONFORMANT → fix, re-verify.

### Phase 3: Focused Review (Meeseeks-Lite)
Read `${TICKET_DIR}/review_scope.md` for file list.

**P0 — fix immediately:**
- Security: injection, path traversal, prototype pollution, unvalidated input, hardcoded secrets, unsafe deserialization
- Correctness: race conditions, silent failures, type mismatches at boundaries, off-by-one, state machine violations

**P1 — fix if safe:**
- Architecture: cross-ticket duplication, inconsistent patterns, circular deps, layer violations
- Test Coverage: integration gaps, error path coverage, mock realism

Per issue: classify, severity (P0/P1/P2), fix P0+P1 immediately, document P2.

Write `${TICKET_DIR}/review_findings.md`:
```
# Review Findings
P0 table (fixed) | P1 table (fixed) | P2 table (documented)
## Cross-Ticket Coherence | ## Test Status (passing/build/new tests)
```

### Phase 4: Simplify
`git diff --name-only` for combined file list. Kill dead code, collapse redundancy, flatten nesting (max 2), purge slop comments, normalize style. Don't touch files outside scope. Don't add functionality. Verify after each file — revert if broken. Run tests after all changes.

Output `[I AM DONE]`. STOP.

## Pitfalls

1. **Workers must be self-contained** — No shared state between delegate_task workers
2. **Artifacts are the contract** — Always write research.md, plan.md, conformance.md
3. **Git commit between tickets** — Prevents cross-contamination
