---
name: insight-data
description: Use when querying task management data — member contributions, iteration progress, task assignments via AGE Cypher graph queries with SQL fallback
---

# 数据洞察

任务管理数据的查询入口，通过 Apache AGE 图查询（Cypher）+ SQL 物化视图提供高效的关系遍历和聚合查询。

## 定位

hub 路由任务/迭代/成员相关问题到 insight-data，由 query_tasks.py 执行 Cypher 或 SQL 查询。

## 架构

```
用户提问 → hub → insight-data/scripts/query_tasks.py
                        ↓
              AGE task_graph (Cypher 优先)
                        ↓ (降级)
              SQL 关系表 + 物化视图
```

## 查询模式

### 1. 成员任务查询
```bash
python3 superteam/skills/insight-data/scripts/query_tasks.py \
  --member 张三 --iteration 迭代25
```
**Cypher**: `MATCH (m:Member {name: '张三'})-[w:WORKS_ON]->(t:Task)-[:BELONGS_TO]->(i:Iteration)`

### 2. 任务成员查询
```bash
python3 superteam/skills/insight-data/scripts/query_tasks.py \
  --task <notable_id>
```
**Cypher**: `MATCH (m:Member)-[w:WORKS_ON]->(t:Task {notable_id: 'xxx'})`

### 3. 迭代进度总结
```bash
python3 superteam/skills/insight-data/scripts/query_tasks.py \
  --iteration 迭代25 --summary
```
**SQL**: `SELECT * FROM mv_iteration_progress WHERE name = '迭代25'`（聚合查询用 SQL 更高效）

## 数据来源

数据由 `sync-task-data` 从钉钉多维表格同步：

| 表 | 内容 |
|----|------|
| tm_iterations | 迭代 |
| tm_tasks | 任务（需求） |
| tm_task_members | 任务-成员-角色关联 |
| tm_bugs | Bug |
| AGE task_graph | 图层（Member→Task→Iteration 关系） |
| mv_member_iteration_summary | 成员-迭代贡献汇总（物化视图） |
| mv_iteration_progress | 迭代进度概览（物化视图） |

## 下辖数据源 Skill

| Skill | 数据类型 | 说明 |
|-------|----------|------|
| source-dingtalk-table | 多维表格 | 钉钉多维表格读取（read_notable.py） |
| source-dingtalk-document | 文档内容 | 钉钉文档直接读取 |
| source-dingtalk-spreadsheet | 电子表格 | 钉钉电子表格读取 |

## 配置

```
KB_TREX_PG_URL=<postgres://...>  # 必需
```

AGE 扩展需在 RDS 控制台启用（PG14+）。未启用时自动降级为 SQL 查询。

## 待设计事项

- [ ] 更多图遍历查询（如：任务依赖链、成员协作网络）
- [ ] 自然语言 → Cypher 生成（LLM 辅助）
- [ ] 数据权限控制
