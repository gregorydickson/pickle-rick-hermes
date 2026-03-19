---
name: pickle-rick-jar
description: "Pickle Jar batch job queue: queue multiple PRDs/tasks for sequential autonomous execution. Add tasks, then open the jar to process them one by one."
version: 0.3.0
author: Gal Zahavi (original), Gregory Dickson (Hermes port)
license: Apache-2.0
metadata:
  hermes:
    tags: [autonomous, batch, queue, jar, sequential]
    homepage: https://github.com/gregorydickson/pickle-rick-hermes
    related_skills: [pickle-rick, pickle-rick-tmux]
---

# Pickle Jar — Batch Job Queue

Queue multiple PRDs/tasks for sequential autonomous execution.

## When to Use

- User says "add to jar", "pickle jar", "batch these tasks"
- User wants to queue multiple tasks for overnight execution
- User has several PRDs to process sequentially

## Adding to the Jar

```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_jar.py add \
  --task "Build user authentication" --working-dir ~/project
```

## Opening the Jar (Execute All)

```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_jar.py run
```

The jar runner processes tasks sequentially, spawning a fresh hermes -q session
for each task. macOS notifications on completion.

## Listing Queued Tasks

```bash
python3 ~/.hermes/skills/autonomous-ai-agents/pickle-rick/scripts/pickle_jar.py list
```

## Jar Data

Jar queue stored at `~/.pickle-rick/jar/`.

## Pitfalls

1. **Working directory must be absolute** — Relative paths break when jar runs later
2. **Each task gets a fresh session** — No shared state between jar items
3. **Signal handling** — Jar runner responds to SIGTERM/SIGINT gracefully
4. **Order matters** — Tasks execute in queue order, not priority
