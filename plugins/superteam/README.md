# Superteam Plugin

> Build fully transparent & efficient **super-teams** with AI — open-source.

Superteam is a comprehensive AI-powered framework for knowledge base management and project analytics. It synchronizes documents from DingTalk, Google Drive, and Notion, manages project task data, and provides intelligent querying through semantic search (RAG) and graph-based relationship traversal (Apache AGE).

## Architecture (v3)

```
                          ┌─────────────────────────────┐
                          │          superteam ✅              │
                          │  route.py  关键词意图路由     │
                          └─────┬──────────┬────────────┘
                                │          │
               ┌────────────────┤          ├──────────────────┐
               ▼                ▼          ▼                  ▼
  ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ superteam-knowledgebase ✅ │  │superteam-data  │  │superteam-report │  │list_members  │
  │ RAG 语义搜索    │  │ MCP 业务数据  │  │ 🔨 周报生成   │  │ ✅ 成员管理   │
  │                 │  │ query_agentic │  │              │  │              │
  │ search_docs.py  │  │ _data.py      │  │gen_report.py │  │ resolve      │
  │ list_source_    │  │               │  │ --member     │  │ review       │
  │   docs.py       │  │               │  │ --week       │  │ alias        │
  └────────┬────────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
           │                  │                  │                  │
           │                  │                  │                  │
═══════════╪══════════════════╪══════════════════╪══════════════════╪═══════════
           │         ⚙️ 数据生产层（定时 / 手动）     │                  │
           │                                     │                  │
           │  ┌──────────────────────────────────────────────────┐  │
           │  │  superteam-sync ✅  run_capture.py                 │  │
           │  │  --step N · --dry-run · --only · hard-gate       │  │
           │  │                                                  │  │
           │  │  ┌──────────┐ ┌──────────────┐ ┌──────────┐     │  │
           │  │  │ sync-    │ │ sync-google- │ │ sync-    │     │  │
           │  │  │dingtalk- │ │ drive-kb ✅  │ │notion-   │     │  │
           │  │  │  kb ✅   │ │              │ │  kb ✅   │     │  │
           │  │  └────┬─────┘ └──────┬───────┘ └────┬─────┘     │  │
           │  │       │              │              │            │  │
           │  │       │   ┌──────────┴──────────┐   │            │  │
           │  │       │   │ v3: 作者智能识别      │   │            │  │
           │  │       └──▶│ _shared/             │◀──┘            │  │
           │  │           │ super_member.py ✅   │───────────────▶│  │
           │  │           │                     │                │  │
           │  │           │ exact → alias cache │  ┌──────────┐  │  │
           │  │           │ → dedup → LLM match │  │ sync-    │  │  │
           │  │           │ → create unverified  │  │task-data │  │  │
           │  │           └──────────┬──────────┘  │ 🔨       │  │  │
           │  │                      │             └──────────┘  │  │
           │  └──────────────────────┼───────────────────────────┘  │
           │                         │                              │
           │                         ▼                              │
           │  ┌─────────────────────────────────────────────────┐   │
           │  │  Per-doc Inline Pipeline ✅                      │   │
           │  │  _shared/pipeline.py                            │   │
           │  │                                                 │   │
           │  │  ┌───────────────────┐    ┌──────────────────┐  │   │
           │  │  │ process-doc-      │    │ process-doc-     │  │   │
           │  │  │ extract ✅        │    │ chunk ✅         │  │   │
           │  │  │                   │    │                  │  │   │
           │  │  │ v3: Unstructured  │    │ v3: LangChain   │  │   │
           │  │  │ PDF/DOCX/XLSX/   │    │ chunk_smart()    │  │   │
           │  │  │ PPTX → plaintext │    │ Markdown-aware   │  │   │
           │  │  │                   │    │ + classify (11类)│  │   │
           │  │  └─────────┬─────────┘    └────────┬─────────┘  │   │
           │  │            │                       │            │   │
           │  │            └───────────┬───────────┘            │   │
           │  │                        ▼                        │   │
           │  │               embedding (1536d)                 │   │
           │  │               DashScope / OpenAI                │   │
           │  └────────────────────────┬────────────────────────┘   │
           │                           │                            │
═══════════╪═══════════════════════════╪════════════════════════════╪═══════════
           │         💾 数据源 API 层    │                            │
           │                           │                            │
  ┌────────┴──────────┐                │                            │
  │ source-dingtalk-  │                │                            │
  │ document ✅       │                │                            │
  │ 钉钉文档 API      │                │                            │
  ├───────────────────┤                │                            │
  │ source-dingtalk-  │                │                            │
  │ spreadsheet ✅    │                │                            │
  │ 钉钉表格 API      │                │                            │
  ├───────────────────┤                │                            │
  │ source-dingtalk-  │                │                            │
  │ table 🔨          │                │                            │
  │ Notable API       │                │                            │
  └───────────────────┘                │                            │
                                       │                            │
═══════════════════════════════════════╪════════════════════════════╪═══════════
                    🗄️ 存储层 — RDS PostgreSQL (trex_hub)           │
                                       │                            │
  ┌────────────────────────────────────┴────────────────────────────┴────────┐
  │                                                                          │
  │  知识库 (superteam-store-kb-pgsql ✅)              成员系统 (v3 新增)               │
  │  ┌──────────────────────────────┐       ┌────────────────────────────┐  │
  │  │ kb_trex_source_docs          │       │ kb_trex_team_members       │  │
  │  │   source_type, file_name,    │  ┌───▶│   user_id, real_name,     │  │
  │  │   creator_id ──────────────────┘    │   real_name_en, email,     │  │
  │  │   source_url, metadata       │       │   aliases (JSONB),         │  │
  │  │                              │       │   verified ← v3            │  │
  │  │ kb_trex_team_docs            │       ├────────────────────────────┤  │
  │  │   + pgvector 1536d           │       │ kb_trex_member_aliases  v3 │  │
  │  │   + doc_type (11类)          │       │   (alias, platform)        │  │
  │  │   + creator_id               │       │   → user_id (LLM 学习缓存) │  │
  │  │                              │       ├────────────────────────────┤  │
  │  │ kb_trex_sync_failures        │       │ kb_trex_member_review_     │  │
  │  └──────────────────────────────┘       │   queue v3                 │  │
  │                                          │   new_member / merge       │  │
  │  任务管理 (superteam-sync-task-data 🔨)            │   pending → approved       │  │
  │  ┌──────────────────────────────┐       └────────────────────────────┘  │
  │  │ tm_iterations, tm_tasks,     │                                       │
  │  │ tm_task_members, tm_bugs     │       运维工具                         │
  │  │ tm_sync_state                │       ┌────────────────────────────┐  │
  │  │                              │       │ backfill_authors.py  v3    │  │
  │  │ 物化视图:                     │       │   --all --source X         │  │
  │  │   mv_member_iteration_summary│       │   --dry-run                │  │
  │  │   mv_iteration_progress      │       │   元数据回填 (不重新同步)    │  │
  │  │                              │       │                            │  │
  │  │ Apache AGE 图层: 🔨          │       │ populate_aliases.py        │  │
  │  │   task_graph                 │       │ backfill_doc_type.py       │  │
  │  │   Member─▶Task─▶Iteration   │       └────────────────────────────┘  │
  │  └──────────────────────────────┘                                       │
  │                                                                          │
  └──────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════

  🔧 共享模块 _shared/                     📊 数据流向

  config.py        统一配置加载              文档流 (v3 完整链路):
                   env > ~/.xxx/config       钉钉/GDrive/Notion
  super_member.py  v3 作者智能识别               ↓ sync-*-kb
                   4 级 fallback + LLM           ↓ SuperMember.resolve(author)
  pipeline.py      Per-doc inline pipeline       ↓ superteam-process-doc-extract (二进制→文本)
                   sync→extract→chunk→embed      ↓ chunk_smart (LangChain)
  chunking.py      v3 LangChain splitters        ↓ embed (1536d)
                   + classify (11类 doc_type)     ↓ superteam-store-kb-pgsql
  embedding.py     1536d 向量化                   ↓ superteam-knowledgebase (RAG)
                   DashScope / OpenAI
  db.py            PostgreSQL 连接管理       任务流 (🔨):
                                              钉钉多维表格 → superteam-sync-task-data
                                              → tm_* → AGE → 分析 / 周报等
                                              → 物化视图 → superteam-report

  状态: ✅ 已上线 | 🔨 骨架实现 | v3 = 本版新增/增强
```

## Naming Convention

| Prefix | Category | Purpose |
|--------|----------|---------|
| `source-` | 数据源 | Platform API wrapper (read-only) |
| `sync-` | 同步 | Platform → DB sync (含作者识别) |
| `process-` | 处理 | 文档提取 / 分块 / 分类 |
| `store-` | 存储 | DB 写入 / 搜索 / 回填 |
| `capture-` | 编排 | 多步骤同步编排 |
| `insight-` | 洞察 | 用户查询接口 (RAG / SQL / AGE) |
| `_shared/` | 共享 | 跨 skill 公共模块 (config, db, chunking, pipeline, super_member) |

## Skills (15)

| Skill | Category | Description | Key Scripts | Status |
|-------|----------|-------------|-------------|--------|
| **superteam** | 路由 | 意图识别 + 分发 | `route.py` | ✅ |
| **superteam-knowledgebase** | 洞察 | RAG 语义搜索 | `search_docs.py` `list_source_docs.py` | ✅ |
| **superteam-data** | 洞察 | 业务侧数据（活动/投放、badge、provider 等；非 Linear/研发任务） | `query_agentic_data.py` | ✅ |
| **superteam-report** | 生成 | 周报生成 | `generate_report.py` | 🔨 |
| **superteam-sync** | 编排 | 同步编排器 | `run_capture.py` | ✅ |
| **superteam-sync-dingtalk-kb** | 同步 | 钉钉 → KB (含作者识别) | `sync_dingtalk_to_kb.py` | ✅ |
| **superteam-sync-google-drive-kb** | 同步 | GDrive → KB (含二进制提取) | `sync_google_drive_to_kb.py` `drive_client.py` | ✅ |
| **superteam-sync-notion-kb** | 同步 | Notion → KB | `sync_notion_to_kb.py` `notion_api.py` | ✅ |
| **superteam-sync-task-data** | 同步 | 钉钉多维表 → PG + AGE | `sync_task_data.py` | 🔨 |
| **superteam-process-doc-chunk** | 处理 | v3: LangChain 智能分块 + 分类 (11类) | `chunk_doc.py` | ✅ |
| **superteam-process-doc-extract** | 处理 | v3: Unstructured 二进制提取 | `content_extractor.py` | ✅ |
| **superteam-store-kb-pgsql** | 存储 | pgvector 向量存储 + 回填工具 | `ingest_doc.py` `backfill_authors.py` | ✅ |
| **superteam-source-dingtalk-document** | 数据源 | 钉钉文档 API | `read_node.py` | ✅ |
| **superteam-source-dingtalk-spreadsheet** | 数据源 | 钉钉表格 API | `read_spreadsheet.py` | ✅ |
| **superteam-source-dingtalk-table** | 数据源 | 钉钉多维表格 Notable API | `read_notable.py` | 🔨 |

## Project Structure

```
superteam/
├── .claude-plugin/plugin.json
├── pytest.ini
├── sql/
│   ├── 001_create_sync_failures.sql
│   ├── 002_add_source_url.sql
│   ├── 003_task_management.sql
│   └── 004_smart_author.sql              ← v3: aliases + review queue
├── docs/
│   ├── README.md                          文档索引
│   ├── guides/                            说明文档（安装、场景、介绍等）
│   ├── architecture/                    架构设计（总览图、superpowers 计划与规格）
│   └── skills-design/                   单技能/能力设计
├── skills/
│   ├── _shared/                           共享模块
│   │   ├── config.py                        统一配置
│   │   ├── db.py                            PG 连接
│   │   ├── embedding.py                     向量化 (1536d)
│   │   ├── chunking.py                      v3: LangChain chunk_smart
│   │   ├── pipeline.py                      Per-doc inline pipeline
│   │   ├── super_member.py                  v3: 作者智能识别 (4级 fallback)
│   │   └── tests/                           6 个测试模块 (55+ tests)
│   ├── superteam/                               意图路由
│   ├── superteam-knowledgebase/                      RAG 搜索 + 成员管理 CLI
│   │   └── scripts/
│   │       ├── search_docs.py
│   │       ├── list_members.py              v3: resolve/review/alias 子命令
│   │       └── list_source_docs.py
│   ├── superteam-data/                      业务数据洞察 (MCP 桥接) ✅
│   │   └── scripts/query_agentic_data.py
│   ├── superteam-report/                     周报生成 🔨
│   ├── superteam-sync/                      同步编排
│   ├── superteam-sync-dingtalk-kb/                  钉钉同步 (含 SuperMember)
│   ├── superteam-sync-google-drive-kb/              GDrive 同步 (含 owners 提取)
│   ├── superteam-sync-notion-kb/                    Notion 同步 (含 created_by)
│   ├── superteam-sync-task-data/                    任务数据同步 🔨
│   ├── superteam-process-doc-chunk/                 智能分块 + 分类
│   ├── superteam-process-doc-extract/               二进制文档提取 (Unstructured)
│   ├── superteam-store-kb-pgsql/                    向量存储 + 运维工具
│   │   └── scripts/
│   │       ├── ingest_doc.py
│   │       ├── search_docs.py
│   │       ├── backfill_authors.py          v3: 作者回填 (元数据)
│   │       ├── populate_aliases.py
│   │       └── verify.py
│   ├── superteam-source-dingtalk-document/          钉钉文档 API
│   ├── superteam-source-dingtalk-spreadsheet/       钉钉表格 API
│   └── superteam-source-dingtalk-table/             钉钉多维表格 API 🔨
├── MIGRATION.md
└── README.md
```

## v3 Changes (2026-03)

| Feature | What Changed | Design Doc |
|---------|-------------|------------|
| **Smart Author Resolve** | 4-step fallback: exact → alias → dedup → LLM (qwen-plus). All 3 sync scripts extract author, `SuperMember.resolve()` always returns user_id. Post-sync review queue. `backfill_authors.py` for existing data. | `docs/architecture/superpowers/specs/2026-03-20-smart-author-resolve-design.md` |
| **Smart Chunking** | `chunk_text()` → `chunk_smart()` (LangChain). Markdown-aware splitting, sentence boundary respect, auto-detect format. | `docs/architecture/superpowers/specs/2026-03-19-smart-chunking-design.md` |
| **Binary Format Extraction** | PDF/DOCX/XLSX/PPTX via Unstructured. Coverage 57% → 90%+. | `docs/architecture/superpowers/specs/2026-03-17-file-format-extraction-design.md` |
| **Google Drive Sync** | Service Account auth, incremental sync, batch + resume, binary format support. | `docs/architecture/superpowers/specs/2026-03-17-google-drive-sync-design.md` |
| **Test Coverage** | 200+ unit tests across 15 skills, pure mock, zero external deps. | `docs/architecture/superpowers/specs/2026-03-19-test-completion-design.md` |

### SQL Migrations

| # | File | Purpose |
|---|------|---------|
| 001 | `create_sync_failures.sql` | Sync failure tracking |
| 002 | `add_source_url.sql` | Source URL for all docs |
| 003 | `task_management.sql` | Task/iteration/bug tables + AGE graph |
| 004 | `smart_author.sql` | v3: member aliases, review queue, email/verified columns |
