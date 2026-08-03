---
title: Engineering Knowledge Dashboard
type: dashboard
status: active
layer: documentation
tags: [dashboard, dataview]
---

# Engineering Knowledge Dashboard

```dataview
TABLE status, layer, version
FROM "docs/knowledge"
WHERE type AND type != "dashboard"
SORT layer ASC, title ASC
```

入口：[[Agent Status]]、[[Version Progress]]、[[Decision Dashboard]]。
