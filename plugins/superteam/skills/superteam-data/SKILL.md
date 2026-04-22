---
name: superteam-data
description: Use when querying live product/business data via Superteam MCP agentic_data — campaigns, advertisers, in-app quests, badges, providers, alpha users; not Linear or engineering task tracking
---

# 数据洞察（MCP: agentic_data）

业务侧只读查询入口：通过 **Superteam MCP** 的 `agentic_data` tools 访问上游 GraphQL（活动、投放、增长玩法、链上 badge、provider 等）。

## 定位与边界

- **适用**：活动 / campaign、投放方 advertiser、**产品内** Quest 配置（`list_tasks` / `get_task`，与研发排期无关）、anchor / badge、provider、条件模板、alpha 用户、项目与全局配置等 **线上业务数据**。
- **不适用**：**Linear工单、研发迭代/Story、团队「任务谁做了多少」** — 请用 **`superteam-linear`**（`query_linear.py`）或知识库文档（`superteam-knowledgebase`）。
- **不适用**：钉钉多维表里的迭代/需求排期（`superteam-superteam-sync-task-data`落库）— 本 skill **不**查 AGE/本地任务图；若需查库请直接 SQL 或其它专用流程。
- **不适用**：团队知识库文档检索 — 请用 `superteam-knowledgebase`。

## 调用方式

**Agent（推荐）**：直接 `call_mcp_tool` 调用各 tool（先读 schema）。

**Hub CLI**：`superteam/scripts/route.py` 可命中本 skill 并执行 `scripts/query_agentic_data.py`（内部用 `skills/_shared/db.py` 的 HTTP MCP 客户端，需配置 `SUPERTEAM_MCP_URL` + `SUPERTEAM_API_TOKEN`）。

```bash
# 显式指定 tool（精确）
python3 skills/superteam-data/scripts/query_agentic_data.py --tool list_advertiser --name "Last Odyssey"

# 依赖句内关键词的轻量启发（适合 route 传入整句）
python3 skills/superteam-data/scripts/query_agentic_data.py "1962 链 series"
```

## 常用工具分组

- 项目与全局：`list_projects`、`get_project_detail`、`get_global_config`
- Campaign/Advertiser：`list_campaigns`、`get_campaign`、`list_campaign_advertisers`、`list_advertiser` 等
- Squad：`list_campaign_squad_tasks`、`list_campaign_squad_task_records`、`list_campaign_squad_reward_persona_records`
- Anchor/Badge：`list_anchor_series`、`list_anchor_tokens`、`get_anchor_token_detail`、`list_anchor_claimable`
- Provider：`search_providers`、`list_providers`、`get_provider`
- 产品 Quest（配置侧）：`list_tasks`、`get_task`（**不是** Linear issue / 多维表任务）
- 条件模板：`list_condition_category_info`、`list_condition_templates`
- Alpha：`list_alpha_users`、`get_alpha_user`

## 意图速查

| 用户意图 | 优先工具 |
|----------|----------|
| 查询项目/配置 | `list_projects` / `get_project_detail` / `get_global_config` |
| 查活动与投放方 | `list_campaigns` / `list_campaign_advertisers` / `list_advertiser` |
| 查产品内 Quest 配置 | `list_tasks` / `get_task` |
| 查 badge/series | `list_anchor_series` / `list_anchor_tokens` |
| 查 provider | `search_providers` / `get_provider` |
| 查条件模板 | `list_condition_category_info` / `list_condition_templates` |
| 查 alpha 用户 | `list_alpha_users` / `get_alpha_user` |

## 配置说明

客户端侧：保证可访问 `SUPERTEAM_MCP_URL` 并通过鉴权。  
服务端侧（MCP 进程）：`AUTH_CENTER_*`、`DEFAULT_PROJECT_ID`、`TASK_GRAPHQL_PATH` 等在部署环境配置。

## 参考

- `superteam-mcp-server/docs/agentic-data-tools-overview.md`
- `superteam-mcp-server/docs/agentic-data-tools.md`
