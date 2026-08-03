---
title: Version Progress
type: dashboard
status: active
layer: release
tags: [dashboard, dataview, version]
aliases: [Version Progress]
---

# Version Progress

```dataview
TABLE version, status, layer
FROM "docs/knowledge"
WHERE version
SORT version DESC
```
