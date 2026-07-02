---
name: superteam
description: Use when answering user questions about the project, team, documents, or querying dynamic system data — routes to appropriate superteam skills
---

# 智能代理中枢

面向用户的 Agentic 代理。接收自然语言提问 → 理解意图 → 调用对应 skill → 返回结果。

## 定位

superteam 是面向用户的智能代理，不参与数据管道。它是知识库对话的入口，负责理解用户意图并路由到正确的 superteam skill。

## 职责边界

✅ 负责：
- 用户自然语言提问的意图识别
- **文档洞察**：调用 superteam-knowledgebase 做语义搜索（RAG）
- **业务数据洞察**：**superteam-data**（`query_agentic_data.py` → MCP `agentic_data`）— 活动/投放/growth、badge、provider、产品 Quest 配置等，**与 Linear / 研发任务排期无关**。
- **研发任务 / Linear**：**superteam-linear**（`query_linear.py`）— 工单、迭代、cycle 等；路由关键词与 **superteam-data 不重叠**（避免误命中业务 MCP）。
- **周报生成**：调用 superteam-report 生成周报（待实现）
- 聚合多 skill 结果，生成自然语言回答
- 未来：多轮对话、追问、引用溯源

❌ 不负责：
- Hub 自身不直接执行写操作（仅负责意图识别与路由）
- 但可路由到具备写能力的下游 skill（如 superteam-git）执行提交/提测流程
- 数据同步 / 分块 / 入库（由 superteam-sync 编排）
- 触发 flow
- 直接操作数据源 API

## 可调用 Skill 清单

| Skill | 调用场景 | 状态 |
|-------|----------|------|
| superteam-knowledgebase | 语义搜索、文档同步状态查询 | ✅ 已上线 |
| superteam-member | 成员查询、成员智能匹配、成员资料管理（写操作仅 Direct 管理员） | ✅ 已上线 |
| superteam-data | 业务侧线上数据（活动/投放、badge、provider、产品 Quest 等，MCP agentic_data） | ✅ `query_agentic_data.py`（桥接 MCP） |
| superteam-linear | Linear 工单/迭代（官方 MCP HTTP + Bearer） | ✅ `query_linear.py` |
| superteam-git | 本地 Git 洞察、提交代码、提测合并（按 superteam-git 规范执行） | ✅ `query_git.py` |
| superteam-report | 智能周报生成、sprint/task/member pulse 快照 | ✅ 已上线 |
| superteam-report-insight | PAI v2 Project Lead 简报（由 sprint 派生） | ✅ `snapshot_pai.py` |
| superteam-pai | PAI 调度框架（规则规划 + pulse/周报编排） | ✅ `run_pai.py`（B V1） |

Hub **不调用** superteam-sync、sync-*、process-*、store-*、source-* 系列 skill。

## 使用方式

通过 route.py 执行查询：
```bash
python superteam/scripts/route.py --query "用户的问题" --execute
```

不加 `--execute` 则只输出路由分类结果（JSON），不实际执行脚本。

## 执行硬约束（必须遵守）

<HARD-GATE>
当用户消息包含 `/superteam` 前缀时，Agent 必须先通过 `skills/superteam/scripts/route.py` 完成路由判定，再决定是否执行下游 skill。
禁止绕过路由直接执行下游动作（尤其是任何写操作）。
</HARD-GATE>

1. **先路由后执行**：先运行 `route.py --query "..." --json`（或等价分类步骤）确认命中 skill，再进入执行阶段。
2. **Git 类请求强制走 superteam-git**：命中“提交/commit/push/提测/merge”等关键词时，只能通过 `superteam-git/scripts/query_git.py` 执行，不得直接调用 git 命令完成最终动作。
3. **执行前可追溯性**：未展示或记录路由结果（至少包含 `skill`、`script`、`score`）时，不得执行下游写操作。

### 多路由命中

`route.py` 对**每条**带关键词的规则独立计分：用户句子中出现该关键词则 `score += 1`。**所有 `score > 0` 的规则都会进入结果**，按分数降序排列（同分保持 `ROUTES` 中的声明顺序）。

- 分类结果 JSON：`routes` 数组（每项含 `skill`、`script`、`score` 等），并保留首条兼容字段 `skill` / `script`。
- `--execute`：**仅一条**命中时行为与以前相同（子进程直连终端 stdout/stderr）；**多条**命中时顺序执行各脚本，**最终 stdout 为一条 JSON**（`executions` 列表，含每步的 `stdout`/`stderr`/`exit_code`）。

## 意图路由规则

| 用户说 | 路由到 | 说明 |
|--------|--------|------|
| "PRD 里提到了什么功能？" | search_docs.py | 语义搜索，返回相关 chunks |
| "张三负责什么模块？" | search_docs.py | 从文档中搜索相关信息 |
| "团队有哪些后端开发？" | superteam-member/list_members.py | 返回团队成员列表 |
| "有哪些文档已同步？" | list_source_docs.py | 返回已同步源文档列表 |
| "张三在迭代25做了什么？" | `query_linear.py` | Linear 工单/周期（**不**走 superteam-data） |
| "帮我生成本周周报" | generate_report.py | 周报生成（骨架） |
| "团队周报 / 迭代周报" | generate_team_weekly_report.py | 团队迭代周报（Linear Cycle，同 superteam-report skill） |
| "pulse 快照 / sprint 日报" | snapshot_sprint.py | TREX-493 sprint daily pulse（`pulse-daily` 同脚本） |
| "PAI / pai 日报 / project lead 简报" | snapshot_pai.py | PAI v2 洞察（`superteam-report-insight`） |
| "更新看板 / 今日 pulse 全量" | run_pai.py | 全量 pulse 编排（`superteam-pai`，等同 daily） |
| "/superteam-pai" | run_pai.py | PAI 调度（自然语言 → plan → 子 skill；`superteam-pai`） |

### 触发关键词

| 路由目标 | 关键词 |
|----------|--------|
| superteam-data | 广告主、项目方、活动、campaign、投放、增长、拉新、邀请、provider、供应商、zktls、quest、alpha、白名单、badge、anchor、series、系列、链、chain、claim、可领取、reward、奖励、persona、人群、multiplier、倍率、project、项目配置、全局配置、global config |
| superteam-linear | 迭代、任务、进度、成员贡献、bug、缺陷、story point、sprint、iteration、task、做了哪些、负责什么任务、工作量、完成率、linear、issue、工单、backlog、cycle |
| superteam-report | **个人**：`周报`（单说默认个人）、个人周报、我的周报、研发周报、本周/上周周报、生成本周周报、工作总结、工作汇报、personal weekly、my weekly report。**团队**：团队周报、迭代周报、全团队周报、组织/部门周报、team weekly report、team report、cycle report（与团队短语同时出现时只跑团队脚本）。**Pulse**：pulse 快照、trex pulse、TREX-493、同步 pulse、sprint 日报、sprint 快照、pulse sprint → sprint 快照；**member**（仅显式）：member 快照、成员负载快照、pulse member |
| superteam-report-insight | PAI、pai 日报、pai 快照、pulse pai、project lead 简报、pl 简报、pulse-pai、生成 pai、pai 简报 |
| superteam-pai | `/superteam-pai`、`superteam-pai`、superteam pai；**编排**：更新看板、刷新看板、今日 pulse、pulse 全量、pulse 入库、编排 pulse、跑 daily |
| superteam-member/list_members | 成员、团队成员、谁是、有哪些人、角色、前端、后端 |
| list_source_docs | 文档列表、已同步、同步状态、有哪些文档 |
| search_docs | （以上均不匹配时的 fallback，适用于任何知识类问题） |

## 结果使用指引

Hub 脚本返回结构化数据，由调用方 agent 负责合成自然语言回答。以下是各脚本输出格式及使用建议。

### search_docs.py 输出

返回 JSON 信封：
```json
{
  "query": "原始查询",
  "skill": "superteam-knowledgebase",
  "total_results": 5,
  "results": [
    {
      "id": 123,
      "title": "文档标题",
      "content": "chunk 文本内容...",
      "doc_type": "tech-design",
      "source_type": "dingtalk",
      "source_url": "https://...",
      "file_name": "xxx.md",
      "score": 0.2341,
      "chunk_index": 3,
      "total_chunks": 12
    }
  ]
}
```

**Agent 合成要点：**
1. **按文档聚合**：同一 `title` 的多个 chunk 应合并理解，不要逐条罗列
2. **引用来源**：使用 `title` 和 `source_url` 标注信息出处，注明来源平台（`source_type`）
3. **评估相关性**：`score` < 0.3 表示高度相关，> 0.5 表示相关性较低；若所有结果 score 均 > 0.5，应提示用户"知识库中相关信息有限"
4. **多次搜索**：对复杂问题，可用不同关键词多次调用 search_docs，聚合多批结果后再合成回答

### 深度报告生成模式

<HARD-GATE>
当用户请求包含"生成"、"总结"、"整理"、"完整"、"全面"等关键词时，触发深度报告模式。
在此模式下，Agent 必须严格遵循以下规则，不得简化或跳过任何步骤。
</HARD-GATE>

**执行流程：**

1. **多维度搜索（至少 5 轮）**：用不同关键词覆盖主题的各个方面
   - 示例：如果用户问"战队设计方案"，至少搜索：
     - "战队设计方案 团队架构"
     - "战队搜索 加入审批 社媒展示"
     - "战队 前端设计 UI 组件"
     - "战队 后端接口 API"
     - "战队 数据库设计"
     - "战队 提测文档 版本记录"
2. **并行搜索**：尽可能并行发起多个搜索请求，提高效率
3. **去重聚合**：将同一文档的不同 chunk 合并理解，去除重复版本
4. **结构化输出**：直接输出完整的 Markdown 文档，包含：
   - 系统概述
   - 产品设计（PRD 要点）
   - 技术设计（前端、后端、数据库）
   - 实现历程与版本记录
   - 相关文档索引（放在文末）

**输出规范：**
- 不输出搜索过程的元信息（如"让我搜索一下"、"返回了 X 条结果"）
- 不逐条列出搜索结果
- 直接以专业文档的形式呈现整合后的内容
- 引用来源统一放在文末"相关文档索引"中
- 知识库中的信息不足时，明确标注"[知识库未覆盖]"而不是编造内容

### superteam-member/list_members.py 输出

返回 JSON 数组，每项包含 `user_id, username, real_name, role, created_at`。
Agent 按用户问题的上下文（角色、姓名等）筛选展示。

### 成员智能匹配流程

当用户提到具体人名（如"Peter"、"小王"、"彼得"）时，通过 `superteam-member/list_members.py resolve` 进行智能匹配，其中 `resolve` 子命令委托给 `superteam-member/core/super_member.py` 实现两级级联匹配：

```bash
python3 superteam-member/scripts/list_members.py resolve "Peter"
```

返回 JSON 数组，含 `user_id, username, real_name, real_name_en, role, aliases, match_type`（exact/fuzzy）。
命中后使用 `user_id` 进行后续操作（如 `search_docs.py --creator-id`）。未命中返回空数组。

**完整链路示例**：
```
用户: "Peter 本周做了什么"
  → superteam-member/list_members.py resolve "Peter" → 命中 user_id=3
  → search_docs.py --query "本周工作" --creator-id 3 --doc-type Plan
  → 汇总结果返回用户
```

### list_source_docs.py 输出

返回 JSON 数组，每项包含 `id, source_type, source_doc_id, file_name, last_edited_at, last_synced_at, sync_version`。
用于回答"有哪些文档"、"同步状态"等运维类问题。

## 动态数据安全原则

<HARD-GATE>
Hub 不得直接构造或执行 GraphQL query。
所有动态数据查询必须通过对应的 skill 执行。
Hub 只负责从用户输入中提取参数，传递给 skill 的预定义接口。
</HARD-GATE>

### 安全规则清单

1. **Query Only**：skill 只暴露查询，不暴露 mutation
2. **模板化查询**：GraphQL query 硬编码在 skill 脚本中，Hub/LLM 只传参数
3. **字段白名单**：skill 脚本过滤返回字段，不暴露敏感数据
4. **参数校验**：skill 脚本校验参数格式（如广告主 ID 必须 7 位数字）
5. **Introspection 禁止**：skill 脚本不得执行 schema introspection 查询

## 依赖

- superteam-knowledgebase（语义搜索、文档状态）
- superteam-member（成员查询、成员解析、成员管理）
- superteam-data（业务数据洞察，Superteam MCP agentic_data）
- superteam-report（周报生成，待实现）
