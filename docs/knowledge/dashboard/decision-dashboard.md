---
title: Decision Dashboard
type: dashboard
status: active
layer: architecture
tags: [dashboard, dataview, adr]
aliases: [Decision Dashboard]
---

# Decision Dashboard

```dataview
TABLE status, layer, tags
FROM "docs/knowledge/06_Decision_Log"
WHERE type = "decision-log"
SORT title ASC
```
