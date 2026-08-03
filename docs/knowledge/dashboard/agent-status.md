---
title: Agent Status
type: dashboard
status: active
layer: agents
tags: [dashboard, dataview, agents]
aliases: [Agent Status]
---

# Agent Status

```dataview
TABLE status, layer, version
FROM "docs/knowledge/02_Agent_Design"
WHERE type = "agent-design"
SORT status ASC, title ASC
```
