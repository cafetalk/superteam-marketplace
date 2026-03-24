---
name: insight-docs
description: Use when querying the team knowledge base — semantic search over documents (PRD, weekly reports, design docs) and team member lookups
---

# 文档洞察

对 `kb_trex_team_docs` 做语义搜索、对 `kb_trex_team_members` 做成员查询。**只读**，不做任何写入。

## 职责边界

✅ 负责：
- 语义搜索：用户查询 → 预计算向量 → pgvector 余弦相似度 → 返回最相关 chunks
- 团队成员查询：按姓名/角色/user_id 查找成员
- 文档元数据查询：查看已同步文档列表、同步状态

❌ 不负责：
- 文档入库 / embedding 生成
- 数据同步

## 脚本接口

### 1. 语义搜索 search_docs.py

**重要**：`--embedding` 参数必须由 agent 预计算后传入。

```bash
python3 scripts/search_docs.py "用户的问题" \
  --embedding "[0.01, -0.03, ...]" \
  [--doc-type Plan] [--top-k 5] [--creator-id 3] [--output-format text]
```

| 参数 | 说明 | 默认 |
|------|------|------|
| query | 自然语言问题（位置参数） | 必填 |
| --embedding | 1536 维向量 JSON 数组（agent 预计算） | 必填 |
| --top-k | 返回条数 | 5 |
| --doc-type | prd / tech-design / reference / guide 等 | 不筛 |
| --creator-id | 只查该成员的文档 | 不筛 |
| --output-format | json / text | json |

输出 JSON 数组，每项含 `id, content, doc_type, file_name, creator_id, score`。

### 2. 团队成员查询 list_members.py

```bash
# 列出所有成员
python3 scripts/list_members.py list

# 按姓名模糊搜索
python3 scripts/list_members.py list --name "张三"

# 按角色筛选
python3 scripts/list_members.py list --role "后端开发"

# 智能成员匹配（精确 + 别名两级级联）
python3 scripts/list_members.py resolve "Peter"
```

输出 JSON 数组，每项含 `user_id, username, real_name, real_name_en, role, aliases, created_at`。

**resolve 子命令** 调用 `_shared/super_member.py`，通过精确匹配 + 别名缓存进行智能成员查找。

### 3. 文档同步状态 list_source_docs.py

```bash
# 列出所有已同步的源文档
python3 scripts/list_source_docs.py

# 按来源类型筛选
python3 scripts/list_source_docs.py --source-type dingtalk

# 按文件名模糊搜索
python3 scripts/list_source_docs.py --name "周报"
```

输出 JSON 数组，每项含 `id, source_type, source_doc_id, file_name, last_edited_at, last_synced_at`。

## 配置

- 环境变量或 `~/.superteam/config`：`KB_TREX_PG_URL`
- Python packages: psycopg2
- 数据库 schema: trex_hub（pgvector 扩展已安装在此 schema）
