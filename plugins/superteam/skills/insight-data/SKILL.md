---
name: insight-data
description: Use when querying task management data — member contributions, iteration progress, task assignments via AGE Cypher graph queries with SQL fallback
---

# 数据洞察 (Coming Soon)

任务管理数据的查询入口，通过 Apache AGE 图查询（Cypher）+ SQL 物化视图提供高效的关系遍历和聚合查询。

## 状态

> **骨架实现** — 核心查询逻辑已完成，数据源待接入。

## 查询模式

### 1. 成员任务查询
```bash
python3 scripts/query_tasks.py --member 张三 --iteration 迭代25
```

### 2. 任务成员查询
```bash
python3 scripts/query_tasks.py --task <notable_id>
```

### 3. 迭代进度总结
```bash
python3 scripts/query_tasks.py --iteration 迭代25 --summary
```

## 配置

```
KB_TREX_PG_URL=<postgres://...>
```

AGE 扩展需在 RDS 控制台启用（PG14+）。未启用时自动降级为 SQL 查询。
