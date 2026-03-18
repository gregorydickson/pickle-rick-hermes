---
name: pickle-rick-jar
description: "Pickle Jar batch job queue: queue multiple PRDs/tasks for sequential autonomous execution. Add tasks to the jar, then open it to process them one by one."
version: 0.2.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, batch, queue, pickle-jar, orchestration]
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: [pickle-rick, pickle-rick-meeseeks]
---

# Pickle Jar — Batch Job Queue

Queue multiple tasks/PRDs for sequential autonomous execution. Add tasks to
the jar, then open it to process them one by one via pickle-rick.

## When to Use

- User has multiple independent tasks to run sequentially
- User says "pickle jar", "queue these tasks", "batch run"
- User wants to set up tasks now but run them later (e.g., overnight)

## File Layout

```
~/.pickle-rick/jar/
  jar_manifest.json     # Queue manifest
  <hash>/
    prd.md              # Task PRD (or description)
    config.json         # Per-task config (working_dir, max_iterations, etc.)
```

## Commands

### Add to Jar

```python
# In a Hermes session:
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_jar.py add --task 'Build user auth' --working-dir ~/project")
```

Creates a jar entry with a PRD placeholder and config.

### List Jar Contents

```python
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_jar.py list")
```

### Open the Jar (Execute All)

```python
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_jar.py run")
```

Processes tasks sequentially:
1. For each task in order:
   a. Initialize a pickle-rick session with the task's config
   b. Run the mux_runner.py to completion
   c. Record result (success/failure)
   d. Move to next task
2. Summary report at the end

### Remove from Jar

```python
terminal(command="python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_jar.py remove --id <hash>")
```

## jar_manifest.json

```json
{
  "created": "2026-03-17T12:00:00Z",
  "tasks": [
    {
      "id": "abc12345",
      "task": "Build user authentication",
      "working_dir": "/home/user/project",
      "max_iterations": 50,
      "status": "queued",
      "added_at": "2026-03-17T12:00:00Z",
      "completed_at": null,
      "session_dir": null,
      "chain_meeseeks": true
    }
  ]
}
```

## Jar Runner Flow

```
jar open
  ├── Task 1: init session → mux_runner.py → complete
  ├── Task 2: init session → mux_runner.py → complete  
  ├── Task 3: init session → mux_runner.py → blocked (logged, continue)
  └── Summary report
```

## Integration

- **Cron**: Schedule jar runs with Hermes cronjob tool
- **Meeseeks chaining**: Set chain_meeseeks=true per task for post-implementation review
- **Overnight runs**: Add tasks during the day, run the jar overnight

## Pitfalls

1. **Tasks must be independent** — jar runs sequentially, no shared state between tasks
2. **Check working_dir** — each task can target a different directory
3. **Monitor progress** — check jar_manifest.json for status updates
