---
name: pickle-rick-standup
description: "Show a formatted standup summary from Pickle Rick activity logs. Slack-formatted with Y:/T: grouped by project."
version: 0.3.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, standup, activity, reporting, metrics]
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: [pickle-rick, pickle-rick-meeseeks]
---

# Pickle Rick Standup — Activity Summary

Show a formatted standup summary from Pickle Rick activity logs.

## When to Use

- User says "standup", "pickle standup", "what did pickle do"
- User wants a summary of recent autonomous work
- User needs a Slack-formatted standup report

Show a formatted standup summary from Pickle Rick activity logs.



## Instructions

### Step 1: Run the standup helper

```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_utils.py standup user input
```

If no arguments provided, defaults to `--days 1` (yesterday's activity).

### Step 2: Format as Slack standup

**CRITICAL**: The raw tool output is NOT visible to the user. You MUST print the results as text in your response.

Format the output as a Slack-ready standup post:

```
Gregory Dickson [8:14 AM] *<date or date range>*
**Y:**
- **[project-name]** Concise summary of accomplishment
- **[project-name]** Another item
...

**T:**
- **[project-name]** What's planned next
```

**Rules:**
1. Every bullet gets a **[project-tag]** prefix (e.g. `[attractor]`, `[loanlight-api]`, `[Pickle Rick]`)
2. Consolidate related commits/activities into single human-readable bullets — don't list every commit or session ID
3. Keep it concise like a real Slack standup — no raw timestamps, session IDs, or commit hashes
4. Multi-day standups get combined into one post with a date range
5. **Y:** = what was accomplished, **T:** = what's planned next (infer from trajectory of recent work)
6. If the user asks for the full/raw output, print the complete standup verbatim instead

**Example:**

```
Gregory Dickson [8:14 AM] *Mar 14–16*
**Y:**
- **[document-ocr-prototypes]** New project to benchmark OCR across approaches. Docling appraisal extraction prototype: microverse convergence loop hit 100% extraction accuracy (96.8% → 100%) across 12 iterations — spatial proximity heuristics, checkbox detection, field defaults
- **[Pickle Rick]** pickle-dot v1.15.0 + v1.16.0: lint/typecheck/conformance gates, multi-provider model routing, "Reviews Are Dead" patterns (spec-first TDD, adversarial red team, competing impls), review convergence ratchet, retry target scoping fix
- **[attractor]** ESLint flat config with TS strict + import boundaries, fixed 49 errors
- **[attractor]** Stream-json live activity monitor, pipeline queue + orphan cleanup, non-root Docker, PM Guide
- **[Pickle Rick]** Fixed microverse infinite loop, Mastra dynamic→static imports, spawn-morty tests

**T:**
- App.loanlight.com integration, support any issues coming from John.
- **[attractor]** Test and fix cycles
- SOC audit prep
- develop ideas for devops automation with John (possibly tomorrow)
- Support new UI development approaches for Encompass UI.
- Review Bank Statement Analyzer (today or tomorrow)
```

### Common usage
- `pickle-rick-standup` — yesterday's activity
- `pickle-rick-standup --days 0` — today's activity
- `pickle-rick-standup --days 3` — last 3 days
- `pickle-rick-standup --since 2026-02-25` — everything since Feb 25


## Pitfalls

1. **Activity logs must exist** — Runs only after pickle-rick sessions have executed
2. **Default is 1 day** — Use --days N for longer lookback
3. **Groups by project** — Multiple sessions in same repo get combined
