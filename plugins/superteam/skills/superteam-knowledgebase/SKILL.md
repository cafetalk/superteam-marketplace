---
name: superteam-knowledgebase
description: Use when querying the team knowledge base — semantic search over documents (PRD, weekly reports, design docs) and team member lookups
---

# 文档洞察

对 `kb_trex_team_docs` 做语义搜索与文档元数据查询。成员域能力已迁移到 `superteam-member`。

## 职责边界

✅ 负责：
- 语义搜索：用户自然语言问题 → embedding → pgvector 余弦相似度 → 返回最相关 chunks
- 文档元数据查询：查看已同步文档列表、同步状态

❌ 不负责：
- 文档入库 / embedding 生成（由 superteam-superteam-store-kb-pgsql 处理）
- 数据同步（由 superteam-superteam-sync-dingtalk-kb 等处理）
- 动态数据查询（由 superteam:source-* 处理）
- 成员查询/解析/管理（由 `superteam-member` 处理）

## 脚本接口

### 1. 语义搜索 search_docs.py

```bash
python3 scripts/search_docs.py "用户的问题" [--doc-type Plan] [--top-k 5] [--creator-id 3] [--output-format text]
```

| 参数 | 说明 | 默认 |
|------|------|------|
| query | 自然语言问题（位置参数） | 必填 |
| --top-k | 返回条数 | 5 |
| --doc-type | PRD / Design / Arch / Plan | 不筛 |
| --creator-id | 只查该成员的文档 | 不筛 |
| --output-format | json / text | json |

输出 JSON 数组，每项含 `id, content, doc_type, file_name, creator_id, metadata, score`（score 为余弦距离，越小越相似）。`--output-format text` 输出可读段落。

### 2. 成员能力迁移说明

成员查询、智能匹配与管理员资料维护已迁移到 `superteam-member`：

```bash
python3 ../superteam-member/scripts/list_members.py list --name "张三"
python3 ../superteam-member/scripts/list_members.py resolve "Peter"
python3 ../superteam-member/scripts/manage_members.py update --operator-user-id 1 --user-id 2 --role "测试"
```

### 3. 文档同步状态 list_source_docs.py

```bash
# 列出所有已同步的源文档
python3 scripts/list_source_docs.py

# 按来源类型筛选
python3 scripts/list_source_docs.py --source-type dingtalk

# 按文件名模糊搜索
python3 scripts/list_source_docs.py --name "周报"
```

输出 JSON 数组，每项含 `id, source_type, source_doc_id, file_name, last_edited_at, last_synced_at, sync_version`。

## 意图路由示例

| 用户说 | 调用 | 参数 |
|--------|------|------|
| "PRD 里提到了什么功能？" | search_docs.py | query="PRD 功能", doc_type="PRD" |
| "最新的周报说了什么？" | search_docs.py | query="最新周报", doc_type="Plan" |
| "李治锋本周做了什么？" | search_docs.py | query="李治锋 本周计划 工作安排", doc_type="Plan" |
| "张三负责什么模块？" | search_docs.py | query="张三 负责 模块" |
| "有哪些文档已经同步了？" | list_source_docs.py | (无参数) |

## 依赖

- 环境变量：KB_TREX_PG_URL, DASHSCOPE_API_KEY (或 OPENAI_API_KEY)
- KB_TREX_PG_URL 也可从 ~/.dingtalk-skills/config 读取
- Python packages: psycopg2
- 数据库 schema: trex_hub（pgvector 扩展已安装在此 schema）
