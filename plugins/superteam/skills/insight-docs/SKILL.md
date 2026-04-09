---
name: superteam:insight-docs
description: Use when querying the team knowledge base — semantic search over documents (PRD, weekly reports, design docs) and team member lookups
---

# 文档洞察

对 `kb_trex_team_docs` 做语义搜索、对 `kb_trex_team_members` 做成员查询。**只读**，不做任何写入。

## 职责边界

✅ 负责：
- 语义搜索：用户自然语言问题 → embedding → pgvector 余弦相似度 → 返回最相关 chunks
- 团队成员查询：按姓名/角色/user_id 查找成员
- 文档元数据查询：查看已同步文档列表、同步状态

❌ 不负责：
- 文档入库 / embedding 生成（由 superteam:store-kb-pgsql 处理）
- 数据同步（由 superteam:sync-dingtalk-kb 等处理）
- 动态数据查询（由 superteam:source-* 处理）

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

### 2. 团队成员查询 list_members.py

```bash
# 列出所有成员
python3 scripts/list_members.py list

# 按姓名模糊搜索
python3 scripts/list_members.py list --name "张三"

# 按角色筛选
python3 scripts/list_members.py list --role "后端开发"

# 按 user_id 精确查
python3 scripts/list_members.py list --user-id 3

# 智能成员匹配（精确 + 模糊两级级联）
python3 scripts/list_members.py resolve "Peter"
python3 scripts/list_members.py resolve "小王" --role "后端开发"

# 别名管理
python3 scripts/list_members.py alias "张三" --add "老张"
python3 scripts/list_members.py review --dry-run     # 查看 LLM 建议
python3 scripts/list_members.py review --apply       # 应用别名建议
```

输出 JSON 数组，每项含 `user_id, username, real_name, real_name_en, role, aliases, created_at`。

**resolve 子命令** 调用 `_shared/super_member.py`，通过两级级联匹配（精确 → 模糊）进行智能成员查找。

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
| "团队里有哪些后端开发？" | list_members.py | role="后端开发" |
| "谁的 user_id 是 5？" | list_members.py | user_id=5 |
| "有哪些文档已经同步了？" | list_source_docs.py | (无参数) |

## 依赖

- 环境变量：KB_TREX_PG_URL, DASHSCOPE_API_KEY (或 OPENAI_API_KEY)
- KB_TREX_PG_URL 也可从 ~/.dingtalk-skills/config 读取
- Python packages: psycopg2
- 数据库 schema: trex_hub（pgvector 扩展已安装在此 schema）
