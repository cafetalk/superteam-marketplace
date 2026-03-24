---
name: hub
description: Use when answering user questions about the project, team, documents, or querying dynamic system data — routes to appropriate superteam skills
---

# Superteam Hub — 智能查询中枢

面向用户的查询代理。接收自然语言提问 → 理解意图 → 调用对应 skill → 返回结果。

## 定位

superteam:hub 是面向用户的智能查询入口。它理解用户意图并路由到正确的 superteam skill，返回结构化数据供 agent 合成自然语言回答。

## 职责边界

✅ 负责：
- 用户自然语言提问的意图识别
- **文档洞察**：调用 insight-docs 做语义搜索（RAG）
- **数据洞察**：调用 insight-data 查询系统实时数据（coming soon）
- **周报生成**：调用 weekly-report 生成周报（coming soon）
- 聚合多 skill 结果，生成自然语言回答

❌ 不负责：
- 数据同步 / 分块 / 入库
- 任何写操作

## 可调用 Skill 清单

| Skill | 调用场景 | 状态 |
|-------|----------|------|
| superteam:insight-docs | 语义搜索、成员查询、文档同步状态查询 | ✅ 已上线 |
| superteam:insight-data | 任务查询（成员贡献、迭代进度、任务详情） | 🔨 Coming soon |
| superteam:weekly-report | 智能周报生成 | 🔨 Coming soon |

## 使用方式

通过 route.py 执行查询：
```bash
python hub/scripts/route.py --query "用户的问题" --execute
```

不加 `--execute` 则只输出路由分类结果（JSON），不实际执行脚本。

## 意图路由规则

| 用户说 | 路由到 | 说明 |
|--------|--------|------|
| "PRD 里提到了什么功能？" | search_docs.py | 语义搜索，返回相关 chunks |
| "张三负责什么模块？" | search_docs.py | 从文档中搜索相关信息 |
| "团队有哪些后端开发？" | list_members.py | 返回团队成员列表 |
| "有哪些文档已同步？" | list_source_docs.py | 返回已同步源文档列表 |
| "张三在迭代25做了什么？" | query_tasks.py | 任务数据查询（coming soon） |
| "帮我生成本周周报" | generate_report.py | 周报生成（coming soon） |

### 触发关键词

| 路由目标 | 关键词 |
|----------|--------|
| insight-data | 迭代、任务、进度、bug、sprint、做了哪些、工作量、完成率 |
| weekly-report | 周报、weekly、report、本周、上周、工作总结 |
| list_members | 成员、团队成员、谁是、有哪些人、角色、前端、后端 |
| list_source_docs | 文档列表、已同步、同步状态、有哪些文档 |
| search_docs | （以上均不匹配时的 fallback，适用于任何知识类问题） |

## 结果使用指引

Hub 脚本返回结构化数据，由调用方 agent 负责合成自然语言回答。

### search_docs.py 输出

返回 JSON 信封：
```json
{
  "query": "原始查询",
  "skill": "insight-docs",
  "total_results": 5,
  "results": [
    {
      "id": 123,
      "title": "文档标题",
      "content": "chunk 文本内容...",
      "doc_type": "tech-design",
      "source_type": "dingtalk",
      "source_url": "https://...",
      "score": 0.2341,
      "chunk_index": 3,
      "total_chunks": 12
    }
  ]
}
```

**Agent 合成要点：**
1. **按文档聚合**：同一 `title` 的多个 chunk 应合并理解，不要逐条罗列
2. **引用来源**：使用 `title` 和 `source_url` 标注信息出处
3. **评估相关性**：`score` < 0.3 高度相关，> 0.5 相关性较低
4. **多次搜索**：对复杂问题，可用不同关键词多次调用 search_docs

### Embedding 预计算指引

**重要**：search_docs.py 需要 agent 预计算查询文本的 embedding 向量。

调用流程：
1. Agent 使用自身能力将用户查询文本转为 1536 维向量
2. 将向量作为 JSON 数组传给 `--embedding` 参数
3. 脚本用该向量做 pgvector 余弦相似度搜索

```bash
python3 search_docs.py "查询文本" --embedding "[0.01, -0.03, ...]"
```

向量维度必须为 1536（text-embedding-v2 / text-embedding-ada-002 兼容）。

### 成员智能匹配流程

当用户提到具体人名时，通过 `list_members.py resolve` 进行匹配：

```bash
python3 insight-docs/scripts/list_members.py resolve "Peter"
```

**完整链路示例**：
```
用户: "Peter 本周做了什么"
  → list_members.py resolve "Peter" → 命中 user_id=3
  → search_docs.py --query "本周工作" --embedding "[...]" --creator-id 3
  → 汇总结果返回用户
```

## 安全原则

1. **Query Only**：skill 只暴露查询，不暴露 mutation
2. **模板化查询**：SQL 查询硬编码在 skill 脚本中，Agent 只传参数
3. **字段白名单**：skill 脚本过滤返回字段，不暴露敏感数据

## 配置

唯一必须配置项：

```
KB_TREX_PG_URL=postgres://user:pass@host:port/db
```

配置位于 `~/.superteam/config`，由 `setup.sh` 引导设置。

## 依赖

- superteam:insight-docs（语义搜索、成员查询、文档状态）
- superteam:insight-data（数据洞察，coming soon）
- superteam:weekly-report（周报生成，coming soon）
