---
name: pickle-rick-refine-prd
description: "Refine PRDs using 3 parallel analyst subagents (requirements, codebase, risk/scope), then decompose into atomic tickets with verification criteria."
version: 0.2.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, PRD, refinement, analysis, tickets, decomposition]
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: [pickle-rick, pickle-rick-prd, pickle-rick-morty]
---

# Pickle Rick PRD Refinement — Parallel Analyst Team

Refine a PRD using 3 parallel analyst subagents, then decompose into atomic
tickets ready for pickle-rick execution. The analysts catch gaps in requirements,
codebase conflicts, and risks BEFORE you spend tokens on implementation.

## When to Use

- User says "refine this PRD", "refine-prd", "analyze my requirements"
- Before executing a complex PRD (5+ tickets expected)
- User wants verification-readiness checking

## Step 1: Locate PRD

Priority:
1. Explicit path provided by user
2. `prd.md` or `PRD.md` in working directory
3. Most recent pickle-rick session's prd.md

Not found → "Write a PRD first (use pickle-rick-prd skill) or provide a path."

## Step 2: Verification Readiness Check

Read the PRD and gate on verification quality:

### 2a: Section Scan
Check for:
- Interface Contracts / API Contracts / type definitions
- Verification Strategy / Acceptance Criteria with commands
- Test Expectations / test descriptions per requirement
- Functional Requirements with Verification column

Score: FULL / PARTIAL / MISSING

### 2b: Quality Scan
- **Contracts**: Exact shapes (fields+types) = PASS. Prose = NEEDS_WORK.
- **Verification**: Runnable commands = PASS. Aspirational = NEEDS_WORK.
- **Tests**: Specific files/assertions = PASS. Vague = NEEDS_WORK.
- **Requirements**: Machine-checkable = PASS. Subjective = NEEDS_WORK.

### 2c: Gate
**FULL + PASS** → Continue to refinement.
**PARTIAL/NEEDS_WORK** → Pause, show gaps, use clarify to interview user:
- Missing contracts: "What data crosses boundaries? Exact shapes."
- Missing verification: "How to verify each requirement? Commands or assertions."
- Missing tests: "What test files? Scenarios and assertions."
Update PRD in place, then continue.

## Step 3: Initialize Session

```bash
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py init --task 'PRD Refinement: TASK' --working-dir .")
```

Copy PRD into session: `cp prd.md {SESSION_DIR}/prd.md`

## Step 4: Deploy Refinement Team

Spawn 3 parallel analysts via delegate_task:

```python
delegate_task(tasks=[
    {
        "goal": "Requirements analysis of PRD",
        "context": """ROLE: Requirements Analyst
        Read the PRD at {SESSION_DIR}/prd.md.
        
        CHECK:
        - Every functional requirement has machine-checkable verification
        - Acceptance criteria are specific and testable
        - No subjective or unmeasurable requirements
        - All CUJs have complete step sequences
        - Interface contracts have exact type shapes
        - Test expectations specify files, descriptions, assertions
        
        Write {SESSION_DIR}/analysis_requirements.md with:
        - P0 gaps (missing verification, vague requirements)
        - P1 improvements (better test coverage, clearer contracts)
        - Specific rewrites for each issue found""",
        "toolsets": ["file"]
    },
    {
        "goal": "Codebase context analysis for PRD",
        "context": """ROLE: Codebase Context Analyst
        Read the PRD at {SESSION_DIR}/prd.md.
        Analyze the target codebase.
        
        CHECK:
        - Integration points exist where PRD says they do
        - File paths referenced in PRD are correct
        - Existing patterns that might conflict
        - Convention alignment (naming, structure, error handling)
        - Dependency requirements are satisfiable
        
        Write {SESSION_DIR}/analysis_codebase.md with:
        - Verified/corrected file paths
        - Integration point assessment
        - Convention conflicts
        - Suggested implementation approach""",
        "toolsets": ["file", "terminal"]
    },
    {
        "goal": "Risk and scope analysis for PRD",
        "context": """ROLE: Risk & Scope Analyst
        Read the PRD at {SESSION_DIR}/prd.md.
        
        CHECK:
        - Scope creep indicators (overly broad requirements)
        - Technical risks (complexity, dependencies, unknowns)
        - Test coverage gaps
        - Missing error handling requirements
        - Deployment/migration risks
        
        Write {SESSION_DIR}/analysis_risk-scope.md with:
        - Risk register (severity + mitigation per risk)
        - Scope concerns
        - Missing requirements discovered
        - Recommended test additions""",
        "toolsets": ["file"]
    }
])
```

## Step 5: Synthesize Refined PRD

Read all three `analysis_*.md` files plus the original PRD.

Write `{SESSION_DIR}/prd_refined.md`:
1. Preserve original structure, additive over rewriting
2. Attribute additions: `*(refined: [source])*`
3. P0 gaps first, P1 next
4. No invention — analyses only
5. Every requirement gets machine-checkable criterion
6. Contracts required: exact I/O/error shapes
7. Implementation-oriented: file paths, signatures, shapes

Copy refined PRD back: preserve original as `prd_pre_refinement.md`, write refined to `prd.md`.

## Step 6: Task Decomposition

Break refined PRD into atomic tickets:

### Ticket Requirements
- Produces code/config/test changes (no research-only tickets)
- Sequential order (10, 20, 30...)
- Self-contained: worker executes without reading PRD
- Embed research seeds (file paths, patterns, APIs)
- Machine-checkable acceptance criteria with verify commands
- Interface contracts: exact I/O/error shapes
- Test expectations: file, description, assertion per criterion
- Sizing: <30min coding, <5 files, <4 criteria, <2 subsystems

### Create Tickets

Create parent: `{SESSION_DIR}/parent_ticket.md`
Create children: `{SESSION_DIR}/tickets/<hash>/ticket.md` using the enhanced template.

### Advance State

```bash
terminal(command="python3 scripts/pickle_state.py update --session SESSION_DIR --step research --current-ticket FIRST_ID")
```

## Step 7: Write Summary

Write `{SESSION_DIR}/refinement_summary.md`: timestamp, per-analysis changes, task list, risk flags.

## Step 8: Handoff

Report: PRD path, ticket count, risk level, resume commands.

"Run pickle-rick with --resume SESSION_DIR to execute, or review the refined PRD first."



## Pitfalls

1. **Don't run all 3 analysts sequentially** — Use delegate_task for parallel execution
2. **Merge conflicts** — Three analysts may propose contradictory changes; the aggregator must resolve
3. **Ticket ordering matters** — Dependencies must be reflected in ticket order numbers
4. **Don't over-decompose** — Each ticket should represent a meaningful, testable change
