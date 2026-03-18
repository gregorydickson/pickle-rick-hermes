---
name: pickle-rick-portal-gun
description: "Pattern transplantation: open a portal to another codebase, extract its patterns, and generate a PRD to transplant them into your project. Supports GitHub repos, local paths, npm/PyPI packages."
version: 0.1.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, transplant, patterns, portal-gun, code-analysis]
    homepage: https://github.com/ATheorical/pickle-rick-claude
    related_skills: [pickle-rick, pickle-rick-meeseeks]
---

# Portal Gun — Pattern Transplantation

Open a portal to another codebase, extract its patterns, and generate a PRD
to transplant them into your project. The PRD can then be fed to pickle-rick
for autonomous implementation.

## When to Use

- User says "portal gun", "transplant", "steal this pattern", "port this from"
- User wants to replicate a pattern from one codebase in another
- User provides a GitHub URL, local path, or package name as the "donor"

## Workflow

### Step 0: Parse Input

The user provides:
- **Exemplar** (required): GitHub URL, local path, npm/PyPI package, or plain text pattern description
- **Target** (optional, default: cwd): Where to transplant the pattern
- **Depth** (optional, default: deep): `shallow` (summary only) or `deep` (full analysis)
- **Flags**: --run (auto-launch pickle-rick after), --meeseeks (chain review), --no-refine (skip refinement)

### Step 1: Initialize Session

```bash
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_state.py init --task 'Portal Gun: EXEMPLAR' --working-dir TARGET_DIR")
```

Create `{session_dir}/portal/donor/` directory for acquired source.

### Step 2: Acquire Exemplar (Open the Portal)

Based on exemplar type:

**GitHub URL:**
- Single file: use web_extract or terminal with `gh api`
- Directory: `gh api repos/{owner}/{repo}/contents/{path}` — fetch key source files (max 10)
- Full repo: clone sparse or fetch README + key dirs
- Save to `{session_dir}/portal/donor/`

**Local Path:**
- File: copy to portal/donor/
- Directory: copy key source files (implementation > tests > docs, max 15)

**Package Name:**
- npm: `npm info <pkg>` for repo URL, then treat as GitHub
- PyPI: `pip show <pkg>` for homepage, then treat as GitHub

**Plain Text Description:**
- No source to fetch — synthesize from knowledge
- Write `{session_dir}/portal/pattern_description.md`
- Skip to Step 4

### Step 3: Pattern Extraction (Scan the Other Side)

Analyze donor code. Write `{session_dir}/portal/pattern_analysis.md`:

```markdown
# Pattern Analysis: [Name]

## Source
[URL/path/package]

## Pattern Summary
[1-2 paragraph description]

## Structural Pattern
[Abstract pattern independent of language/framework]
- Entry points, data flow, key abstractions
- State management, error handling

## Invariants
[Rules that MUST hold for this pattern to work]

## Edge Cases & Gotchas

## Key Implementation Details
[Specific techniques worth preserving]

## Dependencies & Prerequisites

## Anti-Patterns
[What NOT to do]

## File Manifest
[EVERY donor file with purpose]

## Import Graph
[Trace imports from entry point]

## File Classification
[Per-file: Direct transplant / Behavioral reference / Replace with equivalent / Not needed]
```

### Step 4: Target Analysis (Survey This Side)

Analyze target codebase. Write `{session_dir}/portal/target_analysis.md`:

```markdown
# Target Codebase Analysis

## Tech Stack
## Relevant Existing Patterns
## Conventions (naming, structure, error handling, testing)
## Integration Points
## Conflicts & Constraints
## Adaptation Requirements (language, framework, conventions)
## Per-File Modification Specs
```

### Step 5: Synthesize PRD

Cross-reference pattern_analysis.md and target_analysis.md.
Write `{session_dir}/prd.md` using the transplant PRD format:

- Standard PRD template adapted for transplantation
- Functional requirements reference donor file:line + adaptation notes
- Behavioral validation tests map donor invariants to target
- Portal Artifacts section references the analysis files

### Step 5.5: PRD Validation Pass

Validate all file paths in the PRD against the filesystem:
- Extract backtick-quoted paths
- Classify each: VALID, SHIFTED, INVALID, NOT FOUND, STALE, TO-CREATE
- Write `{session_dir}/portal/validation_report.md`
- Fix issues in the PRD

### Step 6: Refinement (Optional)

If not --no-refine, spawn 3 parallel reviewer subagents:

```python
delegate_task(
    goal="Requirements analysis of transplant PRD",
    context="Validate functional requirements against donor invariants...",
    toolsets=['file']
)
delegate_task(
    goal="Codebase context analysis",
    context="Check integration points, convention alignment...",
    toolsets=['file', 'terminal']
)
delegate_task(
    goal="Risk and scope analysis",
    context="Evaluate transplant risks, semantic drift potential...",
    toolsets=['file']
)
```

Synthesize refined PRD from reviewer outputs.

### Step 7: Launch (if --run)

Feed the PRD to pickle-rick for autonomous implementation:
```
"Run pickle rick with the PRD at {session_dir}/prd.md"
```

## Portal Artifacts

```
{session_dir}/portal/
  donor/              # Acquired source files
  pattern_analysis.md # Donor pattern extraction
  target_analysis.md  # Target codebase analysis
  validation_report.md # PRD path validation
```

## Pattern Library (Persistence)

Save extracted patterns for reuse across sessions:

```bash
# Save after extraction
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pattern_library.py save --name 'auth-jwt' --source 'github.com/owner/repo' --analysis SESSION_DIR/portal/pattern_analysis.md --summary 'JWT auth with refresh tokens'")

# Search before extracting (check if pattern already cached)
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pattern_library.py search --query 'auth'")

# List all saved patterns
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pattern_library.py list")

# Load a cached pattern
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pattern_library.py get --name 'auth-jwt'")
```

### Auto-Save Decision Tree

1. `--save-pattern <name>` flag set → save immediately, no prompt
2. Flag not set AND refinement ran → ask user: "Save pattern to library?"
3. Flag not set AND `--no-refine` → skip with hint

### Before Extraction: Check Library

In Step 3a, before analyzing donor code:
1. Search the pattern library for matching patterns
2. On exact match (same source): use cached analysis as baseline, verify against current donor
3. On partial match (related source): use as cross-reference context
4. On no match: full fresh analysis

Patterns stored in `~/.pickle-rick/patterns/<name>/pattern_analysis.md`

## Pitfalls

1. **Always validate paths** — PRDs with wrong paths create broken tickets
2. **Respect depth flag** — shallow analysis doesn't need import graphs
3. **Classify files before transplanting** — not everything needs to be copied
4. **Adapt conventions** — donor patterns must match target style
5. **Test invariants** — every invariant needs a behavioral validation test
6. **Check library first** — don't re-extract patterns you've already cached
