---
name: superteam-member
description: Use when querying or managing team member profiles, aliases, and resolution
---

# 成员管理与解析

统一处理成员域能力：成员查询、智能匹配、别名维护、资料修改与审计。

## 职责边界

✅ 负责：
- 成员查询：按姓名/角色/user_id 查询成员
- 成员智能匹配：`resolve`（精确 + alias + 模糊匹配）
- 资料维护：`update` / `set-aliases` / `append-alias`
- 审计落库：写操作记录 `kb_trex_member_audit_logs`

❌ 不负责：
- 文档语义检索（由 `superteam-knowledgebase` 负责）
- 文档同步、分块、入库（由 `superteam-sync/*`、`superteam-store-kb-pgsql` 负责）

## 脚本接口

### 1) 成员查询与解析 `list_members.py`

```bash
# 列出成员
python3 scripts/list_members.py list
python3 scripts/list_members.py list --name "张三"
python3 scripts/list_members.py list --role "后端开发"
python3 scripts/list_members.py list --user-id 3

# 智能匹配
python3 scripts/list_members.py resolve "Peter"
python3 scripts/list_members.py resolve "小王" --platform github
```

### 2) 写操作 `manage_members.py`

```bash
# 查询单个成员
python3 scripts/manage_members.py get --user-id 2

# 更新资料
python3 scripts/manage_members.py update \
  --operator-user-id 1 \
  --user-id 2 \
  --real-name "许伟" \
  --username "xu.wei" \
  --role "测试" \
  --email "xuwei@example.com"

# 当审计表尚未建好时，可临时跳过审计
python3 scripts/manage_members.py update \
  --user-id 2 \
  --role "测试" \
  --no-audit

# 替换 aliases
python3 scripts/manage_members.py set-aliases \
  --operator-user-id 1 \
  --user-id 2 \
  --aliases-json '["许伟", "Wei", "xuwei"]'

# 追加 alias
python3 scripts/manage_members.py append-alias \
  --operator-user-id 1 \
  --user-id 2 \
  --alias "老许"
```

## 权限规则

- 写操作需要 `KB_TREX_PG_URL`（Direct）
- `--operator-user-id` 可选；传入时用于审计归因（记录操作人）
- 不传 `--operator-user-id` 时，写操作照常执行，但会自动跳过审计写入
- Client/MCP 场景应仅使用只读查询与 resolve
